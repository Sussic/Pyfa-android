"""D05.3 pure contracts. Source-only until integrated execution is admitted.

Synthetic item doubles establish extraction semantics, not EOS numerical parity.
The positive tuples below are the accepted original-interface witnesses; matching
fit calculations still require the separate admitted real-EOS comparison.
"""
import ast
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from android_bridge.offline import damage_patterns as damage
from android_bridge.offline.graph_history import GraphHistory, inputs
from android_bridge.offline.profiles import ProfileError

F, G = 'a' * 32, 'b' * 32
CONTEXT = dict(session_id='c' * 32, dataset_sha256='d' * 64, generation=1)
ROOT = Path(__file__).resolve().parents[3]


def raw(*amounts):
    return dict(zip(damage.DAMAGE_FIELDS, amounts or (0, 0, 83.0, 0)))


def state():
    return dict(version=7, profiles=dict(profiles={}, bindings={}),
                fit_graph=dict(records={key: dict(spec=dict(name=key, modules=[], damage_pattern=raw(25, 25, 25, 25)))
                                        for key in (F, G)}, revisions={F: 1, G: 1}, fit_order=[F, G]),
                damage_patterns=damage.empty())


def wire(operation='read', arguments=None, **changes):
    return dict(version=3, request_id='selected-item', context=deepcopy(CONTEXT), fit_id=F,
                operation=operation, arguments={} if arguments is None else arguments,
                view=dict(query='', offset=0, limit=50, selected_pattern_id=None, bound_offset=0,module_offset=0)) | changes


class Item:
    def __init__(self, amounts, name='Synthetic base item'):
        self.name = name
        self.amounts = dict(zip(damage.ITEM_ATTRIBUTES, amounts))
        self.reads = []

    def getAttribute(self, key):
        self.reads.append(key)
        return self.amounts[key]

    @property
    def attribsWithOverrides(self):
        raise AssertionError('Never read overrides')

    @property
    def category(self):
        raise AssertionError('Category must not restrict eligibility')


def preview(amounts=(0, 0, 83.0, 0), item_id=210):
    source = Item(amounts)
    with patch('android_bridge.fitting.item', return_value=source):
        result = damage.item_options(SimpleNamespace(), item_id)
    return result


def apply(candidate, item=None, fit=F, **floors):
    item = preview() if item is None else item
    return damage.mutate(candidate, 'apply_item', dict(item_id=item['item_id'], fit_revision=1), fit,
                         item=item, **floors)


