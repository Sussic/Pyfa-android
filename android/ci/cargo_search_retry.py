"""Exact C03.2 cargo search correction and bounded synthetic-store recovery."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

BEFORE = '4a8f6c75edeae0edd6f831ce8148403b13d434e0'
TEST_REVISION = 'af2ed23c5f5214f926d0f2d16da21e6489efe7ca'
TEST_PATH = 'android/app/src/androidTest/java/io/github/sussic/pyfa/CargoActionTest.kt'
SUMMARY_PATH = 'android/ci/cargo_action_summary.py'
PAIRS = {
    TEST_PATH: ('ed47414b129f4bff99fc1a07b9ffb758b8a12741441459b13698ba42eca5735e',
                '7ad3adb2140f0d129c978632385be769c47e596c5ee9ea2480146692d64e810d'),
    SUMMARY_PATH: ('1b4e546037187a134da828e9d63e70a0f75590122dd7efbeb2ef364d9cb8a9a3',
                   '9605421af71ee12acf046480fef88507a79bebe2c0125bc3a55d3c8b1068cb36'),
}
ORIGINAL_STORE = '76c14c1027f5236af869a9069c64d57f42440aba947d72c0aba46f1ee2c89d83'
RECOVERED_STORE = 'fde17eb87223b0e0a54b78e0b50547b06cd97c29c3edf610a81de36d87c68404'
PRIOR_REPORT = '9651f64f9be7f2175ae8e26249d8bfb6a032878e687690208f070dbd763f4363'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_source(root, before, after, completed):
    from local_verification import plan
    assert before == BEFORE and completed == plan('full', None)[:122]
    assert plan('full', None)[122] == 'native:check-cargo-actions.py'
    def source(revision, path):
        return subprocess.check_output(['git', 'show', revision + ':' + path], cwd=root)
    for path, pair in PAIRS.items():
        for revision, digest in zip((before, after), pair):
            assert hashlib.sha256(source(revision, path).replace(b'\r\n', b'\n')).hexdigest() == digest, path
        assert source(after, path) == source(TEST_REVISION, path), 'Build/test correction changed'
    changed = subprocess.check_output(['git', 'diff', '--name-only', before, after], cwd=root, text=True).splitlines()
    allowed = {TEST_PATH, SUMMARY_PATH, 'android/ci/test_cargo_search_checks.py',
               'android/ci/cargo_search_retry.py', 'android/ci/test_cargo_search_retry.py',
               'android/ci/local_verification.py', 'android/ci/report_local.py'}
    assert TEST_PATH in changed and SUMMARY_PATH in changed
    assert all(path in allowed or path.startswith('docs/android/') for path in changed), changed
    def executed(revision):
        return {n.name: ast.dump(n, include_attributes=False)
                for n in ast.walk(ast.parse(source(revision, 'android/ci/local_verification.py')))
                if isinstance(n, ast.FunctionDef) and n.name in ('plan', 'host', 'build', 'execute')}
    assert executed(before) == executed(after) == executed(TEST_REVISION), 'Completed execution changed'


def recovery_graph(original, prior, fixture, completed_prepare=False):
    """Remove only nine identified partial-test fits; keep actual recent history."""
    ids = [row['id'] for row in prior['after']['data']]
    assert len(ids) == len(set(ids)) == 47
    assert [key for key in original['fit_order'] if key in ids] == ids
    assert original['sample_id'] in ids
    for field in ('records', 'revisions', 'modified'):
        assert set(original[field]) == set(original['fit_order'])
    assert all(original['revisions'][row['id']] == row['revision'] for row in prior['after']['data'])
    extras = [key for key in original['fit_order'] if key not in ids]
    names = []
    assert len(fixture['cases']) == 5
    for case in fixture['cases'][:4]:
        names.extend(['B07.2 ' + case['name'] + ' – 探索', 'B07.2 copy ' + case['name'] + ' – Δ'])
    names.append('B07.2 ' + fixture['cases'][4]['name'] + ' – 探索')
    if completed_prepare:
        names.append('B07.2 copy ' + fixture['cases'][4]['name'] + ' – Δ')
    assert len(extras) == len(set(extras)) == len(names)
    assert [original['records'][key]['spec']['name'] for key in extras] == names
    for key in extras:
        assert not original['records'][key]['projections'] and not original['records'][key]['commands']
    for key in ids:
        assert not any(edge['source_id'] in extras for field in ('projections', 'commands')
                       for edge in original['records'][key][field])
    recovered = copy.deepcopy(original)
    recovered['fit_order'] = ids
    for field in ('records', 'revisions', 'modified'):
        recovered[field] = {key: original[field][key] for key in ids}
    return recovered, extras


def validate_recovery(root, run, directory):
    import sys
    sys.path.insert(0, str(root))
    from android_bridge.store import GraphStore, decode_graph, encode_graph
    receipt = json.loads((directory / 'recovery.json').read_text(encoding='utf-8'))
    old_path = directory / 'partial-graph.sqlite3'
    new_path = directory / 'recovered-graph.sqlite3'
    assert sha(old_path) == receipt['original_store_sha256'] == ORIGINAL_STORE
    assert sha(new_path) == receipt['recovered_store_sha256'] == RECOVERED_STORE
    assert sha(run / 'native/cargo-stacks-native.json') == receipt['prior_report_sha256'] == PRIOR_REPORT
    prior = json.loads((run / 'native/cargo-stacks-native.json').read_text(encoding='utf-8'))[-1]
    fixture = json.loads((root / 'tools/android_reference/fixtures/cargo-actions.json').read_text(encoding='utf-8'))
    old, new = GraphStore(old_path).current, GraphStore(new_path).current
    expected, removed = recovery_graph(decode_graph(old.payload), prior, fixture)
    assert decode_graph(new.payload) == expected
    assert receipt['source_commit'] == BEFORE and receipt['original_fits'] == 47
    assert removed == receipt['removed_ids']
    assert old.generation == receipt['generation_before'] == 1725
    assert new.generation == receipt['generation_after'] == old.generation + 9
    assert receipt['recent'] == expected['recent']
    preserved = encode_graph({field: expected[field] for field in ('records', 'revisions', 'modified')})
    assert hashlib.sha256(preserved.encode()).hexdigest() == receipt['preserved_original_inputs_sha256']
    assert receipt['original_library_eos_comparison_passed'] is True
    transactions = receipt['transactions']
    assert [row['removed_id'] for row in transactions] == removed
    assert [row['generation'] for row in transactions] == list(range(old.generation + 1, new.generation + 1))
    assert transactions[-1]['payload_sha256'] == new.digest
    return receipt


def validate_artifact_flush_retry(root, run, proof):
    """Rollback only the unaccepted gate to its byte-verified input checkpoint."""
    retry = proof['artifact_flush_retry']
    archive = run / retry['archive']
    assert archive.resolve().parent == run.resolve()
    assert sha(archive / 'run.json') == retry['original_run_sha256']
    old = json.loads((archive / 'run.json').read_text(encoding='utf-8'))
    assert old['commit'] == retry['from_commit'] == '515428bd9ed5dd1d4c966407b27816a146db694d'
    assert old['status'] == 'failed' and old['completed'] == proof['completed_before_adoption']
    assert retry['to_commit'] == proof['to_commit']
    assert sha(archive / 'durability-result.json') == retry['durability_result_sha256']
    results = json.loads((archive / 'durability-result.json').read_text(encoding='utf-8'))
    assert [row['sync_before_shutdown'] for row in results] == [False, True]
    assert results[0]['after_bytes'] == 0 and results[0]['preserved'] is False
    assert results[1]['preserved'] is True and results[1]['before_sha256'] == results[1]['after_sha256']
    assert sha(archive / 'post-prepare-graph.sqlite3') == retry['post_prepare_graph_sha256']
    instrument = archive / 'cargo-actions-prepare-instrumentation.txt'
    assert sha(instrument) == retry['instrumentation_sha256']
    import re
    text = instrument.read_text(encoding='utf-8')
    assert len(re.findall(r'^OK \(1 test\)\s*$', text, re.M)) == 1
    assert 'INSTRUMENTATION_CODE: -1' in text and not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=', text)
    from android_bridge.store import GraphStore, decode_graph
    current = GraphStore(archive / 'post-prepare-graph.sqlite3').current
    baseline_path = run / proof['archive'] / 'recovery/recovered-graph.sqlite3'
    assert sha(baseline_path) == RECOVERED_STORE == retry['rollback_store_sha256']
    baseline = GraphStore(baseline_path).current
    prior = json.loads((run / 'native/cargo-stacks-native.json').read_text(encoding='utf-8'))[-1]
    fixture = json.loads((root / 'tools/android_reference/fixtures/cargo-actions.json').read_text(encoding='utf-8'))
    expected, removed = recovery_graph(decode_graph(current.payload), prior, fixture, completed_prepare=True)
    target = decode_graph(baseline.payload)
    # A failed proof-bearing gate is repeated from its original checkpoint;
    # its unaccepted synthetic fits and recent-use changes are not retained.
    expected['recent'] = target['recent']
    assert expected == target and len(removed) == 10
    assert removed == retry['removed_ids'] and current.generation == 1775 and baseline.generation == 1734
    return baseline_path


def adopt_artifact_flush_retry(runner, current):
    from local_verification import git
    proof = runner.state['cargo_search_reuse']
    assert runner.state['commit'] == proof['to_commit'] == '515428bd9ed5dd1d4c966407b27816a146db694d'
    assert runner.state['status'] == 'failed' and runner.state['completed'] == proof['completed_before_adoption']
    assert runner.state['attempts'][-1]['gate'] == 'native:check-cargo-actions.py'
    assert runner.state['attempts'][-1]['exit_code'] != 0 and proof['prepared'] and proof['installed']
    root = Path(__file__).resolve().parents[2]
    exact_source(root, BEFORE, current, proof['completed_before_adoption'])
    archive = runner.directory / 'cargo-artifact-write-failure-515428bd'
    archive.mkdir(exist_ok=False)
    (archive / 'run.json').write_bytes(runner.original_run_bytes)
    diagnostic = runner.directory / 'artifact-durability-probe-515428bd-3'
    results = json.loads((diagnostic / 'result.json').read_text(encoding='utf-8'))
    assert [row['sync_before_shutdown'] for row in results] == [False, True]
    assert results[0]['after_bytes'] == 0 and results[0]['preserved'] is False
    assert results[1]['preserved'] is True and results[1]['before_sha256'] == results[1]['after_sha256']
    shutil.copyfile(diagnostic / 'result.json', archive / 'durability-result.json')
    shutil.copyfile(diagnostic / 'post-prepare-graph.sqlite3', archive / 'post-prepare-graph.sqlite3')
    for path in runner.directory.joinpath('native').glob('cargo-actions-*'):
        if path.is_file(): shutil.copyfile(path, archive / path.name)
    import sys
    sys.path.insert(0, str(root))
    from android_bridge.store import GraphStore, decode_graph
    graph = decode_graph(GraphStore(archive / 'post-prepare-graph.sqlite3').current.payload)
    prior = json.loads((runner.directory / 'native/cargo-stacks-native.json').read_text(encoding='utf-8'))[-1]
    fixture = json.loads((root / 'tools/android_reference/fixtures/cargo-actions.json').read_text(encoding='utf-8'))
    _, removed = recovery_graph(graph, prior, fixture, completed_prepare=True)
    proof['to_commit'] = current
    proof['artifact_flush_retry'] = dict(from_commit=runner.state['commit'], to_commit=current,
        archive=archive.name, original_run_sha256=sha(archive / 'run.json'),
        post_prepare_graph_sha256=sha(archive / 'post-prepare-graph.sqlite3'),
        instrumentation_sha256=sha(archive / 'cargo-actions-prepare-instrumentation.txt'),
        durability_result_sha256=sha(archive / 'durability-result.json'), rollback_store_sha256=RECOVERED_STORE,
        removed_ids=removed, installed=False)
    validate_artifact_flush_retry(root, runner.directory, proof)
    runner.state['commit'] = current
    runner.state['tree'] = git('rev-parse', 'HEAD^{tree}')


def install_artifact_flush_retry(runner, proof):
    root = Path(__file__).resolve().parents[2]
    baseline = validate_artifact_flush_retry(root, runner.directory, proof)
    retry = proof['artifact_flush_retry']
    def adb(*args):
        return subprocess.check_output(['adb', '-s', runner.serial, *map(str, args)], timeout=60)
    assert adb('shell', 'getprop', 'ro.kernel.qemu').strip() == b'1'
    assert adb('emu', 'avd', 'name').decode().splitlines()[0] == runner.state['avd_name']
    assert adb('shell', 'settings', 'get', 'global', 'airplane_mode_on').strip() == b'1'
    package = 'io.github.sussic.pyfa.dev'
    for pkg, name in ((package, 'app-debug.apk'), (package + '.test', 'app-debug-androidTest.apk')):
        path = adb('shell', 'pm', 'path', pkg).decode().strip().removeprefix('package:')
        assert path.startswith('/data/app/') and '\n' not in path
        assert adb('shell', 'sha256sum', path).split()[0].decode() == proof['build_reuse']['apk_hashes'][name]
    adb('shell', 'am', 'force-stop', package)
    def graph():
        return hashlib.sha256(adb('exec-out', 'run-as', package, 'cat', 'no_backup/fits/graph.sqlite3')).hexdigest()
    assert graph() == retry['post_prepare_graph_sha256'], 'Post-prepare synthetic store changed'
    remote = '/data/local/tmp/pyfa-c032-cargo-checkpoint.sqlite3'
    adb('push', baseline, remote)
    adb('shell', 'run-as', package, 'cp', remote, 'no_backup/fits/graph.sqlite3')
    adb('shell', 'sync')
    assert graph() == RECOVERED_STORE
    adb('shell', 'rm', remote)
    retry['installed'] = True


def validate_retained(root, run, proof):
    exact_source(root, proof['from_commit'], proof['to_commit'], proof['completed_before_adoption'])
    archive = run / proof['archive']
    assert archive.resolve().parent == run.resolve()
    assert sha(archive / 'run.json') == proof['original_run_sha256']
    old = json.loads((archive / 'run.json').read_text(encoding='utf-8'))
    assert sha(archive / 'native-manifest.json') == proof['original_manifest_sha256']
    manifest = json.loads((archive / 'native-manifest.json').read_text(encoding='utf-8'))
    expected_native = {name.replace('\\', '/'): row['sha256'] for name, row in manifest.items()
                       if name.replace('\\', '/').startswith('native/')
                       and not Path(name.replace('\\', '/')).name.startswith('cargo-actions-')
                       and Path(name.replace('\\', '/')).name not in ('failure.png', 'apk-contents.json')
                       and name.replace('\\', '/') != 'native/failure-logcat.txt'}
    assert {name.replace('\\', '/'): digest for name, digest in proof['native_hashes'].items()
            if name.replace('\\', '/') != 'native/failure-logcat.txt'} == expected_native
    from local_verification import plan
    assert old['commit'] == BEFORE and old['status'] == 'failed'
    assert old['completed'] == proof['completed_before_adoption'] == plan('full', None)[:122]
    assert old['attempts'][-1]['gate'] == 'native:check-cargo-actions.py' and old['attempts'][-1]['exit_code'] != 0
    retained = [gate for gate in old['completed'] if not gate.startswith('build:')]
    assert proof['retained_gates'] == retained
    current = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    package_run = run
    targeting = current.get('targeting_phase_reuse')
    if targeting:
        package_run = run / targeting['archive']
        assert package_run.resolve().parent == run.resolve()
        assert sha(package_run / 'run.json') == targeting['original_run_sha256']
        current = json.loads((package_run / 'run.json').read_text(encoding='utf-8'))
        assert current['commit'] == proof['to_commit'] == targeting['from_commit']
    older = {row['gate']: row for row in old['attempts']}
    latest = {row['gate']: row for row in current['attempts']}
    assert set(proof['retained_log_hashes']) == set(retained)
    for gate in retained:
        assert latest[gate] == older[gate] and latest[gate]['exit_code'] == 0
        assert sha(run / latest[gate]['log']) == latest[gate]['log_sha256'] == proof['retained_log_hashes'][gate]
    for name, digest in proof['native_hashes'].items():
        # Only the root failed-gate diagnostic is volatile, never passing proof.
        if name.replace('\\', '/') == 'native/failure-logcat.txt': continue
        path = (run / name).resolve()
        assert path.is_relative_to((run / 'native').resolve()) and sha(path) == digest
    receipt = validate_recovery(root, run, archive / 'recovery')
    if proof.get('artifact_flush_retry'):
        validate_artifact_flush_retry(root, run, proof)
    assert sha(archive / 'recovery/recovery.json') == proof['recovery_receipt_sha256']
    from charge_keyboard_retry import validated_build
    source, state, rows = validated_build(run, proof['build_reuse'], TEST_REVISION)
    build_manifest = json.loads((source / 'files.json').read_text(encoding='utf-8'))
    contents = next(row for name, row in build_manifest.items() if name.replace('\\', '/') == 'native/apk-contents.json')
    assert sha(source / 'native/apk-contents.json') == sha(package_run / 'native/apk-contents.json') == contents['sha256']
    assert sha(archive / 'apks/app-debug.apk') == sha(source / 'apks/app-debug.apk') == sha(run / 'apks/app-debug.apk')
    assert sha(package_run / 'apks/app-debug-androidTest.apk') == proof['build_reuse']['apk_hashes']['app-debug-androidTest.apk']
    from cargo_history_retry import assets_equal
    assets_equal(archive / 'apks/app-debug-androidTest.apk', package_run / 'apks/app-debug-androidTest.apk')
    for gate in plan('build', None):
        row = latest[gate]
        assert row['tested_commit'] == TEST_REVISION and row['reused_from_run'] == source.name
        assert row['log_sha256'] == rows[gate]['log_sha256'] == sha(run / row['log'])
    return receipt


def prepare(runner, proof):
    from local_verification import plan
    from charge_keyboard_retry import validated_build
    root = Path(__file__).resolve().parents[2]
    source = runner.directory.parent / '20261005-232815-af2ed23c-6187cb'
    build = dict(source_run=source.name, state_sha256=sha(source / 'run.json'),
                 manifest_sha256=sha(source / 'files.json'),
                 apk_hashes={p.name: sha(p) for p in (source / 'apks').glob('*.apk')})
    source, state, rows = validated_build(runner.directory, build, TEST_REVISION)
    assert sha(runner.directory / 'apks/app-debug.apk') == sha(source / 'apks/app-debug.apk')
    from cargo_history_retry import assets_equal
    assets_equal(runner.directory / 'apks/app-debug-androidTest.apk', source / 'apks/app-debug-androidTest.apk')
    recovery = runner.directory / 'cargo-search-failure'
    validate_recovery(root, runner.directory, recovery)
    archive = runner.directory / 'cargo-search-fix-original'
    archive.mkdir(exist_ok=False)
    (archive / 'run.json').write_bytes(runner.original_run_bytes)
    # Failed runs have no final publication manifest. Capture actual retained
    # native bytes before any correction, rather than inventing a passing one.
    manifest = {str(p.relative_to(runner.directory)): dict(sha256=sha(p), bytes=p.stat().st_size)
                for p in runner.native.rglob('*') if p.is_file()}
    (archive / 'native-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copytree(runner.directory / 'apks', archive / 'apks')
    shutil.copytree(recovery, archive / 'recovery')
    (archive / 'native').mkdir()
    for path in runner.native.glob('cargo-actions-*'):
        if path.is_file(): shutil.move(str(path), str(archive / 'native' / path.name))
    for name in ('failure.png', 'failure-logcat.txt', 'apk-contents.json'):
        path = runner.native / name
        if path.exists(): shutil.move(str(path), str(archive / 'native' / name))
    shutil.copyfile(source / 'native/apk-contents.json', runner.native / 'apk-contents.json')
    proof.update(archive=archive.name, original_run_sha256=sha(archive / 'run.json'),
                 original_manifest_sha256=sha(archive / 'native-manifest.json'),
                 recovery_receipt_sha256=sha(archive / 'recovery/recovery.json'), build_reuse=build,
                 native_hashes={str(p.relative_to(runner.directory)): sha(p)
                                for p in runner.native.rglob('*') if p.is_file() and p.name != 'apk-contents.json'
                                and p != runner.native / 'failure-logcat.txt'})
    for index, gate in enumerate(plan('build', None)):
        row = dict(rows[gate])
        target = runner.directory / 'logs' / f'cargo-search-reused-build-{index:02}.log'
        shutil.copyfile(source / row['log'], target)
        row.update(log=str(target.relative_to(runner.directory)), reused_from_run=source.name)
        runner.state['attempts'].append(row)
    for name in build['apk_hashes']:
        shutil.copyfile(source / 'apks' / name, runner.directory / 'apks' / name)
    proof['prepared'] = True


def install(runner, proof):
    root = Path(__file__).resolve().parents[2]
    receipt = validate_retained(root, runner.directory, proof)
    def adb(*args):
        return subprocess.check_output(['adb', '-s', runner.serial, *map(str, args)], timeout=60)
    assert adb('shell', 'getprop', 'ro.kernel.qemu').strip() == b'1'
    assert adb('emu', 'avd', 'name').decode().splitlines()[0] == runner.state['avd_name']
    import time
    deadline = time.monotonic() + 120
    health = []
    while True:
        windows = adb('shell', 'dumpsys', 'window').decode(errors='replace')
        processes = adb('shell', 'dumpsys', 'activity', 'processes').decode(errors='replace')
        focused = next((line.strip() for line in windows.splitlines() if 'mCurrentFocus=' in line), '')
        bad = 'Application Not Responding' in windows or 'notResponding=true' in processes
        health.append(dict(focused=focused, anr_present=bad))
        (runner.directory / 'cargo-search-platform-readiness.json').write_text(json.dumps(health, indent=2) + '\n')
        if 'nexuslauncher' in focused and not bad: break
        assert time.monotonic() < deadline, 'Platform did not reach healthy launcher focus'
        time.sleep(2)
    for key, value in [('airplane_mode_on', b'1'), ('wifi_on', b'0'), ('mobile_data', b'0')]:
        assert adb('shell', 'settings', 'get', 'global', key).strip() == value
    package = 'io.github.sussic.pyfa.dev'
    app_path = adb('shell', 'pm', 'path', package).decode().strip().removeprefix('package:')
    assert app_path.startswith('/data/app/') and '\n' not in app_path
    assert adb('shell', 'sha256sum', app_path).split()[0].decode() == proof['build_reuse']['apk_hashes']['app-debug.apk']
    adb('shell', 'am', 'force-stop', package)
    def graph():
        return hashlib.sha256(adb('exec-out', 'run-as', package, 'cat', 'no_backup/fits/graph.sqlite3')).hexdigest()
    assert graph() == ORIGINAL_STORE, 'Synthetic store changed since recovery proof'
    test_path = adb('shell', 'pm', 'path', package + '.test').decode().strip().removeprefix('package:')
    assert test_path.startswith('/data/app/') and '\n' not in test_path
    if adb('shell', 'sha256sum', test_path).split()[0].decode() != proof['build_reuse']['apk_hashes']['app-debug-androidTest.apk']:
        runner.execute('environment:cargo-search-update', ['adb', '-s', runner.serial, 'install', '-r', '-t',
                                                          runner.directory / 'apks/app-debug-androidTest.apk'])
        test_path = adb('shell', 'pm', 'path', package + '.test').decode().strip().removeprefix('package:')
        assert test_path.startswith('/data/app/') and '\n' not in test_path
    assert adb('shell', 'sha256sum', test_path).split()[0].decode() == proof['build_reuse']['apk_hashes']['app-debug-androidTest.apk']
    assert graph() == ORIGINAL_STORE
    target = runner.directory / proof['archive'] / 'recovery/recovered-graph.sqlite3'
    remote = '/data/local/tmp/pyfa-c032-cargo-recovered.sqlite3'
    adb('push', target, remote)
    adb('shell', 'run-as', package, 'cp', remote, 'no_backup/fits/graph.sqlite3')
    assert graph() == receipt['recovered_store_sha256']
    adb('shell', 'rm', remote)
    proof['installed'] = True