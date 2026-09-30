"""B09.1 history regression cases against independent desktop command observations."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from math import isclose
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import compare,digest_file,logical_database_digest,validate_source
from tools.android_headless.check import DEPENDENCIES,NoDesktop


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('database','output','source'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--restore',action='store_true')
    args=parser.parse_args()
    args.database,args.output,args.source=args.database.resolve(strict=True),args.output.resolve(),args.source.resolve(strict=True)
    validate_source(args.source)
    compare(DEPENDENCIES,{name:importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture=ROOT/'tools/android_reference/fixtures/history.json'
    expected=json.loads(fixture.read_text());identity=expected['database_logical_sha256']
    if args.output.is_relative_to(ROOT): raise ValueError('Use fresh output outside checkout')
    if not args.worker and not args.restore:
        compare(identity,logical_database_digest(args.database));before=digest_file(args.database)
        args.output.mkdir(parents=True,exist_ok=False)
        with (args.output/'tests.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),
                '--output',str(args.output),'--source',str(args.source),'--worker'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        compare(before,digest_file(args.database))
        evidence=json.loads((args.output/'evidence.json').read_text())
        evidence.update(task='B09.1',host_only=True,database_sha256=before,database_logical_sha256=identity,
            reference_sha256=digest_file(fixture),game_database_unchanged=True)
        (args.output/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence));return
    guard,network=NoDesktop(),[]
    sys.meta_path.insert(0,guard)
    def audit(event,_):
        if event in ('socket.connect','socket.getaddrinfo','socket.bind'):
            network.append(event);raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.history import LABELS
    engine=HeadlessEngine(args.database)
    def saved(bridge):
        return {'fits':json.loads(bridge.bootstrap())['fits'],'records':deepcopy(bridge._records),
                'recent':bridge.recent_items(),'organization':bridge.organization()}
    def history(bridge,key):
        row=bridge.history_details(key)
        return {'undo_count':row['undo_count'],'redo_count':row['redo_count'],
                'can_undo':row['undo_count']>0,'can_redo':row['redo_count']>0}
    if args.restore:
        bridge=BridgeSession.open(engine,args.output/'fits.db',identity,None)
        compare(json.loads((args.output/'before-restart.json').read_text()),saved(bridge))
        assert all(history(bridge,key)==dict(undo_count=0,redo_count=0,can_undo=False,can_redo=False) for key in bridge._fits)
        (args.output/'restored.json').write_text(json.dumps({'fits':len(bridge._fits),'history_empty':True}))
        return

    class HistoryTests(unittest.TestCase):
        def setUp(self): self.bridge=BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def send(self,operation,arguments,code=None,revision=None):
            keys={arguments[key] for key in ('fit_id','source_id','target_id') if key in arguments}
            result=json.loads(self.bridge.dispatch(json.dumps({'version':1,'session_id':self.bridge.session_id,
                'request_id':'history','operation':operation,'arguments':arguments,
                'expected_revisions':{key:self.bridge._revisions[key] if revision is None else revision for key in keys}})))
            self.assertEqual('ok' if code is None else 'error',result['status'],result.get('error'))
            if code is not None:self.assertEqual(code,result['error']['code'])
            return result
        def create(self,spec=None):
            return self.send('create_fit',{'spec':deepcopy(spec or expected['cases'][0]['spec'])})['fits'][0]['id']
        def state(self,key,recipients):
            fit=self.bridge._fits[key]
            row=self.bridge._snapshots[key]
            return dict(stats=row['stats'],modules=[m for m in row['modules'] if 'empty_slot' not in m],
                ignore_restrictions=fit.ignoreRestrictions,history=history(self.bridge,key),
                recent=self.bridge.recent_items()['item_ids'],recipients=[self.bridge._snapshots[t]['stats'] for t in recipients])
        def equal_state(self,wanted,actual):
            def stats(left,right):
                self.assertEqual(left.keys(),right.keys())
                for name,row in left.items():
                    compare(row['unit'],right[name]['unit']);a,b=row['value'],right[name]['value']
                    if b is None and name in ('gun_optimal','gun_falloff') and a in (0,1):continue
                    if type(a) in (int,float) and type(b) in (int,float):
                        self.assertTrue(isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(name,a,b))
                    else:compare(a,b)
            for field in ('modules','ignore_restrictions','history','recent'):compare(wanted[field],actual[field])
            stats(wanted['stats'],actual['stats'])
            self.assertEqual(len(wanted['recipients']),len(actual['recipients']))
            for a,b in zip(wanted['recipients'],actual['recipients']):stats(a,b)
        def test_all_original_actions_and_repeated_reversals(self):
            covered=set()
            for case in expected['cases']:
                with self.subTest(case=case['name']):
                    self.bridge._reset_storage();self.bridge=BridgeSession(engine)
                    key=self.create(case['spec']);targets=[]
                    for spec in case.get('recipients',[]):
                        target=self.create(spec);targets.append(target)
                        self.send('add_projection',dict(source_id=key,target_id=target,active=True,range_m=0.0,amount=1))
                    for step in case['steps']:
                        prior=self.bridge._revisions[key]
                        if step['action']=='do':
                            covered.add(case['operation'])
                            self.send(case['operation'],dict(fit_id=key,**case['arguments']))
                        elif step['action']!='initial':self.send(step['action'],dict(fit_id=key))
                        if step['action']!='initial':self.assertGreater(self.bridge._revisions[key],prior)
                        self.equal_state(step['result'],self.state(key,targets))
            compare(set(LABELS),covered)
        def test_branch_noop_failure_and_fit_isolation(self):
            key,other=self.create(),self.create()
            for step in expected['branching']:
                if step['action'] in ('submit','noop','failed'):
                    self.send('set_charges',dict(fit_id=key,module_indices=[0],charge=step['charge']),
                              'INVALID_EDIT' if step['action']=='failed' else None)
                else:self.send(step['action'],dict(fit_id=key),None if step['accepted'] else 'INVALID_EDIT')
                compare(step['history'],history(self.bridge,key));compare(step['other_history'],history(self.bridge,other))
                self.assertEqual(step['text'],self.bridge._fits[key].modules[0].charge.name)
            self.send('set_notes',dict(fit_id=key,text=expected['notes_after_undo']))
            self.send('undo',dict(fit_id=key));self.assertEqual(expected['notes_after_undo'],self.bridge.note_details(key)['text'])
        def test_limit_matches_original(self):
            key=self.create()
            for index in range(101):self.send('set_charges',dict(fit_id=key,module_indices=[0],charge='Iron Charge M' if index%2==0 else 'Antimatter Charge M'))
            compare(expected['limit']['before'],history(self.bridge,key))
            for _ in range(expected['limit']['undone']):self.send('undo',dict(fit_id=key))
            compare(expected['limit']['after'],history(self.bridge,key))
            self.assertEqual(expected['limit']['remaining_charge'],self.bridge._fits[key].modules[0].charge.name)
        def test_stale_malformed_and_noop_padding_preserve_cursor(self):
            spec=deepcopy(expected['cases'][0]['spec'])
            spec['modules']=[row for row in spec['modules'] if 'empty_slot' not in row]
            spec.pop('ignore_restrictions',None)
            key=self.create(spec)
            self.send('set_module_charge',dict(fit_id=key,position=0,charge_id=1),'INVALID_EDIT')
            self.send('set_charges',dict(fit_id=key,module_indices=[0],charge='Iron Charge M'))
            self.send('undo',dict(fit_id=key))
            # Original failed/no-op submissions keep redo even if fill introduces spare rows.
            current=self.bridge._fits[key].modules[0].charge.ID
            self.send('set_module_charge',dict(fit_id=key,position=0,charge_id=current))
            self.assertEqual(1,history(self.bridge,key)['redo_count'])
            before=saved(self.bridge);cursor=history(self.bridge,key)
            self.send('redo',dict(fit_id=key),'REVISION_CONFLICT',0)
            self.send('undo',dict(fit_id=key,extra=True),'INVALID_REQUEST')
            compare(before,saved(self.bridge));compare(cursor,history(self.bridge,key))
            self.send('redo',dict(fit_id=key));self.assertEqual('Iron Charge M',self.bridge._fits[key].modules[0].charge.name)
        def test_copy_delete_and_untracked_conflicts(self):
            key=self.create();self.send('remove_module',dict(fit_id=key,position=0))
            response=self.send('duplicate_fit',dict(fit_id=key,name='History copy'))
            copy=next(row['id'] for row in response['fits'] if row['name']=='History copy')
            self.assertEqual(0,history(self.bridge,copy)['undo_count'])
            self.assertEqual(1,history(self.bridge,key)['undo_count'])
            self.send('delete_fit',dict(fit_id=copy,resolve_references=False))
            self.send('undo',dict(fit_id=key))
            # A still-unregistered cargo transfer touches the same module input:
            # B09.2 owns its history, so invalidate safely until registration.
            self.send('transfer_cargo',dict(fit_id=key,direction='TO_CARGO',positions=[0],item_id=None,copy=False))
            self.assertEqual(0,history(self.bridge,key)['redo_count'])
            self.send('undo',dict(fit_id=key),'INVALID_EDIT')
        def test_durable_failure_and_restart_with_empty_session_history(self):
            self.bridge._reset_storage()
            self.bridge=BridgeSession.open(engine,args.output/'fits.db',identity,expected['cases'][0]['spec'])
            key=self.bridge.sample_id;other=self.create()
            self.send('set_charges',dict(fit_id=key,module_indices=[0,1],charge='Iron Charge M'))
            before=saved(self.bridge);cursor=history(self.bridge,key)
            with patch.object(self.bridge._store,'write',side_effect=OSError('synthetic history save failure')):
                self.send('undo',dict(fit_id=key),'ENGINE_ERROR')
            compare(before,saved(self.bridge));compare(cursor,history(self.bridge,key))
            self.send('undo',dict(fit_id=key))
            before=saved(self.bridge);cursor=history(self.bridge,key)
            with patch.object(self.bridge._store,'write',side_effect=OSError('synthetic new branch save failure')):
                self.send('set_charges',dict(fit_id=key,module_indices=[0],charge='Antimatter Charge M'),'ENGINE_ERROR')
            compare(before,saved(self.bridge));compare(cursor,history(self.bridge,key))
            with patch.object(self.bridge._store,'write',side_effect=OSError('synthetic redo save failure')):
                self.send('redo',dict(fit_id=key),'ENGINE_ERROR')
            compare(before,saved(self.bridge));compare(cursor,history(self.bridge,key))
            (args.output/'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            with (args.output/'restart.log').open('w',encoding='utf-8') as log:
                subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),
                    '--output',str(args.output),'--source',str(args.source),'--restore'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
            compare({'fits':2,'history_empty':True},json.loads((args.output/'restored.json').read_text()))

    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HistoryTests))
    if result.testsRun!=6 or not result.wasSuccessful() or result.skipped or guard.attempts or network:
        raise RuntimeError('History regressions failed or attempted forbidden access')
    (args.output/'evidence.json').write_text(json.dumps({'tests_passed':6,'reference_cases':len(expected['cases']),
        'reference_states':sum(len(c['steps']) for c in expected['cases']),'fresh_process_restore':True,'restored_fits':2,
        'desktop_import_attempts':guard.attempts,'network_attempts':network},indent=2)+'\n')


if __name__=='__main__':main()