class SelectedItemExtractionTests(unittest.TestCase):
    def test_original_base_order_value_or_zero_and_no_override_category_read(self):
        source = Item((None, -0.0, 8.9, 0.0))
        engine = SimpleNamespace(resolved_item_ids={'existing': 1})
        with patch('android_bridge.fitting.item', return_value=source) as lookup:
            value = damage.item_options(engine, 12565)
        lookup.assert_called_once_with(engine, 12565)
        self.assertEqual(source.reads, list(damage.ITEM_ATTRIBUTES))
        self.assertTrue(damage.exact(value['values'], raw(0, 0, 8.9, 0)))
        self.assertTrue(value['eligible']); self.assertTrue(value['available'])
        self.assertIsNone(value['unavailable_reason'])
        self.assertEqual(engine.resolved_item_ids, {'existing': 1})

    def test_no_attributes_and_present_zero_remain_distinct(self):
        missing = preview((None,) * 4)
        zero = preview((None, -0.0, None, None))
        self.assertFalse(missing['eligible']); self.assertIsNone(missing['values'])
        self.assertEqual(missing['unavailable_reason'], 'no_damage_attributes')
        self.assertTrue(zero['eligible']); self.assertFalse(zero['available'])
        self.assertEqual(zero['unavailable_reason'], 'zero_total')
        self.assertTrue(damage.exact(zero['values'], raw(0, 0, 0, 0)))

    def test_original_positive_witness_interfaces_do_not_require_loaded_ammo(self):
        # Independent original observations: Scourge, Conflagration, EMP and
        # an eligible non-charge control. These are interface, not EOS tests.
        for item_id, amounts in ((210, (0, 0, 83.0, 0)), (12565, (8.9, 8.9, 0, 0)),
                                 (185, (9.0, 0, 1.0, 2.0)), (2456, (0, 20.0, 0, 0))):
            with self.subTest(item_id=item_id):
                value = preview(amounts, item_id)
                self.assertTrue(value['available'])
                self.assertTrue(damage.exact(value['values'], raw(*amounts)))

    def test_invalid_values_are_null_not_fabricated_and_total_overflow_rejected(self):
        for amount in (-1, float('nan'), float('inf'), -float('inf'), 2**63, True,
                       'damage', Decimal('0.1')):
            with self.subTest(amount=repr(amount)):
                value = preview((amount, None, None, None))
                self.assertTrue(value['eligible']); self.assertFalse(value['available'])
                self.assertEqual(value['unavailable_reason'], 'invalid_values')
                self.assertIsNone(value['values'])
        value = preview((1e308, 1e308, 0, 0))
        self.assertEqual(value['unavailable_reason'], 'invalid_values'); self.assertIsNone(value['values'])

    def test_supported_small_fractional_large_and_falsey_original_values(self):
        for amounts in ((5e-324, None, None, None), (damage.MAX_INT, None, None, None),
                        (False, 7.5, None, None), (0, 0, 0, 12.0)):
            self.assertTrue(preview(amounts)['available'])
        self.assertTrue(damage.exact(preview((False, 7.5, None, None))['values'], raw(0, 7.5, 0, 0)))

    def test_unknown_id_and_int32_boundary(self):
        with patch('android_bridge.fitting.item', side_effect=ValueError('Unknown item')):
            with self.assertRaises(ProfileError) as error: damage.item_options(SimpleNamespace(), 999)
        self.assertEqual(error.exception.code, 'unknown_item')
        for item_id in (None, False, 0, -1, 2**31, 210.0, '210'):
            with patch('android_bridge.fitting.item') as lookup, self.assertRaises(ProfileError):
                damage.item_options(SimpleNamespace(), item_id)
            lookup.assert_not_called()


