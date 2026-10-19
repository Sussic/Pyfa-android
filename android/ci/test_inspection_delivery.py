"""Collector safety/integrity guards, never substitutes for native execution."""
import hashlib
from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from android.ci.inspection_delivery import PHASES, STARTS, SCREENSHOTS, artifacts, previous, arguments
from android.ci.inspection_native import Collector
from android.ci.inspection_delivery import selector
from android.ci.test_inspection_instrumentation import output


class InspectorDeliveryTest(unittest.TestCase):
    def collector(self, root):
        directory = Path(root) / 'run' / 'native'; directory.mkdir(parents=True)
        with patch.dict('os.environ', ANDROID_SERIAL='emulator-5560', PYFA_EXECUTION_KIND='local_windows', PYFA_LOCAL_RUN_ID='run'):
            return Collector(directory)

    def test_every_required_phase_and_restart_remains_explicit(self):
        self.assertEqual(23, len(PHASES)); self.assertEqual(len(PHASES), len(set(PHASES)))
        from android.ci.inspection_delivery import methods
        self.assertEqual(33, sum(len(methods(phase)[1]) for phase in PHASES))
        self.assertEqual(19, len(SCREENSHOTS)); self.assertEqual(19, len(set(SCREENSHOTS)))
        for part in range(5):
            stem = f'contexts{part}'
            self.assertIn(stem, STARTS)
            self.assertEqual(stem, previous(stem + '-restored1'))
            self.assertEqual(stem + '-restored1', previous(stem + '-restored2'))
            self.assertEqual(('c032_phase', stem), arguments(stem))
            for phase in (stem, stem + '-restored1', stem + '-restored2'):
                self.assertEqual((f'files/c032-{stem}-state.json', f'files/c032-{stem}-observations.jsonl'), artifacts(phase))
        for group in ('canonical', 'identity'):
            start = group if group == 'canonical' else 'identity-prepare'
            self.assertEqual(start, previous(group + '-restored1'))
            self.assertEqual(group + '-restored1', previous(group + '-restored2'))
        self.assertEqual(('c032_identity_phase', 'restored2'), arguments('identity-restored2'))
        self.assertIn('observations.jsonl', artifacts('canonical-restored2')[1])

    def test_unowned_or_online_device_is_rejected_before_mutation(self):
        identity = {('shell', 'getprop', 'ro.kernel.qemu'): b'1',
                    ('shell', 'getprop', 'ro.build.version.sdk'): b'36',
                    ('emu', 'avd', 'name'): b'pyfa-local-run\nOK\n',
                    ('shell', 'settings', 'get', 'global', 'airplane_mode_on'): b'1'}
        for key, value in ((('shell', 'getprop', 'ro.kernel.qemu'), b'0'),
                           (('shell', 'getprop', 'ro.build.version.sdk'), b'35'),
                           (('emu', 'avd', 'name'), b'unrelated-avd\nOK\n'),
                           (('shell', 'settings', 'get', 'global', 'airplane_mode_on'), b'0')):
            with tempfile.TemporaryDirectory() as directory:
                collector = self.collector(directory); responses = dict(identity); responses[key] = value
                with patch.object(collector, 'adb', side_effect=lambda *parts: responses[parts]) as adb:
                    with self.assertRaises(AssertionError): collector.collect('canonical')
                    self.assertFalse(any('force-stop' in call.args or 'clear' in call.args for call in adb.call_args_list))
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', ANDROID_SERIAL='physical-phone', PYFA_EXECUTION_KIND='local_windows', PYFA_LOCAL_RUN_ID='run'):
            with self.assertRaises(AssertionError): Collector(Path(directory) / 'run' / 'native')

    def test_verified_stream_pull_rejects_empty_truncated_altered_and_changing_bytes(self):
        data = b'{"actual":"retained bytes"}\n'; digest = hashlib.sha256(data).hexdigest()
        for kind in ('valid', 'empty', 'truncated', 'altered', 'changing-hash', 'changing-size'):
            with tempfile.TemporaryDirectory() as directory:
                collector = self.collector(directory); counts = {'sha256sum': 0, 'stat': 0}
                def adb(*parts):
                    command = parts[3]
                    counts[command] += 1
                    if command == 'sha256sum':
                        value = '0' * 64 if kind == 'changing-hash' and counts[command] > 1 else digest
                        return (value + '  file\n').encode()
                    size = 0 if kind == 'empty' else len(data)
                    if kind == 'changing-size' and counts[command] > 1: size += 1
                    return str(size).encode()
                def run(command, **kwargs):
                    kwargs['stdout'].write(data[:-1] if kind == 'truncated' else b'x' * len(data) if kind == 'altered' else data)
                    return subprocess.CompletedProcess(command, 0)
                with patch.object(collector, 'device', return_value={}), patch.object(collector, 'adb', side_effect=adb), patch('android.ci.inspection_native.subprocess.run', side_effect=run):
                    target = collector.directory / 'retained.jsonl'
                    if kind == 'valid':
                        receipt = collector.pull('files/c032-canonical-observations.jsonl', target)
                        self.assertEqual(data, target.read_bytes()); self.assertTrue(receipt['device_before_after_verified'])
                    else:
                        with self.subTest(kind=kind), self.assertRaises(AssertionError): collector.pull('files/c032-canonical-observations.jsonl', target)

    def test_restart_rejects_missing_substituted_and_escaped_retained_artifacts(self):
        # Temporary guard inputs test receipt integrity only, never native proof.
        with tempfile.TemporaryDirectory() as directory:
            collector = self.collector(directory); phase = 'canonical'
            log = collector.directory / f'inspection-{phase}-instrumentation.txt'
            log.write_text(output(phase), encoding='utf-8')
            retained = []
            for remote in artifacts(phase):
                name = f'inspection-{phase}-{Path(remote).name}'
                (collector.directory / name).write_bytes(b'temporary guard bytes')
                retained.append(dict(remote=remote, file=name, bytes=21,
                                     sha256=hashlib.sha256(b'temporary guard bytes').hexdigest(),
                                     device_before_after_verified=True))
            receipt = dict(schema=1, phase=phase, device={}, selector=selector(phase), timeout_seconds=900,
                           runner_log=log.name, runner_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                           artifacts=retained, worker_process_stopped_before_phase=True, independent_store_reset=True,
                           independent_validation=False, screenshot_review=False, full_delivery=False)
            collector.retained(receipt, phase, {})
            for mutate in (lambda row: row['artifacts'].pop(), lambda row: row['artifacts'].reverse(),
                           lambda row: row['artifacts'][0].update(file='../outside.json'),
                           lambda row: row['artifacts'][0].update(bytes=20),
                           lambda row: row['artifacts'][0].update(sha256='0' * 64),
                           lambda row: row['artifacts'][0].update(device_before_after_verified=False),
                           lambda row: row.update(worker_process_stopped_before_phase=False),
                           lambda row: row.update(independent_store_reset=False),
                           lambda row: row.update(selector='unselectedMethod'),
                           lambda row: row.update(runner_log='../outside.txt'),
                           lambda row: row.update(runner_log_sha256='0' * 64),
                           lambda row: row.update(full_delivery=True)):
                bad = deepcopy(receipt); mutate(bad)
                with self.subTest(mutation=mutate), self.assertRaises(AssertionError): collector.retained(bad, phase, {})


if __name__ == '__main__': unittest.main()
