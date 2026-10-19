"""Exact targeting phase correction and synthetic checkpoint recovery guards."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys

BEFORE = '9736218ec7b212642ce964d76ec3338bf6f91909'
BUILD = 'bec2c0eb'
PHASE_SOURCES = (
    'android/app/src/androidTest/java/io/github/sussic/pyfa/TargetingTest.kt',
    'android/ci/check-targeting.py', 'android/ci/native_suite.py',
    'android/ci/summarize-tests.py', 'android/ci/targeting_summary.py',
    'android/ci/test_targeting_summary.py', 'android/ci/test_inspector_plan.py',
    'android/ci/test_tank_summary.py',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact_source(root, before, after, completed):
    """Accept the reviewed built phase delta only; product/oracles stay identical."""
    import ast
    from local_verification import plan
    assert before == BEFORE
    current_plan = plan('full', None)
    old_plan = [gate for gate in current_plan if gate != 'native:targeting-prepare3']
    assert len(old_plan) == 174 and len(current_plan) == 175
    assert completed == old_plan[:147] == current_plan[:147]
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf-8')
    changed = git('diff', '--name-only', before, after).splitlines()
    allowed = set(PHASE_SOURCES) | {
        'android/ci/targeting_phase_retry.py', 'android/ci/test_targeting_phase_retry.py',
        'android/ci/local_verification.py', 'android/ci/report_local.py',
        'android/ci/test_report_local.py', 'android/ci/cargo_search_retry.py',
        'android/ci/test_cargo_search_retry.py',
    }
    assert set(PHASE_SOURCES) <= set(changed)
    assert all(path in allowed or path.startswith('docs/android/') for path in changed), changed
    for path in PHASE_SOURCES:
        assert git('show', after+':'+path) == git('show', BUILD+':'+path), path
    def executed(revision):
        tree = ast.parse(git('show', revision+':android/ci/local_verification.py'))
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name in ('plan','host','build','execute')}
    assert executed(before) == executed(after) == executed(BUILD), 'Executed host/build checks changed'
    return changed


def typed_graph_equal(wrapper, actual):
    """Restore JSONObject's integer-looking doubles using its original type map."""
    from defense_summary import typed
    expected = typed(wrapper)
    kinds = wrapper['numeric_types']
    visited = set()
    def compare(left, right, path):
        if type(left) is dict:
            assert type(right) is dict and set(left) == set(right), path
            for key in left: compare(left[key], right[key], path + '.' + key)
        elif type(left) is list:
            assert type(right) is list and len(left) == len(right), path
            for index, (a, b) in enumerate(zip(left, right)): compare(a, b, f'{path}[{index}]')
        elif type(left) in (int, float):
            assert path in kinds
            visited.add(path)
            assert type(right) is (float if kinds[path] == 'decimal' else int), path
            assert right == left, path
        else:
            assert type(left) is type(right) and left == right, path
    compare(expected, actual, 'root')
    assert visited == set(kinds)


