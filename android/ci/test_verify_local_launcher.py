"""Exercise Windows launcher dispatch without starting verification or Android."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


POWERSHELL = shutil.which('pwsh') or shutil.which('powershell')
LAUNCHER = Path(__file__).resolve().parents[1] / 'verify-local.ps1'


@unittest.skipUnless(os.name == 'nt' and POWERSHELL, 'Windows PowerShell launcher')
class VerifyLocalLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'checkout with spaces'
        (self.root / 'android').mkdir(parents=True)
        self.launcher = self.root / 'android/verify-local.ps1'
        shutil.copyfile(LAUNCHER, self.launcher)
        shutil.copyfile(LAUNCHER.parents[1]/'execution-policy.json',self.root/'execution-policy.json')
        self.capture = self.root / 'dispatch.json'
        self.python = self.root / 'qualified interpreter.ps1'
        self.python.write_text("@{arguments=@($args);java_home=$env:JAVA_HOME} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $env:PYFA_TEST_CAPTURE\n$global:LASTEXITCODE=[int]$env:PYFA_TEST_EXIT\n")
        self.env = {**os.environ, 'PYFA_TEST_CAPTURE': str(self.capture), 'PYFA_TEST_EXIT': '0',
                    'JAVA_HOME': str(self.root / 'inherited-jdk'),
                    'COMPUTERNAME': 'MSI', 'CODEX_EXECUTION_HOST': 'msi'}

    def invoke(self, *args):
        return subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-File', str(self.launcher), *args],
                              env=self.env, capture_output=True, text=True, timeout=15)

    def dispatch(self, *args):
        result = self.invoke('-PythonPath', str(self.python), *args)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(self.capture.read_text(encoding='utf-8-sig'))

    def test_missing_default_python_fails_with_explicit_existing_path_option(self):
        result = self.invoke('-Action', 'plan')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('-PythonPath', result.stderr)
        self.assertFalse(self.capture.exists())

    def test_plan_needs_no_jdk_and_preserves_inherited_java_home(self):
        row = self.dispatch('-Action', 'plan', '-Mode', 'full')
        self.assertEqual(self.env['JAVA_HOME'], row['java_home'])
        self.assertEqual(['-I', '-B', str(self.root / 'android/ci/local_verification.py'), 'plan', '--mode', 'full'], row['arguments'][:6])

    def test_desktop_forwards_existing_reference_and_source_without_jdk(self):
        row = self.dispatch('-Action', 'start', '-Mode', 'desktop', '-Gate', 'charge_edits',
                            '-ReferencePython', str(self.python), '-Source', str(self.root / 'pinned reference'))
        for flag, value in (('--gate', 'charge_edits'), ('--reference-python', str(self.python)),
                            ('--source', str(self.root / 'pinned reference')), ('--execution-host', 'msi')):
            self.assertEqual(value, row['arguments'][row['arguments'].index(flag) + 1])
        self.assertEqual(self.env['JAVA_HOME'], row['java_home'])

    def test_old_storage_override_is_retired_before_dispatch(self):
        result=self.invoke('-PythonPath',str(self.python),'-Action','plan','-ArtifactBudgetGiB','32')
        self.assertNotEqual(0,result.returncode)
        self.assertIn('retired',result.stderr)
        self.assertFalse(self.capture.exists())

    def test_missing_policy_never_falls_back_to_old_limits(self):
        (self.root/'execution-policy.json').unlink()
        result=self.invoke('-PythonPath',str(self.python),'-Action','plan')
        self.assertNotEqual(0,result.returncode)
        self.assertIn('execution-policy.json',result.stderr)
        self.assertFalse(self.capture.exists())

    def test_build_rejects_missing_jdk_before_dispatch(self):
        result = self.invoke('-PythonPath', str(self.python), '-Action', 'start', '-Mode', 'build')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('-JdkPath', result.stderr)
        self.assertFalse(self.capture.exists())

    def test_explicit_jdk_and_resume_controls_are_forwarded(self):
        jdk = self.root / 'existing jdk'
        (jdk / 'bin').mkdir(parents=True)
        (jdk / 'bin/java.exe').write_bytes(b'not executed')
        row = self.dispatch('-Action', 'resume', '-Mode', 'native', '-JdkPath', str(jdk),
                            '-Run', str(self.root / 'retained evidence'), '-RestartNative')
        self.assertEqual(str(jdk), row['java_home'])
        self.assertIn('--restart-native', row['arguments'])
        self.assertEqual(str(self.root / 'retained evidence'), row['arguments'][row['arguments'].index('--run') + 1])

    def test_interpreter_failure_is_propagated(self):
        self.env['PYFA_TEST_EXIT'] = '7'
        result = self.invoke('-PythonPath', str(self.python), '-Action', 'plan')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Local verification exited 7', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
