"""D04.2 frozen M1-M4 focused host cases; run only in an admitted EOS lane.

These tests assert authority/replay/atomic publication, not the independent
203-row numerical comparison or native/device acceptance.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from test_native_session import NativeSessionTests, spec
from android_bridge.contract import BridgeSession, ContractError, _json, _spec
from android_bridge.offline.native_session import NativeSession
from android_bridge.offline.profile_store import GraphStore, StoreUncertain, StoreWriteRejected
from android_bridge.offline.profiles import ProfileError
from android_bridge.offline.target_profiles import exact


class PilotSecuritySessionTests(unittest.TestCase):
    tearDown = NativeSessionTests.tearDown
    request = NativeSessionTests.request
    edit = NativeSessionTests.edit
    profile = NativeSessionTests.profile
    reopen = NativeSessionTests.reopen

    def setUp(self):
        NativeSessionTests.setUp(self)
        self.edit('create_fit', dict(spec=dict(spec(), name='Security Pacifier', ship='Pacifier', security=dict(system='HISEC', pilot=0))))
        self.control = self.key
        self.key = next(key for key in self.session._fits if key != self.control)

    def row(self, pid=None):
        return self.session.graph._state['profiles']['profiles'][pid or self.profile()]

    def payload(self, operation, arguments, anchor=True):
        return dict(version=3, request_id='security-test', context=self.session.context(),
                    operation=operation, arguments=arguments, anchor_fit_id=self.key if anchor else None)

    def feature(self, operation, arguments, anchor=True):
        result = json.loads(self.session.feature_dispatch(_json(self.payload(operation, arguments, anchor))))
        self.assertTrue(result['ok'], result); self.assertEqual(result['version'], 3)
        self.assertEqual(result['state']['version'], 3)
        self.assertEqual(set(result), {'version', 'request_id', 'ok', 'committed', 'reopen_required', 'state', 'bridge', 'error'})
        self.assertEqual(set(result['state']['bindings']), {fit['id'] for fit in result['bridge']['fits']})
        return result

    def pilot(self, value):
        return self.feature('set_pilot_security', dict(fit_id=self.key, fit_revision=self.session._revisions[self.key], pilot=value))

    def save(self, value, save_as=None, anchor=True):
        return self.feature('save_profile_security', dict(profile_id=self.profile(), revision=self.row()['revision'], sec_status=value, save_as=save_as), anchor)

    def stable(self):
        return self.path.read_bytes(), deepcopy(self.session.graph._state), self.session.history, self.session.context(), deepcopy(self.session.graph._snapshots)

    def reject(self, request, code=None):
        before = self.stable()
        result = json.loads(self.session.feature_dispatch(request if type(request) is str else _json(request)))
        self.assertFalse(result['ok'], result); self.assertFalse(result['committed']); self.assertFalse(result['reopen_required'])
        self.assertIsNone(result['state']); self.assertIsNone(result['bridge'])
        if code: self.assertEqual(result['error']['code'], code, result)
        after = self.stable()
        self.assertEqual(before[0], after[0]); self.assertTrue(exact(before[1], after[1])); self.assertIs(before[2], after[2])
        self.assertEqual(before[3:], after[3:])

    def test_details_exact_shape_unsupported_truth_and_read_no_write(self):
        self.save(-6.25); self.pilot(None); before = self.stable()
        with patch.object(self.engine, '_recalculate', side_effect=AssertionError('Read must not calculate')):
            row = self.session.pilot_security_details(self.key)
            self.session.feature_state(self.key)
        self.assertEqual(set(row), {'version','context','fit_id','revision','hull_id','hull_name','eligible','unavailable_reason','profile','pilot','source','effective','presets'})
        self.assertEqual(set(row['profile']), {'profile_id','name','revision','binding_revision','readonly','sec_status'})
        self.assertEqual(row['source'], 'CHARACTER'); self.assertIsNone(row['pilot']); self.assertEqual(row['effective'], -6.25)
        self.assertEqual(row['hull_id'], 44993); self.assertTrue(row['eligible']); self.assertIsNone(row['unavailable_reason'])
        self.assertEqual(self.stable(), before)
        unsupported = self.session.pilot_security_details(self.control)
        self.assertFalse(unsupported['eligible']); self.assertEqual(unsupported['presets'], []); self.assertEqual(unsupported['unavailable_reason'], 'unsupported_hull')

    def test_all_six_eligible_hulls_and_unsupported_trusted_character_replay(self):
        from android_bridge.pilot_security import HULLS
        for identity, name in HULLS.items():
            if name == 'Pacifier': continue
            self.edit('create_fit', dict(spec=dict(spec(), name='Security ' + name, ship=name)))
        self.assertEqual(len(self.session._fits), 7)
        details = [self.session.pilot_security_details(key) for key in self.session._fits]
        self.assertEqual({row['hull_id']: row['hull_name'] for row in details if row['eligible']}, HULLS)
        fixture = deepcopy(self.session.graph._state)
        record = fixture['fit_graph']['records'][self.control]
        record['spec']['security']['pilot'] = None
        pid = fixture['profiles']['bindings'][self.control]['profile_id']
        fixture['profiles']['profiles'][pid]['sec_status'] = -6.25
        self.session.graph._apply_profiles(fixture)
        content = self.open_fixture(fixture, 'trusted-rifter-character')
        row = self.session.pilot_security_details(self.control)
        self.assertFalse(row['eligible']); self.assertIsNone(row['pilot']); self.assertEqual(row['effective'], -6.25)
        self.assertEqual(self.path.read_bytes(), content)

    def test_missing_replay_inputs_fail_closed_before_snapshot_or_getter(self):
        fit = self.session._fits[self.key]; pair = fit._native_security_inputs
        del fit._native_security_inputs
        try:
            with self.assertRaises(ProfileError): self.session.pilot_security_details(self.key)
            with patch.object(fit, 'calculateModifiedAttributes', side_effect=AssertionError('No fallback calculation')):
                with self.assertRaises(ProfileError): self.engine.prepare_read(fit)
        finally: fit._native_security_inputs = pair

    def test_source_zero_flips_noops_history_and_monotonic_revision(self):
        before = self.stable(); self.assertFalse(self.pilot(-0.0)['committed']); self.assertEqual(self.stable(), before)
        self.assertTrue(self.pilot(None)['committed']); rev = self.session._revisions[self.key]
        self.assertTrue(self.pilot(-0.0)['committed']); self.assertTrue(exact(self.session._records[self.key]['spec']['security']['pilot'], -0.0))
        before = self.stable(); self.assertFalse(self.pilot(0)['committed']); self.assertEqual(self.stable(), before)
        self.feature('undo', {}); self.assertIsNone(self.session._records[self.key]['spec']['security']['pilot']); self.assertGreater(self.session._revisions[self.key], rev)
        self.feature('redo', {}); self.assertTrue(exact(self.session._records[self.key]['spec']['security']['pilot'], -0.0))
        self.reopen(); self.assertTrue(exact(self.session._records[self.key]['spec']['security']['pilot'], -0.0))

    def test_profile_save_as_full_copy_and_source_unchanged(self):
        self.feature('add_profile_implant', dict(profile_id=self.profile(), revision=self.row()['revision'], item_id=self.engine._item("Eifyr and Co. 'Rogue' Navigation NN-601").ID, replace_implant_id=None))
        self.save(2.75); original = deepcopy(self.row()); binding = deepcopy(self.session.graph._state['profiles']['bindings'][self.key])
        result = self.save(-6.25, 'Security copy')
        copy = next(row for row in result['state']['profiles'] if row['name'] == 'Security copy')
        self.assertTrue(exact(self.row(), original)); self.assertEqual(self.session.graph._state['profiles']['bindings'][self.key], binding)
        self.assertEqual(copy['sec_status'], -6.25); self.assertEqual(copy['revision'], 1)
        self.assertEqual(copy['levels'], original['levels']); self.assertEqual(copy['default_level'], original['default_level'])
        self.assertNotEqual(copy['implants'][0]['implant_id'], original['implants'][0]['implant_id'])
        self.assertEqual(copy['implants'][0]['item_id'], original['implants'][0]['item_id'])

    def test_shared_save_closure_override_and_later_copy_reversal_guard(self):
        self.pilot(None); self.edit('duplicate_fit', dict(fit_id=self.key, name='Inherited copy'))
        other = next(key for key in self.session._fits if key not in (self.key, self.control))
        self.feature('assign_profile', dict(fit_id=self.control, profile_id=self.profile()))
        self.edit('add_projection', dict(source_id=self.key, target_id=self.control, range_m=12000, active=True, amount=1))
        before = dict(self.session._revisions); self.save(-6.25)
        for key in (self.key, self.control, other): self.assertGreater(self.session._revisions[key], before[key])
        self.assertEqual(self.session._fits[self.key].getPilotSecurity(), -6.25)
        self.assertEqual(self.session._fits[other].getPilotSecurity(), -6.25)
        self.assertEqual(self.session._fits[self.control].getPilotSecurity(), 0)
        self.edit('duplicate_fit', dict(fit_id=self.key, name='Later holder'))
        self.reject(self.payload('undo', {}), 'history_dependency')

    def test_orm_refresh_capture_duplicate_and_graph_reads_preserve_raw_pair(self):
        import eos.db
        self.save(2.75)
        self.assertTrue(self.save(-0.0)['committed'])
        self.assertTrue(exact(self.row()['sec_status'], -0.0))
        self.pilot(None)
        for pilot in (None, 0, -0.0, -10, 5, -6.25):
            self.pilot(2.75); self.pilot(pilot)
            fit = self.session._fits[self.key]
            eos.db.saveddata_session.flush(); eos.db.saveddata_session.refresh(fit)
            row = self.session.pilot_security_details(self.key)
            self.assertTrue(exact(row['pilot'], pilot)); self.assertTrue(exact(fit.character.secStatus, -0.0))
            self.engine.prepare_read(fit)
            captured = self.session.graph._bridge._capture(self.session._fits, {key: record['spec'] for key, record in self.session._records.items()})
            self.assertTrue(exact(captured[self.key]['spec']['security']['pilot'], pilot))
            self.assertTrue(exact(captured[self.key]['character_security'], -0.0))
        self.edit('duplicate_fit', dict(fit_id=self.key, name='Exact copy'))
        other = next(key for key in self.session._fits if key not in (self.key, self.control))
        self.assertTrue(exact(self.session._records[other]['spec']['security']['pilot'], -6.25))
        self.reopen(); self.assertTrue(exact(self.session._records[other]['character_security'], -0.0))

    def test_invalid_stale_protected_unsupported_and_public_nullable_refused(self):
        args = dict(fit_id=self.key, fit_revision=self.session._revisions[self.key], pilot=None)
        for value in (True, '0', -11, 6): self.reject(self.payload('set_pilot_security', dict(args, pilot=value)), 'invalid_values')
        self.reject(self.payload('set_pilot_security', dict(args, fit_revision=True)))
        self.reject(self.payload('set_pilot_security', args, False))
        for version in (1, 2, True): self.reject(dict(self.payload('set_pilot_security', args), version=version))
        stale = self.payload('set_pilot_security', args); self.pilot(-6.25); self.reject(stale, 'stale_context')
        self.reject(self.payload('set_pilot_security', args), 'conflict')
        old = self.key; self.key = self.control
        self.reject(self.payload('set_pilot_security', dict(fit_id=self.key, fit_revision=self.session._revisions[self.key], pilot=None)), 'unsupported_hull'); self.key = old
        for pid in ('builtin:all0', 'builtin:all5'):
            self.reject(self.payload('save_profile_security', dict(profile_id=pid, revision=0, sec_status=0, save_as='Forbidden')), 'protected')
        nullable = dict(spec(), security=dict(system='HISEC', pilot=None))
        with self.assertRaises(ContractError): _spec(nullable)
        with self.assertRaises(ValueError): self.engine.create_fit(nullable, restore=True)
        self.reject('x' * 16385)

    def test_atomic_failure_preflight_recovery_acknowledgement_and_uncertain(self):
        args = dict(profile_id=self.profile(), revision=self.row()['revision'], sec_status=-6.25, save_as=None)
        for owner, name, error in ((self.session, '_feature_view', ProfileError('response_size', 'bounded')),
                                   (self.session._store, 'prepare', RuntimeError('prepare')),
                                   (self.session._store, 'write', StoreWriteRejected('write'))):
            with patch.object(owner, name, side_effect=error): self.reject(self.payload('save_profile_security', args))
        write = self.session._store.write; generation = self.session.context()['generation']
        def ack(attempt): write(attempt); raise RuntimeError('lost acknowledgement')
        with patch.object(self.session._store, 'write', side_effect=ack): self.save(-6.25)
        self.assertEqual(self.session.context()['generation'], generation + 1)
        with patch.object(self.session._store, 'confirm', side_effect=StoreUncertain('unknown')):
            result = json.loads(self.session.feature_dispatch(_json(self.payload('set_pilot_security', dict(fit_id=self.key, fit_revision=self.session._revisions[self.key], pilot=None)))))
        self.assertTrue(result['reopen_required']); self.assertIsNone(result['committed'])
        with self.assertRaises(Exception): self.session.pilot_security_details(self.key)
        self.reopen(); self.assertIsNone(self.session.pilot_security_details(self.key)['pilot'])

    def open_fixture(self, payload, label):
        self.session.graph._bridge._reset_storage()
        self.path = Path(self.tmp.name) / (label + '.sqlite')
        store = GraphStore(self.path); attempt = store.prepare(payload); store.write(attempt)
        content = self.path.read_bytes()
        self.session = NativeSession(self.engine, self.path, os.environ['PYFA_DATASET_SHA'], spec())
        return content

    def test_m1_all_eight_legacy_envelopes_read_noop_first_edit_reopen(self):
        modern = deepcopy(self.session.graph._state)
        for version in range(1, 9):
            for pilot in (0, -0.0, -10, 5, -6.25):
                with self.subTest(version=version, pilot=pilot):
                    old = deepcopy(modern); old['version'] = version
                    old['profiles']['format'] = 2 if version >= 5 else 1
                    for row in old['profiles']['profiles'].values():
                        row.pop('sec_status')
                        if version < 5: row.pop('implants')
                    for row in old['fit_graph']['records'].values():
                        row.pop('character_security')
                        if version < 5: row.pop('implant_source'); row.pop('character_implants')
                        row['spec']['security']['pilot'] = pilot
                    if version < 6: old.pop('implant_sets')
                    if version < 4: old.pop('damage_patterns')
                    elif version < 7: old['damage_patterns']['version'] = 1
                    if version < 3: old.pop('targets')
                    if version < 2: old.pop('imports')
                    content = self.open_fixture(old, 'legacy-%s-%s' % (version, repr(pilot)))
                    self.assertTrue(self.session.graph.migration_pending)
                    before = self.stable()
                    for _ in range(2):
                        self.session.feature_state(self.key); self.session.pilot_security_details(self.key)
                        self.assertFalse(self.pilot(pilot)['committed'])
                        self.assertFalse(self.save(-0.0)['committed'])
                    self.assertEqual(self.stable(), before); self.assertEqual(self.path.read_bytes(), content)
                    self.save(2.75)
                    state = self.session.graph._state
                    self.assertEqual(state['version'], 9); self.assertEqual(state['profiles']['format'], 3)
                    self.assertEqual(self.session.context()['generation'], 2)
                    self.assertTrue(exact(state['fit_graph']['records'][self.key]['spec']['security']['pilot'], pilot))
                    self.reopen(); self.assertFalse(self.session.graph.migration_pending)
                    self.assertTrue(exact(self.session.pilot_security_details(self.key)['pilot'], pilot))

    def test_m1_standalone_nonempty_and_empty_graph_no_write(self):
        graph = deepcopy(self.session.graph._state['fit_graph'])
        for record in graph['records'].values():
            for key in ('implant_source', 'character_implants', 'character_security'): record.pop(key)
        for empty in (False, True):
            old = deepcopy(graph)
            if empty: old.update(format=2, records={}, revisions={}, modified={}, fit_order=[], sample_id=None)
            content = self.open_fixture(old, 'standalone-' + str(empty))
            self.session.feature_state(None if empty else self.key)
            if not empty: self.session.pilot_security_details(self.key)
            self.assertEqual(self.path.read_bytes(), content); self.assertTrue(self.session.graph.migration_pending)

    def test_m1_legacy_builtin_bindings_fixed_security_after_migration(self):
        for pid, security in (('builtin:all0', 0.0), ('builtin:all5', 5.0)):
            self.feature('assign_profile', dict(fit_id=self.key, profile_id=pid))
            old = deepcopy(self.session.graph._state); old['version'] = 8; old['profiles']['format'] = 2
            for row in old['profiles']['profiles'].values(): row.pop('sec_status')
            for row in old['fit_graph']['records'].values(): row.pop('character_security')
            content = self.open_fixture(old, 'builtin-' + pid.split(':')[1])
            row = self.session.pilot_security_details(self.key)
            self.assertTrue(exact(row['profile']['sec_status'], security))
            self.assertEqual(row['source'], 'EXPLICIT'); self.assertTrue(exact(row['pilot'], 0))
            self.assertEqual(self.path.read_bytes(), content)

    def test_m2_mixed_missing_forged_and_nullable_legacy_stores_preserved(self):
        good = deepcopy(self.session.graph._state)
        corruptions = [lambda s: s.update(version=8),
                       lambda s: s['profiles'].update(format=2),
                       lambda s: s['profiles']['profiles'][self.profile()].pop('sec_status'),
                       lambda s: s['profiles']['profiles']['builtin:all0'].update(sec_status=-0.0),
                       lambda s: s['fit_graph']['records'][self.key].pop('character_security'),
                       lambda s: s['fit_graph']['records'][self.key].update(character_security=0),
                       lambda s: s['profiles']['bindings'].pop(self.key),
                       lambda s: s['profiles']['profiles'][self.profile()].update(sec_status=True)]
        # Capture profile identity before resetting any EOS/session object.
        for index, mutate in enumerate(corruptions):
            bad = deepcopy(good)
            # The lambda profile lookup uses the still-valid previous owner.
            mutate(bad)
            self.session.graph._bridge._reset_storage()
            path = Path(self.tmp.name) / ('corrupt-' + str(index) + '.sqlite')
            store = GraphStore(path); attempt = store.prepare(bad); store.write(attempt); content = path.read_bytes()
            with self.assertRaises(Exception): NativeSession(self.engine, path, os.environ['PYFA_DATASET_SHA'], spec())
            self.assertEqual(path.read_bytes(), content)
            self.engine._fits.clear()
            self.session = NativeSession(self.engine, self.path, os.environ['PYFA_DATASET_SHA'], spec())
        legacy = deepcopy(good); legacy['version'] = 8; legacy['profiles']['format'] = 2
        for row in legacy['profiles']['profiles'].values(): row.pop('sec_status')
        for row in legacy['fit_graph']['records'].values(): row.pop('character_security')
        legacy['fit_graph']['records'][self.key]['spec']['security']['pilot'] = None
        self.session.graph._bridge._reset_storage()
        path = Path(self.tmp.name) / 'legacy-null.sqlite'; store = GraphStore(path)
        attempt = store.prepare(legacy); store.write(attempt); content = path.read_bytes()
        with self.assertRaises(Exception): NativeSession(self.engine, path, os.environ['PYFA_DATASET_SHA'], spec())
        self.assertEqual(path.read_bytes(), content)
        self.engine._fits.clear()
        self.session = NativeSession(self.engine, self.path, os.environ['PYFA_DATASET_SHA'], spec())

    def test_m3_no_fit_security_save_and_builtin_complete_duplicates(self):
        pid = self.profile()
        for key in tuple(self.session._fits): self.edit('delete_fit', dict(fit_id=key, resolve_references=True))
        result = self.feature('save_profile_security', dict(profile_id=pid, revision=self.row(pid)['revision'], sec_status=-0.0, save_as='No fit copy'), anchor=False)
        self.assertEqual(result['bridge']['fits'], []); self.assertIsNone(result['state']['selected_fit_id'])
        copied = next(row for row in result['state']['profiles'] if row['name'] == 'No fit copy')
        self.assertTrue(exact(copied['sec_status'], -0.0))
        self.feature('undo', {}, anchor=False); self.feature('redo', {}, anchor=False)
        for source, value in (('builtin:all0', 0.0), ('builtin:all5', 5.0)):
            result = self.feature('create_profile', dict(name='Copy ' + source, source=source), anchor=False)
            copied = next(row for row in result['state']['profiles'] if row['name'] == 'Copy ' + source)
            self.assertTrue(exact(copied['sec_status'], value)); self.assertFalse(copied['readonly'])

    def test_m4_counter_exhaustion_noop_and_history_branch(self):
        from android_bridge.offline.graph_history import GraphHistory
        self.session.history = GraphHistory(sequence=2**63-1)
        before = self.stable()
        self.assertFalse(self.pilot(0.0)['committed']); self.assertFalse(self.save(0)['committed'])
        self.assertEqual(self.stable(), before)
        args = dict(fit_id=self.key, fit_revision=self.session._revisions[self.key], pilot=None)
        with patch.object(self.session.graph, '_restore', side_effect=AssertionError('Refuse before staging')):
            self.reject(self.payload('set_pilot_security', args), 'revision')
        self.session.history = GraphHistory()
        self.pilot(None); self.pilot(-6.25); self.feature('undo', {}); self.pilot(2.75)
        self.reject(self.payload('redo', {}))

    def test_m4_generation_fit_profile_and_binding_limits_precede_replay(self):
        state = deepcopy(self.session.graph._state); current = self.session._store.current
        pid = self.profile()
        for limit in ('generation', 'fit', 'profile', 'binding'):
            with self.subTest(limit=limit):
                if limit == 'generation':
                    exhausted = current._replace(generation=2**63-1)
                    self.session._store.current = exhausted
                elif limit == 'fit': self.session.graph._state['fit_graph']['revisions'][self.key] = 2**63-1
                elif limit == 'profile': self.row()['revision'] = 2**63-1
                else: self.session.graph._state['profiles']['bindings'][self.key]['revision'] = 2**63-1
                args = dict(profile_id=pid, revision=self.row()['revision'], sec_status=2.75, save_as=None)
                with patch.object(self.session.graph, '_verify_durable'), patch.object(self.session.graph, '_restore', side_effect=AssertionError('Refuse before replay')):
                    self.reject(self.payload('save_profile_security', args), 'revision')
                self.session.graph._state = deepcopy(state); self.session._store.current = current

    def test_m4_resource_rejection_precedes_staging_and_valid_retry_succeeds(self):
        from android_bridge.projected_drone_admission import AdmissionRejected
        args = dict(fit_id=self.key, fit_revision=self.session._revisions[self.key], pilot=None)
        with patch('android_bridge.projected_drone_budget.admit_transition', side_effect=AdmissionRejected('bounded')) as admission, \
             patch.object(self.session.graph, '_restore', side_effect=AssertionError('Refuse before replay')):
            self.reject(self.payload('set_pilot_security', args)); self.assertEqual(admission.call_count, 1)
        self.pilot(None)


if __name__ == '__main__': unittest.main()
