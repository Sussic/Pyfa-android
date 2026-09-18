"""Real EOS projection regressions, run under check.py's import/network guards."""

from copy import deepcopy
import gc
import threading
import unittest
from unittest.mock import patch
import weakref

from tools.android_reference.reference import compare

ENGINE = None
EXPECTED = None


def sample(engine, case):
    source, target = engine.create_fit(case["source"]), engine.create_fit(case["target"])

    def snapshot():
        return {"source": engine.projection_snapshot(source), "target": engine.projection_snapshot(target)}

    result = {"initial": snapshot()}
    for step in case["steps"]:
        op = step["operation"]
        if op in ("add", "configure"):
            method = engine.add_projection if op == "add" else engine.configure_projection
            method(source, target, range_m=step["range_m"], active=step["active"], amount=step["amount"])
        elif op == "charges":
            engine.set_charges(source, step["module_indices"], step["charge"])
        elif op == "remove":
            engine.remove_projection(source, target)
        else:
            raise ValueError("Unknown adapter scenario operation")
        result[step["name"]] = snapshot()
    return result


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.source = ENGINE.create_fit(deepcopy(EXPECTED["inputs"]["source"]))
        self.target = ENGINE.create_fit(deepcopy(EXPECTED["inputs"]["target"]))

    def state(self, name, fit=None, role="target"):
        compare(EXPECTED["states"][name][role], ENGINE.projection_snapshot(fit or self.target))

    def test_all_desktop_states_and_units(self):
        compare(EXPECTED["states"], sample(ENGINE, EXPECTED["inputs"]))

    def test_source_script_edit_updates_all_recipients_and_preserves_unlinked_fit(self):
        other = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        unlinked = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        for target in (self.target, other):
            ENGINE.add_projection(self.source, target)
            self.state("applied_zero", target)
        ENGINE.set_charges(self.source, [1], "Scan Resolution Dampening Script")
        # Read in reverse order; the first recipient must not consume invalidation
        # for the second. No manual target clear/recalc is allowed in this test.
        self.state("script_changed", other)
        self.state("script_changed")
        self.state("initial", unlinked)
        ENGINE.remove_projection(self.source, self.target)
        ENGINE.set_charges(self.source, [1], "Targeting Range Dampening Script")
        self.state("applied_zero", other)
        self.state("initial")
        self.assertNotIn(self.target.ID, self.source.projectedOnto)
        self.assertIn(other.ID, self.source.projectedOnto)

    def test_invalid_options_do_not_change_an_existing_projection(self):
        ENGINE.add_projection(self.source, self.target, range_m=100000.0)
        bad = [(value, False, 1) for value in (-1, True, "100", float("nan"), float("inf"))]
        bad += [(0.0, 1, 1), (0.0, False, 0), (0.0, False, True), (0.0, False, 1.5)]
        for distance, active, amount in bad:
            with self.subTest(distance=distance, active=active, amount=amount):
                with self.assertRaises(ValueError):
                    ENGINE.configure_projection(self.source, self.target, range_m=distance, active=active, amount=amount)
                info = self.source.getProjectionInfo(self.target.ID)
                self.assertEqual((info.projectionRange, info.active, info.amount), (100000.0, True, 1))
                self.state("falloff")

    def test_invalid_add_and_duplicate_do_not_create_or_replace_links(self):
        with self.assertRaises(ValueError):
            ENGINE.add_projection(self.source, self.target, range_m=-1)
        self.assertEqual(dict(self.target.projectedFitDict), {})
        self.assertEqual(dict(self.source.projectedOnto), {})
        ENGINE.add_projection(self.source, self.target, range_m=100000.0)
        with self.assertRaises(ValueError):
            ENGINE.add_projection(self.source, self.target)
        self.state("falloff")
        ENGINE.remove_projection(self.source, self.target)
        with self.assertRaises(ValueError):
            ENGINE.configure_projection(self.source, self.target, range_m=0, active=True, amount=1)
        self.state("initial")

    def test_repeated_apply_remove_clears_both_relationships_and_all_values(self):
        for _ in range(5):
            ENGINE.add_projection(self.source, self.target)
            self.state("applied_zero")
            ENGINE.remove_projection(self.source, self.target)
            self.assertEqual(dict(self.target.projectedFitDict), {})
            self.assertEqual(dict(self.source.projectedOnto), {})
            self.state("initial")
            self.state("initial", self.source, "source")
        with self.assertRaises(ValueError):
            ENGINE.remove_projection(self.source, self.target)
        self.state("initial")

    def test_relationship_refresh_recalculates_collected_source_modules(self):
        import eos.db
        other = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        unlinked = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        session = eos.db.saveddata_session
        refresh = session.refresh
        collected = []

        def refresh_and_collect(instance, *args, **kwargs):
            previous = weakref.ref(instance.modules[0])
            refresh(instance, *args, **kwargs)
            # ORM refresh expires the module collection. Force the old module
            # out of its weak identity map before the adapter reads it again.
            gc.collect()
            collected.append(previous() is None)

        with patch.object(session, "refresh", side_effect=refresh_and_collect):
            for operation, recipient, first, second in (
                    (ENGINE.add_projection, self.target, True, False),
                    (ENGINE.add_projection, other, True, True),
                    (ENGINE.remove_projection, self.target, False, True),
                    (ENGINE.remove_projection, other, False, False)):
                operation(self.source, recipient)
                for fit, linked in ((other, second), (self.target, first), (unlinked, False)):
                    self.state("applied_zero" if linked else "initial", fit)
                    self.assertEqual(set(fit.projectedFitDict), {self.source.ID} if linked else set())
                self.state("applied_zero" if first or second else "initial", self.source, "source")
                self.assertEqual(set(self.source.projectedOnto),
                                 {fit.ID for fit, linked in ((self.target, first), (other, second)) if linked})
        self.assertEqual(collected, [True] * 4)

    def test_rejected_mixed_source_charge_edit_preserves_projected_effects(self):
        ENGINE.add_projection(self.source, self.target)
        with self.assertRaises(ValueError):
            ENGINE.set_charges(self.source, [1, 0], "Scan Resolution Dampening Script")
        self.state("applied_zero")
        self.state("applied_zero", self.source, "source")

    def test_link_edits_are_local_to_the_selected_recipient(self):
        other = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        ENGINE.add_projection(self.source, self.target)
        ENGINE.add_projection(self.source, other)
        ENGINE.configure_projection(self.source, self.target, range_m=300000.0, active=True, amount=1)
        self.state("distant")
        self.state("applied_zero", other)
        ENGINE.configure_projection(self.source, self.target, range_m=0, active=False, amount=1)
        self.state("initial")
        self.state("applied_zero", other)

    def test_wrong_thread_and_foreign_handles_fail_before_mutation(self):
        for source, target in ((object(), self.target), (self.source, object())):
            with self.assertRaises(ValueError):
                ENGINE.add_projection(source, target)
        errors = []

        def attempt():
            try:
                ENGINE.add_projection(self.source, self.target)
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertEqual(dict(self.target.projectedFitDict), {})
        self.state("initial")
