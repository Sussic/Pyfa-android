"""Reject misbound archived package evidence and preserve completed receipts."""
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import summary_repair as repair
import local_verification


class PackageRoutingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.run = Path(self.temp.name) / 'run'
        self.archive = self.run / 'failed-native-fixture'
        for p in (self.archive / 'native', self.run / 'native', self.run / 'apks',
                self.root / 'android/app/build/outputs/apk/debug', self.root / 'android/app/src/main/python'):
            p.mkdir(parents=True)
        database = b'synthetic database'
        digest = hashlib.sha256(database).hexdigest()
        engine = {'database_sha256': digest, 'database_logical_sha256': 'logical', 'engine_source_sha256': 'engine'}
        manifest = dict(engine, database_bytes=len(database), engine_sources={'engine.py': 'source'})
        (self.root / 'android/app/src/main/python/bridge.py').write_bytes(b'pass\n')
        nested = io.BytesIO()
        with ZipFile(nested, 'w') as zipped:
            zipped.writestr('bridge.py', b'pass\n')
        self.report = dict(engine, database_bytes=len(database), engine_source_files=1,
            mobile_sources={'bridge.py': hashlib.sha256(b'pass\n').hexdigest()}, abis={})
        with ZipFile(self.run / 'apks/app-debug.apk', 'w') as apk:
            apk.writestr('assets/engine/manifest.json', json.dumps(manifest))
            apk.writestr('assets/engine/eve.db', database)
            apk.writestr('assets/chaquopy/app.imy', nested.getvalue())
            for abi, machine in (('arm64-v8a', 183), ('x86_64', 62)):
                name = 'lib/' + abi + '/library.so'
                raw = b'synthetic ELF ' + abi.encode()
                apk.writestr(name, raw)
                self.report['abis'][abi] = {'elf_machine': machine, 'runtime_tested': False,
                    'libraries': {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'needed': ['libc.so']}}}
        (self.run / 'apks/app-debug-androidTest.apk').write_bytes(b'synthetic instrumentation APK')
        for apk in (self.run / 'apks').glob('*.apk'):
            (self.root / 'android/app/build/outputs/apk/debug' / apk.name).write_bytes(apk.read_bytes())
        (self.run / 'gate.log').write_bytes(b'original package inspection passed')
        row = {'gate': 'build:package', 'exit_code': 0, 'log': 'gate.log',
            'log_sha256': repair.sha(self.run / 'gate.log'), 'tested_commit': 'build-commit'}
        self.state = {'status': 'failed', 'commit': 'native-commit', 'plan': ['build:package', 'native:summary'],
            'completed': ['build:package'], 'attempts': [row], 'native_restarts': [{'archive': self.archive.name}]}
        self.save()
        (self.archive / 'run.json').write_text(json.dumps(self.state))
        for directory in (self.run / 'native', self.archive / 'native'):
            (directory / 'engine-native.json').write_text(json.dumps(engine))
        self.reader = patch.object(repair.subprocess, 'check_output', return_value=' (NEEDED) Shared library: [libc.so]\n')
        self.reader.start()
        self.addCleanup(self.reader.stop)

    def save(self):
        (self.archive / 'native/apk-contents.json').write_text(json.dumps(self.report))
        (self.run / 'run.json').write_text(json.dumps(self.state))

    def validate(self):
        return repair.validate_package(self.run, self.root)

    def reject(self):
        with self.assertRaises((AssertionError, FileNotFoundError)):
            self.validate()

    def test_valid_report_is_bound_without_mutating_originals(self):
        before = {str(p): p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        source, receipt = self.validate()
        self.assertEqual(source, self.archive / 'native/apk-contents.json')
        self.assertEqual(receipt['report_sha256'], repair.sha(source))
        self.assertEqual(len(receipt['apk_sha256']), 2)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.run.rglob('*') if p.is_file()})

    def test_rejects_changed_retained_apk(self):
        (self.run / 'apks/app-debug-androidTest.apk').write_bytes(b'changed')
        self.reject()

    def test_rejects_wrong_database_or_library_or_dependency(self):
        original = json.loads(json.dumps(self.report))
        for corruption in ('database', 'library', 'dependency'):
            self.report = json.loads(json.dumps(original))
            if corruption == 'database': self.report['database_sha256'] = 'wrong'
            elif corruption == 'library': self.report['abis']['x86_64']['libraries']['lib/x86_64/library.so']['sha256'] = 'wrong'
            else: self.report['abis']['x86_64']['libraries']['lib/x86_64/library.so']['needed'] = []
            self.save()
            with self.subTest(corruption=corruption): self.reject()

    def test_rejects_missing_report(self):
        (self.archive / 'native/apk-contents.json').unlink()
        self.reject()

    def test_rejects_changed_original_log(self):
        (self.run / 'gate.log').write_bytes(b'changed')
        self.reject()

    def test_rejects_report_from_another_build(self):
        archived = json.loads((self.archive / 'run.json').read_text())
        archived['attempts'][0]['tested_commit'] = 'another-build'
        (self.archive / 'run.json').write_text(json.dumps(archived))
        self.reject()

    def test_rejects_archive_outside_this_run(self):
        self.state['native_restarts'][-1]['archive'] = '../other-run'
        self.save()
        self.reject()


