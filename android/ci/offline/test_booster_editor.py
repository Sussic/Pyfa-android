"""C08 integrated booster transactions and read contracts."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_native_session import NativeSessionTests,spec
from android_bridge.offline.profile_store import StoreWriteRejected

class BoosterEditorTests(NativeSessionTests):
    def item(self,name='Standard Blue Pill Booster'):return self.engine._item(name).ID
    def fit(self,name='Standard Blue Pill Booster'):
        return self.edit('fit_booster',dict(fit_id=self.key,item_id=self.item(name)))
    def rows(self):return self.session.booster_details(self.key)['boosters']
    def rejected(self,op,args):
        before=self.path.read_bytes();state=self.session.graph.snapshot();hist=self.session.history_details(self.key)
        value=json.loads(self.session.dispatch(json.dumps(self.request(op,args))))
        self.assertEqual(value['status'],'error',value)
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph.snapshot());self.assertEqual(hist,self.session.history_details(self.key))
        return value
    def test_add_options_are_readonly_and_nonbooster_explicit(self):
        before=self.path.read_bytes();state=self.session.graph.snapshot()
        row=self.session.booster_add_options(self.key,self.item())
        self.assertTrue(row['is_booster']);self.assertFalse(row['is_structure']);self.assertIsNone(row['occupant']);self.assertFalse(row['already_fitted'])
        other=self.session.booster_add_options(self.key,self.item('Small Armor Repairer I'))
        self.assertFalse(other['is_booster']);self.assertIsNone(other['slot']);self.assertIsNone(other['occupant'])
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph.snapshot())
    def test_atomic_replacement_defaults_and_undo_identity(self):
        self.fit();old=deepcopy(self.rows());effect=old[0]['side_effects'][0]['effect_id']
        self.edit('set_booster_side_effect',dict(fit_id=self.key,position=0,effect_id=effect,active=True))
        self.edit('set_booster_active',dict(fit_id=self.key,position=0,active=False))
        old=deepcopy(self.rows());count=self.session.history_details(self.key)['undo_count']
        self.fit('Improved Blue Pill Booster');new=self.rows()
        self.assertEqual(len(new),1);self.assertTrue(new[0]['active']);self.assertTrue(all(not e['active'] for e in new[0]['side_effects']))
        self.assertNotEqual(new[0]['object_key'],old[0]['object_key']);self.assertEqual(self.session.history_details(self.key)['undo_count'],count+1)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows(),old)
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.rows(),new)
    def test_variation_carries_states_and_restart(self):
        self.fit();old=self.rows()[0];effect=old['side_effects'][0]['effect_id']
        self.edit('set_booster_side_effect',dict(fit_id=self.key,position=0,effect_id=effect,active=True))
        self.edit('set_booster_active',dict(fit_id=self.key,position=0,active=False))
        self.edit('change_booster_variation',dict(fit_id=self.key,position=0,item_id=self.item('Improved Blue Pill Booster')))
        row=self.rows()[0];self.assertFalse(row['active']);self.assertTrue(next(e['active'] for e in row['side_effects'] if e['effect_id']==effect))
        saved=deepcopy(self.session._records[self.key]['boosters']);self.reopen()
        self.assertEqual(self.session._records[self.key]['boosters'],saved);self.assertEqual(self.rows()[0]['side_effects'],row['side_effects'])
    def test_replacement_reorders_and_selected_toggle_remove(self):
        self.fit();self.fit('Standard Frentix Booster');rows=self.rows();self.assertEqual(len(rows),2)
        self.fit('Improved Blue Pill Booster');self.assertEqual(self.rows()[0]['name'],'Standard Frentix Booster')
        self.edit('toggle_boosters',dict(fit_id=self.key,main_position=0,positions=[1]));self.assertTrue(all(not r['active'] for r in self.rows()))
        old=deepcopy(self.rows());self.edit('remove_boosters',dict(fit_id=self.key,positions=[0,1]));self.assertFalse(self.rows())
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows(),old)
    def test_invalid_and_duplicate_preserve_everything(self):
        self.fit()
        for op,args in [('fit_booster',dict(item_id=self.item())),('fit_booster',dict(item_id=self.item('Small Armor Repairer I'))),('change_booster_variation',dict(position=0,item_id=self.item('Standard Frentix Booster'))),('toggle_boosters',dict(main_position=0,positions=[0,0])),('remove_boosters',dict(positions=[True]))]:
            self.rejected(op,dict(fit_id=self.key,**args))
    def test_old_add_still_rejects_occupied_slot(self):
        self.fit();self.rejected('add_booster',dict(fit_id=self.key,item_id=self.item('Improved Blue Pill Booster'),active=True))
    def test_structure_add_rejected(self):
        result=self.edit('create_fit',dict(spec=dict(spec(),ship='Fortizar')))
        self.key=result['fits'][0]['id'];self.assertTrue(self.session.booster_details(self.key)['is_structure'])
        self.rejected('fit_booster',dict(fit_id=self.key,item_id=self.item()))
    def test_write_failure_rolls_back_replacement(self):
        self.fit();before=deepcopy(self.rows())
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic rejection')):
            self.rejected('fit_booster',dict(fit_id=self.key,item_id=self.item('Improved Blue Pill Booster')))
        self.assertEqual(self.rows(),before)
    def test_recent_use_order_and_variation_no_promotion(self):
        self.fit();blue=self.item();self.fit('Standard Frentix Booster');frentix=self.item('Standard Frentix Booster')
        self.assertEqual(self.session.recent_items()['item_ids'][:2],[frentix,blue])
        recent=self.session.recent_items()
        self.edit('change_booster_variation',dict(fit_id=self.key,position=0,item_id=self.item('Improved Blue Pill Booster')))
        self.assertEqual(self.session.recent_items(),recent)
        improved=self.item('Improved Blue Pill Booster')
        self.edit('remove_boosters',dict(fit_id=self.key,positions=[0,1]))
        self.assertEqual(self.session.recent_items()['item_ids'][:2],[frentix,improved])
        self.edit('undo',dict(fit_id=self.key));self.edit('redo',dict(fit_id=self.key))
        self.assertEqual(self.session.recent_items()['item_ids'][:2],[frentix,improved])

    def test_profile_copy_and_linked_publication(self):
        self.fit();effect=self.rows()[0]['side_effects'][0]['effect_id']
        self.edit('set_booster_side_effect',dict(fit_id=self.key,position=0,effect_id=effect,active=True))
        expected=deepcopy(self.session._records[self.key]['boosters'])
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        self.assertEqual(expected,self.session._records[self.key]['boosters'])
        previous=set(self.session._fits);self.edit('duplicate_fit',dict(fit_id=self.key,name='Copied boosters'))
        other=next(k for k in self.session._fits if k not in previous)
        self.assertEqual(expected,self.session._records[other]['boosters'])
        self.assertNotEqual(self.rows()[0]['object_key'],self.session.booster_details(other)['boosters'][0]['object_key'])
        identities=deepcopy(self.session._records[self.key]['inspection_ids'])
        self.edit('add_projection',dict(source_id=self.key,target_id=other,range_m=0.0,active=True,amount=1))
        self.assertEqual(self.session._records[self.key]['inspection_ids'],identities)
        self.edit('add_command',dict(source_id=self.key,target_id=other,active=True))
        self.assertEqual(self.session._records[self.key]['inspection_ids'],identities)
        rev=self.session._revisions[other]
        self.fit('Improved Blue Pill Booster');self.assertGreater(self.session._revisions[other],rev)
        identities=deepcopy(self.session._records[self.key]['inspection_ids'])
        for operation in ('remove_projection','remove_command'):
            self.edit(operation,dict(source_id=self.key,target_id=other))
            self.assertEqual(self.session._records[self.key]['inspection_ids'],identities)

    def test_stale_confirmed_occupant_rejected(self):
        self.fit();request=self.request('fit_booster',dict(fit_id=self.key,item_id=self.item('Improved Blue Pill Booster')))
        self.edit('set_booster_active',dict(fit_id=self.key,position=0,active=False));before=self.path.read_bytes()
        result=json.loads(self.session.dispatch(json.dumps(request)));self.assertEqual(result['status'],'error');self.assertEqual(before,self.path.read_bytes())

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(BoosterEditorTests(name) for name in BoosterEditorTests.__dict__ if name.startswith('test_'))
