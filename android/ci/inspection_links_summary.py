"""Independent original linked inspector states, including actual history reversals."""
import hashlib
import re
from market_summary import exact
from defense_summary import typed
from inspection_identity_summary import attributes, original
from mutation_history_summary import settings


def flatten(nodes, prefix=()):
    result = []
    for node in nodes:
        path = (*prefix, node['label'])
        result.append(dict(path=list(path), alternate=node['alternate']))
        result.extend(flatten(node['children'], path))
    return result


def validate(report, fixture, fixture_bytes, kind):
    exact({'task', 'scope', 'kind', 'pid', 'runtime_start', 'source_id', 'target_id', 'observations',
           'followed_sources', 'followed_projected_sources', 'graph', 'fixture_sha256'}, set(report))
    exact('C03.2', report['task']); exact('linked-inspection', report['scope']); exact(kind, report['kind'])
    assert kind in ('projection', 'command')
    exact('8b04f3b271e614b3e103853b44a7851a63d79d0e', fixture['source_commit'])
    exact('5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607', fixture['databaseLogicalSha256'])
    exact(hashlib.sha256(fixture_bytes).hexdigest(), report['fixture_sha256'])
    assert type(report['pid']) is int and report['pid'] > 0
    runtime = report['runtime_start']
    exact(True, runtime['persistence']['enabled'])
    exact(fixture['source_commit'], runtime['manifest']['desktop_source_commit'])
    exact(fixture['databaseLogicalSha256'], runtime['manifest']['database_logical_sha256'])
    settings(fixture['eos_settings'], runtime['eos_settings'])
    exact({'root.'+key: 'decimal' if type(value) is float else 'integer'
           for key, value in fixture['eos_settings'].items() if type(value) in (int, float)}, runtime['eos_settings_numeric_types'])
    exact('pyfa-engine', runtime['android_worker_thread']); exact(False, runtime['android_main_thread'])
    exact([], runtime['desktop_import_attempts'])
    roles = dict(source=report['source_id'], target=report['target_id'])
    assert all(type(key) is str and key for key in roles.values()) and len(set(roles.values())) == 2
    steps = fixture['inputs']['steps']; previous = 'initial'; sequence = [('initial', 'initial')]
    for step in steps:
        sequence.extend([(step['name'], 'edit'), (previous, 'undo'), (step['name'], 'redo')])
        previous = step['name']
    exact(11 if kind == 'projection' else 19, len(fixture['states']))
    exact({'initial', *(step['name'] for step in steps)}, set(fixture['states']))
    assert type(report['observations']) is list and len(report['observations']) == len(sequence)
    targets = attribute_rows = tree_rows = followed = cross_fit = 0
    for (state, action), observed in zip(sequence, report['observations']):
        exact({'state', 'action', 'roles'}, set(observed)); exact(state, observed['state']); exact(action, observed['action'])
        exact(set(roles), set(observed['roles']))
        for role, key in roles.items():
            source_targets = set()
            actual = observed['roles'][role]; expected = fixture['states'][state][role]
            exact({'fit_id', 'revision', 'stats', 'inspection'}, set(actual)); exact(key, actual['fit_id'])
            assert type(actual['revision']) is int and actual['revision'] >= 1
            original({name: value for name, value in expected.items() if name != 'inspection'}, actual['stats'])
            assert type(actual['inspection']) is list and len(actual['inspection']) == len(expected['inspection'])
            for wanted, detail in zip(expected['inspection'], actual['inspection']):
                exact(1, detail['version'])
                if wanted['context'] == 'base':
                    exact(None, detail['fit_id']); exact(None, detail['revision'])
                    exact(None, detail['selection']['index']); assert 'object_key' not in detail['selection']
                else:
                    exact(key, detail['fit_id']); exact(actual['revision'], detail['revision'])
                exact(wanted['context'], detail['selection']['context']); exact(wanted['item_id'], detail['selection']['item_id'])
                if wanted['context'] != 'base':
                    assert type(detail['selection']['object_key']) is str and re.fullmatch('[0-9a-f]{32}', detail['selection']['object_key'])
                for affector in detail['affectors']:
                    selected = affector['source_target']
                    if selected is None:
                        continue
                    owner = affector['source_fit_key']; assert owner in roles.values()
                    exact({'context', 'index', 'item_id', 'object_key'}, set(selected))
                    assert selected['context'] in ('ship', 'module', 'charge', 'drone', 'fighter', 'implant', 'booster', 'mode')
                    assert type(selected['index']) is int and selected['index'] >= 0
                    assert type(selected['item_id']) is int and selected['item_id'] > 0
                    exact(affector['item_id'], selected['item_id'])
                    assert type(selected['object_key']) is str and re.fullmatch('[0-9a-f]{32}', selected['object_key'])
                    identity = (owner, selected['context'], selected['index'], selected['item_id'], selected['object_key'])
                    if identity not in source_targets:
                        source_targets.add(identity); followed += 1; cross_fit += owner != key
                attributes(dict(expected=wanted['attributes'], equipment=wanted['equipment']), detail)
                for mode in ('source', 'attribute'):
                    rows = flatten(detail['affector_views'][mode]); original(wanted['trees'][mode], rows)
                    tree_rows += len(rows)
                attribute_rows += len(wanted['attributes']['precise']); targets += 1
    for count in ('followed_sources', 'followed_projected_sources'):
        assert type(report[count]) is int and report[count] > 0
    assert report['followed_sources'] >= report['followed_projected_sources']
    exact(followed, report['followed_sources']); exact(cross_fit, report['followed_projected_sources'])
    graph = typed(report['graph'])
    for role, key in roles.items(): exact(graph['revisions'][key], report['observations'][-1]['roles'][role]['revision'])
    return dict(kind=kind, original_states=len(fixture['states']), history_observations=len(sequence),
                inspection_targets=targets, precise_attribute_rows=attribute_rows, original_tree_rows=tree_rows,
                followed_sources=report['followed_sources'], followed_projected_sources=report['followed_projected_sources'])
