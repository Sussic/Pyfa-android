"""D05.3 atomic route, history and real-file migration contracts.

Execution is deferred pending an admitted complete integrated source. Replay
calculations below are explicit deterministic doubles, not EOS numerical proof.
The envelope tests use real GraphStore bytes and production validation/migration;
only EOS fit validation, bridge initialization and calculation are doubled.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from android_bridge.contract import BridgeSession, _json
from android_bridge.offline import damage_patterns as damage, implant_sets, target_profiles
from android_bridge.offline.graph_history import GraphHistory
from android_bridge.offline.native_session import NativeSession
from android_bridge.offline.profile_graph import ProfileGraph
from android_bridge.offline.profile_store import GraphStore, StoreUncertain
from android_bridge.offline.profiles import BUILTINS, ProfileError
from test_damage_session import ReplayGraph as DamageReplayGraph, session as damage_session, COPY
from test_selected_item_pattern import F, G, CONTEXT, Item, raw, wire

H = 'f' * 32


class SelectedReplayGraph(DamageReplayGraph):
    """Reuse existing replay double; explicitly update its schema-only boundary."""
    def __init__(self, initial):
        super().__init__(initial)
        self._state = ProfileGraph._migrate(self, initial)
        self.migration_pending = initial['version'] != 9
        self._snapshots = self._restore(self._state['fit_graph'])

    def _validate(self, candidate, *, prospective=False):
        self.assertion(candidate['version'] == 9 and set(candidate) == {
            'kind', 'version', 'fit_graph', 'profiles', 'imports', 'targets', 'damage_patterns', 'implant_sets'})
        target_profiles.validate(candidate['targets'], candidate['fit_graph']['records'])
        damage.validate(candidate['damage_patterns'], candidate['fit_graph']['records'])
        implant_sets.validate(candidate['implant_sets'])
        for revision in candidate['fit_graph']['revisions'].values(): damage.integer(revision, 1)


def session(initial=None):
    owner = damage_session(initial)
    owner.graph = SelectedReplayGraph(deepcopy(owner.graph._state))
    owner._remember_versions()
    return owner


class SelectedItemSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = session()
        self.items = {210: Item((0, 0, 83.0, 0)), 185: Item((9.0, 0, 1.0, 2.0)),
                      12565: Item((8.9, 8.9, 0, 0)), 999: Item((0, 0, 83.0, 0)),
                      10: Item((None,) * 4), 11: Item((0,) * 4), 12: Item((-1, 0, 0, 0))}
        def lookup(engine, identity):
            if identity not in self.items: raise ValueError('Unknown item')
            return self.items[identity]
        self.lookup = patch('android_bridge.fitting.item', side_effect=lookup)
        self.lookup.start(); self.addCleanup(self.lookup.stop)

    def request(self, operation='read', arguments=None, fit=F, **changes):
        return wire(operation, arguments, **(dict(context=self.session.context(), fit_id=fit) | changes))

    def call(self, operation='read', arguments=None, fit=F, **changes):
        before = self.session._store.current.generation
        value = json.loads(self.session.damage_dispatch(_json(self.request(operation, arguments, fit, **changes))))
        self.assertTrue(value['ok'], value)
        self.assertEqual(value['version'], 3); self.assertEqual(value['state']['version'], 3)
        self.assertEqual(value['state']['context']['generation'], before + int(value['committed']))
        self.assertEqual(set(value), {'version', 'request_id', 'ok', 'committed', 'reopen_required', 'state', 'bridge', 'error'})
        self.assertEqual(set(value['state']), {'version', 'context', 'fit_id', 'fit_revision', 'selection', 'page', 'detail', 'history', 'item', 'module'})
        if operation in damage.READ_OPERATIONS:
            self.assertIsNone(value['bridge']); self.assertFalse(value['committed'])
        else: self.assertIsNotNone(value['bridge'])
        if operation not in ('item_options', 'apply_item'): self.assertIsNone(value['state']['item'])
        return value

    def item_call(self, operation='apply_item', item_id=210, fit=F):
        return self.call(operation, dict(item_id=item_id, fit_revision=self.session._revisions[fit]), fit)

    def reject(self, request, code=None):
        stored = self.session._store.current; state = deepcopy(self.session.graph._state)
        history = self.session.history; restores = self.session.graph.restore_calls
        value = json.loads(self.session.damage_dispatch(_json(request)))
        self.assertFalse(value['ok']); self.assertFalse(value['committed']); self.assertFalse(value['reopen_required'])
        self.assertEqual(value['version'], 3); self.assertIsNone(value['state']); self.assertIsNone(value['bridge'])
        if code: self.assertEqual(value['error']['code'], code, value)
        self.assertEqual(self.session._store.current, stored)
        self.assertTrue(damage.exact(self.session.graph._state, state)); self.assertIs(self.session.history, history)
        return restores, value

    def edit(self, operation, arguments):
        request = dict(version=1, request_id='ordinary', session_id=self.session.session_id, operation=operation,
                       expected_revisions={arguments['fit_id']: self.session._revisions[arguments['fit_id']]}, arguments=arguments)
        value = json.loads(self.session.dispatch(_json(request)))
        self.assertEqual(value['status'], 'ok', value)
        return value

    def test_preview_is_read_only_and_never_stages_or_publishes_bridge(self):
        graph = self.session.graph; before = graph.snapshot(); store = self.session._store.current
        with patch.object(graph, '_restore', side_effect=AssertionError('read must not stage')), \
             patch.object(graph._bridge, 'bootstrap', side_effect=AssertionError('read must not publish bridge')):
            value = self.item_call('item_options')
        self.assertTrue(value['state']['item']['available'])
        self.assertEqual(self.session._store.current, store); self.assertEqual(graph.snapshot(), before)
        self.assertEqual(self.session.history.sequence, 0)
        self.assertNotIn(damage.SELECTED_AMMO, graph._state['damage_patterns']['patterns'])

    def test_first_apply_is_one_atomic_action_with_raw_action_time_snapshot(self):
        preview = self.item_call('item_options')['state']['item']
        self.items[210].amounts['kineticDamage'] = 84.0
        generation = self.session._store.current.generation
        value = self.item_call()
        self.assertTrue(value['committed']); self.assertEqual(value['state']['detail']['pattern_id'], damage.SELECTED_AMMO)
        self.assertEqual(value['state']['item']['values']['kineticAmount'], 84.0)
        self.assertEqual(preview['values']['kineticAmount'], 83.0)
        self.assertEqual(self.session._store.current.generation, generation + 1)
        actions = self.session.history.rows[F][0]
        self.assertEqual(len(actions), 1); self.assertEqual(actions[-1].participants, {'library', F})
        self.assertIs(actions[-1], self.session.history.rows['library'][0][-1])
        self.assertEqual(self.session._store.writes, 1)

    def test_equal_values_rebind_and_exact_noop_preserve_unrelated_revisions(self):
        self.item_call(); special = deepcopy(self.session.graph._state['damage_patterns']['patterns'])
        first_binding = deepcopy(self.session.graph._state['damage_patterns']['bindings'][F]); first_revision = self.session._revisions[F]
        self.item_call(fit=G)
        self.assertEqual(self.session._revisions[F], first_revision)
        self.assertEqual(self.session.graph._state['damage_patterns']['patterns'], special)
        self.assertEqual(self.session.graph._state['damage_patterns']['bindings'][F], first_binding)
        self.assertEqual(self.session.history.rows[G][0][-1].participants, {'library', G})
        before = self.session._store.current; state = deepcopy(self.session.graph._state); history = self.session.history
        self.assertFalse(self.item_call(item_id=999, fit=G)['committed'])
        self.assertEqual(before, self.session._store.current); self.assertTrue(damage.exact(state, self.session.graph._state))
        self.assertIs(history, self.session.history)

    def test_shared_update_includes_every_bound_fit_and_link_not_independent_fit(self):
        self.item_call(); self.item_call(fit=G)
        initial = deepcopy(self.session.graph._state)
        initial['fit_graph']['records'][H] = deepcopy(initial['fit_graph']['records'][G])
        initial['fit_graph']['records'][H]['projections'] = [dict(source_id=G)]
        initial['fit_graph']['fit_order'].append(H); initial['fit_graph']['revisions'][H] = 1
        initial['fit_graph']['modified'][H] = 0
        self.session = session(initial)
        value = self.item_call(item_id=185)
        self.assertEqual(self.session.history.rows[F][0][-1].participants, {'library', F, G, H})
        self.assertEqual({row['id'] for row in value['bridge']['fits']}, {F, G, H})
        self.assertEqual(self.session._revisions[H], 2)
        self.assertNotIn(H, self.session.graph._state['damage_patterns']['bindings'])
        self.assertTrue(damage.exact(self.session._records[G]['spec']['damage_pattern'], raw(9.0, 0, 1.0, 2.0)))

    def test_raw_kind_change_is_committed_and_persists_exactly_on_reopen(self):
        self.item_call(); self.items[210].amounts['kineticDamage'] = 83
        self.assertTrue(self.item_call()['committed'])
        self.session = session(json.loads(self.session._store.current.payload))
        value = self.call(view=wire()['view'] | dict(selected_pattern_id=damage.SELECTED_AMMO))
        self.assertIs(type(value['state']['detail']['values']['kineticAmount']), int)
        self.assertEqual(value['state']['history']['undo_count'], 0)
        self.assertFalse(self.session.graph.migration_pending)

    def test_first_creation_undo_removes_special_redo_recreates_monotonically(self):
        self.item_call(); first = self.session._revisions[F]
        self.call('undo'); self.assertNotIn(damage.SELECTED_AMMO, self.session.graph._state['damage_patterns']['patterns'])
        self.assertEqual(self.session.graph._state['version'], 9)
        self.assertEqual(self.session.graph._state['damage_patterns']['version'], 2)
        self.call('redo')
        self.assertGreater(self.session._revisions[F], first)
        self.assertGreater(self.session.graph._state['damage_patterns']['patterns'][damage.SELECTED_AMMO]['revision'], 1)
        self.call('undo'); self.item_call(item_id=185)
        self.assertEqual(self.session.history.details(F)['redo_count'], 0)
        self.assertGreater(self.session.graph._state['damage_patterns']['patterns'][damage.SELECTED_AMMO]['revision'], 2)

    def test_later_copy_keeps_binding_and_blocks_unsafe_undo(self):
        self.item_call(); self.edit('duplicate_fit', dict(fit_id=F, name='Later copy'))
        self.assertEqual(self.session.graph._state['damage_patterns']['bindings'][COPY]['pattern_id'], damage.SELECTED_AMMO)
        before, _ = self.reject(self.request('undo', fit=None), 'history_dependency')
        self.assertEqual(self.session.graph.restore_calls, before)
        self.item_call(item_id=185)
        self.assertIn(COPY, self.session.history.rows[F][0][-1].participants)
        self.assertTrue(damage.exact(self.session._records[COPY]['spec']['damage_pattern'], raw(9.0, 0, 1.0, 2.0)))

    def test_detach_uniform_outgoing_charge_notes_and_explicit_rah_inputs_unchanged(self):
        initial = deepcopy(self.session.graph._state)
        for key in (F, G):
            initial['fit_graph']['records'][key]['spec']['modules'] = [
                dict(name='Synthetic inherited module', charge='Keep charge'),
                dict(name='Synthetic builtin module', charge=None, rah_pattern=dict(mode='builtin', pattern_id=-1)),
                dict(name='Synthetic disabled module', charge=None, rah_pattern=dict(mode='disabled'))]
        initial['fit_graph']['records'][G]['spec']['notes'] = 'Keep note'
        self.session = session(initial); modules = deepcopy({key: row['spec']['modules'] for key, row in self.session._records.items()})
        self.item_call(); self.item_call(fit=G)
        selection = self.call()['state']['selection']
        self.call('detach_to_anonymous', dict(pattern_id=damage.SELECTED_AMMO, revision=selection['pattern_revision'],
                  binding_revision=selection['binding_revision'], fit_revision=self.session._revisions[F]))
        detached = deepcopy(self.session._records[F]['spec']['damage_pattern'])
        self.item_call(item_id=185, fit=G)
        self.assertTrue(damage.exact(self.session._records[F]['spec']['damage_pattern'], detached))
        self.call('reset_uniform', dict(fit_revision=self.session._revisions[G]), G)
        self.assertIn(damage.SELECTED_AMMO, self.session.graph._state['damage_patterns']['patterns'])
        self.assertEqual({key: row['spec']['modules'] for key, row in self.session._records.items()}, modules)
        self.assertEqual(self.session._records[G]['spec']['notes'], 'Keep note')
        self.assertEqual(self.session.graph._state['fit_graph']['recent'], [])

    def test_direct_crud_duplicate_and_user_supplied_values_cannot_bypass(self):
        self.item_call()
        for operation, extra in (('duplicate', dict(name='Copy')), ('rename', dict(name='Rename')),
                                 ('update_values', dict(values=raw(1.0, 0.0, 0.0, 0.0))), ('delete', dict(bound_fit_count=1,bound_module_count=0,affected_fit_count=1))):
            self.reject(self.request(operation, dict(pattern_id=damage.SELECTED_AMMO, revision=1, **extra)), 'protected')
        self.reject(self.request('apply_item', dict(item_id=210, fit_revision=self.session._revisions[F], values=raw())), 'invalid_request')

    def test_unavailable_unknown_stale_input_refuses_before_any_staging(self):
        self.item_call()
        for item_id, code in ((10, 'no_damage_attributes'), (11, 'zero_total'), (12, 'invalid_values'), (777, 'unknown_item')):
            before, _ = self.reject(self.request('apply_item', dict(item_id=item_id, fit_revision=self.session._revisions[F])), code)
            self.assertEqual(self.session.graph.restore_calls, before)
        for operation in ('item_options', 'apply_item'):
            self.reject(self.request(operation, dict(item_id=210, fit_revision=1)), 'stale_fit')
            self.reject(self.request(operation, dict(item_id=210, fit_revision=self.session._revisions[F]), context=CONTEXT), 'stale_context')
        self.item_call(item_id=185)

    def test_preview_errors_and_old_versions_are_recoverable_complete_v3_errors(self):
        self.reject(dict(self.request(), version=1), 'invalid_request')
        self.reject(dict(self.request(), version=2), 'invalid_request')
        self.reject(self.request('item_options', dict(item_id=777, fit_revision=1)), 'unknown_item')
        with patch.object(damage, 'state_view', side_effect=ValueError('parse/preview failure')):
            self.reject(self.request('item_options', dict(item_id=210, fit_revision=1)))
        self.assertTrue(self.session.graph._available); self.item_call('item_options')

    def test_preview_and_apply_share_state_publication_byte_cap(self):
        request = self.request('apply_item', dict(item_id=210, fit_revision=1))
        with patch.object(damage, 'MAX_STATE_BYTES', 1):
            self.reject(self.request('item_options', dict(item_id=210, fit_revision=1)), 'response_size')
            self.reject(request, 'response_size')
        self.assertNotIn(damage.SELECTED_AMMO, self.session.graph._state['damage_patterns']['patterns'])
        self.item_call()

    def test_existing_feature_publication_guard_refusal_is_atomic(self):
        with patch.object(self.session.graph, '_feature_guard', create=True,
                          side_effect=ProfileError('response_size', 'Aggregate publication budget')):
            self.reject(self.request('apply_item', dict(item_id=210, fit_revision=1)), 'response_size')
        self.assertNotIn(damage.SELECTED_AMMO, self.session.graph._state['damage_patterns']['patterns'])
        self.item_call()

    def test_history_generation_pattern_binding_and_fit_exhaustion_preserves_state(self):
        self.item_call(); initial = json.loads(self.session._store.current.payload)
        for kind in ('history', 'generation', 'pattern', 'binding', 'fit'):
            self.session = session(initial)
            if kind == 'history': self.session.history = GraphHistory(sequence=damage.MAX_INT)
            elif kind == 'generation':
                self.session._store.current = self.session._store.current._replace(generation=damage.MAX_INT)
                self.session._store._durable = self.session._store.current
            elif kind == 'pattern': self.session._damage_pattern_floor[damage.SELECTED_AMMO] = damage.MAX_INT
            elif kind == 'binding': self.session._damage_binding_floor[F] = damage.MAX_INT
            else: self.session.graph._revision_floor[F] = damage.MAX_INT
            self.reject(self.request('apply_item', dict(item_id=185, fit_revision=self.session._revisions[F])), 'revision')

    def test_transition_safety_refusal_restores_inputs_and_recovers(self):
        from android_bridge.projected_drone_admission import AdmissionRejected
        with patch('android_bridge.projected_drone_budget.admit_transition', side_effect=AdmissionRejected('budget')) as admission:
            before, _ = self.reject(self.request('apply_item', dict(item_id=210, fit_revision=1)))
            self.assertEqual(admission.call_count, 1); self.assertEqual(self.session.graph.restore_calls, before)
        self.item_call()

    def test_write_rejection_recovers_and_lost_ack_confirms_one_commit(self):
        original = self.session._store.write
        with patch.object(self.session._store, 'write', side_effect=RuntimeError('not written')):
            self.reject(self.request('apply_item', dict(item_id=210, fit_revision=1)))
        def lost_ack(attempt): original(attempt); raise RuntimeError('lost ack')
        with patch.object(self.session._store, 'write', side_effect=lost_ack): self.item_call()
        self.assertEqual(self.session._store.writes, 1)

    def test_uncertain_confirmation_disables_until_reopen_without_retry(self):
        with patch.object(self.session._store, 'confirm', side_effect=RuntimeError('uncertain')):
            value = json.loads(self.session.damage_dispatch(_json(self.request('apply_item', dict(item_id=210, fit_revision=1)))))
        self.assertTrue(value['reopen_required']); self.assertIsNone(value['committed'])
        self.assertIsNone(value['state']); self.assertIsNone(value['bridge']); self.assertFalse(self.session.graph._available)
        self.session = session(json.loads(self.session._store._durable.payload))
        self.assertEqual(self.call()['state']['selection']['pattern_id'], damage.SELECTED_AMMO)

    def test_publication_failure_after_commit_disables_and_reopen_confirms(self):
        with patch.object(self.session, '_remember_versions', side_effect=RuntimeError('publish')):
            value = json.loads(self.session.damage_dispatch(_json(self.request('apply_item', dict(item_id=210, fit_revision=1)))))
        self.assertTrue(value['reopen_required']); self.assertIsNone(value['committed'])
        self.session = session(json.loads(self.session._store.current.payload))
        self.assertEqual(self.call()['state']['selection']['pattern_id'], damage.SELECTED_AMMO)

    def test_read_durable_race_requires_reopen_not_recoverable_read_error(self):
        original = damage.state_view
        def race(*args, **kwargs):
            result = original(*args, **kwargs)
            self.session._store._durable = self.session._store.current._replace(generation=2)
            return result
        with patch.object(damage, 'state_view', side_effect=race):
            value = json.loads(self.session.damage_dispatch(_json(self.request('item_options', dict(item_id=210, fit_revision=1)))))
        self.assertTrue(value['reopen_required']); self.assertIsNone(value['committed'])
        self.assertFalse(self.session.graph._available)


def empty_envelope(version):
    profiles = deepcopy(BUILTINS)
    if version < 9:
        for value in profiles.values(): value.pop('sec_status')
    if version < 5:
        for value in profiles.values(): value.pop('implants')
    result = dict(kind='pyfa.profile-fit-graph', version=version,
        fit_graph=dict(records={}, revisions={}, modified={}, fit_order=[], recent=[], sample_id=None, format=2),
        profiles=dict(kind='pyfa.offline-profiles', format=3 if version >= 9 else 2 if version >= 5 else 1,
                      dataset=CONTEXT['dataset_sha256'], profiles=profiles, bindings={}, default_profile='builtin:all5'))
    if version >= 2: result['imports'] = {}
    if version >= 3: result['targets'] = target_profiles.empty()
    if version >= 4: result['damage_patterns'] = dict(version=2 if version >= 7 else 1, patterns={}, bindings={})
    if version >= 6: result['implant_sets'] = implant_sets.empty()
    return result


@contextmanager
def envelope_owner(path):
    """Run production open/migrate/store logic without importing or executing EOS."""
    module = ModuleType('eos.saveddata.character')
    module.Character = SimpleNamespace(getSkillIDMap=lambda: {1: SimpleNamespace(name='Synthetic skill')})
    engine = SimpleNamespace(_check_thread=lambda: None, _fits=[], settings={}, resolved_item_ids={})
    def initialize(bridge, engine):
        bridge._records = {}; bridge._revisions = {}; bridge._available = True
    with ExitStack() as stack:
        stack.enter_context(patch.dict(sys.modules, {'eos.saveddata.character': module}))
        stack.enter_context(patch.object(BridgeSession, '__init__', initialize))
        stack.enter_context(patch.object(BridgeSession, '_validate_graph'))
        stack.enter_context(patch.object(ProfileGraph, '_restore', return_value={}))
        yield ProfileGraph(engine, path, CONTEXT['dataset_sha256'])


class SelectedItemEnvelopeTests(unittest.TestCase):
    def save(self, path, candidate):
        store = GraphStore(path); store.write(store.prepare(candidate))
        return path.read_bytes()

    def test_all_supported_envelopes_open_normalized_without_writes_or_generation(self):
        with TemporaryDirectory() as directory:
            for version in range(1, 10):
                with self.subTest(version=version):
                    path = Path(directory) / ('v%d.sqlite' % version)
                    original = self.save(path, empty_envelope(version))
                    with envelope_owner(path) as owner:
                        result = owner.snapshot()
                        self.assertEqual(result['graph']['version'], 9)
                        self.assertEqual(result['graph']['damage_patterns']['version'], 2)
                        self.assertEqual(result['graph']['profiles']['format'], 3)
                        self.assertEqual(result['migration_pending'], version < 9)
                        self.assertEqual(owner._store.current.generation, 1)
                    self.assertEqual(path.read_bytes(), original)
                    self.assertEqual(json.loads(GraphStore(path).current.payload)['version'], version)

    def test_mixed_versions_unknown_fields_and_invalid_special_preserve_bytes(self):
        malformed = []
        for version in (4, 5, 6, 7, 8):
            mixed = empty_envelope(version); mixed['damage_patterns']['version'] = 1 if version >= 7 else 2
            malformed.append(mixed)
        for version in range(1, 9):
            extra = empty_envelope(version); extra['unexpected'] = True; malformed.append(extra)
        unknown = empty_envelope(7); unknown['version'] = 10; malformed.append(unknown)
        bad = empty_envelope(7)
        bad['damage_patterns']['patterns'][damage.SELECTED_AMMO] = dict(name='Selected Ammo', revision=1, values=raw(0, 0, 0, 0))
        malformed.append(bad)
        old = empty_envelope(6)
        old['damage_patterns']['patterns'][damage.SELECTED_AMMO] = dict(name='Selected Ammo', revision=1, values=raw())
        malformed.append(old)
        with TemporaryDirectory() as directory:
            for number, candidate in enumerate(malformed):
                path = Path(directory) / ('bad%d.sqlite' % number); original = self.save(path, candidate)
                with self.assertRaises(ProfileError), envelope_owner(path): pass
                self.assertEqual(path.read_bytes(), original)

    def test_v6_raw_custom_migration_is_byte_unchanged_until_effective_commit(self):
        candidate = empty_envelope(6); identity = 'damage:' + '9' * 32
        candidate['damage_patterns']['patterns'][identity] = dict(name='Custom', revision=1, values=raw(-0.0, 8.9, 0, 0))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'v6.sqlite'; original = self.save(path, candidate)
            with envelope_owner(path) as owner:
                self.assertTrue(owner.migration_pending); self.assertEqual(path.read_bytes(), original)
                no_op = owner._commit(deepcopy(owner._state), set())
                self.assertFalse(no_op['committed']); self.assertTrue(owner.migration_pending)
                self.assertEqual(path.read_bytes(), original)
                changed = deepcopy(owner._state); changed['damage_patterns']['patterns'][identity]['name'] = 'Renamed'
                changed['damage_patterns']['patterns'][identity]['revision'] = 2
                self.assertTrue(owner._commit(changed, set())['committed'])
                self.assertEqual(owner._store.current.generation, 2); self.assertFalse(owner.migration_pending)
            with envelope_owner(path) as owner:
                self.assertFalse(owner.migration_pending)
                self.assertTrue(damage.exact(owner._state['damage_patterns']['patterns'][identity]['values'], raw(-0.0, 8.9, 0, 0)))
                self.assertEqual(owner._state['version'], 9); self.assertEqual(owner._state['damage_patterns']['version'], 2)


if __name__ == '__main__': unittest.main()
