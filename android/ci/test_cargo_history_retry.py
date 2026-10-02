"""Reject changes outside the exact observer fix and bounded store recovery."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from zipfile import ZipFile
from unittest.mock import patch
import cargo_history_retry as retry
import report_local
import test_report_local

ROOT=Path(__file__).resolve().parents[2]
BEFORE='287c0c336c0191c78129a017b363dbc3d030adad'

class SourceTest(unittest.TestCase):
    def setUp(self):
        self.old=subprocess.check_output(['git','show',BEFORE+':'+retry.PATH],cwd=ROOT)
        self.new=(ROOT/retry.PATH).read_text().encode()
        self.launcher=(ROOT/'android/ci/local_verification.py').read_bytes()
        self.changed=[retry.PATH,'android/ci/local_verification.py','android/ci/report_local.py',
            'android/ci/cargo_history_retry.py','android/ci/test_cargo_history_retry.py']
    def command(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changed)
        commit,path=args[2].split(':',1)
        if path==retry.PATH:return self.old if commit==BEFORE else self.new
        return self.launcher
    def check(self):
        with patch.object(retry.subprocess,'check_output',side_effect=self.command):retry.exact_source(ROOT,BEFORE,'after')
    def test_exact_observer_passes(self):self.check()
    def test_assertion_change_fails(self):
        self.new=self.new.replace(b'assertEquals(0, history(id).undoCount)',b'assertEquals(1, history(id).undoCount)')
        with self.assertRaises(AssertionError):self.check()
    def test_timeout_change_fails(self):
        self.new=self.new.replace(b'90_000',b'900_000')
        with self.assertRaises(AssertionError):self.check()
    def test_fixture_change_fails(self):
        self.changed.append('tools/android_reference/fixtures/history-mutations.json')
        with self.assertRaises(AssertionError):self.check()
    def test_product_change_fails(self):
        self.changed.append('android_bridge/history.py')
        with self.assertRaises(AssertionError):self.check()

class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads((ROOT/'tools/android_reference/fixtures/history-mutations.json').read_text())
        self.ids=[str(i) for i in range(111)]
        self.extras=['case'+str(i) for i in range(13)]
        names=['Renamed independent — Δ']+['Mutation history '+case['name'] for case in self.fixture['cases'][1:13]]
        self.graph={'sample_id':'0','fit_order':self.ids+self.extras,'recent':[9],
            'records':{key:{'spec':{'name':'old '+key},'commands':[],'projections':[]} for key in self.ids},
            'dataset_identity':'exact','eos_settings':{'exact':True},'format':2}
        self.graph['records'].update({key:{'spec':{'name':name},'commands':[],'projections':[]} for key,name in zip(self.extras,names)})
        self.graph['revisions']={key:7 for key in self.graph['fit_order']}
        self.graph['modified']={key:i for i,key in enumerate(self.graph['fit_order'])}
        self.prior={'after':{'data':[{'id':key,'revision':7} for key in self.ids]},'recent_after':[1,2,3]}
    def check(self):return retry.recovery_graph(self.graph,self.prior,self.fixture)
    def test_all_original_inputs_preserved(self):
        before=copy.deepcopy(self.graph);result=self.check();self.assertEqual(before,self.graph)
        for field in ('records','revisions','modified'):
            self.assertEqual({key:before[field][key] for key in self.ids},result[field])
        self.assertEqual(self.ids,result['fit_order']);self.assertEqual([1,2,3],result['recent'])
        self.assertEqual(before['eos_settings'],result['eos_settings'])
    def test_changed_original_revision_fails(self):
        self.graph['revisions']['0']+=1
        with self.assertRaises(AssertionError):self.check()
    def test_missing_original_fails(self):
        del self.graph['records']['0']
        with self.assertRaises(AssertionError):self.check()
    def test_unknown_extra_fails(self):
        self.graph['records'][self.extras[-1]]['spec']['name']='unrelated fit'
        with self.assertRaises(AssertionError):self.check()
    def test_reordered_original_fails(self):
        self.graph['fit_order'][0:2]=['1','0']
        with self.assertRaises(AssertionError):self.check()
    def test_link_to_removed_fit_fails(self):
        self.graph['records']['0']['projections']=[{'source_id':self.extras[-1]}]
        with self.assertRaises(AssertionError):self.check()
    def test_unknown_modification_entry_fails(self):
        self.graph['modified']['other']=1
        with self.assertRaises(AssertionError):self.check()

class ReceiptTest(unittest.TestCase):
    def setUp(self):
        self.case=test_report_local.LocalResultTest();self.case.setUp()
        self.addCleanup(self.case.doCleanups);self.addCleanup(patch.stopall)
        self.run=self.case.run;archive=self.run/'cargo-sort-fix-original'
        (archive/'apks').mkdir(parents=True);(archive/'recovery').mkdir();(archive/'recovery/recovery.json').write_text('{}')
        (self.run/'apks').mkdir()
        for directory in (archive/'apks',self.run/'apks'):
            (directory/'app-debug.apk').write_bytes(b'unchanged app')
            with ZipFile(directory/'app-debug-androidTest.apk','w') as apk:
                apk.writestr('assets/fixture.json',b'unchanged fixture\r\n')
                apk.writestr('classes.dex',b'old' if directory.parent==archive else b'corrected observer')
        retained=[g for g in self.case.state['plan'] if not g.startswith('native:mutation-history-') and g!='native:summary']
        self.proof={'from_commit':'b'*40,'to_commit':test_report_local.COMMIT,'prepared':True,'installed':True,
            'archive':archive.name,'completed_before_adoption':retained+['native:mutation-history-0-prepare','native:mutation-history-0-restored'],
            'retained_gates':retained,'app_sha256':retry.sha(self.run/'apks/app-debug.apk'),
            'old_test_apk_sha256':retry.sha(archive/'apks/app-debug-androidTest.apk'),
            'new_test_apk_sha256':retry.sha(self.run/'apks/app-debug-androidTest.apk'),
            'recovery_receipt_sha256':retry.sha(archive/'recovery/recovery.json')}
        self.case.state['cargo_observer_reuse']=[self.proof]
        for row in self.case.state['attempts']:
            if row['gate'] in retained:row['tested_commit']='b'*40
        patch.object(retry,'exact_source',return_value=None).start()
        patch.object(retry,'validate_recovery',return_value={}).start();self.case.save()
    def test_valid_receipt_preserves_actual_legacy_commits(self):self.case.validate()
    def test_old_affected_phase_cannot_pass(self):
        next(r for r in self.case.state['attempts'] if r['gate']=='native:mutation-history-0-prepare')['tested_commit']='b'*40
        self.case.save();self.case.reject()
    def test_recovery_receipt_changed_fails(self):
        (self.run/self.proof['archive']/'recovery/recovery.json').write_text('{"changed":true}')
        self.case.save();self.case.reject()
    def test_changed_fixture_even_with_new_hash_fails(self):
        path=self.run/'apks/app-debug-androidTest.apk'
        with ZipFile(path,'w') as apk:apk.writestr('assets/fixture.json',b'changed fixture\r\n')
        self.proof['new_test_apk_sha256']=retry.sha(path);self.case.save();self.case.reject()
    def test_changed_app_fails(self):
        (self.run/'apks/app-debug.apk').write_bytes(b'changed app');self.case.save();self.case.reject()
    def test_uninstalled_correction_fails(self):
        self.proof['installed']=False;self.case.save();self.case.reject()

if __name__=='__main__':unittest.main()