def recovery_graph(original, prior, fixture, skills):
    """Accept only the eleven known unaccepted fixture/source additions."""
    assert prior['task'] == 'C03.1' and prior['phase'] == 'prepare1'
    saved = prior['saved']
    baseline = saved['graph']['data']
    ids = baseline['fit_order']
    assert len(ids) == len(set(ids)) == len(saved['all_fits']['data']) == 313
    assert len(saved['ids']) == len(set(saved['ids'])) == 45
    assert len(saved['outputs']) == len(prior['observations']) == 45
    assert original.keys() == baseline.keys()
    for field in ('format', 'sample_id', 'dataset_identity', 'eos_settings'):
        assert original[field] == baseline[field], field
    assert original['fit_order'][:313] == ids
    for field in ('records', 'revisions', 'modified'):
        assert set(original[field]) == set(original['fit_order'])
        assert set(baseline[field]) == set(ids)
        assert {key: original[field][key] for key in ids} == baseline[field], field
    extras = original['fit_order'][313:]
    assert len(extras) == len(set(extras)) == 11
    expected = []
    for case in fixture['cases'][45:]:
        expected.append('C03 ' + case['spec']['name'])
        if 'source_spec' in case: expected.append('C03 ' + case['source_spec']['name'])
    assert len(fixture['cases']) == 53 and len(expected) == 11
    assert [original['records'][key]['spec']['name'] for key in extras] == expected
    from defense_summary import fit_inputs
    from market_summary import exact
    from inspection_record_identity import graph_identities
    graph_identities(original['records'])
    cursor = 0
    for index, case in enumerate(fixture['cases'][45:], 45):
        key = extras[cursor]; cursor += 1
        record = original['records'][key]
        spec = copy.deepcopy(case['spec']); spec['name'] = 'C03 ' + spec['name']
        for edit in case['edits']:
            if edit['operation'] == 'add_cargo':
                spec['cargo'] = [dict(name='Antimatter Charge M', amount=edit['args']['quantity'])]
            else: assert edit['operation'] == 'set_skill_level'
        fit_inputs(spec, record['spec'])
        assert skills['cases'][index]['case'] == index
        exact(skills['cases'][index]['skills'], record['skills'])
        assert record['implants'] == record['commands'] == [] and original['revisions'][key] == 4
        if 'source_spec' in case:
            source = extras[cursor]; cursor += 1
            source_record = original['records'][source]
            source_spec = copy.deepcopy(case['source_spec']); source_spec['name'] = 'C03 ' + source_spec['name']
            fit_inputs(source_spec, source_record['spec'])
            assert source_record['skills'] == {} and original['revisions'][source] == 2
            assert source_record['implants'] == source_record['commands'] == source_record['projections'] == []
            exact([dict(source_id=source, range_m=None, active=True, amount=1)], record['projections'])
        else: assert record['projections'] == []
    assert cursor == len(extras)
    for key in ids:
        assert not any(edge['source_id'] in extras for field in ('projections', 'commands')
                       for edge in original['records'][key][field])
    # Failed preparation promoted one synthetic cargo item; restore its exact
    # verified predecessor alongside unchanged fit inputs, not guessed recency.
    cargo = fixture['cases'][49]
    assert cargo['spec']['name'] == 'Cargo tooltip refresh'
    item = cargo['edits'][0]['args']['item_id']
    assert original['recent'] == ([item] + [i for i in baseline['recent'] if i != item])[:20]
    restored = copy.deepcopy(original)
    restored['fit_order'] = list(ids)
    for field in ('records', 'revisions', 'modified'):
        restored[field] = {key: original[field][key] for key in ids}
    restored['recent'] = copy.deepcopy(baseline['recent'])
    typed_graph_equal(saved['graph'], restored)
    return restored, extras


def validate_recovery(root, run, directory):
    sys.path.insert(0, str(root))
    from android_bridge.store import GraphStore, decode_graph, encode_graph
    directory = Path(directory)
    receipt = json.loads((directory / 'recovery.json').read_text(encoding='utf-8'))
    partial = directory / 'partial-graph.sqlite3'
    restored = directory / 'restored-graph.sqlite3'
    prior = run / 'native/targeting-prepare1-native.json'
    fixture = root / 'tools/android_reference/fixtures/targeting.json'
    skills = root / 'tools/android_reference/fixtures/targeting-skill-inputs.json'
    for path, field in ((partial, 'partial_sha256'), (restored, 'restored_sha256'),
                        (prior, 'prior_report_sha256'), (fixture, 'fixture_sha256'),
                        (skills, 'skills_fixture_sha256')):
        assert sha(path) == receipt[field], field
    old, new = GraphStore(partial).current, GraphStore(restored).current
    expected, extras = recovery_graph(decode_graph(old.payload), json.loads(prior.read_text(encoding='utf-8')),
                                      json.loads(fixture.read_text(encoding='utf-8')), json.loads(skills.read_text(encoding='utf-8')))
    assert decode_graph(new.payload) == expected
    assert old.generation == receipt['generation_before']
    assert new.generation == old.generation + 1 == receipt['generation_after']
    assert receipt['removed_ids'] == extras and receipt['retained_fits'] == 313
    assert hashlib.sha256(encode_graph(expected).encode()).hexdigest() == receipt['checkpoint_graph_sha256']
    assert receipt['retained_library_eos_comparison_passed'] is True
    return receipt


def adopt(runner, current):
    from local_verification import plan
    state = runner.state
    assert state['status'] == 'failed' and state['mode'] == 'full' and state['gate'] is None
    assert state['attempts'][-1]['gate'] == 'native:targeting-prepare2' and state['attempts'][-1]['exit_code'] != 0
    exact_source(Path(__file__).resolve().parents[2], state['commit'], current, state['completed'])
    assert state['plan'] == [g for g in plan('full', None) if g != 'native:targeting-prepare3']
    state['targeting_phase_reuse'] = dict(from_commit=state['commit'], to_commit=current,
        completed_before_adoption=list(state['completed']),
        retained_gates=[g for g in state['completed'] if not g.startswith('build:')],
        prepared=False, installed=False)
    state['commit'] = current
    state['tree'] = subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()
    state['plan'] = plan('full', None)


