"""Only equivalent metadata lookup may reuse the61 completed pre-build inputs."""
import subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import local_verification as launcher
ROOT=Path(__file__).resolve().parents[2]
BEFORE='bfbbe1570c82b0e884f18461fa379f59b793dfbd'
PATHS=('android/ci/targeting_summary.py','android/ci/test_targeting_summary.py')


class MetadataReuseTests(unittest.TestCase):
    def setUp(self):
        self.old={p:subprocess.check_output(['git','show',BEFORE+':'+p],cwd=ROOT,text=True,encoding='utf-8') for p in PATHS}
        self.new={p:(ROOT/p).read_text(encoding='utf-8') for p in PATHS}
        self.completed=launcher.plan('full',None)[:61]
        self.changed=[*PATHS,'android/ci/local_verification.py','android/ci/report_local.py',
            'android/ci/test_pending_targeting_metadata_index_fix.py','docs/android/STATUS.md']
    def output(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changed)
        revision,path=args[2].split(':',1)
        return (self.old if revision==BEFORE else self.new)[path]
    def validate(self,completed=None,before=BEFORE):
        with patch.object(launcher.subprocess,'check_output',side_effect=self.output):
            launcher.pending_targeting_metadata_index_fix(ROOT,before,'after',self.completed if completed is None else completed)
    def test_exact_index_passes(self):self.validate()
    def test_removed_assertion_fails(self):
        self.new[PATHS[0]]=self.new[PATHS[0]].replace("exact(row,snapshots[key])",'pass')
        self.assertRaises(AssertionError,self.validate)
    def test_weaker_boundary_fails(self):
        self.new[PATHS[0]]=self.new[PATHS[0]].replace("name[index+1] in '.['","name[index+1] == '.'")
        self.assertRaises(AssertionError,self.validate)
    def test_original_corruption_removed_fails(self):
        self.new[PATHS[1]]=self.new[PATHS[1]].replace("'missing_metadata':lambda", "'omitted_metadata':lambda")
        self.assertRaises(AssertionError,self.validate)
    def test_unrelated_summary_change_fails(self):
        self.new[PATHS[0]]+='\n';self.assertRaises(AssertionError,self.validate)
    def test_deadline_change_fails(self):
        self.changed.append('tools/android_headless/check_targeting.py');self.assertRaises(AssertionError,self.validate)
    def test_fixture_change_fails(self):
        self.changed.append('tools/android_reference/fixtures/targeting.json');self.assertRaises(AssertionError,self.validate)
    def test_engine_change_fails(self):
        self.changed.append('android_bridge/targeting.py');self.assertRaises(AssertionError,self.validate)
    def test_application_change_fails(self):
        self.changed.append('android/app/src/main/java/io/github/sussic/pyfa/MainActivity.kt');self.assertRaises(AssertionError,self.validate)
    def test_executed_targeting_cannot_be_reused(self):
        self.assertRaises(AssertionError,self.validate,self.completed+['headless:targeting'])
    def test_missing_completed_gate_fails(self):self.assertRaises(AssertionError,self.validate,self.completed[:-1])
    def test_different_revision_fails(self):self.assertRaises(AssertionError,self.validate,before='different')


if __name__=='__main__':unittest.main()
