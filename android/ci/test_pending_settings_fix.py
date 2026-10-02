"""Exact-source protection for the single settings representation correction."""
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import local_verification as local

ROOT=Path(__file__).resolve().parents[2]
BEFORE='3ab65073103be0dd5fba2ac1d19a560a4a1334ae'
PATH='android/ci/mutation_history_summary.py'

class PendingSettingsFixTest(unittest.TestCase):
    def setUp(self):
        self.old=subprocess.check_output(['git','show',BEFORE+':'+PATH],cwd=ROOT,text=True,encoding='utf-8')
        self.new=subprocess.check_output(['git','show','287c0c336c0191c78129a017b363dbc3d030adad:'+PATH],cwd=ROOT,text=True,encoding='utf-8')
        self.launcher=(ROOT/'android/ci/local_verification.py').read_text(encoding='utf-8')
        self.changes=[PATH,'android/ci/local_verification.py','android/ci/report_local.py',
            'android/ci/test_mutation_history_summary.py','android/ci/revalidate-mutation-history.py','android/ci/test_pending_settings_fix.py']
    def command(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changes)
        commit,path=args[2].split(':',1)
        if path==PATH:return self.old if commit==BEFORE else self.new
        if path=='android/ci/local_verification.py':return self.launcher
        raise AssertionError(args)
    def check(self):
        with patch.object(local.subprocess,'check_output',side_effect=self.command):local.pending_settings_fix(ROOT,BEFORE,'after')
    def test_exact_named_representation_correction_passes(self):self.check()
    def test_value_tolerance_change_fails(self):
        self.new=self.new.replace('value == other','abs(value - other) < 0.1')
        with self.assertRaises(AssertionError):self.check()
    def test_other_setting_type_relaxation_fails(self):
        self.new=self.new.replace('else: exact(value, other)','else: assert value == other')
        with self.assertRaises(AssertionError):self.check()
    def test_runtime_consistency_change_fails(self):
        self.new=self.new.replace("exact(engine['eos_settings'], runtime['eos_settings'])","settings(engine['eos_settings'], runtime['eos_settings'])")
        with self.assertRaises(AssertionError):self.check()
    def test_statistic_tolerance_change_fails(self):
        self.new=self.new.replace('rel_tol=1e-10','rel_tol=1e-5')
        with self.assertRaises(AssertionError):self.check()
    def test_native_source_change_fails(self):
        self.changes.append('android/app/src/androidTest/java/io/github/sussic/pyfa/MutationHistoryTest.kt')
        with self.assertRaises(AssertionError):self.check()
    def test_fixture_change_fails(self):
        self.changes.append('tools/android_reference/fixtures/history-mutations.json')
        with self.assertRaises(AssertionError):self.check()

if __name__=='__main__':unittest.main()