def adopt_preflight_fix(runner, current):
    """Retain the original failed snapshot after an isolated-import preflight error."""
    from local_verification import plan
    state = runner.state; proof = state['targeting_phase_reuse']
    assert state['status'] == 'failed' and not proof['prepared'] and not proof['installed']
    assert state['commit'] == proof['to_commit']
    assert not (runner.directory/'targeting-phase-fix-original').exists()
    exact_source(Path(__file__).resolve().parents[2], BEFORE, current, proof['completed_before_adoption'])
    assert state['completed'] == proof['completed_before_adoption'] == plan('full',None)[:147]
    original = runner.directory/'targeting-timeout-9736218e/failed-run.json'
    old = json.loads(original.read_text(encoding='utf-8'))
    assert old['commit'] == BEFORE and old['status'] == 'failed' and old['completed'] == state['completed']
    old_rows = {row['gate']:row for row in old['attempts']}
    latest = {row['gate']:row for row in state['attempts']}
    assert all(latest[gate] == old_rows[gate] for gate in state['completed'])
    proof.setdefault('preflight_repairs',[]).append(dict(from_commit=state['commit'],to_commit=current,
        reason='Isolated recovery import prerequisite; no native execution or store modification'))
    proof['original_snapshot'] = str(original.relative_to(runner.directory))
    proof['original_run_sha256'] = sha(original)
    proof['to_commit'] = state['commit'] = current
    state['tree'] = subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()


def validate_retained(root, run, proof):
    exact_source(root, proof['from_commit'], proof['to_commit'], proof['completed_before_adoption'])
    archive = run / proof['archive']
    assert archive.resolve().parent == run.resolve()
    assert sha(archive/'run.json') == proof['original_run_sha256']
    old = json.loads((archive/'run.json').read_text(encoding='utf-8'))
    assert old['commit'] == BEFORE and old['status'] == 'failed'
    assert old['completed'] == proof['completed_before_adoption']
    assert proof['retained_gates'] == [g for g in old['completed'] if not g.startswith('build:')]
    current = json.loads((run/'run.json').read_text(encoding='utf-8'))
    older = {row['gate']: row for row in old['attempts']}
    latest = {row['gate']: row for row in current['attempts']}
    for gate in proof['retained_gates']:
        assert latest[gate] == older[gate] and latest[gate]['exit_code'] == 0, gate
        assert sha(run/latest[gate]['log']) == latest[gate]['log_sha256'], gate
    assert sha(archive/'native-manifest.json') == proof['native_manifest_sha256']
    assert json.loads((archive/'native-manifest.json').read_text(encoding='utf-8')) == proof['native_hashes']
    for name, digest in proof['native_hashes'].items():
        path = (run/name).resolve()
        assert path.is_relative_to((run/'native').resolve()) and sha(path) == digest, name
    for name, digest in proof['old_apk_hashes'].items(): assert sha(archive/'apks'/name) == digest
    assert sha(archive/'native/apk-contents.json') == proof['old_package_sha256']
    from charge_keyboard_retry import validated_build
    source, state, rows = validated_build(run, proof['build_reuse'], proof['build_commit'])
    assert proof['build_commit'] == subprocess.check_output(['git','rev-parse',BUILD],cwd=root,text=True).strip()
    for name, digest in proof['build_reuse']['apk_hashes'].items(): assert sha(run/'apks'/name) == digest
    assert sha(source/'apks/app-debug.apk') == proof['old_apk_hashes']['app-debug.apk']
    from cargo_history_retry import assets_equal
    assets_equal(archive/'apks/app-debug-androidTest.apk', run/'apks/app-debug-androidTest.apk')
    manifest = json.loads((source/'files.json').read_text(encoding='utf-8'))
    package = next(v for k,v in manifest.items() if k.replace('\\','/')=='native/apk-contents.json')
    assert sha(run/'native/apk-contents.json') == package['sha256'] == sha(source/'native/apk-contents.json')
    for gate in state['completed']:
        row = latest[gate]
        assert row['tested_commit'] == proof['build_commit'] and row['reused_from_run'] == source.name
        assert row['log_sha256'] == rows[gate]['log_sha256'] == sha(run/row['log'])
    return validate_recovery(root, run, archive/'recovery')


