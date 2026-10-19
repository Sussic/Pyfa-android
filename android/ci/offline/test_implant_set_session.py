"""C07.3 real-EOS graph/commit/history tests; parent-admitted execution only."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from test_native_session import NativeSessionTests, spec
from test_character_implants import NAV1, NAV5, MIND, AURORA
from android_bridge.contract import _json
from android_bridge.offline import implant_sets as sets
from android_bridge.offline.native_session import NativeSession
from android_bridge.offline.profile_store import GraphStore, StoredGraph, StoreWriteRejected
from android_bridge.offline.profiles import ProfileError


class ImplantSetSessionTests(unittest.TestCase):
    setUp=NativeSessionTests.setUp
    tearDown=NativeSessionTests.tearDown
    request=NativeSessionTests.request
    edit=NativeSessionTests.edit
    feature=NativeSessionTests.feature
    profile=NativeSessionTests.profile
    reopen=NativeSessionTests.reopen
    def item(self,label):return self.engine._item(label).ID
    def ledger(self):return self.session.graph._state['implant_sets']['sets']
    def payload(self,op='read',args=None,*,anchor=True,selected=None,profile=None,target=None,**view):
        args={} if args is None else args
        selected=args.get('set_id',selected)
        profile=args.get('profile_id',profile)
        history=(self.key if op=='apply_fit' else 'library') if target is None else target
        return dict(version=1,request_id='set-session',context=self.session.context(),anchor_fit_id=self.key if anchor else None,
            view=dict(query='',offset=0,limit=50,selected_set_id=selected,target_profile_id=profile,history_target=history)|view,
            operation=op,arguments=args)
    def call(self,op='read',args=None,**view):
        request=self.payload(op,args,**view);generation=self.session._store.current.generation
        result=json.loads(self.session.implant_sets_dispatch(_json(request)))
        self.assertTrue(result['ok'],result);self.assertFalse(result['reopen_required']);self.assertIsNone(result['error'])
        self.assertEqual(result['state']['context']['generation'],generation+int(result['committed']))
        self.assertEqual(result['request_id'],request['request_id'])
        self.assertEqual(set(result),{'version','request_id','ok','committed','reopen_required','state','bridge','error'})
        self.assertEqual(set(result['state']),{'version','context','anchor_fit_id','page','detail','destination','save_source','history'})
        if op=='read':self.assertIsNone(result['bridge'])
        else:
            self.assertEqual(result['bridge']['request_id'],'bootstrap')
            self.assertEqual({row['id'] for row in result['bridge']['fits']},set(self.session._fits))
        return result
    def reject(self,request,code=None):
        state=self.session.graph.snapshot();content=self.path.read_bytes();history=self.session.history
        provenance=deepcopy(self.engine.resolved_item_ids);floors=self.floors();live=self.live_implants()
        result=json.loads(self.session.implant_sets_dispatch(request if type(request) is str else _json(request)))
        self.assertFalse(result['ok'],result);self.assertFalse(result['committed'],result);self.assertFalse(result['reopen_required'],result)
        self.assertIsNone(result['state']);self.assertIsNone(result['bridge'])
        if code:self.assertEqual(result['error']['code'],code,result)
        self.assertEqual(self.session.graph.snapshot(),state);self.assertEqual(self.path.read_bytes(),content)
        self.assertIs(self.session.history,history);self.assertEqual(self.engine.resolved_item_ids,provenance)
        self.assertEqual(self.floors(),floors);self.assertEqual(self.live_implants(),live)
        return result
    def floors(self):
        return deepcopy(dict(session={name:value for name,value in vars(self.session).items() if name.endswith('_floor')},
                             graph=self.session.graph._revision_floor))
    def live_implants(self):
        from android_bridge.inspection_identity import capture
        def rows(values):return tuple((row.itemID,row.slot,row.active) for row in values)
        return {key:dict(local=rows(fit.implants),character=rows(fit.character.implants),
                         source=int(fit.implantLocation),ids=tuple(capture(fit)['implants']),
                         character_ids=deepcopy(fit._offline_character_implants))
                for key,fit in self.session._fits.items()}
    def create(self,name='Saved'):
        return self.call('create',dict(name=name))['state']['detail']['set_id']
    def change(self,key,op,**args):
        return self.call(op,dict(set_id=key,revision=self.ledger()[key]['revision'],**args))
    def recipe(self,labels=(NAV1,AURORA),name='Saved'):
        key=self.create(name)
        for label in labels:self.change(key,'add_item',item_id=self.item(label),replace_item_id=None)
        return key
    def apply_fit(self,key):
        revision=0 if key.startswith('builtin:') else self.ledger()[key]['revision']
        return self.call('apply_fit',dict(set_id=key,revision=revision,fit_revision=self.session._revisions[self.key]))
    def apply_profile(self,key,pid=None):
        pid=pid or self.profile();row=self.session.graph._state['profiles']['profiles'][pid]
        return self.call('apply_profile',dict(set_id=key,revision=0 if key.startswith('builtin:') else self.ledger()[key]['revision'],
                                             profile_id=pid,profile_revision=row['revision']))
    def source(self,value):
        return self.feature('set_implant_source',dict(fit_id=self.key,fit_revision=self.session._revisions[self.key],source=value))
    def test_full_predefined_catalogue_membership_order_and_grade_less(self):
        catalogue=self.session.graph.implant_set_catalogue()
        self.assertEqual(len(catalogue),56);self.assertEqual(len({r['family'] for r in catalogue.values()}),23)
        self.assertEqual(sum(len(r['item_ids']) for r in catalogue.values()),334)
        self.assertEqual(catalogue['builtin:implant-set:1']['item_ids'],[2082,2589,33393,33394])
        self.assertIsNone(catalogue['builtin:implant-set:1']['grade'])
        self.assertEqual([r['slot'] for r in sets.items(catalogue['builtin:implant-set:1']['item_ids'])],[1,4,3,2])
        for key in ('builtin:implant-set:10','builtin:implant-set:34'):
            self.assertEqual([r['slot'] for r in sets.items(catalogue[key]['item_ids'])],[1,2,4,5,3,6])
        first=self.call()['state']['page'];last=self.call(offset=50)['state']['page']
        self.assertEqual(first['total'],56);self.assertEqual(len(first['entries']),50);self.assertEqual(len(last['entries']),6)
        for key,row in catalogue.items():
            detail=self.call(selected=key)['state']['detail']
            self.assertEqual([r['item_id'] for r in detail['items']],row['item_ids']);self.assertEqual(detail['revision'],0)
    def test_template_changes_library_only_keep_fit_revision_modified_recent_and_source(self):
        state=deepcopy(self.session.graph._state['fit_graph']);history=self.session.history_details(self.key)
        key=self.recipe();self.change(key,'rename',name='Renamed')
        copied=self.change(key,'duplicate',name='Copy')['state']['detail']['set_id'];self.change(copied,'delete')
        self.assertEqual(self.session.graph._state['fit_graph'],state);self.assertEqual(self.session.history_details(self.key),history)
        self.assertGreater(self.session.history.details('library')['undo_count'],0)
    def test_fit_merge_inactive_duplicate_replace_free_slot_source_and_ids(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV1)))
        self.edit('toggle_implants',dict(fit_id=self.key,main_position=0,positions=[]))
        first=deepcopy(self.session._records[self.key]);self.source('CHARACTER')
        key=self.recipe();recent=deepcopy(self.session._recent);sequence=self.session.history.sequence
        self.apply_fit(key);record=self.session._records[self.key]
        self.assertEqual(record['implant_source'],'CHARACTER');self.assertEqual(record['implants'][0],first['implants'][0])
        self.assertEqual(record['inspection_ids']['implants'][0],first['inspection_ids']['implants'][0]);self.assertEqual(record['implants'][1]['slot'],79)
        self.assertEqual(self.session._recent,recent);self.assertEqual(self.session.history.sequence,sequence+1)
        replacement=self.recipe((NAV5,),name='Replacement');old_id=record['inspection_ids']['implants'][0]
        self.apply_fit(replacement);record=self.session._records[self.key]
        self.assertEqual([r['slot'] for r in record['implants']],[79,6]);self.assertNotEqual(record['inspection_ids']['implants'][1],old_id)
        self.assertTrue(record['implants'][1]['active']);self.assertEqual(record['implant_source'],'CHARACTER')
    def test_fit_application_undo_after_template_change_delete_and_notes(self):
        key=self.recipe();before=deepcopy(self.session._records[self.key]);self.apply_fit(key);applied=deepcopy(self.session._records[self.key])
        self.change(key,'rename',name='Later');self.change(key,'delete')
        self.edit('set_notes',dict(fit_id=self.key,text='Keep note'))
        self.call('undo',target=self.key,selected=key)
        self.assertEqual(self.session._records[self.key]['implants'],before['implants']);self.assertEqual(self.session._records[self.key]['spec']['notes'],'Keep note')
        self.call('redo',target=self.key,selected=key)
        self.assertEqual(self.session._records[self.key]['implants'],applied['implants'])
        self.assertEqual(self.session._records[self.key]['inspection_ids']['implants'],applied['inspection_ids']['implants'])
        self.assertNotIn(key,self.ledger())
    def test_duplicate_only_empty_and_rename_noops_at_exhaustion_without_staging(self):
        key=self.recipe();empty=self.create('Empty');self.apply_fit(key);self.source('CHARACTER')
        self.session.history.sequence=sets.MAX_INT
        self.session.graph._revision_floor[self.key]=sets.MAX_INT
        self.session._implant_set_floor[key]=sets.MAX_INT
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history
        with patch.object(self.session.graph,'_restore',side_effect=AssertionError('No-op must not stage')):
            self.assertFalse(self.apply_fit(key)['committed']);self.assertFalse(self.apply_fit(empty)['committed'])
            self.assertFalse(self.apply_profile(empty)['committed']);self.assertFalse(self.change(key,'rename',name='Saved')['committed'])
            self.assertFalse(self.change(key,'add_item',item_id=self.item(AURORA),replace_item_id=self.item(AURORA))['committed'])
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session.graph.snapshot(),state);self.assertIs(self.session.history,history)
    def test_effective_counter_reservations_before_live_stage(self):
        key=self.recipe();args=dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key])
        for kind in ('history','fit','modified','generation'):
            history=self.session.history.sequence;floor=self.session.graph._revision_floor[self.key]
            modified=self.session.graph._state['fit_graph']['modified'][self.key];store=self.session._store.current
            if kind=='history':self.session.history.sequence=sets.MAX_INT
            elif kind=='fit':self.session.graph._revision_floor[self.key]=sets.MAX_INT
            elif kind=='modified':self.session.graph._state['fit_graph']['modified'][self.key]=sets.MAX_INT
            else:self.session._store.current=StoredGraph(sets.MAX_INT,store.token,store.payload,store.digest)
            with patch.object(self.session._store,'_read',return_value=self.session._store.current),patch.object(self.session.graph,'_restore',side_effect=AssertionError('Must reserve before stage')):
                self.reject(self.payload('apply_fit',args),code='revision')
            self.session.history.sequence=history;self.session.graph._revision_floor[self.key]=floor
            self.session.graph._state['fit_graph']['modified'][self.key]=modified;self.session._store.current=store
        self.apply_fit(key)
    def test_library_operation_does_not_consume_unrelated_modified_counter(self):
        old=self.session.graph._state['fit_graph']['modified'][self.key]
        self.session.graph._state['fit_graph']['modified'][self.key]=sets.MAX_INT
        self.session.graph._bridge._modified[self.key]=sets.MAX_INT
        key=self.create();self.assertEqual(self.session.graph._state['fit_graph']['modified'][self.key],sets.MAX_INT)
        self.call('undo');self.assertNotIn(key,self.ledger())
        # This synthetic injection is in-memory; no counter rewrite to hide it.
        self.assertGreaterEqual(self.session.graph._state['fit_graph']['modified'][self.key],old)
    def test_generation_exhausted_empty_and_duplicate_noops_preserve_migration(self):
        key=self.recipe();self.apply_fit(key);source=self.session._store.current
        self.session._store.current=StoredGraph(sets.MAX_INT,source.token,source.payload,source.digest)
        before=self.path.read_bytes();history=self.session.history;state=self.session.graph.snapshot()
        with patch.object(self.session._store,'_read',return_value=self.session._store.current),patch.object(self.session.graph,'_restore',side_effect=AssertionError('No live no-op stage')):
            self.assertFalse(self.apply_fit(key)['committed']);self.assertFalse(self.change(key,'rename',name='Saved')['committed'])
        self.assertEqual(self.path.read_bytes(),before);self.assertIs(self.session.history,history);self.assertEqual(self.session.graph.snapshot(),state)
        self.session._store.current=source
    def test_character_application_recreates_active_rows_and_shared_fit_projections(self):
        key=self.recipe();self.apply_profile(key);pid=self.profile()
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Shared'));other=next(k for k in self.session._fits if k!=self.key)
        before=deepcopy(self.session.graph._state['profiles']['profiles'][pid]['implants'])
        oldfit=deepcopy(self.session._records[self.key]['implants']);self.apply_profile(key)
        after=self.session.graph._state['profiles']['profiles'][pid]['implants']
        self.assertEqual([r['item_id'] for r in before],[r['item_id'] for r in after]);self.assertNotEqual([r['implant_id'] for r in before],[r['implant_id'] for r in after])
        self.assertTrue(all(r['active'] for r in after));self.assertEqual(self.session._records[self.key]['implants'],oldfit)
        self.assertEqual(self.session._records[other]['character_implants'],self.session._records[self.key]['character_implants'])
        self.assertIsNot(self.session._fits[other].character.implants[0],self.session._fits[self.key].character.implants[0])
        self.call('undo');self.assertEqual(self.session.graph._state['profiles']['profiles'][pid]['implants'],before)
    def test_unassigned_profile_application_does_not_add_unrelated_anchor_participant(self):
        result=self.feature('create_profile',dict(name='Unassigned',source='builtin:all5'))
        pid=next(r['profile_id'] for r in result['state']['profiles'] if r['name']=='Unassigned')
        key=self.recipe();history=self.session.history_details(self.key);graph=deepcopy(self.session.graph._state['fit_graph'])
        self.apply_profile(key,pid);self.assertEqual(self.session.history_details(self.key),history)
        self.assertEqual(self.session.graph._state['fit_graph'],graph)
        self.assertEqual(self.call(profile=pid)['state']['destination']['assigned_fit_count'],0)
    def test_save_current_fit_and_character_sources_inactive_members_unchanged(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV5)))
        self.edit('toggle_implants',dict(fit_id=self.key,main_position=0,positions=[]))
        key=self.recipe((NAV1,AURORA));self.apply_profile(key)
        before=deepcopy(self.session.graph._state['fit_graph']);local=self.call('save_current',dict(name='Local source',fit_revision=self.session._revisions[self.key]))
        self.assertEqual(local['state']['detail']['items'][0]['item_id'],self.item(NAV5));self.assertEqual(self.session.graph._state['fit_graph'],before)
        self.source('CHARACTER');before=deepcopy(self.session.graph._state['fit_graph'])
        result=self.call('save_current',dict(name='Character source',fit_revision=self.session._revisions[self.key]),profile='builtin:all0')
        self.assertEqual([r['item_id'] for r in result['state']['detail']['items']],[self.item(NAV1),self.item(AURORA)])
        self.assertEqual(result['state']['save_source']['profile_id'],self.profile());self.assertEqual(result['state']['destination']['profile_id'],'builtin:all0')
        self.assertEqual(self.session.graph._state['fit_graph'],before)
        self.reject(self.payload('save_current',dict(name='Character source',fit_revision=self.session._revisions[self.key])),code='duplicate_name')
    def test_empty_source_and_protected_invalid_items_and_stale_views(self):
        self.reject(self.payload('save_current',dict(name='Empty',fit_revision=self.session._revisions[self.key])),code='empty_source')
        key=self.create();request=self.payload('rename',dict(set_id=key,revision=1,name='Changed'));self.change(key,'rename',name='Other')
        self.reject(request,code='stale_context')
        self.reject(self.payload('rename',dict(set_id=key,revision=1,name='Changed')),code='stale_set')
        for op,args in [('duplicate',dict(set_id='builtin:implant-set:1',revision=0,name='Copy')),
                        ('delete',dict(set_id='builtin:implant-set:1',revision=0)),
                        ('add_item',dict(set_id=key,revision=self.ledger()[key]['revision'],item_id=self.item('Standard Blue Pill Booster'),replace_item_id=None)),
                        ('apply_profile',dict(set_id=key,revision=self.ledger()[key]['revision'],profile_id='builtin:all5',profile_revision=1))]:
            self.reject(self.payload(op,args))
        bad=self.payload('apply_fit',dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key]))
        bad['view']['history_target']='library';self.reject(bad)
    def test_delete_restore_revision_floor_and_stale_id_protection(self):
        key=self.recipe();revision=self.ledger()[key]['revision'];self.change(key,'delete');floor=self.session._implant_set_floor[key]
        self.assertGreater(floor,revision);self.call('undo',selected=key);self.assertGreater(self.ledger()[key]['revision'],floor)
        self.reject(self.payload('rename',dict(set_id=key,revision=revision,name='Stale')),code='stale_set')
        self.call('redo',selected=key);self.assertNotIn(key,self.ledger());self.call('undo',selected=key)
        self.assertGreater(self.ledger()[key]['revision'],floor+1)
    def test_replay_deletion_and_restoration_exhaustion_before_stage(self):
        key=self.create();old=self.session._implant_set_floor[key]
        self.session._implant_set_floor[key]=sets.MAX_INT
        with patch.object(self.session.graph,'_restore',side_effect=AssertionError('Replay deletion must reserve first')) as restore:
            self.reject(self.payload('undo',selected=key),code='revision');self.assertEqual(restore.call_count,0)
        self.session._implant_set_floor[key]=old;self.call('undo',selected=key)
        floor=self.session._implant_set_floor[key];self.session._implant_set_floor[key]=sets.MAX_INT
        with patch.object(self.session.graph,'_restore',side_effect=AssertionError('Replay restoration must reserve first')) as restore:
            self.reject(self.payload('redo',selected=key),code='revision');self.assertEqual(restore.call_count,0)
        self.session._implant_set_floor[key]=floor;self.call('redo',selected=key)
        self.assertGreater(self.ledger()[key]['revision'],floor)
    def test_fit_delete_prunes_application_but_preserves_detached_template_history(self):
        key=self.recipe();self.apply_fit(key);library=self.session.history.details('library')
        self.edit('delete_fit',dict(fit_id=self.key,resolve_references=True))
        self.assertEqual(self.session.history.details('library'),library)
        self.call('undo',anchor=False,selected=key)
        self.assertEqual(self.ledger()[key]['item_ids'],[self.item(NAV1)])
        self.assertEqual(self.session._fits,{})
    def test_structures_reject_apply_without_touching_template(self):
        key=self.recipe();self.edit('create_fit',dict(spec=dict(spec(),name='Structure',ship='Astrahus')))
        self.key=next(key for key,fit in self.session._fits.items() if fit.isStructure)
        args=dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key])
        self.reject(self.payload('apply_fit',args),code='structure')
    def test_definite_prepare_serialization_size_and_write_failures_recover(self):
        key=self.recipe();request=self.payload('apply_fit',dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key]))
        for owner,method,error in [(sets,'state_view',RuntimeError('state')), (self.session,'_feature_view',ProfileError('response_size','Too large')),
                                   (self.session._store,'prepare',RuntimeError('prepare')), (self.session._store,'write',StoreWriteRejected('write'))]:
            with patch.object(owner,method,side_effect=error):self.reject(request)
        with patch.object(sets,'MAX_STATE_BYTES',1):self.reject(request,code='response_size')
        self.apply_fit(key)
    def test_recalculation_and_metadata_failure_leave_full_authority_and_recover(self):
        key=self.recipe();request=self.payload('apply_fit',dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key]))
        original=self.engine._recalculate;count=[0]
        def fail_once(*args,**kwargs):
            count[0]+=1
            if count[0]==1:raise RuntimeError('recalc')
            return original(*args,**kwargs)
        with patch.object(self.engine,'_recalculate',side_effect=fail_once):self.reject(request)
        with patch.object(sets,'metadata',side_effect=ProfileError('invalid_item','Invalid item')):self.reject(request,code='invalid_item')
        self.apply_fit(key)
    def test_lost_ack_exactly_once_postcommit_publication_disables_and_reopen(self):
        key=self.recipe();original=self.session._store.write;generation=self.session._store.current.generation
        def ack(attempt):original(attempt);raise RuntimeError('lost ack')
        with patch.object(self.session._store,'write',side_effect=ack):self.apply_fit(key)
        self.assertEqual(self.session._store.current.generation,generation+1)
        request=self.payload('rename',dict(set_id=key,revision=self.ledger()[key]['revision'],name='Committed'))
        with patch.object(self.session,'_remember_versions',side_effect=RuntimeError('publish')):result=json.loads(self.session.implant_sets_dispatch(_json(request)))
        self.assertTrue(result['reopen_required']);self.assertIsNone(result['committed']);self.assertFalse(self.session._available)
        self.reopen();self.assertEqual(self.ledger()[key]['name'],'Committed');self.assertEqual(len(self.session._records[self.key]['implants']),2)
    def test_uncertain_confirmation_reopen_reconciles_saved_template(self):
        request=self.payload('create',dict(name='Committed'))
        with patch.object(self.session._store,'confirm',side_effect=RuntimeError('confirm')):result=json.loads(self.session.implant_sets_dispatch(_json(request)))
        self.assertTrue(result['reopen_required']);self.assertIsNone(result['committed']);self.assertFalse(self.session._available)
        self.reopen();self.assertIn('Committed',{r['name'] for r in self.ledger().values()})
    def test_no_fit_library_profile_apply_and_restart(self):
        pid=self.profile();key=self.recipe();self.edit('delete_fit',dict(fit_id=self.key,resolve_references=True))
        result=self.call(anchor=False,selected=key,profile=pid);self.assertIsNone(result['state']['save_source'])
        args=dict(set_id=key,revision=self.ledger()[key]['revision'],profile_id=pid,profile_revision=self.session.graph._state['profiles']['profiles'][pid]['revision'])
        self.call('apply_profile',args,anchor=False);self.reopen()
        result=self.call(anchor=False,selected=key,profile=pid)
        self.assertEqual(len(result['state']['destination']['implants']),2);self.assertEqual(result['state']['history']['undo_count'],0)
        self.assertEqual(self.session.graph._state['version'],9)
    def test_v5_readonly_migration_noop_then_one_v7_edit(self):
        self.edit('fit_implant',dict(fit_id=self.key,item_id=self.item(NAV1)));self.source('CHARACTER')
        v5=deepcopy(self.session.graph._state);v5['version']=5;v5.pop('implant_sets');v5['damage_patterns']['version']=1
        v5['profiles']['format']=2
        for row in v5['profiles']['profiles'].values():row.pop('sec_status')
        for row in v5['fit_graph']['records'].values():row.pop('character_security')
        self.session.graph._bridge._reset_storage();self.path=Path(self.tmp.name)/'v5.sqlite'
        store=GraphStore(self.path);attempt=store.prepare(v5);store.write(attempt);content=self.path.read_bytes()
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec())
        self.assertTrue(self.session.graph.migration_pending);self.call();self.source('CHARACTER')
        projected=deepcopy(v5['fit_graph'])
        for key,row in projected['records'].items():row['character_security']=self.session.graph._state['fit_graph']['records'][key]['character_security']
        self.assertEqual(self.path.read_bytes(),content);self.assertEqual(self.session.graph._state['fit_graph'],projected)
        self.create();self.assertEqual(self.session._store.current.generation,2);self.assertFalse(self.session.graph.migration_pending)
        self.assertEqual(self.session.graph._state['version'],9);self.assertEqual(self.session.graph._state['fit_graph'],projected)
    def test_corrupt_v6_and_mixed_v5_refuse_without_write(self):
        key=self.recipe();base=deepcopy(self.session.graph._state)
        for index,change in enumerate((lambda x:x.update(version=10),lambda x:x.update(version=5),
            lambda x:x['implant_sets']['sets'][key].update(item_ids=[self.item(NAV1),self.item(NAV5)]),
            lambda x:x['implant_sets']['sets'][key].update(active=True))):
            value=deepcopy(base);change(value);self.session.graph._bridge._reset_storage()
            path=Path(self.tmp.name)/('corrupt-'+str(index)+'.sqlite');store=GraphStore(path);attempt=store.prepare(value);store.write(attempt);content=path.read_bytes()
            with self.assertRaises((ProfileError,ValueError)):NativeSession(self.engine,path,os.environ['PYFA_DATASET_SHA'],None)
            self.assertEqual(path.read_bytes(),content)
            self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],None)
    def test_transition_refusal_unchanged_caps_and_recovery(self):
        from android_bridge.projected_drone_admission import AdmissionRejected
        key=self.recipe();request=self.payload('apply_fit',dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key]))
        with patch('android_bridge.projected_drone_budget.admit_transition',side_effect=AdmissionRejected('budget')) as admission,patch.object(self.session.graph,'_restore',side_effect=AssertionError('Admission rejection must not stage')) as restore:
            self.reject(request);self.assertEqual(admission.call_count,1)
            self.assertEqual(restore.call_count,0)
            args,kwargs=admission.call_args;self.assertEqual(kwargs,{})
            self.assertEqual(len(args[0][self.key]['implants']),0);self.assertEqual(len(args[1][self.key]['implants']),2)
        self.apply_fit(key)
    def test_validation_refusal_before_stage_restores_only_provenance(self):
        key=self.recipe();request=self.payload('apply_fit',dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key]))
        def invalid(*args,**kwargs):
            self.engine.resolved_item_ids['synthetic preflight provenance']=123
            raise ProfileError('invalid_item','Injected candidate validation refusal')
        with patch.object(self.session.graph,'_validate',side_effect=invalid),patch.object(self.session.graph,'_restore',side_effect=AssertionError('Validation rejection must not stage')) as restore:
            self.reject(request,code='invalid_item');self.assertEqual(restore.call_count,0)
        self.apply_fit(key)
    def test_candidate_and_rollback_restore_schedules_are_bounded(self):
        key=self.recipe();restore=self.session.graph._restore
        with patch.object(self.session.graph,'_restore',wraps=restore) as calls:
            self.apply_fit(key);self.assertEqual(calls.call_count,1)
            self.assertEqual(len(calls.call_args.args[0]['records'][self.key]['implants']),2)
            calls.reset_mock();self.apply_fit(key);self.assertEqual(calls.call_count,0)
            self.call('undo',target=self.key);self.assertEqual(calls.call_count,1)
        request=self.payload('apply_fit',dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key]))
        for owner,method,error in ((self.session._store,'prepare',RuntimeError('prepare')),
                                   (sets,'state_view',ProfileError('invalid_label','publication')),
                                   (self.session._store,'write',StoreWriteRejected('write'))):
            schedule=[]
            def staged(graph, *, damage_ledger):
                schedule.append(deepcopy(graph));return restore(graph, damage_ledger=damage_ledger)
            with patch.object(self.session.graph,'_restore',side_effect=staged),patch.object(owner,method,side_effect=error):
                self.reject(request)
            self.assertEqual(len(schedule),2)
            self.assertEqual([len(graph['records'][self.key]['implants']) for graph in schedule],[2,0])
            self.assertEqual(schedule[1],self.session.graph._state['fit_graph'])
        self.apply_fit(key)
    def test_character_batch_one_candidate_for_all_members_and_shared_recipients(self):
        key=self.recipe();self.edit('duplicate_fit',dict(fit_id=self.key,name='Shared character'))
        restore=self.session.graph._restore
        for expected_count in (0,2):
            self.assertEqual(len(self.session._records[self.key]['character_implants']),expected_count)
            with patch.object(self.session.graph,'_restore',wraps=restore) as calls:
                result=self.apply_profile(key);self.assertEqual(calls.call_count,1)
            self.assertTrue(result['committed'])
            self.assertEqual({len(row['character_implants']) for row in calls.call_args.args[0]['records'].values()},{2})
        # A failure in the first candidate calculation gets exactly one old
        # graph recovery, not one replay for each recipe member or recipient.
        pid=self.profile();request=self.payload('apply_profile',dict(set_id=key,revision=self.ledger()[key]['revision'],
            profile_id=pid,profile_revision=self.session.graph._state['profiles']['profiles'][pid]['revision']))
        calculate=self.engine._recalculate;count=[0]
        def fail_once(*args,**kwargs):
            count[0]+=1
            if count[0]==1:raise RuntimeError('first candidate calculation')
            return calculate(*args,**kwargs)
        with patch.object(self.session.graph,'_restore',wraps=restore) as calls,patch.object(self.engine,'_recalculate',side_effect=fail_once):
            self.reject(request);self.assertEqual(calls.call_count,2)
        self.apply_profile(key)
    def test_legacy_surrogate_label_refuses_publication_without_rewriting_fit(self):
        # Detached publication-input fault injection, not a claim that SQLite
        # can reopen an EOS fit containing an unpaired surrogate.
        key=self.recipe();name=self.session._records[self.key]['spec']['name']
        original=sets.state_view;injected=[]
        def malformed_view(state,*args,**kwargs):
            detached=deepcopy(state)
            detached['fit_graph']['records'][self.key]['spec']['name']='Historic \ud800 fit'
            injected.append((detached,deepcopy(detached)))
            return original(detached,*args,**kwargs)
        with patch.object(sets,'state_view',side_effect=malformed_view):
            self.reject(self.payload(),code='invalid_label')
            request=self.payload('apply_fit',dict(set_id=key,revision=self.ledger()[key]['revision'],fit_revision=self.session._revisions[self.key]))
            with patch.object(self.session._store,'prepare',side_effect=AssertionError('Invalid publication must precede durable prepare')) as prepare:
                self.reject(request,code='invalid_label');self.assertEqual(prepare.call_count,0)
        self.assertEqual(len(injected),2)
        for detached,before in injected:
            self.assertEqual(detached,before)
            self.assertEqual(detached['fit_graph']['records'][self.key]['spec']['name'],'Historic \ud800 fit')
        self.assertEqual(self.session._records[self.key]['spec']['name'],name)
        self.assertEqual(self.call()['state']['destination']['name'],name)
        self.apply_fit(key);self.assertEqual(self.session._records[self.key]['spec']['name'],name)
    def test_legacy_del_c1_destination_labels_remain_exact(self):
        saved=deepcopy(self.session.graph._state);label='Historic \x7f \x85 fit'
        saved['fit_graph']['records'][self.key]['spec']['name']=label
        self.session.graph._bridge._reset_storage();self.path=Path(self.tmp.name)/'legacy-controls.sqlite'
        store=GraphStore(self.path);attempt=store.prepare(saved);store.write(attempt)
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],None)
        before=self.path.read_bytes();self.assertEqual(self.call()['state']['destination']['name'],label)
        self.assertEqual(self.path.read_bytes(),before)
        result=self.call('create',dict(name='Safe set'));self.assertEqual(result['state']['destination']['name'],label)
        self.assertEqual(self.session._records[self.key]['spec']['name'],label)


if __name__=='__main__':unittest.main()
