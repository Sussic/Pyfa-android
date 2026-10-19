"""Independent complete-context payload and fresh native restart validation."""
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
from pathlib import Path
import re

from inspection_canonical_summary import decode, properties, PROTOCOL, sql_roles, metadata, ATTRIBUTE
from inspection_identity_summary import attributes, original
from inspection_links_summary import flatten
from inspection_record_identity import graph_identities
from defense_summary import typed, fit_inputs
from market_summary import exact
from mutation_history_summary import settings

TABLES = dict(ship='ship', mode='mode', module='modules', charge='modules',
              drone='drones', fighter='fighters', cargo='cargo', implant='implants', booster='boosters')
COUNTS = ((8, 48, 200), (25, 239, 906), (25, 175, 650), (25, 175, 650), (24, 168, 624))


def state_inputs(case, expected, record):
    """Original current members, quantities and flags constrain every saved input."""
    spec = deepcopy(case['spec']); spec['implants'] = []; spec['boosters'] = []
    spec['modules'] = deepcopy(expected['module_inputs'])
    spec['ignore_restrictions'] = expected['ignore_restrictions']
    if 'fighters' not in record['spec']:
        exact([], spec.pop('fighters', []))
    modes = [target['item_id'] for target in expected['targets'] if target['context'] == 'mode']
    assert len(modes) <= 1
    mode = modes[0] if modes else None
    if mode is not None: spec['mode'] = mode
    else: spec.pop('mode', None)
    def property_value(target, name):
        matches = [row['contract'] for row in target['properties'] if row['contract']['name'] == name]
        exact(1, len(matches)); exact(True, matches[0]['available']); return matches[0]['value']
    cargo, implants, boosters = [], [], []
    for target in expected['targets']:
        family = target['context']; identity = target['item_id']
        if family not in ('cargo', 'implant', 'booster'): continue
        table = TABLES[family]
        matches = [row for row in expected['roles'][table] if row['itemID'] == identity]
        exact(1, len(matches)); row = matches[0]
        name = property_value(target, 'item')['name']
        if family == 'cargo': cargo.append(dict(name=name, amount=row['amount']))
        elif family == 'implant': implants.append(dict(name=name, slot=property_value(target, 'slot'), active=bool(row['active'])))
        else:
            flags = [dict(effect_id=effect['effectID'], active=bool(effect['active']))
                     for effect in expected['roles']['booster_side_effects'] if effect['boosterID'] == row['ID']]
            boosters.append(dict(name=name, slot=property_value(target, 'slot'), active=bool(row['active']), side_effects=flags))
    spec['cargo'] = cargo
    fit_inputs(spec, record['spec']); exact({}, record['skills']); exact(implants, record['implants'])
    exact([], record['projections']); exact([], record['commands'])
    fields = {'spec', 'skills', 'implants', 'projections', 'commands', 'inspection_ids'}
    if boosters: fields.add('boosters'); exact(boosters, record['boosters'])
    exact(fields, set(record))


def context_roles(expected, actual, selected_mode=None):
    core = ('fit', 'modules', 'drones', 'fighters')
    exact(set(core) | {'cargo', 'implants', 'boosters', 'booster_side_effects', 'mode'}, set(actual))
    sql_roles({key: expected[key] for key in core}, {key: actual[key] for key in core})
    booster_ids = {}
    for table in ('cargo', 'implants', 'boosters'):
        exact(len(expected[table]), len(actual[table])); seen = set()
        for before in expected[table]:
            matches = [row for row in actual[table] if row['itemID'] == before['itemID']]
            exact(1, len(matches)); after = matches[0]
            identity = after['ID']; assert type(identity) is int and identity > 0 and identity not in seen
            seen.add(identity)
            translated = deepcopy(before); translated['ID'] = identity
            if 'fitID' in before:
                exact(expected['fit'][0]['ID'], before['fitID']); translated['fitID'] = actual['fit'][0]['ID']
            exact(translated, after)
            if table == 'boosters': booster_ids[before['ID']] = identity
    effects = deepcopy(expected['booster_side_effects'])
    for row in effects: row['boosterID'] = booster_ids[row['boosterID']]
    exact(effects, actual['booster_side_effects'])
    exact(1, len(expected['mode'])); exact(1, len(actual['mode']))
    mode = deepcopy(expected['mode'])
    if mode[0]['modeID'] is None and actual['mode'][0]['modeID'] is not None:
        assert type(selected_mode) is int and selected_mode > 0
        exact(selected_mode, actual['mode'][0]['modeID']); mode[0]['modeID'] = selected_mode
    exact(mode, actual['mode'])


