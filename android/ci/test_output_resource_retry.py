"""C02 resource boundary repair preserves55 exact preceding gates."""
from pathlib import Path
import json,subprocess,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
import local_verification as launcher
ROOT=Path(__file__).resolve().parents[2]
PATH='tools/android_headless/check_resources.py'
BEFORE=launcher.OUTPUT_RESOURCE_BEFORE

class ResourceBoundaryReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous=subprocess.check_output(['git','show',BEFORE+':'+PATH],cwd=ROOT)
        cls.previous_launcher=subprocess.check_output(['git','show',BEFORE+':android/ci/local_verification.py'],cwd=ROOT,text=True,encoding='utf-8')
    def setUp(self):
        # Exercise the delivered C02 boundary, before C03 added its own gates.
        gate_patch=patch.multiple(launcher,FAMILIES=[g for g in launcher.FAMILIES if g!='targeting'],
            HEADLESS=[g for g in launcher.HEADLESS if g!='targeting'],
            NATIVE_STEPS=[g for g in launcher.NATIVE_STEPS if not g.startswith('targeting-')])
        gate_patch.start();self.addCleanup(gate_patch.stop)
        self.current=(ROOT/PATH).read_bytes();self.completed=launcher.plan('full',None)[:55]
        self.changed=[PATH,'android/ci/local_verification.py','android/ci/report_local.py','android/ci/test_output_resource_retry.py','docs/android/STATUS.md']
    def output(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changed)
        if args[2].endswith(':android/ci/local_verification.py'):
            return self.previous_launcher if args[2].startswith(BEFORE+':') else (ROOT/'android/ci/local_verification.py').read_text(encoding='utf-8')
        return self.previous if args[2].startswith(BEFORE+':') else self.current
    def validate(self,completed=None):
        with patch.object(launcher.subprocess,'check_output',side_effect=self.output):
            launcher.pending_output_resource_fix(ROOT,BEFORE,'after',self.completed if completed is None else completed)
    def test_exact_extension_passes(self):self.validate()
    def test_any_other_source_difference_fails(self):
        self.current+=b'\n'
        with self.assertRaises(AssertionError):self.validate()
    def test_removed_assertion_fails(self):
        self.current=self.current.replace(b"self.assertTrue(actual['fighter_tubes']['overloaded'])",b'pass')
        with self.assertRaises(AssertionError):self.validate()
    def test_unrelated_engine_change_fails(self):
        self.changed.append('android_bridge/output.py')
        with self.assertRaises(AssertionError):self.validate()
    def test_fixture_change_fails(self):
        self.changed.append('tools/android_reference/fixtures/output.json')
        with self.assertRaises(AssertionError):self.validate()
    def test_changed_completed_boundary_fails(self):
        for completed in (self.completed[:-1],self.completed+['headless:resources'],self.completed+['native:initial']):
            with self.assertRaises(AssertionError):self.validate(completed)
    def test_actual_failed_constructor_preserves55_results_and_failed_attempt(self):
        def git(*args):
            if args[0]=='-C':return launcher.PIN
            if args[0]=='status':return ''
            if args[0]=='rev-parse':return 'after' if args[1]=='HEAD' else 'tree'
            if args[0]=='diff':return '\n'.join(self.changed)
            if args[0]=='show':return self.previous_launcher
            raise AssertionError(args)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            attempts=[dict(gate=g,exit_code=0,tested_commit=launcher.OUTPUT_HISTORY_BEFORE) for g in self.completed[:54]]
            attempts += [dict(gate='headless:history_mutations',exit_code=1,tested_commit=launcher.OUTPUT_HISTORY_BEFORE),dict(gate='headless:history_mutations',exit_code=0),dict(gate='headless:resources',exit_code=1)]
            state=dict(status='failed',commit=BEFORE,tree='previous',mode='full',gate=None,plan=launcher.plan('full',None),completed=self.completed,attempts=attempts)
            (path/'run.json').write_text(json.dumps(state))
            args=SimpleNamespace(run=str(path),action='resume',adopt_launcher_fix=True,restart_native=False,source=None,reference_python=None,
                adopt_capacitor_runner_fix=False,adopt_resource_test_fix=False,adopt_projection_report_fix=False,adopt_stale_history_fix=False,
                adopt_cargo_observer_fix=False,adopt_pending_settings_fix=False,adopt_pending_runner_fix=False)
            with patch.object(launcher,'git',side_effect=git),patch.object(launcher.subprocess,'check_output',side_effect=self.output):runner=launcher.Run(args)
            self.assertEqual(self.completed,runner.state['completed']);self.assertEqual('after',runner.state['commit'])
            self.assertEqual([launcher.OUTPUT_HISTORY_BEFORE]*55+[BEFORE]*2,[row['tested_commit'] for row in runner.state['attempts']])
            self.assertEqual(1,runner.state['attempts'][-1]['exit_code'])
            self.assertEqual(self.completed,runner.state['output_resource_reuse']['completed_before_adoption'])

if __name__=='__main__':unittest.main()
