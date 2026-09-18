"""Real command-source behavior under the headless import/network guards."""

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
        # Reuse A04's 39-field sample vocabulary; no new statistics contract.
        values = {"source": engine.projection_snapshot(source), "target": engine.projection_snapshot(target)}
        if source.commandBonuses or target.commandBonuses:
            raise ValueError("Finished fit retains unconsumed command bonuses")
        return values

    result = {"initial": snapshot()}
    for step in case["steps"]:
        op = step["operation"]
        if op == "add":
            engine.add_command(source, target)
        elif op == "command_state":
            engine.set_command_active(source, target, step["active"])
        elif op == "skill":
            engine.set_skill_level(source, step["skill"], step["level"])
        elif op == "implant_add":
            engine.add_implant(source, step["implant"])
        elif op == "implant_state":
            engine.set_implant_active(source, step["slot"], step["active"])
        elif op == "implant_remove":
            engine.remove_implant(source, step["slot"])
        elif op == "module_state":
            engine.set_module_states(source, step["module_indices"], step["state"])
        elif op == "charges":
            engine.set_charges(source, step["module_indices"], step["charge"])
        elif op == "remove":
            engine.remove_command(source, target)
        else:
            raise ValueError("Unknown command scenario operation")
        result[step["name"]] = snapshot()
    return result


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.source = ENGINE.create_fit(deepcopy(EXPECTED["inputs"]["source"]))
        self.target = ENGINE.create_fit(deepcopy(EXPECTED["inputs"]["target"]))

    def state(self, name, fit=None, role="target"):
        fit = fit or self.target
        compare(EXPECTED["states"][name][role], ENGINE.projection_snapshot(fit))
        self.assertEqual(fit.commandBonuses, {})

    def test_all_desktop_states_and_units(self):
        compare(EXPECTED["states"], sample(ENGINE, EXPECTED["inputs"]))

    def test_skill_and_implant_changes_refresh_all_recipients(self):
        other = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        unlinked = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        for target in (self.target, other):
            ENGINE.add_command(self.source, target)
            self.state("applied", target)
        ENGINE.set_skill_level(self.source, "Shield Command Specialist", 4)
        self.state("specialist_4", other)
        self.state("specialist_4")
        ENGINE.set_skill_level(self.source, "Shield Command Specialist", 5)
        ENGINE.add_implant(self.source, "Shield Command Mindlink")
        self.state("mindlink_added")
        self.state("mindlink_added", other)
        ENGINE.set_implant_active(self.source, 10, False)
        self.state("applied", other)
        self.state("applied")
        ENGINE.set_implant_active(self.source, 10, True)
        self.state("mindlink_added", other)
        self.state("mindlink_added")
        self.state("initial", unlinked)
        # Each created fit has its own synthetic character and implant list.
        self.assertEqual(self.target.character.getSkill("Shield Command Specialist").level, 5)
        self.assertEqual(len(self.target.implants), 0)

    def test_charge_and_module_state_changes_refresh_all_remaining_recipients(self):
        other = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        for target in (self.target, other):
            ENGINE.add_command(self.source, target)
        ENGINE.add_implant(self.source, "Shield Command Mindlink")
        ENGINE.set_charges(self.source, [1], "Shield Harmonizing Charge")
        self.state("harmonizing", other)
        self.state("harmonizing")
        ENGINE.set_module_states(self.source, [1], "ONLINE")
        self.state("initial")
        self.state("initial", other)
        ENGINE.remove_command(self.source, self.target)
        ENGINE.set_charges(self.source, [1], "Shield Extension Charge")
        ENGINE.set_module_states(self.source, [1], "ACTIVE")
        self.state("mindlink_added", other)
        self.state("initial")
        self.assertNotIn(self.target.ID, self.source.boostedOnto)
        self.assertIn(other.ID, self.source.boostedOnto)

    def test_link_state_changes_only_the_selected_recipient(self):
        other = ENGINE.create_fit(EXPECTED["inputs"]["target"])
        ENGINE.add_command(self.source, self.target, active=False)
        ENGINE.add_command(self.source, other)
        self.state("initial")
        self.state("applied", other)
        ENGINE.set_command_active(self.source, self.target, True)
        ENGINE.set_command_active(self.source, other, False)
        self.state("initial", other)
        self.state("applied")

    def test_repeated_apply_remove_clears_relationships_and_bonuses(self):
        for _ in range(5):
            ENGINE.add_command(self.source, self.target)
            self.state("applied")
            ENGINE.remove_command(self.source, self.target)
            self.assertEqual(dict(self.target.commandFitDict), {})
            self.assertEqual(dict(self.source.boostedOnto), {})
            self.state("initial")
            self.state("initial", self.source, "source")

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
            # ORM refresh can replace a collected module with an uncalculated
            # object even though its owning fit still says it is calculated.
            gc.collect()
            collected.append(previous() is None)

        with patch.object(session, "refresh", side_effect=refresh_and_collect):
            for operation, recipient, first, second in (
                    (ENGINE.add_command, self.target, True, False),
                    (ENGINE.add_command, other, True, True),
                    (ENGINE.remove_command, self.target, False, True),
                    (ENGINE.remove_command, other, False, False)):
                operation(self.source, recipient)
                for fit, linked in ((other, second), (self.target, first), (unlinked, False)):
                    self.state("applied" if linked else "initial", fit)
                    self.assertEqual(set(fit.commandFitDict), {self.source.ID} if linked else set())
                self.state("applied" if first or second else "initial", self.source, "source")
                self.assertEqual(set(self.source.boostedOnto),
                                 {fit.ID for fit, linked in ((self.target, first), (other, second)) if linked})
        self.assertEqual(collected, [True] * 4)

    def test_invalid_link_inputs_and_duplicates_preserve_existing_bonuses(self):
        with self.assertRaises(ValueError):
            ENGINE.add_command(self.source, self.target, active=1)
        self.assertEqual(dict(self.target.commandFitDict), {})
        self.assertEqual(dict(self.source.boostedOnto), {})
        ENGINE.add_command(self.source, self.target)
        with self.assertRaises(ValueError):
            ENGINE.add_command(self.source, self.target, active=False)
        for active in (None, 0, "False"):
            with self.subTest(active=active), self.assertRaises(ValueError):
                ENGINE.set_command_active(self.source, self.target, active)
        self.assertIs(self.source.getCommandInfo(self.target.ID).active, True)
        self.state("applied")
        ENGINE.remove_command(self.source, self.target)
        with self.assertRaises(ValueError):
            ENGINE.set_command_active(self.source, self.target, True)
        with self.assertRaises(ValueError):
            ENGINE.remove_command(self.source, self.target)
        self.state("initial")

    def test_invalid_source_edits_do_not_partially_change_source_or_recipients(self):
        ENGINE.add_command(self.source, self.target)
        for skill, level in (("Shield Command Specialist", True), ("Command Ships", 6),
                             ("Command Ships", -1), ("A05 missing skill", 4), ("Vulture", 4)):
            with self.subTest(skill=skill, level=level), self.assertRaises(ValueError):
                ENGINE.set_skill_level(self.source, skill, level)
        # Railgun can overheat; command burst cannot. A naive loop changes the
        # first module before noticing the second is incompatible.
        for indices, state in (([0, 1], "OVERHEATED"), ([1, 999], "ONLINE"),
                               ([False], "ONLINE"), ([1, 1], "ONLINE"), ([], "ONLINE"), ([1], "invalid")):
            with self.subTest(indices=indices, state=state), self.assertRaises(ValueError):
                ENGINE.set_module_states(self.source, indices, state)
        with self.assertRaises(ValueError):
            ENGINE.set_charges(self.source, [1, 0], "Shield Harmonizing Charge")
        self.state("applied")
        self.state("applied", self.source, "source")
        self.assertEqual(self.source.character.getSkill("Command Ships").level, 5)

    def test_implant_slot_rejections_and_repeated_removal_preserve_effects(self):
        ENGINE.add_command(self.source, self.target)
        for _ in range(3):
            ENGINE.add_implant(self.source, "Shield Command Mindlink")
            self.state("mindlink_added")
            for name in ("Shield Command Mindlink", "Information Command Mindlink", "Vulture"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    ENGINE.add_implant(self.source, name)
            with self.assertRaises(ValueError):
                ENGINE.set_implant_active(self.source, 10, 0)
            with self.assertRaises(ValueError):
                ENGINE.remove_implant(self.source, True)
            self.assertEqual(len(self.source.implants), 1)
            self.assertIs(self.source.implants[0].active, True)
            self.state("mindlink_added")
            ENGINE.remove_implant(self.source, 10)
            self.assertEqual(len(self.source.implants), 0)
            self.state("applied")
        with self.assertRaises(ValueError):
            ENGINE.set_implant_active(self.source, 10, True)
        with self.assertRaises(ValueError):
            ENGINE.remove_implant(self.source, 10)
        with self.assertRaises(ValueError):
            ENGINE.add_implant(self.source, "Shield Command Mindlink", active=1)
        self.state("applied")

    def test_wrong_thread_and_foreign_handles_fail_before_mutation(self):
        for source, target in ((object(), self.target), (self.source, object())):
            with self.assertRaises(ValueError):
                ENGINE.add_command(source, target)
        errors = []

        def attempt():
            try:
                ENGINE.add_command(self.source, self.target)
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertEqual(dict(self.target.commandFitDict), {})
        self.state("initial")
