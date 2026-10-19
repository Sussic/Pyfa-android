"""Incoming similarity is bounded read-only metadata; returned identities drive bulk edits."""
import unittest
from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import patch
from test_projected_fighter_editor import ProjectedFighterTests
from test_native_session import spec
from android_bridge.projected_fighter_selection import selection


class ProjectedFighterSelectionTests(ProjectedFighterTests):
    def seed(self):
        for name in ('Dromi I','Cenobite I','Dromi II','Dromi I','Siren I'):self.add(name)
    def query(self, position=0):return self.session.projected_fighter_similar_selection(self.key,position)

    def test_real_noncontiguous_cross_type_duplicates_and_readonly_no_evaluation(self):
        self.seed();before=self.state();recent=self.session.recent_items()
        with patch.object(self.engine,'prepare_read',side_effect=AssertionError('metadata query must not prepare effects')), \
             patch.object(self.engine,'_recalculate',side_effect=AssertionError('metadata query must not calculate')), \
             patch('eos.capSim.CapSimulator.run',side_effect=AssertionError('metadata query must not simulate')), \
             patch.object(self.session._store,'write',side_effect=AssertionError('metadata query must not write')):
            result=self.query(2);self.assertEqual(self.query(2),result)
            self.assertEqual([r['index'] for r in result['matches']],[0,2,3])
            self.assertEqual(result['main'],result['matches'][1])
            self.assertEqual(len({r['object_key'] for r in result['matches']}),3)
            self.assertEqual(result['fit_id'],self.key);self.assertEqual(result['revision'],self.session._revisions[self.key])
            self.assertEqual([r['index'] for r in self.query(1)['matches']],[1])
            self.assertEqual([r['index'] for r in self.query(4)['matches']],[4])
        self.assertEqual(self.state(),before);self.assertEqual(self.session.recent_items(),recent)

    def test_activation_quantity_range_and_ability_bits_do_not_change_membership(self):
        self.seed();expected=self.query()['matches']
        self.change('set_projected_fighter_amount',2,amount=1)
        self.change('set_projected_fighter_active',2,active=False)
        self.change('set_projected_fighter_range',2,range_m=5e-324)
        self.change('toggle_projected_fighter_ability',2,effect_id=6435)
        self.change('toggle_projected_fighter_ability',2,effect_id=6441)
        self.assertEqual(self.query()['matches'],expected)

    def test_returned_noncontiguous_selection_real_bulk_edit_exact_history_and_restart(self):
        self.seed();result=self.query(2);before=deepcopy(self.session._records);count=self.session.history_details(self.key)['undo_count']
        selected=[dict(position=r['index'],object_key=r['object_key']) for r in result['matches']]
        main=dict(position=result['main']['index'],object_key=result['main']['object_key'])
        speed=self.speed()
        self.edit('toggle_projected_fighter_abilities',dict(fit_id=self.key,main=main,selection=selected,effect_id=6435))
        after=deepcopy(self.session._records);self.assertGreater(self.speed(),speed)
        for i in (1,4):self.assertEqual(after[self.key]['spec']['projected_fighters'][i],before[self.key]['spec']['projected_fighters'][i])
        self.assertEqual(self.session.history_details(self.key)['undo_count'],count+1)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.session._records,after)
        self.reopen();self.assertEqual(self.session._records,after);self.assertEqual(self.query(2)['matches'],result['matches'])

    def test_invalid_positions_unknown_fit_and_unavailable_preserve_saved_state(self):
        self.seed();before=self.state()
        for position in (-1,5,True,None,'0',0.0,[],{}):
            with self.assertRaises(ValueError):self.query(position)
        with self.assertRaises(KeyError):self.session.projected_fighter_similar_selection('0'*32,0)
        with patch.object(self.session.graph._bridge,'_available',False):
            with self.assertRaisesRegex(RuntimeError,'Restart'):self.query()
        self.assertEqual(self.state(),before)

    def test_all_refreshes_shared_profile_copy_and_restart_keep_exact_selection(self):
        self.seed();source=self.key;expected=self.query(2)['matches']
        other=self.edit('create_fit',dict(spec=dict(spec(),name='Selection recipient')))['fits'][0]['id']
        for operation,args in [
            ('add_projection',dict(source_id=source,target_id=other,range_m=0,active=True,amount=1)),
            ('remove_projection',dict(source_id=source,target_id=other)),
            ('add_command',dict(source_id=source,target_id=other,active=True)),
            ('remove_command',dict(source_id=source,target_id=other)),
            ('add_command_fit',dict(source_id=source,target_id=other)),
            ('remove_command_fit',dict(source_id=source,target_id=other))]:
            self.edit(operation,args);self.assertEqual(self.query(2)['matches'],expected)
        self.feature('assign_profile',dict(fit_id=source,profile_id='builtin:all0'))
        self.assertEqual(self.query(2)['matches'],expected)
        old=set(self.session._fits);self.edit('duplicate_fit',dict(fit_id=source,name='Selection copy'))
        copied=next(k for k in self.session._fits if k not in old)
        copy_result=self.session.projected_fighter_similar_selection(copied,2)
        self.assertEqual([r['index'] for r in copy_result['matches']],[0,2,3])
        self.assertTrue({r['object_key'] for r in copy_result['matches']}.isdisjoint(r['object_key'] for r in expected))
        self.reopen();self.assertEqual(self.query(2)['matches'],expected)


class ProjectedSelectionBoundsTests(unittest.TestCase):
    def test_container_bound_checked_before_iteration_or_main_lookup(self):
        class Oversize:
            def __len__(self):return 1025
            def __iter__(self):raise AssertionError('must refuse before scan')
            def __getitem__(self,index):raise AssertionError('must refuse before main lookup')
        engine=N(_check_fit=lambda fit:None);fit=N(isStructure=False,projectedFighters=Oversize())
        with self.assertRaisesRegex(ValueError,'Select at most 1024'):selection(engine,fit,0)

    def test_metadata_scan_refuses_structure_ineligible_and_oversize_abilities(self):
        engine=N(_check_fit=lambda fit:None)
        with self.assertRaisesRegex(ValueError,'structures'):selection(engine,N(isStructure=True),0)
        item=N(category=N(name='Fighter'),isType=lambda name:True)
        fighter=N(item=item,abilities=[N(effectID=i) for i in range(129)])
        fit=N(isStructure=False,projectedFighters=[fighter])
        with self.assertRaisesRegex(ValueError,'Unsupported'):selection(engine,fit,0)
        fighter.abilities=[];item.category.name='Drone'
        with self.assertRaisesRegex(ValueError,'Unsupported'):selection(engine,fit,0)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite([ProjectedFighterSelectionTests(name) for name in ProjectedFighterSelectionTests.__dict__ if name.startswith('test_')]+[ProjectedSelectionBoundsTests(name) for name in ProjectedSelectionBoundsTests.__dict__ if name.startswith('test_')])
