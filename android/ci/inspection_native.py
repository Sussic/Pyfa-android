"""Collect actual offline inspector observations from an explicitly owned emulator.

This is a local phase collector. Collection alone never publishes delivery or
replaces full independent report validation and screenshot review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from evidence_paths import evidence_dir
from inspection_delivery import PHASES, STARTS, artifacts, arguments, selector, previous, methods
from inspection_instrumentation import TIMEOUT_SECONDS, validate as validate_runner
from inspection_canonical_summary import decode

PACKAGE = 'io.github.sussic.pyfa.dev'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for data in iter(lambda: source.read(64 * 1024), b''): digest.update(data)
    return digest.hexdigest()


class Collector:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.serial = os.environ['ANDROID_SERIAL']
        assert re.fullmatch(r'emulator-\d+', self.serial), 'Only an explicit emulator serial is allowed'
        assert os.environ['PYFA_EXECUTION_KIND'] == 'local_windows'
        self.run_id = os.environ['PYFA_LOCAL_RUN_ID']
        assert self.directory.name == 'native' and self.directory.parent.name == self.run_id

    def adb(self, *parts):
        return subprocess.check_output(['adb', '-s', self.serial, *parts], timeout=60)

    def device(self):
        expected = {'ro.kernel.qemu': '1', 'ro.build.version.sdk': '36'}
        for key, value in expected.items(): assert self.adb('shell', 'getprop', key).decode().strip() == value
        assert self.adb('emu', 'avd', 'name').decode().splitlines()[0] == 'pyfa-local-' + self.run_id
        assert self.adb('shell', 'settings', 'get', 'global', 'airplane_mode_on').strip() == b'1'
        return dict(serial=self.serial, avd='pyfa-local-' + self.run_id, api=36, qemu=True, airplane_mode=True)

    def stop(self):
        self.device()
        self.adb('shell', 'am', 'force-stop', PACKAGE)
        result = subprocess.run(['adb', '-s', self.serial, 'shell', 'pidof', PACKAGE], capture_output=True, timeout=60)
        assert result.returncode == 1 and not result.stdout.strip(), 'Target process did not stop'

    def pull(self, remote, destination):
        self.device()
        destination = Path(destination).resolve()
        assert destination.parent == self.directory
        assert remote in {path for phase in PHASES for path in artifacts(phase)}
        prefix = ('run-as', PACKAGE) if remote.startswith('files/') else ()
        def value(*command): return self.adb('shell', *prefix, *command).decode().strip()
        before = value('sha256sum', remote).split()[0]
        assert re.fullmatch(r'[0-9a-f]{64}', before)
        size = int(value('stat', '-c', '%s', remote)); assert size > 0
        with destination.open('wb') as output:
            subprocess.run(['adb', '-s', self.serial, 'exec-out', *prefix, 'cat', remote],
                           stdout=output, check=True, timeout=120)
        assert destination.stat().st_size == size and sha(destination) == before, 'Truncated or altered artifact pull'
        assert value('sha256sum', remote).split()[0] == before
        assert int(value('stat', '-c', '%s', remote)) == size
        return dict(remote=remote, file=destination.name, bytes=size, sha256=before,
                    device_before_after_verified=True)

    def collect(self, phase):
        assert phase in PHASES
        identity = self.device()
        prior = previous(phase)
        if prior is not None:
            receipt = decode((self.directory / f'inspection-{prior}-collection.json').read_bytes())
            self.retained(receipt, prior, identity)
        self.stop()
        if phase in STARTS:
            # Each independent fixture group starts from a synthetic empty store.
            # Earlier required observations already reside in retained local files.
            assert self.adb('shell', 'pm', 'clear', PACKAGE).strip() == b'Success'
        key, value = arguments(phase)
        log = self.directory / f'inspection-{phase}-instrumentation.txt'
        command = ['adb', '-s', self.serial, 'shell', 'am', 'instrument', '-w', '-r', '-e', 'class', selector(phase),
                   '-e', key, value, PACKAGE + '.test/io.github.sussic.pyfa.DiagnosticTestRunner']
        with log.open('wb') as output: subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True, timeout=TIMEOUT_SECONDS)
        text = log.read_text(encoding='utf-8')
        validate_runner(text, phase, selected=methods(phase))
        if phase == 'canonical':
            events = re.findall(r'^INSTRUMENTATION_STATUS: test=(\w+)\s*$', text, re.M)
            assert events[-2:] == ['canonicalAttributesCrossNativeWorkerOffline'] * 2
        pulled = [self.pull(remote, self.directory / f'inspection-{phase}-{Path(remote).name}') for remote in artifacts(phase)]
        receipt = dict(schema=1, phase=phase, device=identity, selector=selector(phase), timeout_seconds=TIMEOUT_SECONDS,
                       runner_log=log.name, runner_log_sha256=sha(log), artifacts=pulled,
                       worker_process_stopped_before_phase=True, independent_store_reset=phase in STARTS,
                       independent_validation=False, screenshot_review=False, full_delivery=False)
        (self.directory / f'inspection-{phase}-collection.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        print(f'PASS actual inspector collection:{phase}; independent validation/review still required')

    def retained(self, receipt, phase, identity):
        """Restarts require the complete, unaltered immediately preceding collection."""
        assert receipt['schema'] == 1 and receipt['phase'] == phase and receipt['device'] == identity
        assert receipt['selector'] == selector(phase) and receipt['timeout_seconds'] == TIMEOUT_SECONDS
        assert receipt['worker_process_stopped_before_phase'] is True
        assert receipt['independent_store_reset'] is (phase in STARTS)
        assert all(receipt[key] is False for key in ('independent_validation', 'screenshot_review', 'full_delivery'))
        assert receipt['runner_log'] == f'inspection-{phase}-instrumentation.txt'
        log = self.directory / receipt['runner_log']
        assert sha(log) == receipt['runner_log_sha256']
        validate_runner(log.read_text(encoding='utf-8'), phase, selected=methods(phase))
        assert [row['remote'] for row in receipt['artifacts']] == list(artifacts(phase))
        for artifact in receipt['artifacts']:
            assert set(artifact) == {'remote', 'file', 'bytes', 'sha256', 'device_before_after_verified'}
            assert artifact['file'] == f'inspection-{phase}-{Path(artifact["remote"]).name}'
            assert artifact['device_before_after_verified'] is True
            assert type(artifact['bytes']) is int and artifact['bytes'] > 0
            assert re.fullmatch(r'[0-9a-f]{64}', artifact['sha256'])
            path = (self.directory / artifact['file']).resolve()
            assert path.parent == self.directory
            assert path.stat().st_size == artifact['bytes'] and sha(path) == artifact['sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=PHASES)
    args = parser.parse_args()
    Collector(evidence_dir()).collect(args.phase)


if __name__ == '__main__': main()
