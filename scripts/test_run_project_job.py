"""Owned-root cleanup regressions using fakes; no Windows jobs or Beacon imports."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager, redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
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

    def run_fake(self, *, host_factory=None, use_default_job=False, custody_observer=None):
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
        if custody_observer is not None:
            kwargs['custody_observer'] = custody_observer
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

    def test_custody_observer_borrows_the_same_instance_after_custody_before_close(self):
        self.job.custody_result.update(total_processes=4, retained_identity_count=4)
        observed = []
        def observer(job, snapshot):
            self.events.append('diagnostic')
            self.assertIs(job, self.job)
            self.assertFalse(self.host.locked_now)
            self.assertNotIn('job-close', self.events)
            self.assertEqual(self.job.custody_result, snapshot)
            self.assertIsNot(self.job.custody_result, snapshot)
            observed.append((job.pid, dict(snapshot)))
        code, result, _, leases = self.run_fake(custody_observer=observer)
        self.assertEqual(0, code)
        self.assertEqual(1, leases)
        self.assertEqual(1, len(observed))
        self.assertEqual(4, result['owned_custody']['total_processes'])
        self.assertLess(self.events.index('custody'), self.events.index('diagnostic'))
        self.assertLess(self.events.index('diagnostic'), self.events.index('job-close'))
        self.assertLess(self.events.index('job-close'), self.events.index('host-complete'))
        self.assertLess(self.events.index('host-complete'), self.events.index('lease-exit'))

    def test_custody_observer_snapshot_mutation_cannot_normalize_the_raw_census(self):
        self.job.custody_result.update(total_processes=4, retained_identity_count=4)
        def observer(job, snapshot):
            snapshot.update(total_processes=2, retained_identity_count=2, complete=False)
        code, result, _, _ = self.run_fake(custody_observer=observer)
        self.assertEqual(0, code)
        self.assertEqual(4, self.job.custody_result['total_processes'])
        self.assertEqual(self.job.custody_result, result['owned_custody'])
        self.assertTrue(result['msi_admission']['closure_confirmed'])

    def test_observer_error_cancel_and_system_exit_never_skip_real_finalization(self):
        for failure in (RuntimeError, KeyboardInterrupt, SystemExit):
            with self.subTest(failure=failure.__name__):
                self.events = []
                self.host = FakeHost(self.events)
                self.job = FencedJob(self.settings, self.host, self.events)
                def observer(job, snapshot):
                    self.events.append('diagnostic-failed')
                    raise failure('synthetic diagnostic failure')
                code, result, _, leases = self.run_fake(custody_observer=observer)
                self.assertEqual(0, code)
                self.assertEqual('passed', result['status'])
                self.assertEqual(1, leases)
                self.assertFalse(self.host.tokens)
                self.assertFalse(result['msi_admission']['hold_retained'])
                self.assertEqual(1, self.events.count('job-close'))
                self.assertLess(self.events.index('diagnostic-failed'), self.events.index('job-close'))
                self.assertLess(self.events.index('job-close'), self.events.index('host-complete'))
                self.assertLess(self.events.index('host-complete'), self.events.index('lease-exit'))

    def test_missing_custody_reaches_observer_as_unavailable_and_keeps_the_host_hold(self):
        self.job.custody_error = True
        observed = []
        code, result, _, _ = self.run_fake(custody_observer=lambda job, snapshot: observed.append(snapshot))
        self.assertEqual(0, code)
        self.assertEqual([None], observed)
        self.assertIn('custody_observation_error', result)
        self.assertTrue(result['msi_admission']['hold_retained'])
        self.assertIn('job-close', self.events)
        self.assertNotIn('host-complete', self.events)

    def test_initia_path_does_not_activate_the_msi_custody_observer(self):
        self.settings = policy_api.select(self.policy, 'initia', 'focused_test')
        self.job = FencedJob(self.settings, None, self.events)
        observer = mock.Mock()
        code, result, _, _ = self.run_fake(host_factory=lambda *_: None, custody_observer=observer)
        self.assertEqual(0, code)
        observer.assert_not_called()
        self.assertNotIn('owned_custody', result)

    def test_complete_larger_census_is_preserved_without_topology_normalization(self):
        # Ordinary jobs may own more than the separate two-process qualification fixture.
        for lifetime in (4, 12):
            with self.subTest(lifetime=lifetime):
                self.events = []
                self.host = FakeHost(self.events)
                self.job = FencedJob(self.settings, self.host, self.events)
                self.job.custody_result.update(total_processes=lifetime,
                                              retained_identity_count=lifetime)
                expected = deepcopy(self.job.custody_result)
                code, result, _, leases = self.run_fake()
                self.assertEqual(0, code)
                self.assertEqual('passed', result['status'])
                self.assertEqual(expected, result['owned_custody'])
                self.assertEqual(lifetime, result['owned_custody']['total_processes'])
                self.assertEqual(lifetime, result['owned_custody']['retained_identity_count'])
                self.assertTrue(result['msi_admission']['custody_complete'])
                self.assertTrue(result['msi_admission']['closure_confirmed'])
                self.assertFalse(result['msi_admission']['hold_retained'])
                self.assertFalse(self.host.tokens)
                self.assertEqual(1, leases)
                self.assertEqual(1, self.events.count('launch'))
                self.assertLess(self.events.index('custody'), self.events.index('job-close'))
                self.assertLess(self.events.index('job-close'), self.events.index('host-complete'))
                self.assertLess(self.events.index('host-complete'), self.events.index('lease-exit'))

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


class QueueCLITests(unittest.TestCase):
    # Reuse the existing fixture without inheriting (and rerunning) its tests.
    setUp = MSIFenceRunnerTests.setUp

    def cli(self, *, queued=True, queue_identity='b' * 64, lease_error=None,
            receipt_change=None, setup_error=None, before_run=None):
        self.attempt += 1
        prefix = self.root / str(self.attempt) / 'cli'
        report = Path(str(prefix) + '-result.json')
        clock, output = FakeClock(), io.StringIO()
        @contextmanager
        def lease(policy, settings):
            self.assertIs(policy, self.policy)
            self.assertEqual(self.settings, settings)
            self.events.append('lease-enter')
            try:
                yield
            finally:
                self.events.append('lease-exit')
                if receipt_change is not None:
                    receipt_change(report)
                if lease_error is not None:
                    raise lease_error
        def create_job():
            self.events.append('job-create')
            return self.job
        native = mock.Mock(WindowsJob=create_job)
        arguments = ['--host', self.settings['host'], '--profile', self.settings['workload'],
                     '--required-disk-bytes', '0', '--project-total-bytes', '0',
                     '--report-prefix', str(prefix), '--',
                     'synthetic-command', 'space value', '--literal']
        if before_run is not None:
            before_run(prefix)
        with mock.patch.dict(runner.os.environ, {'CODEX_QUEUE_JOB_ID': queue_identity}), \
                mock.patch.object(policy_api, 'load_policy', return_value=(self.policy, self.digest),
                                  side_effect=setup_error), \
                mock.patch.object(policy_api, 'detect_host', return_value=self.settings['host']), \
                mock.patch.object(policy_api, 'msi_host_control', return_value=self.job.host), \
                mock.patch.object(policy_api, 'msi_native_job', return_value=native), \
                mock.patch.object(runner, 'WindowsJob', side_effect=create_job), \
                mock.patch.object(policy_api, 'heavy_lease', side_effect=lease) as leases, \
                mock.patch.object(runner.time, 'monotonic', clock.monotonic), \
                mock.patch.object(runner.time, 'sleep', lambda _: None), redirect_stdout(output):
            if not queued:
                del runner.os.environ['CODEX_QUEUE_JOB_ID']
            code = runner.main(arguments)
        try:
            result = json.loads(report.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            result = None
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        return code, result, records, prefix, leases.call_count

    def test_queue_payload75_is_terminal_and_keeps_raw_receipt_and_stdout(self):
        self.job.code = 75
        code, result, records, prefix, leases = self.cli()
        self.assertEqual(1, code)
        self.assertEqual(75, result['exit_code'])
        self.assertEqual(75, result['root_exit_code'])
        self.assertEqual('failed', result['status'])
        self.assertFalse(result['msi_admission']['hold_retained'])
        self.assertEqual(1, leases)
        self.assertEqual(dict(status='failed', exit_code=75, report=str(prefix) + '-result.json'), records[0])
        self.assertEqual('queue_disposition', records[1]['record_type'])
        self.assertEqual(75, records[1]['raw_source_exit'])
        self.assertEqual(1, records[1]['queue_return_code'])
        self.assertTrue(records[1]['creation_attempted'])

    def test_absent_queue_identity_preserves_direct_payload75_stdout_and_schema(self):
        self.job.code = 75
        code, result, records, prefix, _ = self.cli(queued=False)
        self.assertEqual(75, code)
        self.assertEqual(1, result['schema_version'])
        self.assertEqual(75, result['exit_code'])
        self.assertEqual(75, result['root_exit_code'])
        self.assertEqual([dict(status='failed', exit_code=75,
                              report=str(prefix) + '-result.json')], records)
        self.assertNotIn('queue_return_code', result)
        self.assertNotIn('creation_attempted', result)

    def fresh_job(self, host='msi', deny_at=None):
        self.settings = policy_api.select(self.policy, host, 'focused_test')
        self.events = []
        self.host = FakeHost(self.events, deny_at=deny_at)
        self.job = FencedJob(self.settings, self.host if host == 'msi' else None, self.events)

    def test_queue_safe_prelaunch_refusals_preserve75_without_creating_a_payload(self):
        for refusal in ('early-host', 'final-host', 'resources'):
            with self.subTest(refusal=refusal):
                self.fresh_job(deny_at={'early-host': 1, 'final-host': 2}.get(refusal))
                if refusal == 'resources':
                    values = self.job.resources(self.root)
                    values['available_physical'] -= 1
                    with mock.patch.object(self.job, 'resources', return_value=values):
                        code, result, records, _, leases = self.cli()
                else:
                    code, result, records, _, leases = self.cli()
                self.assertEqual(75, code)
                self.assertEqual(75, result['exit_code'])
                self.assertEqual('deferred', result['status'])
                self.assertNotIn('launch', self.events)
                self.assertFalse(self.host.tokens)
                self.assertEqual(0 if refusal == 'early-host' else 1, leases)
                self.assertFalse(records[-1]['creation_attempted'])
                self.assertEqual('proven_nonlaunching_deferral', records[-1]['reason'])

    def test_queue_running_memory_and_disk75_are_terminal_without_relabeling_raw_stops(self):
        for pressure in (True, False):
            with self.subTest(pressure=pressure):
                self.fresh_job()
                self.job.live_polls = 100
                self.job.pressure, self.job.low_disk = pressure, not pressure
                code, result, records, _, leases = self.cli()
                self.assertEqual(1, code)
                self.assertEqual(75, result['exit_code'])
                self.assertEqual('deferred', result['status'])
                self.assertIn('memory pressure' if pressure else 'free-disk reserve', result['reason'])
                self.assertEqual(1, result['root_exit_code'])
                self.assertTrue(self.job.stopped)
                self.assertTrue(result['tree_exit_confirmed'])
                self.assertFalse(result['reconciliation_required'])
                self.assertFalse(result['msi_admission']['hold_retained'])
                self.assertEqual(1, leases)
                self.assertEqual(75, records[0]['exit_code'])
                self.assertEqual(75, records[-1]['raw_source_exit'])
                self.assertEqual(1, records[-1]['queue_return_code'])
                if pressure:
                    self.assertGreater(self.job.resource_calls, 3)
                    self.assertLess(result['minimum']['available_physical'], self.settings['running_free_floor_bytes'])
                else:
                    self.assertLess(result['minimum']['free_disk'], self.settings['disk_free_reserve_bytes'])

    def test_both_launch_paths_latch_before_partial_or_unknown_creation_can_raise75(self):
        for host in ('msi', 'initia'):
            for creation in ('partial', 'unknown'):
                with self.subTest(host=host, creation=creation):
                    self.fresh_job(host)
                    launch = self.job.launch
                    def denied_after_attempt(*arguments):
                        launch(*arguments)
                        if creation == 'unknown':
                            self.job.process = None
                        raise policy_api.AdmissionDeferred('fake creation outcome remains uncertain')
                    with mock.patch.object(self.job, 'launch', side_effect=denied_after_attempt):
                        code, result, records, _, leases = self.cli()
                    self.assertEqual(1, code)
                    self.assertEqual(75, result['exit_code'])
                    self.assertEqual('deferred', result['status'])
                    self.assertTrue(records[-1]['creation_attempted'])
                    self.assertEqual(1, leases)
                    self.assertEqual(creation == 'partial', self.job.stopped)
                    if host == 'msi':
                        self.assertTrue(result['msi_admission']['hold_retained'])
                        self.assertTrue(self.host.tokens)
                        self.assertNotIn('host-complete', self.events)

    def test_queue_observer_failure_is_uncertainty_and_cannot_authorize_replay(self):
        real_run = runner.run
        def failing_observer(*arguments, **keywords):
            observe = keywords['attempt_observer']
            def failed(event):
                observe(event)
                if event == 'creation':
                    raise policy_api.AdmissionDeferred('fake observer failure')
            keywords['attempt_observer'] = failed
            return real_run(*arguments, **keywords)
        with mock.patch.object(runner, 'run', side_effect=failing_observer):
            code, result, records, _, _ = self.cli()
        self.assertEqual(1, code)
        self.assertEqual(75, result['exit_code'])
        self.assertIn('observer failure', result['reason'])
        self.assertNotIn('launch', self.events)
        self.assertTrue(records[-1]['creation_attempted'])
        self.assertTrue(result['msi_admission']['hold_retained'])
        self.assertTrue(self.host.tokens)

    def test_unknown_registration_side_effects_cannot_look_like_a_safe_nonlaunch75(self):
        register = self.host.register_locked
        def unknown_registration(*arguments):
            register(*arguments)
            raise policy_api.AdmissionDeferred('fake registration publication is uncertain')
        with mock.patch.object(self.host, 'register_locked', side_effect=unknown_registration):
            code, result, records, _, leases = self.cli()
        self.assertEqual(1, code)
        self.assertEqual(75, result['exit_code'])
        self.assertNotIn('msi_admission', result)  # No token was returned to run().
        self.assertNotIn('launch', self.events)
        self.assertTrue(self.host.tokens)  # Failure of token return did not clear the hold.
        self.assertFalse(records[-1]['creation_attempted'])
        self.assertEqual('ownership_registration_attempted', records[-1]['reason'])
        self.assertEqual(1, leases)

    def test_queue_normal_zero_and_one_preserve_raw_outcomes_and_one_lease(self):
        for expected in (0, 1):
            with self.subTest(expected=expected):
                self.fresh_job()
                self.job.code = expected
                code, result, records, _, leases = self.cli()
                self.assertEqual(expected, code)
                self.assertEqual(expected, result['exit_code'])
                self.assertEqual(expected, records[-1]['raw_source_exit'])
                self.assertEqual(expected, records[-1]['queue_return_code'])
                self.assertFalse(result['msi_admission']['hold_retained'])
                self.assertEqual(1, leases)

    def test_queue_custody_close_and_completion_uncertainty_preserve_holds(self):
        for failure, field in (('custody_error', 'custody_observation_error'),
                               ('telemetry_error', 'usage_observation_error'),
                               ('active_error', 'ownership_observation_error'),
                               ('close_error', 'cleanup_error'),
                               ('completion', 'host_completion_error')):
            with self.subTest(failure=failure):
                self.fresh_job()
                self.job.code = 75
                if failure == 'completion':
                    with mock.patch.object(self.host, 'complete', side_effect=OSError('fake completion failure')):
                        code, result, records, _, _ = self.cli()
                else:
                    setattr(self.job, failure, True)
                    code, result, records, _, _ = self.cli()
                self.assertEqual(1, code)
                self.assertIn(field, result)
                self.assertTrue(result['msi_admission']['hold_retained'])
                self.assertTrue(self.host.tokens)
                self.assertEqual(result['exit_code'], records[-1]['raw_source_exit'])
                self.assertEqual(1, records[-1]['queue_return_code'])

    def test_queue_success_with_incomplete_custody_keeps_its_existing_unqualified_hold(self):
        self.job.custody_result['complete'] = False
        code, result, records, _, _ = self.cli()
        self.assertEqual(0, code)
        self.assertEqual(0, result['exit_code'])
        self.assertTrue(result['msi_admission']['hold_retained'])
        self.assertTrue(self.host.tokens)
        self.assertNotIn('host-complete', self.events)
        self.assertEqual(0, records[-1]['queue_return_code'])
        self.assertNotIn('closure_confirmed', records[-1])

    def test_postlaunch_lease_exit_admission_deferral_never_leaks75(self):
        for raw in (0, 75):
            with self.subTest(raw=raw):
                self.fresh_job()
                self.job.code = raw
                code, result, records, _, leases = self.cli(
                    lease_error=policy_api.AdmissionDeferred('fake lease exit failure'))
                self.assertEqual(1, code)
                self.assertEqual(raw, result['exit_code'])
                self.assertEqual(raw, result['root_exit_code'])
                self.assertIsNone(records[-1]['raw_source_exit'])  # run() did not return.
                self.assertEqual(1, records[-1]['queue_return_code'])
                self.assertIn('run_did_not_return: AdmissionDeferred', records[-1]['reason'])
                self.assertTrue(records[-1]['creation_attempted'])
                self.assertEqual(1, leases)

    def test_prelaunch_deferred_receipt_cannot_hide_a_lease_exit_failure(self):
        self.host.deny_at = 2
        code, result, records, _, _ = self.cli(
            lease_error=policy_api.AdmissionDeferred('fake nonlaunch finalization failure'))
        self.assertEqual(1, code)
        self.assertEqual(75, result['exit_code'])
        self.assertEqual('deferred', result['status'])
        self.assertNotIn('launch', self.events)
        self.assertFalse(records[-1]['creation_attempted'])
        self.assertIsNone(records[-1]['raw_source_exit'])
        self.assertIn('run_did_not_return', records[-1]['reason'])

    def test_postlaunch_policy_deferral_during_receipt_write_never_leaks75(self):
        real_dump = runner.json.dump
        def fail_report(value, stream, **keywords):
            if stream.name.endswith('-result.json'):
                raise policy_api.PolicyError('fake report finalization failure')
            return real_dump(value, stream, **keywords)
        with mock.patch.object(runner.json, 'dump', side_effect=fail_report):
            code, result, records, _, _ = self.cli()
        self.assertEqual(1, code)
        self.assertIsNone(result)
        self.assertIsNone(records[-1]['raw_source_exit'])
        self.assertIn('run_did_not_return: PolicyError', records[-1]['reason'])
        self.assertTrue(records[-1]['creation_attempted'])

    def test_queue_rejects_missing_malformed_and_unreadable_same_attempt_receipts(self):
        for corruption in ('missing', 'malformed', 'unreadable'):
            with self.subTest(corruption=corruption):
                self.fresh_job(deny_at=2)
                def change(report):
                    if corruption == 'malformed':
                        report.write_text('{broken', encoding='utf-8')
                    else:
                        report.unlink()
                        if corruption == 'unreadable':
                            report.mkdir()  # read_text deterministically refuses a directory.
                code, _, records, _, _ = self.cli(receipt_change=change)
                self.assertEqual(1, code)
                self.assertEqual(75, records[0]['exit_code'])
                self.assertEqual(75, records[-1]['raw_source_exit'])
                self.assertIn('invalid_final_receipt', records[-1]['reason'])
                self.assertNotIn('launch', self.events)

    def test_queue_rejects_mismatched_incomplete_stale_and_uncertain_deferred_receipts(self):
        variants = [dict(argv=['another-command']), dict(policy_sha256='c' * 64),
                    dict(host='initia'), dict(workload='light'), dict(project='other'),
                    dict(schema_version=2), dict(exit_code=0), dict(status='failed'),
                    dict(started_utc='2000-01-01T00:00:00+00:00'),
                    dict(completed_utc=None), dict(seconds=-1), dict(seconds=float('nan')),
                    dict(reconciliation_required=True), dict(worker_pid=23456),
                    dict(ownership_observation_error='unknown'),
                    dict(msi_admission=dict(hold_retained=True, closure_confirmed=False)),
                    {'remove': 'completed_utc'}, {'remove': 'reconciliation_required'}]
        for variant in variants:
            with self.subTest(variant=variant):
                self.fresh_job(deny_at=2)
                def change(report):
                    value = json.loads(report.read_text(encoding='utf-8'))
                    if 'remove' in variant:
                        del value[variant['remove']]
                    else:
                        value.update(variant)
                    report.write_text(json.dumps(value), encoding='utf-8')
                code, _, records, _, _ = self.cli(receipt_change=change)
                self.assertEqual(1, code)
                self.assertEqual(75, records[-1]['raw_source_exit'])
                self.assertIn('invalid_final_receipt', records[-1]['reason'])
                self.assertNotIn('launch', self.events)

    def test_queue_rejects_reused_prefix_without_overwriting_old_receipt_or_log(self):
        for suffix in ('-result.json', '.log'):
            with self.subTest(suffix=suffix):
                self.fresh_job()
                def retain(prefix):
                    prefix.parent.mkdir(parents=True)
                    Path(str(prefix) + suffix).write_bytes(b'old evidence must stay')
                code, _, records, prefix, leases = self.cli(before_run=retain)
                self.assertEqual(1, code)
                self.assertEqual(b'old evidence must stay', Path(str(prefix) + suffix).read_bytes())
                self.assertEqual(0, leases)
                self.assertNotIn('job-create', self.events)
                self.assertNotIn('launch', self.events)
                self.assertIsNone(records[-1]['raw_source_exit'])

    def test_queue_invalid_present_identity_refuses_before_setup_lease_or_creation(self):
        for identity in ('', 'not-a-hash', 'B' * 64, 'b' * 63, 'b' * 65, ' b' * 32):
            with self.subTest(identity=identity):
                self.fresh_job()
                code, result, records, _, leases = self.cli(queue_identity=identity,
                    setup_error=AssertionError('Invalid context must fail before policy setup'))
                self.assertEqual(1, code)
                self.assertIsNone(result)
                self.assertEqual(0, leases)
                self.assertNotIn('job-create', self.events)
                self.assertNotIn('launch', self.events)
                self.assertEqual('invalid_queue_identity', records[-1]['reason'])

    def test_initial_setup_refusal_is_nonlaunching75_with_direct_stdout_preserved(self):
        expected = dict(status='deferred', reason='fake policy unavailable', independent_development='continue')
        for failure in (policy_api.PolicyError, policy_api.AdmissionDeferred):
            for queued in (False, True):
                with self.subTest(queued=queued, failure=failure.__name__):
                    code, result, records, _, leases = self.cli(queued=queued,
                        setup_error=failure('fake policy unavailable'))
                    self.assertEqual(75, code)
                    self.assertIsNone(result)
                    self.assertEqual(expected, records[0])
                    self.assertEqual(2 if queued else 1, len(records))
                    self.assertEqual(0, leases)
                    self.assertNotIn('launch', self.events)
                    if queued:
                        self.assertEqual('initial_setup_refusal', records[-1]['reason'])
                        self.assertFalse(records[-1]['creation_attempted'])

    def test_absent_queue_identity_preserves_direct_running_resource75_and_stdout(self):
        self.job.low_disk, self.job.live_polls = True, 100
        code, result, records, prefix, _ = self.cli(queued=False)
        self.assertEqual(75, code)
        self.assertEqual(75, result['exit_code'])
        self.assertEqual('deferred', result['status'])
        self.assertIn('free-disk reserve', result['reason'])
        self.assertEqual([dict(status='deferred', exit_code=75,
                              report=str(prefix) + '-result.json')], records)
        self.assertNotIn('creation_attempted', result)

    def test_two_poll_worker_contract_replayed_old75_but_never_replays_started_queue_failure(self):
        # Maintained worker contract: 75 -> queued, 0 -> passed, others -> failed.
        # This intentionally models only that documented mapping, not private worker code.
        for outcome in ('payload75', 'disk-stop'):
            for queued in (False, True):
                with self.subTest(outcome=outcome, queued=queued):
                    state, invocations, payloads = 'queued', 0, []
                    for _poll in range(2):
                        if state != 'queued':
                            continue
                        self.fresh_job()
                        self.job.code = 75
                        if outcome == 'disk-stop':
                            self.job.low_disk, self.job.live_polls = True, 100
                        launch = self.job.launch
                        def counted_launch(*arguments):
                            payloads.append('same-selected-payload')
                            return launch(*arguments)
                        with mock.patch.object(self.job, 'launch', side_effect=counted_launch):
                            code, result, _, _, _ = self.cli(queued=queued)
                        invocations += 1
                        self.assertEqual(75, result['exit_code'])
                        state = 'queued' if code == 75 else 'passed' if code == 0 else 'failed'
                    self.assertEqual(1 if queued else 2, invocations)
                    self.assertEqual(['same-selected-payload'] * (1 if queued else 2), payloads)
                    self.assertEqual('failed' if queued else 'queued', state)

    def test_two_poll_safe_nonlaunch_deferral_can_make_its_first_launch_after_recovery(self):
        state, payloads, outcomes = 'queued', [], []
        for poll in range(2):
            self.assertEqual('queued', state)
            self.fresh_job(deny_at=1 if poll == 0 else None)
            launch = self.job.launch
            def counted_launch(*arguments):
                payloads.append('first-payload')
                return launch(*arguments)
            with mock.patch.object(self.job, 'launch', side_effect=counted_launch):
                code, _, _, _, _ = self.cli()
            outcomes.append(code)
            state = 'queued' if code == 75 else 'passed' if code == 0 else 'failed'
            self.assertEqual([] if poll == 0 else ['first-payload'], payloads)
        self.assertEqual([75, 0], outcomes)
        self.assertEqual('passed', state)




class CustodyCaptureTests(unittest.TestCase):
    """Synthetic borrowed Win32 queries, never a native process or cause reproduction."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'private-capture.json'

    def fixture(self, count=4, failed=()):
        root_handle, job_handle = 2**40 + 101, 2**40 + 700
        records = {}
        handles = {}
        for index in range(count):
            handle, pid = root_handle + index, 10 * (index + 1)
            records[handle] = dict(pid=pid, creation=8000 + pid, exit=9000 + pid,
                signal=0, exit_code=0, member=True,
                image=r'C:\synthetic\python.exe' if index < 2 else
                      r'C:\private-fixture-directory\helper-' + str(index) + '.exe')
            if index:
                handles[pid] = handle
        calls = []
        kernel = SimpleNamespace()
        def install(name, action):
            def invoke(*args):
                self.assertTrue(hasattr(invoke, 'argtypes'), name + ' must be declared before use')
                self.assertTrue(hasattr(invoke, 'restype'), name + ' must declare its return type')
                calls.append((name, args[0]))
                if name in failed:
                    return 0xffffffff if name == 'WaitForSingleObject' else 0
                return action(*args)
            setattr(kernel, name, invoke)
        def times(handle, creation, exit_time, kernel_time, user_time):
            creation._obj.dwLowDateTime = records[handle]['creation']
            creation._obj.dwHighDateTime = 1
            exit_time._obj.dwLowDateTime = records[handle]['exit']
            exit_time._obj.dwHighDateTime = 1
            return 1
        def membership(handle, exact_job, output):
            self.assertEqual(job_handle, exact_job)
            output._obj.value = records[handle]['member']
            return 1
        def image(handle, flags, buffer, size):
            self.assertEqual(0, flags)
            self.assertEqual(32768, size._obj.value)
            buffer.value = records[handle]['image']
            size._obj.value = len(buffer.value)
            return 1
        def exit_code(handle, output):
            output._obj.value = records[handle]['exit_code']
            return 1
        install('GetProcessId', lambda handle: records[handle]['pid'])
        install('WaitForSingleObject', lambda handle, timeout: records[handle]['signal'])
        install('GetExitCodeProcess', exit_code)
        install('GetProcessTimes', times)
        install('IsProcessInJob', membership)
        install('QueryFullProcessImageNameW', image)
        job = SimpleNamespace(process=root_handle, pid=10, handle=job_handle,
                              assigned=True, descendant_handles=handles, kernel=kernel)
        custody = dict(total_processes=count, retained_identity_count=count,
            all_identities_accounted=True, all_retained_descendants_exited=True, complete=True)
        return job, custody, records, calls

    def capture(self, job, custody, **kwargs):
        observer = runner._CustodyCapture(self.path, r'C:\synthetic\python.exe',
                                         clock=kwargs.pop('clock', lambda: 0), **kwargs)
        observer(job, custody)
        return observer, json.loads(self.path.read_bytes()) if self.path.exists() else None

    def test_four_borrowed_slots_are_joined_without_changing_counts_or_exposing_handles(self):
        job, custody, records, calls = self.fixture()
        before = dict(job.descendant_handles)
        observer, report = self.capture(job, custody)
        self.assertTrue(observer.complete)
        self.assertTrue(report['complete'])
        self.assertEqual(custody, report['raw_custody'])
        self.assertEqual(4, report['observed_slots'])
        self.assertEqual(['root', 'retained', 'retained', 'retained'],
                         [row['origin'] for row in report['rows']])
        self.assertEqual([10, 20, 30, 40], [row['handle_pid'] for row in report['rows']])
        self.assertTrue(all(row['creation_filetime'] > 2**32 for row in report['rows']))
        self.assertTrue(all(row['ancestry'] == 'unavailable' for row in report['rows']))
        self.assertEqual(before, job.descendant_handles)
        encoded = self.path.read_text(encoding='utf-8')
        self.assertNotIn('private-fixture-directory', encoded)
        self.assertNotIn(str(job.process), encoded)
        self.assertNotIn(str(job.handle), encoded)
        self.assertNotIn('unexpected-secret', encoded)
        self.assertEqual({'GetProcessId', 'WaitForSingleObject', 'GetExitCodeProcess',
                          'GetProcessTimes', 'IsProcessInJob', 'QueryFullProcessImageNameW'},
                         {name for name, _ in calls})

    def test_pointer_sized_handles_and_all_metadata_api_declarations_are_bound(self):
        job, custody, _, calls = self.fixture()
        observer, _ = self.capture(job, custody)
        self.assertTrue(observer.complete)
        w, pointer = runner.wintypes, runner.ctypes.POINTER
        expected = {
            'GetProcessId': ((w.HANDLE,), w.DWORD),
            'GetProcessTimes': ((w.HANDLE, pointer(w.FILETIME), pointer(w.FILETIME),
                                pointer(w.FILETIME), pointer(w.FILETIME)), w.BOOL),
            'IsProcessInJob': ((w.HANDLE, w.HANDLE, pointer(w.BOOL)), w.BOOL),
            'WaitForSingleObject': ((w.HANDLE, w.DWORD), w.DWORD),
            'GetExitCodeProcess': ((w.HANDLE, pointer(w.DWORD)), w.BOOL),
            'QueryFullProcessImageNameW': ((w.HANDLE, w.DWORD, w.LPWSTR, pointer(w.DWORD)), w.BOOL),
        }
        for name, (arguments, result) in expected.items():
            self.assertEqual(arguments, getattr(job.kernel, name).argtypes)
            self.assertIs(result, getattr(job.kernel, name).restype)
        self.assertTrue(all(handle > 2**32 for _, handle in calls))
        self.assertEqual(4, runner.ctypes.sizeof(w.DWORD))
        self.assertEqual(4, runner.ctypes.sizeof(w.BOOL))
        self.assertEqual(8, runner.ctypes.sizeof(w.FILETIME))
        self.assertEqual(runner.ctypes.sizeof(runner.ctypes.c_void_p),
                         runner.ctypes.sizeof(w.HANDLE))

    def test_each_query_failure_is_explicit_and_cannot_become_complete(self):
        for api in ('GetProcessId', 'WaitForSingleObject', 'GetExitCodeProcess',
                    'GetProcessTimes', 'IsProcessInJob', 'QueryFullProcessImageNameW'):
            with self.subTest(api=api):
                self.path = self.path.with_name(api + '.json')
                job, custody, _, _ = self.fixture(failed=(api,))
                with mock.patch.object(runner.ctypes, 'get_last_error', return_value=5):
                    observer, report = self.capture(job, custody)
                self.assertFalse(observer.complete)
                self.assertFalse(report['complete'])
                self.assertTrue(any(query['api'] == api and query['error'] == 5
                    for row in report['rows'] for query in row['queries']))
                self.assertEqual(4, custody['total_processes'])

    def test_active_exit_is_not_read_but_a_signalled_exit259_is_valid(self):
        job, custody, records, calls = self.fixture()
        records[job.process]['signal'] = 258
        observer, report = self.capture(job, custody)
        self.assertFalse(observer.complete)
        self.assertIsNone(report['rows'][0]['exit_code'])
        self.assertIsNone(report['rows'][0]['exit_filetime'])
        self.assertNotIn(('GetExitCodeProcess', job.process), calls)
        self.path = self.path.with_name('exit259.json')
        job, custody, records, _ = self.fixture()
        records[job.process]['exit_code'] = 259
        observer, report = self.capture(job, custody)
        self.assertTrue(observer.complete)
        self.assertEqual(259, report['rows'][0]['exit_code'])

    def test_mismatched_pid_nonmember_and_truncated_image_stay_incomplete(self):
        for field, value in (('pid', 999), ('member', False), ('image', 'x' * 261)):
            with self.subTest(field=field):
                self.path = self.path.with_name(field + '.json')
                job, custody, records, _ = self.fixture()
                records[job.process][field] = value
                observer, report = self.capture(job, custody)
                self.assertFalse(observer.complete)
                self.assertFalse(report['rows'][0]['complete'])
                if field == 'image':
                    self.assertTrue(report['rows'][0]['image_truncated'])

    def test_sixteen_slot_boundary_and_seventeen_slot_refusal(self):
        for count in (16, 17):
            with self.subTest(count=count):
                self.path = self.path.with_name(str(count) + '.json')
                job, custody, _, calls = self.fixture(count=count)
                observer, report = self.capture(job, custody)
                self.assertEqual(count == 16, observer.complete)
                self.assertEqual(count, report['raw_custody']['total_processes'])
                if count == 17:
                    self.assertFalse(calls)
                    self.assertEqual(0, report['observed_slots'])

    def test_query_budget_expiry_writes_only_incomplete_evidence(self):
        job, custody, _, calls = self.fixture()
        ticks = iter((0, 3, 3))
        observer, report = self.capture(job, custody, clock=lambda: next(ticks))
        self.assertFalse(observer.complete)
        self.assertEqual('TimeoutError', report['error'])
        self.assertFalse(calls)

    def test_query_exception_and_cancellation_preserve_incomplete_coverage(self):
        for failure in (OSError, KeyboardInterrupt, SystemExit):
            with self.subTest(failure=failure.__name__):
                self.path = self.path.with_name(failure.__name__ + '.json')
                job, custody, _, _ = self.fixture()
                def fail(*args):
                    error = failure('synthetic query failure')
                    if isinstance(error, OSError):
                        error.winerror = 5
                    raise error
                job.kernel.GetProcessId = fail
                observer, report = self.capture(job, custody)
                self.assertFalse(observer.complete)
                self.assertEqual(failure.__name__, report['error'])
                self.assertLess(report['observed_slots'], report['expected_slots'])
                query = report['rows'][0]['queries'][0]
                self.assertEqual('GetProcessId', query['api'])
                self.assertFalse(query['ok'])
                self.assertEqual('raised' if failure is OSError else 'interrupted', query['outcome'])
                self.assertEqual(failure.__name__, query['exception_type'])
                self.assertEqual(5 if failure is OSError else None, query['error'])
                self.assertNotIn('synthetic query failure', self.path.read_text(encoding='utf-8'))

    def test_missing_snapshot_or_invalid_owned_ledger_is_not_repaired_or_reopened(self):
        for mode in ('missing', 'duplicate_root', 'bad_handle'):
            with self.subTest(mode=mode):
                self.path = self.path.with_name(mode + '.json')
                job, custody, _, calls = self.fixture()
                if mode == 'missing':
                    custody = None
                elif mode == 'duplicate_root':
                    job.descendant_handles[job.pid] = 42
                else:
                    job.descendant_handles[20] = -1
                observer, report = self.capture(job, custody)
                self.assertFalse(observer.complete)
                self.assertFalse(calls)
                self.assertEqual(0, report['observed_slots'])

    def test_evidence_cap_and_existing_or_unwritable_output_never_claim_success(self):
        job, custody, _, _ = self.fixture()
        with mock.patch.object(runner._CustodyCapture, 'MAX_BYTES', 1):
            observer, report = self.capture(job, custody)
        self.assertFalse(observer.complete)
        self.assertIsNone(report)
        self.path.write_bytes(b'original')
        observer = runner._CustodyCapture(self.path, r'C:\synthetic\python.exe', clock=lambda: 0)
        observer(job, custody)
        self.assertFalse(observer.complete)
        self.assertEqual('FileExistsError', observer.error)
        self.assertEqual(b'original', self.path.read_bytes())
        self.path = self.path.with_name('unwritable.json')
        with mock.patch.object(Path, 'open', side_effect=PermissionError('synthetic write refusal')):
            observer = runner._CustodyCapture(self.path, r'C:\synthetic\python.exe', clock=lambda: 0)
            observer(job, custody)
        self.assertFalse(observer.complete)
        self.assertEqual('PermissionError', observer.error)


if __name__ == '__main__':
    unittest.main()
