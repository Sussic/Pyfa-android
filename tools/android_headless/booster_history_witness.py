"""Actual registered booster command reversals against the independent C03 oracle."""
from copy import deepcopy
from tools.android_reference.reference import compare, digest_file
from tools.android_headless.tests.test_contract import original_context_reference, original_booster_case


def witness(bridge, send, fixture_path):
    fixture = original_context_reference()
    compare('8b04f3b271e614b3e103853b44a7851a63d79d0e', fixture['sourceCommit'])
    case = original_booster_case()
    states = case['states']
    spec = deepcopy(case['spec']); spec['boosters'] = []
    key = send('create_fit', {'spec': spec})['fits'][0]['id']
    observations = []

    def observe(expected, operation):
        targets = [row for row in expected['targets'] if row['context'] != 'base']
        options = bridge.inspection_options(key)['targets']
        compare([(row['context'], row['item_id']) for row in targets],
                [(row['context'], row['item_id']) for row in options])
        for wanted, option in zip(targets, options):
            selected = {name: option[name] for name in ('context', 'index', 'item_id', 'object_key')}
            actual = bridge.inspection_details(key, selected)
            compare(wanted['attributes']['precise'],
                    [{name: row[name] for name in ('name', 'id', 'current', 'base', 'unit')}
                     for row in actual['attributes']['rows']])
        observations.append(dict(operation=operation, action=deepcopy(expected['action']),
                                 targets=len(targets), revision=bridge._revisions[key]))

    def command(operation, arguments, before_expected, after_expected, label):
        before = deepcopy(bridge._records[key])
        baseline = bridge.history_details(key)['undo_count']
        previous = bridge._revisions[key]
        send(operation, dict(fit_id=key, **arguments))
        compare(previous + 1, bridge._revisions[key])
        observe(after_expected, operation)
        after = deepcopy(bridge._records[key])
        for action, record, expected, undo, redo in (
                ('undo', before, before_expected['replayed'], baseline, 1),
                ('redo', after, after_expected['replayed'], baseline + 1, 0),
                ('undo', before, before_expected['replayed'], baseline, 1)):
            history = bridge.history_details(key)
            compare(label, history['undo_label'] if action == 'undo' else history['redo_label'])
            revision = bridge._revisions[key]
            send(action, dict(fit_id=key))
            compare(revision + 1, bridge._revisions[key]); compare(record, bridge._records[key])
            history = bridge.history_details(key)
            compare((undo, redo), (history['undo_count'], history['redo_count']))
            observe(expected, operation + '-' + action)

    removed = next(state for state in states if state['action']['kind'] == 'remove_booster')
    item_id = next(row['item_id'] for row in states[0]['targets'] if row['context'] == 'booster')
    command('add_booster', dict(item_id=item_id, active=True), removed, states[0], 'Add booster')
    send('redo', dict(fit_id=key))
    send('set_booster_active', dict(fit_id=key, position=0, active=True))
    observe(states[1]['replayed'], 'warm')
    inactive = next(state for state in states if state['action']['kind'] == 'set_booster_active')
    command('set_booster_active', dict(position=0, active=False), states[1], inactive, 'Change booster state')
    side = next(state for state in states if state['action']['kind'] == 'set_booster_side_effect')
    command('set_booster_side_effect', dict(position=0, effect_id=side['action']['effect_id'], active=True),
            states[1], side, 'Change booster side effect')
    command('remove_booster', dict(position=0), states[1], removed, 'Remove booster')
    operations = {row['operation'] for row in observations if '-' not in row['operation']} - {'warm'}
    compare({'add_booster', 'set_booster_active', 'set_booster_side_effect', 'remove_booster'}, operations)
    return dict(case=case['spec']['name'], fixture_sha256=digest_file(fixture_path),
                operations=sorted(operations), observations=observations, actual_command_reversals=True)
