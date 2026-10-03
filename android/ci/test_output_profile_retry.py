"""Exact C02 repair reuses host proof and requires fresh build/native proof."""
import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import local_verification as launcher
import output_profile_retry as repair

ROOT=Path(__file__).resolve().parents[2]

class ProfileRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths=[*repair.PAIRS,'android/ci/local_verification.py']
        cls.old={p:subprocess.check_output(['git','show',repair.BEFORE+':'+p],cwd=ROOT) for p in paths}
    def setUp(self):
        self.new={p:(ROOT/p).read_bytes() for p in self.old}
        self.changed=[*repair.PAIRS,'android/ci/local_verification.py','android/ci/report_local.py',
                      'android/ci/output_profile_retry.py','android/ci/test_output_profile_retry.py']
        self.completed=launcher.plan('full',None)[:106]
    def output(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changed)
        revision,path=args[2].split(':',1)
        value=(self.old if revision==repair.BEFORE else self.new)[path]
        return value.decode('utf-8') if kwargs.get('text') else value
    def validate(self,completed=None):
        with patch.object(repair.subprocess,'check_output',side_effect=self.output):
            repair.exact_source(ROOT,repair.BEFORE,'after',self.completed if completed is None else completed)
    def test_exact_android_repairs_pass(self):self.validate()
    def test_unrelated_android_source_fails(self):
        self.changed.append('android/app/src/main/java/io/github/sussic/pyfa/MainActivity.kt')
        with self.assertRaises(AssertionError):self.validate()
    def test_fixture_or_engine_change_fails(self):
        for path in ('tools/android_reference/fixtures/output.json','android_bridge/output.py'):
            with self.subTest(path=path):
                self.changed.append(path)
                with self.assertRaises(AssertionError):self.validate()
                self.changed.remove(path)
    def test_any_other_profile_change_fails(self):
        path=next(iter(repair.PAIRS));self.new[path]+=b'\n'
        with self.assertRaises(AssertionError):self.validate()
    def test_weakened_native_assertion_fails(self):
        path='android/app/src/androidTest/java/io/github/sussic/pyfa/OutputTest.kt'
        self.new[path]=self.new[path].replace(b'assertEquals(268,EngineRuntime.library.value.size)',b'assertTrue(true)')
        with self.assertRaises(AssertionError):self.validate()
    def test_host_execution_change_fails(self):
        path='android/ci/local_verification.py'
        original=b"self.db=output/'eve.db'"
        self.assertIn(original,self.new[path])
        self.new[path]=self.new[path].replace(original,b"self.db=output/'wrong.db'")
        with self.assertRaises(AssertionError):self.validate()
    def test_changed_boundary_fails(self):
        for completed in (self.completed[:-1],self.completed+['native:output-prepare']):
            with self.assertRaises(AssertionError):self.validate(completed)
    def test_constructor_reuses_only60_host_results_and_preserves_commit_stamps(self):
        def git(*args):
            if args[0]=='-C':return launcher.PIN
            if args[0]=='status':return ''
            if args[0]=='rev-parse':return 'after' if args[1]=='HEAD' else 'tree'
            raise AssertionError(args)
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory)
            attempts=[dict(gate=g,exit_code=0) for g in self.completed]
            attempts[0]['tested_commit']=launcher.OUTPUT_HISTORY_BEFORE
            attempts+=[dict(gate='native:output-prepare',exit_code=1)]
            state=dict(status='failed',mode='full',gate=None,plan=launcher.plan('full',None),
                       completed=self.completed,attempts=attempts,commit=repair.BEFORE,tree='old')
            (run/'run.json').write_text(json.dumps(state))
            args=SimpleNamespace(run=str(run),action='resume',restart_native=True,adopt_launcher_fix=False,
                source=None,reference_python=None,adopt_tank_history_fix=False,adopt_capacitor_runner_fix=False,
                adopt_resource_test_fix=False,adopt_projection_report_fix=False,adopt_stale_history_fix=False,
                adopt_cargo_observer_fix=False,adopt_pending_settings_fix=False,adopt_pending_runner_fix=False)
            with patch.object(launcher,'git',side_effect=git),patch.object(repair.subprocess,'check_output',side_effect=self.output):
                runner=launcher.Run(args)
            self.assertEqual(launcher.plan('full',None)[:60],runner.state['completed'])
            self.assertTrue(all(g.startswith(('desktop:','reference:','headless:')) for g in runner.state['completed']))
            self.assertEqual(launcher.OUTPUT_HISTORY_BEFORE,runner.state['attempts'][0]['tested_commit'])
            self.assertTrue(all(r['tested_commit']==repair.BEFORE for r in runner.state['attempts'][1:]))
            self.assertEqual(1,runner.state['attempts'][-1]['exit_code'])
            self.assertEqual(self.completed,runner.state['output_profile_host_reuse']['completed_before_adoption'])
            self.assertEqual('after',runner.state['commit'])

if __name__=='__main__':unittest.main()
