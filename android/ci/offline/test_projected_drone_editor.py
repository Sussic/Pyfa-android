"""D01.3 atomic integration invariants; independent numerical oracle is separate.

All fits are synthetic. Original source/EOS remains responsible for calculations;
these tests assert real effect direction, complete rollback and captured inputs.
"""
import json
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_native_session import NativeSessionTests, spec
from android_bridge.offline.profile_store import StoreWriteRejected


class ProjectedDroneTests(NativeSessionTests):
    def item(self, name):
        return self.engine._item(name).ID

    def rows(self, key=None):
        return self.session.projected_drone_details(key or self.key)['stacks']

    def add(self, name):
        return self.edit('add_projected_drone', dict(fit_id=self.key, item_id=self.item(name)))

    def change(self, operation, index=0, **values):
        row = self.rows()[index]
        return self.edit(operation, dict(fit_id=self.key, position=row['index'],
                                        object_key=row['object_key'], **values))

    def seeded(self, rows, **changes):
        value = dict(spec(), projected_drones=rows, **changes)
        self.key = self.edit('create_fit', dict(spec=value))['fits'][0]['id']
        return self.key

    @staticmethod
    def drone(name='Warrior SW-300', amount=5, active=2, range_m=63.7):
        return dict(name=name, amount=amount, active=active, range_m=range_m)

    def state(self):
        return dict(bytes=self.path.read_bytes(), graph=self.session.graph.snapshot(),
                    revisions=deepcopy(self.session._revisions), snapshots=deepcopy(self.session._snapshots),
                    history={key: self.session.history_details(key) for key in self.session._fits},
                    library_history=self.session.feature_state()['history'],
                    context=self.session.context())

    def reject(self, operation, arguments, contains=None):
        before = self.state()
        response = json.loads(self.session.dispatch(json.dumps(self.request(operation, arguments))))
        self.assertEqual(response['status'], 'error', response)
        if contains:
            self.assertIn(contains, response['error']['message'])
        self.assertTrue(self.session._available)
        self.assertEqual(self.state(), before)
        return response

    def undo(self):
        return self.edit('undo', dict(fit_id=self.key))

    def redo(self):
        return self.edit('redo', dict(fit_id=self.key))

    def test_real_web_add_merge_quantity_range_activation_removal_and_recent(self):
        # Materialize the original GUI fill postcondition before full-stat equality.
        self.edit('add_module', dict(fit_id=self.key, item_id=self.item('Small Armor Repairer I')))
        position = next(i for i, m in enumerate(self.session._fits[self.key].modules)
                        if not m.isEmpty and m.item.name == 'Small Armor Repairer I')
        self.edit('remove_module', dict(fit_id=self.key, position=position))
        baseline = deepcopy(self.session._snapshots[self.key]['stats'])
        baseline_speed = baseline['max_velocity']['value']
        recent = deepcopy(self.session.graph._state['fit_graph']['recent'])
        self.assertNotIn('projected_drones', self.session._records[self.key]['spec'])
        item = self.item('Warrior SW-300')
        options = self.session.projected_drone_add_options(self.key, item)
        self.assertTrue(options['is_drone'] and options['is_projectable'] and options['enabled'])
        self.add('Warrior SW-300')
        key = self.rows()[0]['object_key']
        first_speed = self.session._snapshots[self.key]['stats']['max_velocity']['value']
        self.assertLess(first_speed, baseline_speed)
        self.add('Warrior SW-300')
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual((self.rows()[0]['amount'], self.rows()[0]['active']), (2, 2))
        self.assertEqual(self.rows()[0]['object_key'], key)
        self.assertLess(self.session._snapshots[self.key]['stats']['max_velocity']['value'], first_speed)
        self.change('set_projected_drone_amount', amount=6)
        self.assertEqual(self.rows()[0]['active'], 6)  # No local five-active-drone cap.
        self.change('set_projected_drone_active', active=False)
        self.assertEqual(self.session._snapshots[self.key]['stats'], baseline)
        self.change('set_projected_drone_amount', amount=3)
        self.assertEqual(self.rows()[0]['active'], 0)
        self.change('set_projected_drone_active', active=True)
        self.assertEqual(self.rows()[0]['active'], 3)
        self.change('set_projected_drone_range', range_m=1_000_000_000)
        self.assertEqual(self.session._snapshots[self.key]['stats'], baseline)
        self.change('set_projected_drone_range', range_m=0)
        zero = deepcopy(self.session._snapshots[self.key]['stats'])
        self.assertIs(type(self.rows()[0]['range_m']), float)
        self.change('set_projected_drone_range', range_m=None)
        self.assertIsNone(self.rows()[0]['range_m'])
        self.assertEqual(self.session._snapshots[self.key]['stats'], zero)
        captured = deepcopy(self.session._records)
        self.change('remove_projected_drone', amount=1)
        self.assertEqual((self.rows()[0]['amount'], self.rows()[0]['active']), (2, 2))
        self.undo(); self.assertEqual(self.session._records, captured)
        self.redo(); self.assertEqual(self.rows()[0]['amount'], 2)
        self.change('remove_projected_drone', amount=2)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.session._records[self.key]['spec']['projected_drones'], [])
        self.assertEqual(self.session._records[self.key]['inspection_ids']['projected_drones'], [])
        self.assertEqual(self.session._snapshots[self.key]['stats'], baseline)
        self.undo(); self.assertEqual(self.rows()[0]['object_key'], key)
        self.assertEqual(self.session.graph._state['fit_graph']['recent'], recent)

    def test_partial_quantity_and_remove_one_differ_and_zero_undo_is_exact(self):
        self.seeded([self.drone()])
        # Original GUI wrappers fill vacant local slots even for a state no-op.
        # Materialize that real postcondition before asserting exact no-op history.
        self.change('set_projected_drone_range', range_m=0)
        self.change('set_projected_drone_range', range_m=63.7)
        saved = deepcopy(self.session._records)
        self.add('Warrior SW-300')
        self.assertEqual((self.rows()[0]['amount'], self.rows()[0]['active']), (6, 3))
        self.undo(); self.assertEqual(self.session._records, saved)
        self.change('set_projected_drone_amount', amount=4)
        self.assertEqual((self.rows()[0]['amount'], self.rows()[0]['active']), (4, 1))
        self.undo(); self.assertEqual(self.session._records, saved)
        self.change('remove_projected_drone', amount=1)
        self.assertEqual((self.rows()[0]['amount'], self.rows()[0]['active']), (4, 2))
        self.undo(); self.assertEqual(self.session._records, saved)
        count = self.session.history_details(self.key)['undo_count']
        self.change('set_projected_drone_active', active=True)
        self.assertEqual(self.session._records, saved)
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count)
        self.change('set_projected_drone_active', active=False)
        self.change('set_projected_drone_active', active=True)
        self.assertEqual(self.rows()[0]['active'], 5)
        self.undo(); self.assertEqual(self.rows()[0]['active'], 0)
        self.undo(); self.assertEqual(self.session._records, saved)
        self.change('set_projected_drone_amount', amount=0)
        self.assertEqual(self.rows(), [])
        self.undo(); self.assertEqual(self.session._records, saved)
        self.reopen(); self.assertEqual(self.session._records, saved)

    def test_variation_new_destination_resets_range_and_merge_preserves_destination(self):
        first = 'Light Armor Maintenance Bot I'
        second = 'Light Armor Maintenance Bot II'
        self.seeded([self.drone(first, 2, 1), self.drone(amount=1, active=1, range_m=0)])
        menu = self.session.projected_drone_options(self.key, 0)
        self.assertTrue(any(r['id'] == self.item(second) and r['enabled'] for r in menu['variations']))
        original = deepcopy(self.session._records)
        old = self.rows()[0]
        self.change('change_projected_drone_variation', item_id=self.item(second))
        rows = self.rows()
        self.assertEqual([r['name'] for r in rows], ['Warrior SW-300', second])
        self.assertEqual((rows[-1]['amount'], rows[-1]['active']), (2, 1))
        self.assertIsNone(rows[-1]['range_m'])
        self.assertNotEqual(rows[-1]['object_key'], old['object_key'])
        self.undo(); self.assertEqual(self.session._records, original)
        self.redo(); self.assertEqual(self.rows()[-1]['name'], second)
        self.undo()
        self.seeded([self.drone(first, 2, 1), self.drone(second, 3, 0, 0)])
        original = deepcopy(self.session._records); destination = self.rows()[1]
        self.change('change_projected_drone_variation', item_id=self.item(second))
        row = self.rows()[0]
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual((row['amount'], row['active'], row['range_m']), (5, 0, 0.0))
        self.assertEqual(row['object_key'], destination['object_key'])
        self.undo(); self.assertEqual(self.session._records, original)
        # Partial active destination grows by the whole incoming quantity, not source active count.
        self.seeded([self.drone(first, 2, 0), self.drone(second, 3, 1, 0)])
        self.change('change_projected_drone_variation', item_id=self.item(second))
        self.assertEqual((self.rows()[0]['amount'], self.rows()[0]['active']), (5, 3))

    def test_five_source_refreshes_copy_shared_profile_and_exact_reopen(self):
        self.seeded([self.drone('Light Armor Maintenance Bot II', 2, 1, 5e-324),
                     self.drone(amount=3, active=2, range_m=63.7)])
        source = self.key
        other = self.edit('create_fit', dict(spec=dict(spec(), name='Other recipient')))['fits'][0]['id']
        expected = deepcopy(self.session._records[source])
        expected_rows = deepcopy(self.rows())
        operations = [
            ('add_projection', dict(source_id=source, target_id=other, range_m=0, active=True, amount=1)),
            ('remove_projection', dict(source_id=source, target_id=other)),
            ('add_command', dict(source_id=source, target_id=other, active=True)),
            ('remove_command', dict(source_id=source, target_id=other)),
            ('add_command_fit', dict(source_id=source, target_id=other)),
        ]
        for operation, args in operations:
            self.edit(operation, args)
            self.assertEqual(self.session._records[source], expected, operation)
            self.assertEqual(self.rows(), expected_rows, operation)
        self.edit('remove_command_fit', dict(source_id=source, target_id=other))
        # Policy fill preparation makes the full recipient stats comparable.
        self.edit('add_projected_fit', dict(source_id=source, target_id=other))
        self.edit('remove_projected_fit', dict(source_id=source, target_id=other))
        second_stats = deepcopy(self.session._snapshots[other]['stats'])
        self.edit('add_projected_fit', dict(source_id=source, target_id=other))
        self.assertEqual(self.session._snapshots[other]['stats'], second_stats)
        old = set(self.session._fits)
        self.edit('duplicate_fit', dict(fit_id=source, name='Copied incoming drone stacks'))
        copied = next(key for key in self.session._fits if key not in old)
        self.assertEqual(self.session._records[source]['spec']['projected_drones'],
                         self.session._records[copied]['spec']['projected_drones'])
        self.assertTrue(set(self.session._records[source]['inspection_ids']['projected_drones']).isdisjoint(
            self.session._records[copied]['inspection_ids']['projected_drones']))
        self.feature('create_profile', dict(name='Drone shared profile', source='builtin:all5'))
        pid = next(key for key, row in self.session.graph._state['profiles']['profiles'].items()
                   if row['name'] == 'Drone shared profile')
        for key in (source, copied):
            self.feature('assign_profile', dict(fit_id=key, profile_id=pid))
        before = deepcopy(self.session._records)
        speeds = {key: self.session._snapshots[key]['stats']['max_velocity']['value'] for key in (source, copied)}
        profile = self.session.graph._state['profiles']['profiles'][pid]
        skill = next(key for key, value in self.session.graph.catalog.items() if value.name == 'Navigation')
        self.feature('set_profile_skill', dict(profile_id=pid, revision=profile['revision'], skill_id=skill, level=4))
        for key in (source, copied):
            self.assertEqual(self.session._records[key]['spec']['projected_drones'], before[key]['spec']['projected_drones'])
            self.assertEqual(self.session._records[key]['inspection_ids'], before[key]['inspection_ids'])
            self.assertLess(self.session._snapshots[key]['stats']['max_velocity']['value'], speeds[key])
        self.undo()
        self.assertEqual(self.session._records, before)
        self.redo()
        saved = self.session.graph.snapshot(); snapshots = deepcopy(self.session._snapshots)
        self.reopen()
        self.assertEqual(self.session.graph.snapshot(), saved)
        self.assertEqual(self.session._snapshots, snapshots)
        self.assertEqual(self.session.feature_state()['history']['undo_count'], 0)
        for key in self.session._fits:
            self.assertEqual(self.session.history_details(key)['undo_count'], 0)
            self.assertEqual(self.session.history_details(key)['redo_count'], 0)

    def test_refused_inputs_stale_identity_and_budget_preserve_complete_saved_state(self):
        self.add('Warrior SW-300')
        row = self.rows()[0]
        anchor = dict(fit_id=self.key, position=0, object_key=row['object_key'])
        for item in ('Hobgoblin I', 'Small Armor Repairer I'):
            options = self.session.projected_drone_add_options(self.key, self.item(item))
            self.assertFalse(options['enabled'])
            self.reject('add_projected_drone', dict(fit_id=self.key, item_id=self.item(item)))
        for amount in (-1, True, '2', 2.5, 2**31):
            self.reject('set_projected_drone_amount', dict(anchor, amount=amount))
        for amount in (0, -1, True):
            self.reject('remove_projected_drone', dict(anchor, amount=amount))
        for value in (-1, True, '0', 9007199254740993, float('inf')):
            self.reject('set_projected_drone_range', dict(anchor, range_m=value))
        self.reject('set_projected_drone_active', dict(anchor, active=1))
        self.reject('change_projected_drone_variation', dict(anchor, item_id=self.item('Hobgoblin I')))
        self.reject('remove_projected_drone', dict(anchor, object_key='0'*32, amount=1))
        self.reject('set_projected_drone_amount', dict(anchor, amount=2**31-1), 'Projected-drone evaluation budget:')
        stale = self.request('remove_projected_drone', dict(anchor, amount=1))
        self.edit('rename_fit', dict(fit_id=self.key, name='New revision'))
        before = self.state()
        response = json.loads(self.session.dispatch(json.dumps(stale)))
        self.assertEqual(response['error']['code'], 'REVISION_CONFLICT')
        self.assertEqual(self.state(), before)
        # A valid key from another fit still cannot address its row zero.
        other = self.edit('create_fit', dict(spec=dict(spec(), projected_drones=[self.drone(amount=1, active=1)])))['fits'][0]['id']
        self.reject('remove_projected_drone', dict(fit_id=other, position=0, object_key=row['object_key'], amount=1))

    def test_failed_write_read_queries_export_loss_and_structure_boundary(self):
        self.add('Warrior SW-300')
        row = self.rows()[0]
        args = dict(fit_id=self.key, position=0, object_key=row['object_key'], amount=3)
        with patch.object(self.session._store, 'write', side_effect=StoreWriteRejected('synthetic failed drone write')):
            self.reject('set_projected_drone_amount', args)
        before = self.state()
        self.session.projected_drone_details(self.key)
        self.session.projected_drone_options(self.key, 0)
        self.session.projected_drone_add_options(self.key, self.item('Warrior SW-300'))
        request = dict(version=1, request_id='drone-export', context=self.session.context(), fit_id=self.key,
                       revision=self.session._revisions[self.key],
                       options=dict.fromkeys(('loaded_charges', 'cargo', 'implants', 'boosters', 'mutations'), True))
        exported = json.loads(self.session.export_preview(json.dumps(request)))
        self.assertTrue(exported['ok'], exported)
        self.assertIn('projected_drones_lost', {r['code'] for r in exported['diagnostics']})
        self.assertNotIn('Warrior SW-300', exported['text'])
        self.assertEqual(self.state(), before)
        self.undo(); self.redo(); self.assertEqual(self.rows()[0]['object_key'], row['object_key'])
        structure = self.edit('create_fit', dict(spec=dict(spec(), ship='Fortizar', name='Structure')))['fits'][0]['id']
        self.assertTrue(self.session.projected_drone_details(structure)['is_structure'])
        self.assertFalse(self.session.projected_drone_add_options(structure, self.item('Warrior SW-300'))['enabled'])
        self.reject('add_projected_drone', dict(fit_id=structure, item_id=self.item('Warrior SW-300')))
        self.reject('create_fit', dict(spec=dict(spec(), ship='Fortizar', projected_drones=[self.drone()])))
        for rows in ([self.drone(amount=0, active=0)], [self.drone(active=6)],
                     [self.drone(), self.drone()], [dict(self.drone(), charge=None)],
                     [self.drone(name='Hobgoblin I')]):
            self.reject('create_fit', dict(spec=dict(spec(), projected_drones=rows)))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(ProjectedDroneTests(name) for name in ProjectedDroneTests.__dict__
                              if name.startswith('test_'))
