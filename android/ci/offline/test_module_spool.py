"""C09.1 cycle override durability through the integrated native facade."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_native_session import NativeSessionTests,spec
from android_bridge.offline.profile_store import StoreWriteRejected

class ModuleSpoolTests(NativeSessionTests):
    def setUp(self):
        super().setUp()
        result=self.edit('create_fit',dict(spec=dict(spec(),ship='Vedmak',modules=[dict(name='Heavy Entropic Disintegrator II',state='ACTIVE',charge='Occult M')])))
        self.key=result['fits'][0]['id']
    def rows(self):return self.session.module_spool_details(self.key)['modules']
    def set_cycles(self,value):
        return self.edit('set_module_spool',dict(fit_id=self.key,position=self.rows()[0]['index'],cycles=value))
    def rejected(self,op,args):
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history_details(self.key)
        result=json.loads(self.session.dispatch(json.dumps(self.request(op,args))))
        self.assertEqual(result['status'],'error',result);self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph.snapshot());self.assertEqual(history,self.session.history_details(self.key))
    def test_readonly_details_empty_fit_and_choices(self):
        before=self.path.read_bytes();row=self.rows()[0]
        self.assertIsNone(row['override_cycles']);self.assertGreater(row['maximum_cycles'],0)
        self.assertEqual(row['choices'],sorted(set(row['choices'])));self.assertIn(row['current_cycles'],row['choices'])
        self.assertEqual(before,self.path.read_bytes())
        other=next(k for k in self.session._fits if k!=self.key)
        self.assertEqual(self.session.module_spool_details(other)['modules'],[])
    def test_explicit_zero_reset_history_and_restart(self):
        original=self.rows()[0];self.set_cycles(0);zero=self.rows()[0]
        self.assertEqual(zero['override_cycles'],0);self.assertEqual(zero['current_cycles'],0);self.assertEqual(zero['object_key'],original['object_key'])
        self.reopen();self.assertEqual(self.rows()[0]['override_cycles'],0)
        self.set_cycles(None);self.assertIsNone(self.rows()[0]['override_cycles']);self.assertEqual(self.rows()[0]['current_cycles'],self.rows()[0]['default_cycles'])
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows()[0]['override_cycles'],0)
        self.edit('redo',dict(fit_id=self.key));self.assertIsNone(self.rows()[0]['override_cycles'])
        self.reopen();self.assertIsNone(self.rows()[0]['override_cycles'])
        self.assertTrue(all('spool_cycles' not in row for row in self.session._records[self.key]['spec']['modules']))
    def test_weapon_damage_and_repair_spool_update(self):
        self.set_cycles(0);base=self.engine.snapshot(self.session._fits[self.key]);self.set_cycles(self.rows()[0]['maximum_cycles'])
        full=self.engine.snapshot(self.session._fits[self.key]);self.assertGreater(full['weapon_dps']['value'],base['weapon_dps']['value'])
        result=self.edit('create_fit',dict(spec=dict(spec(),ship='Rodiva',modules=[dict(name='Heavy Mutadaptive Remote Armor Repairer II',state='ACTIVE')])))
        self.key=result['fits'][0]['id'];row=self.rows()[0];self.assertGreater(row['maximum_cycles'],0)
        self.set_cycles(0);self.assertEqual(self.rows()[0]['current_seconds'],0)
        self.set_cycles(self.rows()[0]['maximum_cycles']);self.assertGreater(self.rows()[0]['current_seconds'],0)
    def test_invalid_input_stale_and_rollback(self):
        row=self.rows()[0]
        for value in (-1,True,1.5,2**31,{},'0'):
            self.rejected('set_module_spool',dict(fit_id=self.key,position=row['index'],cycles=value))
        invalid=next(i for i in range(row['maximum_cycles']+2) if i not in row['choices'])
        self.rejected('set_module_spool',dict(fit_id=self.key,position=row['index'],cycles=invalid))
        request=self.request('set_module_spool',dict(fit_id=self.key,position=row['index'],cycles=0));self.edit('rename_fit',dict(fit_id=self.key,name='Changed'))
        before=self.path.read_bytes();self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error');self.assertEqual(before,self.path.read_bytes())
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic rejection')):
            self.rejected('set_module_spool',dict(fit_id=self.key,position=self.rows()[0]['index'],cycles=0))
    def test_variation_copy_profile_and_linked_publication(self):
        self.set_cycles(0);row=self.rows()[0]
        self.edit('change_variation',dict(fit_id=self.key,context='module',position=row['index'],item_id=self.engine._item('Heavy Entropic Disintegrator I').ID))
        self.assertEqual(self.rows()[0]['override_cycles'],0)
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'));self.assertEqual(self.rows()[0]['override_cycles'],0)
        old=set(self.session._fits);self.edit('duplicate_fit',dict(fit_id=self.key,name='Copied spool'));other=next(k for k in self.session._fits if k not in old)
        self.assertEqual(self.session.module_spool_details(other)['modules'][0]['override_cycles'],0)
        self.edit('add_projection',dict(source_id=self.key,target_id=other,range_m=0.0,active=True,amount=1));revision=self.session._revisions[other]
        self.set_cycles(None);self.assertGreater(self.session._revisions[other],revision)
        self.reopen();self.assertIsNone(self.rows()[0]['override_cycles']);self.assertEqual(self.session.module_spool_details(other)['modules'][0]['override_cycles'],0)
    def test_saved_override_keeps_requested_value_not_effective_clamp(self):
        result=self.edit('create_fit',dict(spec=dict(spec(),ship='Vedmak',modules=[dict(name='Heavy Entropic Disintegrator II',state='ACTIVE',charge='Occult M',spool_cycles=999)])))
        self.key=result['fits'][0]['id'];row=self.rows()[0]
        self.assertEqual(row['override_cycles'],999);self.assertLess(row['current_cycles'],999)
        self.edit('rename_fit',dict(fit_id=self.key,name='Unchanged request'));self.reopen();self.assertEqual(self.rows()[0]['override_cycles'],999)
    def test_eft_reports_zero_override_loss(self):
        self.set_cycles(0)
        request=dict(version=1,request_id='spool-export',context=self.session.context(),fit_id=self.key,revision=self.session._revisions[self.key],options=dict.fromkeys(('loaded_charges','cargo','implants','boosters','mutations'),True))
        result=json.loads(self.session.export_preview(json.dumps(request)));self.assertTrue(result['ok'],result)
        self.assertIn('module_spool_loss',{row['code'] for row in result['diagnostics']})
    def test_clone_keeps_explicit_cycle_override(self):
        self.edit('set_fit_restrictions',dict(fit_id=self.key,ignore=True))
        self.set_cycles(0)
        self.edit('clone_selected_modules',dict(fit_id=self.key,module_indices=[self.rows()[0]['index']]))
        self.assertGreaterEqual(len(self.rows()),2)
        self.assertTrue(all(row['override_cycles']==0 for row in self.rows()))
        self.reopen();self.assertTrue(all(row['override_cycles']==0 for row in self.rows()))

    def test_degenerate_source_range_fails_readonly(self):
        module=self.session._fits[self.key].modules[self.rows()[0]['index']]
        before=self.path.read_bytes()
        with patch.object(module,'getSpoolData',return_value=(0,0)):
            with self.assertRaises(ValueError):self.session.module_spool_details(self.key)
        self.assertEqual(before,self.path.read_bytes())

    def test_noncycle_and_fractional_live_state_are_not_silently_saved(self):
        from android_bridge.module_spool import capture
        from eos.const import SpoolType
        module=self.session._fits[self.key].modules[self.rows()[0]['index']]
        module.spoolType=SpoolType.TIME;module.spoolAmount=1
        with self.assertRaises(ValueError):capture(module)
        module.spoolType=SpoolType.CYCLES;module.spoolAmount=.5
        with self.assertRaises(ValueError):capture(module)
        module.spoolType=None;module.spoolAmount=None

    def test_saved_invalid_override_rejected(self):
        for value in (-1,True,1.5,None):
            self.rejected('create_fit',dict(spec=dict(spec(),ship='Vedmak',modules=[dict(name='Heavy Entropic Disintegrator II',state='ACTIVE',spool_cycles=value)])))
        self.rejected('create_fit',dict(spec=dict(spec(),modules=[dict(name='Small Armor Repairer I',state='ACTIVE',spool_cycles=0)])))

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(ModuleSpoolTests(name) for name in ModuleSpoolTests.__dict__ if name.startswith('test_'))
