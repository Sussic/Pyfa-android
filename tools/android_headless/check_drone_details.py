"""Focused C04 existing-mutation, family-detail and persistence development checks."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_headless.check import DEPENDENCIES,NoDesktop
from tools.android_reference.reference import compare,digest_file
from tools.android_reference.drone_edits import PIN

def source_provenance(root,baseline='5e4a6207'):
    """Hash present changed sources and retain explicit historical deletion evidence."""
    def git(*arguments):
        return subprocess.check_output(['git',*arguments],cwd=root,text=True,encoding='utf-8')
    commit=git('rev-parse','--verify',baseline+'^{commit}').strip()
    changed=git('diff','--name-only','--no-renames','--diff-filter=d','-z',commit,'--').split('\0')
    deleted=git('diff','--name-only','--no-renames','--diff-filter=D','-z',commit,'--').split('\0')
    new=git('ls-files','--others','--exclude-standard','-z').split('\0')
    return dict(source_baseline_commit=commit,
        source_files={relative:digest_file(root/relative) for relative in sorted(set(changed+new))
                      if relative.endswith(('.py','.kt'))},
        deleted_source_files={relative:'D' for relative in sorted(deleted)
                              if relative.endswith(('.py','.kt'))})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('database','reference','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--restore',action='store_true')
    args=p.parse_args()
    args.database=args.database.resolve(strict=True); args.reference=args.reference.resolve(strict=True)
    args.output=args.output.resolve()
    assert not args.output.is_relative_to(ROOT) and not args.database.is_relative_to(args.output)
    expected=json.loads(args.reference.read_text())
    compare(PIN,expected['source_commit']); compare(expected['database_sha256'],digest_file(args.database))
    compare(DEPENDENCIES,{name:importlib.metadata.version(name) for name in DEPENDENCIES})
    for relative,digest in expected['source_files'].items():
        compare(digest,digest_file(ROOT/'build/reference-upstream'/relative),relative)
    guard,network=NoDesktop(),[]
    sys.meta_path.insert(0,guard)
    def audit(event,arguments):
        if event in ('socket.connect','socket.getaddrinfo','socket.bind'):
            network.append(event); raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.store import GraphStore,StoreWriteRejected,StoreError
    from android_bridge import drone_records,drones
    engine=HeadlessEngine(args.database)
    identity=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    def state(bridge,history=True):
        value=dict(records=deepcopy(bridge._records),revisions=dict(bridge._revisions),
                   details={key:bridge.drone_details(key) for key in bridge._fits},recent=bridge.recent_items())
        if history: value['history']={key:bridge._history.details(key) for key in bridge._fits}
        return value
    if args.restore:
        bridge=BridgeSession.open(engine,args.output/'existing-rolls.db',identity,None)
        compare(json.loads((args.output/'before-restart.json').read_text()),state(bridge,False))
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output/'restored.json').write_text(json.dumps(dict(matched=True,mutated_stacks=sum(
            'mutation' in row for record in bridge._records.values() for row in record['spec']['drones']))))
        return
    args.output.mkdir(parents=True,exist_ok=False)
    observed=[]
    class Tests(unittest.TestCase):
        def setUp(self): self.bridge=BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def adopt(self,case):
            self.bridge._reset_storage()
            spec=deepcopy(case['spec'])
            fit=engine.create_fit(spec,restore=True)
            self.bridge=BridgeSession(engine,fit,spec)
            return self.bridge.sample_id
        def dispatch(self,operation,arguments,ok=True):
            keys=[arguments['fit_id']] if 'fit_id' in arguments else []
            result=json.loads(self.bridge.dispatch(json.dumps(dict(version=1,request_id='drone-details',
                session_id=self.bridge.session_id,operation=operation,arguments=arguments,
                expected_revisions={key:self.bridge._revisions[key] for key in keys}))))
            self.assertEqual('ok' if ok else 'error',result['status'],result.get('error'))
            return result
        def test_original_details_all_families_patterns_skills_and_distinct_rolls(self):
            for case in expected['cases']:
                with self.subTest(case=case['spec']['name']):
                    key=self.adopt(case); before=deepcopy(self.bridge._records)
                    details=self.bridge.drone_details(key)
                    compare(case['resources'],{name:details[name] for name in case['resources']})
                    self.assertEqual(len(case['stacks']),len(details['stacks']))
                    for want,got in zip(case['stacks'],details['stacks']):
                        compare({k:v for k,v in want.items() if k!='metrics'},
                                {k:got[k] for k in want if k!='metrics'})
                        compare(want['metrics'],{row['key']:row['value'] for row in got['metrics']})
                        self.assertTrue(all(bool(row['unit']) and ((row['value'] is None)==(row['text'] is None)) for row in got['metrics']))
                    compare(case['spec']['drones'],self.bridge._records[key]['spec']['drones'])
                    compare(before,self.bridge._records) # Reads must not modify stored inputs.
                    by_type={row['item_id']:{metric['key']:metric['value'] for metric in row['metrics']} for row in details['stacks']}
                    for item_id,metric_key in ((2454,'dps_total'),(10250,'mining_yield'),(32787,'accessDifficultyBonus'),
                                        (23719,'remote_shield'),(23707,'scanGravimetricStrengthBonus'),
                                        (23659,'energyNeutralizerAmount'),(23659,'energyNeutralizerDuration')):
                        self.assertGreater(by_type[item_id][metric_key],0,(item_id,metric_key))
                    self.assertLess(by_type[23731]['speedFactor'],0)
                    self.assertLess(by_type[23727]['trackingSpeedBonus'],0)
                    self.assertLess(by_type[23715]['scanResolutionBonus'],0)
                    self.assertGreater(by_type[23723]['signatureRadiusBonus'],0)
                    left,right=details['stacks'][-2:]
                    self.assertEqual(left['item_id'],right['item_id'])
                    self.assertNotEqual(left['object_key'],right['object_key'])
                    self.assertNotEqual(left['mutation']['attributes'],right['mutation']['attributes'])
                    self.assertEqual([],self.bridge.variation_options(key)['targets'][-1]['choices'])
                    observed.append(dict(case=case['spec']['name'],stacks=len(details['stacks']),
                                         metrics=sum(len(row['metrics']) for row in details['stacks'])))
        def test_rolled_clone_history_duplicate_and_rejected_conversion(self):
            key=self.adopt(expected['cases'][-1]); before=state(self.bridge)
            original=deepcopy(self.bridge._records[key]['spec']['drones'][13])
            self.dispatch('clone_drone',dict(fit_id=key,position=13))
            compare(original,self.bridge._records[key]['spec']['drones'][-1])
            self.dispatch('set_drone_amount',dict(fit_id=key,position=15,amount=2))
            compare(original,self.bridge._records[key]['spec']['drones'][13])
            compare(original['mutation'],self.bridge._records[key]['spec']['drones'][15]['mutation'])
            self.dispatch('undo',dict(fit_id=key)); self.dispatch('undo',dict(fit_id=key))
            compare(before['records'],self.bridge._records)
            self.dispatch('redo',dict(fit_id=key)); self.dispatch('redo',dict(fit_id=key))
            before=state(self.bridge)
            self.dispatch('change_variation',dict(fit_id=key,context='drone',position=13,item_id=2456),False)
            compare(before,state(self.bridge))
            copy_key=self.dispatch('duplicate_fit',dict(fit_id=key,name='Synthetic mutated copy'))['fits'][-1]['id']
            self.assertNotEqual(key,copy_key)
            compare(self.bridge._records[key]['spec']['drones'],self.bridge._records[copy_key]['spec']['drones'])
            self.assertTrue(set(self.bridge._records[key]['inspection_ids']['drones']).isdisjoint(
                self.bridge._records[copy_key]['inspection_ids']['drones']))
        def test_mutation_creation_and_invalid_saved_rolls_are_rejected(self):
            case=expected['cases'][-1]; key=self.adopt(case); before=state(self.bridge)
            self.dispatch('create_fit',dict(spec=case['spec']),False)
            compare(before,state(self.bridge))
            row=case['spec']['drones'][13]
            invalid=[]
            def bad(change):
                value=deepcopy(row); change(value['mutation']); invalid.append(value)
            bad(lambda m:m.update(base_item_id=587))
            bad(lambda m:m.update(mutaplasmid_id=2454))
            bad(lambda m:m['attributes'].pop())
            bad(lambda m:m['attributes'].append(deepcopy(m['attributes'][0])))
            bad(lambda m:m['attributes'][0].update(value=float('nan')))
            bad(lambda m:m['attributes'][0].update(value=True))
            bad(lambda m:m['attributes'][0].update(value=1e100))
            for value in invalid:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError): drone_records.restore(engine,value)
            compare(before,state(self.bridge))
        def test_mutated_failures_and_durable_restart(self):
            key=self.adopt(expected['cases'][-1])
            before=state(self.bridge); real=drones.change
            def fail(*a,**k): real(*a,**k); raise RuntimeError('Injected after rolled clone')
            with patch.object(drones,'change',side_effect=fail):
                self.dispatch('clone_drone',dict(fit_id=key,position=13),False)
            compare(before,state(self.bridge))
            # Attach the already existing synthetic graph to a durable store.
            # No public mutation creation/edit operation is added or invoked.
            self.bridge._store=GraphStore(args.output/'existing-rolls.db')
            self.bridge._dataset_identity=identity
            store=self.bridge._store
            attempt=store.prepare(self.bridge._graph(self.bridge._records,self.bridge._revisions))
            self.assertEqual('new',self.bridge._write_and_confirm(attempt)); store.accept(attempt)
            before=state(self.bridge); bytes_before=store.path.read_bytes()
            with patch.object(store,'write',side_effect=StoreWriteRejected('Injected rolled save rejection')):
                self.dispatch('clone_drone',dict(fit_id=key,position=13),False)
            compare(before,state(self.bridge)); self.assertEqual(bytes_before,store.path.read_bytes())
            self.dispatch('clone_drone',dict(fit_id=key,position=13))
            self.dispatch('set_drone_amount',dict(fit_id=key,position=15,amount=2))
            self.dispatch('toggle_drones',dict(fit_id=key,main_position=15,positions=[13,14]))
            (args.output/'before-restart.json').write_text(json.dumps(state(self.bridge,False),allow_nan=False))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful(): raise SystemExit(1)
    with (args.output/'restart.log').open('w') as log:
        subprocess.run([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--database',str(args.database),
            '--reference',str(args.reference),'--output',str(args.output),'--restore'],check=True,
            stdout=log,stderr=subprocess.STDOUT,timeout=90)
    assert not guard.attempts and not network
    evidence=dict(host_only=True,tests=result.testsRun,observations=observed,
        fresh_process_restart=json.loads((args.output/'restored.json').read_text()),
        reference_sha256=digest_file(args.reference),database_sha256=digest_file(args.database),
        **source_provenance(ROOT),
        limitations=['Native source has not been built or executed','Split/merge unresolved',
                     'Full inherited and integrated C04 verification not run'])
    (args.output/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence))

if __name__=='__main__': main()
