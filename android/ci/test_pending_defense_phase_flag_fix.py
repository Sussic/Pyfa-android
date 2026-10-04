"""Only the missing persistent C03 flag expectation may retain the preceding58 gates."""
import subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import local_verification as launcher
ROOT=Path(__file__).resolve().parents[2]
BEFORE='9badd3ec58aa3a5bb2e325ec60da5751eea64830';PATH='android/ci/test_defense_summary.py'


class PendingDefensePhaseTests(unittest.TestCase):
    def setUp(self):
        self.old=subprocess.check_output(['git','show',BEFORE+':'+PATH],cwd=ROOT,text=True,encoding='utf-8')
        self.new=(ROOT/PATH).read_text(encoding='utf-8');self.completed=launcher.plan('full',None)[:58]
        self.changed=[PATH,'android/ci/local_verification.py','android/ci/report_local.py','android/ci/test_pending_defense_phase_flag_fix.py','docs/android/STATUS.md']
    def output(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changed)
        return self.old if args[2].startswith(BEFORE+':') else self.new
    def validate(self,completed=None,before=BEFORE):
        with patch.object(launcher.subprocess,'check_output',side_effect=self.output):
            launcher.pending_defense_phase_flag_fix(ROOT,before,'after',self.completed if completed is None else completed)
    def test_exact_expectation_passes(self):self.validate()
    def test_missing_old_flag_fails(self):
        self.new=self.new.replace("'c02_phase',",'');self.assertRaises(AssertionError,self.validate)
    def test_removed_assertion_fails(self):
        self.new=self.new.replace('self.assertTrue(eval(condition','self.assertFalse(eval(condition');self.assertRaises(AssertionError,self.validate)
    def test_unrelated_test_change_fails(self):
        self.new+='\n';self.assertRaises(AssertionError,self.validate)
    def test_native_source_change_fails(self):
        self.changed.append('android/app/src/androidTest/java/io/github/sussic/pyfa/TargetingTest.kt');self.assertRaises(AssertionError,self.validate)
    def test_fixture_change_fails(self):
        self.changed.append('tools/android_reference/fixtures/targeting.json');self.assertRaises(AssertionError,self.validate)
    def test_engine_change_fails(self):
        self.changed.append('android_bridge/targeting.py');self.assertRaises(AssertionError,self.validate)
    def test_executed_defense_gate_cannot_be_reused(self):
        self.assertRaises(AssertionError,self.validate,self.completed+['headless:defenses'])
    def test_missing_completed_gate_fails(self):self.assertRaises(AssertionError,self.validate,self.completed[:-1])
    def test_different_revision_fails(self):self.assertRaises(AssertionError,self.validate,before='different')


if __name__=='__main__':unittest.main()
