#!/usr/bin/env python3
"""D02.2 public mobile_runtime / NativeSession finite remote-support proof.

Read original-only receipts from another process. Mutations and observations use
public APIs; internals only establish exact state, failure recovery and workload.
No numerical expected value comes from the candidate and no product guard is added.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import fields, is_dataclass
import hashlib
import json
import os
from pathlib import Path
import resource
import sqlite3
import sys
import time
from unittest.mock import patch
import uuid

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO/'android/app/src/main/python')]
from tools.android_reference.reference import compare
from tools.android_reference.remote_support.cases import LABELS, SUITES, SKILL, ARMOR, fixtures, scenario
from tools.android_reference.remote_support.preflight import exact, diagnostic

PROCESS_NONCE = uuid.uuid4().hex


def canonical(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, exclusive=True):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def publication_ids(step, before, after, ids):
    if step['op'] in ('share_profile', 'shared_skill'):
        return sorted(ids.values())  # Feature wire publishes its complete bootstrap.
    reached = {ids[step['args'][key]] for key in ('fit', 'source', 'target') if key in step['args']}
    edges = [(row['source_id'], target) for records in (before, after) for target, record in records.items()
             for family in ('projections', 'commands') for row in record[family]]
    while True:
        expanded = reached | {target for source, target in edges if source in reached}
        if expanded == reached: return sorted(reached & set(after))
        reached = expanded


def changed_paths(before, after, prefix=()):
    """Typed input paths for independent NON_HISTORY conflict expectations."""
    for key in sorted(set(before) | set(after)):
        if key in before and key in after and type(before[key]) is dict and type(after[key]) is dict:
            yield from changed_paths(before[key], after[key], (*prefix, key))
        elif key not in before or key not in after or json.dumps(before[key], sort_keys=True, allow_nan=False) != json.dumps(after[key], sort_keys=True, allow_nan=False):
            yield (*prefix, key)


def deletion_histories(graph_rows, legacy_rows, before, after):
    # NON_HISTORY first drops whole legacy recipient histories if any recorded
    # change conflicts with removed references. NativeSession then synchronizes
    # legacy tokens and prunes shared actions containing the deleted participant.
    legacy = {key:row for key, row in legacy_rows.items() if key in after}
    for key in list(legacy):
        paths = list(changed_paths(before[key], after[key]))
        if any(left[:len(right)] == right or right[:len(left)] == left
               for left in paths for action in legacy[key][0] for right in (change.path for change in action.changes)):
            del legacy[key]
    live = set(after) | {'library'}; graph = {}
    for key, (actions, cursor) in graph_rows.items():
        if key not in live: continue
        tokens = {id(action) for action in legacy.get(key, ((), 0))[0]}
        keep = lambda action: (action.legacy_token is None or id(action.legacy_token) in tokens) and action.participants <= live
        graph[key] = (tuple(action for action in actions if keep(action)), sum(keep(action) for action in actions[:cursor]))
    return graph, legacy


def frozen(value):
    """Exact action payloads, including present/absent fields and shared actions."""
    if is_dataclass(value):
        return {field.name:frozen(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict): return {key:frozen(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)): return sorted(frozen(item) for item in value)
    if isinstance(value, (tuple, list)): return [frozen(item) for item in value]
    return value


def full_history(session):
    legacy = session.graph._bridge._history
    legacy_actions = []; legacy_ids = {}
    def legacy_ref(action):
        if id(action) not in legacy_ids:
            legacy_ids[id(action)] = len(legacy_actions); legacy_actions.append(frozen(action))
        return legacy_ids[id(action)]
    legacy_rows = {key:dict(actions=[legacy_ref(action) for action in actions], cursor=cursor)
                   for key, (actions, cursor) in sorted(legacy.rows.items())}
    actions = []; identities = {}
    def reference(action):
        if id(action) not in identities:
            identities[id(action)] = len(actions)
            payload = frozen(action)
            payload['legacy_token_ref'] = None if action.legacy_token is None else legacy_ref(action.legacy_token)
            actions.append(payload)
        return identities[id(action)]
    rows = {key:dict(actions=[reference(action) for action in values], cursor=cursor)
            for key, (values, cursor) in sorted(session.history.rows.items())}
    return dict(sequence=session.history.sequence, rows=rows, actions=actions,
                legacy_rows=legacy_rows, legacy_actions=legacy_actions)


def scalar(row, unit):
    exact(unit, row['unit'], 'detail unit')
    value = row['value']
    expected_type = 'unavailable' if value is None else 'integer' if type(value) is int else 'decimal'
    exact(expected_type, row['value_type'], 'detail value type')
    assert value is None or type(value) in (int, float)
    assert row['display'] is None or type(row['display']) is str
    assert row['detail'] is None or type(row['detail']) is str
    return value


def decode_details(stats, tank, capacitor, output):
    """Map public fields to original EOS observation names, without calculating EOS."""
    tanks = {}
    for mode, prefix, unit in (('raw', '', 'HP/s'), ('effective', 'effective', 'EHP/s')):
        values = tank['tank'][mode]
        for stability, suffix in (('reinforced', 'Tank'), ('sustained', 'SustainableTank')):
            name = prefix + suffix if prefix else suffix[0].lower() + suffix[1:]
            row = values[stability]
            tanks[name] = {key:scalar(value, unit) for key, value in row['repairs'].items()}
            tanks[name].update(passiveShield=scalar(values['passive_shield'], unit),
                armorRepairPreSpool=scalar(row['armor_spool']['pre'], unit),
                armorRepairFullSpool=scalar(row['armor_spool']['full'], unit))
    cap = capacitor['capacitor']; stability = capacitor['stability']
    stable = stats['capacitor_stable']['value']
    assert type(stable) is bool
    exact('%' if stable else 's', stability['unit'], 'stability unit')
    exact(('stable_range' if len(stability['values']) == 2 else 'stable') if stable else 'depletion', stability['kind'], 'stability kind')
    for value, kind in zip(stability['values'], stability['value_types']):
        exact('integer' if type(value) is int else 'decimal', kind, 'stability value type')
    state = stability['values'] if len(stability['values']) == 2 else stability['values'][0]
    # Public resistance is a percentage; compare the source factor separately in
    # verify_sample rather than introducing a numerical inverse here.
    result = dict(stats=stats, tank=tanks,
        capacitor=dict(capacity=scalar(cap['capacity'], 'GJ'), recharge_time_ms=stats['capacitor_recharge_time']['value'],
            used=scalar(cap['use'], 'GJ/s'), recharge=scalar(cap['recharge'], 'GJ/s'), delta=scalar(cap['delta'], 'GJ/s'),
            stable=stable, state=state, state_unit=stability['unit']),
        outgoing={key:scalar(row['current'], 'GJ/s' if key == 'capacitor' else 'HP/s') for key, row in output['output']['outgoing'].items()})
    resistance = scalar(cap['neutralizer_resistance'], '%')
    return result, resistance


class Candidate:
    def __init__(self, args, oracle):
        self.args = args; self.oracle = oracle; self.checks = []; self.requests = []
        self.stage = 'startup'; self.active_request = None; self.network_attempts = []
        self.details = {}; self.edge_orders = {}; self.states = {}; self.history_evidence = []; self.failures_evidence = []
        def network_guard(event, values):
            if event in {'socket.connect', 'socket.connect_ex', 'socket.bind', 'socket.getaddrinfo'}:
                self.network_attempts.append(event)
                raise AssertionError('Offline proof: ' + event)
        sys.addaudithook(network_guard)
        import mobile_runtime as runtime
        self.runtime = runtime
        database = Path(os.environ['PYFA_DATABASE']).resolve()
        with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as connection:
            metadata = dict(connection.execute('SELECT field_name,field_value FROM metadata'))
        self.order = list(reversed(LABELS)) if args.reverse else list(LABELS)
        self.specs = fixtures(args.suite)
        filled = json.loads((REPO/'tools/android_reference/remote_support/filled_modules.json').read_text())['suites'][args.suite]
        # Same approved original output in both construction orders.
        for label, spec in self.specs.items():
            exact(filled['modules'][label], oracle['states']['initial']['raw'][label]['modules'], 'original filled inputs')
            spec['modules'] = deepcopy(filled['modules'][label])
        runtime.boot(str(database), json.dumps(dict(dataset_metadata=metadata, database_logical_sha256=os.environ['PYFA_DATASET_SHA'])),
                     json.dumps(dict(self.specs[self.order[0]], edit={})), str(args.store))
        boot = json.loads(runtime.bridge_bootstrap()); assert boot['status'] == 'ok', boot
        self.session = runtime._bridge
        self.ids = {row['name'].removeprefix('D02.2 '):row['id'] for row in boot['fits']}
        if args.phase == 'candidate':
            for label in self.order[1:]:
                result = self.edit('create_fit', dict(spec=self.specs[label]))
                self.ids[label] = result['fits'][0]['id']
        assert set(self.ids) == set(LABELS)
        self.labels = {value:key for key, value in self.ids.items()}

    def item(self, name):
        import eos.db
        item = eos.db.getItem(name); assert item is not None, name
        return item.ID

    def request(self, operation, arguments):
        ids = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
        return dict(version=1, request_id='d022-'+operation, session_id=self.session.session_id,
                    operation=operation, arguments=arguments, expected_revisions={key:self.session._revisions[key] for key in ids})

    @contextmanager
    def measured(self, operation):
        assert self.active_request is None
        row = dict(stage=self.stage, operation=operation, roots=0, calculation_calls=0, effects={}, simulations=[], admissions=[])
        self.active_request = row; started = time.monotonic()
        try:
            yield
        finally:
            row['elapsed_seconds'] = time.monotonic()-started
            self.requests.append(row); self.active_request = None

    def edit(self, operation, arguments):
        with self.measured(operation):
            result = json.loads(self.runtime.bridge_dispatch(json.dumps(self.request(operation, arguments))))
        assert result['status'] == 'ok', (operation, result)
        return result

    def feature(self, operation, arguments):
        request = dict(version=1, request_id='d022-'+operation, context=self.session.context(), operation=operation,
                       arguments=arguments, anchor_fit_id=self.ids['source_a'])
        with self.measured(operation):
            result = json.loads(self.runtime.offline_feature_dispatch(json.dumps(request)))
        assert result['ok'], (operation, result)
        return result

    def read(self, operation, fit_id):
        with self.measured(operation):
            return json.loads(getattr(self.runtime, operation)(fit_id))

    def rows(self, label):
        return self.read('projected_module_details', self.ids[label])['modules']

    def selection(self, label, index=0):
        row = self.rows(label)[index]
        return dict(position=row['index'], object_key=row['object_key'])

    def local_index(self, label, item):
        rows = self.edit('snapshot', dict(fit_ids=[self.ids[label]]))['fits'][0]['modules']
        return next(row['index'] for row in rows if row.get('name') == item)

    def mapped(self, step):
        op, args = step['op'], step['args']; fit_id = self.ids.get(args.get('fit'))
        if op in ('add_link', 'link_amount', 'link_range', 'link_active', 'remove_link'):
            operation = dict(add_link='add_projected_fit', link_amount='set_projected_fit_amount', link_range='set_projected_fit_range',
                             link_active='set_projected_fit_active', remove_link='remove_projected_fit')[op]
            return operation, dict(source_id=self.ids[args['source']], target_id=self.ids[args['target']],
                                   **{key:value for key, value in args.items() if key in ('amount', 'range_m', 'active')})
        if op == 'local_state':
            return 'set_module_states', dict(fit_id=fit_id, module_indices=[self.local_index(args['fit'], args['item'])], state=args['state'])
        if op == 'local_remove':
            return 'remove_module', dict(fit_id=fit_id, position=self.local_index(args['fit'], args['item']))
        if op in ('local_add', 'add_module'):
            return 'add_module' if op == 'local_add' else 'add_projected_module', dict(fit_id=fit_id, item_id=self.item(args['item']))
        if op == 'projector_active':
            return 'set_projected_module_state', dict(fit_id=fit_id, **self.selection(args['fit'], args['index']), state='active' if args['active'] else 'inactive')
        if op == 'remove_projector':
            return 'remove_projected_module', dict(fit_id=fit_id, **self.selection(args['fit'], args['index']))
        raise AssertionError(op)

    def profile(self):
        return self.session.feature_state()['bindings'][self.ids['source_a']]['profile_id']

    def apply(self, step):
        if step['op'] == 'share_profile':
            self.feature('create_profile', dict(name='D02.2 shared all V', source='builtin:all5'))
            profile = next(row['profile_id'] for row in self.session.feature_state()['profiles'] if row['name'] == 'D02.2 shared all V')
            for label in ('source_a', 'source_b'):
                result = self.feature('assign_profile', dict(fit_id=self.ids[label], profile_id=profile))
            return result['bridge']
        if step['op'] == 'shared_skill':
            profile = self.profile(); row = next(row for row in self.session.feature_state()['profiles'] if row['profile_id'] == profile)
            return self.feature('set_profile_skill', dict(profile_id=profile, revision=row['revision'], skill_id=self.item(SKILL), level=step['args']['level']))['bridge']
        return self.edit(*self.mapped(step))

    def raw(self, label):
        record = self.session._records[self.ids[label]]; spec = record['spec']; original = self.specs[label]
        projected = {'projected_modules', 'projected_drones', 'projected_fighters'}
        assert set(original) <= set(spec) <= set(original)|projected, ('Unexpected spec keys', label)
        for key, value in original.items():
            if key not in projected|{'modules'}:
                exact(value, spec[key], 'Unrelated spec '+label+'.'+key)
        modules = [dict(empty_slot=row['empty_slot']) if 'empty_slot' in row else dict(name=row['name'], state=row['state'], charge=row.get('charge')) for row in spec['modules']]
        assert not record['commands'] and not record['implants'] and not record.get('boosters')
        return dict(name=spec['name'], ship=spec['ship'], modules=modules, drones=deepcopy(spec['drones']),
            projected_modules=deepcopy(spec.get('projected_modules', [])), projected_drones=deepcopy(spec.get('projected_drones', [])),
            projected_fighters=deepcopy(spec.get('projected_fighters', [])), skills=deepcopy(record['skills']),
            projections=sorted([dict(row, source_id=self.labels[row['source_id']]) for row in record['projections']], key=lambda row:row['source_id']))

    def edge_order(self):
        live = {id(fit):self.labels[key] for key, fit in self.session._fits.items()}
        actual = {label:[live[id(source)] for source in self.session._fits[key].projectedFits] for label, key in self.ids.items()}
        durable = {label:[self.labels[row['source_id']] for row in self.session._records[key]['projections']] for label, key in self.ids.items()}
        return dict(actual=actual, durable=durable)

    def sample(self, order=None):
        order = [label for label in (order or self.order) if label in self.ids]
        result = self.edit('snapshot', dict(fit_ids=[self.ids[label] for label in order]))
        stats = {self.labels[row['id']]:row['stats'] for row in result['fits']}
        assert all(len(value) == 39 for value in stats.values())
        values = {}; details = {}
        for label in order:
            fit_id = self.ids[label]
            details[label] = {name:self.read(name+'_details', fit_id) for name in ('tank', 'capacitor', 'output')}
            for row in details[label].values():
                exact(fit_id, row['fit_id'], 'detail endpoint'); exact(self.session._revisions[fit_id], row['revision'], 'detail revision')
            values[label], resistance = decode_details(stats[label], **details[label])
            values[label]['capacitor']['neutralizer_resistance_percent'] = resistance
        self.details[self.stage] = details
        return dict(values=values, raw={label:self.raw(label) for label in self.ids})

    def verify_sample(self, expected, actual, label):
        values = deepcopy(expected['values'])
        for row in values.values():
            factor = row['capacitor'].pop('neutralizer_resistance')
            row['capacitor']['neutralizer_resistance_percent'] = None if factor is None else (1-factor)*100
        compare(values, actual['values'], label+'.values')
        exact(expected['raw'], actual['raw'], label+'.raw')

    def state(self):
        return canonical(dict(graph=self.session.graph.snapshot(), records=self.session._records, revisions=self.session._revisions,
            histories={key:self.session.history_details(key) for key in self.session._fits}, library_history=self.session.feature_state()['history'],
            recent=json.loads(self.runtime.recent_items()), context=self.session.context(), file_sha256=sha(self.args.store), full_history=full_history(self.session),
            edge_order=self.edge_order()))

    def captured(self):
        authority = deepcopy(self.session.graph.snapshot()['graph']['profiles'])
        for collection in ('profiles', 'bindings'):
            for value in authority[collection].values(): value.pop('revision')
        return canonical(dict(records=self.session._records, profile_authority=authority, edge_order=self.edge_order()))

    def durable(self):
        feature = self.session.feature_state()
        return canonical(dict(graph=self.session.graph.snapshot(), profiles=feature['profiles'], bindings=feature['bindings'],
            recent=json.loads(self.runtime.recent_items()), modules={label:self.rows(label) for label in self.ids},
            generation=self.session.context()['generation'], file_sha256=sha(self.args.store), edge_order=self.edge_order()))

    def history(self, step, before, after, prior, expected):
        owner = step['args'].get('fit', step['args'].get('target', 'source_a')); fit_id = self.ids[owner]
        count = self.session.history_details(fit_id)['undo_count']
        assert count == prior[owner]+1, (step['name'], 'not exactly one action')
        self.edit('undo', dict(fit_id=fit_id)); exact(before, self.captured(), 'exact undo '+step['name'])
        self.verify_sample(expected, self.sample(), 'undo '+step['name'])
        self.edit('redo', dict(fit_id=fit_id)); exact(after, self.captured(), 'exact redo '+step['name'])
        self.verify_sample(self.oracle['states'][step['name']], self.sample(), 'redo '+step['name'])
        self.history_evidence.append(dict(stage=step['name'], owner=owner, single_action=True,
                                         exact_before=before, exact_after=after))

    def failures(self):
        from android_bridge.offline.profile_store import StoreWriteRejected
        before = self.state(); profile = self.profile()
        row = next(row for row in self.session.feature_state()['profiles'] if row['profile_id'] == profile)
        args = dict(profile_id=profile, revision=row['revision'], skill_id=self.item(SKILL), level=4)
        request = dict(version=1, request_id='d022-rejected-write', context=self.session.context(), operation='set_profile_skill', arguments=args, anchor_fit_id=self.ids['source_a'])
        attempts = []
        def reject(attempt):
            proposed = json.loads(attempt.after.payload)
            assert proposed != json.loads(attempt.before.payload)
            for label in ('source_a', 'source_b'):
                key = self.ids[label]
                assert proposed['fit_graph']['records'][key]['skills'][SKILL] == 4
                assert proposed['fit_graph']['revisions'][key] > before['revisions'][key]
            attempts.append(proposed)
            raise StoreWriteRejected('D02.2 injected durable write rejection')
        with self.measured('injected_shared_profile_write'), patch.object(self.session._store, 'write', side_effect=reject) as written:
            result = json.loads(self.runtime.offline_feature_dispatch(json.dumps(request)))
        assert written.call_count == 1 and not result['ok'] and not result['committed'], result
        exact(before, self.state(), 'rejected durable write'); assert self.session._available
        self.verify_sample(self.oracle['states']['share_profile'], self.sample(), 'post-write-rejection')
        self.failures_evidence.append(dict(kind='durable_write', result=result, before=before, proposed=attempts))
        operation, args = self.mapped(dict(op='local_state', args=dict(fit='source_a', item=ARMOR, state='ONLINE')))
        before = self.state(); proposals = []
        def late(graph):
            assert graph != before['graph']['graph']
            source = graph['fit_graph']['records'][self.ids['source_a']]
            module = next(row for row in source['spec']['modules'] if row.get('name') == ARMOR)
            assert module['state'] == 'ONLINE'
            for label in ('source_a', 'source_b', 'target_c'):
                assert graph['fit_graph']['revisions'][self.ids[label]] > before['revisions'][self.ids[label]]
            proposals.append(deepcopy(graph))
            raise ValueError('D02.2 late preparation failure after real source edit')
        with self.measured('injected_late_prepare'), patch.object(self.session._store, 'prepare', side_effect=late) as prepared:
            result = json.loads(self.runtime.bridge_dispatch(json.dumps(self.request(operation, args))))
        assert prepared.call_count == 1 and result['status'] == 'error', result
        exact(before, self.state(), 'late preparation failure'); assert self.session._available
        self.verify_sample(self.oracle['states']['share_profile'], self.sample(), 'post-late-failure')
        self.failures_evidence.append(dict(kind='late_prepare', result=result, before=before, proposed=proposals))
        operation, args = self.mapped(dict(op='link_range', args=dict(source='source_a', target='target_c', range_m=0.0)))
        stale = self.request(operation, args); stale['expected_revisions'][self.ids['source_a']] -= 1
        before = self.state()
        with self.measured('stale_endpoint'), patch.object(self.session._store, 'write', wraps=self.session._store.write) as written:
            result = json.loads(self.runtime.bridge_dispatch(json.dumps(stale)))
        assert result['status'] == 'error' and result['error']['code'] == 'REVISION_CONFLICT' and written.call_count == 0, result
        exact(before, self.state(), 'stale endpoint')
        self.checks.append('failed shared-profile durable write and late source-edit preparation recover exact graph/identities/revisions/history; stale endpoint rejects before write')

    def stale_object(self):
        args = dict(fit_id=self.ids['source_a'], **self.selection('source_a'), range_m=0.0)
        args['object_key'] = '0'*32; before = self.state()
        from android_bridge import projected_module_editor
        original_selected = projected_module_editor.selected
        rejection_reasons = []
        def checked(*values, **kwargs):
            try:
                return original_selected(*values, **kwargs)
            except ValueError as error:
                rejection_reasons.append(str(error))
                raise
        with self.measured('stale_direct_object'), patch.object(self.session._store, 'write', wraps=self.session._store.write) as written, patch.object(projected_module_editor, 'selected', side_effect=checked) as selected:
            result = json.loads(self.runtime.bridge_dispatch(json.dumps(self.request('set_projected_module_range', args))))
        assert selected.call_count == 1
        exact(['Projected module changed; reload its controls'], rejection_reasons, 'original stale rejection witness')
        assert result['status'] == 'error' and result['error']['code'] == 'INVALID_EDIT' and written.call_count == 0, result
        exact("{'code': 'INVALID_EDIT', 'message': 'The edit is not supported by this fit'}", result['error']['message'], 'public sanitized rejection')
        exact(before, self.state(), 'stale direct-object token')
        self.failures_evidence.append(dict(kind='stale_direct_object', result=result, rejection_reasons=rejection_reasons,
            original_selected_calls=selected.call_count, durable_write_calls=written.call_count, exact_state_preserved=True))
        self.checks.append('stale direct-object identity rejects before write with exact recovery')

    def interleave(self, expected):
        before = self.state()
        for label in self.order:
            for operation in ('tank_details', 'capacitor_details', 'output_details'):
                self.read(operation, self.ids[label])
        entries = [dict(fit_id=self.ids[label], revision=self.session._revisions[self.ids[label]]) for label in self.order]
        request = dict(version=1, request_id='d022-interleaved', context=self.session.context(), fits=entries, resolution=16, budget_ms=10000,
                       x=dict(quantity='time', unit='s', range=[0, 30]), y=dict(quantity='cap_amount', unit='GJ'), starting_cap_percent=100, use_simulation=True)
        with self.measured('offline_capacitor_samples'):
            result = json.loads(self.runtime.offline_capacitor_samples(json.dumps(request)))
        assert result['ok'], result
        self.verify_sample(expected, self.sample(list(reversed(self.order))), 'read interleaving '+self.stage)
        exact(before, self.state(), 'reads preserve inputs/history/context')
        self.checks.append('tank/cap/outgoing/full-start 16-point capacitor read interleaving then reverse snapshots at '+self.stage)

    def delete_source(self):
        deleted = self.ids['source_a']; sequence = self.session.history.sequence
        expected_records = deepcopy(self.session._records); expected_records.pop(deleted)
        for record in expected_records.values():
            record['projections'] = [edge for edge in record['projections'] if edge['source_id'] != deleted]
        expected_profiles = deepcopy(self.session.graph.snapshot()['graph']['profiles'])
        expected_profiles['bindings'].pop(deleted)
        expected_history, expected_legacy = deletion_histories(self.session.history.rows, self.session.graph._bridge._history.rows,
                                                               self.session._records, expected_records)
        expected_history_payload = frozen(expected_history); expected_legacy_payload = frozen(expected_legacy)
        before_history_payload = frozen(self.session.history.rows)
        removed_legacy_owners = sorted(set(self.session.graph._bridge._history.rows) - set(expected_legacy))
        assert self.ids['source_b'] in removed_legacy_owners and self.ids['target_c'] in removed_legacy_owners
        assert not expected_history[self.ids['source_b']][0] and not expected_history[self.ids['target_c']][0]
        self.edit('delete_fit', dict(fit_id=deleted, resolve_references=True))
        self.ids.pop('source_a'); self.labels.pop(deleted)
        assert deleted not in self.session._records and deleted not in self.session.history.rows
        exact(expected_records, self.session._records, 'delete exact surviving records and identities')
        exact(expected_profiles, self.session.graph.snapshot()['graph']['profiles'], 'delete exact profile authority')
        assert self.session.history.sequence == sequence
        exact(expected_history_payload, frozen(self.session.history.rows), 'delete exact integrated history payloads/cursors')
        exact(expected_legacy_payload, frozen(self.session.graph._bridge._history.rows), 'delete exact legacy history payloads/cursors')
        for key, (actions, _) in expected_history.items():
            assert all(actual is expected for actual, expected in zip(self.session.history.rows[key][0], actions))
        for row in self.session._records.values():
            assert all(edge['source_id'] != deleted for edge in row['projections'])
        self.history_evidence.append(dict(stage='source_deleted', sequence=sequence, before=before_history_payload,
            expected_after=expected_history_payload, expected_legacy=expected_legacy_payload,
            removed_conflicting_legacy_owners=removed_legacy_owners, removed_source=deleted))
        self.checks.append('source deletion is NON_HISTORY and exactly prunes source edges and affected actions')

    @contextmanager
    def observe_work(self):
        from android_bridge import projected_drone_budget as budget
        from eos.saveddata.fit import Fit
        from eos.capSim import CapSimulator
        import eos.effects
        original_calc, original_run, original_admit = Fit.calculateModifiedAttributes, CapSimulator.run, budget.admit
        depth = 0
        def calculated(fit, *args, **kwargs):
            nonlocal depth
            row = self.active_request
            if row is not None:
                row['calculation_calls'] += 1; row['roots'] += depth == 0
            depth += 1
            try: return original_calc(fit, *args, **kwargs)
            finally: depth -= 1
        def admitted(*args, **kwargs):
            value = original_admit(*args, **kwargs)
            assert not value.get('enabled'), 'Module-only graph unexpectedly enabled drone/fighter guard'
            if self.active_request is not None: self.active_request['admissions'].append(canonical(value))
            return value
        def simulated(simulator, *args, **kwargs):
            estimate = diagnostic(simulator.modules, simulator.reload)
            result = original_run(simulator, *args, **kwargs)
            limit = estimate['horizons'][str(simulator.t_max)]
            assert simulator.iterations <= limit['events'] and len(simulator.saved_changes) <= limit['events']
            assert self.active_request is not None, 'Unmeasured simulation'
            self.active_request['simulations'].append(dict(horizon_ms=simulator.t_max, drains=len(simulator.modules),
                states=len(simulator.state), iterations=simulator.iterations, saved_events=len(simulator.saved_changes),
                runtime=simulator.runtime, estimate=limit))
            return result
        handlers = []
        for effect_id in (6184, 6185, 6186, 6187, 6188, 6197):
            cls = getattr(eos.effects, 'Effect'+str(effect_id)); original = cls.handler
            def handler(*args, original=original, effect_id=effect_id, **kwargs):
                if self.active_request is not None:
                    counts = self.active_request['effects']; key = str(effect_id); counts[key] = counts.get(key, 0)+1
                return original(*args, **kwargs)
            handlers.append(patch.object(cls, 'handler', staticmethod(handler)))
        try:
            for item in handlers: item.start()
            with patch.object(Fit, 'calculateModifiedAttributes', calculated), patch.object(CapSimulator, 'run', simulated), patch.object(budget, 'admit', admitted):
                yield
        finally:
            for item in reversed(handlers): item.stop()


def main(args):
    started = time.monotonic(); oracle = json.loads(args.oracle.read_text())
    assert oracle['mode'] == 'measure' and oracle['suite'] == args.suite and oracle['reverse'] == args.reverse
    assert oracle['process_nonce'] != PROCESS_NONCE
    assert 0 < resource.getrlimit(resource.RLIMIT_AS)[0] <= 1024**3
    exact(fixtures(args.suite), oracle['inputs'], 'fixture inputs')
    exact(scenario(args.suite, oracle['ranges'], args.reverse), oracle['steps'], 'source schedule')
    if args.phase == 'candidate': assert not args.store.exists()
    candidate = Candidate(args, oracle)
    exact(oracle['settings'], candidate.session.engine.settings, 'EOS settings')
    exact(oracle['dataset_metadata'], candidate.session.engine.metadata, 'dataset metadata')
    for name, identity in oracle['resolved_item_ids'].items(): exact(identity, candidate.item(name), 'item '+name)
    steps = oracle['steps']
    # Reopen while saved links and direct projector remain, before cleanup.
    cut_name = {'repair':'remove_direct_armor', 'capacitor':'remove_direct_Medium Energy Neutralizer II',
                'nosferatu':'remove_local_nos', 'reciprocal':'remove_direct_neut_a'}[args.suite]
    cut = next(index for index, step in enumerate(steps) if step['name'] == cut_name)
    receipt = Path(str(args.store)+'.receipt.json')
    with candidate.observe_work():
        if args.phase == 'reopen':
            saved = json.loads(receipt.read_text())
            assert saved['process_nonce'] != PROCESS_NONCE and saved['session_id'] != candidate.session.session_id
            exact(saved['durable'], candidate.durable(), 'fresh-process populated durable state')
            candidate.stage = saved['last_stage']
            candidate.verify_sample(oracle['states'][saved['last_stage']], candidate.sample(), 'fresh-process populated values')
            for key in candidate.session._fits:
                history = candidate.session.history_details(key); assert history['undo_count'] == history['redo_count'] == 0
            history = candidate.session.feature_state()['history']; assert history['undo_count'] == history['redo_count'] == 0
            candidate.states = saved['states']; candidate.checks = saved['checks'] + ['fresh-process populated graph exact durable identities/order/profiles/revisions and complete original values; all histories reset']
            selected = steps[cut:]; previous = saved['last_stage']
        else:
            candidate.stage = 'initial'; candidate.states['initial'] = candidate.sample()
            candidate.verify_sample(oracle['states']['initial'], candidate.states['initial'], 'initial')
            candidate.edge_orders['initial'] = candidate.edge_order()
            selected = steps[:cut]; previous = 'initial'
        for step in selected:
            candidate.stage = step['name']
            before = candidate.captured(); counts = {label:candidate.session.history_details(key)['undo_count'] for label, key in candidate.ids.items()}
            if step['name'] == 'shared_skill_four': candidate.failures()
            published = candidate.apply(step)
            exact(publication_ids(step, before['records'], candidate.session._records, candidate.ids), sorted(row['id'] for row in published['fits']), 'complete publication endpoints '+step['name'])
            for row in published['fits']:
                label = candidate.labels[row['id']]
                compare(oracle['states'][step['name']]['values'][label]['stats'], row['stats'], step['name']+'.published.'+label)
            sample = candidate.sample(); candidate.states[step['name']] = sample
            candidate.edge_orders[step['name']] = candidate.edge_order()
            write(Path(str(args.output)+'.partial.json'), dict(stage=step['name'], states=candidate.states, checks=candidate.checks, requests=candidate.requests, projection_order=candidate.edge_orders, histories=candidate.history_evidence, failures=candidate.failures_evidence), exclusive=False)
            candidate.verify_sample(oracle['states'][step['name']], sample, step['name'])
            candidate.verify_sample(oracle['states'][step['name']], candidate.sample(list(reversed(candidate.order))), 'reverse read '+step['name'])
            candidate.edge_orders[step['name']] = candidate.edge_order()
            exact(oracle['states'][step['name']]['projection_iteration'], candidate.edge_orders[step['name']]['actual'], 'original projection iteration '+step['name'])
            if step['name'] in ('a_armor_online', 'a_to_b_range_zero', 'shared_skill_four'):
                candidate.history(step, before, candidate.captured(), counts, oracle['states'][previous])
            if step['name'] == 'direct_neut_a': candidate.stale_object()
            if step['name'] in ('a_to_b_range_zero', 'shared_skill_four', 'direct_neut_a'):
                candidate.interleave(oracle['states'][step['name']])
            previous = step['name']; print('CANDIDATE', args.suite, step['name'], flush=True)
        if args.phase == 'candidate':
            write(receipt, dict(phase='populated_checkpoint', process_nonce=PROCESS_NONCE, session_id=candidate.session.session_id,
                last_stage=previous, states=candidate.states, durable=candidate.durable(), checks=candidate.checks))
        else:
            exact(sorted(oracle['states']), sorted(candidate.states), 'all schedule stages')
            if args.suite == 'reciprocal':
                # Complete original cleanup first, then rebuild the previously
                # proved populated topology for reference-pruning deletion.
                for step in steps[:3]: candidate.apply(step)
                candidate.delete_source()
                final = candidate.sample()
                expected = {field:{label:oracle['states']['remove_b_a'][field][label] for label in candidate.ids} for field in ('raw', 'values')}
                candidate.verify_sample(expected, final, 'post-delete complete original baseline with retained post-profile authority')
        assert not candidate.runtime._forbidden and not candidate.network_attempts
    write(args.output, dict(schema_version=1, suite=args.suite, reverse=args.reverse, phase=args.phase,
        process_nonce=PROCESS_NONCE, pid=os.getpid(), oracle_sha256=sha(args.oracle), states=candidate.states,
        checks=candidate.checks, histories=candidate.history_evidence, failures=candidate.failures_evidence,
        projection_order=candidate.edge_orders, requests=candidate.requests, details=candidate.details,
        strict_stats_per_fit=39, network_attempts=candidate.network_attempts, no_desktop_imports=not candidate.runtime._forbidden,
        startup_measurement='Boot and initial fixture construction precede observation instrumentation; process time/RSS include startup',
        incoming_drone_fighter_admission=dict(enabled=False, reason='ordinary module-only graph; diagnostic is not production admission'),
        elapsed_seconds=time.monotonic()-started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        source_qualification=oracle['source_kind'], remaining_steps=steps[cut:] if args.phase == 'candidate' else []))
    print('PASS', args.phase, args.suite, len(candidate.states), 'stages', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=SUITES, required=True)
    for name in ('oracle', 'store', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--phase', choices=('candidate', 'reopen'), required=True); parser.add_argument('--reverse', action='store_true')
    main(parser.parse_args())
