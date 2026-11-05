"""Owned-root cleanup regressions using fakes; no Windows jobs or Beacon imports."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import execution_policy as policy_api
import run_project_job as runner


class FakeClock:
    def __init__(self):
        self.now = 0

    def monotonic(self):
        self.now += 1
        return self.now


class UnassignedRoot:
    """Creation succeeded; assignment failed before the suspended root could run."""
    def __init__(self, settings, polls_until_exit):
        self.settings = settings
        self.polls_until_exit = polls_until_exit
        self.poll_count = 0
        self.process = None
        self.pid = 12345
        self.stop_called = False
        self.closed = False

    def resources(self, _disk_root):
        available = self.settings['ram_reserve_bytes'] + self.settings['estimated_peak_bytes']
        return dict(available_physical=available, available_commit=available,
                    free_disk=self.settings['disk_free_reserve_bytes'])

    def launch(self, _argv, _environment, _cwd, _log):
        self.process = object()
        raise OSError('fake suspended-root assignment failure')

    def stop(self, _code):
        self.stop_called = True

    def poll(self):
        self.poll_count += 1
        if self.polls_until_exit is not None and self.poll_count >= self.polls_until_exit:
            return 1
        return None

    def active(self):
        return 0  # The failed assignment never put the root in this Job.

    def telemetry(self):
        return {}

    def close(self):
        self.closed = True
        self.process = None


class NativeExitObservationTests(unittest.TestCase):
    def test_signalled_worker_can_return_the_legitimate_exit_code_259(self):
        job = runner.WindowsJob.__new__(runner.WindowsJob)
        job.process = object()
        def exited(_handle, output):
            output._obj.value = 259
            return True
        job.kernel = mock.Mock()
        job.kernel.WaitForSingleObject.return_value = 0
        job.kernel.GetExitCodeProcess.side_effect = exited
        self.assertEqual(259, job.poll())
        job.kernel.WaitForSingleObject.assert_called_once_with(job.process, 0)

    def test_unsignalled_worker_is_live_without_interpreting_its_exit_code(self):
        job = runner.WindowsJob.__new__(runner.WindowsJob)
        job.process = object()
        job.kernel = mock.Mock()
        job.kernel.WaitForSingleObject.return_value = 258
        self.assertIsNone(job.poll())
        job.kernel.GetExitCodeProcess.assert_not_called()


class OwnedRootCleanupTests(unittest.TestCase):
    def setUp(self):
        current, self.digest = policy_api.load_policy()
        self.policy = deepcopy(current)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.policy['locations']['shared_root'] = str(self.root / 'shared')
        self.settings = policy_api.select(self.policy, 'initia', 'focused_test')

    def run_fake(self, polls_until_exit):
        job = UnassignedRoot(self.settings, polls_until_exit)
        clock = FakeClock()
        prefix = self.root / 'results' / 'fake-root'
        with mock.patch.object(runner.time, 'monotonic', clock.monotonic), \
                mock.patch.object(runner.time, 'sleep', lambda _seconds: None):
            code = runner.run(self.policy, self.digest, self.settings, ['fake-owned-root'],
                              prefix, 0, 0, job_factory=lambda: job)
        result = json.loads(Path(str(prefix) + '-result.json').read_text(encoding='utf-8'))
        return code, result, job

    def test_empty_job_does_not_confirm_delayed_unassigned_root_exit(self):
        code, result, job = self.run_fake(polls_until_exit=3)
        self.assertEqual(1, code)  # The assignment failure remains a failure.
        self.assertTrue(job.stop_called)
        self.assertEqual(3, job.poll_count)
        self.assertTrue(result['root_exit_confirmed'])
        self.assertTrue(result['tree_exit_confirmed'])
        self.assertEqual(0, result['remaining_job_processes'])
        self.assertFalse(result['reconciliation_required'])
        self.assertTrue(job.closed)
        self.assertFalse(policy_api.reconciliation_path(self.policy, self.settings).exists())
        with policy_api.heavy_lease(self.policy, self.settings) as lease:
            self.assertIsNotNone(lease)

    def test_unconfirmed_unassigned_root_blocks_later_heavy_admission(self):
        code, result, job = self.run_fake(polls_until_exit=None)
        self.assertEqual(1, code)
        self.assertFalse(result['root_exit_confirmed'])
        self.assertFalse(result['tree_exit_confirmed'])
        self.assertTrue(result['reconciliation_required'])
        marker = Path(result['reconciliation_marker'])
        original = marker.read_bytes()
        record = json.loads(original)
        self.assertEqual('OWNED_PROCESS_CLOSURE_UNRESOLVED', record['state'])
        self.assertEqual(job.pid, record['details']['worker_pid'])
        self.assertEqual(0, record['details']['remaining_job_processes'])
        self.assertFalse(record['details']['root_exit_confirmed'])
        # The OS lease has closed, but durable unknown ownership still refuses admission.
        for _ in range(2):
            with self.assertRaises(policy_api.AdmissionDeferred):
                with policy_api.heavy_lease(self.policy, self.settings):
                    self.fail('Unresolved root must prevent another heavy holder')
            self.assertEqual(original, marker.read_bytes())
        # Independent light work has no heavy-lease requirement and never clears proof.
        light = policy_api.select(self.policy, 'initia', 'light')
        with policy_api.heavy_lease(self.policy, light) as lease:
            self.assertIsNone(lease)
        self.assertEqual(original, marker.read_bytes())


class FakeHost:
    class denied_error(RuntimeError):
        pass

    def __init__(self, events, deny_at=None):
        self.events, self.deny_at = events, deny_at
        self.locked_now, self.checks = False, 0
        self.tokens = set()

    @contextmanager
    def locked(self):
        assert not self.locked_now
        self.locked_now = True
        self.events.append('host-lock')
        try:
            yield
        finally:
            self.locked_now = False
            self.events.append('host-unlock')

    def assert_development(self):
        assert self.locked_now
        self.checks += 1
        self.events.append('host-check')
        if self.checks == self.deny_at:
            raise self.denied_error('fake wind-down requested')

    def register_locked(self, route, details=None):
        assert self.locked_now and route == 'direct'
        assert details['project'] == 'pyfa' and details['policy_sha256']
        self.events.append('host-register')
        token = 'a' * 32
        self.tokens.add(token)
        return token

    def complete(self, token, closure=True):
        assert not self.locked_now and closure is True
        assert 'job-close' in self.events and 'lease-exit' not in self.events
        self.events.append('host-complete')
        self.tokens.remove(token)


class FencedJob:
    """Synthetic ordinary-job interface; it creates no native process."""
    def __init__(self, settings, host, events):
        self.settings, self.host, self.events = settings, host, events
        self.process, self.pid = None, 23456
        self.stopped, self.closed = False, False
        self.resource_calls, self.poll_calls, self.active_calls = 0, 0, 0
        self.live_polls, self.code = 1, 0
        self.launch_error, self.telemetry_error, self.custody_error = None, None, None
        self.resource_interrupt, self.active_error, self.close_error = False, False, False
        self.pressure, self.low_disk, self.never_stops = False, False, False
        self.custody_result = dict(total_processes=2, retained_identity_count=2,
            all_identities_accounted=True, all_retained_descendants_exited=True, complete=True)

    def resources(self, disk_root):
        self.events.append('resources')
        self.resource_calls += 1
        if self.host is not None:
            assert not self.host.locked_now
        if self.resource_interrupt and self.resource_calls == 2:
            raise KeyboardInterrupt('fake cancellation')
        required = self.settings['ram_reserve_bytes'] + self.settings['estimated_peak_bytes']
        if self.pressure and self.resource_calls > 1:
            required = self.settings['running_free_floor_bytes'] - 1
        disk = self.settings['disk_free_reserve_bytes']
        if self.low_disk and self.resource_calls > 1:
            disk -= 1
        return dict(available_physical=required, available_commit=required, free_disk=disk)

    def launch(self, argv, environment, cwd, log):
        self.events.append('launch')
        if self.host is not None:
            assert self.host.locked_now and self.host.tokens
        self.launched_argv, self.environment, self.cwd = argv, environment, cwd
        log.write(b'combined ordinary output\n')
        if self.launch_error != 'unknown':
            self.process = object()
        if self.launch_error:
            raise OSError('fake partial or unknown creation')

    def poll(self):
        self.events.append('poll')
        self.poll_calls += 1
        if self.stopped:
            return None if self.never_stops else 1
        return None if self.poll_calls <= self.live_polls else self.code

    def active(self):
        self.events.append('active')
        self.active_calls += 1
        assert self.host is None or not self.host.locked_now
        if self.active_error and self.active_calls == 1:
            raise OSError('fake unreadable descendant identity')
        return int(self.never_stops or (not self.stopped and self.poll_calls <= self.live_polls))

    def stop(self, code):
        self.events.append('stop')
        self.stopped = True

    def telemetry(self):
        self.events.append('telemetry')
        if self.telemetry_error:
            raise OSError('fake telemetry failure')
        return dict(peak_job_commit_bytes=123, peak_process_commit_bytes=100, owned_cpu_seconds=0.5)

    def custody(self):
        assert not self.closed
        self.events.append('custody')
        if self.custody_error:
            raise OSError('fake custody failure')
        return self.custody_result

    def close(self):
        self.events.append('job-close')
        self.closed, self.process = True, None
        if self.close_error:
            if self.close_error == 'interrupt':
                raise KeyboardInterrupt('fake interrupted close')
            raise OSError('fake close failure')


class MSIFenceRunnerTests(unittest.TestCase):
    def setUp(self):
        policy, self.digest = policy_api.load_policy()
        self.policy = deepcopy(policy)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.policy['locations']['shared_root'] = str(self.root / 'shared')
        self.settings = policy_api.select(self.policy, 'msi', 'focused_test')
        self.events = []
        self.host = FakeHost(self.events)
        self.job = FencedJob(self.settings, self.host, self.events)
        self.attempt = 0

    def run_fake(self, *, host_factory=None, use_default_job=False):
        self.attempt += 1
        prefix = self.root / str(self.attempt) / 'job'
        clock = FakeClock()
        @contextmanager
        def lease(policy, settings):
            self.assertIs(policy, self.policy)
            self.assertIs(settings, self.settings)
            self.events.append('lease-enter')
            try:
                yield
            finally:
                self.events.append('lease-exit')
        kwargs = dict(host_factory=host_factory or (lambda *_: self.host))
        if not use_default_job:
            def create_job():
                self.events.append('job-create')
                return self.job
            kwargs['job_factory'] = create_job
        with mock.patch.object(runner.time, 'monotonic', clock.monotonic), \
                mock.patch.object(runner.time, 'sleep', lambda _: None), \
                mock.patch.object(policy_api, 'heavy_lease', side_effect=lease) as leases:
            code = runner.run(self.policy, self.digest, self.settings,
                ['synthetic-command', 'space value', '--literal'], prefix, 0, 0, **kwargs)
        result = json.loads(Path(str(prefix) + '-result.json').read_text(encoding='utf-8'))
        return code, result, prefix, leases.call_count

    def test_success_fences_creation_and_retains_custody_before_completion_and_lease_release(self):
        code, result, prefix, leases = self.run_fake()
        self.assertEqual(0, code)
        self.assertEqual(1, leases)
        self.assertEqual(2, self.host.checks)
        self.assertFalse(self.host.tokens)
        self.assertTrue(result['msi_admission']['closure_confirmed'])
        self.assertFalse(result['msi_admission']['hold_retained'])
        self.assertTrue(result['tree_exit_confirmed'])
        self.assertEqual(self.job.custody_result, result['owned_custody'])
        self.assertLess(self.events.index('host-register'), self.events.index('launch'))
        self.assertLess(self.events.index('custody'), self.events.index('job-close'))
        self.assertLess(self.events.index('job-close'), self.events.index('host-complete'))
        self.assertLess(self.events.index('host-complete'), self.events.index('lease-exit'))
        self.assertGreaterEqual(self.job.active_calls, 3)
        self.assertLess(self.events.index('active'), self.events.index('poll'))
        self.assertGreaterEqual(self.job.resource_calls, 4)
        self.assertEqual(['synthetic-command', 'space value', '--literal'], self.job.launched_argv)
        self.assertEqual(result['argv'], self.job.launched_argv)
        self.assertEqual(str(self.settings['workers']), self.job.environment['MAX_JOBS'])
        self.assertEqual('1', self.job.environment['PYTHONDONTWRITEBYTECODE'])
        self.assertEqual(Path.cwd(), self.job.cwd)
        self.assertEqual(b'combined ordinary output\n', Path(str(prefix) + '.log').read_bytes())
        self.assertEqual(1, result['schema_version'])
        self.assertEqual('passed', result['status'])
        self.assertEqual(self.digest, result['policy_sha256'])
        self.assertIsNone(result['hard_memory_cap_bytes'])
        self.assertIsNone(result['cpu_hard_cap_percent'])
        self.assertEqual(123, result['owned_usage']['peak_job_commit_bytes'])
        self.assertEqual(result['admission'], result['minimum'])

    def test_every_msi_profile_rechecks_wind_down_before_creating_any_child(self):
        for workload in self.policy['workloads']:
            with self.subTest(workload=workload):
                self.events = []
                self.host = FakeHost(self.events, deny_at=2)
                self.settings = policy_api.select(self.policy, 'msi', workload)
                self.job = FencedJob(self.settings, self.host, self.events)
                code, result, _, leases = self.run_fake()
                self.assertEqual(75, code)
                self.assertEqual('deferred', result['status'])
                self.assertNotIn('launch', self.events)
                self.assertNotIn('host-register', self.events)
                self.assertFalse(self.host.tokens)
                self.assertEqual(1, leases)
                self.assertNotIn('worker_pid', result)

    def test_early_light_denial_never_constructs_job_or_takes_resource_lease(self):
        self.settings = policy_api.select(self.policy, 'msi', 'light')
        self.host.deny_at = 1
        code, result, _, leases = self.run_fake()
        self.assertEqual(75, code)
        self.assertEqual(0, leases)
        self.assertEqual(0, self.job.resource_calls)
        self.assertNotIn('job-create', self.events)
        self.assertNotIn('launch', self.events)
        self.assertNotIn('msi_admission', result)

    def test_missing_host_cannot_silently_use_an_unfenced_msi_path(self):
        code, result, _, leases = self.run_fake(host_factory=lambda *_: None)
        self.assertEqual(75, code)
        self.assertEqual(0, leases)
        self.assertNotIn('launch', self.events)
        self.assertNotIn('msi_admission', result)

    def test_default_msi_job_comes_from_qualified_native_loader(self):
        native = mock.Mock(WindowsJob=lambda: self.job)
        with mock.patch.object(policy_api, 'msi_native_job', return_value=native) as loader, \
                mock.patch.object(runner, 'WindowsJob', side_effect=AssertionError('Initia fallback')):
            code, _, _, _ = self.run_fake(use_default_job=True)
        self.assertEqual(0, code)
        loader.assert_called_once_with(self.policy, self.settings)

    def test_native_loader_deferral_never_constructs_or_launches_fallback(self):
        with mock.patch.object(policy_api, 'msi_native_job', side_effect=policy_api.AdmissionDeferred('bad pin')), \
                mock.patch.object(runner, 'WindowsJob', side_effect=AssertionError('Initia fallback')):
            code, result, _, leases = self.run_fake(use_default_job=True)
        self.assertEqual(75, code)
        self.assertEqual(0, leases)
        self.assertNotIn('launch', self.events)
        self.assertNotIn('msi_admission', result)

    def test_resource_denial_precedes_registration_and_creation_without_a_host_hold(self):
        required = self.settings['ram_reserve_bytes'] + self.settings['estimated_peak_bytes']
        values = dict(available_physical=required - 1, available_commit=required,
                      free_disk=self.settings['disk_free_reserve_bytes'])
        with mock.patch.object(self.job, 'resources', return_value=values):
            code, result, _, leases = self.run_fake()
        self.assertEqual(75, code)
        self.assertEqual(1, leases)
        self.assertNotIn('host-register', self.events)
        self.assertNotIn('launch', self.events)
        self.assertFalse(self.host.tokens)
        self.assertNotIn('msi_admission', result)

    def test_partial_or_unknown_creation_keeps_registration_even_after_cleanup(self):
        for creation in ('partial', 'unknown'):
            with self.subTest(creation=creation):
                self.events = []
                self.host = FakeHost(self.events)
                self.job = FencedJob(self.settings, self.host, self.events)
                self.job.launch_error = creation
                code, result, _, _ = self.run_fake()
                self.assertEqual(1, code)
                self.assertEqual({'a' * 32}, self.host.tokens)
                self.assertTrue(result['msi_admission']['hold_retained'])
                self.assertNotIn('host-complete', self.events)
                self.assertEqual(creation == 'partial', self.job.stopped)
                if creation == 'partial':
                    self.assertTrue(result['tree_exit_confirmed'])
                    self.assertFalse(result['reconciliation_required'])

    def test_incomplete_missing_or_inconsistent_lifetime_custody_keeps_successful_command_held(self):
        variants = [dict(total_processes=3, retained_identity_count=2, all_identities_accounted=False,
                         all_retained_descendants_exited=True, complete=False),
                    {}, dict(self.job.custody_result, complete=1),
                    dict(self.job.custody_result, retained_identity_count=1)]
        for custody in variants:
            with self.subTest(custody=custody):
                self.events = []
                self.host = FakeHost(self.events)
                self.job = FencedJob(self.settings, self.host, self.events)
                self.job.custody_result = custody
                code, result, _, _ = self.run_fake()
                self.assertEqual(0, code)
                self.assertEqual('passed', result['status'])
                self.assertTrue(result['tree_exit_confirmed'])
                self.assertTrue(result['msi_admission']['hold_retained'])
                self.assertTrue(self.host.tokens)
                self.assertFalse(result['reconciliation_required'])
                self.assertNotIn('host-complete', self.events)

    def test_observation_or_handle_failure_never_completes_host_custody(self):
        for failure, field in (('telemetry_error', 'usage_observation_error'),
                               ('custody_error', 'custody_observation_error'),
                               ('active_error', 'ownership_observation_error'),
                               ('close_error', 'cleanup_error'),
                               ('interrupted_close', 'cleanup_error')):
            with self.subTest(failure=failure):
                self.events = []
                self.host = FakeHost(self.events)
                self.job = FencedJob(self.settings, self.host, self.events)
                if failure == 'interrupted_close':
                    self.job.close_error = 'interrupt'
                else:
                    setattr(self.job, failure, True)
                _, result, _, _ = self.run_fake()
                self.assertIn(field, result)
                self.assertTrue(result['msi_admission']['hold_retained'])
                self.assertTrue(self.host.tokens)
                self.assertTrue(self.job.closed)
                self.assertNotIn('host-complete', self.events)

    def test_host_completion_failure_keeps_the_registration_and_fails_the_receipt(self):
        with mock.patch.object(self.host, 'complete', side_effect=OSError('fake completion write failure')):
            code, result, _, _ = self.run_fake()
        self.assertEqual(1, code)
        self.assertEqual('failed', result['status'])
        self.assertIn('host_completion_error', result)
        self.assertTrue(result['msi_admission']['hold_retained'])
        self.assertTrue(self.host.tokens)

    def test_legitimate_nonzero_exit_keeps_product_failure_and_releases_proven_custody(self):
        self.job.code = 259
        code, result, _, _ = self.run_fake()
        self.assertEqual(259, code)
        self.assertEqual(259, result['root_exit_code'])
        self.assertEqual('failed', result['status'])
        self.assertFalse(result['msi_admission']['hold_retained'])
        self.assertFalse(self.host.tokens)

    def test_timeout_and_cancellation_release_only_after_proven_cleanup(self):
        for failure in ('timeout', 'cancel'):
            with self.subTest(failure=failure):
                self.events = []
                self.host = FakeHost(self.events)
                self.job = FencedJob(self.settings, self.host, self.events)
                self.job.live_polls = 100
                self.job.resource_interrupt = failure == 'cancel'
                if failure == 'timeout':
                    self.settings = dict(self.settings, timeout_seconds=1)
                    self.job.settings = self.settings
                code, result, _, _ = self.run_fake()
                self.assertEqual(1, code)
                self.assertEqual('KeyboardInterrupt' if failure == 'cancel' else 'TimeoutError', result['failure_type'])
                self.assertTrue(self.job.stopped)
                self.assertTrue(result['tree_exit_confirmed'])
                self.assertFalse(result['msi_admission']['hold_retained'])
                self.assertFalse(self.host.tokens)

    def test_memory_pressure_and_disk_stops_preserve_polling_and_clean_custody(self):
        for pressure in (True, False):
            with self.subTest(pressure=pressure):
                self.events = []
                self.host = FakeHost(self.events)
                self.job = FencedJob(self.settings, self.host, self.events)
                self.job.live_polls = 100
                self.job.pressure, self.job.low_disk = pressure, not pressure
                code, result, _, leases = self.run_fake()
                self.assertEqual(75, code)
                self.assertEqual('deferred', result['status'])
                self.assertTrue(self.job.stopped)
                self.assertTrue(result['tree_exit_confirmed'])
                self.assertFalse(result['msi_admission']['hold_retained'])
                self.assertEqual(1, leases)
                if pressure:
                    self.assertLess(result['minimum']['available_physical'], self.settings['running_free_floor_bytes'])
                    self.assertGreater(self.job.resource_calls, 3)
                else:
                    self.assertLess(result['minimum']['free_disk'], self.settings['disk_free_reserve_bytes'])

    def test_unclosed_root_retains_both_host_registration_and_existing_reconciliation(self):
        self.job.launch_error, self.job.never_stops = 'partial', True
        code, result, _, _ = self.run_fake()
        self.assertEqual(1, code)
        self.assertFalse(result['tree_exit_confirmed'])
        self.assertTrue(result['reconciliation_required'])
        self.assertTrue(Path(result['reconciliation_marker']).exists())
        self.assertTrue(result['msi_admission']['hold_retained'])
        self.assertTrue(self.host.tokens)

    def test_initia_default_path_needs_no_shared_helper_or_custody_and_keeps_schema_one(self):
        self.settings = policy_api.select(self.policy, 'initia', 'focused_test')
        self.job = FencedJob(self.settings, None, self.events)
        self.job.custody = None
        with mock.patch.object(policy_api, '_msi_shared_module', side_effect=AssertionError('No Shared on Initia')), \
                mock.patch.object(runner, 'WindowsJob', return_value=self.job) as original:
            code, result, _, leases = self.run_fake(host_factory=policy_api.msi_host_control, use_default_job=True)
        self.assertEqual(0, code)
        original.assert_called_once_with()
        self.assertEqual(1, leases)
        self.assertNotIn('msi_admission', result)
        self.assertNotIn('owned_custody', result)
        # Historical consumers can keep reading the same schema-1 result fields.
        old_fields = {key: result[key] for key in ('schema_version', 'status', 'argv', 'exit_code',
            'worker_pid', 'root_exit_confirmed', 'tree_exit_confirmed', 'remaining_job_processes',
            'owned_usage', 'reconciliation_required', 'policy_sha256')}
        self.assertEqual(dict(schema_version=1, status='passed',
            argv=['synthetic-command', 'space value', '--literal'], exit_code=0,
            worker_pid=23456, root_exit_confirmed=True, tree_exit_confirmed=True,
            remaining_job_processes=0,
            owned_usage=dict(peak_job_commit_bytes=123, peak_process_commit_bytes=100, owned_cpu_seconds=0.5),
            reconciliation_required=False, policy_sha256=self.digest), old_fields)


if __name__ == '__main__':
    unittest.main()
