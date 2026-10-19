"""Focused cloud integration tests; supplemental EOS data, no native claim."""
import os
import sys
from pathlib import Path
sys.path[:0]=[os.environ['PYFA_CURRENT_REPO'],os.environ['PYFA_REFERENCE_SOURCE']]
import json
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch
from android_bridge.engine import HeadlessEngine
from android_bridge.offline.native_session import NativeSession
from android_bridge.offline.profile_store import StoreWriteRejected
ENGINE=None

def spec():
    return dict(name='Synthetic Rifter',ship='Rifter',skill_level=5,factor_reload=False,
                damage_pattern=dict(emAmount=25,thermalAmount=25,kineticAmount=25,explosiveAmount=25),
                target_profile=None,security=dict(system='HISEC',pilot=0.0),implants=[],boosters=[],
                projections=[],commands=[],environments=[],modules=[],drones=[],cargo=[],ignore_restrictions=False)

class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        global ENGINE
        if ENGINE is None:ENGINE=HeadlessEngine(os.environ['PYFA_DATABASE'])
        self.engine=ENGINE;self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'fits.sqlite'
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec())
        self.key=next(iter(self.session._fits))
    def tearDown(self):
        self.session.graph._bridge._reset_storage();self.tmp.cleanup()
    def request(self,op,args):
        ids={args[k] for k in ('fit_id','source_id','target_id') if k in args}
        return dict(version=1,request_id='test',session_id=self.session.session_id,operation=op,
                    expected_revisions={k:self.session._revisions[k] for k in ids},arguments=args)
    def edit(self,op,args):
        value=json.loads(self.session.dispatch(json.dumps(self.request(op,args))))
        self.assertEqual(value['status'],'ok',value);return value
    def feature(self,op,args,anchor=True):
        r=dict(version=3,request_id='feature-test',context=self.session.context(),operation=op,
               arguments=args,anchor_fit_id=self.key if anchor else None)
        value=json.loads(self.session.feature_dispatch(json.dumps(r)))
        self.assertTrue(value['ok'],value);return value
    def profile(self):return self.session.graph._state['profiles']['bindings'][self.key]['profile_id']
    def reopen(self):
        self.session.graph._bridge._reset_storage()
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec())
    def test_existing_rename_undo_redo_and_restart(self):
        self.edit('rename_fit',dict(fit_id=self.key,name='Renamed'))
        self.assertEqual(self.session.history_details(self.key)['undo_count'],1)
        rev=self.session._revisions[self.key]
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records[self.key]['spec']['name'],'Synthetic Rifter')
        self.assertGreater(self.session._revisions[self.key],rev)
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.session._records[self.key]['spec']['name'],'Renamed')
        self.reopen();self.assertEqual(self.session._records[self.key]['spec']['name'],'Renamed')
        self.assertEqual(self.session.history_details(self.key)['undo_count'],0)
    def test_profile_change_undo_has_monotonic_revisions(self):
        pid=self.profile();old=deepcopy(self.session.graph._state['profiles']['profiles'][pid])
        self.feature('rename_profile',dict(profile_id=pid,revision=old['revision'],name='New pilot'))
        changed=self.session.graph._state['profiles']['profiles'][pid]['revision']
        self.edit('undo',dict(fit_id=self.key))
        row=self.session.graph._state['profiles']['profiles'][pid]
        self.assertEqual(row['name'],old['name']);self.assertGreater(row['revision'],changed)
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.session.graph._state['profiles']['profiles'][pid]['name'],'New pilot')
    def test_shared_profile_undo_requires_later_fit_edits_first(self):
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Other'))
        other=next(k for k in self.session._fits if k!=self.key);pid=self.profile()
        row=self.session.graph._state['profiles']['profiles'][pid]
        skill=next(iter(self.session.graph.catalog))
        self.feature('set_profile_skill',dict(profile_id=pid,revision=row['revision'],skill_id=skill,level=0))
        self.edit('rename_fit',dict(fit_id=other,name='Later'))
        before=self.path.read_bytes()
        error=json.loads(self.session.dispatch(json.dumps(self.request('undo',dict(fit_id=self.key)))))
        self.assertEqual(error['status'],'error');self.assertEqual(self.path.read_bytes(),before)
        self.edit('undo',dict(fit_id=other));self.edit('undo',dict(fit_id=self.key))
        self.assertEqual(self.session.history_details(other)['redo_count'],2)
    def test_notes_survive_unrelated_history(self):
        self.edit('rename_fit',dict(fit_id=self.key,name='New name'))
        self.edit('set_notes',dict(fit_id=self.key,text='Keep this synthetic note'))
        self.edit('undo',dict(fit_id=self.key))
        self.assertEqual(self.session._records[self.key]['spec']['notes'],'Keep this synthetic note')
    def test_failed_commit_preserves_history_and_graph(self):
        self.edit('rename_fit',dict(fit_id=self.key,name='New name'))
        state=self.session.graph.snapshot();content=self.path.read_bytes();history=self.session.history_details(self.key)
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('injected')):
            result=json.loads(self.session.dispatch(json.dumps(self.request('undo',dict(fit_id=self.key)))))
        self.assertEqual(result['status'],'error');self.assertEqual(self.path.read_bytes(),content)
        self.assertEqual(self.session.graph.snapshot(),state);self.assertEqual(self.session.history_details(self.key),history)
        self.edit('undo',dict(fit_id=self.key))
    def test_catalog_and_builtin_assignment(self):
        state=self.session.feature_state(self.key);self.assertGreater(len(state['skills']),400)
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        self.assertEqual(self.profile(),'builtin:all0')
        self.edit('undo',dict(fit_id=self.key));self.assertNotEqual(self.profile(),'builtin:all0')
    def test_new_binding_blocks_older_profile_reversal(self):
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Other'))
        other=next(k for k in self.session._fits if k!=self.key)
        self.feature('create_profile',dict(name='Unassigned',source='builtin:all5'))
        pid=next(k for k,v in self.session.graph._state['profiles']['profiles'].items() if v['name']=='Unassigned')
        row=self.session.graph._state['profiles']['profiles'][pid]
        self.feature('set_profile_skill',dict(profile_id=pid,revision=row['revision'],skill_id=next(iter(self.session.graph.catalog)),level=0))
        oldkey=self.key;self.key=other
        self.feature('assign_profile',dict(fit_id=other,profile_id=pid));self.key=oldkey
        content=self.path.read_bytes();rev=self.session._revisions[other]
        failed=json.loads(self.session.dispatch(json.dumps(self.request('undo',dict(fit_id=self.key)))))
        self.assertEqual(failed['status'],'error');self.assertEqual(self.path.read_bytes(),content)
        self.assertEqual(self.session._revisions[other],rev)
        self.edit('undo',dict(fit_id=other));self.edit('undo',dict(fit_id=self.key))
    def test_uncertain_commit_disables_public_reads(self):
        with patch.object(self.session._store,'confirm',side_effect=RuntimeError('injected unknown')):
            result=json.loads(self.session.dispatch(json.dumps(self.request('rename_fit',dict(fit_id=self.key,name='Unknown')))))
        self.assertEqual(result['error']['code'],'ENGINE_UNAVAILABLE')
        for call in (self.session.bootstrap,lambda:self.session.history_details(self.key),lambda:self.session.feature_state(self.key)):
            with self.assertRaises(Exception):call()
        self.assertFalse(self.session.graph._bridge._available)
    def test_ordinary_create_response_stays_affected_only(self):
        result=self.edit('create_fit',dict(spec=dict(spec(),name='Created')))
        self.assertEqual(len(result['fits']),1)
        self.assertEqual(len(self.session._fits),2)
    def preview(self,text='[Rifter, Imported]\n',request_id='import-test'):
        return json.loads(self.session.import_preview(json.dumps(dict(version=1,request_id=request_id,
                         profile_id=self.profile(),documents=[dict(label='Synthetic EFT',text=text)]))))
    def test_import_undo_redo_replay_restart_and_deleted_receipt(self):
        preview=self.preview();self.assertTrue(preview['ok'],preview)
        exact=json.dumps(preview['request']);result=json.loads(self.session.import_execute(exact))
        self.assertTrue(result['ok'],result);key=result['import_result']['fit_ids'][0]
        self.assertEqual(self.session.graph._state['profiles']['bindings'][key]['profile_id'],self.profile())
        rev=self.session._revisions[key]
        self.feature('undo',{},anchor=False);self.assertNotIn(key,self.session._fits)
        self.feature('redo',{},anchor=False);self.assertIn(key,self.session._fits);self.assertGreater(self.session._revisions[key],rev)
        generation=self.session._store.current.generation
        replay=json.loads(self.session.import_execute(exact));self.assertTrue(replay['import_result']['replayed'])
        self.assertEqual(self.session._store.current.generation,generation)
        self.edit('delete_fit',dict(fit_id=key,resolve_references=True));self.reopen()
        replay=json.loads(self.session.import_execute(exact));self.assertEqual(replay['import_result']['missing_fit_ids'],[key])
        self.assertNotIn(key,self.session._fits)
    def test_import_rejection_invalid_and_stale_are_atomic(self):
        preview=self.preview();exact=json.dumps(preview['request']);content=self.path.read_bytes()
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('injected')):
            result=json.loads(self.session.import_execute(exact))
        self.assertFalse(result['ok']);self.assertFalse(result['committed']);self.assertEqual(content,self.path.read_bytes())
        invalid=self.preview('[Rifter, Bad]\nNonexistent item 971298374\n');self.assertFalse(invalid['ok'])
        self.assertIsNone(invalid['request']);self.assertEqual(content,self.path.read_bytes())
        self.edit('rename_fit',dict(fit_id=self.key,name='Changed'))
        result=json.loads(self.session.import_execute(exact));self.assertFalse(result['ok']);self.assertFalse(result['committed'])
    def cap_request(self):
        return dict(version=1,request_id='cap',context=self.session.context(),fits=[dict(fit_id=self.key,revision=self.session._revisions[self.key])],
                    x=dict(quantity='time',unit='s',range=[0,300]),y=dict(quantity='cap_amount',unit='GJ'),
                    starting_cap_percent=100,use_simulation=True,resolution=32,budget_ms=10000)
    def test_capacitor_readonly_cache_cleanup_cancel_stale(self):
        content=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history_details(self.key)
        fit=self.session._fits[self.key]
        with patch.object(fit,'clear',wraps=fit.clear) as clear:
            result=json.loads(self.session.capacitor_samples(json.dumps(self.cap_request())))
            self.assertTrue(result['ok'],result);self.assertTrue(clear.called)
        self.assertEqual(self.path.read_bytes(),content);self.assertEqual(self.session.graph.snapshot(),state)
        self.assertEqual(self.session.history_details(self.key),history)
        cancelled=json.loads(self.session.capacitor_samples(json.dumps(self.cap_request()),lambda:True))
        self.assertEqual(cancelled['error']['code'],'cancelled')
        request=self.cap_request();self.edit('rename_fit',dict(fit_id=self.key,name='Changed'))
        stale=json.loads(self.session.capacitor_samples(json.dumps(request)));self.assertFalse(stale['ok'])
        # Normal fitting remains usable after the public cache cleanup.
        self.edit('undo',dict(fit_id=self.key))
    def test_rebinding_history_uses_current_authoritative_projection(self):
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Other'))
        other=next(k for k in self.session._fits if k!=self.key)
        self.feature('create_profile',dict(name='Detached',source='builtin:all5'))
        pid=next(k for k,v in self.session.graph._state['profiles']['profiles'].items() if v['name']=='Detached')
        row=self.session.graph._state['profiles']['profiles'][pid]
        self.feature('set_profile_skill',dict(profile_id=pid,revision=row['revision'],skill_id=next(iter(self.session.graph.catalog)),level=0))
        original=self.key;self.key=other
        self.feature('assign_profile',dict(fit_id=other,profile_id=pid))
        self.feature('assign_profile',dict(fit_id=other,profile_id='builtin:all0'))
        self.key=original;self.edit('undo',dict(fit_id=original))
        self.edit('undo',dict(fit_id=other));self.edit('redo',dict(fit_id=other))
        self.assertEqual(self.session.graph._state['profiles']['bindings'][other]['profile_id'],'builtin:all0')
    def test_module_history_retains_original_tokens_and_noop_behavior(self):
        module=self.engine._item('200mm AutoCannon I')
        self.edit('add_module',dict(fit_id=self.key,item_id=module.ID))
        self.assertEqual(sum(m.item is not None for m in self.session._fits[self.key].modules),1)
        token=self.session.graph._bridge._history.rows[self.key][0][-1]
        self.assertIs(self.session.history.rows[self.key][0][-1].legacy_token,token)
        self.edit('undo',dict(fit_id=self.key))
        self.edit('redo',dict(fit_id=self.key))
        self.assertEqual([m.item.ID for m in self.session._fits[self.key].modules if m.item is not None],[module.ID])
        before=self.session.history_details(self.key)['undo_count']
        name=self.session._records[self.key]['spec']['name']
        self.edit('rename_fit',dict(fit_id=self.key,name=name))
        self.assertEqual(self.session.history_details(self.key)['undo_count'],before)
    def test_integrated_unstable_capacitor_multi_fit_units(self):
        unstable=dict(spec(),name='Unstable Merlin',ship='Merlin',
                      modules=[dict(name=name,state='ACTIVE') for name in ('Small Shield Booster II','5MN Microwarpdrive II')])
        response=self.edit('create_fit',dict(spec=unstable));other=response['fits'][0]['fit_id'] if 'fit_id' in response['fits'][0] else response['fits'][0]['id']
        self.assertFalse(self.session._fits[other].capStable)
        request=self.cap_request();request['fits'].append(dict(fit_id=other,revision=self.session._revisions[other]))
        result=json.loads(self.session.capacitor_samples(json.dumps(request)));self.assertTrue(result['ok'],result)
        self.assertEqual(len(result['series']),2)
        request['x']=dict(quantity='cap_amount',unit='%',range=[0,100]);request['y']=dict(quantity='cap_regen',unit='GJ/s')
        result=json.loads(self.session.capacitor_samples(json.dumps(request)));self.assertTrue(result['ok'],result)
        self.assertTrue(all(row['mode']=='recharge_only' for row in result['series']))
        request['starting_cap_percent']=float('nan')
        result=json.loads(self.session.capacitor_samples(json.dumps(request)));self.assertFalse(result['ok'])
    def test_import_postcommit_response_failure_closes_until_exact_replay(self):
        preview=self.preview();exact=json.dumps(preview['request'])
        with patch('android_bridge.offline.eft_import._success',side_effect=RuntimeError('injected response failure')):
            result=json.loads(self.session.import_execute(exact))
        self.assertFalse(result['ok']);self.assertIsNone(result['committed']);self.assertTrue(result['reopen_required'])
        with self.assertRaises(Exception):self.session.bootstrap()
        self.reopen()
        replay=json.loads(self.session.import_execute(exact));self.assertTrue(replay['ok'],replay)
        self.assertTrue(replay['import_result']['replayed']);self.assertEqual(len(self.session._fits),2)
    def test_postcommit_history_publication_failure_disables_session(self):
        pid=self.profile();revision=self.session.graph._state['profiles']['profiles'][pid]['revision']
        request=dict(version=3,request_id='postcommit',context=self.session.context(),operation='rename_profile',
                     arguments=dict(profile_id=pid,revision=revision,name='Committed name'),anchor_fit_id=self.key)
        with patch.object(self.session,'_remember_versions',side_effect=RuntimeError('injected history failure')):
            result=json.loads(self.session.feature_dispatch(json.dumps(request)))
        self.assertIsNone(result['committed']);self.assertTrue(result['reopen_required'])
        with self.assertRaises(Exception):self.session.fitting_details(self.key)
        with self.assertRaises(Exception):_ = self.session._fits
        self.reopen();self.assertEqual(self.session.graph._state['profiles']['profiles'][pid]['name'],'Committed name')
    def test_malformed_ordinary_request_keeps_legacy_code(self):
        value=json.loads(self.session.dispatch('{'))
        self.assertEqual(value['error']['code'],'INVALID_REQUEST')
    def test_legacy_store_migration_is_readonly_until_first_edit(self):
        from android_bridge.contract import BridgeSession
        self.session.graph._bridge._reset_storage()
        self.path=Path(self.tmp.name)/'legacy.sqlite'
        legacy=BridgeSession.open(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],dict(spec(),notes='Legacy synthetic note'))
        key=legacy.sample_id;records=deepcopy(legacy._records);content=self.path.read_bytes()
        legacy._reset_storage()
        self.session=NativeSession(self.engine,self.path,os.environ['PYFA_DATASET_SHA'],spec());self.key=key
        self.assertEqual(self.path.read_bytes(),content);self.assertTrue(self.session.graph.migration_pending)
        self.assertEqual({k:{field:v for field,v in row.items() if field not in ('implant_source','character_implants','character_security')} for k,row in self.session._records.items()},records)
        pid=self.profile();row=self.session.graph._state['profiles']['profiles'][pid]
        self.feature('rename_profile',dict(profile_id=pid,revision=row['revision'],name='Migrated profile'))
        self.assertFalse(self.session.graph.migration_pending);self.assertNotEqual(self.path.read_bytes(),content)
        self.assertEqual(self.session.graph._state['version'],9)
        self.assertEqual(self.session.graph._state['targets'],dict(version=1,profiles={},bindings={}))
        self.assertEqual(self.session.graph._state['damage_patterns'],dict(version=2,patterns={},bindings={}))
        self.assertEqual(self.session.graph._state['imports'],{})
        self.reopen();self.assertEqual(self.session._records[key]['spec']['notes'],'Legacy synthetic note')
        self.assertEqual(self.session.graph._state['profiles']['profiles'][pid]['name'],'Migrated profile')
    def test_multi_document_import_redo_preserves_source_order(self):
        pid=self.profile()
        self.edit('delete_fit',dict(fit_id=self.key,resolve_references=True))
        request=dict(version=1,request_id='ordered-import',profile_id=pid,
                     documents=[dict(label=str(i),text='[Rifter, Imported %s]\n'%i) for i in range(4)])
        preview=json.loads(self.session.import_preview(json.dumps(request)));self.assertTrue(preview['ok'],preview)
        response=json.loads(self.session.import_execute(json.dumps(preview['request'])));self.assertTrue(response['ok'],response)
        ids=response['import_result']['fit_ids']
        before=list(self.session.graph._state['fit_graph']['fit_order'])
        self.assertEqual(before[-4:],ids)
        self.feature('undo',{},anchor=False);self.feature('redo',{},anchor=False)
        self.assertEqual(self.session.graph._state['fit_graph']['fit_order'],before)
        self.assertEqual(self.session.sample_id,ids[0])
    def test_invalid_unicode_profile_names_never_write(self):
        content=self.path.read_bytes();state=self.session.graph.snapshot();pid=self.profile()
        for value in ('Bad\ud800','Bad\udfff'):
            for operation,arguments in (
                ('create_profile',dict(name=value,source='builtin:all5')),
                ('rename_profile',dict(profile_id=pid,revision=state['graph']['profiles']['profiles'][pid]['revision'],name=value))):
                request=dict(version=3,request_id='unicode',context=self.session.context(),operation=operation,
                             arguments=arguments,anchor_fit_id=self.key)
                response=json.loads(self.session.feature_dispatch(json.dumps(request)))
                self.assertFalse(response['ok']);self.assertFalse(response['committed'])
                self.assertEqual(self.path.read_bytes(),content);self.assertEqual(self.session.graph.snapshot(),state)
    def test_legacy_generated_label_sanitizes_surrogate_without_changing_fit(self):
        legacy=deepcopy(self.session.graph._state['fit_graph'])
        legacy['records'][self.key]['spec']['name']='Legacy \ud800 name'
        candidate=self.session.graph._from_legacy(legacy)
        self.assertEqual(candidate['fit_graph']['records'][self.key]['spec']['name'],'Legacy \ud800 name')
        pid=candidate['profiles']['bindings'][self.key]['profile_id']
        label=candidate['profiles']['profiles'][pid]['name']
        self.assertNotIn('\ud800',label)
