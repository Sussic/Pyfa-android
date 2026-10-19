"""D01.7 one-transaction incoming-squadron integration invariants."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_projected_fighter_editor import ProjectedFighterTests
from test_native_session import spec
from android_bridge.offline.profile_store import StoreWriteRejected


class ProjectedFighterBulkTests(ProjectedFighterTests):
    def seed(self):
        for name in ('Dromi I','Cenobite I','Dromi I','Siren I'): self.add(name)
        self.change('set_projected_fighter_amount',0,amount=1)
        self.change('set_projected_fighter_range',0,range_m=63.7)
        self.change('set_projected_fighter_range',2,range_m=5e-324)
        self.change('set_projected_fighter_active',2,active=False)
        self.change('toggle_projected_fighter_ability',2,effect_id=6435)
        return self.rows()

    def selection(self, indices):
        rows=self.rows()
        return [dict(position=rows[i]['index'],object_key=rows[i]['object_key']) for i in indices]

    def bulk(self, operation, indices, **args):
        return self.edit(operation,dict(fit_id=self.key,selection=self.selection(indices),**args))

    def raw(self): return self.session._records[self.key]['spec']['projected_fighters']

    def bits(self, index): return {a['effect_id']:a['active'] for a in self.raw()[index]['abilities']}

    def test_selected_activation_one_history_noop_and_untouched_counts(self):
        self.seed();before=deepcopy(self.session._records);count=self.session.history_details(self.key)['undo_count']
        self.bulk('set_projected_fighters_active',[2,0],active=True)
        self.assertEqual([r['active'] for r in self.rows()],[True,True,True,True])
        self.assertEqual([r['amount'] for r in self.rows()],[1,3,3,3])
        self.assertFalse(self.bits(2)[6435])
        after=deepcopy(self.session._records)
        self.assertEqual(self.session.history_details(self.key)['undo_count'],count+1)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.session._records,after)
        count=self.session.history_details(self.key)['undo_count']
        self.bulk('set_projected_fighters_active',[2,0],active=True)
        self.assertEqual(self.session.history_details(self.key)['undo_count'],count)
        self.bulk('set_projected_fighters_active',[2,0],active=False)
        self.assertEqual([r['active'] for r in self.rows()],[False,True,False,True])

    def test_main_drives_one_direction_skips_missing_secondary_and_appends_main(self):
        self.seed();before=deepcopy(self.raw());main=self.selection([0])[0]
        self.bulk('toggle_projected_fighter_abilities',[2,1],main=main,effect_id=6435)
        self.assertFalse(self.bits(0)[6435]);self.assertFalse(self.bits(2)[6435])
        self.assertEqual(self.raw()[1],before[1]);self.assertEqual(self.raw()[3],before[3])
        self.assertFalse(self.rows()[2]['active']);self.assertEqual(self.bits(0)[6441],next(a['active'] for a in before[0]['abilities'] if a['effect_id']==6441))
        self.bulk('toggle_projected_fighter_abilities',[0,1],main=self.selection([2])[0],effect_id=6435)
        self.assertTrue(self.bits(0)[6435]);self.assertTrue(self.bits(2)[6435])
        self.assertFalse(self.rows()[2]['active'])
        # Propulsion is editable while incoming numerical output is unchanged.
        stats={k:deepcopy(v['stats']) for k,v in self.session._snapshots.items()}
        revision=self.session._revisions[self.key]
        self.bulk('toggle_projected_fighter_abilities',[0,2],main=self.selection([0])[0],effect_id=6441)
        self.assertTrue(self.bits(0)[6441]);self.assertTrue(self.bits(2)[6441])
        self.assertEqual({k:v['stats'] for k,v in self.session._snapshots.items()},stats)
        self.assertGreater(self.session._revisions[self.key],revision)

    def test_exact_raw_ranges_preserve_unselected_and_reopen(self):
        self.seed();before=deepcopy(self.raw())
        for value in (None,0,63.7,5e-324):
            self.bulk('set_projected_fighter_ranges',[2,0],range_m=value)
            for i in (0,2):self.assertEqual(self.raw()[i]['range_m'],value)
            for i in (1,3):self.assertEqual(self.raw()[i],before[i])
        final=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,final)

    def test_complete_removal_retains_order_identity_and_exact_undo(self):
        rows=self.seed();before=deepcopy(self.session._records);count=self.session.history_details(self.key)['undo_count']
        self.bulk('remove_projected_fighters',[0,2])
        self.assertEqual([r['object_key'] for r in self.rows()],[rows[i]['object_key'] for i in (1,3)])
        self.assertEqual(self.session.history_details(self.key)['undo_count'],count+1)
        after=deepcopy(self.session._records);self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.session._records,after)
        self.bulk('remove_projected_fighters',[1,0]);self.assertEqual(self.raw(),[])
        final=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,final)

    def test_invalid_whole_selection_main_and_values_preserve_durable_state(self):
        self.seed();selected=self.selection([2,0]);main=self.selection([0])[0]
        bads=[None,[],{},[selected[0],selected[0]],selected+[dict(position=99,object_key='0'*32)],
              [dict(selected[0],position=True)], [dict(selected[0],object_key='F'*32)],
              [dict(selected[0],extra=1)], [dict(selected[0],object_key=selected[1]['object_key'])]]
        for selection in bads:
            self.reject('set_projected_fighters_active',dict(fit_id=self.key,selection=selection,active=True))
        for value in (None,1,'true'):
            self.reject('set_projected_fighters_active',dict(fit_id=self.key,selection=selected,active=value))
        for value in (True,-1,'2',float('inf')):
            self.reject('set_projected_fighter_ranges',dict(fit_id=self.key,selection=selected,range_m=value))
        for effect in (None,True,-1,6434,999999):
            self.reject('toggle_projected_fighter_abilities',dict(fit_id=self.key,selection=selected,main=main,effect_id=effect))
        self.reject('toggle_projected_fighter_abilities',dict(fit_id=self.key,selection=selected,main=dict(main,object_key='0'*32),effect_id=6435))
        request=self.request('remove_projected_fighters',dict(fit_id=self.key,selection=selected))
        self.bulk('set_projected_fighters_active',[1],active=False);before=self.state()
        result=json.loads(self.session.dispatch(json.dumps(request)));self.assertEqual(result['status'],'error');self.assertEqual(self.state(),before)

    def test_failed_durable_write_restores_all_rows_then_retry(self):
        self.seed();args=dict(fit_id=self.key,selection=self.selection([0,2]),main=self.selection([0])[0],effect_id=6435)
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('injected')):
            self.reject('toggle_projected_fighter_abilities',args)
        self.edit('toggle_projected_fighter_abilities',args)
        self.assertFalse(self.bits(0)[6435]);self.assertFalse(self.bits(2)[6435])

    def test_bulk_values_all_refreshes_copy_shared_profile_and_exact_restart(self):
        self.seed();self.bulk('set_projected_fighters_active',[0,2],active=False)
        self.bulk('set_projected_fighter_ranges',[2,0],range_m=5e-324)
        self.bulk('toggle_projected_fighter_abilities',[2,1],main=self.selection([0])[0],effect_id=6435)
        source=self.key;other=self.edit('create_fit',dict(spec=dict(spec(),name='Bulk fighter recipient')))['fits'][0]['id']
        expected=deepcopy(self.session._records[source])
        for operation,args in [
            ('add_projection',dict(source_id=source,target_id=other,range_m=0,active=True,amount=1)),
            ('remove_projection',dict(source_id=source,target_id=other)),
            ('add_command',dict(source_id=source,target_id=other,active=True)),
            ('remove_command',dict(source_id=source,target_id=other)),
            ('add_command_fit',dict(source_id=source,target_id=other)),
            ('remove_command_fit',dict(source_id=source,target_id=other))]:
            self.edit(operation,args);self.assertEqual(self.session._records[source],expected)
        old=set(self.session._fits);self.edit('duplicate_fit',dict(fit_id=source,name='Bulk fighter copy'))
        copied=next(k for k in self.session._fits if k not in old)
        self.assertTrue(set(self.session._records[copied]['inspection_ids']['projected_fighters']).isdisjoint(expected['inspection_ids']['projected_fighters']))
        self.feature('create_profile',dict(name='Selected fighter profile',source='builtin:all5'))
        pid=next(k for k,v in self.session.graph._state['profiles']['profiles'].items() if v['name']=='Selected fighter profile')
        for key in (source,copied):self.feature('assign_profile',dict(fit_id=key,profile_id=pid))
        before=deepcopy(self.session._records);profile=self.session.graph._state['profiles']['profiles'][pid]
        skill=next(k for k,v in self.session.graph.catalog.items() if v.name=='Navigation')
        self.feature('set_profile_skill',dict(profile_id=pid,revision=profile['revision'],skill_id=skill,level=4))
        self.edit('undo',dict(fit_id=source));self.assertEqual(self.session._records,before)
        self.edit('redo',dict(fit_id=source));graph=self.session.graph.snapshot();stats=deepcopy(self.session._snapshots)
        self.reopen();self.assertEqual(self.session.graph.snapshot(),graph);self.assertEqual(self.session._snapshots,stats)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(ProjectedFighterBulkTests(name) for name in ProjectedFighterBulkTests.__dict__ if name.startswith('test_'))
