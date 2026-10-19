#!/usr/bin/env python3
"""One owner-approved serial G05.1 candidate process, bounded to 180s / 1GiB."""
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
SUITES = ('ordinary', 'drones', 'spool', 'ancillary', 'linked')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('seed', 'reopen'))
    parser.add_argument('suite', choices=SUITES)
    parser.add_argument('label')
    parser.add_argument('--store', type=Path)
    args = parser.parse_args()
    assert args.label and Path(args.label).name == args.label
    oracle = ROOT/'preflight-evidence'/(args.suite+'-v2.json')
    original = json.loads(oracle.read_text())
    assert original['status'] == 'passed' and original['suite'] == args.suite
    approved = json.loads((ROOT/'preflight-evidence/verify-v2.json').read_text())
    assert approved['receipts']['../preflight-evidence/'+oracle.name] == sha(oracle)
    source = Path(original['source'])
    database = Path(os.environ['PYFA_DATABASE']).resolve()
    assert sha(database) == original['dataset_sha256']
    assert source == Path(os.environ['PYFA_REFERENCE_SOURCE']).resolve()
    for relative, expected in {**original['source_files'], **original['original_imports']}.items():
        assert sha(source/relative) == sha(REPO/relative) == expected, relative
    for relative, expected in {**original['harness_files'], **original['fixture_files']}.items():
        assert sha(REPO/relative) == expected, relative
    directory = ROOT/'comparison-evidence'/args.label
    directory.mkdir(parents=True, exist_ok=False)
    harness = sorted((REPO/'tools/android_reference/remote_repair_range').glob('*.py'))
    product = sorted((REPO/'android_bridge').rglob('*.py'))+[REPO/'android/app/src/main/python/mobile_runtime.py']
    engine = sorted((REPO/'eos').rglob('*.py'))+sorted((REPO/'utils').rglob('*.py'))+sorted((REPO/'graphs').rglob('*.py'))
    for path in harness: shutil.copy2(path, directory/path.name)
    store = (args.store or directory/'fits.sqlite').resolve()
    if args.phase == 'seed': assert not store.exists()
    else: assert args.store and store.exists() and Path(str(store)+'.checkpoint.json').exists()
    command = [sys.executable, '-B', str(Path(__file__).with_name('test_candidate.py')), '--execute',
               '--suite', args.suite, '--phase', args.phase, '--oracle', str(oracle),
               '--store', str(store), '--output', str(directory/'output.json')]
    binding = dict(command=command, phase=args.phase, suite=args.suite,
        harness={str(p.relative_to(REPO)):sha(p) for p in harness},
        production={str(p.relative_to(REPO)):sha(p) for p in product},
        engine={str(p.relative_to(REPO)):sha(p) for p in engine},
        source_files=original['source_files'], original_imports=original['original_imports'],
        oracle_path=str(oracle), oracle_sha256=sha(oracle), original_process_nonce=original['process_nonce'],
        dataset_path=str(database), dataset_sha256=sha(database), logical_dataset_sha256=os.environ['PYFA_DATASET_SHA'],
        source_path=str(source), source_qualification=original['source_kind'],
        store_path=str(store), initial_store_sha256=sha(store) if store.exists() else None,
        checkpoint_sha256=sha(Path(str(store)+'.checkpoint.json')) if args.phase == 'reopen' else None,
        limits=dict(external_timeout_seconds=180, address_space_bytes=1024**3))
    write(directory/'binding.json', binding)
    def bounded(): resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    started = time.monotonic(); code = 124
    with (directory/'process.log').open('wb') as log:
        try: code = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, timeout=180, preexec_fn=bounded).returncode
        except subprocess.TimeoutExpired: log.write(b'\nHARNESS TIMEOUT 180 seconds\n')
    unchanged = all(sha(REPO/path) == value for group in ('harness','production','engine') for path,value in binding[group].items())
    unchanged &= all(sha(source/path) == value for group in ('source_files','original_imports') for path,value in binding[group].items())
    unchanged &= sha(database) == binding['dataset_sha256'] and sha(oracle) == binding['oracle_sha256']
    result = dict(exit_code=code, elapsed_seconds=time.monotonic()-started, inputs_unchanged=bool(unchanged),
                  process_log_sha256=sha(directory/'process.log'), binding_sha256=sha(directory/'binding.json'), **binding['limits'])
    write(directory/'result.json', result)
    print((directory/'process.log').read_text()); print(json.dumps(result))
    raise SystemExit(code or (0 if unchanged else 3))


if __name__ == '__main__': main()
