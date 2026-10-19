"""C07.2 finite resource/source guards with fake metadata, never an EOS session."""
from copy import deepcopy
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

from android_bridge import projected_drone_budget as budget
from android_bridge.projected_drone_admission import AdmissionRejected
from android_bridge.offline.ewar_resource import (
    CONTRIBUTORS, DEFAULT_ALLOWANCE, EwarReservation, PRICES, admit_preparation)
from android_bridge.offline.ewar_samples import sample_ewar
from test_ewar_samples import CONTEXT, request


def record(*, source='FIT', modern=True, incoming=False):
    result = dict(spec=dict(modules=[], drones=[], fighters=[], cargo=[], environments=[],
        projected_modules=[], projected_drones=[], projected_fighters=[]),
        implants=[], boosters=[], commands=[], projections=[])
    if modern: result.update(implant_source=source, character_implants=[])
    if incoming:
        result['spec']['projected_drones'] = [dict(name='Web', amount=1, active=1, range_m=None)]
    return result


class LiveFit:
    def __init__(self, identity=1, source='FIT'):
        self.ID = identity
        for name in ('modules', 'drones', 'fighters', 'cargo', 'projectedModules',
                     'projectedDrones', 'projectedFighters', 'implants', 'boosters'):
            setattr(self, name, [])
        self.character = NS(implants=[])
        self._offline_character_implants = []
        self.implantLocation = 0 if source == 'FIT' else 1
        self.projectedFitDict = {}; self.commandFitDict = {}
        self.maxTargetRange = 20000
        self.extraAttributes = {'droneControlRange': 40000}

    @property
    def appliedImplants(self):
        return self.implants if self.implantLocation == 0 else self.character.implants

    def activeModulesIter(self): return iter(())
    def activeDronesIter(self): return iter(())
    def activeFighterAbilityIter(self): return iter(())


class Fixture(unittest.TestCase):
    def setUp(self):
        effect = NS(ID=6687, activeByDefault=True, runTime='normal',
                    isType=lambda kind: kind == 'projected', getattr=lambda name: False)
        self.catalog = {'Web': NS(ID=1, name='Web', isDrone=True, isAbyssal=False,
            isType=lambda kind: kind == 'projected', category=NS(name='Drone'), effects={'web': effect})}
        eos = ModuleType('eos'); db = ModuleType('eos.db')
        db.getItem = self.catalog.get; eos.db = db
        context = patch.dict(sys.modules, {'eos': eos, 'eos.db': db})
        context.start(); self.addCleanup(context.stop)
        self.records = {'fit': record()}; self.fits = {'fit': LiveFit()}
        self.revisions = {'fit': 1}

    def implant(self, *, key='fit', slot=79, character=True, active=False):
        name = 'Implant ' + str(slot)
        item = NS(ID=1000 + slot, name=name, isImplant=True, effects={},
                  getAttribute=lambda name: slot if name == 'implantness' else None)
        self.catalog[name] = item
        row = dict(name=name, slot=slot, active=active)
        obj = NS(item=item, itemID=item.ID, slot=slot, active=active)
        if character:
            row.update(implant_id=format(slot, '032x'), item_id=item.ID)
            self.records[key]['character_implants'].append(row)
            self.fits[key].character.implants.append(obj)
            self.fits[key]._offline_character_implants.append(deepcopy(row))
        else:
            self.records[key]['implants'].append(row)
            self.fits[key].implants.append(obj)
        return row, obj

    def admit(self, *, mode='webStr', reserve=None, selected=None):
        rows = selected if selected is not None else [dict(fit_id='fit', revision=1)]
        return admit_preparation(self.records, self.fits, self.revisions,
            list(self.fits.values()), rows, [self.fits[row['fit_id']] for row in rows],
            mode, EwarReservation() if reserve is None else reserve, lambda: None,
            lookup=self.catalog.get)

    def sample(self, *, mode='webStr', reserve=None, prepared=None, selected=None):
        def prepare(rows, handles, mode, charge, check):
            return admit_preparation(self.records, self.fits, self.revisions,
                list(self.fits.values()), rows, handles, mode, charge, check,
                lookup=self.catalog.get)
        value = request(mode)
        if selected is not None: value['fits'] = selected
        return sample_ewar(value, resolve_fit=lambda key: (self.fits[key], self.revisions[key]),
            current_context=lambda: CONTEXT, clock=lambda: 0, prep_admit=prepare,
            reserve=reserve, prepare_fit=lambda fit: prepared.append(fit) if prepared is not None else None)


