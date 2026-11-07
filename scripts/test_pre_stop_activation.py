"""Fake checks for the activation binding on a separate verification branch."""
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import stat
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parent
POLICY = SOURCE.parent / 'execution-policy.json'
PINNED_INPUTS = {'execution_policy.py': '647579eaac5be57db951bbb5d68432f237bbdd4191338328d34067320e355c03',
 'run_project_job.py': '40d25ca01499448a01978115acbe4e0accbae582923e9f0bf91ae4ee0a46fc8f',
 'test_run_project_job.py': 'a84294405c998dcb2a131ad2e3e245ec8e3c8c89c7d134569c96d6cf508cab94'}
for filename, expected in PINNED_INPUTS.items():
    if hashlib.sha256((SOURCE / filename).read_bytes()).hexdigest() != expected:
        raise ValueError(f'Pinned fake-verification input differs: {filename}')
if hashlib.sha256(POLICY.read_bytes()).hexdigest() != (
        '8a5ef27c6051ae6268ee7735c767aea3457779525f191b2cb4313146ab8d5827'):
    raise ValueError('Pinned fake-verification policy differs')
sys.path.insert(0, str(SOURCE))
import execution_policy as policy_api
import run_project_job as runner
from test_run_project_job import FakeClock, FakeHost, FencedJob


# Frozen original #237 queue descriptor. Tests substitute a synthetic interpreter and commit.
ORIGINAL_REQUEST = {'argv': ['C:/Program Files/Python313/python.exe',
          '-B',
          '-m',
          'unittest',
          'discover',
          '-s',
          'scripts',
          '-p',
          'test_run_project_job.py',
          '-v'],
 'commit': '6286d8175957d58cecb108e9e27f5aa2ec348ef1',
 'estimated_disk_write_bytes': 268435456,
 'idempotency_key': '3c843e595047e2490c1fb1c45ac8dd0ff989d5ab770e911e97dfd76265860406',
 'kind': 'codex-msi-validation',
 'policy_path': 'execution-policy.json',
 'policy_sha256': '8a5ef27c6051ae6268ee7735c767aea3457779525f191b2cb4313146ab8d5827',
 'project': 'pyfa',
 'repository': 'Sussic/Pyfa-android',
 'required_capabilities': ['windows', 'python'],
 'schema_version': 1,
 'workload': 'focused_test'}

class ActivationBindingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.policy = {'project': 'pyfa', 'locations': {'execution_root': str(self.root)}}
        self.digest = runner._DIAGNOSTIC_POLICY_SHA256
        self.settings = dict(host='msi', workload='focused_test', workers=4,
                             estimated_peak_bytes=1073741824, cpu_hard_cap_percent=None)
        self.runtime = self.root / 'python.exe'
        self.runtime.write_bytes(b'fake interpreter')
        self.argv = [str(self.runtime), *runner._DIAGNOSTIC_ARGV[1:]]
        self.forecast = 268435456
        commit = 'a' * 40
        original = ORIGINAL_REQUEST
        self.assertEqual(tuple(original['argv']), runner._DIAGNOSTIC_ARGV)
        self.request = {key: value for key, value in original.items() if key != 'idempotency_key'}
        original_bytes = json.dumps(self.request, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        self.assertEqual(original['idempotency_key'], hashlib.sha256(original_bytes.encode('utf-8')).hexdigest())
        self.request.update(commit=commit, argv=self.argv)
        data = json.dumps(self.request, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        self.key = hashlib.sha256(data.encode('utf-8')).hexdigest()
        self.request['idempotency_key'] = self.key
        self.job = self.root / 'jobs' / self.key
        self.source = self.job / 'source'
        self.attempt = self.job / 'results' / 'attempt-0001'
        self.prefix = self.attempt / 'policy'
        self.attempt.mkdir(parents=True)
        (self.source / '.git').mkdir(parents=True)
        (self.source / 'scripts').mkdir()
        self.head = self.source / '.git' / 'HEAD'
        self.head.write_text(commit + '\n', encoding='ascii')
        self.fixture = self.source / 'scripts' / 'test_run_project_job.py'
        self.fixture.write_bytes(b'fake frozen fixture')
        self.request_path = self.attempt / 'request.json'
        self.request_path.write_text(json.dumps(self.request), encoding='utf-8')
        self.marker = self.job / '.msi-job-owner.json'
        owner = {name: self.request[name] for name in ('project', 'repository', 'commit', 'policy_sha256')}
        # Worker mark_new_job layout from the retained f9c42c4 runner_lifecycle.py.
        owner.update(schema_version=1, kind='codex-msi-owned-job', job_root=str(self.job),
                     request_sha256=self.key, created_utc='2026-11-07T00:00:00+00:00',
                     git_refs_sha256='1' * 64, git_metadata_sha256='2' * 64,
                     source_tree_sha256='3' * 64)
        self.marker.write_text(json.dumps(owner), encoding='utf-8')
        for target, name, value in (
            (runner, '_DIAGNOSTIC_ARGV', tuple(self.argv)),
            (runner, '_DIAGNOSTIC_RUNTIME_SHA256', hashlib.sha256(self.runtime.read_bytes()).hexdigest()),
            (runner, '_DIAGNOSTIC_FIXTURE_SHA256', hashlib.sha256(self.fixture.read_bytes()).hexdigest()),
            (runner, '__file__', str(self.source / 'scripts' / 'run_project_job.py')),
            (Path, 'cwd', lambda: self.source),
        ):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.dict(os.environ, {'CODEX_QUEUE_JOB_ID': self.key})
        patcher.start()
        self.addCleanup(patcher.stop)

    def queue(self, *, argv=None, prefix=None, raw=1):
        output = io.StringIO()
        receipt = {'status': 'deferred', 'reconciliation_required': False, 'reason': 'fake no launch'}
        with mock.patch.object(runner, 'run', return_value=raw) as run, \
                mock.patch.object(runner, '_queue_receipt', return_value=receipt), redirect_stdout(output):
            code = runner._queue_run(self.policy, self.digest, self.settings,
                                     argv or self.argv, prefix or self.prefix, self.forecast, 0)
        return code, run, json.loads(output.getvalue())

    def test_exact_worker_owned_request_selects_observer(self):
        code, run, verdict = self.queue()
        self.assertEqual(1, code)
        run.assert_called_once()
        self.assertTrue(callable(run.call_args.kwargs['activity_observer']))
        self.assertEqual('raw_outcome_preserved', verdict['reason'])
        capture = run.call_args.kwargs['activity_observer']
        with mock.patch.object(runner._CustodyCapture, 'observe_activity', autospec=True) as observe:
            job, accounting = object(), object()
            capture(job, accounting, 0, 3, 20)
        self.assertEqual((job, accounting, 0, 3, 20), observe.call_args.args[1:])
        self.assertEqual(self.request['commit'], observe.call_args.kwargs['source_commit'])
        self.assertEqual(self.digest, observe.call_args.kwargs['policy_sha256'])
        self.assertEqual(runner._DIAGNOSTIC_RUNTIME_SHA256, observe.call_args.kwargs['runtime_sha256'])

    def test_mismatched_inputs_refuse_before_runner_creation(self):
        for path, replacement in (
            (self.head, b'ref: refs/heads/other\n'),
            (self.head, b'b' * 40),
            (self.request_path, b'{}'),
            (self.marker, b'{}'),
            (self.fixture, b'wrong fixture'),
            (self.runtime, b'wrong runtime'),
        ):
            with self.subTest(path=path.name):
                old = path.read_bytes()
                try:
                    path.write_bytes(replacement)
                    code, run, verdict = self.queue()
                finally:
                    path.write_bytes(old)
                self.assertEqual(1, code)
                self.assertEqual('diagnostic_binding_refused', verdict['reason'])
                self.assertFalse(verdict['creation_attempted'])
                run.assert_not_called()

    def test_wrong_attempt_policy_host_profile_or_forecast_refuses(self):
        saved = self.digest, self.settings, self.forecast
        for mode in ('later-attempt', 'policy', 'host', 'profile', 'forecast'):
            with self.subTest(mode=mode):
                prefix = self.prefix
                if mode == 'later-attempt':
                    prefix = self.attempt.parent / 'attempt-0002' / 'policy'
                if mode == 'policy':
                    self.digest = 'd' * 64
                if mode == 'host':
                    self.settings = dict(self.settings, host='initia')
                if mode == 'profile':
                    self.settings = dict(self.settings, workload='build')
                if mode == 'forecast':
                    self.forecast += 1
                try:
                    code, run, verdict = self.queue(prefix=prefix)
                finally:
                    self.digest, self.settings, self.forecast = saved
                self.assertEqual(1, code)
                self.assertEqual('diagnostic_binding_refused', verdict['reason'])
                self.assertFalse(verdict['creation_attempted'])
                run.assert_not_called()

    def test_wrong_key_checkout_owner_and_reparse_refuse_before_runner(self):
        original_lstat = Path.lstat

        def reparse_marker(path):
            if path == self.marker:
                return SimpleNamespace(st_mode=stat.S_IFREG,
                                       st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
            return original_lstat(path)

        owner = json.loads(self.marker.read_bytes())
        for mode in ('key', 'checkout', 'owner', 'reparse'):
            with self.subTest(mode=mode):
                with mock.patch.dict(os.environ), mock.patch.object(Path, 'cwd', lambda: self.source):
                    if mode == 'key':
                        os.environ['CODEX_QUEUE_JOB_ID'] = 'c' * 64
                    if mode == 'checkout':
                        Path.cwd = lambda: self.root
                    if mode == 'owner':
                        self.marker.write_text(json.dumps(dict(owner, request_sha256='c' * 64)), encoding='utf-8')
                    try:
                        with mock.patch.object(Path, 'lstat', reparse_marker if mode == 'reparse' else original_lstat):
                            code, run, verdict = self.queue()
                    finally:
                        self.marker.write_text(json.dumps(owner), encoding='utf-8')
                self.assertEqual(1, code)
                self.assertEqual('diagnostic_binding_refused', verdict['reason'])
                self.assertFalse(verdict['creation_attempted'])
                run.assert_not_called()

    def test_queue_validates_extended_receipt_without_overriding_raw_result(self):
        def fake_run(policy, digest, settings, command, prefix, forecast, total, *,
                     activity_observer, attempt_observer):
            self.assertTrue(callable(activity_observer))
            attempt_observer('registration')
            attempt_observer('creation')
            stamp = datetime.now(timezone.utc).isoformat()
            report = dict(schema_version=1, status='failed', exit_code=raw_in_receipt,
                          project=policy['project'], host=settings['host'], workload=settings['workload'],
                          policy_sha256=digest, argv=command, workers=settings['workers'],
                          project_logical_bytes=total, estimated_disk_write_bytes=forecast,
                          estimated_peak_bytes=settings['estimated_peak_bytes'], hard_memory_cap_bytes=None,
                          cpu_hard_cap_percent=settings['cpu_hard_cap_percent'], started_utc=stamp,
                          completed_utc=stamp, seconds=0, reconciliation_required=False,
                          pre_stop_activity={'kind': 'private-owned-activity-diagnostic', 'complete': True})
            Path(str(prefix) + '-result.json').write_text(json.dumps(report), encoding='utf-8')
            return 1

        for raw_in_receipt in (1, 0):
            with self.subTest(raw_in_receipt=raw_in_receipt):
                output = io.StringIO()
                with mock.patch.object(runner, 'run', side_effect=fake_run), redirect_stdout(output):
                    code = runner._queue_run(self.policy, self.digest, self.settings, self.argv,
                                             self.prefix, self.forecast, 0)
                Path(str(self.prefix) + '-result.json').unlink()
                verdict = json.loads(output.getvalue())
                self.assertEqual(1, code)
                self.assertEqual(1, verdict['raw_source_exit'])
                self.assertTrue(verdict['creation_attempted'])
                if raw_in_receipt == 1:
                    self.assertEqual('raw_outcome_preserved', verdict['reason'])
                else:
                    self.assertTrue(verdict['reason'].startswith('invalid_final_receipt'))

    def test_other_command_uses_original_queue_path(self):
        code, run, verdict = self.queue(argv=['ordinary-command'], raw=75)
        self.assertEqual(75, code)
        run.assert_called_once()
        self.assertNotIn('activity_observer', run.call_args.kwargs)
        self.assertEqual('proven_nonlaunching_deferral', verdict['reason'])

    def test_diagnostic_deferral_preserves_raw_75_and_is_terminal(self):
        code, run, verdict = self.queue(raw=75)
        self.assertEqual(1, code)
        run.assert_called_once()
        self.assertEqual(75, verdict['raw_source_exit'])
        self.assertEqual('diagnostic_attempt_consumed', verdict['reason'])

    def test_exact_command_requires_queue_entry_and_default_policy(self):
        args = ['--profile', 'focused_test', '--required-disk-bytes', str(self.forecast), '--', *self.argv]
        with mock.patch.dict(os.environ), mock.patch.object(runner, 'run') as run, redirect_stdout(io.StringIO()):
            del os.environ['CODEX_QUEUE_JOB_ID']
            self.assertEqual(1, runner.main(args))
            run.assert_not_called()
        with mock.patch.object(policy_api, 'load_policy') as load, redirect_stdout(io.StringIO()):
            self.assertEqual(1, runner.main(['--policy', str(self.root / 'wrong.json'), *args]))
            load.assert_not_called()


class ActivationReceiptTests(unittest.TestCase):
    def run_guard(self, mode):
        policy, digest = policy_api.load_policy(POLICY)
        policy = deepcopy(policy)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        policy['locations']['shared_root'] = str(root / 'shared')
        settings = policy_api.select(policy, 'msi', 'focused_test')
        events = []
        host = FakeHost(events)
        job = FencedJob(settings, host, events)
        job.poll = mock.Mock(return_value=0)
        job.active = lambda: int(mode != 'empty' and not job.stopped)
        native = SimpleNamespace(WindowsJob=lambda: job, Accounting=object())
        prefix = root / 'results' / 'policy'
        clock = FakeClock()

        @contextmanager
        def lease(*_):
            try:
                yield
            finally:
                events.append('lease-exit')

        def observe(*_):
            events.append('diagnostic')
            self.assertNotIn('stop', events)
            if mode == 'cancel':
                raise KeyboardInterrupt()
            record = {'kind': 'private-owned-activity-diagnostic', 'complete': False,
                      'original_guard': {'root_exit_code': 0, 'active_return': 1}}
            if mode == 'cap':
                record['padding'] = 'x' * runner._CustodyCapture.MAX_BYTES
            if mode == 'nan':
                record['value'] = float('nan')
            return record

        def validate(record):
            self.assertIn('host-complete', events)
            self.assertNotIn('lease-exit', events)
            events.append('validate-activity')
            return original_validate(record)

        original_validate = runner._activity_receipt
        with mock.patch.object(policy_api, 'msi_native_job', return_value=native), \
                mock.patch.object(policy_api, 'heavy_lease', side_effect=lease), \
                mock.patch.object(runner.time, 'monotonic', clock.monotonic), \
                mock.patch.object(runner.time, 'sleep'), \
                mock.patch.object(runner, '_activity_receipt', side_effect=validate), redirect_stdout(io.StringIO()):
            code = runner.run(policy, digest, settings, ['synthetic'], prefix, 0, 0,
                              host_factory=lambda *_: host, activity_observer=observe)
        result = json.loads(Path(str(prefix) + '-result.json').read_bytes())
        self.assertEqual(['policy-result.json', 'policy.log'],
                         sorted(p.name for p in prefix.parent.iterdir()))
        self.assertEqual('lease-exit', events[-1])
        self.assertTrue(result['msi_admission']['closure_confirmed'])
        self.assertFalse(result['reconciliation_required'])
        return code, result, events

    def test_valid_extension_keeps_guard_and_raw_fields(self):
        code, result, events = self.run_guard('sample')
        self.assertEqual(1, code)
        self.assertEqual(1, result['exit_code'])
        self.assertEqual('RuntimeError', result['failure_type'])
        self.assertEqual(0, result['root_exit_code'])
        self.assertEqual(0, result['remaining_job_processes'])
        self.assertEqual({'root_exit_code': 0, 'active_return': 1},
                         result['pre_stop_activity']['original_guard'])
        ordered = ['diagnostic', 'stop', 'custody', 'job-close', 'host-complete', 'validate-activity', 'lease-exit']
        self.assertEqual(ordered, [event for event in events if event in ordered])

    def test_cap_invalid_value_and_cancel_leave_valid_failed_receipt(self):
        for mode in ('cap', 'nan', 'cancel'):
            with self.subTest(mode=mode):
                code, result, _ = self.run_guard(mode)
                self.assertEqual(1, code)
                self.assertEqual('RuntimeError', result['failure_type'])
                self.assertEqual({'status': 'unavailable'}, result['pre_stop_activity'])

    def test_normal_completion_has_no_diagnostic_extension(self):
        code, result, events = self.run_guard('empty')
        self.assertEqual(0, code)
        self.assertNotIn('diagnostic', events)
        self.assertNotIn('pre_stop_activity', result)


if __name__ == '__main__':
    unittest.main()
