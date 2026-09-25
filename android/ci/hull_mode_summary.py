"""Validate B06.1 native mode choices, desktop values and offline process restart."""
import json
from math import isclose
from pathlib import Path
from market_summary import exact

PREPARE = ['all_original_mode_states_and_choices', 'copy_keeps_selected_mode',
           'atomic_rejections', 'typed_mode_protocol']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
PROTOCOL = ['negative_request', 'wrong_current', 'duplicate_choice', 'extra_field']


def summarize(reports, engine):
    assert [row['phase'] for row in reports] == ['prepare', 'restored']
    assert len({row['pid'] for row in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B06.1'
        for stage in ('runtime_start', 'runtime_end'):
            runtime = report[stage]
            assert runtime['persistence']['enabled'] and runtime['persistence']['opened_existing']
            assert runtime['android_worker_thread'] == 'pyfa-engine'
            assert runtime['android_main_thread'] is False
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
    assert len(new) == len(old) + 5
    exact(old, {key: new[key] for key in old})
    ids = prepare['new_ids']
    assert len(ids) == len(set(ids)) == 5 and set(new) - set(old) == set(ids)
    exact(['B06.1 Confessor – 探索', 'B06.1 Jackdaw – 探索', 'B06.1 Anhinga – 探索',
           'B06.1 Vexor – 探索', 'B06.1 copied mode – Δ'], [new[key]['name'] for key in ids])
    exact(new[ids[0]]['stats'], new[ids[4]]['stats'])
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/hull-modes.json').read_text())
    assert len(fixture['cases']) == len(prepare['cases']) == 4
    total = 0
    for desktop, native in zip(fixture['cases'], prepare['cases']):
        exact(desktop['ship'], native['ship'])
        exact(desktop['choices'], native['choices'])
        assert len(desktop['steps']) == len(native['steps'])
        for left, right in zip(desktop['steps'], native['steps']):
            total += 1
            exact(left['requested'], right['requested'])
            exact(left['result']['mode_id'], right['current'])
            reference, actual = left['result']['stats'], right['stats']
            assert reference.keys() == actual.keys()
            for key, result in actual.items():
                expected = reference[key]
                exact(expected['unit'], result['unit'])
                a, b = expected['value'], result['value']
                if b is None and key in ('gun_optimal', 'gun_falloff'):
                    assert a in (0, 1), key
                elif type(a) in (int, float) and type(b) in (int, float):
                    assert isclose(a, b, rel_tol=1e-10, abs_tol=1e-9), key
                else:
                    exact(a, b)
    assert total == 16
    return {'cases': 4, 'states': 16, 'new_fits': 5, 'restored_fits': len(new),
            'screenshots': 4, 'protocol_rejections': len(PROTOCOL),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
