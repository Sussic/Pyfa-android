"""Owned-root cleanup regressions using fakes; no Windows jobs or Beacon imports."""
from __future__ import annotations

from copy import deepcopy
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


if __name__ == '__main__':
    unittest.main()
