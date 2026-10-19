"""Reject source, prefix and graph changes outside the exact cargo search repair."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import io
import shutil
import unittest
from unittest.mock import patch, Mock
import cargo_search_retry as retry
import report_local
from local_verification import plan, Run

ROOT = Path(__file__).resolve().parents[2]


class SourceTest(unittest.TestCase):
    def setUp(self):
        self.sources = {(rev, path): subprocess.check_output(['git', 'show', rev + ':' + path], cwd=ROOT)
                        for rev in (retry.BEFORE, retry.TEST_REVISION)
                        for path in (*retry.PAIRS, 'android/ci/local_verification.py')}
        self.sources[('after', 'android/ci/local_verification.py')] = (ROOT / 'android/ci/local_verification.py').read_bytes()
        for path in retry.PAIRS:
            self.sources[('after', path)] = self.sources[(retry.TEST_REVISION, path)]
        self.changed = [*retry.PAIRS, 'android/ci/local_verification.py', 'android/ci/report_local.py',
                        'android/ci/cargo_search_retry.py', 'android/ci/test_cargo_search_retry.py']
        self.completed = plan('full', None)[:122]
    def check(self):
        def output(args, **kwargs):
            if args[1] == 'diff': return '\n'.join(self.changed)
            return self.sources[tuple(args[2].split(':', 1))]
        with patch.object(retry.subprocess, 'check_output', side_effect=output):
            retry.exact_source(ROOT, retry.BEFORE, 'after', self.completed)
    def test_exact_test_correction(self): self.check()
    def test_completed_prefix_change_rejected(self):
        self.completed.pop()
        with self.assertRaises(AssertionError): self.check()
    def test_product_change_rejected(self):
        self.changed.append('android/app/src/main/java/io/github/sussic/pyfa/MainActivity.kt')
        with self.assertRaises(AssertionError): self.check()
    def test_timeout_or_assertion_change_rejected(self):
        for old, new in ((b'60_000', b'600_000'), (b'assertNull(equipment.error)', b'// omitted')):
            with self.subTest(old=old):
                original = self.sources[('after', retry.TEST_PATH)]
                self.sources[('after', retry.TEST_PATH)] = original.replace(old, new)
                with self.assertRaises(AssertionError): self.check()
                self.sources[('after', retry.TEST_PATH)] = original
    def test_report_validator_change_rejected(self):
        self.sources[('after', retry.SUMMARY_PATH)] += b'\n# altered\n'
        with self.assertRaises(AssertionError): self.check()
    def test_completed_execution_change_rejected(self):
        source = self.sources[('after', 'android/ci/local_verification.py')]
        self.sources[('after', 'android/ci/local_verification.py')] = source.replace(b'def host(self,step):', b'def host(self,step):\n        return')
        self.assertNotEqual(source, self.sources[('after', 'android/ci/local_verification.py')])
        with self.assertRaises(AssertionError): self.check()


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / 'tools/android_reference/fixtures/cargo-actions.json').read_text())
        self.ids = [str(i) for i in range(47)]
        self.extras = ['extra' + str(i) for i in range(9)]
        names = []
        for case in self.fixture['cases'][:4]:
            names.extend(['B07.2 ' + case['name'] + ' – 探索', 'B07.2 copy ' + case['name'] + ' – Δ'])
        names.append('B07.2 ' + self.fixture['cases'][4]['name'] + ' – 探索')
        self.graph = dict(sample_id='0', fit_order=self.ids + self.extras, recent=[222, 30013],
                          eos_settings={'unchanged': True}, dataset_identity='unchanged')
        self.graph['records'] = {key: dict(spec={'name': 'old ' + key}, projections=[], commands=[])
                                 for key in self.ids}
        self.graph['records'].update({key: dict(spec={'name': name}, projections=[], commands=[])
                                      for key, name in zip(self.extras, names)})
        self.graph['revisions'] = {key: 7 for key in self.graph['fit_order']}
        self.graph['modified'] = {key: i for i, key in enumerate(self.graph['fit_order'])}
        self.prior = {'after': {'data': [{'id': key, 'revision': 7} for key in self.ids]}}
    def check(self): return retry.recovery_graph(self.graph, self.prior, self.fixture)
    def test_preserves_every_original_input_and_actual_recent_history(self):
        before = copy.deepcopy(self.graph)
        recovered, removed = self.check()
        self.assertEqual(before, self.graph)
        self.assertEqual(removed, self.extras)
        self.assertEqual(recovered['fit_order'], self.ids)
        for field in ('records', 'revisions', 'modified'):
            self.assertEqual(recovered[field], {key: before[field][key] for key in self.ids})
        for field in ('recent', 'dataset_identity', 'eos_settings', 'sample_id'):
            self.assertEqual(before[field], recovered[field])
    def test_completed_prepare_requires_exact_tenth_copy_and_preserves_prior_inputs(self):
        key = 'extra9'
        self.graph['fit_order'].append(key)
        self.graph['records'][key] = dict(spec={'name': 'B07.2 copy ' + self.fixture['cases'][4]['name'] + ' – Δ'},
                                         projections=[], commands=[])
        self.graph['revisions'][key] = 7
        self.graph['modified'][key] = 99
        with self.assertRaises(AssertionError): self.check()
        result, removed = retry.recovery_graph(self.graph, self.prior, self.fixture, completed_prepare=True)
        self.assertEqual(removed, self.extras + [key])
        self.assertEqual(result['fit_order'], self.ids)
        self.assertEqual(result['recent'], self.graph['recent'])
        self.graph['records'][key]['spec']['name'] = 'unrelated'
        with self.assertRaises(AssertionError):
            retry.recovery_graph(self.graph, self.prior, self.fixture, completed_prepare=True)
    def test_changed_original_revision_rejected(self):
        self.graph['revisions']['0'] += 1
        with self.assertRaises(AssertionError): self.check()
    def test_unknown_partial_fit_rejected(self):
        self.graph['records'][self.extras[-1]]['spec']['name'] = 'unrelated'
        with self.assertRaises(AssertionError): self.check()
    def test_link_to_partial_fit_rejected(self):
        self.graph['records']['0']['projections'] = [{'source_id': self.extras[-1]}]
        with self.assertRaises(AssertionError): self.check()
    def test_partial_fit_link_rejected(self):
        self.graph['records'][self.extras[-1]]['commands'] = [{'source_id': '0'}]
        with self.assertRaises(AssertionError): self.check()
    def test_reordered_original_rejected(self):
        self.graph['fit_order'][:2] = ['1', '0']
        with self.assertRaises(AssertionError): self.check()
    def test_missing_or_extra_original_record_rejected(self):
        del self.graph['modified']['0']
        with self.assertRaises(AssertionError): self.check()


class ReportMembershipTest(unittest.TestCase):
    def setUp(self):
        self.retained = [gate for gate in plan('full', None)[:122] if not gate.startswith('build:')]
        self.state = {'commit': 'after', 'cargo_search_reuse': {'from_commit': retry.BEFORE,
                       'to_commit': 'after', 'retained_gates': self.retained}}
    def test_retained_native_gate_uses_exact_validated_source(self):
        gate = next(g for g in self.retained if g.startswith('native:'))
        self.assertTrue(report_local.validate_c03_host_reuse(ROOT, self.state, gate, retry.BEFORE, set()))
    def test_pending_native_gate_cannot_reuse(self):
        self.assertFalse(report_local.validate_c03_host_reuse(ROOT, self.state,
                         'native:check-cargo-actions.py', retry.BEFORE, set()))
    def test_old_build_gate_cannot_reuse(self):
        self.assertFalse(report_local.validate_c03_host_reuse(ROOT, self.state,
                         'build:package', retry.BEFORE, set()))


class RetainedEvidenceTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.run = Path(temporary.name) / 'run'
        self.archive = self.run / 'archive'
        self.source = Path(temporary.name) / 'build'
        for path in (self.run / 'native', self.run / 'apks', self.run / 'logs',
                     self.archive / 'apks', self.source / 'native', self.source / 'apks'):
            path.mkdir(parents=True, exist_ok=True)
        completed = plan('full', None)[:122]
        self.retained = [g for g in completed if not g.startswith('build:')]
        self.old = dict(commit=retry.BEFORE, status='failed', completed=completed, attempts=[])
        for i, gate in enumerate(completed):
            log = self.run / 'logs' / str(i)
            log.write_text(gate)
            self.old['attempts'].append(dict(gate=gate, log=str(log.relative_to(self.run)),
                      log_sha256=retry.sha(log), tested_commit=retry.BEFORE, exit_code=0))
        self.old['attempts'].append(dict(gate='native:check-cargo-actions.py', exit_code=1))
        (self.archive / 'run.json').write_text(json.dumps(self.old))
        (self.archive / 'recovery').mkdir()
        (self.archive / 'recovery/recovery.json').write_text('{}')
        report = self.run / 'native/retained-report.json'
        report.write_text('actual retained bytes')
        self.manifest = {'native/retained-report.json': {'sha256': retry.sha(report)}}
        (self.archive / 'native-manifest.json').write_text(json.dumps(self.manifest))
        self.current = copy.deepcopy(self.old)
        self.current['commit'] = 'after'
        self.build_rows = {}
        for row in self.current['attempts']:
            if row['gate'].startswith('build:'):
                row.update(tested_commit=retry.TEST_REVISION, reused_from_run=self.source.name)
                self.build_rows[row['gate']] = row
        for directory in (self.archive, self.run, self.source):
            (directory / 'apks/app-debug.apk').write_bytes(b'unchanged application')
            (directory / 'apks/app-debug-androidTest.apk').write_bytes(b'corrected tests')
        for directory in (self.run, self.source):
            (directory / 'native/apk-contents.json').write_text('verified build report')
        (self.source / 'files.json').write_text(json.dumps({'native/apk-contents.json':
                    {'sha256': retry.sha(self.source / 'native/apk-contents.json')}}))
        self.proof = dict(from_commit=retry.BEFORE, to_commit='after', completed_before_adoption=completed,
                retained_gates=self.retained, archive='archive',
                original_run_sha256=retry.sha(self.archive / 'run.json'),
                original_manifest_sha256=retry.sha(self.archive / 'native-manifest.json'),
                recovery_receipt_sha256=retry.sha(self.archive / 'recovery/recovery.json'),
                retained_log_hashes={r['gate']: r['log_sha256'] for r in self.old['attempts']
                                     if r['gate'] in self.retained},
                native_hashes={'native/retained-report.json': retry.sha(report)},
                build_reuse={'apk_hashes': {'app-debug-androidTest.apk': retry.sha(self.run / 'apks/app-debug-androidTest.apk')}})
    def check(self):
        (self.run / 'run.json').write_text(json.dumps(self.current))
        with patch.object(retry, 'exact_source'), patch.object(retry, 'validate_recovery', return_value={}), \
             patch('charge_keyboard_retry.validated_build', return_value=(self.source, {}, self.build_rows)), \
             patch('cargo_history_retry.assets_equal'):
            return retry.validate_retained(ROOT, self.run, self.proof)
    def test_exact_retained_bytes_and_gate_records_pass(self): self.check()
    def test_changed_retained_log_rejected(self):
        (self.run / self.old['attempts'][0]['log']).write_text('changed')
        with self.assertRaises(AssertionError): self.check()
    def test_changed_retained_native_artifact_rejected(self):
        (self.run / 'native/retained-report.json').write_text('changed')
        with self.assertRaises(AssertionError): self.check()
    def test_missing_native_digest_rejected(self):
        self.proof['native_hashes'] = {}
        with self.assertRaises(AssertionError): self.check()
    def test_relabelled_retained_gate_rejected(self):
        self.current['attempts'][0]['tested_commit'] = 'after'
        with self.assertRaises(AssertionError): self.check()
    def test_changed_build_report_rejected(self):
        (self.run / 'native/apk-contents.json').write_text('changed')
        with self.assertRaises(AssertionError): self.check()


class VolatileDiagnosticTest(RetainedEvidenceTest):
    def setUp(self):
        super().setUp()
        failed = self.run / 'native/failure-logcat.txt'
        failed.write_text('original failed-gate diagnostic')
        digest = retry.sha(failed)
        self.manifest['native/failure-logcat.txt'] = {'sha256': digest}
        (self.archive / 'native-manifest.json').write_text(json.dumps(self.manifest))
        self.proof['original_manifest_sha256'] = retry.sha(self.archive / 'native-manifest.json')
        self.proof['native_hashes']['native/failure-logcat.txt'] = digest
        failed.write_text('later failed collector diagnostic')
    def test_missing_failed_diagnostic_does_not_replace_passing_proof(self):
        (self.run / 'native/failure-logcat.txt').unlink()
        self.check()
    def test_nested_same_name_retains_hash_requirement(self):
        nested = self.run / 'native/nested/failure-logcat.txt'
        nested.parent.mkdir()
        nested.write_text('retained nested artifact')
        digest = retry.sha(nested)
        self.manifest['native/nested/failure-logcat.txt'] = {'sha256': digest}
        (self.archive / 'native-manifest.json').write_text(json.dumps(self.manifest))
        self.proof['original_manifest_sha256'] = retry.sha(self.archive / 'native-manifest.json')
        self.proof['native_hashes']['native/nested/failure-logcat.txt'] = digest
        self.check()
        nested.write_text('changed passing artifact')
        with self.assertRaises(AssertionError): self.check()


class TargetingArchiveRoutingTest(unittest.TestCase):
    def setUp(self):
        self.case = RetainedEvidenceTest()
        self.case.setUp(); self.addCleanup(self.case.doCleanups)
        archive = self.case.run / 'targeting-archive'
        archive.mkdir()
        (archive / 'run.json').write_text(json.dumps(self.case.current))
        shutil.copytree(self.case.run / 'apks', archive / 'apks')
        (archive / 'native').mkdir()
        shutil.copyfile(self.case.run / 'native/apk-contents.json', archive / 'native/apk-contents.json')
        self.case.current['targeting_phase_reuse'] = dict(archive=archive.name,
            original_run_sha256=retry.sha(archive / 'run.json'), from_commit='after')
        (self.case.run / 'apks/app-debug-androidTest.apk').write_text('new targeting instrumentation')
        (self.case.run / 'native/apk-contents.json').write_text('new targeting package proof')
        self.archive = archive
    def test_old_proof_routes_to_archived_apk_and_build_rows(self):self.case.check()
    def test_altered_archived_apk_or_state_is_rejected(self):
        for path in (self.archive / 'apks/app-debug-androidTest.apk', self.archive / 'run.json'):
            with self.subTest(path=path):
                original=path.read_bytes();path.write_text('changed old proof')
                with self.assertRaises((AssertionError,json.JSONDecodeError)):self.case.check()
                path.write_bytes(original)


class EmulatorShutdownTest(unittest.TestCase):
    def setUp(self):
        self.runner = Run.__new__(Run)
        self.runner.emulator = Mock()
        self.runner.emulator_log = io.StringIO()
        self.runner.serial = 'emulator-5560'
        self.runner.state = {'commit': 'exact'}
        self.runner.file = Path('unused.json')
    def test_flush_precedes_console_kill_and_records_actual_success(self):
        with patch('local_verification.subprocess.run') as call, patch('local_verification.save') as save:
            self.runner.stop_emulator()
        self.assertEqual([['adb', '-s', 'emulator-5560', 'shell', 'sync'],
                          ['adb', '-s', 'emulator-5560', 'emu', 'kill']], [v.args[0] for v in call.call_args_list])
        self.assertTrue(call.call_args_list[0].kwargs['check'])
        self.assertEqual(self.runner.state['emulator_flushes'],
                         [{'serial': 'emulator-5560', 'exit_code': 0, 'tested_commit': 'exact'}])
        save.assert_called_once()
        self.assertIsNone(self.runner.emulator)
        self.assertTrue(self.runner.emulator_log.closed)
    def test_flush_failure_is_not_accepted_and_owned_process_is_cleaned_up(self):
        failure = subprocess.CalledProcessError(1, ['adb', 'shell', 'sync'])
        with patch('local_verification.subprocess.run', side_effect=[failure, Mock()]) as call, \
             patch('local_verification.save') as save:
            with self.assertRaises(subprocess.CalledProcessError): self.runner.stop_emulator()
        self.assertEqual(call.call_count, 2)
        save.assert_not_called()
        self.assertNotIn('emulator_flushes', self.runner.state)
        self.assertIsNone(self.runner.emulator)
    def test_no_process_has_no_flush_or_mutation(self):
        self.runner.emulator = None
        with patch('local_verification.subprocess.run') as call:
            self.runner.stop_emulator()
            call.assert_not_called()


if __name__ == '__main__': unittest.main()
