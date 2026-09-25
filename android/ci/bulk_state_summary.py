"""Require every native bulk-state comparison and durable process restart."""
from copy import deepcopy
import json
from pathlib import Path
from market_summary import exact
from module_edit_summary import typed_compare

PREPARE = ['complete_matrix', 'all_four_recipients', 'prior_fits_unchanged',
    'selection_recreation', 'similar_outside_selection', 'selected_only', 'supported_fallbacks',
    'empty_fit', 'stale_selection_discarded', 'fit_switch', 'independent_copy',
    'atomic_rejections', 'recent_unchanged', 'typed_protocol_guards']
RESTORED = ['fresh_process_restore', 'identities_inputs_values_retained',
    'state_types_and_recent_retained', 'reopen_each_fit']
CODEC = ['decimal_index', 'decimal_revision', 'boolean_id', 'invalid_state',
         'duplicate_candidate', 'decimal_candidate', 'missing_reference', 'missing_click', 'extra_field']


def summarize(reports, engine):
    fixture = json.loads((Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures/bulk-states.json').read_text())
    assert [report['phase'] for report in reports] == ['prepare', 'restored']
    assert len({report['pid'] for report in reports}) == 2
    prepare, restored = reports
    for report in reports:
        assert report['task'] == 'B05.2'
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
    assert len(prepare['cases']) == len(fixture['cases']) == 6
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
    assert states == 27
    exact(PREPARE, prepare['checks']); exact(RESTORED, restored['checks'])
    exact([{'label': label, 'code': code} for label, code in (
        ('vacancy', 'INVALID_EDIT'), ('missing_reference', 'INVALID_EDIT'), ('duplicate', 'INVALID_REQUEST'),
        ('negative', 'INVALID_REQUEST'), ('out_of_range', 'INVALID_EDIT'), ('stale', 'REVISION_CONFLICT'))],
        prepare['rejections'])
    exact(CODEC, prepare['codec_rejections'])
    exact(prepare['saved'], restored['saved'])
    exact(prepare['before'], prepare['saved']['prior']); exact(prepare['after'], prepare['saved']['fits'])
    exact(prepare['after'], restored['before']); exact(restored['before'], restored['after'])
    exact(prepare['options'], restored['options']); exact(prepare['options'], prepare['saved']['options'])
    exact(prepare['recent_after'], restored['recent_after']); exact(prepare['recent_before'], prepare['saved']['recent'])
    before, after = prepare['before']['data'], prepare['after']['data']
    old_ids = {fit['id'] for fit in before}
    new = [fit for fit in after if fit['id'] not in old_ids]
    assert len(new) == 2 and len(after) == len(before) + 2
    exact(before, [fit for fit in after if fit['id'] in old_ids])
    assert len(set(prepare['saved']['new_ids'])) == 2
    exact(sorted(prepare['saved']['new_ids']), sorted(fit['id'] for fit in new))
    named = {fit['name']: fit for fit in new}
    source = named['B05 bulk states – 探索']; copied = named['B05 independent state copy']
    assert prepare['saved']['active_id'] == source['id']
    for value in (source, copied):
        exact(['150mm Light AutoCannon II', '150mm Light AutoCannon II', '200mm AutoCannon II'],
              [row['name'] for row in value['modules'][:3]])
    exact(['ONLINE', 'OVERHEATED', 'OVERHEATED'], [row['state'] for row in source['modules'][:3]])
    assert copied['modules'][0]['state'] != source['modules'][0]['state']
    for report in reports:
        raw = report['options']
        expected_kinds = {}
        for i, fit in enumerate(raw['data']):
            expected_kinds[f'root[{i}].revision'] = 'integer'
            for j, row in enumerate(fit['modules']):
                prefix = f'root[{i}].modules[{j}]'
                for key in ('index', 'item_id'):
                    if row[key] is not None: expected_kinds[f'{prefix}.{key}'] = 'integer'
                for k in range(len(row['similar_candidates'])):
                    expected_kinds[f'{prefix}.similar_candidates[{k}]'] = 'integer'
        exact(expected_kinds, raw['numeric_types'])
    return {'cases': 6, 'states': states, 'recipients': 4, 'new_fits': 2,
            'restored_fits': len(after), 'protocol_rejections': len(CODEC),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
