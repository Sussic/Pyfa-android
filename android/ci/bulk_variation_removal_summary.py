"""Validate retained B05.4 native touch and real offline restart reports."""
import json
from math import isclose
from pathlib import Path
from market_summary import exact


PREPARE = ['selected_family_skip_recreation_charge', 'similar_cross_family_outside_selection',
           'selected_removal_reverse_history', 'empty_and_fit_switch', 'atomic_rejections',
           'typed_bulk_requests']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
PROTOCOL = ['empty_selection', 'duplicate_selection', 'negative_position', 'negative_item',
            'negative_family_candidate', 'duplicate_family_candidate', 'missing_family_row',
            'asymmetric_family', 'extra_family_field']


def summarize(reports, engine):
    assert [report['phase'] for report in reports] == ['prepare', 'restored']
    assert len({report['pid'] for report in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B05.4'
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
    exact([{'label': 'out_of_range', 'code': 'INVALID_EDIT'},
           {'label': 'wrong_family', 'code': 'INVALID_EDIT'},
           {'label': 'stale', 'code': 'REVISION_CONFLICT'}], prepare['rejections'])
    exact(prepare['saved'], restored['saved'])
    exact(prepare['after'], prepare['saved']['fits'])
    exact(prepare['after'], restored['before'])
    exact(restored['before'], restored['after'])
    exact(prepare['saved']['recent'], restored['recent_after'])
    exact(prepare['saved']['prior'], prepare['before'])
    old = {fit['id']: fit for fit in prepare['before']['data']}
    new = {fit['id']: fit for fit in prepare['after']['data']}
    assert len(new) == len(old) + 4
    exact(old, {key: new[key] for key in old})
    ids = prepare['new_ids']
    assert len(ids) == len(set(ids)) == 4 and set(new) - set(old) == set(ids)
    mixed, similar, removal, empty = (new[key] for key in ids)
    exact(['B05.4 mixed selected – 探索', 'B05.4 related similar', 'B05.4 selected removal',
           'B05.4 empty'], [fit['name'] for fit in (mixed, similar, removal, empty)])
    exact(['Dual 150mm Railgun I', 'Dual 150mm Railgun I', '200mm Railgun II', 'Sensor Booster I'],
          [row['name'] for row in prepare['results']['mixed']])
    assert prepare['results']['mixed'][0]['charge'] is None
    exact(['Dual 150mm Railgun II'] * 3, [row['name'] for row in prepare['results']['similar']])
    exact(['Sensor Booster I'], [row['name'] for row in prepare['results']['removal']])
    exact([3106, 2048], prepare['recent_after'][:2])
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/bulk-variation-removal.json').read_text())
    desktop = {case['name']: case['steps'][-1]['result']['stats'] for case in fixture['cases']}
    for native, name in ((mixed, 'mixed-family-selected-variation'),
                         (similar, 'related-variant-similar-variation'),
                         (removal, 'selected-removal-history')):
        left, right = desktop[name], native['stats']
        assert left.keys() == right.keys()
        for key, result in right.items():
            expected = left[key]
            exact(expected['unit'], result['unit'])
            a, b = expected['value'], result['value']
            if b is None and key in ('gun_optimal', 'gun_falloff'):
                assert a in (0, 1), key
            elif type(a) in (int, float) and type(b) in (int, float):
                assert isclose(a, b, rel_tol=1e-10, abs_tol=1e-9), key
            else:
                exact(a, b)
    return {'new_fits': 4, 'restored_fits': len(new), 'screenshots': 8,
            'protocol_rejections': len(PROTOCOL),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
