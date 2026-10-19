#!/usr/bin/env python3
"""One serial bounded D02.2 candidate process; coordinator must grant EOS lane."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[3]
ROOT = REPO.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('candidate', 'reopen', 'legacy'))
    parser.add_argument('suite', choices=('repair', 'capacitor', 'nosferatu', 'reciprocal'))
    parser.add_argument('label'); parser.add_argument('--reverse', action='store_true')
    parser.add_argument('--store', type=Path)
    args = parser.parse_args()
    directory = ROOT/'remote-support-evidence'/args.label
    directory.mkdir(parents=True, exist_ok=False)
    assert sha(REPO/'android_bridge/contract.py') == '2694298327de1261ecb41e3ffe2c5640989e0efb59646d3b5b06f99e5a99657c'
    oracle = ROOT/'preflight-evidence'/(args.suite+('-reverse' if args.reverse else '')+'-measure-v4.json')
    assert oracle.is_file()
    original = json.loads(oracle.read_text())
    source = Path(original['source'])
    files = sorted((REPO/'tools/android_reference/remote_support').glob('*.py')) + sorted((REPO/'tools/android_reference/remote_support').glob('*.json'))
    files += [REPO/'tools/android_headless/check_remote_support_parity.py', REPO/'tools/android_reference/multisource/oracle.py', REPO/'tools/android_reference/reference.py']
    production = sorted((REPO/'android_bridge').rglob('*.py')) + [REPO/'android/app/src/main/python/mobile_runtime.py']
    candidate_engine = sorted((REPO/'eos').rglob('*.py')) + sorted((REPO/'utils').rglob('*.py')) + sorted((REPO/'graphs').rglob('*.py'))
    for relative, expected in original['original_imports'].items():
        assert sha(REPO/relative) == expected, ('candidate EOS differs from measured original', relative)
    for path in files: shutil.copy2(path, directory/path.name)
    database = Path(os.environ['PYFA_DATABASE'])
    assert sha(database) == original['dataset_sha256']
    for relative, expected in {**original['source_files'], **original['original_imports']}.items():
        assert sha(source/relative) == expected, relative
    for relative, expected in original['harness_files'].items():
        assert sha(REPO/relative) == expected, relative
    for relative, expected in original['fixture_files'].items():
        assert sha(REPO/'tools/android_reference/fixtures'/relative) == expected, relative
    store = (args.store or directory/'fits.sqlite').resolve()
    command = [sys.executable, '-B', str(REPO/'tools/android_headless/check_remote_support_parity.py'), '--suite', args.suite,
               '--phase', args.phase, '--oracle', str(oracle), '--store', str(store), '--output', str(directory/'output.json')]
    if args.reverse: command.append('--reverse')
    if args.phase == 'legacy':
        assert args.store and args.suite == 'repair' and args.reverse
        command = [sys.executable, '-B', str(REPO/'tools/android_reference/remote_support/check_legacy_reopen.py'),
                   '--oracle', str(oracle), '--store', str(store), '--output', str(directory/'output.json')]
    binding = dict(command=command, harness={str(path.relative_to(REPO)):sha(path) for path in files},
                   production={str(path.relative_to(REPO)):sha(path) for path in production},
                   candidate_engine={str(path.relative_to(REPO)):sha(path) for path in candidate_engine}, original_receipt_sha256=sha(oracle),
                   database_path=str(database), database_sha256=sha(database), logical_dataset_sha256=os.environ['PYFA_DATASET_SHA'],
                   source_files=original['source_files'], original_imports=original['original_imports'],
                   original_process_nonce=original['process_nonce'], qualification=original['source_kind'])
    write(directory/'binding.json', binding)
    def bounded():
        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    started = time.monotonic(); code = 124
    with (directory/'process.log').open('wb') as log:
        try:
            code = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, timeout=180, preexec_fn=bounded).returncode
        except subprocess.TimeoutExpired:
            log.write(b'\nHARNESS TIMEOUT 180 seconds\n')
    unchanged = all(sha(REPO/path) == expected for group in ('harness', 'production', 'candidate_engine') for path, expected in binding[group].items())
    unchanged = unchanged and all(sha(source/path) == expected for group in ('source_files', 'original_imports') for path, expected in binding[group].items())
    unchanged = unchanged and sha(database) == binding['database_sha256'] and sha(oracle) == binding['original_receipt_sha256']
    result = dict(exit_code=code, elapsed_seconds=time.monotonic()-started, bound_seconds=180, bound_address_space_bytes=1024**3,
                  inputs_unchanged=unchanged, process_log_sha256=sha(directory/'process.log'), binding_sha256=sha(directory/'binding.json'))
    write(directory/'result.json', result)
    print((directory/'process.log').read_text()); print(json.dumps(result))
    raise SystemExit(code or (0 if unchanged else 3))


if __name__ == '__main__':
    main()
