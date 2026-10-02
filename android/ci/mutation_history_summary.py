"""Strict B09.2 raw-result validation; no assertion-only or fixture-hash shortcuts."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile
from market_summary import exact
from math import isclose, isfinite

PREPARE = ['original_matrix', 'touch_repeated_reversals', 'single_action_grouping', 'recipient_ownership']
RESTORED = ['fresh_process_restore', 'all_session_history_empty', 'all_new_inputs_retained', 'reopen_every_fit']
ZERO = dict(undo_count=0, redo_count=0, can_undo=False, can_redo=False)


def settings(expected, actual):
    # JSONObject writes the whole-valued double 1.0 as 1. Only this setting's
    # representation may differ; its numeric value must still match exactly.
    exact(set(expected), set(actual))
    for key, value in expected.items():
        other = actual[key]
        if key == 'globalDefaultSpoolupPercentage':
            assert type(value) is float and type(other) in (int, float)
            assert isfinite(value) and isfinite(other) and value == other
        else: exact(value, other)


def _typed_shape(value):
    # B09.1's shape is intentionally limited to modules/statistics. Remaining
    # mutations also contain decimal projection ranges and linked statistics.
    exact({'data', 'numeric_types'}, set(value))
    paths = {}
    def walk(row, path):
        if type(row) is dict:
            for key, entry in row.items(): walk(entry, path + '.' + key)
        elif type(row) is list:
            for index, entry in enumerate(row): walk(entry, f'{path}[{index}]')
        elif type(row) in (int, float): paths[path] = row
    walk(value['data'], 'root')
    exact(set(paths), set(value['numeric_types']))
    for path, number in paths.items():
        kind = value['numeric_types'][path]
        assert kind in ('integer', 'decimal') and isfinite(number)
        if kind == 'integer': assert type(number) is int and -(2**63) <= number < 2**63
        if path.endswith('.range_m'): exact('decimal', kind)
        elif '.stats.' not in path and '.linked_stats.' not in path: exact('integer', kind)


def stats(expected, actual):
    exact(set(expected), set(actual))
    for name, row in expected.items():
        other = actual[name]; exact(row['unit'], other['unit'])
        a, b = row['value'], other['value']
        if name in ('gun_optimal', 'gun_falloff') and b is None and a in (0, 1): continue
        if type(a) in (int, float) and type(b) in (int, float):
            assert isclose(a, b, rel_tol=1e-10, abs_tol=1e-9), (name, a, b)
        else: exact(a, b)


def projection_inputs(expected, actual, kinds):
    # JSONObject renders integral Double metres as JSON integers. Require the
    # retained decimal kind and lossless exact value; all other fields stay typed.
    exact(len(expected), len(actual))
    for index, (left, right) in enumerate(zip(expected, actual)):
        exact(set(left), set(right))
        for key, value in left.items():
            other = right[key]
            if key == 'range_m':
                exact('decimal', kinds[f'root.projections[{index}].range_m'])
                assert type(value) is float and type(other) in (int, float)
                assert isfinite(value) and isfinite(other) and float(other) == other
                exact(value, float(other))
            else: exact(value, other)


def state(case, step, observed, recent):
    _typed_shape(observed)
    actual = observed['data']; wanted = deepcopy(step['result'])
    operation = case['operation']
    if operation in ('add_implant', 'remove_implant'): top = []
    elif operation == 'remove_cargo': top = [] if step['action'] == 'initial' else [case['arguments']['item_id']]
    else: top = wanted['recent']
    wanted['recent'] = (top + [key for key in recent if key not in top])[:20]
    exact(set(wanted), set(actual))
    def input_kinds(value, path):
        if type(value) is dict:
            for key, row in value.items():
                if key not in ('stats', 'linked_stats'): input_kinds(row, path + '.' + key)
        elif type(value) is list:
            for index, row in enumerate(value): input_kinds(row, f'{path}[{index}]')
        elif type(value) in (int, float):
            exact('integer' if type(value) is int else 'decimal', observed['numeric_types'].get(path))
    input_kinds(wanted, 'root')
    for field in wanted:
        if field in ('stats', 'linked_stats') and wanted[field] is not None: stats(wanted[field], actual[field])
        elif field == 'projections': projection_inputs(wanted[field], actual[field], observed['numeric_types'])
        else: exact(wanted[field], actual[field])


def same_state(left, right):
    for field in left['data']:
        if field != 'recent': exact(left['data'][field], right['data'][field])
    exact({k: v for k, v in left['numeric_types'].items() if not k.startswith('root.recent[')},
        {k: v for k, v in right['numeric_types'].items() if not k.startswith('root.recent[')})


def fixture_bytes():
    root = Path(__file__).resolve().parents[2]
    reference = (root / 'tools/android_reference/fixtures/history-mutations.json').read_bytes()
    test_apk = Path(os.environ.get('PYFA_INSTRUMENTATION_APK',
        str(root / 'android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk')))
    with ZipFile(test_apk) as apk: packaged = apk.read('assets/history-mutations-expected.json')
    assert packaged.replace(b'\r\n', b'\n') == reference.replace(b'\r\n', b'\n')
    return json.loads(reference), hashlib.sha256(packaged).hexdigest()


def validate_fixture(report, digest):
    assert type(report['fixture_sha256']) is str and len(report['fixture_sha256']) == 64
    exact(digest, report['fixture_sha256'])


def recent_case(expected, observed):
    exact({'owner_id', 'other_id', 'recent_before', 'steps'}, set(observed))
    assert observed['owner_id'] != observed['other_id']
    exact(5, len(observed['steps']))
    for step, actual in zip(expected['steps'], observed['steps']):
        exact(step['action'], actual['action'])
        exact({'action', 'owner', 'other', 'owner_history', 'other_history'}, set(actual))
        for side in ('owner', 'other'):
            state({'operation': 'add_cargo'}, {'action': step['action'], 'result': step[side]},
                actual[side], observed['recent_before'])
            exact(step[side + '_history'], actual[side + '_history'])
    same_state(observed['steps'][0]['owner'], observed['steps'][2]['owner'])
    same_state(observed['steps'][1]['owner'], observed['steps'][4]['owner'])


def summarize(reports, engine, prior, complete=True):
    fixture, fixture_hash = fixture_bytes()
    exact(28, len(fixture['cases']))
    assert len(reports) in (2, 4, 6, 8)
    if complete: exact(8, len(reports))
    groups = len(reports) // 2
    assert all(type(r['pid']) is int and r['pid'] > 0 for r in reports)
    settings(fixture['eos_settings'], engine['eos_settings'])
    assert len({r['pid'] for r in reports}) == len(reports)
    assert not {r['pid'] for r in reports} & {r['pid'] for r in prior}
    previous = prior[-1]['after']; previous_recent = prior[-1]['recent_after']
    accumulated, states = set(), 0
    for group in range(groups):
        prepare, restored = reports[group * 2:group * 2 + 2]
        exact(['prepare', 'restored'], [r['phase'] for r in (prepare, restored)])
        for report in (prepare, restored):
            exact('B09.2', report['task']); exact(group, report['group'])
            validate_fixture(report, fixture_hash)
            for value in (report['before'], report['after']): _typed_shape(value)
            for stage in ('runtime_start', 'runtime_end'):
                runtime = report[stage]
                exact(True, runtime['persistence']['enabled']); exact(True, runtime['persistence']['opened_existing'])
                assert runtime['android_worker_thread'] == 'pyfa-engine' and runtime['android_main_thread'] is False
                assert runtime['saveddata_connectionstring'] == 'sqlite:///:memory:'
                exact([], runtime['desktop_import_attempts'])
                assert type(runtime['persistence']['generation']) is int and runtime['persistence']['generation'] > 0
                exact(engine['eos_settings'], runtime['eos_settings'])
                for key in ('database_sha256', 'database_logical_sha256', 'engine_source_sha256',
                    'source_data_sha256', 'desktop_source_commit', 'dataset_metadata'):
                    exact(engine[key], runtime['manifest'][key])
                exact(fixture['source_commit'], runtime['manifest']['desktop_source_commit'])
                exact(fixture['database_logical_sha256'], runtime['manifest']['database_logical_sha256'])
                exact(len(report['before' if stage == 'runtime_start' else 'after']['data']), runtime['retained_fit_count'])
        exact(previous, prepare['before']); exact(previous_recent, prepare['recent_before'])
        exact(prepare['after'], restored['before']); exact(restored['before'], restored['after'])
        exact(prepare['saved'], restored['saved'])
        saved = prepare['saved']; exact(group, saved['group'])
        exact(prepare['before'], saved['prior']); exact(prepare['after'], saved['fits'])
        for value in (prepare['recent_after'], restored['recent_before'], restored['recent_after']): exact(saved['recent'], value)
        assert prepare['runtime_end']['session_id'] != restored['runtime_start']['session_id']
        generation = prepare['runtime_end']['persistence']['generation']
        assert generation > prepare['runtime_start']['persistence']['generation']
        exact(generation, restored['runtime_start']['persistence']['generation'])
        exact(generation, restored['runtime_end']['persistence']['generation'])
        checks = PREPARE + (['cargo_selection_safety'] if group == 0 else [])
        if group == 1: checks += ['interleaved_recent_repromoted']
        checks += ['notes_preserved', 'history_recreation']
        if group == 2: checks += ['transfer_selection_safety']
        if group == 3: checks += ['copy_history_empty', 'stale_rejected', 'deleted_source_not_revived']
        exact(checks, prepare['checks']); exact(RESTORED, restored['checks'])
        exact([], restored['cases']); exact({}, restored['observations']); exact({}, prepare['restored_inputs'])
        old = {r['id']: r for r in prepare['before']['data']}; new = {r['id']: r for r in prepare['after']['data']}
        assert len(old) == (111 if group == 0 else len(previous['data']))
        exact(old, {key: new[key] for key in old})
        created, deleted = saved['created_ids'], saved['deleted_ids']
        assert len(created) == len(set(created)) and not set(created) & set(old)
        exact(set(created) - set(deleted), set(new) - set(old))
        exact(set(saved['all_ids']), set(new)); assert len(saved['all_ids']) == len(new)
        assert not deleted if group != 3 else len(deleted) == 1
        accumulated.update(created); accumulated.difference_update(deleted)
        exact(accumulated, set(saved['persisted_states']))
        exact(saved['persisted_states'], restored['restored_inputs'])
        for value in saved['persisted_states'].values(): _typed_shape(value)
        expected_cases = fixture['cases'][group * 7:(group + 1) * 7]
        exact(7, len(prepare['cases'])); expected_histories = {key: ZERO for key in old}
        case_ids, source_ids = [], []
        for case, observed in zip(expected_cases, prepare['cases']):
            exact(case['name'], observed['name']); key, source = observed['fit_id'], observed['source_id']
            assert key in created and key not in case_ids; case_ids.append(key)
            baseline = len(case['spec'].get('cargo', [])) + len(case['spec']['implants']) + int(case['setup_link'])
            exact(baseline, observed['baseline_undo'])
            if case['source_spec'] is None: exact(None, source)
            else:
                assert source in created and source not in source_ids; source_ids.append(source)
                expected_histories[source] = ZERO
            exact(6, len(observed['steps']))
            previous_revision = None
            for step, actual in zip(case['steps'], observed['steps']):
                exact(step['action'], actual['action'])
                state(case, step, actual['result'], observed['recent_before'])
                done = step['action'] in ('do', 'redo'); redo = int(step['action'] == 'undo')
                count = baseline + int(done)
                exact(dict(undo_count=count, redo_count=redo, can_undo=count > 0, can_redo=redo > 0), actual['history'])
                if source: exact(ZERO, actual['source_history'])
                else: exact(None, actual['source_history'])
                before, after = actual['revision_before'], actual['revision_after']
                assert type(before) is int and type(after) is int and before > 0
                assert after == before if step['action'] == 'initial' else after > before
                if previous_revision is not None: exact(previous_revision, before)
                previous_revision = after; states += 1
            for index in (2, 4): same_state(observed['steps'][0]['result'], observed['steps'][index]['result'])
            for index in (3, 5): same_state(observed['steps'][1]['result'], observed['steps'][index]['result'])
            expected_histories[key] = dict(undo_count=baseline + 1, redo_count=0, can_undo=True, can_redo=False)
            if source and source not in deleted:
                stats(observed['steps'][-1]['result']['data']['linked_stats'], new[source]['stats'])
        exact(case_ids[0], saved['active_id'])
        observation = prepare['observations']
        wanted_observations = set()
        if group == 0:
            wanted_observations.add('cargo_selection_after_redo'); exact([], observation['cargo_selection_after_redo'])
        recent_ids = []
        if group == 1:
            wanted_observations.add('recent_case')
            row = observation['recent_case']; recent_case(fixture['interleaved_recent'], row)
            recent_ids = [row['owner_id'], row['other_id']]
            assert len(set(recent_ids)) == 2 and not set(recent_ids) & set(case_ids + source_ids)
            for side, key in zip(('owner', 'other'), recent_ids):
                assert key in created
                expected_histories[key] = row['steps'][-1][side + '_history']
                same_state(row['steps'][-1][side], saved['persisted_states'][key])
        if group == 2:
            wanted_observations.add('module_selection_after_undo'); exact([], observation['module_selection_after_undo'])
        if group == 3:
            wanted_observations.update(('copy_id', 'copy_history', 'stale_error_code', 'stale_before', 'stale_after', 'stale_history_before',
                'stale_history_after', 'deleted_source', 'recipient_after_delete', 'copy_after_delete',
                'recipient_history_after_delete', 'copy_history_after_delete'))
            copy_id = observation['copy_id']; assert copy_id in created and copy_id not in case_ids + source_ids
            exact(ZERO, observation['copy_history']); expected_histories[copy_id] = ZERO
            exact('REVISION_CONFLICT', observation['stale_error_code'])
            exact(observation['stale_before'], observation['stale_after'])
            exact(observation['stale_history_before'], observation['stale_history_after'])
            exact(expected_histories[case_ids[0]], observation['stale_history_before'])
            exact([source_ids[0]], deleted); exact(deleted[0], observation['deleted_source'])
            expected_histories.pop(deleted[0]); expected_histories[case_ids[0]] = ZERO
            for label, id_ in (('recipient', case_ids[0]), ('copy', copy_id)):
                exact(ZERO, observation[label + '_history_after_delete'])
                value = observation[label + '_after_delete']; _typed_shape(value)
                stats(expected_cases[0]['steps'][0]['result']['stats'], value['data']['stats'])
                exact([], value['data']['projections']); exact([], new[id_]['projections'])
            exact('B09.2 independent link copy — Δ', new[copy_id]['name'])
        exact(wanted_observations, set(observation))
        exact(set(case_ids + source_ids + recent_ids + ([observation['copy_id']] if group == 3 else [])), set(created))
        exact(expected_histories, prepare['histories'])
        exact({key: ZERO for key in new}, restored['histories'])
        previous, previous_recent = restored['after'], restored['recent_after']
    exact(42 * groups, states)
    if complete: exact(147, len(previous['data']))
    return dict(reference_cases=7 * groups, reference_states=states, groups=groups, process_executions=len(reports),
        complete=complete, new_retained_fits=len(accumulated), restored_fits=len(previous['data']),
        screenshots=21 if complete else None, interleaved_recent_steps=5 if groups >= 2 else 0, fixture_sha256=fixture_hash)
