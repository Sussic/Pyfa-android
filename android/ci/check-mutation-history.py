"""Run one B09.2 native phase; completed phases are separate resumable gates."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from evidence_paths import evidence_dir
from mutation_history_summary import fixture_bytes, recent_case, state, summarize

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--group', type=int, choices=range(4), required=True)
parser.add_argument('--phase', choices=('prepare', 'restored'), required=True)
args = parser.parse_args()
evidence = evidence_dir()
package = 'io.github.sussic.pyfa.dev'
fixture, fixture_hash = fixture_bytes()
engine = json.loads((evidence / 'engine-native.json').read_text())
prior = json.loads((evidence / 'history-native.json').read_text())
prefix = [json.loads((evidence / f'mutation-history-{g}-{p}-native.json').read_text())
    for g in range(args.group) for p in ('prepare', 'restored')]
if args.phase == 'restored':
    prefix.append(json.loads((evidence / f'mutation-history-{args.group}-prepare-native.json').read_text()))


def adb(*command, timeout=30, binary=False):
    return subprocess.run(['adb', *command], capture_output=True, text=not binary, check=True, timeout=timeout).stdout


assert adb('shell', 'getprop', 'ro.kernel.qemu').strip() == '1'
assert adb('shell', 'settings', 'get', 'global', 'airplane_mode_on').strip() == '1'
tag = f'{args.group}-{args.phase}'
names = ([f'{args.group}-{name}' for name in ('undone', 'redone', 'recreated')] if args.phase == 'prepare'
    else [f'{args.group}-restored'])
if args.phase == 'prepare':
    names += {0: ['0-cargo-cleared'], 1: ['1-recent-redone'], 2: ['2-transfer-undone'], 3: ['3-stale', '3-deleted-source']}.get(args.group, [])
# Keep prior failed local artifacts before a retry. The installed runner retains
# its original nonzero gate log; this also retains its instrumentation/screens.
old = [p for p in [evidence / f'mutation-history-{tag}-instrumentation.txt',
    evidence / f'mutation-history-{tag}-native.json',
    *(evidence / f'mutation-history-{name}.png' for name in names),
    evidence / f'mutation-history-{args.group}-failure.png'] if p.exists()]
if old:
    archive = evidence / 'mutation-history-attempts' / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    archive.mkdir(parents=True)
    for path in old: shutil.copyfile(path, archive / path.name)
adb('shell', 'am', 'force-stop', package)
path = f'/sdcard/Download/pyfa-b092-{tag}.json'
adb('shell', 'rm', '-f', path)
for name in (*names, f'{args.group}-failure'):
    adb('shell', 'rm', '-f', f'/sdcard/Download/pyfa-b092-{name}.png')
try:
    output = adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class', 'io.github.sussic.pyfa.MutationHistoryTest',
        '-e', 'b092_group', str(args.group), '-e', 'b092_phase', args.phase,
        f'{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner', timeout=2400 if os.name == 'nt' else 900)
    (evidence / f'mutation-history-{tag}-instrumentation.txt').write_text(output, encoding='utf-8')
finally:
    (evidence / f'mutation-history-{tag}-logcat.txt').write_text(adb('logcat', '-d'), encoding='utf-8')
    for name in (*names, f'{args.group}-failure'):
        picture = f'/sdcard/Download/pyfa-b092-{name}.png'
        if subprocess.run(['adb', 'shell', 'test', '-f', picture], timeout=30).returncode == 0:
            png = adb('exec-out', 'cat', picture, binary=True); assert png.startswith(b'\x89PNG\r\n\x1a\n')
            (evidence / f'mutation-history-{name}.png').write_bytes(png)
assert re.search(r'OK \(1 test\)', output), output[-6000:]
assert 'INSTRUMENTATION_CODE: -1' in output and not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=', output)
report = json.loads(adb('exec-out', 'cat', path))
(evidence / f'mutation-history-{tag}-native.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
assert report['task'] == 'B09.2' and report['group'] == args.group and report['phase'] == args.phase
assert report['fixture_sha256'] == fixture_hash
assert report['pid'] not in {r['pid'] for r in prior + prefix}
for name in names: assert (evidence / f'mutation-history-{name}.png').is_file()
if args.phase == 'prepare':
    assert len(report['cases']) == 7
    for expected, observed in zip(fixture['cases'][args.group * 7:(args.group + 1) * 7], report['cases']):
        assert expected['name'] == observed['name'] and len(observed['steps']) == 6
        for step, actual in zip(expected['steps'], observed['steps']):
            assert step['action'] == actual['action']
            state(expected, step, actual['result'], observed['recent_before'])
    if args.group == 1: recent_case(fixture['interleaved_recent'], report['observations']['recent_case'])
else:
    summary = summarize(prefix + [report], engine, prior, complete=args.group == 3)
    (evidence / f'mutation-history-{args.group}-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    if args.group == 3:
        (evidence / 'mutation-history-native.json').write_text(json.dumps(prefix + [report], indent=2) + '\n', encoding='utf-8')
