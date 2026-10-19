"""Focused C04 core parity/transaction/history/restart development check.

Consumes a fresh independent drone_edits.py export. Host-only; not a C04 full
gate, and does not yet cover split/merge, details, mutations or native UI.
"""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import compare, digest_file
from tools.android_reference.drone_edits import observe, PIN
from tools.android_headless.check import NoDesktop, DEPENDENCIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--restore',action='store_true')
    args = parser.parse_args()
    args.database = args.database.resolve(strict=True)
    args.reference = args.reference.resolve(strict=True)
    args.output = args.output.resolve()
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError('Use a fresh output outside checkout and input database')
    expected = json.loads(args.reference.read_text())
    compare(PIN,expected['source_commit'])
    compare(expected['database_sha256'],digest_file(args.database))
    compare(DEPENDENCIES,{name:importlib.metadata.version(name) for name in DEPENDENCIES})
    for relative,digest in expected['source_files'].items():
        compare(digest,digest_file(ROOT/'build/reference-upstream'/relative),relative)
    guard, network = NoDesktop(), []
    sys.meta_path.insert(0,guard)
    def audit(event,arguments):
        if event in ('socket.connect','socket.getaddrinfo','socket.bind'):
            network.append(event)
            raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.store import StoreWriteRejected
    from android_bridge import drones
    engine = HeadlessEngine(args.database)
    identity = json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    def durable_state(bridge):
        return dict(records=deepcopy(bridge._records),
                    observed={key:observe(fit) for key,fit in bridge._fits.items()},
                    revisions=dict(bridge._revisions),recent=bridge.recent_items())
    if args.restore:
        bridge = BridgeSession.open(engine,args.output/'restart.db',identity,None)
        compare(json.loads((args.output/'before-restart.json').read_text()),durable_state(bridge))
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output/'restored.json').write_text(json.dumps(dict(matched=True,host_only=True)))
        return
    args.output.mkdir(parents=True,exist_ok=False)
    observations = []
    class DroneTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def dispatch(self,operation,arguments,ok=True,revision=None):
            named = [arguments['fit_id']] if 'fit_id' in arguments else []
            result = json.loads(self.bridge.dispatch(json.dumps(dict(version=1,request_id='drone-core',
                session_id=self.bridge.session_id,operation=operation,arguments=arguments,
                expected_revisions={key:self.bridge._revisions[key] if revision is None else revision for key in named}))))
            self.assertEqual('ok' if ok else 'error',result['status'],result.get('error'))
            return result
        def create(self,case):
            return self.dispatch('create_fit',dict(spec=deepcopy(case['spec'])))['fits'][0]['id']
        def state(self):
            return dict(durable_state(self.bridge),snapshots=json.loads(self.bridge.bootstrap()),
                        history={key:self.bridge._history.details(key) for key in self.bridge._fits})
        def test_original_parity_undo_redo_and_identity(self):
            covered=set()
            for case in expected['cases']:
                with self.subTest(case=case['spec']['name']):
                    key=self.create(case)
                    compare(case['before'],observe(self.bridge.get_fit(key)))
                    before=deepcopy(self.bridge._records[key])
                    self.dispatch(case['operation'],dict(fit_id=key,**case['arguments']))
                    compare(case['after'],observe(self.bridge.get_fit(key)))
                    after=deepcopy(self.bridge._records[key])
                    self.assertEqual(1,self.bridge._history.details(key)['undo_count'])
                    if case['operation']=='clone_drone':
                        ids=after['inspection_ids']['drones']
                        self.assertEqual(len(ids),len(set(ids)))
                        self.assertEqual(before['inspection_ids']['drones'],ids[:-1])
                    self.dispatch('undo',dict(fit_id=key))
                    compare(case['restored'],observe(self.bridge.get_fit(key)))
                    compare(before['spec']['drones'],self.bridge._records[key]['spec']['drones'])
                    compare(before['inspection_ids']['drones'],self.bridge._records[key]['inspection_ids']['drones'])
                    self.dispatch('redo',dict(fit_id=key))
                    compare(case['after'],observe(self.bridge.get_fit(key)))
                    compare(after['inspection_ids']['drones'],self.bridge._records[key]['inspection_ids']['drones'])
                    observations.append(case['spec']['name'])
                    covered.add(case['operation'])
            compare(sorted(drones.ORIGINAL_OPERATIONS),sorted(covered))
        def test_every_operation_rolls_back_after_mutation_and_stale_revision(self):
            real=drones.change
            def fail(*args,**kwargs):
                real(*args,**kwargs)
                raise RuntimeError('Injected after drone mutation')
            seen=set()
            for case in expected['cases']:
                if case['operation'] in seen: continue
                seen.add(case['operation'])
                key=self.create(case)
                before=self.state()
                with patch.object(drones,'change',side_effect=fail):
                    self.dispatch(case['operation'],dict(fit_id=key,**case['arguments']),False)
                compare(before,self.state())
                self.dispatch(case['operation'],dict(fit_id=key,**case['arguments']),False,revision=0)
                compare(before,self.state())
            compare(sorted(drones.ORIGINAL_OPERATIONS),sorted(seen))
        def test_invalid_selections_and_amounts_are_atomic(self):
            case=next(row for row in expected['cases'] if row['operation']=='clone_drone')
            key=self.create(case)
            requests=[('add_drone',dict(item_id=2454,amount=value)) for value in (True,-1,0,2**31,1.5)]
            requests += [('set_drone_amount',dict(position=0,amount=value)) for value in (False,-1,2**31)]
            requests += [('remove_drones',dict(positions=value,amount=1)) for value in ([],[0,0],[0,999],[True],None)]
            requests += [('toggle_drones',dict(main_position=0,positions=value)) for value in ([0,0],[0,999],[True],None)]
            requests += [('clone_drone',dict(position=value)) for value in (-1,999,True)]
            requests += [('add_drone',dict(item_id=587,amount=1))] # Rifter is not a drone.
            for operation,arguments in requests:
                with self.subTest(operation=operation,arguments=arguments):
                    before=self.state()
                    self.dispatch(operation,dict(fit_id=key,**arguments),False)
                    compare(before,self.state())
        def test_each_operation_rejected_store_write_and_restart(self):
            self.bridge._reset_storage()
            seen=set()
            for case in expected['cases']:
                if case['operation'] in seen: continue
                seen.add(case['operation'])
                path=args.output/(case['operation']+'.db')
                self.bridge=BridgeSession.open(engine,path,identity,case['spec'])
                key=self.bridge.sample_id
                before=self.state(); file_before=path.read_bytes()
                with patch.object(self.bridge._store,'write',side_effect=StoreWriteRejected('Injected write rejection')):
                    self.dispatch(case['operation'],dict(fit_id=key,**case['arguments']),False)
                compare(before,self.state())
                self.assertEqual(file_before,path.read_bytes())
                self.dispatch(case['operation'],dict(fit_id=key,**case['arguments']))
                self.bridge._reset_storage()
            compare(sorted(drones.ORIGINAL_OPERATIONS),sorted(seen))
            case=next(row for row in expected['cases'] if row['operation']=='clone_drone')
            self.bridge=BridgeSession.open(engine,args.output/'restart.db',identity,case['spec'])
            key=self.bridge.sample_id
            self.dispatch('clone_drone',dict(fit_id=key,position=0))
            self.dispatch('set_drone_amount',dict(fit_id=key,position=1,amount=2))
            self.dispatch('toggle_drones',dict(fit_id=key,main_position=1,positions=[0,1]))
            (args.output/'before-restart.json').write_text(json.dumps(durable_state(self.bridge),allow_nan=False))
        def test_clone_isolation_and_history_branch(self):
            case=next(row for row in expected['cases'] if row['operation']=='clone_drone')
            key=self.create(case)
            self.dispatch('clone_drone',dict(fit_id=key,position=0))
            source=deepcopy(self.bridge._records[key]['spec']['drones'][0])
            self.dispatch('set_drone_amount',dict(fit_id=key,position=1,amount=2))
            compare(source,self.bridge._records[key]['spec']['drones'][0])
            self.dispatch('undo',dict(fit_id=key))
            self.dispatch('remove_drones',dict(fit_id=key,positions=[1],amount=1))
            self.assertEqual(0,self.bridge._history.details(key)['redo_count'])
            before=self.state()
            self.dispatch('redo',dict(fit_id=key),False)
            compare(before,self.state())
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DroneTests))
    if not result.wasSuccessful(): raise SystemExit(1)
    with (args.output/'restart.log').open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--database',str(args.database),
                        '--reference',str(args.reference),'--output',str(args.output),'--restore'],
                       check=True,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    assert not guard.attempts and not network
    evidence=dict(host_only=True,stage='C04 core development slice',tests=result.testsRun,
                  original_cases=observations,operations=sorted(drones.ORIGINAL_OPERATIONS),
                  reference_sha256=digest_file(args.reference),database_sha256=digest_file(args.database),
                  fresh_process_restart=json.loads((args.output/'restored.json').read_text()),
                  source_files={str(path.relative_to(ROOT)):digest_file(path) for path in
                    [ROOT/'android_bridge/drones.py',ROOT/'android_bridge/contract.py',ROOT/'android_bridge/history.py',
                     Path(__file__).resolve()]},
                  pending=['split/merge decision and implementation','mutation distinctions','complete details/families',
                           'native UI/build/offline/restart','complete inherited and C04 full verification'])
    (args.output/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence))


if __name__=='__main__': main()
