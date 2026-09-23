"""Require complete native variation parity, exact inputs and real restart."""
from copy import deepcopy
import json
from pathlib import Path
from market_summary import exact
from module_edit_summary import typed_compare

PREPARE = ['complete_matrix', 'all_5226_families', 'all_six_recipients', 'prior_fits_unchanged', 'picker_recreation',
    'charge_reconciliation', 'neighbour_retained', 'drone_pagination_search', 'distinct_stacks_quantities_order',
    'implant_activation_location', 'disabled_choices', 'empty_fit_refresh', 'independent_copy', 'atomic_rejections',
    'recent_unchanged', 'typed_protocol_guards']
RESTORED = ['fresh_process_restore', 'identities_inputs_values_retained', 'options_and_recent_retained', 'reopen_each_fit']
CODEC = ['decimal_index', 'decimal_revision', 'boolean_id', 'unknown_context', 'missing_targets', 'extra_field',
    'duplicate_target', 'duplicate_choice', 'nonboolean_enablement', 'invalid_state', 'wrong_current_fields',
    'drone_active_exceeds_total', 'unsupported_implant_location']


def summarize(reports, engine):
    fixture = json.loads((Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures/variation-edits.json').read_text())
    assert [report['phase'] for report in reports] == ['prepare', 'restored']
    assert len({report['pid'] for report in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B04.2.3.2'
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
    assert len(prepare['cases']) == len(fixture['cases']) == 17
    states = 0
    for expected, observed in zip(fixture['cases'], prepare['cases']):
        exact(expected['name'], observed['name'])
        assert len(expected['steps']) == len(observed['steps'])
        for row, actual in zip(expected['steps'], observed['steps']):
            exact(row['input'], actual['input']); exact(row['changed'], actual['changed'])
            result = deepcopy(row['result'])
            assert result['recent'] == []
            result['recent'] = prepare['recent_before']
            typed_compare(result, actual['result'])
            states += 1
    assert states == 55
    exact(fixture['families'], prepare['families'])
    assert len(prepare['families']) == 5226
    exact({'item_id': 33681, 'choices': 94, 'recreated_page': 1, 'previous_page': 0}, prepare['pagination'])
    paged = next(row for row in fixture['families'] if row['id'] == prepare['pagination']['item_id'])
    assert paged['context'] == 'drone' and len(paged['choices']) == prepare['pagination']['choices']
    exact(PREPARE, prepare['checks']); exact(RESTORED, restored['checks'])
    exact([{'label': 'wrong_family', 'code': 'INVALID_EDIT'}, {'label': 'disabled_hull', 'code': 'INVALID_EDIT'},
           {'label': 'unknown', 'code': 'INVALID_EDIT'}, {'label': 'stale', 'code': 'REVISION_CONFLICT'}], prepare['rejections'])
    exact(CODEC, prepare['codec_rejections'])
    exact(prepare['saved'], restored['saved'])
    exact(prepare['before'], prepare['saved']['prior']); exact(prepare['after'], prepare['saved']['fits'])
    exact(prepare['after'], restored['before']); exact(restored['before'], restored['after'])
    exact(prepare['options'], restored['options']); exact(prepare['options'], prepare['saved']['options'])
    exact(prepare['recent_after'], restored['recent_after'])
    before, after = prepare['before']['data'], prepare['after']['data']
    old_ids = {fit['id'] for fit in before}
    new = [fit for fit in after if fit['id'] not in old_ids]
    assert len(new) == 2 and len(after) == len(before) + 2
    exact(before, [fit for fit in after if fit['id'] in old_ids])
    assert len(set(prepare['saved']['new_ids'])) == 2
    exact(sorted(prepare['saved']['new_ids']), sorted(fit['id'] for fit in new))
    named = {fit['name']: fit for fit in new}
    source = named['B04 variations – 探索']; copied = named['B04 independent variation copy']
    assert source['modules'][0]['name'] == 'Dual 150mm Railgun I' and source['modules'][0]['charge'] is None
    assert source['modules'][1]['charge'] == 'Antimatter Charge M' and source['modules'][1]['state'] == 'OVERHEATED'
    assert copied['modules'][0]['name'] == 'Dual 150mm Railgun II' and copied['modules'][0]['charge'] is None
    for value, drone_name, implant_name in ((source, 'Hobgoblin II', "Eifyr and Co. 'Rogue' Navigation NN-605"),
                                          (copied, 'Hobgoblin I', "Eifyr and Co. 'Rogue' Navigation NN-601")):
        options = next(row for row in prepare['options'] if row['fit_id'] == value['id'])
        drones = [row for row in options['targets'] if row['context'] == 'drone']
        exact(['Hobgoblin II', drone_name], [row['name'] for row in drones])
        exact([{'amount': 4, 'active': 0}, {'amount': 5, 'active': 3}], [row['current'] for row in drones])
        implants = [row for row in options['targets'] if row['context'] == 'implant']
        assert len(implants) == 4
        implant = next(row for row in implants if row['name'] == implant_name)
        exact({'slot': 6, 'active': False, 'location': 'FIT'}, implant['current'])
        for name, active in [('Genolution Core Augmentation CA-1', False), ('Genolution Core Augmentation CA-2', True),
                             ('Genolution Core Augmentation CA-3', False)]:
            current = next(row['current'] for row in implants if row['name'] == name)
            assert current['active'] is active and current['location'] == 'FIT'
        assert len({row['current']['slot'] for row in implants}) == 4
    return {'cases': 17, 'states': states, 'variation_families': 5226, 'new_fits': 2,
            'restored_fits': len(after), 'protocol_rejections': len(CODEC), 'pagination': prepare['pagination'],
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
