"""Validate original module matrix, typed native observations and durable restart."""
import json
import math
from pathlib import Path
from market_summary import exact


def typed_compare(expected, observed, *, numeric_tolerance=True):
    assert observed.keys() == {'data', 'numeric_types'}
    kinds = {}
    def check(left, right, path):
        if type(left) is dict:
            assert type(right) is dict and left.keys() == right.keys(), path
            for key in left:
                check(left[key], right[key], path + '.' + key)
        elif type(left) is list:
            assert type(right) is list and len(left) == len(right), path
            for index, (a, b) in enumerate(zip(left, right)):
                check(a, b, f'{path}[{index}]')
        elif type(left) in (int, float):
            kinds[path] = 'integer' if type(left) is int else 'decimal'
            if type(left) is int:
                exact(left, right)
            else:
                assert type(right) in (int, float) and math.isfinite(right), path
                if numeric_tolerance:
                    assert math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9), path
                else:
                    assert left == right, path
        else:
            exact(left, right)
    check(expected, observed['data'], 'root')
    exact(kinds, observed['numeric_types'])


def summarize(reports, engine):
    fixture = json.loads((Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures/module-edits.json').read_text())
    assert [report['phase'] for report in reports] == ['prepare', 'restored']
    assert len({report['pid'] for report in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B04.2.2'
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
    assert prepare['runtime_end']['session_id'] != restored['runtime_start']['session_id']
    assert prepare['runtime_end']['persistence']['generation'] == restored['runtime_start']['persistence']['generation']
    assert restored['runtime_start']['persistence']['generation'] == restored['runtime_end']['persistence']['generation']
    assert len(prepare['cases']) == len(fixture['cases']) == 11
    steps = 0
    for expected, observed in zip(fixture['cases'], prepare['cases']):
        exact(expected['name'], observed['name'])
        assert len(expected['steps']) == len(observed['steps'])
        for row, result in zip(expected['steps'], observed['steps']):
            exact(row['input'], result['input'])
            exact(row['accepted'], result['accepted'])
            typed_compare(row['result'], result['result'])
            steps += 1
    assert steps == 91
    exact(fixture['default_states'], prepare['default_states'])
    assert len(prepare['default_states']) == 4242
    assert len(prepare['history']) == len(fixture['recent_history']) == 25
    for index, (row, observed) in enumerate(zip(fixture['recent_history'], prepare['history'])):
        exact(row['id'], observed['id'])
        assert type(observed['accepted']) is bool and len(observed['recent']) <= 20
        assert len(observed['recent']) == len(set(observed['recent']))
        if index >= 21:
            exact(row['result'], observed['recent'])
    exact(fixture['recent_history'][-1]['result'], prepare['recent'])
    exact(prepare['recent'], prepare['saved']['recent'])
    exact(prepare['recent'], prepare['saved']['recent_ui_ids'])
    exact(prepare['recent'], restored['recent'])
    assert fixture['abyssal_id'] not in prepare['recent']
    exact(prepare['before'], prepare['saved']['prior'])
    exact(prepare['after'], prepare['saved']['fits'])
    exact(prepare['details'], prepare['saved']['details'])
    exact(prepare['saved'], restored['saved'])
    exact(prepare['after'], restored['before'])
    exact(restored['before'], restored['after'])
    exact(prepare['details'], restored['details'])
    before = {fit['id']: fit for fit in prepare['before']['data']}
    after = {fit['id']: fit for fit in prepare['after']['data']}
    exact(before, {key: after[key] for key in before})
    new_ids = prepare['saved']['new_ids']
    assert len(new_ids) == len(set(new_ids)) == 3 and set(after) - set(before) == set(new_ids)
    ship, copied, structure = (after[key] for key in new_ids)
    assert [fit['ship'] for fit in (ship, copied, structure)] == ['Rifter', 'Rifter', 'Astrahus']
    assert prepare['saved']['active_id'] == copied['id']
    assert ship['modules'][7]['name'] == '200mm AutoCannon II'
    exact({'index': 7, 'empty_slot': 'HIGH'}, copied['modules'][7])
    assert not any(module.get('name') == 'Capital Armor Repairer I' for module in ship['modules'])
    assert any(module.get('name') == 'Large Shield Extender II' for module in ship['modules'])
    assert structure['modules'][14]['name'] == 'Standup Research Lab I'
    details = {fit['fit_id']: fit for fit in prepare['details']['data']}
    assert details[ship['id']]['resources']['powergrid']['overloaded'] is True
    assert details[ship['id']]['ignore_restrictions'] is False and details[ship['id']]['skill_warnings']
    exact([{'label': 'stale_revision', 'code': 'REVISION_CONFLICT'}, {'label': 'unknown_item', 'code': 'INVALID_EDIT'}], prepare['rejections'])
    exact(['resource_boolean', 'missing_resource_unit', 'wrong_resource_unit', 'vacancy_with_identity',
           'vacancy_with_legality', 'noncontiguous_position', 'missing_slot_totals', 'unknown_vacancy_slot',
           'mixed_vacant_fitted_shape', 'recent_boolean_id', 'recent_decimal_id', 'recent_duplicate', 'recent_over_limit'],
          prepare['codec_rejections'])
    for name in ('cases', 'default_states', 'history', 'rejections', 'codec_rejections'):
        exact([], restored[name])
    assert set(prepare['checks']) == {'complete_matrix', 'all_default_states', 'two_recipients', 'prior_fits_unchanged',
        'ui_add_replace_remove', 'vacant_position_reused', 'picker_recreation', 'resource_warning', 'skill_warning',
        'restriction_confirmation_recreation', 'override_reenable', 'independent_copy', 'structure_service_replacement',
        'twenty_recent_items', 'recent_order_visible', 'views_do_not_record_use', 'stale_unknown_atomic', 'typed_protocol_guards'}
    assert set(restored['checks']) == {'fresh_process_restore', 'identities_positions_states_values_retained',
                                     'recent_retained', 'reopen_each_fit'}
    return {'cases': 11, 'states': steps, 'default_module_states': 4242, 'history_attempts': 25,
            'recent_items': 20, 'retained_fits': len(after), 'new_fits': 3,
            'checks': {row['phase']: row['checks'] for row in reports}}