def sequence(case, restored_phase=None):
    states = case['states']
    if restored_phase: return [(restored_phase, states[-1]['replayed'], False)]
    result = [('construction', states[0], True), ('initial', states[1], True)]
    edited = None
    for state in states[2:]:
        kind = state['action']['kind']
        restored = kind.startswith('reverse') and not (kind == 'reverse_remove' and case['family'] == 'booster')
        result.append((kind, state['replayed'] if restored else state, True))
        if kind.startswith('reverse'):
            if not (kind == 'reverse_remove' and case['family'] == 'booster'):
                assert edited is not None
                result.extend([(kind + '-redo', edited['replayed'], False), (kind + '-undo', state['replayed'], False)])
        elif kind != 'recreated':
            edited = state
            if kind == 'remove_booster':
                result.extend([('remove-undo', states[-1]['replayed'], False), ('remove-redo', state['replayed'], False)])
    result.append(('copy', states[-1]['replayed'], False))
    return result


def raw_reference(expected, actual, fit_id, record, before, after, selections):
    rows = []
    for expected_row in expected:
        row = deepcopy(expected_row)
        exact(before['fit'][0]['ID'], row['source_fit_id'])
        exact(before['fit'][0]['name'], row['source_fit_name'])
        row['source_fit_id'], row['source_fit_key'] = after['fit'][0]['ID'], fit_id
        source = row.pop('source_role')
        if source is not None:
            matches = [selection for selection in selections if selection['context'] == source['context'] and selection['item_id'] == source['item_id']]
            exact(1, len(matches)); source = matches[0]
            if row['source_id'] is not None:
                table = TABLES[source['context']]
                key = 'groupID' if table in ('drones', 'fighters') else 'ID'
                def member(roles):
                    values = [value for value in roles[table] if value['chargeID' if source['context'] == 'charge' else 'itemID'] == source['item_id']]
                    exact(1, len(values)); return values[0]
                exact(member(before)[key], row['source_id']); row['source_id'] = member(after)[key]
        row['source_target'] = source; rows.append(row)
    exact(len(rows), len(actual))
    for expected_row, actual_row in zip(rows, actual):
        exact(set(expected_row), set(actual_row))
        for key in expected_row:
            if key in ('before', 'after', 'stacking'): original(expected_row[key], actual_row[key])
            else: exact(expected_row[key], actual_row[key])


