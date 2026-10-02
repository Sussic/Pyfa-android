"""The storage-flag repair cannot stand in for changed executed tests or product."""
from pathlib import Path
import subprocess
import json
from zipfile import ZipFile
import unittest
from unittest.mock import patch
import local_verification as local
import report_local
import test_report_local

ROOT=Path(__file__).resolve().parents[2]
PATH='android/app/src/androidTest/java/io/github/sussic/pyfa/DiagnosticTestRunner.kt'
BEFORE='7dc60a00972d991037f51d875d39df7024d4998e'

class PendingRunnerFixTest(unittest.TestCase):
    def setUp(self):
        self.original=subprocess.check_output(['git','show',BEFORE+':'+PATH],cwd=ROOT,text=True,encoding='utf-8')
        self.new=(ROOT/PATH).read_text(encoding='utf-8')
        self.launcher=(ROOT/'android/ci/local_verification.py').read_text(encoding='utf-8')
        self.old_launcher=self.launcher
        self.changes=[PATH,'android/ci/local_verification.py','android/ci/report_local.py','android/ci/test_pending_runner_fix.py']
        self.completed=['native:check-history.py']
    def command(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changes)
        commit,path=args[2].split(':',1)
        if path==PATH:return self.original if commit==BEFORE else self.new
        if path=='android/ci/local_verification.py':return self.old_launcher if commit==BEFORE else self.launcher
        raise AssertionError(args)
    def check(self):
        with patch.object(local.subprocess,'check_output',side_effect=self.command):
            local.pending_runner_fix(ROOT,BEFORE,'after',self.completed)
    def test_exact_pending_flag_passes(self):self.check()
    def test_existing_phase_change_fails(self):
        self.new=self.new.replace('b091_phase','unrecognized_phase')
        with self.assertRaises(AssertionError):self.check()
    def test_other_runner_change_fails(self):
        self.new=self.new.replace('super.onCreate(arguments)','super.onCreate(Bundle())')
        with self.assertRaises(AssertionError):self.check()
    def test_changed_product_fails(self):
        self.changes.append('android_bridge/history.py')
        with self.assertRaises(AssertionError):self.check()
    def test_changed_mutation_assertion_fails(self):
        self.changes.append('android/app/src/androidTest/java/io/github/sussic/pyfa/MutationHistoryTest.kt')
        with self.assertRaises(AssertionError):self.check()
    def test_already_executed_phase_cannot_be_reused(self):
        self.completed.append('native:mutation-history-0-prepare')
        with self.assertRaises(AssertionError):self.check()
    def test_missing_prior_history_fails(self):
        self.completed=[]
        with self.assertRaises(AssertionError):self.check()
    def test_changed_executed_commands_fail(self):
        self.launcher=self.launcher.replace("desktop=['desktop:utilities'", "desktop=['desktop:wrong-command'",1)
        with self.assertRaises(AssertionError):self.check()

class RunnerReceiptTest(unittest.TestCase):
    def setUp(self):
        self.case=test_report_local.LocalResultTest()
        self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.addCleanup(patch.stopall)
        self.run=self.case.run
        archive=self.run/'pending-runner-fix-original';(archive/'apks').mkdir(parents=True)
        (self.run/'apks').mkdir()
        for directory in (archive/'apks',self.run/'apks'):
            (directory/'app-debug.apk').write_bytes(b'unchanged target APK fixture')
            with ZipFile(directory/'app-debug-androidTest.apk','w') as apk:
                apk.writestr('assets/history.json',b'unchanged exact fixture bytes\r\n')
                apk.writestr('classes.dex',b'old' if directory.parent==archive else b'new runner')
        self.proof={'from_commit':BEFORE,'to_commit':test_report_local.COMMIT,
            'completed_before_adoption':[g for g in self.case.state['plan'] if not g.startswith('native:mutation-history-') and g!='native:summary'],
            'prepared':True,'installed':True,'archive':archive.name,
            'app_sha256':report_local.sha(archive/'apks/app-debug.apk'),
            'old_test_apk_sha256':report_local.sha(archive/'apks/app-debug-androidTest.apk'),
            'new_test_apk_sha256':report_local.sha(self.run/'apks/app-debug-androidTest.apk')}
        self.case.state['runner_fix_reuse']=[self.proof]
        for row in self.case.state['attempts']:
            if row['gate'] in self.proof['completed_before_adoption']:row['tested_commit']=BEFORE
        patch.object(local,'pending_runner_fix',return_value=None).start()
        self.case.save()
    def test_valid_reuse_keeps_actual_gate_revisions(self):
        self.case.validate()
        self.assertEqual(BEFORE,self.case.state['attempts'][0]['tested_commit'])
    def test_changed_target_apk_fails(self):
        (self.run/'apks/app-debug.apk').write_bytes(b'changed target APK')
        self.case.save();self.case.reject()
    def test_wrong_archived_apk_digest_fails(self):
        self.proof['old_test_apk_sha256']='0'*64
        self.case.save();self.case.reject()
    def test_changed_fixture_fails_even_with_updated_apk_digest(self):
        apk_path=self.run/'apks/app-debug-androidTest.apk'
        with ZipFile(apk_path,'w') as apk:
            apk.writestr('assets/history.json',b'changed fixture bytes\r\n')
            apk.writestr('classes.dex',b'new runner')
        self.proof['new_test_apk_sha256']=report_local.sha(apk_path)
        self.case.save();self.case.reject()
    def test_uninstalled_runner_cannot_pass(self):
        self.proof['installed']=False
        self.case.save();self.case.reject()

if __name__=='__main__':unittest.main()
