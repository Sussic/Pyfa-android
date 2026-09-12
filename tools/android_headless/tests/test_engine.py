"""Real EOS regression cases; configured/run by ../check.py in a fresh process."""

from copy import deepcopy
import sys
import threading
import unittest

from tools.android_reference.reference import compare

ENGINE = None
EXPECTED = None


def fit_spec(case):
    spec = deepcopy(case)
    del spec["edit"]
    return spec


def sample(engine, case):
    fit = engine.create_fit(fit_spec(case))
    initial = engine.snapshot(fit)
    engine.set_charges(fit, case["edit"]["module_indices"], case["edit"]["charge"])
    changed = engine.snapshot(fit)
    # Restore each original charge; the fixture currently uses identical guns.
    for index in case["edit"]["module_indices"]:
        engine.set_charges(fit, [index], case["modules"][index].get("charge"))
    return {"initial": initial, "iron_ammunition": changed, "restored": engine.snapshot(fit)}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.fit = ENGINE.create_fit(fit_spec(EXPECTED["inputs"]))
        self.before = ENGINE.snapshot(self.fit)

    def test_reference_states_and_units(self):
        compare(EXPECTED["states"], sample(ENGINE, EXPECTED["inputs"]))

    def test_incompatible_mixed_selection_does_not_partially_change_guns(self):
        # Gun followed by afterburner: a naive loop would change the gun first.
        with self.assertRaises(ValueError):
            ENGINE.set_charges(self.fit, [0, 3], "Iron Charge M")
        compare(self.before, ENGINE.snapshot(self.fit))
        self.assertEqual(self.fit.modules[0].charge.ID, EXPECTED["resolved_item_ids"]["Antimatter Charge M"])

    def test_invalid_selection_and_unknown_ammo_preserve_fit(self):
        for indices, charge in (([0, 999], "Iron Charge M"), ([False], "Iron Charge M"),
                                ([0, 0], "Iron Charge M"), ([], "Iron Charge M"),
                                ([0, 1], "A03 nonexistent ammunition")):
            with self.subTest(indices=indices, charge=charge):
                with self.assertRaises(ValueError):
                    ENGINE.set_charges(self.fit, indices, charge)
                compare(self.before, ENGINE.snapshot(self.fit))

    def test_unsupported_features_and_unknown_fields_are_rejected(self):
        for field in ("implants", "boosters", "projections", "commands", "environments", "target_profile", "unknown_option"):
            spec = fit_spec(EXPECTED["inputs"])
            spec[field] = ["not implemented"]
            with self.subTest(field=field), self.assertRaises(ValueError):
                ENGINE.create_fit(spec)
        compare(self.before, ENGINE.snapshot(self.fit))

    def test_invalid_inputs_do_not_poison_later_fit_creation(self):
        for field, value in (("skill_level", True), ("factor_reload", 1), ("modules", None)):
            spec = fit_spec(EXPECTED["inputs"])
            spec[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                ENGINE.create_fit(spec)
        spec = fit_spec(EXPECTED["inputs"])
        spec["drones"][0]["active"] = 6
        with self.assertRaises(ValueError):
            ENGINE.create_fit(spec)
        compare(self.before, ENGINE.snapshot(ENGINE.create_fit(fit_spec(EXPECTED["inputs"]))))

    def test_separate_fits_do_not_share_charge_edits(self):
        other = ENGINE.create_fit(fit_spec(EXPECTED["inputs"]))
        ENGINE.set_charges(self.fit, [0, 1], "Iron Charge M")
        compare(EXPECTED["states"]["iron_ammunition"], ENGINE.snapshot(self.fit))
        compare(self.before, ENGINE.snapshot(other))

    def test_game_database_is_read_only(self):
        import eos.db
        with eos.db.gamedata_engine.connect() as connection:
            from sqlalchemy.exc import OperationalError
            with self.assertRaises(OperationalError):
                connection.execute("UPDATE metadata SET field_value='changed' WHERE field_name='client_build'")
        self.assertEqual(ENGINE.metadata["client_build"], EXPECTED["dataset_metadata"]["client_build"])

    def test_reinitialization_and_wrong_thread_fail_before_engine_work(self):
        from android_bridge import HeadlessEngine
        with self.assertRaises(RuntimeError):
            HeadlessEngine(ENGINE.database)
        errors = []

        def attempt():
            try:
                ENGINE.set_charges(self.fit, [0, 1], "Iron Charge M")
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        compare(self.before, ENGINE.snapshot(self.fit))

    def test_current_schema_check_does_not_import_desktop_config(self):
        import eos.db
        from eos.db import migration
        eos.db.saveddata_engine.execute("PRAGMA user_version = {}".format(migration.getAppVersion()))
        migration.update(eos.db.saveddata_engine)
        self.assertNotIn("config", sys.modules)
        self.assertNotIn("wx", sys.modules)

    def test_missing_database_is_not_created(self):
        from pathlib import Path
        import tempfile
        from android_bridge import HeadlessEngine
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.db"
            with self.assertRaises(FileNotFoundError):
                HeadlessEngine(missing)
            self.assertFalse(missing.exists())
