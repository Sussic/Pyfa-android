"""Validate retained package evidence and finish only a failed aggregate summary."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def equivalent(root, tested, head):
    """Only setup controls/reporting may differ; executed suites stay identical."""
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf-8')
    changed = git('diff', '--name-only', tested, head).splitlines()
    if 'android/ci/tank_summary.py' in changed:
        assert all(p in {'android/ci/tank_summary.py','android/ci/test_tank_summary.py',
            'android/ci/summary_repair.py','android/ci/test_summary_repair.py'} or p.startswith('docs/android/') for p in changed), changed
        assert git('show', head+':android/ci/tank_summary.py') == corrected_tank_source(git('show', tested+':android/ci/tank_summary.py'))
        assert git('show', head+':android/ci/test_tank_summary.py') == corrected_tank_test_source(git('show', tested+':android/ci/test_tank_summary.py'))
        return changed
    allowed = {'AGENTS.md', 'android/README.md', 'android/verify-local.ps1',
        'android/ci/local_verification.py', 'android/ci/summary_repair.py',
        'android/ci/test_summary_repair.py', 'android/ci/report_local.py',
        'android/ci/test_report_local.py', 'android/ci/history_progress.py',
        'android/ci/contract_summary.py', 'android/ci/test_contract_fixtures.py',
        'android/ci/persistence_summary.py', 'android/ci/test_persistence_fixtures.py',
        '.github/workflows/android.yml', '.github/workflows/desktop-reference.yml'}
    assert all(p in allowed or p.startswith('docs/android/') for p in changed), changed
    if 'android/ci/contract_summary.py' in changed:
        before = git('show', tested + ':android/ci/contract_summary.py')
        after = git('show', head + ':android/ci/contract_summary.py')
        assert after == corrected_contract_source(before), 'Unexpected contract verifier change'
    if 'android/ci/persistence_summary.py' in changed:
        before = git('show', tested + ':android/ci/persistence_summary.py')
        after = git('show', head + ':android/ci/persistence_summary.py')
        assert after == corrected_persistence_source(before), 'Unexpected persistence verifier change'
    if 'android/ci/local_verification.py' in changed:
        def executed(source):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.FunctionDef) and n.name in ('plan', 'host', 'build', 'execute')}
        assert executed(git('show', tested + ':android/ci/local_verification.py')) == executed(
            git('show', head + ':android/ci/local_verification.py')), 'Executed host/build commands changed'
    if 'android/ci/history_progress.py' in changed:
        before = git('show', tested + ':android/ci/history_progress.py')
        after = git('show', head + ':android/ci/history_progress.py')
        assert before.count("'%s %Y'") == 1 and after == before.replace("'%s %Y'", "'%s:%Y'"), 'Unexpected diagnostic change'
    return changed


def corrected_contract_source(source):
    """The sole approved fixture verifier delta; every other byte stays exact."""
    old = '''        # The build stages LF-normalized fixtures, including on Windows hosts.
        assert proof["sha256"] == hashlib.sha256(data.replace(b"\\r\\n", b"\\n")).hexdigest()
'''
    new = '''        test_apk = Path(os.environ.get("PYFA_INSTRUMENTATION_APK",
            str(root / "android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk")))
        with ZipFile(test_apk) as apk:
            packaged = apk.read(f"assets/{filename}-expected.json")
        assert proof["sha256"] == hashlib.sha256(packaged).hexdigest()
        assert packaged.replace(b"\\r\\n", b"\\n") == data.replace(b"\\r\\n", b"\\n")
'''
    assert source.count(old) == 1 and source.count('import json\n') == 1
    return source.replace('import json\n', 'import json\nimport os\nfrom zipfile import ZipFile\n', 1).replace(old, new, 1)


def corrected_persistence_source(source):
    """Only bind the existing fixture hash comparisons to exact APK bytes."""
    old = '        fixture_hashes[kind] = hashlib.sha256(data).hexdigest()\n'
    new = '''        test_apk = Path(os.environ.get("PYFA_INSTRUMENTATION_APK",
            str(root / "android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk")))
        with ZipFile(test_apk) as apk:
            packaged = apk.read(f"assets/{filename}-expected.json")
        assert packaged.replace(b"\\r\\n", b"\\n") == data
        fixture_hashes[kind] = hashlib.sha256(packaged).hexdigest()
'''
    assert source.count(old) == 1 and source.count('import re\n') == 1
    return source.replace('import re\n', 'import re\nimport os\nfrom zipfile import ZipFile\n', 1).replace(old, new, 1)


TANK_RECENT = '''def recent_after_removal(previous, module_id):
    assert type(previous) is list and len(previous) <= 20
    assert all(type(i) is int and 0 < i < 2**63 for i in previous)
    assert len(previous) == len(set(previous)) and type(module_id) is int and 0 < module_id < 2**63
    # Original module removal promotes the removed item; Undo does not rewind
    # equipment recent use and Redo promotes that same item again.
    return [module_id, *[i for i in previous if i != module_id][:19]]


'''
TANK_EXPECTED_RECENT = '''        exact(before['sample_id'], after['sample_id'])
        catalog = json.loads((ROOT/'tools/android_reference/fixtures/equipment.json').read_text(encoding='utf-8'))['catalog']['items']
        module_name = fixture['cases'][4]['spec']['modules'][0]['name']
        exact('Medium Armor Repairer II', module_name)
        module_ids = [row['id'] for row in catalog if row['name'] == module_name]
        exact([3530], module_ids)
        exact(recent_after_removal(before.get('recent',[]), module_ids[0]), after.get('recent',[]))'''
TANK_RECENT_TESTS = '''class RecentTests(unittest.TestCase):
    def test_exact_twenty_item_eviction(self):self.assertEqual([3530,*range(1,20)],recent_after_removal(list(range(1,21)),3530))
    def test_existing_item_promoted_once(self):self.assertEqual([3530,1,2],recent_after_removal([1,3530,2],3530))
    def test_empty_list(self):self.assertEqual([3530],recent_after_removal([],3530))
    def test_invalid_list(self):
        for value in ([1,1],[True],[1.0],list(range(1,22))):
            with self.assertRaises(AssertionError):recent_after_removal(value,3530)
    def test_invalid_promoted_id(self):
        for value in (True,3530.0,0):
            with self.assertRaises(AssertionError):recent_after_removal([],value)


'''


def corrected_tank_source(source):
    from capacitor_runner_retry import once
    source=once(source,'from copy import deepcopy\n','from copy import deepcopy\nimport json\n')
    source=once(source,'def summarize(reports, engine, prior_pids=()):',TANK_RECENT+'def summarize(reports, engine, prior_pids=()):')
    return once(source,"        exact(before['sample_id'], after['sample_id']); exact(before.get('recent',[]), after.get('recent',[]))",TANK_EXPECTED_RECENT)


def corrected_tank_test_source(source):
    from capacitor_runner_retry import once
    source=once(source,'from tank_summary import tank, summarize, REJECTIONS','from tank_summary import tank, summarize, REJECTIONS, recent_after_removal')
    source=once(source,"        copied=deepcopy(graph['records'][ids[23]])","        graph['recent']=recent_after_removal(before['recent'],3530)\n        copied=deepcopy(graph['records'][ids[23]])")
    anchor="                    'edit':lambda r:r[0]['saved']['edits'][0]['after']['tank']['raw']['reinforced']['repairs']['armorRepair'].update(value=9999),\n"
    source=once(source,anchor,anchor+"                    'wrong_recent':lambda r:r[0]['saved']['graph']['data'].update(recent=[3531]),\n                    'missing_recent':lambda r:r[0]['saved']['graph']['data'].update(recent=[]),\n                    'extra_recent':lambda r:r[0]['saved']['graph']['data'].update(recent=[3530,3082]),\n")
    return once(source,'class NativeBoundaryTests(unittest.TestCase):',TANK_RECENT_TESTS+'class NativeBoundaryTests(unittest.TestCase):')


def clear_native_results(directory):
    """Build evidence stays valid when only the disposable native store restarts."""
    for path in directory.iterdir():
        if path.name in ('apk-contents.json', 'lint-results-debug.html'):
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def validate_package(run, root):
    state = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    tank = state.get('tank_history_reuse') if not state.get('native_restarts') else None
    if tank:
        from tank_history_retry import exact_source, validate_retained
        assert state['completed']==state['plan'][:-1] and len(state['completed'])==104
        exact_source(root,tank['from_commit'],tank['to_commit']);validate_retained(root,run,tank)
        assert tank['to_commit']==state['commit'] and tank['prepared'] and tank['installed']
    archive = (run / (tank['archive'] if tank else state['native_restarts'][-1]['archive'])).resolve()
    assert archive.is_relative_to(run.resolve()) and archive != run.resolve()
    prior = json.loads((archive / 'run.json').read_text(encoding='utf-8'))
    assert prior['status'] == 'failed' and prior['plan'] == state['plan']
    latest = {r['gate']: r for r in state['attempts']}
    older = {r['gate']: r for r in prior['attempts']}
    for gate in state['completed']:
        row = latest[gate]
        assert row['exit_code'] == 0 and sha(run / row['log']) == row['log_sha256'], gate
        if gate.startswith('build:') and not tank:
            assert row == older[gate], 'Archived report is from a different build: ' + gate
    report_path = (run if tank else archive) / 'native/apk-contents.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    assert set(report) == {'database_bytes', 'database_sha256', 'database_logical_sha256',
        'engine_source_sha256', 'mobile_sources', 'engine_source_files', 'abis'}
    apks = sorted((run / 'apks').glob('*.apk'))
    assert {p.name for p in apks} == {'app-debug.apk', 'app-debug-androidTest.apk'}
    digests = {}
    for apk in apks:
        outputs = list((root / 'android/app/build/outputs/apk').rglob(apk.name))
        assert len(outputs) == 1 and sha(apk) == sha(outputs[0]), 'Retained APK changed: ' + apk.name
        digests[apk.name] = sha(apk)
    with ZipFile(run / 'apks/app-debug.apk') as apk:
        manifest = json.loads(apk.read('assets/engine/manifest.json'))
        database = apk.read('assets/engine/eve.db')
        assert report['database_bytes'] == len(database) == manifest['database_bytes']
        assert report['database_sha256'] == hashlib.sha256(database).hexdigest() == manifest['database_sha256']
        for key in ('database_logical_sha256', 'engine_source_sha256'):
            assert report[key] == manifest[key], key
        assert report['engine_source_files'] == len(manifest['engine_sources'])
        files = {}
        for name in apk.namelist():
            if name.endswith('.so'):
                files[name] = apk.read(name)
            elif name.startswith('assets/chaquopy/') and name.endswith(('.imy', '.zip')):
                with ZipFile(io.BytesIO(apk.read(name))) as nested:
                    for inner in nested.namelist():
                        files[name + '!/' + inner] = nested.read(inner)
        sources = {}
        for source in sorted((root / 'android/app/src/main/python').glob('*.py')):
            matches = [raw for name, raw in files.items() if name.endswith('!/' + source.name)]
            assert len(matches) == 1
            raw = matches[0].replace(b'\r\n', b'\n')
            assert raw == source.read_bytes().replace(b'\r\n', b'\n')
            sources[source.name] = hashlib.sha256(raw).hexdigest()
        assert report['mobile_sources'] == sources
        assert set(report['abis']) == {'arm64-v8a', 'x86_64'}
        for abi, machine in (('arm64-v8a', 183), ('x86_64', 62)):
            recorded = report['abis'][abi]
            assert set(recorded) == {'elf_machine', 'runtime_tested', 'libraries'}
            assert recorded['elf_machine'] == machine and recorded['runtime_tested'] is False
            libraries = {n: b for n, b in files.items() if n.endswith('.so') and abi in n}
            assert set(recorded['libraries']) == set(libraries)
            # Digests bind the original dependency inspection to these exact ELF bytes.
            for name, raw in libraries.items():
                info = recorded['libraries'][name]
                assert set(info) == {'sha256', 'bytes', 'needed'}
                assert info['sha256'] == hashlib.sha256(raw).hexdigest() and info['bytes'] == len(raw), name
                assert isinstance(info['needed'], list) and all(isinstance(n, str) for n in info['needed'])
                with tempfile.TemporaryDirectory() as directory:
                    library = Path(directory) / 'library.so'
                    library.write_bytes(raw)
                    dynamic = subprocess.check_output(['readelf', '-d', str(library)], text=True)
                    assert info['needed'] == re.findall(r'\(NEEDED\).*?\[(.*?)\]', dynamic), name
    engine = json.loads((run / 'native/engine-native.json').read_text(encoding='utf-8'))
    archived_engine = engine if tank else json.loads((archive / 'native/engine-native.json').read_text(encoding='utf-8'))
    for key in ('database_sha256', 'database_logical_sha256', 'engine_source_sha256'):
        assert report[key] == engine[key] == archived_engine[key], key
    return report_path, {'archive': archive.name, 'report_sha256': sha(report_path),
        'apk_sha256': digests, 'package_gate_commit': latest['build:package']['tested_commit'],
        'package_log_sha256': latest['build:package']['log_sha256'],
        'native_tested_commit': state['commit']}


def finish(run, root):
    from local_verification import plan, save
    import msvcrt
    lock = (run / 'run.lock').open('a+b')
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        state = json.loads((run / 'run.json').read_text(encoding='utf-8'))
        assert state['status'] == 'failed' and state['mode'] == 'full' and state['gate'] is None
        assert state['plan'] == plan('full', None)
        assert [g for g in state['plan'] if g not in state['completed']] == ['native:summary']
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        changed = equivalent(root, state['commit'], head)
        source, provenance = validate_package(run, root)
        destination = run / 'native/apk-contents.json'
        assert not destination.exists() or sha(destination) == sha(source), 'Conflicting active package evidence'
        original = run / 'failed-summary-run.json'
        assert not any(r['gate'] == 'native:summary' and r.get('tested_commit') == head
            for r in state['attempts']), 'Unchanged summary retry is forbidden'
        if original.exists():
            original = run / f'failed-summary-run-{len(state["attempts"]):03}.json'
        assert not original.exists(), 'Failed-attempt snapshot already exists'
        shutil.copyfile(run / 'run.json', original)
        if not destination.exists():
            shutil.copyfile(source, destination)
        assert sha(destination) == provenance['report_sha256']
        provenance.update({'summary_commit': head, 'changed_setup_files': changed})
        state.setdefault('summary_repairs', []).append(provenance)
        log = run / 'logs' / f'{len(state["attempts"]):03}-native-summary.log'
        command = [sys.executable, str(root / 'android/ci/summarize-tests.py')]
        row = {'gate': 'native:summary', 'command': command, 'log': str(log.relative_to(run)),
            'started_utc': datetime.now(timezone.utc).isoformat(), 'tested_commit': head}
        state['attempts'].append(row)
        state['status'] = 'running'
        save(run / 'run.json', state)
        env = os.environ.copy()
        env.update(PYFA_EVIDENCE_DIR=str(run / 'native'), PYFA_EXECUTION_KIND='local_windows',
            PYFA_LOCAL_RUN_ID=run.name, PYTHONUTF8='1',
            PYFA_INSTRUMENTATION_APK=str(run / 'apks/app-debug-androidTest.apk'))
        env.pop('GITHUB_RUN_ID', None)
        env.pop('GITHUB_STEP_SUMMARY', None)
        started = time.monotonic()
        try:
            with log.open('wb') as stream:
                result = subprocess.run(command, cwd=root / 'android', env=env, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=300)
        except BaseException:
            row.update(exit_code=None, interrupted=True, seconds=round(time.monotonic() - started, 3), log_sha256=sha(log))
            state['status'] = 'failed'
            save(run / 'run.json', state)
            raise
        row.update(exit_code=result.returncode, seconds=round(time.monotonic() - started, 3), log_sha256=sha(log))
        state['status'] = 'passed' if result.returncode == 0 else 'failed'
        if result.returncode == 0:
            state['completed'].append('native:summary')
            state['completed_utc'] = datetime.now(timezone.utc).isoformat()
            shutil.copytree(root / 'android/app/build/outputs/androidTest-results/connected', run / 'native/junit', dirs_exist_ok=True)
        save(run / 'run.json', state)
        if result.returncode:
            raise RuntimeError('Summary failed; no completed gate was replayed. See ' + str(log))
        files = {str(p.relative_to(run)): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in run.rglob('*') if p.is_file() and not p.is_relative_to(run / 'avd')
            and p.name not in ('run.lock', 'files.json')}
        save(run / 'files.json', files)
        print(f'PASS outstanding summary; all {len(state["completed"])-1} completed results retained. Screenshot review remains required.')
    finally:
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    directory = Path(args.run).resolve()
    assert not directory.is_relative_to(ROOT)
    if args.validate_only:
        print(json.dumps(validate_package(directory, ROOT)[1], indent=2))
    else:
        finish(directory, ROOT)
