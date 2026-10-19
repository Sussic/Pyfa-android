"""Reject malformed added metadata and retain every inherited core/copy input."""
from copy import deepcopy
import sys
from pathlib import Path
from uuid import uuid4
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspection_record_identity import CORE, core_keys, graph_identities, copy_record, modes


class RecordIdentityTests(unittest.TestCase):
    def record(self, ship='Vexor', metadata=True):
        record = dict(spec=dict(ship=ship, name='original', modules=[dict(name='module')], drones=[],
                               boosters=[], cargo=[], fighters=[]), skills={}, implants=[], projections=[], commands=[])
        if metadata:
            record['inspection_ids'] = {family: [uuid4().hex for _ in range(count)] for family, count in
                dict(ship=1, modules=1, drones=0, fighters=0, implants=0, boosters=0, cargo=0, mode=int(bool(modes().get(ship)))).items()}
        return record
    def test_legacy_and_added_metadata_preserve_core_members(self):
        for metadata in (False, True):
            record = self.record(metadata=metadata); before=deepcopy(record)
            self.assertEqual(CORE, core_keys(record)); graph_identities({'fit': record})
            self.assertEqual(before, record)
    def test_default_and_explicit_modes_follow_independent_fixture(self):
        self.assertEqual({'Confessor','Svipul','Jackdaw','Hecate','Anhinga','Skua'},set(modes()))
        for ship, choices in modes().items():
            record = self.record(ship); core_keys(record)
            for choice in choices: record['spec']['mode']=choice; core_keys(record)
            record['spec']['mode']=True
            with self.assertRaises(AssertionError):core_keys(record)
            record['spec']['mode']=0
            with self.assertRaises(AssertionError):core_keys(record)
            record['spec'].pop('mode'); record['inspection_ids']['mode']=[]
            with self.assertRaises(AssertionError):core_keys(record)
        absent=self.record();absent['spec']['mode']=modes()['Confessor'][0]
        with self.assertRaises(AssertionError):core_keys(absent)
    def test_malformed_counts_families_keys_and_extra_fields_rejected(self):
        changes=[lambda r:r.update(extra=1), lambda r:r.pop('skills'),
                 lambda r:r['inspection_ids'].update(extra=[]), lambda r:r['inspection_ids'].pop('cargo'),
                 lambda r:r['inspection_ids'].update(modules=[]), lambda r:r['inspection_ids'].update(ship='x'),
                 lambda r:r['inspection_ids'].update(ship=[True]), lambda r:r['inspection_ids'].update(ship=['X'*32]),
                 lambda r:r['inspection_ids'].update(ship=['0'*31]),
                 lambda r:r['inspection_ids'].update(modules=r['inspection_ids']['ship'])]
        for change in changes:
            record=self.record();change(record)
            with self.assertRaises(AssertionError):core_keys(record)
    def test_families_count_actual_record_members_including_empty_slots(self):
        record=self.record(); record['spec']['modules'].append(dict(empty_slot='HIGH'))
        for family in ('drones','fighters','boosters','cargo'):record['spec'][family]=[{}]
        record['implants']=[{}]
        for family in ('modules','drones','fighters','boosters','cargo','implants'):
            count=2 if family=='modules' else 1
            record['inspection_ids'][family]=[uuid4().hex for _ in range(count)]
        core_keys(record)
        for family in ('ship','modules','drones','fighters','boosters','cargo','implants'):
            changed=deepcopy(record);changed['inspection_ids'][family].pop()
            with self.assertRaises(AssertionError):core_keys(changed)
    def test_global_and_copy_identity_reuse_rejected(self):
        first=self.record(); second=deepcopy(first)
        with self.assertRaises(AssertionError):graph_identities({'first':first,'second':second})
        with self.assertRaises(AssertionError):copy_record(first,second)
        second=self.record(); copy_record(first,second); graph_identities({'first':first,'second':second})
        second.pop('inspection_ids')
        with self.assertRaises(AssertionError):copy_record(first,second)
    def test_legacy_copy_and_every_core_value_or_type_remain_exact(self):
        for metadata in (False,True):
            first=self.record(metadata=metadata);second=self.record(metadata=metadata);copy_record(first,second)
            changes=[lambda r:r['spec'].update(name='other'), lambda r:r.update(skills={'skill':1}),
                     lambda r:r.update(implants=[{}]), lambda r:r.update(projections=[{}]),
                     lambda r:r.update(commands=[{}]), lambda r:r['spec'].update(boosters={})]
            for change in changes:
                changed=deepcopy(second);change(changed)
                with self.assertRaises((AssertionError,KeyError)):copy_record(first,changed)

    def test_optional_boosters_count_real_members_and_copy_every_flag(self):
        first = self.record()
        first['boosters'] = [dict(name='Synthetic booster', slot=504, active=True,
                                  side_effects=[dict(effect_id=100, active=False)])]
        first['inspection_ids']['boosters'] = [uuid4().hex]
        self.assertEqual(CORE | {'boosters'}, core_keys(first))
        second = deepcopy(first)
        second['inspection_ids'] = {family: [uuid4().hex for _ in values] for family, values in first['inspection_ids'].items()}
        copy_record(first, second); graph_identities({'first': first, 'second': second})
        for field, value in (('name', 'Other'), ('slot', 503), ('active', False),
                             ('side_effects', [dict(effect_id=100, active=True)])):
            changed = deepcopy(second); changed['boosters'][0][field] = value
            with self.assertRaises(AssertionError): copy_record(first, changed)
        changed = deepcopy(second); changed.pop('boosters')
        with self.assertRaises(AssertionError): copy_record(first, changed)

    def test_booster_extra_missing_duplicate_malformed_states_rejected(self):
        def value():
            record = self.record()
            record['boosters'] = [dict(name='Synthetic booster', slot=504, active=True,
                                       side_effects=[dict(effect_id=100, active=False)])]
            record['inspection_ids']['boosters'] = [uuid4().hex]
            return record
        changes = [lambda r: r.update(boosters=[]),
                   lambda r: r['inspection_ids'].update(boosters=[]),
                   lambda r: r['boosters'][0].update(extra=0),
                   lambda r: r['boosters'][0].pop('side_effects'),
                   lambda r: r['boosters'][0].update(active=1),
                   lambda r: r['boosters'][0].update(slot=True),
                   lambda r: r['boosters'].append(deepcopy(r['boosters'][0])),
                   lambda r: r['boosters'][0]['side_effects'][0].update(active=0),
                   lambda r: r['boosters'][0]['side_effects'][0].update(effect_id=True),
                   lambda r: r['boosters'][0]['side_effects'].append(dict(effect_id=100, active=False))]
        for change in changes:
            record=value(); change(record)
            with self.assertRaises((AssertionError,KeyError)): core_keys(record)

if __name__=='__main__':unittest.main()
