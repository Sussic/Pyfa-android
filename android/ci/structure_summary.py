"""Validate B06.3 native structure services against pinned desktop states."""
import json
from math import isclose
from pathlib import Path
from market_summary import exact

PREPARE = ['five_original_structure_sequences', 'service_bonus_copy',
           'atomic_rejections', 'typed_structure_service_protocol']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
PROTOCOL = ['duplicate_choice', 'wrong_flag', 'negative_capacity',
            'wrong_version', 'extra_field', 'wrong_boolean']


def number(expected, actual, path):
    assert type(expected) in (int, float) and type(actual) in (int, float), path
    assert isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-9), (path, expected, actual)


def state(expected, actual, *, vacancies=True):
    left, right = expected['modules'], actual['modules']
    if not vacancies:
        # Original failed adds may rearrange empty dummies; bridge rejection
        # deliberately leaves the saved graph unchanged.
        left = [row for row in left if row['id'] is not None]
        right = [row for row in right if row['id'] is not None]
    exact(left, right)
    for left, right in zip(expected['slots'], actual['slots']):
        exact(left['slot'], right['slot'])
        exact(left['used'], right['used'])
        number(left['total'], right['total'], 'slot total')
    assert len(expected['slots']) == len(actual['slots']) == 5
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
    assert [report['phase'] for report in reports] == ['prepare', 'restored']
    assert len({report['pid'] for report in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B06.3'
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
    exact([{'label': 'ship_standup', 'code': 'INVALID_EDIT'},
           {'label': 'stale', 'code': 'REVISION_CONFLICT'}], prepare['rejections'])
    exact(prepare['saved']['fits'], prepare['after'])
    exact(prepare['after'], restored['before'])
    exact(restored['before'], restored['after'])
    exact(prepare['before'], prepare['saved']['prior'])
    old = {fit['id']: fit for fit in prepare['before']['data']}
    new = {fit['id']: fit for fit in prepare['after']['data']}
    assert len(old) == 37 and len(new) == 44
    exact(old, {key: new[key] for key in old})
    ids = prepare['new_ids']
    assert len(ids) == len(set(ids)) == 7 and set(new) - set(old) == set(ids)
    exact(['B06.3 Astrahus – 探索', 'B06.3 Fortizar – 探索',
           'B06.3 Athanor – 探索', 'B06.3 Ansiblex Jump Bridge – 探索',
           'B06.3 Metenox Moon Drill – 探索', 'B06.3 structure copy – Δ',
           'B06.3 Vexor – 探索'], [new[key]['name'] for key in ids])
    assert prepare['saved']['copy_id'] == ids[5]
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/structures.json').read_text())
    assert len(fixture['cases']) == len(prepare['cases']) == 5
    states = 0
    for original, native in zip(fixture['cases'], prepare['cases']):
        exact(original['ship'], native['ship'])
        assert len(original['steps']) == len(native['steps'])
        for index, (desktop, result) in enumerate(zip(original['steps'], native['steps'])):
            exact(desktop['operation'], result['operation'])
            exact(desktop['accepted'], result['accepted'])
            state(desktop['result'], result['result'], vacancies=index > 0 and desktop['accepted'])
            states += 1
    assert states == 27
    astrahus = prepare['cases'][0]['steps']
    number(3600000, astrahus[0]['result']['stats']['shield_hp']['value'], 'Astrahus base shield HP')
    number(14400000, astrahus[1]['result']['stats']['shield_hp']['value'], 'Astrahus service shield HP')
    number(7200000, astrahus[1]['result']['stats']['armor_hp']['value'], 'Astrahus service armor HP')
    ansiblex = prepare['cases'][3]['steps']
    number(500000, ansiblex[0]['result']['stats']['shield_hp']['value'], 'Ansiblex base shield HP')
    number(2000000, ansiblex[1]['result']['stats']['shield_hp']['value'], 'Ansiblex service shield HP')
    number(500000, ansiblex[-1]['result']['stats']['shield_hp']['value'], 'Ansiblex restored shield HP')
    return {'cases': 5, 'states': states, 'desktop_hulls': 19,
            'desktop_service_choices': 118,
            'new_fits': 7, 'restored_fits': len(new), 'screenshots': 7,
            'protocol_rejections': len(PROTOCOL),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
