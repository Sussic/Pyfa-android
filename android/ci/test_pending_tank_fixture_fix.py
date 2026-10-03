"""Exact pending falloff correction cannot reuse changed or executed inputs."""
from pathlib import Path
import subprocess
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import local_verification as launcher

ROOT = Path(__file__).resolve().parents[2]
BEFORE = '7a0aaa27b1739d9600e14915d62cb2d35a873db0'
COMPLETED = ['desktop:utilities','desktop:reference','desktop:migration','reference:projection',
    'reference:command','reference:catalog','reference:equipment','reference:empty_hulls','reference:module_edits']
PATHS = ['tools/android_reference/tank.py','tools/android_reference/fixtures/tank.json',
    'android/ci/local_verification.py','android/ci/report_local.py','android/ci/test_pending_tank_fixture_fix.py']


class PendingTankTests(unittest.TestCase):
    def setUp(self):
        self.outputs = {BEFORE+':'+path: subprocess.check_output(['git','show',BEFORE+':'+path],cwd=ROOT)
            for path in PATHS[:2]}
        self.outputs.update({'after:'+path:(ROOT/path).read_bytes() for path in PATHS[:2]})
        self.changed = list(PATHS)
    def output(self, args, **kwargs):
        return '\n'.join(self.changed) if args[1] == 'diff' else self.outputs[args[2]]
    def validate(self, completed=None):
        with patch.object(launcher.subprocess,'check_output',side_effect=self.output):
            launcher.pending_tank_fixture_fix(ROOT,BEFORE,'after',COMPLETED if completed is None else completed)
    def test_exact_reviewed_correction_passes(self): self.validate()
    def test_already_executed_tank_or_build_cannot_be_reused(self):
        for gate in ('reference:tank','headless:tank','build:engine-assets','native:initial'):
            with self.assertRaises(AssertionError):self.validate(COMPLETED+[gate])
    def test_unrelated_engine_difference_fails(self):
        self.changed.append('android_bridge/tank.py')
        with self.assertRaises(AssertionError):self.validate()
    def test_any_unrelated_reference_source_change_fails(self):
        self.outputs['after:tools/android_reference/tank.py'] += b'\n'
        with self.assertRaises(AssertionError):self.validate()
    def test_changed_fixture_even_with_plausible_results_fails(self):
        key='after:tools/android_reference/fixtures/tank.json'
        self.outputs[key]=self.outputs[key].replace(b'Empty tank',b'Other tank')
        with self.assertRaises(AssertionError):self.validate()
    def test_actual_paused_constructor_retains_nine_gates_and_status_note(self):
        previous=subprocess.check_output(['git','show',BEFORE+':android/ci/local_verification.py'],cwd=ROOT,text=True,encoding='utf-8')
        self.changed.append('docs/android/STATUS.md')
        def git(*args):
            if args[0]=='-C':return launcher.PIN
            if args[0]=='status':return ''
            if args[0]=='rev-parse':return 'after' if args[1]=='HEAD' else 'tree'
            if args[0]=='diff':return '\n'.join(self.changed)
            if args[0]=='show':return previous
            raise AssertionError(args)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            state=dict(status='paused',commit=BEFORE,tree='previous',mode='full',gate=None,plan=launcher.plan('full',None),
                completed=COMPLETED,attempts=[dict(gate=g,exit_code=0) for g in COMPLETED])
            (path/'run.json').write_text(json.dumps(state),encoding='utf-8')
            args=SimpleNamespace(run=str(path),action='resume',adopt_launcher_fix=True,restart_native=False,source=None,reference_python=None,
                adopt_capacitor_runner_fix=False,adopt_resource_test_fix=False,adopt_projection_report_fix=False,adopt_stale_history_fix=False,
                adopt_cargo_observer_fix=False,adopt_pending_settings_fix=False,adopt_pending_runner_fix=False)
            with patch.object(launcher,'git',side_effect=git),patch.object(launcher.subprocess,'check_output',side_effect=self.output):
                runner=launcher.Run(args)
            self.assertEqual(COMPLETED,runner.state['completed'])
            self.assertEqual('after',runner.state['commit'])
            self.assertEqual([BEFORE]*9,[r['tested_commit'] for r in runner.state['attempts']])
            self.assertEqual(COMPLETED,runner.state['launcher_fix_reuse'][0]['completed_before_adoption'])


if __name__ == '__main__': unittest.main()