class CompletedRunTest(unittest.TestCase):
    def test_restart_retains_package_and_lint_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            native = Path(directory)
            for name in ('apk-contents.json', 'lint-results-debug.html', 'history-native.json'):
                (native / name).write_text(name)
            (native / 'junit').mkdir()
            (native / 'junit/old.xml').write_text('old native result')
            repair.clear_native_results(native)
            self.assertEqual(sorted(p.name for p in native.iterdir()), ['apk-contents.json', 'lint-results-debug.html'])
            self.assertEqual((native / 'apk-contents.json').read_text(), 'apk-contents.json')

    def test_completed_resume_rejected_before_git_or_evidence_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            original = b'{"status":"passed"}\n'
            (run / 'run.json').write_bytes(original)
            with patch.object(local_verification, 'git') as git:
                with self.assertRaisesRegex(AssertionError, 'Completed runs are immutable'):
                    local_verification.Run(SimpleNamespace(run=str(run), action='resume'))
                git.assert_not_called()
            self.assertEqual((run / 'run.json').read_bytes(), original)
            self.assertEqual([p.name for p in run.iterdir()], ['run.json'])


class EquivalenceTest(unittest.TestCase):
    def test_rejects_every_native_or_product_source_change(self):
        for name in ('android/ci/check-history.py', 'android/ci/history_summary.py',
                'android/ci/summarize-tests.py', 'android/ci/native_suite.py', 'android_bridge/engine.py'):
            with self.subTest(name=name), patch.object(repair.subprocess, 'check_output', return_value=name + '\n'):
                with self.assertRaises(AssertionError): repair.equivalent(Path('.'), 'before', 'after')

    def test_only_exact_diagnostic_format_change_is_accepted(self):
        before = "stat = '%s %Y'\n"
        for after, accepted in (("stat = '%s:%Y'\n", True), ("stat = '%s:%Y'\nimport os\n", False)):
            with patch.object(repair.subprocess, 'check_output', side_effect=['android/ci/history_progress.py\n', before, after]):
                if accepted: repair.equivalent(Path('.'), 'before', 'after')
                else:
                    with self.assertRaises(AssertionError): repair.equivalent(Path('.'), 'before', 'after')

    def test_rejects_changed_executed_build_command(self):
        with patch.object(repair.subprocess, 'check_output', side_effect=[
                'android/ci/local_verification.py\n', 'def build(): return 1\n', 'def build(): return 2\n']):
            with self.assertRaises(AssertionError): repair.equivalent(Path('.'), 'before', 'after')


if __name__ == '__main__':
    unittest.main()