def validate(state, payload_path, fixture):
    exact({'pids', 'fits', 'phase', 'cases', 'observations', 'original_states', 'original_targets',
           'payload_sha256', 'graph', 'all_fits', 'runtime_start'}, set(state))
    match = re.fullmatch(r'contexts([0-4])(?:-restored([12]))?', state['phase']); assert match
    part, restart = int(match[1]), int(match[2] or 0)
    expected_cases, expected_states, expected_targets = COUNTS[part]
    exact(expected_cases, state['cases']); exact(0 if restart else expected_states, state['original_states'])
    exact(0 if restart else expected_targets, state['original_targets'])
    pids = state['pids']; assert len(pids) == restart + 1 and len(pids) == len(set(pids))
    assert all(type(pid) is int and pid > 0 for pid in pids)
    exact('8b04f3b271e614b3e103853b44a7851a63d79d0e', fixture['sourceCommit'])
    exact('5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607', fixture['databaseLogicalSha256'])
    exact(107, len(fixture['cases']))
    runtime = typed(state['runtime_start'])
    exact(fixture['sourceCommit'], runtime['manifest']['desktop_source_commit'])
    exact(fixture['databaseLogicalSha256'], runtime['manifest']['database_logical_sha256'])
    exact('pyfa-engine', runtime['android_worker_thread']); exact(False, runtime['android_main_thread'])
    exact([], runtime['desktop_import_attempts']); exact(True, runtime['persistence']['enabled'])
    if restart: exact(True, runtime['persistence']['opened_existing'])
    settings(fixture['eos_settings'], runtime['eos_settings'])
    initial_graph = typed(runtime['context_initial_graph'])
    if not restart:
        exact(True, runtime['persistence']['opened_existing'])
        exact(dict(format=2, dataset_identity=fixture['databaseLogicalSha256'],
                   eos_settings=fixture['eos_settings'], sample_id=None, fit_order=[],
                   records={}, revisions={}, modified={}), initial_graph)
    else:
        exact(typed(state['graph']), initial_graph)

    directory = Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures'
    item_fixture = decode((directory / 'inspector-context-metadata.json').read_bytes())
    for key in ('sourceCommit', 'databaseLogicalSha256', 'eos_settings'): exact(fixture[key], item_fixture[key])
    items = {row['item_id']: row for row in item_fixture['items']}; exact(127, len(items))
    inventory = decode((directory / 'inspector-inventory.json').read_bytes())
    definitions = {row[0]: row for row in inventory['attributes']}
    for key in ('sourceCommit', 'databaseLogicalSha256'): exact(fixture[key], inventory[key])
    final_graph, final_fits = typed(state['graph']), typed(state['all_fits'])
    graph_identities(final_graph['records'])
    exact(set(final_graph['records']), {fit['id'] for fit in final_fits})
    low, high = (0, 8) if part == 0 else (8 + (part - 1) * 25, min(107, 8 + part * 25))
    exact({str(index) for index in range(low, high)}, set(state['fits']))
    digest = hashlib.sha256(); count = 0; original_states = 0; original_targets = 0; contexts = Counter()
    with Path(payload_path).open('rb') as stream:
        for case_index in range(low, high):
            case = fixture['cases'][case_index]; fit_id = state['fits'][str(case_index)]
            assert fit_id in final_graph['records']
            copy_id = None
            for label, expected, is_original in sequence(case, state['phase'] if restart else None):
                raw = stream.readline(); assert raw.endswith(b'\n'); digest.update(raw); observation = decode(raw)
                exact({'case_index', 'observation', 'fit_id', 'pid', 'sql_roles', 'graph', 'targets'}, set(observation))
                exact(case_index, observation['case_index']); exact(label, observation['observation']); exact(pids[-1], observation['pid'])
                actual_id = observation['fit_id']; graph = typed(observation['graph']); graph_identities(graph['records'])
                if label == 'copy':
                    assert actual_id != fit_id and actual_id not in final_graph['records']; copy_id = actual_id
                    left, right = deepcopy(graph['records'][fit_id]), deepcopy(graph['records'][copy_id])
                    original_keys, copy_keys = left.pop('inspection_ids'), right.pop('inspection_ids')
                    exact(left, right); exact(set(original_keys), set(copy_keys))
                    originals = [value for values in original_keys.values() for value in values]
                    copies = [value for values in copy_keys.values() for value in values]
                    assert not set(originals) & set(copies)
                    exact([len(values) for values in original_keys.values()], [len(copy_keys[key]) for key in original_keys])
                else: exact(fit_id, actual_id)
                record = graph['records'][actual_id]
                state_inputs(case, expected, record)
                modes = [target['item_id'] for target in expected['targets'] if target['context'] == 'mode']
                assert len(modes) <= 1
                context_roles(expected['roles'], observation['sql_roles'], modes[0] if modes else None)
                wanted, actual_targets = expected['targets'], observation['targets']
                exact(len(wanted), len(actual_targets))
                decoded = [typed(value) for value in actual_targets]
                selections = [value['selection'] for value in decoded if value['selection']['context'] != 'base']
                assert len(selections) == len({(value['context'], value['index']) for value in selections})
                for original_target, actual in zip(wanted, decoded):
                    exact(PROTOCOL, set(actual)); exact(1, actual['version'])
                    selection = actual['selection']; family = original_target['context']; item_id = original_target['item_id']
                    exact(family, selection['context']); exact(item_id, selection['item_id']); exact(item_id, actual['item']['id'])
                    if family == 'base':
                        exact({'context', 'index', 'item_id'}, set(selection)); exact(None, selection['index'])
                        exact(None, actual['fit_id']); exact(None, actual['revision'])
                    else:
                        exact({'context', 'index', 'item_id', 'object_key'}, set(selection))
                        position = selection['index']; assert type(position) is int and position >= 0
                        exact(record['inspection_ids'][TABLES[family]][position], selection['object_key'])
                        exact(actual_id, actual['fit_id']); exact(graph['revisions'][actual_id], actual['revision'])
                    attributes({'expected': original_target['attributes'], 'equipment': original_target['equipment']}, actual)
                    normal = {row['name']: row for row in original_target['attributes']['normal']}
                    for row in actual['attributes']['rows']:
                        exact(ATTRIBUTE, set(row)); known = row['id'] is not None
                        exact(known, row['metadata']); exact(row['name'] in normal, row['normal'])
                        if known:
                            info = definitions[row['id']]; exact(info[1], row['name']); exact(bool(info[3]), row['published'])
                        else: exact(False, row['published']); exact(row['name'], row['label'])
                        for field in ('current', 'base'): exact(normal[row['name']][field] if row['name'] in normal else None, row['display_' + field])
                    original(original_target['equipment'], actual['equipment'])
                    original(properties(original_target['properties'], selection, expected['roles'], observation['sql_roles'], TABLES), actual['properties'])
                    for view in ('source', 'attribute'): original(original_target['affector_views'][view], flatten(actual['affector_views'][view]))
                    raw_reference(original_target['affectors'], actual['affectors'], actual_id, record,
                                  expected['roles'], observation['sql_roles'], selections)
                    metadata(items[item_id], actual)
                    contexts[family] += 1
                count += 1
                if is_original: original_states += 1; original_targets += len(wanted)
        exact(b'', stream.read(1))
    exact(state['payload_sha256'], digest.hexdigest()); exact(state['observations'], count)
    exact(state['original_states'], original_states); exact(state['original_targets'], original_targets)
    return dict(phase=state['phase'], cases=expected_cases, observations=count, contexts=dict(contexts),
                original_states=original_states, original_targets=original_targets, pids=pids,
                fresh_native_observations=True, payload_sha256=digest.hexdigest())


def load_fixture():
    path = Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures/inspector-contexts.json.gz'
    return decode(gzip.decompress(path.read_bytes()))


def validate_restores(states, payload_paths, fixture):
    exact(3, len(states)); exact(3, len(payload_paths))
    result = [validate(state, path, fixture) for state, path in zip(states, payload_paths)]
    part = states[0]['phase']; assert re.fullmatch(r'contexts[0-4]', part)
    exact([part, part + '-restored1', part + '-restored2'], [state['phase'] for state in states])
    for index in (1, 2):
        for key in ('graph', 'all_fits', 'fits'): exact(states[0][key], states[index][key])
        exact(states[index - 1]['pids'], states[index]['pids'][:-1])
        assert states[index - 1]['payload_sha256'] != states[index]['payload_sha256']
    return result
