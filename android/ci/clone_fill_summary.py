"""Require native B05.3 touch, EOS outcomes and real offline process restart."""
import json
from pathlib import Path
from market_summary import exact


PREPARE = ['selection_recreation', 'selected_positions_states_charges',
           'targeted_vacancy', 'fitted_source_fill', 'market_touch_preview_stop_history',
           'linked_recipient', 'atomic_rejections', 'typed_fill_preview']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
CODEC = ['decimal_item', 'unknown_slot', 'negative_vacancies', 'extra_field',
         'boolean_vacancy_index', 'subsystem_vacancy', 'duplicate_vacancy']


def summarize(reports, engine):
    assert [report['phase'] for report in reports] == ['prepare', 'restored']
    assert len({report['pid'] for report in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B05.3'
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
    exact(CODEC, prepare['codec_rejections'])
    exact([{'label': label, 'code': code} for label, code in (
        ('duplicate', 'INVALID_REQUEST'), ('vacancy', 'INVALID_EDIT'),
        ('out_of_range', 'INVALID_EDIT'), ('stale', 'REVISION_CONFLICT'))],
        prepare['rejections'])
    exact(prepare['saved'], restored['saved'])
    exact(prepare['after'], prepare['saved']['fits'])
    exact(prepare['after'], restored['before'])
    exact(restored['before'], restored['after'])
    exact(prepare['saved']['recent'], restored['recent_after'])
    exact(prepare['saved']['prior'], prepare['before'])
    old = {fit['id']: fit for fit in prepare['before']['data']}
    new = {fit['id']: fit for fit in prepare['after']['data']}
    assert len(new) == len(old) + 5
    exact(old, {key: new[key] for key in old})
    ids = prepare['saved']['new_ids']
    assert len(ids) == len(set(ids)) == 5 and set(new) - set(old) == set(ids)
    selected, filled, market, source, target = (new[key] for key in ids)
    exact(['B05 selected clone – 探索', 'B05 fitted source fill', 'B05 market fill',
           'B05 projected fill', 'B05 projected receiver'],
          [fit['name'] for fit in (selected, filled, market, source, target)])
    exact([0, 1, 11, 12], [row['index'] for row in prepare['selected']['fitted']])
    exact(['OVERHEATED', 'ACTIVE', 'OVERHEATED', 'ACTIVE'],
          [row['state'] for row in prepare['selected']['fitted']])
    exact(['Antimatter Charge M', 'Iron Charge M',
           'Antimatter Charge M', 'Iron Charge M'],
          [row['charge'] for row in prepare['selected']['fitted']])
    assert len(prepare['filled']['fitted']) == 4
    assert all(row['state'] == 'OVERHEATED' and row['charge'] == 'Antimatter Charge M'
               for row in prepare['filled']['fitted'])
    assert [row['id'] for row in prepare['market']['fitted']] == [2048]
    assert prepare['recent_after'][0] == 2048
    assert prepare['recipient']['before'] != prepare['recipient']['after']
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/clone-fill.json').read_text())
    projected = fixture['cases'][-1]['steps'][-1]['result']['recipients'][0]['stats']
    native = prepare['recipient']['after']
    assert projected.keys() == native.keys()
    for key, value in projected.items():
        if native[key]['value'] is None and key in ('gun_optimal', 'gun_falloff'):
            assert value['value'] in (0, 1)
            exact(value['unit'], native[key]['unit'])
        else:
            from math import isclose
            left, right = value['value'], native[key]['value']
            exact(value['unit'], native[key]['unit'])
            if type(left) in (int, float) and type(right) in (int, float):
                assert isclose(left, right, rel_tol=1e-10, abs_tol=1e-9), key
            else:
                exact(left, right)
    return {'new_fits': 5, 'restored_fits': len(new), 'screenshots': 8,
            'protocol_rejections': len(CODEC),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
