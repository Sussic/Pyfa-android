"""Validate B06.2 native subsystem states, dynamic slots and offline restart."""
import json
from math import isclose
from pathlib import Path
from market_summary import exact

PREPARE = ['charged_launcher_retained_and_marked_illegal',
           'invalid_fit_copies_without_erasure', 'all_original_subsystem_states_and_choices',
           'atomic_rejections', 'typed_subsystem_protocol']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
PROTOCOL = ['negative_request', 'unknown_kind_request', 'wrong_current',
            'duplicate_group', 'wrong_capacity', 'extra_field']


def number(expected, actual, path):
    assert type(expected) in (int, float) and type(actual) in (int, float), path
    assert isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-9), (path, expected, actual)


def state(expected, actual, *, vacancies=True):
    left, right = expected['modules'], actual['modules']
    if not vacancies:
        left = [row for row in left if row['id'] is not None]
        right = [row for row in right if row['id'] is not None]
    exact(left, right)
    for field in ('slots', 'hardpoints'):
        assert len(expected[field]) == len(actual[field])
        for left, right in zip(expected[field], actual[field]):
            for key in left:
                if key == 'total': number(left[key], right[key], field + '.total')
                else: exact(left[key], right[key])
    exact(expected['resources'].keys(), actual['resources'].keys())
    for key, value in expected['resources'].items():
        number(value, actual['resources'][key], 'resources.' + key)
    assert expected['stats'].keys() == actual['stats'].keys()
    for key, value in expected['stats'].items():
        found = actual['stats'][key]
        exact(value['unit'], found['unit'])
        a, b = value['value'], found['value']
        if b is None and key in ('gun_optimal', 'gun_falloff'):
            assert a in (0, 1), key
        elif type(a) in (int, float) and type(b) in (int, float):
            number(a, b, 'stats.' + key)
        else: exact(a, b)


def summarize(reports, engine):
    assert [row['phase'] for row in reports] == ['prepare', 'restored']
    assert len({row['pid'] for row in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B06.2'
        for stage in ('runtime_start', 'runtime_end'):
            runtime = report[stage]
            assert runtime['persistence']['enabled'] and runtime['persistence']['opened_existing']
            assert runtime['android_worker_thread'] == 'pyfa-engine' and runtime['android_main_thread'] is False
            assert runtime['saveddata_connectionstring'] == 'sqlite:///:memory:'
            assert not runtime['desktop_import_attempts']
            exact(engine['eos_settings'], runtime['eos_settings'])
            for key in ('database_sha256', 'database_logical_sha256', 'engine_source_sha256',
                        'source_data_sha256', 'desktop_source_commit', 'dataset_metadata'):
                exact(engine[key], runtime['manifest'][key])
            assert runtime['retained_fit_count'] == len(report['before' if stage == 'runtime_start'
                                                                else 'after']['data'])
    assert prepare['runtime_end']['session_id'] != restored['runtime_start']['session_id']
    assert prepare['runtime_end']['persistence']['generation'] == restored['runtime_start']['persistence']['generation']
    assert restored['runtime_start']['persistence']['generation'] == restored['runtime_end']['persistence']['generation']
    exact(PREPARE, prepare['checks']); exact(RESTORED, restored['checks'])
    exact(PROTOCOL, prepare['protocol_rejections'])
    exact([{'label': 'cross_hull', 'code': 'INVALID_EDIT'},
           {'label': 'stale', 'code': 'REVISION_CONFLICT'}], prepare['rejections'])
    exact(prepare['saved']['fits'], prepare['after'])
    exact(prepare['after'], restored['before'])
    exact(restored['before'], restored['after'])
    exact(prepare['before'], prepare['saved']['prior'])
    old = {fit['id']: fit for fit in prepare['before']['data']}
    new = {fit['id']: fit for fit in prepare['after']['data']}
    assert len(old) == 34 and len(new) == 37
    exact(old, {key: new[key] for key in old})
    ids = prepare['new_ids']
    assert len(ids) == len(set(ids)) == 3 and set(new) - set(old) == set(ids)
    exact(['B06.2 Tengu – 探索', 'B06.2 invalid copy – Δ', 'B06.2 Vexor – 探索'],
          [new[key]['name'] for key in ids])
    assert prepare['saved']['invalid_id'] == ids[1]
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/subsystems.json').read_text())
    steps = fixture['cases'][0]['steps']
    assert len(steps) == len(prepare['steps']) == 14
    for index, (desktop, native) in enumerate(zip(steps, prepare['steps'])):
        exact(desktop['operation'], native['operation'])
        exact(desktop['accepted'], native['accepted'])
        state(desktop['result'], native['result'], vacancies=index not in (0, 13))
    illegal = prepare['steps'][8]['result']
    launcher = next(row for row in illegal['modules'] if row['name'] == 'Heavy Missile Launcher II')
    assert launcher['legal'] is False and launcher['charge'] == 'Scourge Heavy Missile'
    assert launcher['state'] == 'ACTIVE'
    assert next(row for row in illegal['slots'] if row['slot'] == 'HIGH')['total'] == 0
    return {'cases': 1, 'states': 14, 'hull_choices': 48, 'new_fits': 3,
            'restored_fits': len(new), 'screenshots': 6,
            'protocol_rejections': len(PROTOCOL),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
