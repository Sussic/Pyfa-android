"""C07.2 focused EOS lifecycle contracts; run only in parent's admitted lane."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from test_native_session import NativeSessionTests, spec
from android_bridge.contract import _json
from android_bridge.offline.native_session import NativeSession
from android_bridge.offline.profile_store import GraphStore, StoreWriteRejected, StoreUncertain
from android_bridge.character_implants import catalog_response

NAV1="Eifyr and Co. 'Rogue' Navigation NN-601"
NAV5="Eifyr and Co. 'Rogue' Navigation NN-605"
MIND='Shield Command Mindlink'
AURORA="Genolution 'Auroral' AU-79"


class CharacterImplantTests(unittest.TestCase):
    setUp=NativeSessionTests.setUp
    tearDown=NativeSessionTests.tearDown
    request=NativeSessionTests.request
    edit=NativeSessionTests.edit
    feature=NativeSessionTests.feature
    profile=NativeSessionTests.profile
    reopen=NativeSessionTests.reopen
    def row(self,pid=None):return self.session.graph._state['profiles']['profiles'][pid or self.profile()]
    def item(self,name):return self.engine._item(name).ID
    def add(self,name=NAV1,pid=None,replace=None):
        pid=pid or self.profile()
        return self.feature('add_profile_implant',dict(profile_id=pid,revision=self.row(pid)['revision'],item_id=self.item(name),replace_implant_id=replace))
    def source(self,value,key=None):
        key=key or self.key
        old=self.key;self.key=key
        try:return self.feature('set_implant_source',dict(fit_id=key,fit_revision=self.session._revisions[key],source=value))
        finally:self.key=old
    def local(self):return self.session.implant_details(self.key)['implants']
    def payload(self,operation,args,anchor=True):
        return dict(version=3,request_id='character-test',context=self.session.context(),operation=operation,arguments=args,anchor_fit_id=self.key if anchor else None)
    def reject(self,request,*,code=None):
        state=self.session.graph.snapshot();store=self.path.read_bytes();history=self.session.history;recent=deepcopy(self.session._recent)
        result=json.loads(self.session.feature_dispatch(request if type(request) is str else _json(request)))
        self.assertEqual(set(result),{'version','request_id','ok','committed','reopen_required','state','bridge','error'})
        self.assertFalse(result['ok'],result);self.assertFalse(result['committed']);self.assertFalse(result['reopen_required'])
        self.assertIsNone(result['state']);self.assertIsNone(result['bridge'])
        if code:self.assertEqual(result['error']['code'],code,result)
        self.assertEqual(self.path.read_bytes(),store);self.assertEqual(self.session.graph.snapshot(),state)
        self.assertIs(self.session.history,history);self.assertEqual(self.session._recent,recent)
        return result
    def test_shared_collection_source_switch_local_identity_and_complete_publication(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV5)))
        self.edit('toggle_implants',dict(fit_id=self.key,main_position=0,positions=[]));local=self.local()
        other=self.edit('duplicate_fit',dict(fit_id=self.key,name='Shared'))['fits'][-1]['id']
        if other==self.key:other=next(key for key in self.session._fits if key!=self.key)
        result=self.add();self.assertEqual(len(result['bridge']['fits']),2)
        self.assertEqual(set(result['state']['bindings']),set(self.session._fits))
        self.assertEqual(self.session._records[other]['character_implants'],self.session._records[self.key]['character_implants'])
        self.assertIsNot(self.session._fits[other].character.implants[0],self.session._fits[self.key].character.implants[0])
        self.source('CHARACTER');self.assertEqual(self.local(),local)
        self.source('FIT');self.assertEqual(self.local(),local)
        self.source('CHARACTER');self.reopen();self.assertEqual(self.local(),local)
        self.assertEqual(self.session._records[self.key]['implant_source'],'CHARACTER')
        self.assertEqual(len(self.session._fits[self.key].character.implants),1)
        self.assertEqual(self.session.history_details(self.key)['undo_count'],0)
    def test_source_noop_preserves_all_bytes_revisions_and_history(self):
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history
        result=self.source('FIT');self.assertFalse(result['committed'])
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session.graph.snapshot(),state);self.assertIs(self.session.history,history)
    def test_equipment_existing_local_source_only_and_undo_preserve_inactive_row(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV5)))
        self.edit('toggle_implants',dict(fit_id=self.key,main_position=0,positions=[]));local=self.local()
        self.add();self.source('CHARACTER');before=self.session.history_details(self.key)['undo_count']
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV5)))
        self.assertEqual(self.session._records[self.key]['implant_source'],'FIT');self.assertEqual(self.local(),local)
        self.assertEqual(self.session.history_details(self.key)['undo_count'],before+1)
        self.assertEqual(self.session._recent[0],self.item(NAV5))
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records[self.key]['implant_source'],'CHARACTER');self.assertEqual(self.local(),local)
        self.edit('redo',dict(fit_id=self.key));self.reopen();self.assertEqual(self.local(),local)
    def test_equipment_replace_and_switch_are_one_atomic_history_action(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV1)));local=self.local()
        self.add(NAV5);self.source('CHARACTER')
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV5)));self.assertEqual(self.local()[0]['name'],NAV5)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.local(),local);self.assertEqual(self.session._records[self.key]['implant_source'],'CHARACTER')
    def test_character_replace_order_new_identity_active_slot79_and_recent_unchanged(self):
        recent=deepcopy(self.session._recent);self.add(NAV1);first=deepcopy(self.row()['implants'][0]);self.add(AURORA)
        self.add(NAV1,replace=first['implant_id']);rows=deepcopy(self.row()['implants'])
        self.assertEqual([r['slot'] for r in rows],[79,6]);self.assertNotEqual(rows[-1]['implant_id'],first['implant_id']);self.assertTrue(rows[-1]['active'])
        self.feature('remove_profile_implant',dict(profile_id=self.profile(),revision=self.row()['revision'],implant_id=rows[0]['implant_id']))
        self.assertEqual(self.row()['implants'],[rows[-1]]);self.assertEqual(self.session._recent,recent)
        self.feature('undo',{});self.assertEqual(self.row()['implants'],rows)
    def test_all_local_routes_and_builtins_protected_booster_refused(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV1)));self.source('CHARACTER')
        for op,args in [('add_implant',dict(implant=MIND,active=True)),('set_implant_active',dict(slot=6,active=False)),('remove_implant',dict(slot=6)),
                        ('toggle_implants',dict(main_position=0,positions=[])),('remove_implants',dict(positions=[0])),('change_variation',dict(context='implant',position=0,item_id=self.item(NAV5)))]:
            before=self.path.read_bytes();r=json.loads(self.session.dispatch(_json(self.request(op,dict(fit_id=self.key,**args)))))
            self.assertEqual(r['status'],'error',r);self.assertEqual(self.path.read_bytes(),before)
        for op,args in [('add_profile_implant',dict(profile_id='builtin:all5',revision=0,item_id=self.item(NAV1),replace_implant_id=None)),
                        ('remove_profile_implant',dict(profile_id='builtin:all0',revision=0,implant_id='a'*32)),
                        ('rename_profile',dict(profile_id='builtin:all5',revision=0,name='Changed')),('delete_profile',dict(profile_id='builtin:all5',replacement=None))]:self.reject(self.payload(op,args))
        self.reject(self.payload('add_profile_implant',dict(profile_id=self.profile(),revision=self.row()['revision'],item_id=self.item('Standard Blue Pill Booster'),replace_implant_id=None)))
    def test_full_copy_ids_assignment_and_delete_preserve_local_and_source(self):
        self.add();original=deepcopy(self.row());self.source('CHARACTER');local=self.local()
        result=self.feature('create_profile',dict(name='Complete copy',source=self.profile()))
        copy=next(row for row in result['state']['profiles'] if row['name']=='Complete copy')
        self.assertEqual(copy['levels'],original['levels']);self.assertNotEqual(copy['implants'][0]['implant_id'],original['implants'][0]['implant_id'])
        pid=self.profile();self.feature('assign_profile',dict(fit_id=self.key,profile_id=copy['profile_id']))
        self.feature('delete_profile',dict(profile_id=copy['profile_id'],replacement='builtin:all5'))
        self.assertEqual(self.session._records[self.key]['implant_source'],'CHARACTER');self.assertEqual(self.local(),local);self.assertEqual(self.session._records[self.key]['character_implants'],[])
        self.assertEqual(self.row(pid),original)
    def test_profile_replay_blocked_by_later_fit_copy_without_history(self):
        self.add();before_row=deepcopy(self.row());self.edit('duplicate_fit',dict(fit_id=self.key,name='Later shared copy'))
        self.reject(self.payload('undo',{}),code='history_dependency');self.assertEqual(self.row(),before_row)
    def test_fit_binding_and_source_history_do_not_order_unrelated_library_edits(self):
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Independent binding'))
        other=next(key for key in self.session._fits if key!=self.key);original=self.key
        result=self.feature('create_profile',dict(name='Detached implant owner',source='builtin:all5'))
        pid=next(row['profile_id'] for row in result['state']['profiles'] if row['name']=='Detached implant owner')
        self.add(pid=pid);library=self.session.history.details('library')
        self.source('CHARACTER',other)
        self.key=other;self.feature('assign_profile',dict(fit_id=other,profile_id=pid));self.key=original
        self.assertEqual(self.session.history.details('library'),library)
        self.reject(self.payload('undo',{}),code='history_dependency')
        self.key=other;self.feature('assign_profile',dict(fit_id=other,profile_id='builtin:all0'));self.key=original
        self.assertEqual(self.session.history.details('library'),library)
        self.edit('undo',dict(fit_id=original));self.assertEqual(self.row(pid)['implants'],[])
        self.edit('undo',dict(fit_id=other))
        self.assertEqual(self.session.graph._state['profiles']['bindings'][other]['profile_id'],pid)
        self.assertEqual(self.session._records[other]['character_implants'],[])
        self.assertEqual(list(self.session._fits[other].character.implants),[])
        self.assertEqual(self.session._records[other]['implant_source'],'CHARACTER')
        self.edit('redo',dict(fit_id=other))
        self.assertEqual(self.session.graph._state['profiles']['bindings'][other]['profile_id'],'builtin:all0')

    def test_stale_context_profile_fit_occupant_wrong_kinds_and_anchor_reject(self):
        self.add();row=self.row();pid=self.profile();implant=row['implants'][0]
        for args in [dict(profile_id=pid,revision=row['revision'],item_id=self.item(NAV5),replace_implant_id=None),
                     dict(profile_id=pid,revision=True,item_id=self.item(NAV5),replace_implant_id=implant['implant_id']),
                     dict(profile_id=pid,revision=row['revision'],item_id=True,replace_implant_id=implant['implant_id'])]:self.reject(self.payload('add_profile_implant',args))
        self.reject(self.payload('set_implant_source',dict(fit_id=self.key,fit_revision=True,source='CHARACTER')))
        self.reject(self.payload('set_implant_source',dict(fit_id=self.key,fit_revision=self.session._revisions[self.key],source='CHARACTER'),anchor=False))
        request=self.payload('set_implant_source',dict(fit_id=self.key,fit_revision=self.session._revisions[self.key],source='CHARACTER'));self.source('CHARACTER');self.reject(request,code='stale_context')
    def test_feature_strict_wire_and_bounded_complete_errors(self):
        base=self.payload('undo',{})
        for change in [dict(version=1),dict(version=2),dict(version=True),dict(request_id='bad\ud800'),dict(extra=True),dict(context=dict(self.session.context(),generation=True))]:self.reject(_json(dict(base,**change)))
        self.reject(_json(base)+' false');self.reject('{"version":2,"version":2}');self.reject('x'*16385)
        self.reject(json.dumps(dict(base,arguments={'x':float('nan')})))
    def test_definite_serialization_prepare_write_rejections_preserve_and_recover(self):
        args=dict(profile_id=self.profile(),revision=self.row()['revision'],item_id=self.item(NAV1),replace_implant_id=None)
        for owner,name,error in [(self.session,'_feature_view',RuntimeError('serialize')), (self.session._store,'prepare',RuntimeError('prepare')), (self.session._store,'write',StoreWriteRejected('write'))]:
            with patch.object(owner,name,side_effect=error):self.reject(self.payload('add_profile_implant',args))
        self.add();self.assertEqual(len(self.row()['implants']),1)
    def test_size_refusal_and_materialize_recalc_failures_are_definite(self):
        args=dict(profile_id=self.profile(),revision=self.row()['revision'],item_id=self.item(NAV1),replace_implant_id=None)
        from android_bridge.offline.profiles import ProfileError
        with patch.object(self.session,'_feature_view',side_effect=ProfileError('response_size','Too large')):self.reject(self.payload('add_profile_implant',args),code='response_size')
        with patch('android_bridge.offline.profile_graph.materialize',side_effect=RuntimeError('materialize')):self.reject(self.payload('add_profile_implant',args))
        original=self.engine._recalculate;calls=[0]
        def one_failure(*a,**kw):
            calls[0]+=1
            if calls[0]==1:raise RuntimeError('recalc')
            return original(*a,**kw)
        with patch.object(self.engine,'_recalculate',side_effect=one_failure):self.reject(self.payload('add_profile_implant',args))
        self.add()
    def test_success_then_ack_failure_is_confirmed_once_and_postcommit_publication_disables(self):
        original=self.session._store.write
        def ack(attempt):original(attempt);raise RuntimeError('lost ack')
        generation=self.session._store.current.generation
        with patch.object(self.session._store,'write',side_effect=ack):self.add()
        self.assertEqual(self.session._store.current.generation,generation+1)
        args=dict(profile_id=self.profile(),revision=self.row()['revision'],implant_id=self.row()['implants'][0]['implant_id'])
        with patch.object(self.session,'_remember_versions',side_effect=RuntimeError('publication')):result=json.loads(self.session.feature_dispatch(_json(self.payload('remove_profile_implant',args))))
        self.assertIsNone(result['committed']);self.assertTrue(result['reopen_required']);self.assertFalse(self.session._available)
        self.reopen();self.assertEqual(self.row()['implants'],[])
    def test_uncertain_confirmation_disables_both_until_reopen(self):
        request=self.payload('add_profile_implant',dict(profile_id=self.profile(),revision=self.row()['revision'],item_id=self.item(NAV1),replace_implant_id=None))
        with patch.object(self.session._store,'confirm',side_effect=RuntimeError('confirm')):result=json.loads(self.session.feature_dispatch(_json(request)))
        self.assertIsNone(result['committed']);self.assertTrue(result['reopen_required']);self.assertFalse(self.session.graph._bridge._available)
        self.reopen();self.assertEqual(len(self.row()['implants']),1)
    def test_external_writer_freshness_checked_before_feature_read_or_stage(self):
        store=GraphStore(self.path);candidate=deepcopy(self.session.graph._state);attempt=store.prepare(candidate);store.write(attempt)
        with self.assertRaises(StoreUncertain):self.session.feature_state(self.key)
        self.assertFalse(self.session._available)
    def test_no_fit_library_and_catalogue_no_mutation_genuine_slot79(self):
        pid=self.profile();self.edit('delete_fit',dict(fit_id=self.key,resolve_references=True))
        before=self.path.read_bytes();provenance=deepcopy(self.engine.resolved_item_ids);history=self.session.history
        result=catalog_response(self.engine,os.environ['PYFA_DATASET_SHA']);self.assertTrue(result['ok'],result)
        rows=result['implants'];self.assertEqual([r['item_id'] for r in rows],sorted(set(r['item_id'] for r in rows)))
        self.assertTrue(any(r['slot']==79 for r in rows));self.assertNotIn('Standard Blue Pill Booster',{r['name'] for r in rows})
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.engine.resolved_item_ids,provenance);self.assertIs(self.session.history,history)
        self.feature('add_profile_implant',dict(profile_id=pid,revision=self.row(pid)['revision'],item_id=self.item(NAV1),replace_implant_id=None),anchor=False)
        self.feature('undo',{},anchor=False);self.assertEqual(self.row(pid)['implants'],[])
    def test_v1_through_v4_migration_readonly_noop_and_one_v7_commit(self):
        for version in (1,2,3,4):
            baseline=deepcopy(self.session.graph._state);baseline['version']=version;baseline.pop('implant_sets');baseline['profiles']['format']=1
            for row in baseline['profiles']['profiles'].values():row.pop('implants');row.pop('sec_status')
            for row in baseline['fit_graph']['records'].values():row.pop('implant_source');row.pop('character_implants');row.pop('character_security')
            if version<4:baseline.pop('damage_patterns')
            else:baseline['damage_patterns']['version']=1
            if version<3:baseline.pop('targets')
            if version<2:baseline.pop('imports')
            self.session.graph._bridge._reset_storage();self.path=Path(self.tmp.name)/('legacy-'+str(version)+'.sqlite')
            store=GraphStore(self.path);attempt=store.prepare(baseline);store.write(attempt);content=self.path.read_bytes()
            self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec())
            self.assertTrue(self.session.graph.migration_pending);self.assertEqual(self.path.read_bytes(),content)
            self.source('FIT');self.assertEqual(self.path.read_bytes(),content);self.assertTrue(self.session.graph.migration_pending)
            self.add();self.assertEqual(self.session._store.current.generation,2);self.assertEqual(self.session.graph._state['version'],9)
            self.reopen();self.assertEqual(len(self.row()['implants']),1)
            # Restore an empty authority before manufacturing the next legacy fixture.
            self.feature('remove_profile_implant',dict(profile_id=self.profile(),revision=self.row()['revision'],implant_id=self.row()['implants'][0]['implant_id']))
    def test_fit_generation_and_history_exhaustion_before_eos_staging(self):
        from android_bridge.offline.profile_store import StoredGraph
        source=self.session._store.current
        request=self.payload('add_profile_implant',dict(profile_id=self.profile(),revision=self.row()['revision'],item_id=self.item(NAV1),replace_implant_id=None))
        self.session.graph._revision_floor[self.key]=2**63-1
        with patch.object(self.session.graph,'_restore',side_effect=AssertionError('must not stage')):
            self.reject(request,code='revision')
        self.session.graph._revision_floor[self.key]=self.session._revisions[self.key]
        self.session.history.sequence=2**63-1
        with patch.object(self.session.graph,'_restore',side_effect=AssertionError('must not stage')):
            self.reject(request,code='revision')
        self.session.history.sequence=0
        exhausted=StoredGraph(2**63-1,source.token,source.payload,source.digest)
        self.session._store.current=exhausted
        with patch.object(self.session._store,'_read',return_value=exhausted),patch.object(self.session.graph,'_restore',side_effect=AssertionError('must not stage')):
            request=self.payload('add_profile_implant',dict(profile_id=self.profile(),revision=self.row()['revision'],item_id=self.item(NAV1),replace_implant_id=None))
            self.reject(request,code='revision')
        self.session._store.current=source
    def test_equipment_source_only_counter_exhaustion_precedes_eos_and_write(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV5)));self.source('CHARACTER')
        request=self.request('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV5)))
        before=self.path.read_bytes();state=self.session.graph.snapshot();sequence=self.session.history.sequence
        for kind in ('history','fit','modified'):
            old_floor=self.session.graph._revision_floor[self.key]
            old_modified=self.session.graph._state['fit_graph']['modified'][self.key]
            if kind=='history':self.session.history.sequence=2**63-1
            elif kind=='fit':self.session.graph._revision_floor[self.key]=2**63-1
            else:self.session.graph._state['fit_graph']['modified'][self.key]=2**63-1
            with patch.object(self.session.graph,'_legacy_edit',side_effect=AssertionError('must not stage')):
                result=json.loads(self.session.dispatch(_json(request)))
            self.assertEqual(result['status'],'error');self.assertEqual(result['error']['code'],'INVALID_EDIT');self.assertTrue(self.session._available)
            self.assertEqual(self.path.read_bytes(),before)
            self.session.history.sequence=sequence;self.session.graph._revision_floor[self.key]=old_floor
            self.session.graph._state['fit_graph']['modified'][self.key]=old_modified
            self.assertEqual(self.session.graph.snapshot(),state)
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV5)))
        self.assertEqual(self.session._records[self.key]['implant_source'],'FIT')

    def test_modified_exhaustion_blocks_profile_and_replay_before_projection(self):
        self.add();old=self.session.graph._state['fit_graph']['modified'][self.key]
        self.session.graph._state['fit_graph']['modified'][self.key]=2**63-1
        actions=[('rename_profile',dict(profile_id=self.profile(),revision=self.row()['revision'],name='Changed')),('undo',{})]
        try:
            for operation,args in actions:
                with patch.object(self.session.graph,'_apply_profiles',side_effect=AssertionError('must not project')):
                    self.reject(self.payload(operation,args),code='revision')
        finally:self.session.graph._state['fit_graph']['modified'][self.key]=old

    def test_same_skill_noop_at_exhausted_history_generation_retains_legacy_bytes(self):
        from android_bridge.offline.profile_store import StoredGraph
        baseline=deepcopy(self.session.graph._state);baseline['version']=4;baseline.pop('implant_sets');baseline['profiles']['format']=1;baseline['damage_patterns']['version']=1
        for row in baseline['profiles']['profiles'].values():row.pop('implants');row.pop('sec_status')
        for row in baseline['fit_graph']['records'].values():row.pop('implant_source');row.pop('character_implants');row.pop('character_security')
        self.session.graph._bridge._reset_storage();self.path=Path(self.tmp.name)/'legacy-skill.sqlite'
        store=GraphStore(self.path);store.write(store.prepare(baseline))
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec())
        source=self.session._store.current
        exhausted=StoredGraph(2**63-1,source.token,source.payload,source.digest)
        self.session._store.current=exhausted;self.session.history.sequence=2**63-1
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history
        with patch.object(self.session._store,'_read',return_value=exhausted):
            result=self.feature('set_profile_skill',dict(profile_id=self.profile(),revision=self.row()['revision'],skill_id=next(iter(self.session.graph.catalog)),level=5))
        self.assertFalse(result['committed']);self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.session.graph.snapshot(),state);self.assertIs(self.session.history,history)
        self.assertTrue(self.session.graph.migration_pending)
        self.session._store.current=source

    def test_same_scalar_skill_normalization_still_applies_eos_dependencies(self):
        from android_bridge.offline.eos_profiles import edit_level
        skill=next(value for value in self.session.graph.catalog.values()
                   if any(item.group.category.ID==16 and needed>0 for item,needed in value.requiredFor.items()))
        dependent=next(item for item,needed in skill.requiredFor.items() if item.group.category.ID==16 and needed>0)
        record=deepcopy(self.row());record['levels'][str(skill.ID)]=0;before=deepcopy(record)
        levels=edit_level(record,skill.ID,0)
        self.assertEqual(record,before);self.assertIsNone(levels[str(dependent.ID)])
        self.assertNotEqual(levels,record['levels'])

    def test_effective_skill_counters_reserve_before_projection(self):
        from android_bridge.offline.profile_store import StoredGraph
        self.add();pid=self.profile();skill=next(iter(self.session.graph.catalog))
        state=deepcopy(self.session.graph._state);source=self.session._store.current
        sequence=self.session.history.sequence;floor=self.session.graph._revision_floor[self.key]
        for kind in ('history','generation','modified','fit','profile','binding'):
            if kind=='history':self.session.history.sequence=2**63-1
            elif kind=='generation':self.session._store.current=StoredGraph(2**63-1,source.token,source.payload,source.digest)
            elif kind=='modified':self.session.graph._state['fit_graph']['modified'][self.key]=2**63-1
            elif kind=='fit':self.session.graph._revision_floor[self.key]=2**63-1
            elif kind=='profile':self.row(pid)['revision']=2**63-1
            else:self.session.graph._state['profiles']['bindings'][self.key]['revision']=2**63-1
            with patch.object(self.session._store,'_read',return_value=self.session._store.current),patch.object(self.session.graph,'_apply_profiles',side_effect=AssertionError('must not project')):
                self.reject(self.payload('set_profile_skill',dict(profile_id=pid,revision=self.row(pid)['revision'],skill_id=skill,level=4)),code='revision')
            self.session.graph._state=deepcopy(state);self.session._store.current=source
            self.session.history.sequence=sequence;self.session.graph._revision_floor[self.key]=floor

    def test_legacy_structure_local_rows_reopen_copy_and_new_edits_reject(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV1)))
        self.edit('toggle_implants',dict(fit_id=self.key,main_position=0,positions=[]))
        baseline=deepcopy(self.session.graph._state);baseline['version']=4;baseline.pop('implant_sets');baseline['profiles']['format']=1;baseline['damage_patterns']['version']=1
        for row in baseline['profiles']['profiles'].values():row.pop('implants');row.pop('sec_status')
        for row in baseline['fit_graph']['records'].values():row.pop('implant_source');row.pop('character_implants');row.pop('character_security')
        baseline['fit_graph']['records'][self.key]['spec']['ship']='Astrahus'
        self.session.graph._bridge._reset_storage();self.path=Path(self.tmp.name)/'legacy-structure.sqlite'
        store=GraphStore(self.path);store.write(store.prepare(baseline));before=self.path.read_bytes()
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec())
        self.assertTrue(self.session._fits[self.key].isStructure);self.assertEqual(self.path.read_bytes(),before)
        local=self.local();self.assertEqual(local[0]['name'],NAV1);self.assertFalse(local[0]['active'])
        for operation,args in [('add_implant',dict(implant=MIND,active=True)),('fit_implant',dict(item_id=self.item(MIND)))]:
            result=json.loads(self.session.dispatch(_json(self.request(operation,dict(fit_id=self.key,**args)))))
            self.assertEqual(result['status'],'error');self.assertEqual(self.path.read_bytes(),before)
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Historical structure copy'))
        other=next(key for key in self.session._fits if key!=self.key)
        self.assertTrue(self.session._fits[other].isStructure)
        self.assertEqual(self.local(),local)
        copied=self.session.implant_details(other)['implants'];self.assertEqual(copied[0]['name'],NAV1);self.assertFalse(copied[0]['active'])
        self.reopen();self.assertEqual(self.local(),local)

    def test_profile_control_names_reject_new_input_preserve_legacy_publication(self):
        for control in ('\x7f','\x80','\x9f'):
            self.reject(self.payload('create_profile',dict(name='New'+control+'pilot',source='builtin:all5')),code='invalid_name')
            self.reject(self.payload('rename_profile',dict(profile_id=self.profile(),revision=self.row()['revision'],name='New'+control+'pilot')),code='invalid_name')
        baseline=deepcopy(self.session.graph._state);baseline['version']=4;baseline.pop('implant_sets');baseline['profiles']['format']=1;baseline['damage_patterns']['version']=1
        for row in baseline['profiles']['profiles'].values():row.pop('implants');row.pop('sec_status')
        for row in baseline['fit_graph']['records'].values():row.pop('implant_source');row.pop('character_implants');row.pop('character_security')
        pid=self.profile();baseline['profiles']['profiles'][pid]['name']='Historical\x7f\x80\x9fpilot'
        self.session.graph._bridge._reset_storage();self.path=Path(self.tmp.name)/'legacy-name.sqlite'
        store=GraphStore(self.path);store.write(store.prepare(baseline));before=self.path.read_bytes()
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec())
        published=next(row for row in self.session.feature_state(self.key)['profiles'] if row['profile_id']==pid)
        self.assertEqual(published['name'],'Historical\x7f\x80\x9fpilot');self.assertEqual(self.path.read_bytes(),before)
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all5'))
        self.feature('assign_profile',dict(fit_id=self.key,profile_id=pid))
        self.add();self.reopen();self.assertEqual(self.row(pid)['name'],published['name'])
        result=self.feature('create_profile',dict(name='Explicit safe copy',source=pid))
        copied=next(row for row in result['state']['profiles'] if row['name']=='Explicit safe copy')
        self.assertEqual(copied['levels'],self.row(pid)['levels'])
        self.assertEqual(copied['implants'][0]['item_id'],self.row(pid)['implants'][0]['item_id'])
        self.assertNotEqual(copied['implants'][0]['implant_id'],self.row(pid)['implants'][0]['implant_id'])
        self.assertEqual(self.row(pid)['name'],published['name'])
        self.feature('rename_profile',dict(profile_id=pid,revision=self.row(pid)['revision'],name='Safe pilot'))

    def test_publication_guard_prices_next_generation_selection_and_history(self):
        from android_bridge.offline.profile_store import StoredGraph
        source=self.session._store.current
        self.session._store.current=StoredGraph(9,source.token,source.payload,source.digest)
        with patch.object(self.session,'_feature_view') as view:
            self.session._guard_feature_publication(self.session.graph._state)
        state,context,selected,history=view.call_args.args
        self.assertEqual(context['generation'],10);self.assertEqual(selected,self.key)
        bound=history.details(selected)
        self.assertEqual(bound['undo_count'],100);self.assertEqual(bound['redo_count'],100)
        self.assertGreaterEqual(len(_json(bound['undo_label'])),len(_json('Fit implant')))
        self.session._store.current=source

    def test_equipment_near_feature_cap_rejects_before_durable_write(self):
        from types import SimpleNamespace
        from android_bridge.offline.profiles import ProfileError
        item_id=self.item(NAV1);catalog=self.session.graph.catalog
        base=self.session.feature_state(None);budget=524288-len(_json(base).encode('utf-8'))-1
        self.assertGreater(budget,0)
        first=next(iter(catalog));expanded=dict(catalog)
        expanded[first]=SimpleNamespace(name=catalog[first].name+'x'*budget)
        with patch.object(self.session.graph,'catalog',expanded):
            self.assertEqual(len(_json(self.session.feature_state(None)).encode('utf-8')),524287)
            with self.assertRaises(ProfileError):self.session.feature_state(self.key)
            before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history
            result=json.loads(self.session.dispatch(_json(self.request('fit_implant',dict(fit_id=self.key,item_id=item_id)))))
            self.assertEqual(result['status'],'error');self.assertEqual(result['error']['code'],'INVALID_EDIT')
            self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session.graph.snapshot(),state)
            self.assertIs(self.session.history,history);self.assertTrue(self.session._available)

    def test_ordinary_history_exhaustion_rejects_effective_edits_but_not_noops(self):
        self.session.history.sequence=2**63-1
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history
        skill=next(iter(self.session.graph.catalog.values()))
        for operation,args in [('rename_fit',dict(name='Changed')),('set_skill_level',dict(skill=skill.name,level=4))]:
            result=json.loads(self.session.dispatch(_json(self.request(operation,dict(fit_id=self.key,**args)))))
            self.assertEqual(result['status'],'error');self.assertEqual(result['error']['code'],'INVALID_EDIT')
            self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session.graph.snapshot(),state)
            self.assertIs(self.session.history,history);self.assertTrue(self.session._available);self.assertFalse(self.session._pending_history)
        for operation,args in [('rename_fit',dict(name=state['graph']['fit_graph']['records'][self.key]['spec']['name'])),('set_skill_level',dict(skill=skill.name,level=5))]:
            self.edit(operation,dict(fit_id=self.key,**args));self.assertEqual(self.path.read_bytes(),before)
            self.assertEqual(self.session.history.sequence,2**63-1);self.assertTrue(self.session._available)

    def test_import_history_exhaustion_rejects_new_import_and_allows_receipt_replay(self):
        def preview(identity):
            result=json.loads(self.session.import_preview(_json(dict(version=1,request_id=identity,profile_id='builtin:all5',
                documents=[dict(label='Synthetic import',text='[Rifter, History bounded import]\n')]))))
            self.assertTrue(result['ok'],result);return result['request']
        request=preview('first-history-import')
        result=json.loads(self.session.import_execute(_json(request)));self.assertTrue(result['ok'],result)
        next_request=preview('second-history-import');self.session.history.sequence=2**63-1
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history
        rejected=json.loads(self.session.import_execute(_json(next_request)))
        self.assertFalse(rejected['ok']);self.assertFalse(rejected['committed']);self.assertFalse(rejected['reopen_required'])
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session.graph.snapshot(),state)
        self.assertIs(self.session.history,history);self.assertFalse(self.session._pending_history)
        replay=json.loads(self.session.import_execute(_json(request)))
        self.assertTrue(replay['ok'],replay);self.assertTrue(replay['import_result']['replayed'])
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session.graph.snapshot(),state)
        self.assertIs(self.session.history,history);self.assertTrue(self.session._available)

    def test_recovery_failure_after_definite_rejection_requires_reopen(self):
        request=self.payload('add_profile_implant',dict(profile_id=self.profile(),revision=self.row()['revision'],item_id=self.item(NAV1),replace_implant_id=None))
        original=self.session.graph._restore;calls=[0]
        def restore(graph,**kwargs):
            calls[0]+=1
            if calls[0]>1:raise RuntimeError('recovery failed')
            return original(graph,**kwargs)
        before=self.path.read_bytes()
        with patch.object(self.session.graph,'_restore',side_effect=restore),patch.object(self.session._store,'write',side_effect=StoreWriteRejected('write')):
            result=json.loads(self.session.feature_dispatch(_json(request)))
        self.assertIsNone(result['committed']);self.assertTrue(result['reopen_required']);self.assertEqual(self.path.read_bytes(),before)
        self.reopen();self.assertEqual(self.row()['implants'],[])

    def test_corrupt_modern_schema_projection_builtins_and_unknown_version_preserve_file(self):
        self.add();valid=deepcopy(self.session.graph._state)
        corruptions=[]
        for field in ('implant_source','character_implants'):
            bad=deepcopy(valid);bad['fit_graph']['records'][self.key].pop(field);corruptions.append(bad)
        bad=deepcopy(valid);bad['fit_graph']['records'][self.key]['character_implants'][0]['active']=False;corruptions.append(bad)
        bad=deepcopy(valid);bad['profiles']['profiles']['builtin:all5']['implants']=deepcopy(self.row()['implants']);corruptions.append(bad)
        bad=deepcopy(valid);bad['version']=10;corruptions.append(bad)
        for index,bad in enumerate(corruptions):
            self.session.graph._bridge._reset_storage();path=Path(self.tmp.name)/('bad-'+str(index)+'.sqlite')
            store=GraphStore(path);store.write(store.prepare(bad));before=path.read_bytes()
            with self.assertRaises(Exception):NativeSession(self.engine,path,os.environ['PYFA_DATASET_SHA'],spec())
            self.assertEqual(path.read_bytes(),before)
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec())


if __name__=='__main__':unittest.main()
