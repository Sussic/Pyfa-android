"""Validate B07.2 raw native actions, menu options and durable restart."""
from copy import deepcopy
import json
from pathlib import Path
from market_summary import exact
from cargo_stack_summary import state

PREPARE = ['five_original_cargo_action_sequences',
    'touch_selected_quantity_remove_presets_fill_and_variations', 'durable_cargo_copies',
    'atomic_rejections', 'typed_cargo_actions_protocol']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
PROTOCOL = ['wrong_version', 'extra_field', 'negative_fill', 'invalid_preset',
    'wrong_context', 'boolean_item', 'zero_revision', 'missing_fill']


def summarize(reports, engine):
    assert len(reports) == 2
    prepare, restored = reports
    exact(['prepare', 'restored'], [report['phase'] for report in reports])
    assert prepare['pid'] != restored['pid']
    for report in reports:
        assert report['task'] == 'B07.2'
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
            assert runtime['retained_fit_count'] == len(report['before' if stage == 'runtime_start' else 'after']['data'])
    assert prepare['runtime_end']['session_id'] != restored['runtime_start']['session_id']
    assert prepare['runtime_end']['persistence']['generation'] == restored['runtime_start']['persistence']['generation']
    assert restored['runtime_start']['persistence']['generation'] == restored['runtime_end']['persistence']['generation']
    exact(PREPARE, prepare['checks']); exact(RESTORED, restored['checks'])
    exact(PROTOCOL, prepare['protocol_rejections'])
    exact([{'label': 'duplicate_selection', 'code': 'INVALID_REQUEST'},
           {'label': 'missing_stack', 'code': 'INVALID_EDIT'},
           {'label': 'wrong_variation', 'code': 'INVALID_EDIT'},
           {'label': 'stale', 'code': 'REVISION_CONFLICT'}], prepare['rejections'])
    exact([], restored['protocol_rejections']); exact([], restored['rejections']); exact([], restored['cases'])
    exact(prepare['saved']['fits'], prepare['after'])
    exact(prepare['after'], restored['before']); exact(restored['before'], restored['after'])
    exact(prepare['before'], prepare['saved']['prior'])
    exact(prepare['saved'], restored['saved'])
    old = {fit['id']: fit for fit in prepare['before']['data']}
    new = {fit['id']: fit for fit in prepare['after']['data']}
    assert len(old) == 47 and len(new) == 57
    exact(old, {key: new[key] for key in old})
    ids = prepare['new_ids']
    assert len(ids) == len(set(ids)) == 10 and set(new) - set(old) == set(ids)
    exact(ids, restored['new_ids']); exact(ids, prepare['saved']['new_ids'])
    assert prepare['saved']['active_id'] == ids[-1]
    saved_states = prepare['saved']['cargo_states']
    assert set(saved_states) == set(ids)
    exact(saved_states, restored['restored_cargo'])
    for observed in saved_states.values():
        assert observed.keys() == {'data', 'numeric_types'}
        kinds = observed['numeric_types']
        assert kinds['root.used_m3'] == kinds['root.capacity_m3'] == 'decimal'
        for index, cargo in enumerate(observed['data']['cargo']):
            assert kinds[f'root.cargo[{index}].id'] == kinds[f'root.cargo[{index}].amount'] == 'integer'
            assert kinds[f'root.cargo[{index}].unit_volume_m3'] == 'decimal'
        exact(prepare['recent_after'], observed['data']['recent'])
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/cargo-actions.json').read_text())
    assert len(fixture['cases']) == len(prepare['cases']) == 5
    identities = {row['name']: row['id'] for case in fixture['cases']
                  for step in case['steps'] for row in step['result']['cargo']}
    states = 0
    history = list(prepare['recent_before'])
    assert len(history) <= 20 and len(history) == len(set(history))
    for index, (original, native) in enumerate(zip(fixture['cases'], prepare['cases'])):
        exact(original['name'], native['name']); exact(original['ship'], native['ship'])
        exact(f"B07.2 {original['name']} – 探索", new[ids[2 * index]]['name'])
        exact(f"B07.2 copy {original['name']} – Δ", new[ids[2 * index + 1]]['name'])
        assert len(original['steps']) == len(native['steps'])
        for desktop, result in zip(original['steps'], native['steps']):
            operation, outcome, options = desktop['operation'], desktop['outcome'], result['options']
            exact(operation, result['operation'])
            if operation is None:
                assert options is None
            else:
                kind = operation['kind']
                if kind in ('preset', 'fill_market', 'fill_cargo', 'variation'):
                    assert options is not None
                    exact(identities[operation.get('main', operation['item'])], options['item_id'])
                    exact(kind in ('fill_cargo', 'variation'), options['from_cargo'])
                    if kind == 'variation':
                        exact(outcome['variations'], options['variations'])
                    else:
                        expected = (outcome['submitted'][0]['quantity'] if outcome['submitted'] else
                                    0 if outcome['visible'] else None)
                        exact(expected, options['preset_quantity' if kind == 'preset' else 'fill_quantity'])
                else:
                    assert options is None
                # The independent original GUI command reports the actual IDs submitted.
                # History is global and the inherited native fits already have history.
                if kind in ('add', 'remove', 'preset', 'fill_market', 'fill_cargo'):
                    for command in outcome['submitted']:
                        for item_id in command['item_ids']:
                            history = ([item_id] + [value for value in history if value != item_id])[:20]
            state(desktop['result'], result['result'])
            exact(history, result['result']['recent'])
            states += 1
        end = deepcopy(native['steps'][-1]['result'])
        end['recent'] = prepare['recent_after']
        exact(end, saved_states[ids[2 * index]]['data'])
        exact(saved_states[ids[2 * index]], saved_states[ids[2 * index + 1]])
    assert states == 37
    for found in (prepare['recent_after'], prepare['saved']['recent'], restored['recent_before'], restored['recent_after']):
        exact(history, found)
    return {'cases': 5, 'states': states, 'new_fits': 10, 'restored_fits': len(new),
            'screenshots': 6, 'protocol_rejections': len(PROTOCOL),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