def prepare(runner, proof):
    root = Path(__file__).resolve().parents[2]
    source = runner.directory.parent/'20261006-030306-bec2c0eb-148ce6'
    build = dict(source_run=source.name, state_sha256=sha(source/'run.json'), manifest_sha256=sha(source/'files.json'),
                 apk_hashes={p.name:sha(p) for p in (source/'apks').glob('*.apk')})
    commit = subprocess.check_output(['git','rev-parse',BUILD],cwd=root,text=True).strip()
    from charge_keyboard_retry import validated_build
    source, state, rows = validated_build(runner.directory, build, commit)
    assert sha(runner.directory/'apks/app-debug.apk') == build['apk_hashes']['app-debug.apk']
    from cargo_history_retry import assets_equal
    assets_equal(runner.directory/'apks/app-debug-androidTest.apk',source/'apks/app-debug-androidTest.apk')
    recovery = runner.directory/'targeting-store-recovery-9736218e'
    validate_recovery(root,runner.directory,recovery)
    archive = runner.directory/'targeting-phase-fix-original';archive.mkdir(exist_ok=False)
    original_bytes = runner.original_run_bytes
    if proof.get('original_snapshot'):
        snapshot = (runner.directory/proof['original_snapshot']).resolve()
        assert snapshot.is_relative_to(runner.directory.resolve()) and sha(snapshot) == proof['original_run_sha256']
        original_bytes = snapshot.read_bytes()
    (archive/'run.json').write_bytes(original_bytes)
    shutil.copytree(runner.directory/'apks',archive/'apks')
    (archive/'native').mkdir();shutil.copyfile(runner.native/'apk-contents.json',archive/'native/apk-contents.json')
    shutil.copytree(recovery,archive/'recovery')
    hashes = {str(p.relative_to(runner.directory)):sha(p) for p in runner.native.rglob('*') if p.is_file()
              and not (p.parent == runner.native and (p.name in ('failure.png','failure-logcat.txt','apk-contents.json')
                       or p.name.startswith('targeting-prepare2-')))}
    (archive/'native-manifest.json').write_text(json.dumps(hashes,indent=2)+'\n')
    for name in ('failure.png','failure-logcat.txt'):
        path = runner.native/name
        if path.exists(): shutil.move(str(path),str(archive/'native'/name))
    proof.update(archive=archive.name, original_run_sha256=sha(archive/'run.json'),
        native_manifest_sha256=sha(archive/'native-manifest.json'),native_hashes=hashes,
        old_apk_hashes={p.name:sha(p) for p in (archive/'apks').glob('*.apk')},
        old_package_sha256=sha(archive/'native/apk-contents.json'),build_commit=commit,build_reuse=build)
    for index, gate in enumerate(state['completed']):
        row = dict(rows[gate]);target = runner.directory/'logs'/f'targeting-reused-build-{index:02}.log'
        assert not target.exists();shutil.copyfile(source/row['log'],target)
        row.update(log=str(target.relative_to(runner.directory)),reused_from_run=source.name)
        runner.state['attempts'].append(row)
    for name in build['apk_hashes']: shutil.copyfile(source/'apks'/name,runner.directory/'apks'/name)
    shutil.copyfile(source/'native/apk-contents.json',runner.native/'apk-contents.json')
    proof['prepared'] = True


def install(runner, proof):
    root = Path(__file__).resolve().parents[2]
    receipt = validate_retained(root,runner.directory,proof)
    def adb(*args): return subprocess.check_output(['adb','-s',runner.serial,*map(str,args)],timeout=60)
    assert adb('shell','getprop','ro.kernel.qemu').strip() == b'1'
    assert adb('emu','avd','name').decode().splitlines()[0] == runner.state['avd_name']
    assert adb('shell','settings','get','global','airplane_mode_on').strip() == b'1'
    package = 'io.github.sussic.pyfa.dev'
    def installed_hash(name):
        path = adb('shell','pm','path',name).decode().strip().removeprefix('package:')
        assert path.startswith('/data/app/') and '\n' not in path
        return adb('shell','sha256sum',path).split()[0].decode()
    assert installed_hash(package) == proof['build_reuse']['apk_hashes']['app-debug.apk']
    adb('shell','am','force-stop',package)
    def graph(): return hashlib.sha256(adb('exec-out','run-as',package,'cat','no_backup/fits/graph.sqlite3')).hexdigest()
    assert graph() == receipt['partial_sha256'], 'Synthetic store changed since verified recovery capture'
    runner.execute('environment:targeting-test-update',['adb','-s',runner.serial,'install','-r','-t',runner.directory/'apks/app-debug-androidTest.apk'])
    assert installed_hash(package+'.test') == proof['build_reuse']['apk_hashes']['app-debug-androidTest.apk']
    assert graph() == receipt['partial_sha256'], 'Instrumentation installation changed the fit store'
    remote = '/data/local/tmp/pyfa-c032-targeting-recovered.sqlite3'
    adb('push',runner.directory/proof['archive']/'recovery/restored-graph.sqlite3',remote)
    adb('shell','run-as',package,'cp',remote,'no_backup/fits/graph.sqlite3');adb('shell','sync')
    assert graph() == receipt['restored_sha256']
    adb('shell','rm',remote);proof['installed'] = True