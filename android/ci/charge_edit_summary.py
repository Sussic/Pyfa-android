"""Require complete native charge parity, typed values and durable restart."""
from copy import deepcopy
import json
from pathlib import Path
from market_summary import exact
from module_edit_summary import typed_compare

PREPARE = ['complete_matrix', 'all_4242_charge_sets', 'projection_and_command_recipients', 'prior_fits_unchanged',
    'picker_pagination_search', 'picker_recreation', 'load_replace_unload', 'neighbour_state_charge_retained',
    'script', 'laser_crystal', 'mining_crystal', 'active_fit_discovery', 'empty_fit_refresh', 'independent_copy',
    'rejections_atomic', 'recent_unchanged', 'typed_protocol_guards']
RESTORED = ['fresh_process_restore', 'identities_states_charges_values_retained', 'options_and_recent_retained', 'reopen_each_fit']


def summarize(reports, engine):
    fixture = json.loads((Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures/charge-edits.json').read_text())
    assert [report['phase'] for report in reports] == ['prepare', 'restored']
    assert len({report['pid'] for report in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B04.2.3.1'
        for stage in ('runtime_start', 'runtime_end'):
            runtime = report[stage]
            assert runtime['persistence']['enabled'] and runtime['persistence']['opened_existing']
            assert runtime['android_worker_thread'] == 'pyfa-engine' and runtime['android_main_thread'] is False
            assert runtime['saveddata_connectionstring'] == 'sqlite:///:memory:' and not runtime['desktop_import_attempts']
            typed_compare(fixture['eos_settings'], {'data': runtime['eos_settings'],
                'numeric_types': runtime['eos_settings_numeric_types']}, numeric_tolerance=False)
            exact(engine['eos_settings'], runtime['eos_settings'])
            for key in ('database_sha256', 'database_logical_sha256', 'engine_source_sha256', 'source_data_sha256',
                        'desktop_source_commit', 'dataset_metadata'):
                exact(engine[key], runtime['manifest'][key])
            assert runtime['retained_fit_count'] == len(report['before' if stage == 'runtime_start' else 'after']['data'])
        exact(report['recent_before'], report['recent_after'])
    assert prepare['runtime_end']['session_id'] != restored['runtime_start']['session_id']
    assert prepare['runtime_end']['persistence']['generation'] == restored['runtime_start']['persistence']['generation']
    assert restored['runtime_start']['persistence']['generation'] == restored['runtime_end']['persistence']['generation']
    assert len(prepare['cases']) == len(fixture['cases']) == 14
    states = 0
    for expected, observed in zip(fixture['cases'], prepare['cases']):
        exact(expected['name'], observed['name'])
        assert len(expected['steps']) == len(observed['steps'])
        for row, actual in zip(expected['steps'], observed['steps']):
            exact(row['input'], actual['input'])
            exact(row['changed'], actual['changed'])
            result = deepcopy(row['result'])
            assert result['recent'] == []  # The desktop matrix begins with empty history.
            result['recent'] = prepare['recent_before']  # Same unchanged-history transition with prior native data.
            typed_compare(result, actual['result'])
            states += 1
    assert states == 74
    exact(fixture['compatibility'], prepare['compatibility'])
    assert len(prepare['compatibility']) == 4242
    exact(PREPARE, prepare['checks'])
    exact(RESTORED, restored['checks'])
    exact([{'label': 'incompatible', 'code': 'INVALID_EDIT'}, {'label': 'unknown', 'code': 'INVALID_EDIT'},
           {'label': 'stale', 'code': 'REVISION_CONFLICT'}], prepare['rejections'])
    exact(['decimal_id', 'decimal_revision', 'boolean_id', 'negative_revision', 'missing_items', 'extra_field',
           'noncontiguous_position', 'duplicate_charge', 'incorrect_union', 'vacancy_with_charge', 'decimal_compatibility'],
          prepare['codec_rejections'])
    exact(prepare['saved'], restored['saved'])
    exact(prepare['before'], prepare['saved']['prior'])
    exact(prepare['after'], prepare['saved']['fits'])
    exact(prepare['after'], restored['before'])
    exact(restored['before'], restored['after'])
    exact(prepare['options'], restored['options'])
    exact(prepare['options'], prepare['saved']['options'])
    exact(prepare['recent_after'], restored['recent_after'])
    before = prepare['before']['data']
    after = prepare['after']['data']
    ids = {fit['id'] for fit in before}
    new = [fit for fit in after if fit['id'] not in ids]
    assert len(new) == 4 and len(after) == len(before) + 4
    exact(before, [fit for fit in after if fit['id'] in ids])
    assert len(set(prepare['saved']['new_ids'])) == 4
    exact(sorted(prepare['saved']['new_ids']), sorted(fit['id'] for fit in new))
    named = {fit['name']: fit for fit in new}
    source = named['B04 charge picker – 探索']
    assert source['modules'][0]['charge'] == 'Javelin M'
    assert source['modules'][1]['charge'] == 'Iron Charge M' and source['modules'][1]['state'] == 'OVERHEATED'
    assert source['modules'][2]['charge'] == 'Tracking Speed Script'
    assert named['B04 laser crystal']['modules'][0]['charge'] == 'Scorch S'
    assert named['B04 mining crystal']['modules'][0]['charge'] == 'Simple Asteroid Mining Crystal Type B II'
    assert named['B04 independent charge copy']['modules'][0]['charge'] is None
    return {'cases': 14, 'states': states, 'module_compatibility_sets': 4242, 'new_fits': 4,
            'restored_fits': len(after), 'protocol_rejections': 11, 'checks': {'prepare': PREPARE, 'restored': RESTORED}}
