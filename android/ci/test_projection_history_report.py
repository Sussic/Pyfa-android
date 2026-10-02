"""Projection decimals require exact values and retained kinds after JSONObject."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import mutation_history_summary as summary
import projection_history_retry as retry
from test_mutation_history_summary import FIXTURE,typed
import test_stale_history_retry

ROOT=Path(__file__).resolve().parents[2]
BEFORE='7812de8024259d890e77435f794e69f71e75326b'

class ProjectionTest(unittest.TestCase):
    def setUp(self):
        self.case=deepcopy(next(c for c in FIXTURE['cases'] if c['name']=='projection-configure'))
        self.step=self.case['steps'][1];self.actual=typed(deepcopy(self.step['result']))
        self.path='root.projections[0].range_m'
    def check(self):summary.state(self.case,self.step,self.actual,[])
    def test_integral_double_json_representation_with_decimal_kind_passes(self):
        self.actual['data']['projections'][0]['range_m']=int(self.actual['data']['projections'][0]['range_m'])
        before=deepcopy(self.actual);self.check();self.assertEqual(before,self.actual)
    def test_all_projection_fixture_states_after_json_serialization(self):
        count=0
        for case in FIXTURE['cases']:
            if 'projection' not in case['operation']:continue
            for step in case['steps']:
                actual=typed(deepcopy(step['result']))
                for row in actual['data']['projections']:
                    if row['range_m'].is_integer():row['range_m']=int(row['range_m'])
                summary.state(case,step,actual,[]);count+=1
        self.assertEqual(18,count)
    def test_wrong_or_missing_decimal_kind_fails(self):
        for kind in ('integer','boolean',None):
            actual=deepcopy(self.actual)
            if kind is None:actual['numeric_types'].pop(self.path)
            else:actual['numeric_types'][self.path]=kind
            with self.assertRaises(AssertionError):summary.state(self.case,self.step,actual,[])
    def test_changed_range_value_fails_without_tolerance(self):
        for delta in (1e-6,1):
            actual=deepcopy(self.actual);actual['data']['projections'][0]['range_m']+=delta
            with self.assertRaises(AssertionError):summary.state(self.case,self.step,actual,[])
    def test_boolean_string_and_nonfinite_ranges_fail(self):
        for value in (True,'0',float('nan'),float('inf')):
            actual=deepcopy(self.actual);actual['data']['projections'][0]['range_m']=value
            with self.assertRaises(AssertionError):summary.state(self.case,self.step,actual,[])
    def test_other_projection_fields_remain_exactly_typed(self):
        for value in (1.0,True):
            actual=deepcopy(self.actual);actual['data']['projections'][0]['amount']=value
            with self.assertRaises(AssertionError):summary.state(self.case,self.step,actual,[])
    def test_changed_source_and_missing_projection_field_fail(self):
        for change in (lambda row:row.update(source_name='wrong source'),lambda row:row.pop('active')):
            actual=deepcopy(self.actual);change(actual['data']['projections'][0])
            with self.assertRaises(AssertionError):summary.state(self.case,self.step,actual,[])
    def test_lossy_integer_to_double_conversion_fails(self):
        step=deepcopy(self.step);step['result']['projections'][0]['range_m']=float(2**53)
        actual=typed(deepcopy(step['result']));actual['data']['projections'][0]['range_m']=2**53+1
        with self.assertRaises(AssertionError):summary.state(self.case,step,actual,[])

class SourceTest(unittest.TestCase):
    def setUp(self):
        paths=('android/ci/mutation_history_summary.py','android/ci/test_pending_settings_fix.py','android/ci/local_verification.py')
        self.old={p:subprocess.check_output(['git','show',BEFORE+':'+p],cwd=ROOT,text=True,encoding='utf-8') for p in paths}
        self.new={p:(ROOT/p).read_text() for p in paths}
        self.changed=list(paths)+['android/ci/projection_history_retry.py','android/ci/test_projection_history_report.py','android/ci/revalidate-projection-history.py','android/ci/report_local.py']
    def command(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changed)
        commit,path=args[2].split(':',1);return (self.old if commit==BEFORE else self.new)[path]
    def check(self):
        with patch.object(retry.subprocess,'check_output',side_effect=self.command):retry.exact_source(ROOT,BEFORE,'after')
    def test_exact_decimal_projection_comparison_passes(self):self.check()
    def test_precision_guard_removal_fails(self):
        p='android/ci/mutation_history_summary.py';self.new[p]=self.new[p].replace(' and float(other) == other','')
        with self.assertRaises(AssertionError):self.check()
    def test_other_fields_relaxation_fails(self):
        p='android/ci/mutation_history_summary.py';self.new[p]=self.new[p].replace('else: exact(value, other)','else: assert value == other')
        with self.assertRaises(AssertionError):self.check()
    def test_statistic_tolerance_change_fails(self):
        p='android/ci/mutation_history_summary.py';self.new[p]=self.new[p].replace('abs_tol=1e-9','abs_tol=1e-6')
        with self.assertRaises(AssertionError):self.check()
    def test_native_or_fixture_change_fails(self):
        for path in ('android/app/src/androidTest/java/io/github/sussic/pyfa/MutationHistoryTest.kt','tools/android_reference/fixtures/history-mutations.json'):
            with self.subTest(path=path):
                self.changed.append(path)
                with self.assertRaises(AssertionError):self.check()
                self.changed.pop()

class ReceiptTest(unittest.TestCase):
    def setUp(self):
        self.base=test_stale_history_retry.ReceiptTest();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.case=self.base.case;self.run=self.case.run;old=self.case.state['commit'];new='d'*40
        archive=self.run/'projection-range-fix-original';archive.mkdir()
        import shutil
        hashes={}
        for suffix in ('native.json','instrumentation.txt'):
            name='mutation-history-3-prepare-'+suffix;(self.run/'native'/name).write_text('{}' if suffix=='native.json' else 'retained successful instrumentation')
            shutil.copyfile(self.run/'native'/name,archive/name);hashes[name]=summary.hashlib.sha256((archive/name).read_bytes()).hexdigest()
        apks={p.name:summary.hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.run/'apks').glob('*.apk')}
        self.proof={'from_commit':old,'to_commit':new,'validated':True,'archive':archive.name,'retained_hashes':hashes,'apk_hashes':apks,
            'retained_gates':self.base.proof['retained_gates']}
        self.case.state['projection_report_reuse']=[self.proof];self.case.state['commit']=new;self.case.review['tested_commit']=new
        for row in self.case.state['attempts']:
            if row['gate'] not in self.proof['retained_gates']:row['tested_commit']=new
            if row['gate']=='native:mutation-history-3-prepare':row['retained_native_execution_commit']=old
        p=self.run/'native/native-summary.json';s=json.loads(p.read_text());s['checkout_sha']=new;p.write_text(json.dumps(s))
        patch.object(retry,'exact_source',return_value=None).start();self.case.save()
    def test_valid_retained_instrumentation_chain(self):self.case.validate()
    def test_report_modified_even_with_new_manifest_fails(self):
        (self.run/'native/mutation-history-3-prepare-native.json').write_text('{"changed":true}');self.case.save();self.case.reject()
    def test_wrong_execution_commit_fails(self):
        next(r for r in self.case.state['attempts'] if r['gate']=='native:mutation-history-3-prepare')['retained_native_execution_commit']='0'*40
        self.case.save();self.case.reject()
    def test_missing_apk_proof_fails(self):
        self.proof['apk_hashes'].pop('app-debug-androidTest.apk');self.case.save();self.case.reject()
    def test_unvalidated_projection_repair_fails(self):
        self.proof['validated']=False;self.case.save();self.case.reject()

if __name__=='__main__':unittest.main()
