"""ALPHA1 production NativeSession contracts. All cases require later admission.

Source-table assertions are orchestration/skill contracts, not independent
fitting goldens. The final case requires a separately generated original8b04
witness, never an adapter-generated expected snapshot.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from test_native_session import NativeSessionTests, spec
from android_bridge.contract import _json, BridgeSession
from android_bridge.offline.native_session import NativeSession
from android_bridge.offline.profile_store import GraphStore, StoreUncertain, StoreWriteRejected


class AlphaProfileSessionTests(unittest.TestCase):
    setUp = NativeSessionTests.setUp
    tearDown = NativeSessionTests.tearDown
    request = NativeSessionTests.request
    edit = NativeSessionTests.edit
    feature = NativeSessionTests.feature
    profile = NativeSessionTests.profile
    reopen = NativeSessionTests.reopen

    def row(self, pid=None):
        return self.session.graph._state['profiles']['profiles'][pid or self.profile()]

    def choices(self):
        catalogue = self.session.feature_state(self.key)['alpha_catalogue']
        self.assertTrue(catalogue['available'], catalogue['error'])
        self.assertTrue(catalogue['clones'])
        return catalogue['clones']

    def clone(self, identity, pid=None):
        pid = pid or self.profile()
        return self.feature('set_profile_clone', dict(profile_id=pid,
            revision=self.row(pid)['revision'], alpha_clone_id=identity))

    def learned(self, skill, value, pid=None):
        pid = pid or self.profile()
        return self.feature('set_profile_skill', dict(profile_id=pid,
            revision=self.row(pid)['revision'], skill_id=skill, level=value))

    def view(self, pid=None):
        return next(row for row in self.session.feature_state(self.key)['profiles']
                    if row['profile_id'] == (pid or self.profile()))

    def stable(self):
        return (self.path.read_bytes(), self.session.graph.snapshot(),
                self.session.history, deepcopy(self.engine.resolved_item_ids))

    def payload(self, args, **changes):
        return dict(dict(version=4, request_id='alpha-test', context=self.session.context(),
                    operation='set_profile_clone', arguments=args, anchor_fit_id=self.key), **changes)

    def refused(self, request):
        before = self.stable()
        result = json.loads(self.session.feature_dispatch(_json(request)))
        self.assertFalse(result['ok'], result); self.assertFalse(result['committed'])
        self.assertFalse(result['reopen_required']); self.assertIsNone(result['state'])
        self.assertEqual(self.stable(), before)
        return result

    def test_every_source_clone_below_equal_above_absent_null_and_zero(self):
        import eos.db
        for choice in self.choices():
            clone = eos.db.getAlphaClone(choice['alpha_clone_id'])
            capped = next((row for row in clone.skills if 1 <= row.level <= 4), None)
            self.assertIsNotNone(capped, 'Source clone needs a nontrivial cap for this qualification')
            absent = next((i for i in self.session.graph.catalog if i not in {r.typeID for r in clone.skills}), None)
            self.assertIsNotNone(absent, 'Source clone needs an absent skill for this qualification')
            self.clone(clone.ID)
            for learned, expected in ((None, 0), (0, 0), (capped.level-1, capped.level-1),
                                      (capped.level, capped.level), (capped.level+1, capped.level)):
                with self.subTest(clone=clone.ID, learned=learned):
                    self.learned(capped.typeID, learned)
                    view = self.view()
                    self.assertEqual(view['levels'].get(str(capped.typeID), view['default_level']), learned)
                    self.assertEqual(view['effective_levels'][str(capped.typeID)], expected)
                    self.assertEqual(self.session._fits[self.key].character.getSkill(capped.typeID).level, expected)
            self.learned(absent, 5)
            self.assertEqual(self.view()['effective_levels'][str(absent)], 0)
            self.assertEqual(self.session._fits[self.key].character.getSkill(absent).level, 0)
            before = deepcopy(self.row()); self.clone(None)
            self.assertEqual(self.row()['levels'], before['levels'])
            self.assertEqual(self.view()['effective_levels'][str(absent)], 5)

    def test_apply_switch_remove_baseline5_restoration_and_noop_history(self):
        choices = self.choices(); original = deepcopy(self.row()); omega = self.engine.snapshot(self.session._fits[self.key])
        for choice in choices:
            self.clone(choice['alpha_clone_id'])
            before = self.stable(); result = self.clone(choice['alpha_clone_id'])
            self.assertFalse(result['committed']); self.assertEqual(self.stable(), before)
            view = self.view()
            self.assertEqual(set(view['effective_levels']), {str(i) for i in self.session.graph.catalog})
            for i in self.session.graph.catalog:
                self.assertEqual(self.session._fits[self.key].character.getSkill(i).level, view['effective_levels'][str(i)])
            self.assertEqual(self.row()['levels'], original['levels']); self.assertEqual(self.row()['default_level'], 5)
        self.clone(None)
        self.assertEqual(self.engine.snapshot(self.session._fits[self.key]), omega)

    def test_two_shared_fits_linked_recipient_and_unrelated_state_are_atomic(self):
        self.edit('duplicate_fit', dict(fit_id=self.key, name='Shared Alpha'))
        shared = next(i for i in self.session._fits if i != self.key)
        self.edit('create_fit', dict(spec=dict(spec(), name='Linked recipient')))
        recipient = next(i for i in self.session._fits if i not in (self.key, shared))
        self.edit('create_fit', dict(spec=dict(spec(), name='Unrelated')))
        unrelated = next(i for i in self.session._fits if i not in (self.key, shared, recipient))
        self.edit('add_projection', dict(source_id=self.key, target_id=recipient, range_m=0, active=True, amount=1))
        graph = self.session.graph._state
        other_pid = graph['profiles']['bindings'][unrelated]['profile_id']
        other = (deepcopy(graph['fit_graph']['records'][unrelated]), deepcopy(self.row(other_pid)),
                 graph['fit_graph']['revisions'][unrelated], graph['fit_graph']['modified'][unrelated])
        revisions = dict(self.session._revisions); generation = self.session.context()['generation']
        self.clone(self.choices()[0]['alpha_clone_id'])
        self.assertEqual(self.session.context()['generation'], generation+1)
        for key in (self.key, shared, recipient):
            self.assertGreater(self.session._revisions[key], revisions[key])
            self.assertIs(self.session.history.rows[key][0][-1], self.session.history.rows[self.key][0][-1])
        graph = self.session.graph._state
        self.assertEqual(other, (graph['fit_graph']['records'][unrelated], self.row(other_pid),
                         graph['fit_graph']['revisions'][unrelated], graph['fit_graph']['modified'][unrelated]))
        self.assertEqual(self.session._records[self.key]['skills'], self.session._records[shared]['skills'])
        self.feature('undo', {})
        self.assertIsNone(self.row()['alpha_clone_id']); self.feature('redo', {})
        self.reopen()
        self.assertEqual(self.row()['alpha_clone_id'], self.choices()[0]['alpha_clone_id'])
        self.assertEqual(self.session.history_details(self.key)['undo_count'], 0)

    def test_learned_edit_while_capped_undo_redo_and_reopen_preserve_null_zero(self):
        import eos.db
        identity = self.choices()[0]['alpha_clone_id']; clone = eos.db.getAlphaClone(identity)
        skill = next(row.typeID for row in clone.skills)
        self.learned(skill, None); self.clone(identity); before = deepcopy(self.row())
        self.learned(skill, 0); self.assertEqual(self.row()['levels'][str(skill)], 0)
        self.feature('undo', {}); self.assertEqual(self.row()['levels'], before['levels'])
        self.assertIsNone(self.row()['levels'][str(skill)])
        self.feature('redo', {}); self.reopen(); self.assertEqual(self.row()['levels'][str(skill)], 0)
        self.clone(None); self.assertEqual(self.row()['levels'][str(skill)], 0)
        self.assertEqual(self.view()['effective_levels'][str(skill)], 0)

    def test_detached_copy_save_as_and_ordinary_duplicate_binding(self):
        # Complete saved characters retain non-skill values through cap/copy.
        item = self.engine._item("Eifyr and Co. 'Rogue' Navigation NN-601")
        self.feature('add_profile_implant', dict(profile_id=self.profile(), revision=self.row()['revision'],
                     item_id=item.ID, replace_implant_id=None))
        self.feature('save_profile_security', dict(profile_id=self.profile(), revision=self.row()['revision'],
                     sec_status=2.75, save_as=None))
        self.clone(self.choices()[0]['alpha_clone_id']); original = deepcopy(self.row()); pid = self.profile()
        self.feature('create_profile', dict(name='Detached Alpha', source=pid))
        copy_id = next(i for i,r in self.session.graph._state['profiles']['profiles'].items() if r['name']=='Detached Alpha')
        self.assertEqual(self.row(copy_id)['alpha_clone_id'], original['alpha_clone_id'])
        self.assertEqual(self.row(copy_id)['levels'], original['levels'])
        self.assertEqual(self.row(copy_id)['sec_status'], original['sec_status'])
        self.assertNotEqual(self.row(copy_id)['implants'][0]['implant_id'], original['implants'][0]['implant_id'])
        self.assertEqual({k:v for k,v in self.row(copy_id)['implants'][0].items() if k!='implant_id'},
                         {k:v for k,v in original['implants'][0].items() if k!='implant_id'})
        self.feature('save_profile_security', dict(profile_id=pid, revision=self.row()['revision'],
                     sec_status=original['sec_status'], save_as='Saved Alpha'))
        saved_id = next(i for i,r in self.session.graph._state['profiles']['profiles'].items() if r['name']=='Saved Alpha')
        self.assertEqual(self.row(saved_id)['alpha_clone_id'], original['alpha_clone_id'])
        self.clone(None, copy_id); self.assertEqual(self.row(), original)
        self.edit('duplicate_fit', dict(fit_id=self.key, name='Retains binding'))
        other = next(i for i in self.session._fits if i != self.key)
        self.assertEqual(self.session.graph._state['profiles']['bindings'][other]['profile_id'], pid)
        self.reopen(); self.assertEqual(self.row(saved_id)['levels'], original['levels'])
        self.assertIsNone(self.row(copy_id)['alpha_clone_id'])

    def test_later_binding_blocks_older_cap_undo_until_assignment_is_reversed(self):
        identity = self.choices()[0]['alpha_clone_id']; self.clone(identity); first = self.key
        self.edit('create_fit', dict(spec=dict(spec(), name='Later binding')))
        other = next(i for i in self.session._fits if i != first)
        self.key = other
        self.feature('assign_profile', dict(fit_id=other, profile_id=self.session.graph._state['profiles']['bindings'][first]['profile_id']))
        self.key = first; self.refused(dict(self.payload({}), operation='undo'))
        self.key = other; self.feature('undo', {}); self.key = first; self.feature('undo', {})
        self.assertIsNone(self.row()['alpha_clone_id'])

    def test_builtin_unknown_malformed_stale_context_revision_and_wire_refuse_exactly(self):
        identity = self.choices()[0]['alpha_clone_id']; pid = self.profile()
        args = dict(profile_id=pid, revision=self.row()['revision'], alpha_clone_id=identity)
        for value in (True, False, '1', 1.0, -1, 0, {}, [], 2**63):
            self.refused(self.payload(dict(args, alpha_clone_id=value)))
        unknown = max(row['alpha_clone_id'] for row in self.choices())+1
        self.refused(self.payload(dict(args, alpha_clone_id=unknown)))
        for builtin in ('builtin:all0', 'builtin:all5'):
            self.refused(self.payload(dict(args, profile_id=builtin, revision=0)))
        self.refused(self.payload(dict(args, revision=args['revision']+1)))
        self.refused(self.payload(args, version=3))
        request = self.payload(args); self.edit('rename_fit', dict(fit_id=self.key, name='Makes context stale'))
        self.refused(request)

    def test_missing_empty_and_malformed_catalogue_are_explicit_unavailable(self):
        import eos.db
        from android_bridge.offline.eos_profiles import alpha_catalogue
        from types import SimpleNamespace
        # Malformed synthetic shape only: no fabricated cap values or fitting oracle.
        for rows in (None, [], [SimpleNamespace(ID=True)], [SimpleNamespace(ID=1, alphaCloneName='Missing skills')]):
            with patch.object(eos.db, 'getAlphaCloneList', return_value=rows):
                result = alpha_catalogue(self.session.graph.catalog)
            self.assertFalse(result['available']); self.assertEqual(result['clones'], []); self.assertTrue(result['error'])
        self.session.graph._bridge._reset_storage()
        with patch.object(eos.db, 'getAlphaCloneList', return_value=[]):
            self.session = NativeSession(self.engine, self.path, os.environ['PYFA_DATASET_SHA'], spec())
            self.assertFalse(self.session.feature_state(self.key)['alpha_catalogue']['available'])
            self.refused(self.payload(dict(profile_id=self.profile(), revision=self.row()['revision'], alpha_clone_id=1)))

    def test_v9_readonly_noop_first_edit_reopen_preserves_other_collections(self):
        old = deepcopy(self.session.graph._state); old['version'] = 9; old['profiles']['format'] = 3
        for row in old['profiles']['profiles'].values(): row.pop('alpha_clone_id')
        self.session.graph._bridge._reset_storage(); self.path = Path(self.tmp.name)/'v9.sqlite'
        store = GraphStore(self.path); store.write(store.prepare(old)); content = self.path.read_bytes()
        self.session = NativeSession(self.engine, self.path, os.environ['PYFA_DATASET_SHA'], spec())
        self.assertTrue(self.session.graph.migration_pending); self.assertEqual(self.path.read_bytes(), content)
        self.assertFalse(self.clone(None)['committed']); self.assertEqual(self.path.read_bytes(), content)
        self.clone(self.choices()[0]['alpha_clone_id']); state = self.session.graph._state
        self.assertEqual((state['version'], state['profiles']['format']), (10, 4))
        for key in ('targets', 'damage_patterns', 'implant_sets', 'imports'):
            self.assertEqual(state[key], old[key])
        self.reopen(); self.assertFalse(self.session.graph.migration_pending)

    def test_projection_disagreement_and_unsupported_envelope_fail_without_rewrite(self):
        self.clone(self.choices()[0]['alpha_clone_id']); original = deepcopy(self.session.graph._state)
        for changed in ('projection', 'version', 'profile_format'):
            state = deepcopy(original)
            if changed == 'projection': state['fit_graph']['records'][self.key]['spec']['skill_level'] = 5
            elif changed == 'version': state['version'] = 11
            else: state['profiles']['format'] = 5
            with self.assertRaises(Exception): self.session.graph._validate(state)
        self.session.graph._bridge._reset_storage()
        with self.assertRaises(Exception): BridgeSession.open(self.engine, self.path, os.environ['PYFA_DATASET_SHA'], spec())
        self.reopen()

    def test_rejected_write_and_preflight_publication_failure_keep_graph_history(self):
        identity = self.choices()[0]['alpha_clone_id']
        args = dict(profile_id=self.profile(), revision=self.row()['revision'], alpha_clone_id=identity)
        for owner, method in ((self.session._store, 'write'), (self.session, '_feature_view')):
            with patch.object(owner, method, side_effect=StoreWriteRejected('injected known refusal')):
                self.refused(self.payload(args))
        self.clone(identity)

    def test_lost_acknowledgement_is_confirmed_once(self):
        identity = self.choices()[0]['alpha_clone_id']; original = self.session._store.write
        generation = self.session.context()['generation']
        def write(attempt): original(attempt); raise RuntimeError('lost ack')
        with patch.object(self.session._store, 'write', side_effect=write): self.clone(identity)
        self.assertEqual(self.session.context()['generation'], generation+1)
        self.assertEqual(self.session.history_details(self.key)['undo_count'], 1)

    def test_uncertain_commit_requires_reopen_and_never_blindly_retries(self):
        identity = self.choices()[0]['alpha_clone_id']
        args = dict(profile_id=self.profile(), revision=self.row()['revision'], alpha_clone_id=identity)
        with patch.object(self.session._store, 'confirm', side_effect=StoreUncertain('unknown')):
            result = json.loads(self.session.feature_dispatch(_json(self.payload(args))))
        self.assertTrue(result['reopen_required']); self.assertIsNone(result['committed'])
        with self.assertRaises(Exception): self.session.feature_state(self.key)
        self.reopen(); self.assertEqual(self.row()['alpha_clone_id'], identity)

    def test_postcommit_publication_failure_reopen_recovers_saved_clone(self):
        identity = self.choices()[0]['alpha_clone_id']
        args = dict(profile_id=self.profile(), revision=self.row()['revision'], alpha_clone_id=identity)
        with patch.object(self.session, '_remember_versions', side_effect=RuntimeError('publication')):
            result = json.loads(self.session.feature_dispatch(_json(self.payload(args))))
        self.assertTrue(result['reopen_required']); self.assertIsNone(result['committed'])
        with self.assertRaises(Exception): self.session.bootstrap()
        self.reopen(); self.assertEqual(self.row()['alpha_clone_id'], identity)

    def test_independent_original_reference_fitting_witness(self):
        from tools.android_reference.reference import compare, SOURCE_COMMIT, DEPENDENCIES, digest_file
        witness = json.loads(Path(os.environ['PYFA_ALPHA_REFERENCE']).read_text(encoding='utf-8'))
        self.assertEqual(witness['source_commit'], SOURCE_COMMIT)
        self.assertEqual(witness['dataset_sha256'], os.environ['PYFA_DATASET_SHA'])
        self.assertEqual(witness['schema_version'], 1)
        self.assertTrue(witness['reference_imports']); self.assertTrue(witness['generator_sha256'])
        runtime = witness['reference_runtime']
        self.assertEqual(set(runtime), {'python', 'platform', 'sqlite', 'dependencies'})
        self.assertRegex(runtime['python'], r'^3\.11\.\d+$')
        self.assertIs(type(runtime['platform']), str); self.assertTrue(runtime['platform'].strip())
        self.assertRegex(runtime['sqlite'], r'^\d+\.\d+\.\d+$')
        compare(DEPENDENCIES, runtime['dependencies'], 'original_reference_dependencies')
        source = Path(os.environ['PYFA_CURRENT_REPO'])/'tools'/'android_reference'
        self.assertEqual(witness['generator_sha256'], digest_file(source/'alpha_profiles.py'))
        self.assertEqual(witness['reference_helper_sha256'], digest_file(source/'reference.py'))
        self.assertEqual(witness['input_fixture_sha256'], digest_file(source/'vexor.json'))
        self.assertEqual(witness['eos_settings'], self.engine.settings)
        self.edit('create_fit', dict(spec=witness['spec']))
        self.key = next(i for i,r in self.session._records.items() if r['spec']['name']==witness['spec']['name'])
        self.assertEqual({row['alpha_clone_id'] for row in self.choices()}, {row['alpha_clone_id'] for row in witness['clones']})
        for case in witness['clones']:
            compare(case['omega'], self.engine.snapshot(self.session._fits[self.key]))
            self.clone(case['alpha_clone_id'])
            compare(case['capped'], self.engine.snapshot(self.session._fits[self.key]))
            self.reopen(); compare(case['capped'], self.engine.snapshot(self.session._fits[self.key]))
            self.clone(None); compare(case['restored'], self.engine.snapshot(self.session._fits[self.key]))
            import eos.db
            rows = eos.db.getAlphaClone(case['alpha_clone_id']).skills
            self.assertEqual(case['cap_rows'], sorted((dict(skill_id=row.typeID, cap=row.level) for row in rows), key=lambda row: row['skill_id']))
            self.clone(case['alpha_clone_id'])
            for sample in case['skill_cases']:
                self.learned(sample['skill_id'], sample['learned'])
                view = self.view()
                self.assertEqual(view['levels'].get(str(sample['skill_id']), view['default_level']), sample['learned'])
                self.assertEqual(view['effective_levels'][str(sample['skill_id'])], sample['effective'])
            # Fresh independent all-V learned input for the next clone's fitting witness.
            self.feature('create_profile', dict(name='Next original witness '+str(case['alpha_clone_id']), source='builtin:all5'))
            pid = next(i for i,r in self.session.graph._state['profiles']['profiles'].items() if r['name']=='Next original witness '+str(case['alpha_clone_id']))
            self.feature('assign_profile', dict(fit_id=self.key, profile_id=pid))


class AlphaReferenceProvenanceTests(unittest.TestCase):
    """Standalone exporter refusals before EOS, source or database access."""
    def test_wrong_python_refuses_before_source_or_database(self):
        from tools.android_reference import alpha_profiles as exporter
        with patch.object(exporter.sys, 'version_info', (3, 12, 0)), \
             patch.object(exporter.reference, 'validate_source') as source, \
             patch.object(exporter.reference, 'logical_database_digest') as database, \
             patch.object(exporter.reference, 'bootstrap') as bootstrap:
            with self.assertRaisesRegex(ValueError, 'Use Python 3.11'):
                exporter.generate(Path('unused-source'), Path('unused-data'), 'a'*64, 32)
        source.assert_not_called(); database.assert_not_called(); bootstrap.assert_not_called()

    def test_wrong_actual_dependency_refuses_before_source_or_database(self):
        from tools.android_reference import alpha_profiles as exporter
        pins = exporter.reference.DEPENDENCIES
        def actual(name): return pins[name]+'-wrong' if name == next(iter(pins)) else pins[name]
        with patch.object(exporter.sys, 'version_info', (3, 11, 9)), \
             patch.object(exporter.importlib.metadata, 'version', side_effect=actual) as version, \
             patch.object(exporter.reference, 'validate_source') as source, \
             patch.object(exporter.reference, 'logical_database_digest') as database, \
             patch.object(exporter.reference, 'bootstrap') as bootstrap:
            with self.assertRaisesRegex(ValueError, 'dependencies'):
                exporter.generate(Path('unused-source'), Path('unused-data'), 'a'*64, 32)
        self.assertEqual({call.args[0] for call in version.call_args_list}, set(pins))
        source.assert_not_called(); database.assert_not_called(); bootstrap.assert_not_called()


if __name__ == '__main__': unittest.main()
