"""Reactive armor selection durability and loss boundaries."""
import json
from unittest.mock import patch
import unittest
from test_native_session import NativeSessionTests,spec
from android_bridge.offline.profile_store import StoreWriteRejected

class ModuleRahTests(NativeSessionTests):
    def setUp(self):
        super().setUp()
        r=self.edit('create_fit',dict(spec=dict(spec(),ship='Vexor',modules=[dict(name='Reactive Armor Hardener',state='ACTIVE')])))
        self.key=r['fits'][0]['id']
    def details(self):return self.session.module_rah_details(self.key)
    def row(self):return self.details()['module_page']['entries'][0]
    def select(self,mode,**extra):return self.edit('set_module_rah',dict(fit_id=self.key,position=self.row()['index'],mode=mode,**extra))
    def reject(self,args):
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history_details(self.key)
        result=json.loads(self.session.dispatch(json.dumps(self.request('set_module_rah',args))))
        self.assertEqual(result['status'],'error',result);self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph.snapshot());self.assertEqual(history,self.session.history_details(self.key))
    def test_modes_history_and_restart(self):
        original=self.row();self.assertEqual(original['mode'],'fit')
        for mode,extra in [('disabled',{}),('builtin',{'pattern_id':-1}),('builtin',{'pattern_id':-2}),('fit',{})]:
            self.select(mode,**extra);self.assertEqual(self.row()['mode'],mode);self.assertEqual(self.row()['object_key'],original['object_key'])
            self.reopen();self.assertEqual(self.row()['mode'],mode)
        self.select('builtin',pattern_id=-2);self.select('fit')
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.row()['builtin_id'],-2)
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.row()['mode'],'fit')
    def test_source_order_components_readonly(self):
        from eos.saveddata.damagePattern import DamagePattern
        self.select('builtin',pattern_id=-1)
        before=self.path.read_bytes();d=self.details()
        self.assertEqual(d['module_page']['entries'][0]['components'],dict(em=25,thermal=25,kinetic=25,explosive=25))
        ids=[]
        for offset in (0,50,100):
            request=dict(version=3,request_id='rah-options',context=self.session.context(),fit_id=self.key,
                view=dict(query='',offset=offset,limit=50,selected_pattern_id=None,bound_offset=0,module_offset=0),
                operation='read',arguments={})
            value=json.loads(self.session.damage_dispatch(json.dumps(request)))
            self.assertTrue(value['ok'],value)
            ids.extend(row['pattern_id'] for row in value['state']['page']['entries'])
        self.assertEqual(ids,['damage:builtin:'+str(p.ID) for p in DamagePattern.getBuiltinList()])
        self.assertEqual(self.path.read_bytes(),before)
    def test_invalid_and_failed_commit_are_atomic(self):
        base=dict(fit_id=self.key,position=self.row()['index'])
        for x in [dict(mode='fit',pattern_id=-1),dict(mode='disabled',pattern_id=None),dict(mode='builtin'),dict(mode='builtin',pattern_id=True),dict(mode='builtin',pattern_id=999),dict(mode='custom')]:self.reject(dict(base,**x))
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic')):self.reject(dict(base,mode='disabled'))
    def test_link_profile_copy_preserve_override(self):
        self.select('builtin',pattern_id=-2)
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'));self.assertEqual(self.row()['builtin_id'],-2)
        other=next(k for k in self.session._fits if k!=self.key)
        self.edit('add_projection',dict(source_id=self.key,target_id=other,range_m=0.0,active=True,amount=1));self.assertEqual(self.row()['builtin_id'],-2)
        self.edit('remove_projection',dict(source_id=self.key,target_id=other));self.assertEqual(self.row()['builtin_id'],-2)
        self.edit('set_fit_restrictions',dict(fit_id=self.key,ignore=True))
        self.edit('clone_selected_modules',dict(fit_id=self.key,module_indices=[self.row()['index']]))
        self.assertTrue(all(r['builtin_id']==-2 for r in self.details()['module_page']['entries']));self.reopen()
        self.assertTrue(all(r['builtin_id']==-2 for r in self.details()['module_page']['entries']))
    def test_custom_is_explicitly_unavailable(self):
        from eos.saveddata.damagePattern import DamagePattern
        from android_bridge.module_rah import CUSTOM_ERROR,capture
        module=self.session._fits[self.key].modules[self.row()['index']];module.rahPatternOverride=DamagePattern()
        with self.assertRaisesRegex(ValueError,CUSTOM_ERROR):self.details()
        with self.assertRaisesRegex(ValueError,CUSTOM_ERROR):capture(module)
        module.rahPatternOverride=None
    def test_eft_loss_is_reported(self):
        self.select('disabled');request=dict(version=1,request_id='rah-export',context=self.session.context(),fit_id=self.key,revision=self.session._revisions[self.key],options=dict.fromkeys(('loaded_charges','cargo','implants','boosters','mutations'),True))
        result=json.loads(self.session.export_preview(json.dumps(request)));self.assertTrue(result['ok'],result)
        self.assertIn('module_rah_loss',{r['code'] for r in result['diagnostics']})

    def test_stale_request_and_remove_undo(self):
        request=self.request('set_module_rah',dict(fit_id=self.key,position=self.row()['index'],mode='disabled'))
        self.edit('rename_fit',dict(fit_id=self.key,name='Changed'))
        before=self.path.read_bytes()
        self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error')
        self.assertEqual(before,self.path.read_bytes())
        self.select('builtin',pattern_id=-1)
        self.edit('remove_module',dict(fit_id=self.key,position=self.row()['index']))
        self.assertEqual(self.details()['module_page']['entries'],[])
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.row()['builtin_id'],-1)
        self.reopen();self.assertEqual(self.row()['builtin_id'],-1)

    def test_invalid_saved_tag_and_wrong_module_are_rejected(self):
        for record in (None,{}, {'mode':'fit'},{'mode':'builtin','pattern_id':True}, {'mode':'disabled','pattern_id':-1}, {'mode':'builtin','pattern_id':999}):
            before=self.path.read_bytes()
            request=self.request('create_fit',dict(spec=dict(spec(),modules=[dict(name='Reactive Armor Hardener',state='ACTIVE',rah_pattern=record)])))
            self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error')
            self.assertEqual(before,self.path.read_bytes())
        before=self.path.read_bytes()
        request=self.request('create_fit',dict(spec=dict(spec(),modules=[dict(name='Small Armor Repairer I',state='ACTIVE',rah_pattern={'mode':'disabled'})])))
        self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error')
        self.assertEqual(before,self.path.read_bytes())

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(ModuleRahTests(name) for name in ModuleRahTests.__dict__ if name.startswith('test_'))
