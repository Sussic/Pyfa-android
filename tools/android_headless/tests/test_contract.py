"""Real EOS contract, revision and failure-recovery regressions."""
from copy import deepcopy
from functools import cache
import gzip
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from android_bridge.contract import BridgeSession
from tools.android_reference.reference import compare

ENGINE = None
CASES = None
EXPECTED = None
LIFECYCLE_SLICE = None
LIFECYCLE_COVERAGE = []


@cache
def original_context_reference():
    path = Path(__file__).resolve().parents[3] / 'tools/android_reference/fixtures/inspector-contexts.json.gz'
    return json.loads(gzip.decompress(path.read_bytes()))


@cache
def original_booster_reference():
    fixture = original_context_reference()
    case = next(case for case in fixture['cases'] if case['spec']['name'] == 'Inspector booster: Standard Crash Booster')
    return case, fixture['boosterCatalogue']


def original_booster_case():
    return original_booster_reference()[0]


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

    def test_every_booster_shape_cold_warm_complete_original_inspection(self):
        import sys
        import eos.db
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'android/ci'))
        from inspection_identity_summary import attributes, original
        from inspection_context_summary import context_roles, raw_reference, TABLES
        from inspection_canonical_summary import properties
        from inspection_links_summary import flatten
        from android_bridge.inspection_diagnostics import sql_roles
        cases = [case for case in original_context_reference()['cases'] if case['family'] == 'booster']
        self.assertEqual(99, len(cases))
        compare(original_context_reference()['eos_settings'], ENGINE.settings)
        start = 0 if LIFECYCLE_SLICE is None else LIFECYCLE_SLICE * 25
        stop = 99 if LIFECYCLE_SLICE is None else min(99, start + 25)
        for case_index in range(start, stop):
            case = cases[case_index]
            with self.subTest(booster=case['spec']['boosters'][0]['name']):
                self.bridge._reset_storage(); self.bridge = BridgeSession(ENGINE)
                # The independent export has already inspected eight preceding
                # mode/cargo/implant cases. Match that Item cache, without edits.
                before = self.current()
                self.bridge.inspection_base_details(eos.db.getItem(case['spec']['ship']).ID)
                self.assertEqual(before, self.current())
                spec = deepcopy(case['spec']); spec['boosters'] = []; spec['implants'] = []
                spec.pop('cargo', None); spec.pop('ignore_restrictions', None)
                key = self.send('create_fit', dict(spec=spec))['fits'][0]['id']
                self.send('add_booster', dict(fit_id=key,
                    item_id=eos.db.getItem(case['spec']['boosters'][0]['name']).ID, active=True))
                for index in (0, 1):
                    if index: self.send('set_booster_active', dict(fit_id=key, position=0, active=True))
                    expected = case['states'][index]
                    selections = [{field: row[field] for field in ('context', 'index', 'item_id', 'object_key')}
                                  for row in self.bridge.inspection_options(key)['targets']]
                    roles = sql_roles(self.bridge._session, self.bridge._fits[key].ID, complete=True)
                    context_roles(expected['roles'], roles)
                    for target in expected['targets']:
                        selection = dict(context='base', index=None, item_id=target['item_id']) if target['context'] == 'base' else next(
                            row for row in selections if (row['context'], row['item_id']) == (target['context'], target['item_id']))
                        actual = self.bridge.inspection_base_details(target['item_id']) if target['context'] == 'base' else self.bridge.inspection_details(key, selection)
                        attributes(dict(expected=target['attributes'], equipment=target['equipment']), actual)
                        original(properties(target['properties'], selection, expected['roles'], roles, TABLES), actual['properties'])
                        for view in ('source', 'attribute'):
                            original(target['affector_views'][view], flatten(actual['affector_views'][view]))
                        raw_reference(target['affectors'], actual['affectors'], key, self.bridge._records[key],
                                      expected['roles'], roles, selections)
                LIFECYCLE_COVERAGE.append(case_index)

    def test_booster_complete_original_attributes_history_copy_and_stale_targets(self):
        import eos.db
        original = original_booster_case()
        spec = deepcopy(original['spec']); spec['boosters'] = []
        key = self.send('create_fit', {'spec': spec})['fits'][0]['id']
        item = eos.db.getItem(original['spec']['boosters'][0]['name'])
        self.assertNotIn('boosters', self.bridge._records[key])
        self.send('add_booster', dict(fit_id=key, item_id=item.ID, active=True))
        self.send('set_booster_active', dict(fit_id=key, position=0, active=True))
        target = next(row for row in self.bridge.inspection_options(key)['targets'] if row['context'] == 'booster')
        selected = {field: target[field] for field in ('context', 'index', 'item_id', 'object_key')}
        actual = self.bridge.inspection_details(key, selected)
        expected = next(target for target in original['states'][1]['targets'] if target['context'] == 'booster')
        compare(expected['attributes']['precise'], [{field: row[field] for field in ('name', 'id', 'current', 'base', 'unit')} for row in actual['attributes']['rows']])
        saved = deepcopy(self.bridge._records[key])
        flags = saved['boosters'][0]['side_effects']
        self.assertTrue(flags)
        self.assertTrue(all(flag['active'] is False for flag in flags))
        self.send('set_booster_side_effect', dict(fit_id=key, position=0, effect_id=flags[0]['effect_id'], active=True))
        self.assertIs(self.bridge._records[key]['boosters'][0]['side_effects'][0]['active'], True)
        self.send('undo', dict(fit_id=key))
        self.assertEqual(saved, self.bridge._records[key])
        self.send('redo', dict(fit_id=key))
        self.assertIs(self.bridge._records[key]['boosters'][0]['side_effects'][0]['active'], True)
        previous_ids = set(self.bridge._records)
        self.send('duplicate_fit', dict(fit_id=key, name='Booster copy'))
        created = set(self.bridge._records) - previous_ids
        self.assertEqual(1, len(created))
        copy_key = created.pop()
        self.assertEqual(self.bridge._records[key]['boosters'], self.bridge._records[copy_key]['boosters'])
        self.assertNotEqual(self.bridge._records[key]['inspection_ids']['boosters'], self.bridge._records[copy_key]['inspection_ids']['boosters'])
        before_remove = deepcopy(self.bridge._records[key])
        self.send('remove_booster', dict(fit_id=key, position=0))
        self.assertNotIn('boosters', self.bridge._records[key])
        with self.assertRaises(ValueError): self.bridge.inspection_details(key, selected)
        self.send('undo', dict(fit_id=key))
        self.assertEqual(before_remove, self.bridge._records[key])
        self.bridge.inspection_details(key, selected)
        self.send('redo', dict(fit_id=key))
        with self.assertRaises(ValueError): self.bridge.inspection_details(key, selected)

    def test_booster_bad_inputs_and_real_post_change_failure_preserve_full_state(self):
        import eos.db
        original = original_booster_case()
        spec = deepcopy(original['spec']); spec['boosters'] = []
        key = self.send('create_fit', {'spec': spec})['fits'][0]['id']
        item = eos.db.getItem(original['spec']['boosters'][0]['name'])
        self.send('add_booster', dict(fit_id=key, item_id=item.ID, active=True))
        requests = [('add_booster', dict(item_id=item.ID, active=True), 'INVALID_EDIT'),
                    ('add_booster', dict(item_id=eos.db.getItem('Vexor').ID, active=True), 'INVALID_EDIT'),
                    ('add_booster', dict(item_id=item.ID, active=1), 'INVALID_REQUEST'),
                    ('set_booster_active', dict(position=True, active=False), 'INVALID_REQUEST'),
                    ('set_booster_active', dict(position=2, active=False), 'INVALID_EDIT'),
                    ('set_booster_side_effect', dict(position=0, effect_id=True, active=True), 'INVALID_REQUEST'),
                    ('set_booster_side_effect', dict(position=0, effect_id=1, active=True), 'INVALID_EDIT')]
        for operation, args, code in requests:
            previous = deepcopy(self.bridge._records); snapshots = self.current(); history = self.bridge.history_details(key)
            self.send(operation, {'fit_id': key, **args}, code)
            self.assertEqual(previous, self.bridge._records); self.assert_restored(snapshots)
            self.assertEqual(history, self.bridge.history_details(key))
        from android_bridge import boosters
        previous = deepcopy(self.bridge._records); snapshots = self.current()
        bad_rows = []
        for mutate in (lambda row: row.update(slot=row['slot'] + 1),
                       lambda row: row['side_effects'].pop(),
                       lambda row: row['side_effects'][0].update(effect_id=1),
                       lambda row: row['side_effects'][0].update(active=1),
                       lambda row: row.update(active=0),
                       lambda row: row.update(name='Vexor')):
            row=deepcopy(previous[key]['boosters'][0]); mutate(row); bad_rows.append([row])
        bad_rows.extend([[], deepcopy(previous[key]['boosters']) * 2])
        for rows in bad_rows:
            with self.assertRaises(ValueError): boosters.restore(ENGINE, self.bridge.get_fit(key), rows)
            self.assertEqual(previous, self.bridge._records); self.assert_restored(snapshots)
        previous = deepcopy(self.bridge._records); snapshots = self.current(); history = self.bridge.history_details(key)
        with self.fail_after(boosters, 'change'):
            self.send('set_booster_active', dict(fit_id=key, position=0, active=False), 'ENGINE_ERROR')
        self.assertEqual(previous, self.bridge._records); self.assert_restored(snapshots)
        self.assertEqual(history, self.bridge.history_details(key))

    def test_booster_durable_reopen_and_rejected_write_preserve_complete_inputs(self):
        import eos.db
        from android_bridge.store import GraphStore
        original = original_booster_case()
        spec = deepcopy(original['spec']); spec['boosters'] = []
        identity = EXPECTED['ammunition']['database_logical_sha256']
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory) / 'fits.db'
            self.bridge = BridgeSession.open(ENGINE, store, identity, spec)
            key = self.bridge.sample_id
            item = eos.db.getItem(original['spec']['boosters'][0]['name'])
            self.send('add_booster', dict(fit_id=key, item_id=item.ID, active=True))
            flag = self.bridge._records[key]['boosters'][0]['side_effects'][0]
            self.send('set_booster_side_effect', dict(fit_id=key, position=0, effect_id=flag['effect_id'], active=True))
            previous = deepcopy(self.bridge._records); snapshots = self.current(); history = self.bridge.history_details(key)
            saved_bytes = store.read_bytes()
            with patch.object(GraphStore, 'write', side_effect=OSError('Injected rejected booster save')):
                self.send('set_booster_active', dict(fit_id=key, position=0, active=False), 'ENGINE_ERROR')
            self.assertEqual(previous, self.bridge._records); self.assert_restored(snapshots)
            self.assertEqual(history, self.bridge.history_details(key)); self.assertEqual(saved_bytes, store.read_bytes())
            self.bridge._reset_storage()
            self.bridge = BridgeSession.open(ENGINE, store, identity, None)
            self.assertEqual(previous, self.bridge._records); self.assert_restored(snapshots)
            self.assertEqual(0, self.bridge.history_details(key)['undo_count'])
            self.assertEqual(0, self.bridge.history_details(key)['redo_count'])

    def test_every_published_booster_slot_side_effect_record_and_fresh_identity(self):
        original, catalogue = original_booster_reference()
        self.assertEqual(311, len(catalogue))
        spec = deepcopy(original['spec']); spec['boosters'] = []
        key = self.send('create_fit', {'spec': spec})['fits'][0]['id']
        seen = set()
        for row in catalogue:
            with self.subTest(booster=row['name'], slot=row['slot']):
                self.send('add_booster', dict(fit_id=key, item_id=row['id'], active=True))
                saved = self.bridge._records[key]
                self.assertEqual([dict(name=row['name'], slot=row['slot'], active=True,
                    side_effects=[dict(effect_id=identity, active=False) for identity in row['side_effects']])], saved['boosters'])
                identity = saved['inspection_ids']['boosters'][0]
                self.assertNotIn(identity, seen); seen.add(identity)
                self.send('set_booster_active', dict(fit_id=key, position=0, active=False))
                self.assertIs(self.bridge._records[key]['boosters'][0]['active'], False)
                self.send('remove_booster', dict(fit_id=key, position=0))
                self.assertNotIn('boosters', self.bridge._records[key])
                self.assertEqual([], self.bridge._records[key]['inspection_ids']['boosters'])