class ImplantBudgetTests(Fixture):
    def test_caps_and_prices_remain_exact(self):
        self.assertEqual(DEFAULT_ALLOWANCE, 100663296)
        self.assertEqual(budget.MAX_COLD_UNITS, 16384)
        self.assertEqual(budget.MAX_REQUEST_UNITS, 134217728)
        self.assertEqual(budget.REQUEST_PHASES, 8)
        self.assertEqual(PRICES['container'], 128)
        self.assertEqual(PRICES['mapping_slot'], 320)
        self.assertEqual(PRICES['list_slot'], 64)
        self.assertEqual(PRICES['sort_slot'], 32)

    def test_both_sources_count_all_materialized_rows_per_fit(self):
        records = {'a': record(incoming=True), 'b': record(incoming=True)}
        original = budget.admit(records)
        for source in ('FIT', 'CHARACTER'):
            for row in records.values():
                row.update(implant_source=source, character_implants=[None, None])
            admitted = budget.admit(records)
            # Four independent materialized rows plus 4 * two max-fit rows.
            self.assertEqual(admitted['root_calls_per_phase'] - original['root_calls_per_phase'], 12)
            self.assertEqual(admitted['request_units'] - original['request_units'], 8 * 12 * 14)
            self.assertEqual(admitted['cold_units'], original['cold_units'])

    def test_local_and_character_have_the_same_row_price(self):
        local = {'fit': record(incoming=True)}; shared = deepcopy(local)
        local['fit']['implants'] = [None] * 3
        shared['fit']['character_implants'] = [None] * 3
        self.assertEqual(budget.admit(local), budget.admit(shared))

    def test_missing_pair_unknown_source_and_invalid_containers_refuse(self):
        for changes in (dict(implant_source=None), dict(implant_source=True),
                        dict(implant_source='ALL'), dict(character_implants=()), dict(implants=())):
            rows = {'fit': record(incoming=True)}; rows['fit'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(AdmissionRejected): budget.admit(rows)
        for omitted in ('implant_source', 'character_implants'):
            rows = {'fit': record(incoming=True)}; rows['fit'].pop(omitted)
            with self.assertRaises(AdmissionRejected): budget.admit(rows)

    def test_live_snapshot_retains_dormant_rows_and_source_without_capture(self):
        self.implant(character=False, active=True); self.implant(character=True)
        fit = self.fits['fit']
        for source, location in (('FIT', 0), ('CHARACTER', 1)):
            fit.implantLocation = location
            rows = budget.live_records([fit])[id(fit)]
            self.assertEqual(rows['implant_source'], source)
            self.assertEqual(rows['implants'], [None])
            self.assertEqual(rows['character_implants'], [None])
            self.assertFalse(fit.character.implants[0].active)

    def test_finite_character_growth_crosses_existing_bound_without_mutation(self):
        records = {'fit': record(incoming=True)}
        records['fit']['spec']['projected_drones'][0].update(amount=2047, active=2047)
        records['fit']['character_implants'] = [None] * 152
        admitted = budget.admit(records)
        self.assertEqual(admitted['root_calls_per_phase'], 1023)
        self.assertEqual(admitted['cold_units'], 16382)
        records['fit']['character_implants'].append(None)
        before = deepcopy(records)
        with self.assertRaisesRegex(AdmissionRejected, 'complete-request'): budget.admit(records)
        self.assertEqual(records, before)
        records['fit']['character_implants'].pop()
        self.assertEqual(budget.admit(records), admitted)

    def test_transition_reserves_crossed_root_and_cold_maxima_for_rollback(self):
        previous = {'fit': record(incoming=True)}
        previous['fit']['spec']['projected_drones'][0].update(amount=1000, active=1000)
        proposed = {'fit': record(incoming=True)}
        proposed['fit']['character_implants'] = [None] * 1000
        self.assertLess(budget.admit(previous)['request_units'], budget.MAX_REQUEST_UNITS)
        self.assertLess(budget.admit(proposed)['request_units'], budget.MAX_REQUEST_UNITS)
        saved = deepcopy((previous, proposed))
        with self.assertRaisesRegex(AdmissionRejected, 'rollback'):
            budget.admit_transition(previous, proposed)
        self.assertEqual((previous, proposed), saved)
        with self.assertRaises(AdmissionRejected): budget.admit_transition(proposed, previous)
        proposed['fit']['character_implants'] = [None]
        self.assertTrue(budget.admit_transition(previous, proposed)['enabled'])

    def test_transition_keeps_legacy_exemption_and_accounts_nonincoming_side(self):
        empty = {'fit': record(modern=False)}
        with patch.object(sys.modules['eos.db'], 'getItem', side_effect=AssertionError('lookup')):
            self.assertEqual(budget.admit_transition(empty, empty),
                             dict(enabled=False, cold_units=0, request_units=0))
        previous = {'fit': record()}; previous['fit']['character_implants'] = [None] * 7
        proposed = {'fit': record(incoming=True)}
        result = budget.admit_transition(previous, proposed)
        self.assertEqual(result['root_calls_per_phase'], 259 + 5 * 7)
        self.assertEqual(result['cold_units'], 14)
        self.assertEqual(result['request_units'], 8 * (259 + 5 * 7) * 14)


class ImplantPreparationTests(Fixture):
    def test_slot79_both_collections_count_even_when_dormant_and_inactive(self):
        base = EwarReservation(); self.admit(reserve=base)
        self.implant(character=False); self.implant(character=True)
        for source, location in (('FIT', 0), ('CHARACTER', 1)):
            self.records['fit']['implant_source'] = source
            self.fits['fit'].implantLocation = location
            charged = EwarReservation(); self.assertEqual(self.admit(reserve=charged), [(0, 0)])
            # K=selected+1=2; each independent row keeps the original T prices.
            self.assertEqual(charged.counts['container'] - base.counts['container'], 2 * 2 * 8)
            self.assertEqual(charged.counts['mapping_slot'] - base.counts['mapping_slot'], 2 * 2 * 16)
            self.assertEqual(charged.counts['list_slot'] - base.counts['list_slot'], 2 * 2 * 8)
            self.assertEqual(charged.counts['sort_slot'] - base.counts['sort_slot'], 2 * 2 * 4)
            self.assertEqual(charged.used - base.used, 2 * 2 * (8*128 + 16*320 + 8*64 + 4*32))

    def test_shared_profile_rows_charged_again_on_unselected_bound_fit(self):
        self.implant()
        first = EwarReservation(); self.admit(reserve=first)
        self.records['other'] = deepcopy(self.records['fit'])
        self.fits['other'] = LiveFit(2); self.revisions['other'] = 1
        self.records['other']['character_implants'] = []
        baseline = EwarReservation(); self.admit(reserve=baseline)
        self.implant(key='other')
        charged = EwarReservation(); self.admit(reserve=charged)
        self.assertEqual(charged.used - baseline.used, 2 * (8*128 + 16*320 + 8*64 + 4*32))
        self.assertIsNot(self.fits['fit'].character.implants[0], self.fits['other'].character.implants[0])
        self.assertEqual(self.records['fit']['character_implants'], self.records['other']['character_implants'])

    def test_selected_source_mismatch_and_invalid_enum_refuse(self):
        for location in (1, True, None, 2, 'FIT'):
            self.fits['fit'].implantLocation = location
            with self.subTest(location=location), self.assertRaises(AdmissionRejected): self.admit()
        self.fits['fit'].implantLocation = 0
        self.assertEqual(self.admit(), [(0, 0)])

    def test_applied_collection_mismatch_refuses(self):
        fake = NS(**self.fits['fit'].__dict__)
        fake.appliedImplants = fake.character.implants
        self.fits['fit'] = fake
        with self.assertRaises(AdmissionRejected): self.admit()

    def test_dormant_local_and_character_values_are_each_checked(self):
        for character in (False, True):
            self.records = {'fit': record(source='FIT' if character else 'CHARACTER')}
            self.fits = {'fit': LiveFit(source='FIT' if character else 'CHARACTER')}
            row, obj = self.implant(character=character)
            for attr, value in (('active', True), ('slot', 1), ('itemID', 999)):
                old = getattr(obj, attr); setattr(obj, attr, value)
                with self.subTest(character=character, attr=attr), self.assertRaises(AdmissionRejected): self.admit()
                setattr(obj, attr, old)
            self.assertEqual(self.admit(), [(0, 0)])

    def test_character_projection_identity_and_order_must_match_live_metadata(self):
        self.implant(slot=79); self.implant(slot=6)
        meta = self.fits['fit']._offline_character_implants
        meta[0]['implant_id'] = 'f' * 32
        with self.assertRaises(AdmissionRejected): self.admit()
        meta[:] = deepcopy(self.records['fit']['character_implants'])
        self.fits['fit'].character.implants.reverse()
        with self.assertRaises(AdmissionRejected): self.admit()
        self.fits['fit'].character.implants.reverse()
        self.assertEqual(self.admit(), [(0, 0)])

    def test_genuine_implant_and_pinned_slot_metadata_are_required(self):
        row, obj = self.implant()
        obj.item.isImplant = False
        with self.assertRaises(AdmissionRejected): self.admit()
        obj.item.isImplant = True
        for value in (True, None, float('nan'), float('inf'), 79.5, 6):
            obj.item.getAttribute = lambda key, value=value: value
            with self.subTest(value=value), self.assertRaises(AdmissionRejected): self.admit()
        obj.item.getAttribute = lambda key: 79
        self.assertEqual(self.admit(), [(0, 0)])

    def test_legacy_inputs_may_not_hide_character_collection_or_selection(self):
        self.records['fit'] = record(modern=False)
        self.assertEqual(self.admit(), [(0, 0)])
        character = self.fits['fit'].character
        self.fits['fit'].character = None
        with self.assertRaises(AdmissionRejected): self.admit()
        self.fits['fit'].character = character
        del self.fits['fit'].implantLocation
        with self.assertRaises(AdmissionRejected): self.admit()
        self.fits['fit'].implantLocation = 1
        with self.assertRaises(AdmissionRejected): self.admit()
        self.fits['fit'].implantLocation = 0
        self.fits['fit'].character.implants.append(NS())
        with self.assertRaises(AdmissionRejected): self.admit()

    def test_new_row_charge_refuses_before_lookup_and_recovers_at_exact_cost(self):
        base = EwarReservation(); self.admit(reserve=base)
        self.implant()
        needed = base.used + 2 * (8*128 + 16*320 + 8*64 + 4*32)
        previous = deepcopy(self.records)
        with patch.object(self.catalog['Implant 79'], 'getAttribute', side_effect=AssertionError('lookup before reservation')):
            with self.assertRaises(AdmissionRejected): self.admit(reserve=EwarReservation(needed - 1))
        self.assertEqual(self.records, previous)
        exact = EwarReservation(needed); self.assertEqual(self.admit(reserve=exact), [(0, 0)])
        self.assertEqual(exact.used, needed)

    def test_all_seven_graph_modes_preserve_success_after_resource_refusal(self):
        self.implant(character=False); self.implant(character=True)
        before = deepcopy(self.records)
        for mode in CONTRIBUTORS:
            prepared = []
            error = self.sample(mode=mode, reserve=EwarReservation(1024), prepared=prepared)
            self.assertEqual(error['error']['code'], 'resource_exhausted')
            self.assertEqual(set(error), {'version', 'request_id', 'ok', 'error'})
            self.assertEqual(prepared, [])
            self.assertEqual(self.records, before)
            for source, location in (('FIT', 0), ('CHARACTER', 1)):
                self.records['fit']['implant_source'] = source
                self.fits['fit'].implantLocation = location
                output = self.sample(mode=mode)
                self.assertTrue(output['ok'], output)
                self.assertEqual(set(output['series'][0]['y']), {0})
            self.records['fit']['implant_source'] = 'FIT'; self.fits['fit'].implantLocation = 0

    def test_default_allowance_is_cumulative_across_shared_materializations(self):
        # A finite fake pinned catalogue allows many legal slots; there is no
        # invented gameplay row/character cap. Eight selections charge K=9.
        for slot in range(1, 241): self.implant(slot=slot)
        for index in range(1, 8):
            key = 'fit' + str(index)
            self.records[key] = deepcopy(self.records['fit']); self.fits[key] = LiveFit(index + 1)
            self.revisions[key] = 1
            self.records[key]['character_implants'] = []
            for slot in range(1, 241): self.implant(key=key, slot=slot)
        selected = [dict(fit_id=key, revision=1) for key in self.records]
        before = deepcopy(self.records); prepared = []
        output = self.sample(selected=selected, prepared=prepared)
        self.assertEqual(output['error']['code'], 'resource_exhausted')
        self.assertEqual(prepared, []); self.assertEqual(self.records, before)
        # The failed request cannot consume the next request's allowance.
        recovered = self.sample()
        self.assertTrue(recovered['ok'], recovered)
        self.assertEqual(self.records, before)


if __name__ == '__main__': unittest.main()
