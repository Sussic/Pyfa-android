"""Validate every retained canonical inspector target against pinned expectations.

This validates preparation payloads and their unchanged persisted bytes. Native
restart assertions are required separately; retained preparation bytes alone do
not prove that the restarted worker produced matching observations.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import gzip
import json
from pathlib import Path
from market_summary import exact
from defense_summary import typed, fit_inputs
from inspection_identity_summary import attributes, original
from inspection_links_summary import flatten
from inspection_record_identity import graph_identities

COUNTS = dict(base=362, ship=152, module=142, charge=40, drone=28, fighter=2)
PROTOCOL = {'version', 'fit_id', 'revision', 'selection', 'item', 'attributes',
            'effects', 'affectors', 'properties', 'equipment', 'variations', 'stack', 'affector_views'}
ATTRIBUTE = {'name', 'id', 'label', 'metadata', 'published', 'current', 'base',
             'raw_current', 'raw_base', 'display_current', 'display_base', 'normal', 'unit'}
FAMILIES = dict(ship='ship', module='modules', charge='modules', drone='drones', fighter='fighters')


def sources(actual, fit_id, record, roles):
    """Check actual navigation metadata against complete saved and mapped memberships."""
    owner = roles['fit'][0]
    def link(row):
        exact(fit_id, row['source_fit_key']); exact(owner['ID'], row['source_fit_id'])
        exact(owner['name'], row['source_fit_name'])
        selected = row['source_target']
        if selected is None: return
        exact({'context', 'index', 'item_id', 'object_key'}, set(selected))
        family, index = selected['context'], selected['index']
        assert family in FAMILIES and type(index) is int and index >= 0
        exact(record['inspection_ids'][FAMILIES[family]][index], selected['object_key'])
        if family == 'ship':
            exact(0, index); item_id = owner['shipID']
        else:
            member = roles[FAMILIES[family]][index]
            item_id = member['chargeID' if family == 'charge' else 'itemID']
        exact(item_id, selected['item_id']); exact(item_id, row['item_id'])
    fields = {'after', 'attribute', 'before', 'changed', 'item_id', 'item_name', 'operator',
              'projected', 'source_fit_id', 'source_fit_key', 'source_fit_name', 'source_id',
              'source_ship_id', 'source_target', 'source_type', 'stacking', 'used'}
    for row in actual['affectors']:
        exact(fields, set(row)); link(row)
        exact(owner['shipID'], row['source_ship_id'])
    def tree(nodes):
        for node in nodes:
            exact({'alternate', 'children', 'label', 'sources'}, set(node))
            for row in node['sources']:
                exact({'source_fit_id', 'source_fit_key', 'source_fit_name', 'item_id', 'source_target'}, set(row))
                link(row)
            tree(node['children'])
    for mode in ('source', 'attribute'): tree(actual['affector_views'][mode])


def sql_roles(expected, actual):
    """Translate SQL IDs by independently verified table position, never value guesses."""
    exact({'fit', 'modules', 'drones', 'fighters'}, set(actual))
    exact(1, len(actual['fit']))
    fit_id = actual['fit'][0]['ID']; assert type(fit_id) is int and fit_id > 0
    translated = deepcopy(expected); translated['fit'][0]['ID'] = fit_id
    for table in ('modules', 'drones', 'fighters'):
        exact(len(expected[table]), len(actual[table]))
        identity = 'ID' if table == 'modules' else 'groupID'
        seen = set()
        for original, row in zip(translated[table], actual[table]):
            value = row[identity]; assert type(value) is int and value > 0 and value not in seen
            seen.add(value); original[identity] = value; original['fitID'] = fit_id
    exact(translated, actual)


def raw_affectors(expected, actual, fit_id, record, before, after):
    """Compare every original raw field with only proven saved identity mappings."""
    result = []
    for original_row in expected:
        row = deepcopy(original_row)
        exact(before['fit'][0]['ID'], row['source_fit_id'])
        exact(before['fit'][0]['name'], row['source_fit_name'])
        row['source_fit_id'] = after['fit'][0]['ID']
        row['source_fit_key'] = fit_id
        selected = row.pop('source_role')
        if selected is not None:
            family, index = selected['context'], selected['index']
            table = FAMILIES[family]
            selected['object_key'] = record['inspection_ids'][table][index]
            if row['source_id'] is not None:
                key = 'ID' if table == 'modules' else 'groupID'
                exact(before[table][index][key], row['source_id'])
                row['source_id'] = after[table][index][key]
        row['source_target'] = selected
        result.append(row)
    original(result, actual)


def properties(expected, selection, before, after, tables=None):
    """Original public properties with independently proven saved-row identity roles."""
    old_fit, new_fit = before['fit'][0], after['fit'][0]
    def translate(value):
        if type(value) is list: return [translate(member) for member in value]
        if type(value) is dict:
            result = {key: translate(member) for key, member in value.items()}
            if value.get('object_type') == 'Fit':
                exact(old_fit['ID'], value['id']); exact(old_fit['name'], value['name'])
                result['id'] = new_fit['ID']
            return result
        return value
    result = []
    for expected_row in expected:
        row = deepcopy(expected_row['contract'])
        if row['available']:
            row['value'] = translate(row['value'])
            name = row['name']
            if selection['context'] != 'base' and name in ('ID', 'groupID', 'fitID'):
                if name == 'fitID':
                    old_id, new_id = old_fit['ID'], new_fit['ID']
                else:
                    family = selection['context']
                    table = (tables or {'module': 'modules', 'charge': 'modules', 'drone': 'drones', 'fighter': 'fighters'})[family]
                    key = 'groupID' if table in ('drones', 'fighters') else 'ID'
                    position = selection['index']
                    def member(roles):
                        if family not in ('cargo', 'implant', 'booster'): return roles[table][position]
                        matches = [row for row in roles[table] if row['itemID'] == selection['item_id']]
                        exact(1, len(matches)); return matches[0]
                    left, right = member(before), member(after)
                    exact(selection['item_id'], left['chargeID' if selection['context'] == 'charge' else 'itemID'])
                    old_id, new_id = left[key], right[key]
                exact(old_id, row['value']); exact(str(old_id), row['display'])
                row['value'], row['display'] = new_id, str(new_id)
        result.append(row)
    return result


def metadata(expected, actual):
    original(expected['effects'], actual['effects'])
    variations = actual['variations']
    exact({'columns', 'rows'}, set(variations))
    exact(expected['variation_ids'], [row['id'] for row in variations['rows']])
    original(expected['variation_columns'], variations['columns'])
    for row, wanted in zip(variations['rows'], expected['variation_presentation']['raw']['rows']):
        exact({'id', 'name', 'meta', 'selected', 'values', 'price'}, set(row))
        exact(row['id'] == actual['item']['id'], row['selected'])
        exact(len(variations['columns']), len(row['values']))
        for column, cell, raw_value in zip(variations['columns'], row['values'], wanted[1:-1]):
            exact({'name', 'available', 'value', 'raw', 'display'}, set(cell))
            exact(column['name'], cell['name']); exact(raw_value != '', cell['available'])
            if cell['available']:
                original(float(raw_value), cell['value'])
            else:
                for key in ('value', 'raw', 'display'): exact(None, cell[key])
        price = row['price']
        exact({'available', 'value', 'currency', 'timestamp', 'display'}, set(price))
        exact('ISK', price['currency']); exact(wanted[-1] != '', price['available'])
        if not price['available']:
            for key in ('value', 'timestamp', 'display'): exact(None, price[key])
    for mode in ('normal', 'raw'):
        key = 'display' if mode == 'normal' else 'raw'
        rows = [[row['name']] + [cell[key] if cell['available'] else '' for cell in row['values']]
                + [row['price']['display'] if row['price']['available'] else ''] for row in variations['rows']]
        wanted = expected['variation_presentation'][mode]
        exact(wanted['columns'], ['Item'] + [column['label'] for column in variations['columns']] + ['Price'])
        exact(wanted['rows'], rows)


def unique(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, ('Duplicate report key', key)
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(AssertionError(value)))


def observation_header(saved, phase, pid, fresh=False):
    exact({'case_index', 'fit_id', 'sql_roles', 'targets'} | ({'phase', 'pid'} if fresh else set()), set(saved))
    if fresh:
        exact(phase, saved['phase'])
        assert type(saved['pid']) is int and saved['pid'] > 0
        exact(pid, saved['pid'])


def validate(state, raw, fixture, fresh=False):
    exact({'last_phase', 'pids', 'cases', 'targets', 'payload_sha256', 'graph', 'all_fits'}, set(state))
    phase = state['last_phase']
    assert phase in ('canonical', 'canonical-restored1', 'canonical-restored2')
    expected_pids = ('canonical', 'canonical-restored1', 'canonical-restored2').index(phase) + 1
    assert type(state['pids']) is list and len(state['pids']) == expected_pids
    assert all(type(pid) is int and pid > 0 for pid in state['pids'])
    assert len(set(state['pids'])) == expected_pids
    exact(152, state['cases']); exact(726, state['targets'])
    exact(hashlib.sha256(raw).hexdigest(), state['payload_sha256'])
    exact('8b04f3b271e614b3e103853b44a7851a63d79d0e', fixture['sourceCommit'])
    exact('5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607', fixture['databaseLogicalSha256'])
    cases = fixture['cases']; exact(152, len(cases))
    directory = Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures'
    def reference(name):
        path = directory / ('inspector-' + name + '.json')
        content = gzip.decompress(path.with_suffix('.json.gz').read_bytes()) if name == 'affector-metadata' else path.read_bytes()
        result = decode(content)
        for key in ('sourceCommit', 'databaseLogicalSha256', 'eos_settings'):
            exact(fixture[key], result[key])
        return result
    identities = reference('identities')
    property_cases = reference('properties')['cases']
    affector_cases = reference('affectors')['cases']
    raw_cases = reference('affector-metadata')['cases']
    metadata_rows = {row['item_id']: row for row in reference('metadata')['items']}
    inventory = decode((directory / 'inspector-inventory.json').read_bytes())
    for key in ('sourceCommit', 'databaseLogicalSha256'): exact(fixture[key], inventory[key])
    attribute_metadata = {row[0]: row for row in inventory['attributes']}
    exact(2860, len(attribute_metadata))
    exact(152, len(identities['cases']))
    exact(152, len(property_cases)); exact(152, len(affector_cases))
    exact(152, len(raw_cases))
    graph, fits = typed(state['graph']), typed(state['all_fits'])
    graph_identities(graph['records'])
    exact(set(graph['records']), {fit['id'] for fit in fits})
    lines = raw.splitlines(); exact(152, len(lines))
    ids, counts, property_count, raw_count = set(), Counter(), 0, 0
    for index, (line, case) in enumerate(zip(lines, cases)):
        saved = decode(line)
        observation_header(saved, phase, state['pids'][-1], fresh)
        exact(index, saved['case_index'])
        fit_id = saved['fit_id']; assert type(fit_id) is str and fit_id and fit_id not in ids
        ids.add(fit_id); assert fit_id in graph['records']
        identity_case = identities['cases'][index]
        exact(case['spec'], identity_case['spec'])
        exact(case['spec'], property_cases[index]['spec'])
        exact(case['spec'], affector_cases[index]['spec'])
        exact(case['spec'], raw_cases[index]['spec'])
        exact(len(case['targets']), len(raw_cases[index]['targets']))
        sql_roles(identity_case['expected'], saved['sql_roles'])
        record = graph['records'][fit_id]
        expected_spec = deepcopy(case['spec'])
        # CreateFit's typed encoder emits an explicit null for omitted ammunition
        # and omits empty fighter lists. These declared defaults change only the
        # input representation; all actual fields and original values still match.
        for module in expected_spec['modules']:
            if 'empty_slot' not in module:
                module.setdefault('charge', None)
        if 'fighters' in expected_spec and 'fighters' not in record['spec']:
            exact([], expected_spec.pop('fighters'))
        fit_inputs(expected_spec, record['spec'])
        exact({}, record['skills']); exact([], record['implants'])
        exact([], record['projections']); exact([], record['commands'])
        assert type(saved['targets']) is list
        exact(len(case['targets']), len(saved['targets']))
        selections = set()
        for target_index, (wanted, wrapped) in enumerate(zip(case['targets'], saved['targets'])):
            actual = typed(wrapped); exact(PROTOCOL, set(actual))
            exact(1, actual['version'])
            selected = actual['selection']; context = wanted['context']
            exact(context, selected['context']); exact(wanted['item_id'], selected['item_id'])
            exact(wanted['item_id'], actual['item']['id'])
            if context == 'base':
                exact({'context', 'index', 'item_id'}, set(selected))
                exact(None, selected['index']); exact(None, actual['fit_id']); exact(None, actual['revision'])
            else:
                exact({'context', 'index', 'item_id', 'object_key'}, set(selected))
                position = selected['index']; assert type(position) is int and position >= 0
                identity = (context, position); assert identity not in selections
                selections.add(identity)
                exact(record['inspection_ids'][FAMILIES[context]][position], selected['object_key'])
                exact(fit_id, actual['fit_id']); exact(graph['revisions'][fit_id], actual['revision'])
            attributes(wanted, actual)
            normal = {row['name']: row for row in wanted['expected']['normal']}
            for row in actual['attributes']['rows']:
                exact(ATTRIBUTE, set(row))
                known = row['id'] is not None
                exact(known, row['metadata'])
                exact(row['name'] in normal, row['normal'])
                if known:
                    info = attribute_metadata[row['id']]
                    exact(info[1], row['name']); exact(bool(info[3]), row['published'])
                else:
                    exact(False, row['published']); exact(row['name'], row['label'])
                for field in ('current', 'base'):
                    exact(normal[row['name']][field] if row['name'] in normal else None, row['display_' + field])
            property_target = property_cases[index]['targets'][target_index]
            affector_target = affector_cases[index]['targets'][target_index]
            for target in (property_target, affector_target):
                exact(context, target['context']); exact(wanted['item_id'], target['item_id'])
            original(properties(property_target['expected'], selected, identity_case['expected'], saved['sql_roles']), actual['properties'])
            property_count += len(property_target['expected'])
            for mode in ('source', 'attribute'):
                original(affector_target['expected'][mode], flatten(actual['affector_views'][mode]))
            metadata(metadata_rows[wanted['item_id']], actual)
            sources(actual, fit_id, record, saved['sql_roles'])
            raw_target = raw_cases[index]['targets'][target_index]
            exact(context, raw_target['context']); exact(wanted['item_id'], raw_target['item_id'])
            raw_expected = raw_target['expected']
            exact(identity_case['expected'], {table: raw_expected['sql_roles'][table] for table in identity_case['expected']})
            raw_affectors(raw_expected['affectors'], actual['affectors'], fit_id, record,
                          identity_case['expected'], saved['sql_roles'])
            raw_count += len(raw_expected['affectors'])
            counts[context] += 1
    exact(COUNTS, dict(counts))
    exact(57216, property_count)
    exact(5588, raw_count)
    return dict(cases=len(ids), targets=sum(counts.values()), contexts=dict(counts),
                original_properties=property_count, original_raw_affectors=raw_count, pids=state['pids'], phase=phase,
                payload_sha256=state['payload_sha256'])


def validate_restores(states, payloads, fixture):
    exact(3, len(states)); exact(3, len(payloads))
    summaries = []
    for index, (phase, state, raw) in enumerate(zip(
            ('canonical', 'canonical-restored1', 'canonical-restored2'), states, payloads)):
        exact(phase, state['last_phase'])
        summaries.append(validate(state, raw, fixture))
        exact(states[0]['pids'], state['pids'][:1])
        if index:
            exact(states[index - 1]['pids'], state['pids'][:-1])
            for key in ('cases', 'targets', 'payload_sha256', 'graph', 'all_fits'):
                exact(states[0][key], state[key])
            exact(payloads[0], raw)
    return summaries


def validate_fresh_restores(states, payloads, fixture):
    """Require actual complete payloads labelled by each distinct native worker."""
    exact(3, len(states)); exact(3, len(payloads))
    summaries = []
    for index, (phase, state, raw) in enumerate(zip(
            ('canonical', 'canonical-restored1', 'canonical-restored2'), states, payloads)):
        exact(phase, state['last_phase'])
        summaries.append(validate(state, raw, fixture, fresh=True))
        if index:
            exact(states[index - 1]['pids'], state['pids'][:-1])
            for key in ('cases', 'targets', 'graph', 'all_fits'): exact(states[0][key], state[key])
            assert states[index - 1]['payload_sha256'] != state['payload_sha256']
    return summaries
