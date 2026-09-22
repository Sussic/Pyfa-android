"""Validate complete empty-hull native values, scalar types and process persistence."""
import json
import math
from pathlib import Path
from market_summary import exact


def stats(expected, snapshot):
    actual, types = snapshot['stats'], snapshot['scalar_types']
    assert expected.keys() == actual.keys() == types.keys()
    for name, stat in expected.items():
        value = stat['value']
        observed = actual[name]
        assert observed.keys() == {'value', 'unit'} and observed['unit'] == stat['unit']
        assert types[name] == {int: 'integer', float: 'decimal', bool: 'boolean', str: 'text', type(None): 'null'}[type(value)]
        # The Android report writer normalizes integral decimals; the DTO's wire
        # type is retained separately. Integers, bools and absent values are exact.
        if type(value) is float:
            assert type(observed['value']) in (int, float) and math.isfinite(observed['value'])
            assert math.isclose(value, observed['value'], rel_tol=1e-10, abs_tol=1e-9), name
        else:
            exact(value, observed['value'])


def summarize(reports, engine):
    fixture = json.loads((Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures/empty-hulls.json').read_text(encoding='utf-8'))
    assert [row['phase'] for row in reports] == ['prepare', 'restored']
    assert len({row['pid'] for row in reports}) == 2
    expected = {row['id']: row for row in fixture['hulls']}
    by_name = {row['name']: row for row in fixture['hulls']}
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B04.2.1'
        for stage in ('runtime_start', 'runtime_end'):
            runtime = report[stage]
            assert runtime['persistence']['enabled'] and runtime['persistence']['opened_existing']
            assert runtime['android_worker_thread'] == 'pyfa-engine' and runtime['android_main_thread'] is False
            assert runtime['saveddata_connectionstring'] == 'sqlite:///:memory:' and not runtime['desktop_import_attempts']
            assert fixture['eos_settings'] == runtime['eos_settings']
            exact(engine['eos_settings'], runtime['eos_settings'])
            for key in ('database_sha256', 'database_logical_sha256', 'engine_source_sha256', 'source_data_sha256', 'desktop_source_commit', 'dataset_metadata'):
                exact(engine[key], runtime['manifest'][key])
            assert runtime['retained_fit_count'] == len(report['before' if stage == 'runtime_start' else 'after'])
    assert prepare['runtime_end']['session_id'] != restored['runtime_start']['session_id']
    assert prepare['runtime_end']['persistence']['generation'] == restored['runtime_start']['persistence']['generation']
    assert restored['runtime_start']['persistence']['generation'] == restored['runtime_end']['persistence']['generation']
    assert len(prepare['hulls']) == len(expected) == 437
    exact(sorted(expected), sorted(row['hull_id'] for row in prepare['hulls']))
    for row in prepare['hulls']:
        golden = expected[row['hull_id']]
        exact(golden['category'], row['category'])
        exact(golden['name'], row['fit']['ship'])
        for key in ('modules', 'implants', 'projections', 'commands'):
            exact([], row['fit'][key])
        stats(golden['stats'], row['fit'])
    assert not restored['hulls'] and not restored['rejections']
    exact(prepare['saved'], restored['saved'])
    exact(prepare['after'], restored['before'])
    exact(restored['before'], restored['after'])
    exact(prepare['after'], prepare['saved']['fits'])
    exact(prepare['before'], prepare['saved']['prior'])
    before = {row['id']: row for row in prepare['before']}
    after = {row['id']: row for row in prepare['after']}
    exact(before, {id: after[id] for id in before})
    new_ids = prepare['saved']['new_ids']
    assert len(set(new_ids)) == 3 and set(after) - set(before) == set(new_ids)
    assert prepare['saved']['active_id'] == new_ids[1]
    exact(['探索 Δ empty Rifter', 'B04 renamed empty copy', 'B04 empty Astrahus'], [after[id]['name'] for id in new_ids])
    exact(['Rifter', 'Rifter', 'Astrahus'], [after[id]['ship'] for id in new_ids])
    exact([1, 2, 1], [after[id]['revision'] for id in new_ids])
    for id in new_ids:
        fit = after[id]
        stats(by_name[fit['ship']]['stats'], fit)
        for key in ('modules', 'implants', 'projections', 'commands'):
            exact([], fit[key])
    exact(['non_hull', 'unknown_hull', 'empty_charge_index', 'empty_state_index', 'stale_revision'],
          [row['label'] for row in prepare['rejections']])
    for row in prepare['rejections']:
        assert row['code'] == ('REVISION_CONFLICT' if row['label'] == 'stale_revision' else 'INVALID_EDIT')
        exact(prepare['after'], row['fits'])
    assert set(prepare['checks']) == {'complete_hulls', 'prior_fits_unchanged', 'picker_pagination', 'picker_search_and_empty',
        'picker_recreation', 'blank_name_rejected', 'ship_creation', 'independent_copy', 'hull_browser_structure_creation',
        'cancel_unchanged', 'failed_edits_unchanged', 'explicit_absence'}
    assert set(restored['checks']) == {'fresh_process_restore', 'identities_inputs_values_retained', 'reopen_each_fit', 'explicit_absence'}
    return {'hulls': len(expected), 'ships': sum(row['category'] == 'Ship' for row in expected.values()),
        'structures': sum(row['category'] == 'Structure' for row in expected.values()), 'statistics_per_hull': 39,
        'restart_fits': len(after), 'new_empty_fits': len(new_ids), 'rejected_edits': len(prepare['rejections']),
        'checks': {row['phase']: row['checks'] for row in reports}}
