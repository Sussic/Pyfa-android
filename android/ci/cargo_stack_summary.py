"""Validate B07.1 native cargo reports against independent desktop states."""
import json
from math import isclose
from pathlib import Path
from market_summary import exact

PREPARE = ['two_original_cargo_sequences', 'touch_add_set_partial_remove_and_over_capacity',
           'durable_cargo_copy', 'atomic_rejections', 'typed_cargo_protocol']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
PROTOCOL = ['duplicate_stack', 'zero_amount', 'negative_volume',
            'wrong_over', 'wrong_version', 'extra_field']


def number(expected, actual, path):
    assert type(expected) in (int, float) and type(actual) in (int, float), path
    assert isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-9), (path, expected, actual)


def state(expected, actual):
    assert len(expected['cargo']) == len(actual['cargo'])
    for left, right in zip(expected['cargo'], actual['cargo']):
        for key in ('id', 'name', 'amount'):
            exact(left[key], right[key])
        number(left['unit_volume_m3'], right['unit_volume_m3'], 'unit cargo volume')
    number(expected['used_m3'], actual['used_m3'], 'cargo used')
    number(expected['capacity_m3'], actual['capacity_m3'], 'cargo capacity')
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
        assert report['task'] == 'B07.1'
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
    exact([{'label': 'zero_quantity', 'code': 'INVALID_REQUEST'},
           {'label': 'structure_module', 'code': 'INVALID_EDIT'},
           {'label': 'stale', 'code': 'REVISION_CONFLICT'}], prepare['rejections'])
    exact(prepare['saved']['fits'], prepare['after'])
    exact(prepare['after'], restored['before'])
    exact(restored['before'], restored['after'])
    exact(prepare['before'], prepare['saved']['prior'])
    old = {fit['id']: fit for fit in prepare['before']['data']}
    new = {fit['id']: fit for fit in prepare['after']['data']}
    assert len(old) == 44 and len(new) == 47
    exact(old, {key: new[key] for key in old})
    ids = prepare['new_ids']
    assert len(ids) == len(set(ids)) == 3 and set(new) - set(old) == set(ids)
    exact(['B07.1 Vexor – 探索', 'B07.1 Astrahus – 探索', 'B07.1 cargo copy – Δ'],
          [new[key]['name'] for key in ids])
    assert prepare['saved']['copy_id'] == ids[2]
    assert set(prepare['saved']['cargo_states']) == set(ids)
    exact(prepare['saved']['cargo_states'], restored['restored_cargo'])
    for observed in prepare['saved']['cargo_states'].values():
        assert observed.keys() == {'data', 'numeric_types'}
        kinds = observed['numeric_types']
        assert kinds['root.used_m3'] == kinds['root.capacity_m3'] == 'decimal'
        for index, cargo in enumerate(observed['data']['cargo']):
            assert kinds[f'root.cargo[{index}].id'] == 'integer'
            assert kinds[f'root.cargo[{index}].amount'] == 'integer'
            assert kinds[f'root.cargo[{index}].unit_volume_m3'] == 'decimal'
    # These are all native reports: retain exact nulls and numeric kinds.
    # Only the independent desktop comparison below maps its absent gun defaults.
    exact(prepare['cases'][0]['steps'][-1]['result'], prepare['saved']['cargo_states'][ids[0]]['data'])
    exact(prepare['cases'][1]['steps'][-1]['result'], prepare['saved']['cargo_states'][ids[1]]['data'])
    exact(prepare['saved']['cargo_states'][ids[0]], prepare['saved']['cargo_states'][ids[2]])
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/cargo-stacks.json').read_text())
    assert len(fixture['cases']) == len(prepare['cases']) == 2
    states = 0
    for original, native in zip(fixture['cases'], prepare['cases']):
        exact(original['ship'], native['ship'])
        assert len(original['steps']) == len(native['steps'])
        for desktop, result in zip(original['steps'], native['steps']):
            exact(desktop['operation'], result['operation'])
            exact(desktop['accepted'], result['accepted'])
            state(desktop['result'], result['result'])
            states += 1
    assert states == 17
    number(500, prepare['cases'][0]['steps'][-2]['result']['used_m3'], 'over-capacity Vexor')
    number(480, prepare['cases'][0]['steps'][-2]['result']['capacity_m3'], 'Vexor capacity')
    number(2.5, prepare['cases'][1]['steps'][1]['result']['used_m3'], 'structure charge volume')
    number(0, prepare['cases'][1]['steps'][1]['result']['capacity_m3'], 'structure capacity')
    return {'cases': 2, 'states': states, 'new_fits': 3, 'restored_fits': len(new),
            'screenshots': 6, 'protocol_rejections': len(PROTOCOL),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
