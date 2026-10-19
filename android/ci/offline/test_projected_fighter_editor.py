"""Durable incoming fighter integration; original-command oracle is separate."""
import json
from copy import deepcopy
import unittest
from unittest.mock import patch
from test_native_session import NativeSessionTests, spec
from android_bridge.offline.profile_store import StoreWriteRejected


class ProjectedFighterTests(NativeSessionTests):
    def item(self, name): return self.engine._item(name).ID
    def rows(self): return self.session.projected_fighter_details(self.key)['squadrons']
    def add(self, name='Dromi I'):
        return self.edit('add_projected_fighter', dict(fit_id=self.key, item_id=self.item(name)))
    def change(self, operation, index=0, **args):
        row = self.rows()[index]
        return self.edit(operation, dict(fit_id=self.key, position=row['index'], object_key=row['object_key'], **args))
    def state(self):
        return dict(bytes=self.path.read_bytes(), records=deepcopy(self.session._records),
                    graph=self.session.graph.snapshot(), revisions=deepcopy(self.session._revisions),
                    snapshots=deepcopy(self.session._snapshots), context=self.session.context(),
                    history={key:self.session.history_details(key) for key in self.session._fits},
                    library_history=self.session.feature_state()['history'])
    def reject(self, operation, arguments):
        before = self.state()
        value = json.loads(self.session.dispatch(json.dumps(self.request(operation, arguments))))
        self.assertEqual(value['status'], 'error', value)
        self.assertEqual(self.state(), before)
        self.assertTrue(self.session._available)
        return value
    def args(self, index=0, **values):
        row = self.rows()[index]
        return dict(fit_id=self.key, position=row['index'], object_key=row['object_key'], **values)
    def speed(self): return self.session._snapshots[self.key]['stats']['max_velocity']['value']

    def test_real_duplicate_squadrons_quantity_maximum_and_exact_history(self):
        before_speed = self.speed()
        self.add(); first = self.rows()[0]; one_speed = self.speed()
        self.assertEqual(first['amount'], 3); self.assertEqual(first['max_size'], 3)
        self.assertLess(one_speed, before_speed)
        self.add(); self.assertLess(self.speed(), one_speed)
        self.assertEqual([r['item_id'] for r in self.rows()], [self.item('Dromi I')]*2)
        self.assertNotEqual(self.rows()[0]['object_key'], self.rows()[1]['object_key'])
        before = deepcopy(self.session._records)
        self.change('set_projected_fighter_amount', amount=1)
        self.assertEqual(self.rows()[0]['amount'], 1)
        self.assertEqual(self.rows()[0]['object_key'], first['object_key'])
        after = deepcopy(self.session._records)
        self.edit('undo', dict(fit_id=self.key)); self.assertEqual(self.session._records, before)
        self.edit('redo', dict(fit_id=self.key)); self.assertEqual(self.session._records, after)
        self.change('set_projected_fighter_amount', amount=2**31-1)
        self.assertEqual(self.rows()[0]['amount'], 3)
        self.change('set_projected_fighter_amount', amount=0)
        self.assertEqual(len(self.rows()), 1)
        self.assertNotEqual(self.rows()[0]['object_key'], first['object_key'])
        final = deepcopy(self.session._records); self.reopen(); self.assertEqual(self.session._records, final)

    def test_active_ability_and_nonprojected_prop_state_preserve_complete_bits(self):
        base = self.speed(); self.add(); affected = self.speed()
        opts = self.session.projected_fighter_options(self.key, 0)
        self.assertEqual({a['effect_id'] for a in opts['abilities']}, {6435, 6441})
        self.change('toggle_projected_fighter_ability', effect_id=6435)
        self.assertEqual(self.speed(), base)
        count = self.session.history_details(self.key)['undo_count']
        self.change('toggle_projected_fighter_ability', effect_id=6441)
        self.assertEqual(self.speed(), base)
        self.assertEqual(self.session.history_details(self.key)['undo_count'], count+1)
        self.change('toggle_projected_fighter_ability', effect_id=6435)
        self.assertEqual(self.speed(), affected)
        self.change('set_projected_fighter_active', active=False)
        self.assertEqual(self.speed(), base)
        self.change('set_projected_fighter_active', active=True)
        self.assertEqual(self.speed(), affected)
        final = deepcopy(self.session._records); self.reopen(); self.assertEqual(self.session._records, final)
        self.assertTrue(all(a['active'] for a in final[self.key]['spec']['projected_fighters'][0]['abilities']))

    def test_variation_moves_to_tail_resets_range_preserves_matching_abilities(self):
        self.add(); self.add('Cenobite I')
        self.change('set_projected_fighter_amount', amount=1)
        self.change('set_projected_fighter_range', range_m=63.7)
        self.change('toggle_projected_fighter_ability', effect_id=6435)
        before = deepcopy(self.session._records); old_key = self.rows()[0]['object_key']
        self.change('change_projected_fighter_variation', item_id=self.item('Dromi II'))
        rows = self.rows(); self.assertEqual([r['name'] for r in rows], ['Cenobite I','Dromi II'])
        self.assertEqual(rows[1]['amount'], 1); self.assertIsNone(rows[1]['range_m'])
        self.assertNotEqual(rows[1]['object_key'], old_key)
        self.assertFalse(next(a for a in self.session.projected_fighter_options(self.key,1)['abilities'] if a['effect_id']==6435)['active'])
        after = deepcopy(self.session._records)
        self.edit('undo',dict(fit_id=self.key)); self.assertEqual(self.session._records,before)
        self.edit('redo',dict(fit_id=self.key)); self.assertEqual(self.session._records,after)
        self.reopen(); self.assertEqual(self.session._records,after)

    def test_nullable_fractional_subnormal_ranges_replay_and_noops(self):
        self.add()
        for value in (5e-324, 63.7, 0, None):
            self.change('set_projected_fighter_range', range_m=value)
            self.assertEqual(self.rows()[0]['range_m'],value)
            before = deepcopy(self.session._records); count=self.session.history_details(self.key)['undo_count']
            self.change('set_projected_fighter_range', range_m=value)
            self.assertEqual(self.session._records,before)
            self.assertEqual(self.session.history_details(self.key)['undo_count'],count)
        self.change('set_projected_fighter_range', range_m=5e-324)
        before=deepcopy(self.session._records); self.reopen(); self.assertEqual(self.session._records,before)

    def test_invalid_shapes_stale_identity_wrong_type_and_write_failure(self):
        self.add()
        for op, values in [('set_projected_fighter_amount',dict(amount=-1)),
                           ('set_projected_fighter_amount',dict(amount=True)),
                           ('set_projected_fighter_active',dict(active=1)),
                           ('toggle_projected_fighter_ability',dict(effect_id=999999)),
                           ('toggle_projected_fighter_ability',dict(effect_id=True)),
                           ('set_projected_fighter_range',dict(range_m=-1)),
                           ('set_projected_fighter_range',dict(range_m=True)),
                           ('change_projected_fighter_variation',dict(item_id=self.item('Firbolg I')))]:
            self.reject(op,self.args(**values))
        self.reject('remove_projected_fighter',dict(self.args(),object_key='0'*32))
        self.reject('add_projected_fighter',dict(fit_id=self.key,item_id=self.item('Firbolg I')))
        request=self.request('remove_projected_fighter',self.args())
        self.edit('rename_fit',dict(fit_id=self.key,name='New revision'))
        before=self.state();response=json.loads(self.session.dispatch(json.dumps(request)))
        self.assertEqual(response['error']['code'],'REVISION_CONFLICT');self.assertEqual(self.state(),before)
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic fighter failure')):
            self.reject('remove_projected_fighter',self.args())
        self.change('remove_projected_fighter');self.assertEqual(self.rows(),[])

    def test_optional_empty_family_zero_saved_row_and_complete_ability_validation(self):
        self.assertNotIn('projected_fighters',self.session._records[self.key]['spec'])
        self.add(); value=deepcopy(self.session._records[self.key]['spec'])
        value['projected_fighters'][0]['amount']=0
        self.key=self.edit('create_fit',dict(spec=value))['fits'][0]['id']
        self.assertEqual(self.rows()[0]['amount'],0)
        self.change('set_projected_fighter_amount',amount=0);self.assertEqual(self.rows(),[])
        self.assertEqual(self.session._records[self.key]['spec']['projected_fighters'],[])
        before=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,before)
        for change in ('missing','duplicate','unknown'):
            bad=deepcopy(value)
            if change=='missing':bad['projected_fighters'][0]['abilities'].pop()
            elif change=='duplicate':bad['projected_fighters'][0]['abilities']*=2
            else:bad['projected_fighters'][0]['abilities'][0]['effect_id']=1
            self.reject('create_fit',dict(spec=bad))

    def test_five_refreshes_shared_profile_copy_and_exact_restart(self):
        self.add(); self.add(); self.add('Cenobite I')
        self.change('set_projected_fighter_amount', amount=1)
        self.change('set_projected_fighter_range', range_m=5e-324)
        self.change('toggle_projected_fighter_ability', effect_id=6435)
        self.change('toggle_projected_fighter_ability', effect_id=6441)
        source=self.key
        other=self.edit('create_fit',dict(spec=dict(spec(),name='Fighter recipient')))['fits'][0]['id']
        expected=deepcopy(self.session._records[source])
        for operation,args in [
            ('add_projection',dict(source_id=source,target_id=other,range_m=0,active=True,amount=1)),
            ('remove_projection',dict(source_id=source,target_id=other)),
            ('add_command',dict(source_id=source,target_id=other,active=True)),
            ('remove_command',dict(source_id=source,target_id=other)),
            ('add_command_fit',dict(source_id=source,target_id=other)),
            ('remove_command_fit',dict(source_id=source,target_id=other))]:
            self.edit(operation,args);self.assertEqual(self.session._records[source],expected,operation)
        old=set(self.session._fits);self.edit('duplicate_fit',dict(fit_id=source,name='Copied incoming squadrons'))
        copied=next(k for k in self.session._fits if k not in old)
        self.assertEqual(self.session._records[copied]['spec']['projected_fighters'],expected['spec']['projected_fighters'])
        self.assertTrue(set(self.session._records[copied]['inspection_ids']['projected_fighters']).isdisjoint(expected['inspection_ids']['projected_fighters']))
        self.feature('create_profile',dict(name='Fighter profile',source='builtin:all5'))
        pid=next(k for k,v in self.session.graph._state['profiles']['profiles'].items() if v['name']=='Fighter profile')
        for key in (source,copied):self.feature('assign_profile',dict(fit_id=key,profile_id=pid))
        before=deepcopy(self.session._records);profile=self.session.graph._state['profiles']['profiles'][pid]
        skill=next(k for k,v in self.session.graph.catalog.items() if v.name=='Navigation')
        self.feature('set_profile_skill',dict(profile_id=pid,revision=profile['revision'],skill_id=skill,level=4))
        for key in (source,copied):
            self.assertEqual(self.session._records[key]['spec']['projected_fighters'],before[key]['spec']['projected_fighters'])
            self.assertEqual(self.session._records[key]['inspection_ids'],before[key]['inspection_ids'])
        self.edit('undo',dict(fit_id=source));self.assertEqual(self.session._records,before)
        self.edit('redo',dict(fit_id=source));graph=self.session.graph.snapshot();stats=deepcopy(self.session._snapshots)
        self.reopen();self.assertEqual(self.session.graph.snapshot(),graph);self.assertEqual(self.session._snapshots,stats)
        for key in self.session._fits:self.assertEqual(self.session.history_details(key)['undo_count'],0)

    def test_read_only_queries_loss_aware_export_and_structure_refusal(self):
        self.add();before=self.state()
        self.rows();self.session.projected_fighter_options(self.key,0)
        good=self.session.projected_fighter_add_options(self.key,self.item('Dromi I'))
        bad=self.session.projected_fighter_add_options(self.key,self.item('Firbolg I'))
        self.assertTrue(good['enabled']);self.assertFalse(bad['enabled'])
        request=dict(version=1,request_id='fighter-export',context=self.session.context(),fit_id=self.key,
                     revision=self.session._revisions[self.key],options=dict.fromkeys(('loaded_charges','cargo','implants','boosters','mutations'),True))
        result=json.loads(self.session.export_preview(json.dumps(request)))
        self.assertTrue(result['ok'],result)
        self.assertIn('projected_fighters_lost',{r['code'] for r in result['diagnostics']})
        self.assertNotIn('Dromi I',result['text']);self.assertEqual(self.state(),before)
        self.key=self.edit('create_fit',dict(spec=dict(spec(),ship='Astrahus')))['fits'][0]['id']
        self.assertTrue(self.session.projected_fighter_details(self.key)['is_structure'])
        self.assertFalse(self.session.projected_fighter_add_options(self.key,self.item('Dromi I'))['enabled'])
        self.reject('add_projected_fighter',dict(fit_id=self.key,item_id=self.item('Dromi I')))



def load_tests(loader, tests, pattern):
    return unittest.TestSuite(ProjectedFighterTests(name) for name in ProjectedFighterTests.__dict__
                              if name.startswith('test_'))
