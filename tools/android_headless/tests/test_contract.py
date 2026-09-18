"""Real EOS contract, revision and failure-recovery regressions."""
from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import patch

from android_bridge.contract import BridgeSession
from tools.android_reference.reference import compare

ENGINE = None
CASES = None
EXPECTED = None


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.bridge = BridgeSession(ENGINE)
        self.serial = 0

    def tearDown(self):
        import eos.db
        self.bridge._reset_storage()
        eos.db.saveddata_session.commit()

    def envelope(self, operation, arguments, revisions=None):
        self.serial += 1
        named = {arguments[key] for key in ("fit_id", "source_id", "target_id") if key in arguments}
        return {"version": 1, "request_id": str(self.serial), "session_id": self.bridge.session_id,
                "operation": operation, "arguments": arguments,
                "expected_revisions": {key: self.bridge._revisions[key] for key in named} if revisions is None else revisions}

    def send(self, operation, arguments, code=None, revisions=None):
        request = self.envelope(operation, arguments, revisions)
        result = json.loads(self.bridge.dispatch(json.dumps(request)))
        self.assertEqual(result["request_id"], request["request_id"])
        self.assertEqual(result["session_id"], self.bridge.session_id)
        if code:
            self.assertEqual(result["status"], "error", result)
            self.assertEqual(result["error"]["code"], code, result)
            self.assertEqual(result["fits"], [])
        else:
            self.assertEqual(result["status"], "ok", result)
            self.assertIsNone(result["error"])
        return result

    def create(self, kind="ammunition", role=None):
        spec = deepcopy(CASES[kind] if role is None else CASES[kind][role])
        spec.pop("edit", None)
        return self.send("create_fit", {"spec": spec})["fits"][0]["id"]

    def current(self):
        return self.send("snapshot", {"fit_ids": []})["fits"]

    def assert_restored(self, previous):
        self.assertEqual(previous, self.current())
        self.assertEqual(len(previous), len(ENGINE._fits))
        self.assertEqual(len(previous), len(self.bridge._fits))

    def fail_after(self, owner, method):
        original = getattr(owner, method)
        calls = 0

        def failure(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = original(*args, **kwargs)
            if calls == 1:
                raise RuntimeError("Injected failure after real " + method)
            return result
        return patch.object(owner, method, side_effect=failure)

    def pair_stats(self, source, target, expected):
        fits = self.send("snapshot", {"fit_ids": [source, target]})["fits"]
        compare(expected, {"source": fits[0]["stats"], "target": fits[1]["stats"]})

    def test_adopts_existing_sample_without_duplicate_objects(self):
        spec = deepcopy(CASES["ammunition"])
        spec.pop("edit")
        fit = ENGINE.create_fit(spec)
        self.bridge = BridgeSession(ENGINE, fit, spec)
        response = json.loads(self.bridge.bootstrap())
        self.assertEqual(response["request_id"], "bootstrap")
        self.assertEqual(len(response["fits"]), 1)
        self.assertIs(self.bridge.get_fit(self.bridge.sample_id), fit)
        self.assertEqual(response["fits"][0]["revision"], 1)
        self.assertEqual(len(ENGINE._fits), 1)

    def test_wire_rejections_have_no_partial_state(self):
        fit = self.create()
        before = self.current()
        base = self.envelope("snapshot", {"fit_ids": []})
        rows = [("{", "INVALID_REQUEST"), ("[" * 1500 + "]" * 1500, "INVALID_REQUEST")]
        for key, value, code in (("version", True, "INVALID_REQUEST"), ("version", 2, "UNSUPPORTED_VERSION"),
                                 ("operation", "unknown", "UNKNOWN_OPERATION"),
                                 ("session_id", "old-session", "REVISION_CONFLICT"),
                                 ("expected_revisions", {fit: 1}, "INVALID_REQUEST")):
            rows.append((json.dumps({**base, key: value}), code))
        rows += [(json.dumps(base)[:-1] + ',"version":1}', "INVALID_REQUEST"),
                 (json.dumps({**base, "arguments": {"fit_ids": [fit, fit]}}), "INVALID_REQUEST"),
                 (json.dumps({**base, "arguments": {"fit_ids": ["missing"]}}), "UNKNOWN_FIT")]
        for text, code in rows:
            with self.subTest(code=code, text=text[:100]):
                result = json.loads(self.bridge.dispatch(text))
                self.assertEqual(result["error"]["code"], code)
                self.assertEqual(result["fits"], [])
        self.send("set_skill_level", {"fit_id": fit, "skill": "Gunnery", "level": True}, "INVALID_REQUEST")
        self.send("set_skill_level", {"fit_id": fit, "skill": "Gunnery", "level": 4}, "REVISION_CONFLICT", {fit: 0})
        self.send("set_skill_level", {"fit_id": fit, "skill": "Gunnery", "level": 4}, "INVALID_REQUEST", {})
        self.assert_restored(before)

    def test_bulk_ammunition_matches_a01_and_rejects_mixed_selection(self):
        fit = self.create()
        for name, stage in ((CASES["ammunition"]["edit"]["charge"], "iron_ammunition"),
                            (CASES["ammunition"]["modules"][0]["charge"], "restored")):
            snapshot = self.send("set_charges", {"fit_id": fit, "module_indices": [0, 1], "charge": name})["fits"][0]
            compare(EXPECTED["ammunition"]["states"][stage],
                    {key: value for key, value in snapshot["stats"].items() if key != "scan_resolution"})
            self.assertEqual([module["charge"] for module in snapshot["modules"][:2]], [name, name])
        before = self.current()
        self.send("set_charges", {"fit_id": fit, "module_indices": [0, 2], "charge": "Iron Charge M"}, "INVALID_EDIT")
        self.assert_restored(before)

    def test_all_projection_reference_states(self):
        source, target = self.create("projection", "source"), self.create("projection", "target")
        self.pair_stats(source, target, EXPECTED["projection"]["states"]["initial"])
        for step in CASES["projection"]["steps"]:
            op = step["operation"]
            if op in ("add", "configure"):
                self.send("add_projection" if op == "add" else "configure_projection",
                          {"source_id": source, "target_id": target,
                           **{key: step[key] for key in ("range_m", "active", "amount")}})
            elif op == "charges":
                self.send("set_charges", {"fit_id": source, "module_indices": step["module_indices"], "charge": step["charge"]})
            else:
                self.send("remove_projection", {"source_id": source, "target_id": target})
            self.pair_stats(source, target, EXPECTED["projection"]["states"][step["name"]])

    def test_all_command_reference_states(self):
        source, target = self.create("command", "source"), self.create("command", "target")
        self.pair_stats(source, target, EXPECTED["command"]["states"]["initial"])
        operations = {"add": "add_command", "command_state": "set_command_active", "skill": "set_skill_level",
                      "implant_add": "add_implant", "implant_state": "set_implant_active",
                      "implant_remove": "remove_implant", "module_state": "set_module_states",
                      "charges": "set_charges", "remove": "remove_command"}
        for step in CASES["command"]["steps"]:
            op = step["operation"]
            args = {key: value for key, value in step.items() if key not in ("operation", "name")}
            args.update({"source_id": source, "target_id": target} if op in ("add", "command_state", "remove") else {"fit_id": source})
            if op in ("add", "implant_add"):
                args["active"] = True
            self.send(operations[op], args)
            self.pair_stats(source, target, EXPECTED["command"]["states"][step["name"]])

    def test_revisions_cover_transitive_union_graph_and_leave_unrelated_fits(self):
        source = self.create("projection", "source")
        middle, target, unrelated = self.create(), self.create(), self.create()
        self.send("add_projection", {"source_id": source, "target_id": middle, "range_m": 0, "active": True, "amount": 1})
        self.send("add_command", {"source_id": middle, "target_id": target, "active": False})
        before = dict(self.bridge._revisions)
        result = self.send("set_charges", {"fit_id": source, "module_indices": [1], "charge": "Scan Resolution Dampening Script"})
        self.assertEqual([fit["id"] for fit in result["fits"]], [source, middle, target])
        self.assertEqual(self.bridge._revisions, {key: revision + (key != unrelated) for key, revision in before.items()})
        before = dict(self.bridge._revisions)
        result = self.send("remove_projection", {"source_id": source, "target_id": middle})
        self.assertEqual([fit["id"] for fit in result["fits"]], [source, middle, target])
        self.assertEqual(self.bridge._revisions, {key: revision + (key != unrelated) for key, revision in before.items()})
        ordered = self.send("snapshot", {"fit_ids": [unrelated, source]})
        self.assertEqual([fit["id"] for fit in ordered["fits"]], [unrelated, source])

    def test_create_failure_after_real_creation_recovers_last_snapshot(self):
        self.create()
        before = self.current()
        with self.fail_after(ENGINE, "create_fit"):
            spec = deepcopy(CASES["projection"]["source"])
            self.send("create_fit", {"spec": spec}, "ENGINE_ERROR")
        self.assert_restored(before)
        spec["modules"].append({"name": "B01 nonexistent module", "state": "ONLINE"})
        self.send("create_fit", {"spec": spec}, "INVALID_EDIT")
        self.assert_restored(before)

    def test_link_failures_after_real_mutations_recover_both_graphs(self):
        source = self.create("command", "source")
        target = self.create()
        for method, kwargs in (("add_projection", {"range_m": 0, "active": True, "amount": 1}),
                               ("add_command", {"active": True})):
            before = self.current()
            with self.fail_after(ENGINE, method):
                self.send(method, {"source_id": source, "target_id": target, **kwargs}, "ENGINE_ERROR")
            self.assert_restored(before)
            self.send(method, {"source_id": source, "target_id": target, **kwargs})
            before = self.current()
            removal = method.replace("add_", "remove_")
            with self.fail_after(ENGINE, removal):
                self.send(removal, {"source_id": source, "target_id": target}, "ENGINE_ERROR")
            self.assert_restored(before)

    def test_skill_and_implant_failures_after_real_changes_recover(self):
        source = self.create("command", "source")
        target = self.create()
        self.send("add_command", {"source_id": source, "target_id": target, "active": True})
        for method, args in (("set_skill_level", {"skill": "Shield Command Specialist", "level": 4}),
                             ("add_implant", {"implant": "Shield Command Mindlink", "active": True})):
            before = self.current()
            with self.fail_after(ENGINE, method):
                self.send(method, {"fit_id": source, **args}, "ENGINE_ERROR")
            self.assert_restored(before)

    def test_strict_skill_none_overrides_survive_parent_restore_and_recovery(self):
        source = self.create("command", "source")
        target = self.create()
        self.send("add_command", {"source_id": source, "target_id": target, "active": True})
        self.send("set_skill_level", {"fit_id": source, "skill": "Shield Command", "level": 0})
        result = self.send("set_skill_level", {"fit_id": source, "skill": "Shield Command", "level": 5})
        snapshot = next(fit for fit in result["fits"] if fit["id"] == source)
        self.assertIsNone(snapshot["skills"]["Shield Command Specialist"])
        before = self.current()
        with self.fail_after(ENGINE, "add_implant"):
            self.send("add_implant", {"fit_id": source, "implant": "Shield Command Mindlink", "active": True}, "ENGINE_ERROR")
        self.assert_restored(before)
        self.assertIsNone(self.bridge.get_fit(source).character.getSkill("Shield Command Specialist").activeLevel)

    def test_serialization_failure_after_edit_recovers(self):
        fit = self.create()
        before = self.current()
        with self.fail_after(self.bridge, "_serialize_success"):
            self.send("set_charges", {"fit_id": fit, "module_indices": [0, 1], "charge": "Iron Charge M"}, "ENGINE_ERROR")
        self.assert_restored(before)

    def test_failure_after_real_sql_commit_recovers_same_session_and_caches(self):
        import eos.db
        from eos.db.saveddata import queries
        fit = self.create()
        old = self.bridge.get_fit(fit)
        self.assertIs(eos.db.getFit(old.ID), old)
        caches = [cache for functions in queries.queryCache.values() for cache in functions.values()]
        session = eos.db.saveddata_session
        before = self.current()
        with self.fail_after(session, "commit"):
            self.send("set_charges", {"fit_id": fit, "module_indices": [0, 1], "charge": "Iron Charge M"}, "ENGINE_ERROR")
        self.assert_restored(before)
        self.assertIs(eos.db.saveddata_session, session)
        restored = self.bridge.get_fit(fit)
        self.assertIsNot(restored, old)
        self.assertIs(eos.db.getFit(restored.ID), restored)
        self.assertEqual([id(cache) for cache in caches],
                         [id(cache) for functions in queries.queryCache.values() for cache in functions.values()])

    def test_recovery_failure_is_terminal_and_never_publishes_partial_fits(self):
        fit = self.create()
        with self.fail_after(ENGINE, "set_charges"), patch.object(ENGINE, "create_fit", side_effect=RuntimeError("Recovery failure")):
            self.send("set_charges", {"fit_id": fit, "module_indices": [0, 1], "charge": "Iron Charge M"}, "ENGINE_UNAVAILABLE")
        self.send("snapshot", {"fit_ids": []}, "ENGINE_UNAVAILABLE")
        self.send("set_charges", {"fit_id": fit, "module_indices": [0, 1], "charge": "Iron Charge M"}, "ENGINE_UNAVAILABLE")
        with self.assertRaises(RuntimeError):
            self.bridge.get_fit(fit)

    def test_wrong_thread_rejects_before_engine_mutation(self):
        fit = self.create()
        before = self.current()
        request = json.dumps(self.envelope("set_charges", {"fit_id": fit, "module_indices": [0, 1], "charge": "Iron Charge M"}))
        results = []
        thread = threading.Thread(target=lambda: results.append(json.loads(self.bridge.dispatch(request))))
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]["error"]["code"], "ENGINE_ERROR")
        self.assert_restored(before)
