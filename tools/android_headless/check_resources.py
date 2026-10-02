"""C01.1 real EOS resources, presentation, read-only boundaries and durable reopening."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import gc
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import compare,digest_file,logical_database_digest,validate_source
from tools.android_headless.check import DEPENDENCIES,NoDesktop


def compare_resources(expected,actual):
    compare(set(expected),set(actual))
    for name,row in expected.items():
        value=actual[name]
        compare(set(value),{'used','total','used_type','total_type','unit','overloaded',
                            'used_display','total_display','used_detail','total_detail'})
        for key in ('used','total','unit','overloaded'): compare(row[key],value[key],name+'.'+key)
        for key in ('used','total'):
            kind='unavailable' if row[key] is None else 'integer' if type(row[key]) is int else 'decimal'
            compare(kind,value[key+'_type'])
            compare(None if row[key] is None else row['desktop_'+key],value[key+'_display'])
            compare(None if row[key] is None else row['desktop_'+key+'_detail'],value[key+'_detail'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('database','source','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--restore',action='store_true')
    args=parser.parse_args()
    args.database,args.source,args.output=args.database.resolve(strict=True),args.source.resolve(strict=True),args.output.resolve()
    validate_source(args.source)
    compare(DEPENDENCIES,{n:importlib.metadata.version(n) for n in DEPENDENCIES})
    fixture=ROOT/'tools/android_reference/fixtures/resources.json'
    expected=json.loads(fixture.read_text())
    identity=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    if args.output.is_relative_to(ROOT): raise ValueError('Use fresh external output')
    if not args.worker and not args.restore:
        compare(identity,logical_database_digest(args.database));before=digest_file(args.database)
        args.output.mkdir(parents=True,exist_ok=False)
        with (args.output/'tests.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),
                '--source',str(args.source),'--output',str(args.output),'--worker'],stdout=log,stderr=subprocess.STDOUT,
                check=True,timeout=300)
        compare(before,digest_file(args.database))
        with (args.output/'validator-tests.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(ROOT/'android/ci/test_resource_summary.py')],
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        receipt=json.loads((args.output/'evidence.json').read_text())
        receipt.update(task='C01.1',host_only=True,database_sha256=before,database_logical_sha256=identity,
                       fixture_sha256=digest_file(fixture),game_database_unchanged=True,validator_tests_passed=8)
        (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));return
    guard,network=NoDesktop(),[];sys.meta_path.insert(0,guard)
    def audit(event,_):
        if event in ('socket.connect','socket.getaddrinfo','socket.bind'):
            network.append(event);raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.resources import details,_number
    engine=HeadlessEngine(args.database)
    compare(expected['eos_settings'],engine.settings)
    if args.restore:
        bridge=BridgeSession.open(engine,args.output/'fits.db',identity,None)
        before=json.loads((args.output/'before-restart.json').read_text())
        compare(before,{key:bridge.resource_details(key) for key in bridge._fits})
        assert all(bridge.history_details(k)['undo_count']==bridge.history_details(k)['redo_count']==0 for k in bridge._fits)
        (args.output/'restored.json').write_text(json.dumps(dict(fits=len(bridge._fits),history_empty=True)))
        return

    class ResourceTests(unittest.TestCase):
        def setUp(self): self.bridge=BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def send(self,operation,arguments):
            named={arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}
            value=json.loads(self.bridge.dispatch(json.dumps(dict(version=1,request_id='resources',
                session_id=self.bridge.session_id,operation=operation,arguments=arguments,
                expected_revisions={k:self.bridge._revisions[k] for k in named}))))
            self.assertEqual('ok',value['status'],value['error']);return value
        def create(self,spec):
            old=set(self.bridge._fits);self.send('create_fit',dict(spec=spec));return (set(self.bridge._fits)-old).pop()
        def case(self,name): return next(c for c in expected['cases'] if c['spec']['name']==name)
        def state(self,key):
            return deepcopy(dict(records=self.bridge._records,revisions=self.bridge._revisions,
                recent=self.bridge.recent_items(),organization=self.bridge.organization(),history=self.bridge.history_details(key)))

        def test_full_independent_matrix_and_fighters(self):
            actual=[]
            for row in expected['cases']:
                print('RESOURCE CASE',row['spec']['name'],flush=True)
                if row['execution']=='durable':
                    key=self.create(row['spec']);value=self.bridge.resource_details(key)['resources']
                else:
                    # Real EOS provisional diagnostic inputs; no fighter editor or
                    # persistence support is claimed by C01's read-only statistics.
                    from android_bridge.resource_probe import run
                    value=run(engine,row['spec'],row['fighters'])
                compare_resources(row['resources'],value);actual.append(dict(name=row['spec']['name'],resources=value))
            (args.output/'matrix.json').write_text(json.dumps(actual,indent=2,allow_nan=False)+'\n')

        def test_queries_leave_inputs_history_and_recent_unchanged_after_gc(self):
            row=self.case('Fitted cruiser');key=self.create(row['spec'])
            self.send('rename_fit',dict(fit_id=key,name='Read-only resource fit'))
            before=self.state(key)
            for _ in range(3):
                gc.collect();compare_resources(row['resources'],self.bridge.resource_details(key)['resources'])
                compare(before,self.state(key))

        def test_edit_undo_redo_and_copy_refresh_correct_resources(self):
            key=self.create(self.case('Empty cruiser')['spec']);before=self.bridge.resource_details(key)
            self.send('set_skill_level',dict(fit_id=key,skill='CPU Management',level=0))
            changed=self.bridge.resource_details(key)
            self.assertLess(changed['resources']['cpu']['total'],before['resources']['cpu']['total'])
            self.send('undo',dict(fit_id=key));compare(before['resources'],self.bridge.resource_details(key)['resources'])
            self.send('redo',dict(fit_id=key));compare(changed['resources'],self.bridge.resource_details(key)['resources'])
            old=set(self.bridge._fits);self.send('duplicate_fit',dict(fit_id=key,name='Resource copy'))
            copy=(set(self.bridge._fits)-old).pop();compare(changed['resources'],self.bridge.resource_details(copy)['resources'])
            self.assertEqual(0,self.bridge.history_details(copy)['undo_count'])

        def test_invalid_identity_wrong_thread_and_unavailable_engine_fail(self):
            key=self.create(self.case('Empty cruiser')['spec'])
            with self.assertRaises(KeyError): self.bridge.resource_details('missing')
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaises(RuntimeError): pool.submit(self.bridge.resource_details,key).result()
            self.bridge._available=False
            with self.assertRaises(RuntimeError): self.bridge.resource_details(key)

        def test_diagnostic_inputs_do_not_expand_saved_fit_creation(self):
            for row in expected['cases']:
                if row['execution']=='durable': continue
                spec=deepcopy(row['spec'])
                if row['fighters']: spec['fighters']=row['fighters']
                before=deepcopy(self.bridge._records)
                response=json.loads(self.bridge.dispatch(json.dumps(dict(version=1,request_id='diagnostic-boundary',
                    session_id=self.bridge.session_id,operation='create_fit',arguments=dict(spec=spec),expected_revisions={}))))
                self.assertEqual('error',response['status'])
                self.assertEqual('INVALID_REQUEST' if row['fighters'] else 'INVALID_EDIT',response['error']['code'])
                compare(before,self.bridge._records)

        def test_presentation_source_is_exact_and_boundary_rounding_matches(self):
            def body(text):
                nodes=ast.parse(text).body
                return ast.dump(ast.Module(body=[n for n in nodes if not isinstance(n,ast.Expr)],type_ignores=[]),include_attributes=False)
            compare(body((args.source/'gui/utils/numberFormatter.py').read_text()),body((ROOT/'android_bridge/number_format.py').read_text()))
            from android_bridge.number_format import formatAmount
            compare('1M',formatAmount(999999,3,0,9))
            compare('906.2',formatAmount(906.25,4,0,9))
            compare('',formatAmount(None))  # Resource serialization intercepts this as explicit null.
            self.assertEqual('unavailable',_number(None))
            for invalid in (True,float('nan'),float('inf'),'0'):
                with self.assertRaises(ValueError): _number(invalid)

        def test_durable_resource_values_reopen_in_a_fresh_process(self):
            self.bridge=BridgeSession.open(engine,args.output/'fits.db',identity,self.case('Empty cruiser')['spec'])
            for row in expected['cases'][1:]:
                if row['execution']=='durable': self.create(row['spec'])
            before={key:self.bridge.resource_details(key) for key in self.bridge._fits}
            (args.output/'before-restart.json').write_text(json.dumps(before,allow_nan=False))
            with (args.output/'restart.log').open('w',encoding='utf-8') as log:
                subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),
                    '--source',str(args.source),'--output',str(args.output),'--restore'],stdout=log,stderr=subprocess.STDOUT,
                    check=True,timeout=120)
            self.assertEqual(dict(fits=len(before),history_empty=True),json.loads((args.output/'restored.json').read_text()))

    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ResourceTests))
    if result.testsRun!=7 or not result.wasSuccessful() or result.skipped or guard.attempts or network:
        raise RuntimeError('Resource checks failed or attempted forbidden access')
    (args.output/'evidence.json').write_text(json.dumps(dict(tests_passed=7,reference_cases=len(expected['cases']),resource_pairs=11,
        fresh_process_restore=True,restored=json.loads((args.output/'restored.json').read_text()),
        desktop_import_attempts=guard.attempts,network_attempts=network),indent=2)+'\n')


if __name__=='__main__': main()
