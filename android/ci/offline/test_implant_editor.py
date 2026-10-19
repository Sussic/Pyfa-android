"""C07.1 integrated fit-local implant editor persistence contracts."""
import json
import unittest
from unittest.mock import patch
from test_native_session import NativeSessionTests,spec
from android_bridge.offline.profile_store import StoreWriteRejected

NAV1="Eifyr and Co. 'Rogue' Navigation NN-601"
NAV5="Eifyr and Co. 'Rogue' Navigation NN-605"
MIND='Shield Command Mindlink'

class ImplantEditorTests(NativeSessionTests):
    def rows(self):return self.session.implant_details(self.key)['implants']
    def fit(self,name):return self.edit('fit_implant',dict(fit_id=self.key,item_id=self.engine._item(name).ID))
    def reject(self,operation,args):
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history_details(self.key)
        result=json.loads(self.session.dispatch(json.dumps(self.request(operation,args))))
        self.assertEqual(result['status'],'error',result);self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph.snapshot());self.assertEqual(history,self.session.history_details(self.key))
    def test_metadata_query_empty_and_booster_distinction(self):
        self.assertEqual(self.rows(),[]);before=self.path.read_bytes()
        for name in ('Standard Blue Pill Booster','Small Armor Repairer I'):
            data=self.session.implant_add_options(self.key,self.engine._item(name).ID)
            self.assertFalse(data['is_implant']);self.assertIsNone(data['slot']);self.assertIsNone(data['occupant']);self.assertFalse(data['already_fitted'])
        self.assertEqual(before,self.path.read_bytes())
    def test_slot_replacement_default_activation_and_history(self):
        self.fit(NAV1);first=self.rows()[0];self.assertTrue(first['active'])
        self.edit('toggle_implants',dict(fit_id=self.key,main_position=0,positions=[]));self.assertFalse(self.rows()[0]['active'])
        options=self.session.implant_add_options(self.key,self.engine._item(NAV5).ID)
        self.assertEqual(options['occupant']['object_key'],first['object_key'])
        self.fit(NAV5);self.assertEqual(len(self.rows()),1);self.assertTrue(self.rows()[0]['active']);self.assertEqual(self.rows()[0]['name'],NAV5)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows()[0]['name'],NAV1);self.assertFalse(self.rows()[0]['active'])
        self.edit('redo',dict(fit_id=self.key));self.reopen();self.assertEqual(self.rows()[0]['name'],NAV5)
    def test_selected_activation_removal_and_recent_use(self):
        self.fit(MIND);self.fit(NAV1);self.assertEqual([r['slot'] for r in self.rows()],[10,6])
        self.edit('toggle_implants',dict(fit_id=self.key,main_position=1,positions=[0]))
        self.assertTrue(all(not r['active'] for r in self.rows()))
        self.edit('toggle_implants',dict(fit_id=self.key,main_position=0,positions=[1]));self.assertTrue(all(r['active'] for r in self.rows()))
        self.edit('remove_implants',dict(fit_id=self.key,positions=[0,1]));self.assertEqual(self.rows(),[])
        self.edit('undo',dict(fit_id=self.key));self.assertEqual([r['name'] for r in self.rows()],[MIND,NAV1]);self.reopen();self.assertEqual(len(self.rows()),2)
    def test_invalid_duplicate_stale_and_rollback(self):
        self.fit(NAV1)
        self.reject('fit_implant',dict(fit_id=self.key,item_id=self.engine._item(NAV1).ID))
        self.reject('fit_implant',dict(fit_id=self.key,item_id=self.engine._item('Standard Blue Pill Booster').ID))
        for values in ([],[0,0],[-1],[True],[99]):self.reject('remove_implants',dict(fit_id=self.key,positions=values))
        request=self.request('fit_implant',dict(fit_id=self.key,item_id=self.engine._item(NAV5).ID));self.edit('rename_fit',dict(fit_id=self.key,name='Changed'))
        before=self.path.read_bytes();self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error');self.assertEqual(before,self.path.read_bytes())
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic')):self.reject('fit_implant',dict(fit_id=self.key,item_id=self.engine._item(NAV5).ID))
    def test_variation_retains_active_and_profile_link_restart(self):
        self.fit(NAV1);self.edit('toggle_implants',dict(fit_id=self.key,main_position=0,positions=[]))
        self.edit('change_variation',dict(fit_id=self.key,context='implant',position=0,item_id=self.engine._item(NAV5).ID));self.assertFalse(self.rows()[0]['active'])
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'));self.assertFalse(self.rows()[0]['active'])
        other=self.edit('create_fit',dict(spec=spec()))['fits'][0]['id'];saved=self.rows()
        self.edit('add_projection',dict(source_id=self.key,target_id=other,range_m=0.0,active=True,amount=1));self.assertEqual(self.rows(),saved)
        self.edit('remove_projection',dict(source_id=self.key,target_id=other));self.assertEqual(self.rows(),saved)
        self.reopen();self.assertEqual(self.rows(),saved)
    def test_structure_and_character_source_guard(self):
        from android_bridge import implant_editor,variations
        from eos.const import ImplantLocation
        self.fit(NAV1);fit=self.session._fits[self.key]
        fit.implantLocation=ImplantLocation.CHARACTER
        for operation,args in [('toggle_implants',{'main_position':0,'positions':[]}),('remove_implants',{'positions':[0]})]:
            with self.assertRaises(ValueError):implant_editor.change(self.engine,fit,operation,args)
        self.assertTrue(all(not v['enabled'] for v in variations.choices(self.engine,fit,fit.implants[0].item,'implant')))
        with self.assertRaises(ValueError):variations.change(self.engine,fit,'implant',0,self.engine._item(NAV5).ID)
        fit.implantLocation=ImplantLocation.FIT
        self.key=self.edit('create_fit',dict(spec=dict(spec(),ship='Fortizar')))['fits'][0]['id']
        self.reject('fit_implant',dict(fit_id=self.key,item_id=self.engine._item(NAV1).ID))

    def test_recent_use_and_variation_no_promotion(self):
        self.fit(NAV1);self.fit(MIND)
        nav1=self.engine._item(NAV1).ID;nav5=self.engine._item(NAV5).ID;mind=self.engine._item(MIND).ID
        self.assertEqual(self.session.recent_items()['item_ids'][:2],[mind,nav1])
        recent=self.session.recent_items()
        self.edit('change_variation',dict(fit_id=self.key,context='implant',position=0,item_id=nav5))
        self.assertEqual(self.session.recent_items(),recent)
        # The original variation removes/appends, leaving Mindlink first.
        self.assertEqual([r['name'] for r in self.rows()],[MIND,NAV5])
        self.edit('remove_implants',dict(fit_id=self.key,positions=[0,1]))
        self.assertEqual(self.session.recent_items()['item_ids'][:2],[mind,nav5])
        self.edit('undo',dict(fit_id=self.key));self.edit('redo',dict(fit_id=self.key))
        self.assertEqual(self.session.recent_items()['item_ids'][:2],[mind,nav5])

    def test_pinned_slot79_implant_is_not_hidden_by_a_conventional_cap(self):
        self.fit("Genolution 'Auroral' AU-79")
        row=self.rows()[0];self.assertEqual(row['slot'],79)
        self.reopen();self.assertEqual(self.rows()[0],row)

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(ImplantEditorTests(name) for name in ImplantEditorTests.__dict__ if name.startswith('test_'))