class SelectedItemAuthorityTests(unittest.TestCase):
    def setUp(self): self.value = state()

    def test_first_use_and_same_snapshot_from_different_item_exact_noop(self):
        selected, affected = apply(self.value)
        self.assertEqual(selected, damage.SELECTED_AMMO); self.assertEqual(affected, {F})
        ledger = self.value['damage_patterns']
        self.assertEqual(ledger['patterns'][selected]['name'], 'Selected Ammo')
        self.assertEqual(ledger['patterns'][selected]['revision'], 1)
        before = deepcopy(self.value)
        self.assertEqual(apply(self.value, preview(item_id=999))[1], set())
        self.assertTrue(damage.exact(before, self.value))
        damage.validate(ledger, self.value['fit_graph']['records'])

    def test_equal_value_rebind_touches_only_current_binding(self):
        apply(self.value); before = deepcopy(self.value['damage_patterns'])
        self.assertEqual(apply(self.value, fit=G)[1], {G})
        self.assertTrue(damage.exact(before['patterns'], self.value['damage_patterns']['patterns']))
        self.assertEqual(before['bindings'][F], self.value['damage_patterns']['bindings'][F])

    def test_changed_raw_kinds_are_real_shared_update(self):
        apply(self.value); apply(self.value, fit=G)
        self.assertEqual(apply(self.value, preview((0, 0, 83, 0)))[1], {F, G})
        ledger = self.value['damage_patterns']
        self.assertEqual(ledger['patterns'][damage.SELECTED_AMMO]['revision'], 2)
        self.assertEqual(ledger['bindings'][F]['revision'], 2)
        self.assertEqual(ledger['bindings'][G]['revision'], 2)
        self.assertIs(type(ledger['patterns'][damage.SELECTED_AMMO]['values']['kineticAmount']), int)

    def test_ordinary_crud_and_duplicate_reject_special_at_authority(self):
        apply(self.value)
        for operation, extra in (('update_values', dict(values=raw(1.0, 0.0, 0.0, 0.0))),
                                 ('rename', dict(name='Other')), ('duplicate', dict(name='Copy')),
                                 ('delete', dict(bound_fit_count=1,bound_module_count=0,affected_fit_count=1))):
            before = deepcopy(self.value)
            with self.assertRaises(ProfileError) as error:
                damage.mutate(self.value, operation, dict(pattern_id=damage.SELECTED_AMMO, revision=1, **extra), F)
            self.assertEqual(error.exception.code, 'protected')
            self.assertTrue(damage.exact(before, self.value))
        with self.assertRaises(ProfileError):
            damage.mutate(self.value, 'create', dict(name='Selected Ammo', values=raw(1.0, 0.0, 0.0, 0.0)), None)
        # Existing builtin duplication remains an ordinary supported capability.
        copied, _ = damage.mutate(self.value, 'duplicate', dict(pattern_id=damage.UNIFORM, revision=0, name='Copy'), None)
        self.assertNotEqual(copied, damage.SELECTED_AMMO)

    def test_special_assign_detach_uniform_and_zero_binding_survival(self):
        apply(self.value)
        damage.mutate(self.value, 'assign', dict(pattern_id=damage.SELECTED_AMMO, revision=1, fit_revision=1), G)
        damage.mutate(self.value, 'detach_to_anonymous', dict(pattern_id=damage.SELECTED_AMMO, revision=1,
                       binding_revision=1, fit_revision=1), F)
        damage.mutate(self.value, 'reset_uniform', dict(fit_revision=1), G)
        self.assertIn(damage.SELECTED_AMMO, self.value['damage_patterns']['patterns'])
        self.assertTrue(damage.exact(self.value['fit_graph']['records'][F]['spec']['damage_pattern'], raw()))
        apply(self.value, preview((9.0, 0, 1.0, 2.0)), G)
        self.assertTrue(damage.exact(self.value['fit_graph']['records'][F]['spec']['damage_pattern'], raw()))

    def test_refusal_preserves_last_valid_values_and_all_inputs(self):
        apply(self.value)
        for item in (preview((None,) * 4), preview((0,) * 4), preview((-1, 0, 0, 0))):
            before = deepcopy(self.value)
            with self.assertRaises(ProfileError) as error: apply(self.value, item)
            self.assertEqual(error.exception.code, item['unavailable_reason'])
            self.assertTrue(damage.exact(before, self.value))

    def test_revision_exhaustion_preflights_all_participants_without_partial_mutation(self):
        apply(self.value); apply(self.value, fit=G)
        for floors in (dict(pattern_floor={damage.SELECTED_AMMO: damage.MAX_INT}),
                       dict(binding_floor={G: damage.MAX_INT})):
            before = deepcopy(self.value)
            with self.assertRaises(ProfileError): apply(self.value, preview((9.0, 0, 1.0, 2.0)), **floors)
            self.assertTrue(damage.exact(before, self.value))
        # Exact no-op does not spend even an exhausted revision floor.
        before = deepcopy(self.value)
        apply(self.value, pattern_floor={damage.SELECTED_AMMO: damage.MAX_INT}, binding_floor={F: damage.MAX_INT})
        self.assertTrue(damage.exact(before, self.value))

    def test_special_storage_identity_name_positive_values_and_exact_fields(self):
        apply(self.value)
        valid = self.value['damage_patterns']
        bad = []
        for change in (lambda x: x['patterns'][damage.SELECTED_AMMO].update(name='Not special'),
                       lambda x: x['patterns'][damage.SELECTED_AMMO].update(values=raw(0, 0, 0, 0)),
                       lambda x: x['patterns'][damage.SELECTED_AMMO].update(revision=0),
                       lambda x: x['patterns'][damage.SELECTED_AMMO].update(item_id=210),
                       lambda x: x.update(version=1)):
            row = deepcopy(valid); change(row); bad.append(row)
        row = deepcopy(valid); row['patterns']['damage:' + 'e' * 32] = row['patterns'].pop(damage.SELECTED_AMMO); bad.append(row)
        for row in bad:
            with self.assertRaises(ProfileError): damage.validate(row, self.value['fit_graph']['records'])
        with self.assertRaises(ProfileError): damage.validate(dict(valid, version=1), self.value['fit_graph']['records'], version=1)

    def test_builtin_special_custom_order_and_item_field_only_in_item_state(self):
        apply(self.value)
        damage.mutate(self.value, 'create', dict(name='AAA', values=raw(1.0, 0.0, 0.0, 0.0)), None)
        view = wire()['view'] | dict(offset=115, selected_pattern_id=damage.SELECTED_AMMO)
        result = damage.state_view(self.value, CONTEXT, F, view, GraphHistory())
        entries = result['page']['entries']
        self.assertEqual([row['kind'] for row in entries], ['builtin'] * 3 + ['selected_ammo', 'custom'])
        self.assertIsNone(result['item']); self.assertEqual(result['version'], 3)
        self.assertEqual(result['detail']['kind'], 'selected_ammo')
        item = preview()
        self.assertEqual(damage.state_view(self.value, CONTEXT, F, view, GraphHistory(), item=item)['item'], item)

    def test_history_normalizes_old_damage_before_recording_and_first_use_undo(self):
        before = deepcopy(self.value); before['version'] = 6; before['damage_patterns']['version'] = 1
        self.assertTrue(damage.exact(inputs(before), inputs(self.value)))
        self.assertEqual(GraphHistory().record(before, self.value, 'Migration', {F}).sequence, 0)
        apply(self.value)
        history = GraphHistory().record(before, self.value, 'Use item', {'library', F})
        replayed, _, action = history.replay(F, False, self.value)
        self.assertEqual(replayed['damage_patterns']['version'], 2)
        self.assertNotIn(damage.SELECTED_AMMO, replayed['damage_patterns']['patterns'])
        self.assertFalse(any(change.path == ('damage_patterns', 'version') for change in action.changes))


