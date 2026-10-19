"""Validate actual C03.2 repeated-module observations across two fresh processes.

This is a bounded identity witness, not the complete inspector delivery report.
"""
import hashlib
import math
import re
from market_summary import exact
from mutation_history_summary import settings
from defense_summary import typed


def original(expected, actual):
    """Preserve the inspector's original numeric tolerances and exact other fields."""
    if type(expected) in (int, float):
        assert type(actual) in (int, float) and math.isfinite(expected) and math.isfinite(actual)
        assert abs(expected-actual) <= max(1e-9, 1e-10*max(abs(expected), abs(actual)))
    elif type(expected) is dict:
        assert type(actual) is dict and expected.keys() == actual.keys()
        for key in expected: original(expected[key], actual[key])
    elif type(expected) is list:
        assert type(actual) is list and len(expected) == len(actual)
        for left, right in zip(expected, actual): original(left, right)
    else:
        exact(expected, actual)


def attributes(target, actual):
    expected = target['expected']
    rows = actual['attributes']['rows']
    assert len({row['name'] for row in rows}) == len(rows)
    precise = [{key: row[key] for key in ('name', 'id', 'current', 'base', 'unit')} for row in rows]
    original(expected['precise'], precise)
    members = {row['name']: row for row in rows}
    for mode in ('normal', 'raw'):
        result = []
        for entry in actual['attributes'][mode]:
            row = members[entry['name']]
            result.append(dict(entry, current=row['raw_current' if mode == 'raw' else 'display_current'],
                               base=row['raw_base' if mode == 'raw' else 'display_base']))
        original(expected[mode], result)
    original(target['equipment'], actual['equipment'])


def validate(reports, fixture, fixture_bytes):
    assert type(reports) is list and len(reports) == 3
    exact('8b04f3b271e614b3e103853b44a7851a63d79d0e', fixture['sourceCommit'])
    exact('5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607', fixture['databaseLogicalSha256'])
    targets = dict(enumerate(row for row in fixture['cases'][0]['targets'] if row['context'] == 'module'))
    assert 0 in targets and 1 in targets and targets[0]['item_id'] == targets[1]['item_id']
    pids = []
    for phase, report in zip(('prepare', 'restored1', 'restored2'), reports):
        exact({'task', 'scope', 'phase', 'pid', 'runtime_start', 'saved', 'observations', 'history', 'fixture_sha256'}, set(report))
        exact('C03.2', report['task']); exact('repeated-module-identity', report['scope']); exact(phase, report['phase'])
        exact(hashlib.sha256(fixture_bytes).hexdigest(), report['fixture_sha256'])
        assert type(report['pid']) is int and report['pid'] > 0 and report['pid'] not in pids
        pids.append(report['pid'])
        runtime = report['runtime_start']
        exact(True, runtime['persistence']['enabled'])
        if phase != 'prepare': exact(True, runtime['persistence']['opened_existing'])
        exact('pyfa-engine', runtime['android_worker_thread']); exact(False, runtime['android_main_thread'])
        exact([], runtime['desktop_import_attempts'])
        exact(fixture['sourceCommit'], runtime['manifest']['desktop_source_commit'])
        exact(fixture['databaseLogicalSha256'], runtime['manifest']['database_logical_sha256'])
        settings(fixture['eos_settings'], runtime['eos_settings'])
        exact({'root.'+key: 'decimal' if type(value) is float else 'integer'
               for key, value in fixture['eos_settings'].items() if type(value) in (int, float)},
              runtime['eos_settings_numeric_types'])
        saved = report['saved']
        exact({'id', 'targets', 'pids', 'last_phase', 'graph', 'all_fits'}, set(saved))
        exact(phase, saved['last_phase']); exact(pids, saved['pids'])
        assert type(saved['id']) is str and saved['id']
        graph = typed(saved['graph']); fits = typed(saved['all_fits'])
        exact({fit['id'] for fit in fits}, set(report['history']))
        exact(set(graph['records']), set(report['history']))
        revision = graph['revisions'][saved['id']]
        assert type(revision) is int and revision >= 1
        durable_keys = graph['records'][saved['id']]['inspection_ids']['modules']
        for history in report['history'].values():
            exact({'undo_count', 'redo_count'}, set(history))
            for count in history.values(): assert type(count) is int and count >= 0
            if phase != 'prepare': exact(dict(undo_count=0, redo_count=0), history)
        if phase == 'prepare': assert report['history'][saved['id']]['redo_count'] > 0
        assert type(saved['targets']) is list and len(saved['targets']) == 2
        assert type(report['observations']) is list and len(report['observations']) == 2
        keys = []
        for index, (target, actual) in enumerate(zip(saved['targets'], report['observations'])):
            exact({'index', 'item_id', 'object_key', 'protocol'}, set(target)); exact(index, target['index'])
            exact(targets[index]['item_id'], target['item_id'])
            exact(durable_keys[index], target['object_key'])
            assert type(target['object_key']) is str and re.fullmatch('[0-9a-f]{32}', target['object_key'])
            keys.append(target['object_key'])
            exact(target['protocol'], actual)
            exact(1, actual['version']); exact(saved['id'], actual['fit_id'])
            exact(revision, actual['revision'])
            exact(dict(context='module', index=index, item_id=target['item_id'], object_key=target['object_key']), actual['selection'])
            attributes(targets[index], actual)
        assert len(set(keys)) == 2
        if phase != 'prepare':
            for key in ('id', 'targets', 'graph', 'all_fits'): exact(reports[0]['saved'][key], saved[key])
            exact(reports[0]['observations'], report['observations'])
    return dict(scope='repeated-module-identity', processes=3, restart_boundaries=2, modules=2,
                original_attribute_rows=sum(len(targets[index]['expected']['precise']) for index in (0, 1)))
