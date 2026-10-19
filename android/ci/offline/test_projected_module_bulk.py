"""Atomic selected projector controls through the actual durable native session."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_native_session import NativeSessionTests, spec
from android_bridge.offline.profile_store import StoreWriteRejected


class ProjectedModuleBulkTests(NativeSessionTests):
    def seed(self, environment=False, drone=False):
        value = spec()
        if environment:
            value['environments'] = [dict(name='Class 1 Red Giant Effects', state='ONLINE')]
        value['projected_modules'] = [
            dict(name='Remote Sensor Booster II', state='ACTIVE', charge='Scan Resolution Script', range_m=63.7),
            dict(name='Remote Sensor Booster II', state='OFFLINE', charge=None, range_m=None),
            dict(name='Remote Sensor Booster II', state='ACTIVE', charge=None, range_m=5e-324),
            dict(name='Small Energy Neutralizer II', state='OFFLINE', charge=None, range_m=0.0),
        ]
        if drone:
            value['projected_drones'] = [dict(name='Warrior SW-300', amount=6, active=6, range_m=None)]
        response = self.edit('create_fit', dict(spec=value))
        self.key = response['fits'][0]['id']
        # Create-spec fixtures lack the ordinary GUI's empty-slot fill. Establish
        # that normal displayed baseline before testing selected-action identity.
        row = next(row for row in self.rows() if row['editable'])
        self.edit('set_projected_module_range', dict(fit_id=self.key, position=row['index'],
                  object_key=row['object_key'], range_m=row['range_m']))
        return self.rows()

    def rows(self):
        return self.session.projected_module_details(self.key)['modules']

    def selection(self, indices):
        rows = self.rows()
        return [dict(position=rows[i]['index'], object_key=rows[i]['object_key']) for i in indices]

    def bulk(self, operation, selection, **args):
        return self.edit(operation, dict(fit_id=self.key, selection=selection, **args))

    def reject(self, operation, selection, **args):
        before = (self.path.read_bytes(), deepcopy(self.session._records), deepcopy(self.session.history_details(self.key)))
        result = json.loads(self.session.dispatch(json.dumps(self.request(operation, dict(fit_id=self.key, selection=selection, **args)))))
        self.assertEqual(result['status'], 'error', result)
        self.assertEqual((self.path.read_bytes(), self.session._records, self.session.history_details(self.key)), before)
        self.assertTrue(self.session.graph._bridge._available)
        return result

    def test_noncontiguous_states_one_history_and_exact_undo_redo(self):
        self.seed(drone=True)
        before = deepcopy(self.session._records)
        selection = self.selection([2, 0])
        count = self.session.history_details(self.key)['undo_count']
        self.bulk('set_projected_module_states', selection, state='inactive')
        after = deepcopy(self.session._records)
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count + 1)
        old = before[self.key]['spec']; new = after[self.key]['spec']
        for i in (0, 2): self.assertEqual(new['projected_modules'][i]['state'], 'OFFLINE')
        for i in (1, 3): self.assertEqual(new['projected_modules'][i], old['projected_modules'][i])
        self.assertEqual(new['projected_drones'], old['projected_drones'])
        self.assertEqual(after[self.key]['inspection_ids'], before[self.key]['inspection_ids'])
        self.edit('undo', dict(fit_id=self.key)); self.assertEqual(self.session._records, before)
        self.edit('redo', dict(fit_id=self.key)); self.assertEqual(self.session._records, after)
        count = self.session.history_details(self.key)['undo_count']
        self.bulk('set_projected_module_states', selection, state='inactive')
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count)
        self.reopen(); self.assertEqual(self.session._records, after)

    def test_ordered_range_null_zero_raw_and_unchanged_no_history(self):
        self.seed()
        before = deepcopy(self.session._records)
        selection = self.selection([2, 0])
        self.bulk('set_projected_module_ranges', selection, range_m=5e-324)
        after = deepcopy(self.session._records)
        for i in (0, 2): self.assertEqual(after[self.key]['spec']['projected_modules'][i]['range_m'], 5e-324)
        self.assertEqual(after[self.key]['spec']['projected_modules'][1], before[self.key]['spec']['projected_modules'][1])
        count = self.session.history_details(self.key)['undo_count']
        self.bulk('set_projected_module_ranges', selection, range_m=5e-324)
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count)
        self.bulk('set_projected_module_ranges', selection, range_m=None)
        self.assertTrue(all(self.rows()[i]['range_m'] is None for i in (0, 2)))
        null = deepcopy(self.session._records)
        self.bulk('set_projected_module_ranges', selection, range_m=0)
        self.assertTrue(all(self.rows()[i]['range_m'] == 0 for i in (0, 2)))
        self.edit('undo', dict(fit_id=self.key)); self.assertEqual(self.session._records, null)
        self.reopen(); self.assertEqual(self.session._records, null)

    def test_descending_removal_retains_legacy_unselected_identity_and_history(self):
        self.seed(environment=True)
        before = deepcopy(self.session._records)
        original = self.rows()
        selection = self.selection([1, 3])
        count = self.session.history_details(self.key)['undo_count']
        self.bulk('remove_projected_modules', selection)
        self.assertEqual([r['object_key'] for r in self.rows()], [original[i]['object_key'] for i in (0, 2, 4)])
        self.assertFalse(self.rows()[0]['editable'])
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count + 1)
        removed = deepcopy(self.session._records)
        self.edit('undo', dict(fit_id=self.key)); self.assertEqual(self.session._records, before)
        self.edit('redo', dict(fit_id=self.key)); self.assertEqual(self.session._records, removed)
        self.reopen(); self.assertEqual(self.session._records, removed)

    def test_entire_selection_prevalidated_invalid_shapes_stale_and_read_only(self):
        self.seed(environment=True)
        valid = self.selection([1, 3])
        bad_sets = [[], None, valid * 513, [valid[0], valid[0]],
                    [valid[0], dict(valid[1], object_key=valid[0]['object_key'])],
                    [valid[0], dict(valid[1], object_key='0' * 32)],
                    [valid[0], dict(valid[1], position=999)],
                    [valid[0], dict(valid[1], position=True)],
                    [valid[0], dict(valid[1], extra=1)],
                    [valid[0], dict(position=3)],
                    [valid[0], self.selection([0])[0]]]
        for selection in bad_sets:
            with self.subTest(selection=selection[:2] if type(selection) is list else selection):
                self.reject('remove_projected_modules', selection)
        self.reject('set_projected_module_states', valid, state='ACTIVE')
        for invalid in (-1, True, '1', 2**53 + 1):
            self.reject('set_projected_module_ranges', valid, range_m=invalid)
        request = self.request('remove_projected_modules', dict(fit_id=self.key, selection=valid))
        self.edit('rename_fit', dict(fit_id=self.key, name='Changed'))
        before = (self.path.read_bytes(), deepcopy(self.session._records))
        response = json.loads(self.session.dispatch(json.dumps(request)))
        self.assertEqual(response['error']['code'], 'REVISION_CONFLICT')
        self.assertEqual((self.path.read_bytes(), self.session._records), before)

    def test_failed_write_rolls_back_all_rows_and_history_then_retry(self):
        self.seed(drone=True)
        selection = self.selection([2, 0])
        for operation, args in [('set_projected_module_states', dict(state='inactive')),
                                ('set_projected_module_ranges', dict(range_m=1000)),
                                ('remove_projected_modules', {})]:
            with patch.object(self.session._store, 'write', side_effect=StoreWriteRejected('synthetic bulk failure')):
                self.reject(operation, selection, **args)
        self.bulk('remove_projected_modules', selection)
        self.assertEqual(len(self.rows()), 2)

    def test_bulk_values_all_five_refreshes_copy_profile_and_restart(self):
        self.seed(drone=True)
        self.bulk('set_projected_module_ranges', self.selection([2, 0]), range_m=5e-324)
        self.bulk('set_projected_module_states', self.selection([0, 2]), state='inactive')
        source = self.key
        other = self.edit('create_fit', dict(spec=dict(spec(), name='Bulk recipient')))['fits'][0]['id']
        expected = deepcopy(self.session._records[source])
        for operation, args in [
            ('add_projection', dict(source_id=source, target_id=other, range_m=0, active=True, amount=1)),
            ('remove_projection', dict(source_id=source, target_id=other)),
            ('add_command', dict(source_id=source, target_id=other, active=True)),
            ('remove_command', dict(source_id=source, target_id=other)),
            ('add_command_fit', dict(source_id=source, target_id=other)),
            ('remove_command_fit', dict(source_id=source, target_id=other)),
        ]:
            self.edit(operation, args)
            self.assertEqual(self.session._records[source], expected, operation)
        old = set(self.session._fits)
        self.edit('duplicate_fit', dict(fit_id=source, name='Copied bulk projectors'))
        copied = next(key for key in self.session._fits if key not in old)
        self.assertEqual(self.session._records[copied]['spec']['projected_modules'], expected['spec']['projected_modules'])
        self.assertTrue(set(self.session._records[copied]['inspection_ids']['projected_modules']).isdisjoint(
            expected['inspection_ids']['projected_modules']))
        self.feature('create_profile', dict(name='Bulk shared profile', source='builtin:all5'))
        pid = next(key for key, value in self.session.graph._state['profiles']['profiles'].items()
                   if value['name'] == 'Bulk shared profile')
        for key in (source, copied): self.feature('assign_profile', dict(fit_id=key, profile_id=pid))
        before = deepcopy(self.session._records)
        profile = self.session.graph._state['profiles']['profiles'][pid]
        skill = next(key for key, value in self.session.graph.catalog.items() if value.name == 'Navigation')
        self.feature('set_profile_skill', dict(profile_id=pid, revision=profile['revision'], skill_id=skill, level=4))
        for key in (source, copied):
            self.assertEqual(self.session._records[key]['spec']['projected_modules'], before[key]['spec']['projected_modules'])
            self.assertEqual(self.session._records[key]['inspection_ids'], before[key]['inspection_ids'])
        self.edit('undo', dict(fit_id=source)); self.assertEqual(self.session._records, before)
        self.edit('redo', dict(fit_id=source))
        graph = self.session.graph.snapshot(); snapshots = deepcopy(self.session._snapshots)
        self.reopen()
        self.assertEqual(self.session.graph.snapshot(), graph)
        self.assertEqual(self.session._snapshots, snapshots)
        for key in self.session._fits:
            self.assertEqual(self.session.history_details(key)['undo_count'], 0)
            self.assertEqual(self.session.history_details(key)['redo_count'], 0)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(ProjectedModuleBulkTests(name) for name in ProjectedModuleBulkTests.__dict__
                              if name.startswith('test_'))
