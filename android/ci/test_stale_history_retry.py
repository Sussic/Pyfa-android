"""Preserve typed rejection criteria and retain only unaffected final-group inputs."""
import copy,json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import stale_history_retry as retry
import test_cargo_history_retry as cargo_test
import test_report_local
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[2]
BEFORE='66e89f31864ff12396f02dd420f5b3b5a1a5fd00'

class SourceTest(unittest.TestCase):
    def setUp(self):
        self.old={path:subprocess.check_output(['git','show',BEFORE+':'+path],cwd=ROOT,text=True,encoding='utf-8') for path in (retry.PATH,'android/ci/cargo_history_retry.py','android/ci/local_verification.py','android/ci/test_cargo_history_retry.py')}
        self.new={path:(ROOT/path).read_text() for path in self.old}
        self.changed=[retry.PATH,'android/ci/cargo_history_retry.py','android/ci/stale_history_retry.py','android/ci/test_stale_history_retry.py','android/ci/test_cargo_history_retry.py','android/ci/local_verification.py','android/ci/report_local.py']
    def command(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changed)
        commit,path=args[2].split(':',1);return (self.old if commit==BEFORE else self.new)[path]
    def check(self):
        with patch.object(retry.subprocess,'check_output',side_effect=self.command):retry.exact_source(ROOT,BEFORE,'after')
    def test_exact_typed_error_and_wire_name_pass(self):self.check()
    def test_different_error_fails(self):
        self.new[retry.PATH]=self.new[retry.PATH].replace('assertEquals(BridgeErrorCode.REVISION_CONFLICT','assertEquals(BridgeErrorCode.INVALID_ARGUMENT')
        with self.assertRaises(AssertionError):self.check()
    def test_success_assertion_change_fails(self):
        self.new[retry.PATH]=self.new[retry.PATH].replace('assertFalse(rejected.isSuccess)','assertTrue(rejected.isSuccess)')
        with self.assertRaises(AssertionError):self.check()
    def test_unrelated_history_assertion_fails(self):
        self.new[retry.PATH]=self.new[retry.PATH].replace('assertEquals(0, history(copy).undoCount)','assertEquals(1, history(copy).undoCount)')
        with self.assertRaises(AssertionError):self.check()
    def test_reported_error_change_fails(self):
        self.new[retry.PATH]=self.new[retry.PATH].replace('rejected.error!!.code.name)','rejected.error!!.code.name.lowercase())')
        with self.assertRaises(AssertionError):self.check()
    def test_fixture_change_fails(self):
        self.changed.append('tools/android_reference/fixtures/history-mutations.json')
        with self.assertRaises(AssertionError):self.check()
    def test_other_install_change_fails(self):
        self.new['android/ci/cargo_history_retry.py']=self.new['android/ci/cargo_history_retry.py'].replace("assert hashlib.sha256(graph()).hexdigest()==receipt['restored_store_sha256']","assert True")
        with self.assertRaises(AssertionError):self.check()

class RecoveryTest(cargo_test.RecoveryTest):
    def setUp(self):
        super().setUp();self.ids=[str(i) for i in range(134)];self.extras=['case'+str(i) for i in range(14)]
        names=[]
        for case in self.fixture['cases'][21:28]:
            names.append(case['spec']['name'])
            if case['source_spec'] is not None:names.append(case['source_spec']['name'])
        names.append('B09.2 independent link copy — Δ')
        self.graph['fit_order']=self.ids+self.extras
        self.graph['records']={key:{'spec':{'name':'old '+key},'commands':[],'projections':[]} for key in self.ids}
        self.graph['records'].update({key:{'spec':{'name':name},'commands':[],'projections':[]} for key,name in zip(self.extras,names)})
        self.graph['revisions']={key:7 for key in self.graph['fit_order']};self.graph['modified']={key:i for i,key in enumerate(self.graph['fit_order'])}
        self.prior['after']['data']=[{'id':key,'revision':7} for key in self.ids]
    def check(self):return retry.recovery_graph(self.graph,self.prior,self.fixture)

class ReceiptTest(unittest.TestCase):
    def setUp(self):
        self.base=cargo_test.ReceiptTest();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.case=self.base.case;self.run=self.case.run;old=test_report_local.COMMIT;new='c'*40
        archive=self.run/'stale-error-fix-original';(archive/'recovery').mkdir(parents=True)
        (archive/'recovery/recovery.json').write_text('{}')
        import shutil;shutil.copytree(self.run/'apks',archive/'apks')
        with ZipFile(self.run/'apks/app-debug-androidTest.apk','w') as apk:
            apk.writestr('assets/fixture.json',b'unchanged fixture\r\n');apk.writestr('classes.dex',b'correct typed stale assertion')
        retained=[g for g in self.case.state['plan'] if g not in ('native:mutation-history-3-prepare','native:mutation-history-3-restored','native:summary')]
        hashes={}
        for group in range(3):
            for phase in ('prepare','restored'):
                name=f'mutation-history-{group}-{phase}-native.json';(self.run/'native'/name).write_text('{}');hashes[name]=retry.sha(self.run/'native'/name)
        self.proof={'from_commit':old,'to_commit':new,'prepared':True,'installed':True,'archive':archive.name,
            'retained_gates':retained,'retained_report_hashes':hashes,
            'app_sha256':retry.sha(self.run/'apks/app-debug.apk'),'old_test_apk_sha256':retry.sha(archive/'apks/app-debug-androidTest.apk'),
            'new_test_apk_sha256':retry.sha(self.run/'apks/app-debug-androidTest.apk'),'recovery_receipt_sha256':retry.sha(archive/'recovery/recovery.json')}
        self.case.state['stale_history_reuse']=[self.proof];self.case.state['commit']=new;self.case.review['tested_commit']=new
        for row in self.case.state['attempts']:
            if row['gate'] not in retained:row['tested_commit']=new
        path=self.run/'native/native-summary.json';summary=json.loads(path.read_text());summary['checkout_sha']=new;path.write_text(json.dumps(summary))
        patch.object(retry,'exact_source',return_value=None).start();patch.object(retry,'validate_recovery',return_value={}).start()
        self.case.save()
    def test_valid_chain_keeps_groups_0_to_2_revisions(self):self.case.validate()
    def test_group_3_old_revision_fails(self):
        next(row for row in self.case.state['attempts'] if row['gate']=='native:mutation-history-3-prepare')['tested_commit']=test_report_local.COMMIT
        self.case.save();self.case.reject()
    def test_retained_report_changed_fails(self):
        (self.run/'native'/next(iter(self.proof['retained_report_hashes']))).write_text('{"changed":true}')
        self.case.save();self.case.reject()
    def test_missing_retained_report_hash_fails(self):
        self.proof['retained_report_hashes'].pop(next(iter(self.proof['retained_report_hashes'])))
        self.case.save();self.case.reject()
    def test_wrong_apk_digest_fails(self):
        self.proof['new_test_apk_sha256']='0'*64;self.case.save();self.case.reject()
    def test_uninstalled_fix_fails(self):
        self.proof['installed']=False;self.case.save();self.case.reject()

if __name__=='__main__':unittest.main()
