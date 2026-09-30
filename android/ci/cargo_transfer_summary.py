"""Validate B07.3 raw native transfers, atomic rejection and durable restart."""
from copy import deepcopy
import json
from pathlib import Path
from market_summary import exact
from cargo_stack_summary import state

PREPARE = ['fourteen_original_transfer_sequences', 'touch_move_copy_swap_selected_and_recreation',
    'atomic_desktop_failure_correction', 'durable_transfer_copies', 'atomic_rejections',
    'typed_transfer_protocol', 'captured_selection']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
PROTOCOL = ['wrong_version', 'extra_field', 'boolean_amount', 'negative_amount', 'unknown_slot',
    'duplicate_position', 'missing_charge_amount', 'missing_module_name', 'zero_revision', 'decimal_amount']


def transfer_state(expected, actual):
    exact(set(expected), set(actual))
    exact(expected['modules'], actual['modules'])
    left, right = deepcopy(expected), deepcopy(actual)
    for value in (left, right):
        value['cargo'].sort(key=lambda row: row['id'])
    state(left, right)


def summarize(reports, engine):
    assert len(reports) == 2
    prepare, restored = reports
    exact(['prepare', 'restored'], [report['phase'] for report in reports])
    assert prepare['pid'] != restored['pid']
    for report in reports:
        assert report['task'] == 'B07.3'
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
    exact([{'label': 'duplicate_positions', 'code': 'INVALID_REQUEST'},
           {'label': 'missing_stack', 'code': 'INVALID_EDIT'},
           {'label': 'invalid_destination', 'code': 'INVALID_EDIT'},
           {'label': 'stale', 'code': 'REVISION_CONFLICT'}], prepare['rejections'])
    exact([], restored['protocol_rejections']); exact([], restored['rejections']); exact([], restored['cases'])
    exact(prepare['saved']['fits'], prepare['after'])
    exact(prepare['after'], restored['before']); exact(restored['before'], restored['after'])
    exact(prepare['before'], prepare['saved']['prior'])
    exact(prepare['saved'], restored['saved'])
    old = {fit['id']: fit for fit in prepare['before']['data']}
    new = {fit['id']: fit for fit in prepare['after']['data']}
    assert len(old) == 57 and len(new) == 85
    exact(old, {key: new[key] for key in old})
    ids = prepare['new_ids']
    assert len(ids) == len(set(ids)) == 28 and set(new) - set(old) == set(ids)
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
        for index, module in enumerate(observed['data']['modules']):
            assert kinds[f'root.modules[{index}].index'] == 'integer'
            assert kinds[f'root.modules[{index}].charge_amount'] == 'integer'
            if module['id'] is not None:
                assert kinds[f'root.modules[{index}].id'] == 'integer'
            if module['charge_id'] is not None:
                assert kinds[f'root.modules[{index}].charge_id'] == 'integer'
        exact(prepare['recent_after'], observed['data']['recent'])
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/cargo-transfers.json').read_text())
    assert len(fixture['cases']) == len(prepare['cases']) == 14
    states = 0
    history = list(prepare['recent_before'])
    assert len(history) <= 20 and len(history) == len(set(history))
    for index, (original, native) in enumerate(zip(fixture['cases'], prepare['cases'])):
        exact(original['name'], native['name']); exact(original['ship'], native['ship'])
        exact(f"B07.3 {original['name']} – 探索", new[ids[2 * index]]['name'])
        exact(f"B07.3 copy {original['name']} – Δ", new[ids[2 * index + 1]]['name'])
        assert len(original['steps']) == len(native['steps'])
        # Setup uses market additions (or fits then transfers a structure module).
        # Only these setup actions promote recent use; every transfer preserves it.
        identities = {row['name']: row['id'] for row in original['steps'][0]['result']['cargo']}
        for row in original['cargo']:
            item_id = identities[row['name']]
            history = ([item_id] + [old for old in history if old != item_id])[:20]
        previous = original['steps'][0]['result']
        for desktop, result in zip(original['steps'], native['steps']):
            operation = desktop['operation']
            exact(operation, result['operation'])
            if operation is None:
                assert result['accepted'] is None
            else:
                position = operation.get('position', operation.get('positions', [0])[0])
                target = previous['modules'][position]
                noop = (operation['kind'] == 'to_cargo' and target['id'] is None or
                        operation['cargo_item_id'] is not None and
                        operation['cargo_item_id'] in (target['id'], target['charge_id']))
                accepted = desktop['changed'] or noop
                exact(accepted, result['accepted'])
                if accepted:
                    previous = desktop['result']
            transfer_state(previous, result['result'])
            exact(history, result['result']['recent'])
            states += 1
        end = deepcopy(native['steps'][-1]['result'])
        end['recent'] = prepare['recent_after']
        exact(end, saved_states[ids[2 * index]]['data'])
        exact(saved_states[ids[2 * index]], saved_states[ids[2 * index + 1]])
    assert states == 80
    for found in (prepare['recent_after'], prepare['saved']['recent'], restored['recent_before'], restored['recent_after']):
        exact(history, found)
    return {'cases': 14, 'states': states, 'new_fits': 28, 'restored_fits': len(new),
            'screenshots': 6, 'protocol_rejections': len(PROTOCOL),
            'checks': {'prepare': PREPARE, 'restored': RESTORED}}