class SelectedItemWireTests(unittest.TestCase):
    def check(self, request):
        return damage.request(request, CONTEXT, state()['fit_graph']['records'], damage.empty())

    def test_exact_new_operation_arguments_context_and_version(self):
        for operation in ('item_options', 'apply_item'):
            valid = wire(operation, dict(item_id=210, fit_revision=1)); self.check(valid)
            invalid = [dict(valid, version=v) for v in (1, 2, 4, True, 3.0)]
            invalid += [dict(valid, fit_id=None), dict(valid, context=CONTEXT | dict(generation=2))]
            invalid += [dict(valid, arguments=valid['arguments'] | extra) for extra in (dict(values=raw()), dict(name='Name'), dict(item_id=True), dict(item_id=2**31), dict(fit_revision=0))]
            invalid += [dict(valid, arguments=dict(item_id=210))]
            for request in invalid:
                with self.subTest(request=request), self.assertRaises(ProfileError): self.check(request)

    def test_source_contract_keeps_passthrough_and_existing_budget(self):
        tree = ast.parse((ROOT / 'android/app/src/main/python/mobile_runtime.py').read_text())
        route = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'offline_damage_patterns')
        calls = [node for node in ast.walk(route) if isinstance(node, ast.Call)]
        self.assertTrue(any(isinstance(node.func, ast.Attribute) and node.func.attr == 'damage_dispatch' for node in calls))
        self.assertEqual(damage.READ_OPERATIONS, {'read', 'item_options', 'module_options'})
        self.assertEqual(damage.MAX_REQUEST_BYTES, 16384); self.assertEqual(damage.MAX_STATE_BYTES, 524288)
        self.assertEqual(len(damage.CATALOGUE), 118)
        self.assertEqual(GraphHistory().details(F)['limit'], 100)


if __name__ == '__main__': unittest.main()
