"""Exact pending falloff correction cannot reuse changed or executed inputs."""
from pathlib import Path
import subprocess
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


if __name__ == '__main__': unittest.main()
