"""D01.5 atomic selected incoming drone integration invariants."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_projected_drone_editor import ProjectedDroneTests
from test_native_session import spec
from android_bridge.offline.profile_store import StoreWriteRejected


class ProjectedDroneBulkTests(ProjectedDroneTests):
    def seed(self):
        self.seeded([
            self.drone('Warrior SW-300', amount=5, active=2, range_m=63.7),
            self.drone('Valkyrie SW-600', amount=3, active=0, range_m=None),
            self.drone('Berserker SW-900', amount=2, active=2, range_m=5e-324),
            self.drone('Hornet EC-300', amount=4, active=0, range_m=0.0),
        ])
        # Materialize the original GUI fill before comparing complete identity.
        self.change('set_projected_drone_range', range_m=63.7)
        return self.rows()

    def selection(self, indices):
        rows = self.rows()
        return [dict(position=rows[i]['index'], object_key=rows[i]['object_key']) for i in indices]

    def bulk(self, operation, selection, **args):
        return self.edit(operation, dict(fit_id=self.key, selection=selection, **args))

    def reject_bulk(self, operation, selection, **args):
        return self.reject(operation, dict(fit_id=self.key, selection=selection, **args))

    def test_activation_partial_noop_whole_history_undo_redo(self):
        self.seed()
        before = deepcopy(self.session._records)
        selection = self.selection([2, 0, 1])
        count = self.session.history_details(self.key)['undo_count']
        self.bulk('set_projected_drones_active', selection, active=True)
        self.assertEqual([r['active'] for r in self.rows()], [2, 3, 2, 0])
        after = deepcopy(self.session._records)
        self.assertEqual(after[self.key]['inspection_ids'], before[self.key]['inspection_ids'])
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count + 1)
        self.undo(); self.assertEqual(self.session._records, before)
        self.redo(); self.assertEqual(self.session._records, after)
        count = self.session.history_details(self.key)['undo_count']
        self.bulk('set_projected_drones_active', selection, active=True)
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count)
        self.bulk('set_projected_drones_active', selection, active=False)
        self.assertEqual([r['active'] for r in self.rows()], [0, 0, 0, 0])
        self.reopen(); self.assertEqual([r['active'] for r in self.rows()], [0, 0, 0, 0])

    def test_ranges_null_zero_subnormal_preserve_unselected(self):
        self.seed()
        before = deepcopy(self.session._records)
        selection = self.selection([2, 0])
        for value in (5e-324, None, 0, 63.7):
            self.bulk('set_projected_drone_ranges', selection, range_m=value)
            rows = self.session._records[self.key]['spec']['projected_drones']
            for i in (0, 2): self.assertEqual(rows[i]['range_m'], value)
            for i in (1, 3): self.assertEqual(rows[i], before[self.key]['spec']['projected_drones'][i])
        final = deepcopy(self.session._records)
        self.reopen(); self.assertEqual(self.session._records, final)

    def test_whole_stack_removal_noncontiguous_preserves_identity(self):
        original = self.seed()
        before = deepcopy(self.session._records)
        count = self.session.history_details(self.key)['undo_count']
        self.bulk('remove_projected_drones', self.selection([0, 2]))
        self.assertEqual([r['object_key'] for r in self.rows()], [original[i]['object_key'] for i in (1, 3)])
        self.assertEqual([r['amount'] for r in self.rows()], [3, 4])
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count + 1)
        after = deepcopy(self.session._records)
        self.undo(); self.assertEqual(self.session._records, before)
        self.redo(); self.assertEqual(self.session._records, after)
        self.reopen(); self.assertEqual(self.session._records, after)

    def test_invalid_complete_selection_and_stale_revision(self):
        self.seed()
        valid = self.selection([0, 2])
        bad = [[], None, valid * 513, [valid[0], valid[0]],
               [valid[0], dict(valid[1], object_key=valid[0]['object_key'])],
               [valid[0], dict(valid[1], object_key='0' * 32)],
               [valid[0], dict(valid[1], position=999)],
               [valid[0], dict(valid[1], position=True)],
               [valid[0], dict(valid[1], extra=1)], [valid[0], dict(position=2)]]
        for selection in bad:
            self.reject_bulk('remove_projected_drones', selection)
        for active in (0, 1, None, 'true'):
            self.reject_bulk('set_projected_drones_active', valid, active=active)
        for value in (-1, True, '1', 2**53 + 1):
            self.reject_bulk('set_projected_drone_ranges', valid, range_m=value)
        request = self.request('remove_projected_drones', dict(fit_id=self.key, selection=valid))
        self.edit('rename_fit', dict(fit_id=self.key, name='Changed'))
        before = self.state()
        response = json.loads(self.session.dispatch(json.dumps(request)))
        self.assertEqual(response['error']['code'], 'REVISION_CONFLICT')
        self.assertEqual(self.state(), before)

    def test_write_failure_restores_complete_graph_then_retry(self):
        self.seed()
        selection = self.selection([2, 0, 1])
        for operation, args in [('set_projected_drones_active', dict(active=True)),
                                ('set_projected_drone_ranges', dict(range_m=1000)),
                                ('remove_projected_drones', {})]:
            with patch.object(self.session._store, 'write', side_effect=StoreWriteRejected('synthetic selected failure')):
                self.reject_bulk(operation, selection, **args)
        self.bulk('remove_projected_drones', selection)
        self.assertEqual([r['name'] for r in self.rows()], ['Hornet EC-300'])

    def test_bulk_values_all_five_refreshes_copy_profile_and_restart(self):
        self.seed()
        self.bulk('set_projected_drone_ranges', self.selection([2, 0]), range_m=5e-324)
        self.bulk('set_projected_drones_active', self.selection([0, 2]), active=False)
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
        self.edit('duplicate_fit', dict(fit_id=source, name='Copied bulk drone stacks'))
        copied = next(key for key in self.session._fits if key not in old)
        self.assertEqual(self.session._records[copied]['spec']['projected_drones'], expected['spec']['projected_drones'])
        self.assertTrue(set(self.session._records[copied]['inspection_ids']['projected_drones']).isdisjoint(
            expected['inspection_ids']['projected_drones']))
        self.feature('create_profile', dict(name='Bulk shared profile', source='builtin:all5'))
        pid = next(key for key, value in self.session.graph._state['profiles']['profiles'].items()
                   if value['name'] == 'Bulk shared profile')
        for key in (source, copied): self.feature('assign_profile', dict(fit_id=key, profile_id=pid))
        before = deepcopy(self.session._records)
        profile = self.session.graph._state['profiles']['profiles'][pid]
        skill = next(key for key, value in self.session.graph.catalog.items() if value.name == 'Navigation')
        self.feature('set_profile_skill', dict(profile_id=pid, revision=profile['revision'], skill_id=skill, level=4))
        for key in (source, copied):
            self.assertEqual(self.session._records[key]['spec']['projected_drones'], before[key]['spec']['projected_drones'])
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
    return unittest.TestSuite(ProjectedDroneBulkTests(name) for name in ProjectedDroneBulkTests.__dict__
                              if name.startswith('test_'))
