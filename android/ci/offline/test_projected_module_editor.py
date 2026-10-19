"""Individual projected modules through atomic saved graph/history."""
import json
from copy import deepcopy
import unittest
from unittest.mock import patch
from test_native_session import NativeSessionTests,spec
from android_bridge.offline.profile_store import StoreWriteRejected

class ProjectedModuleTests(NativeSessionTests):
    def item(self,name):return self.engine._item(name).ID
    def rows(self):return self.session.projected_module_details(self.key)['modules']
    def add(self,name):return self.edit('add_projected_module',dict(fit_id=self.key,item_id=self.item(name)))
    def change(self,op,index=0,**values):
        row=self.rows()[index]
        return self.edit(op,dict(fit_id=self.key,position=row['index'],object_key=row['object_key'],**values))
    def reject(self,op,args):
        before=(self.path.read_bytes(),deepcopy(self.session._records))
        result=json.loads(self.session.dispatch(json.dumps(self.request(op,args))))
        self.assertEqual(result['status'],'error',result)
        self.assertEqual((self.path.read_bytes(),self.session._records),before)
    def test_sensor_identity_range_charge_variation_history_restart(self):
        original=deepcopy(self.session._records)
        self.assertNotIn('projected_modules',original[self.key]['spec'])
        self.add('Remote Sensor Booster II')
        row=self.rows()[0];self.assertEqual(row['state'],'ACTIVE');self.assertTrue(row['editable'])
        choices=self.session.projected_module_options(self.key,0)
        self.assertTrue(choices['charges']);self.assertTrue(choices['variations'])
        self.change('set_projected_module_charge',charge_id=self.item('Scan Resolution Script'))
        self.change('set_projected_module_range',range_m=0)
        before=deepcopy(self.session._records)
        self.change('set_projected_module_range',range_m=1000000)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
        self.change('set_projected_module_state',state='inactive');self.assertEqual(self.rows()[0]['state'],'OFFLINE')
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
        variation=next(r['id'] for r in choices['variations'] if r['enabled'] and r['id']!=row['item_id'])
        self.change('change_projected_module_variation',item_id=variation)
        self.assertIsNone(self.rows()[0]['range_m']);self.assertNotEqual(self.rows()[0]['object_key'],row['object_key'])
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
        self.add('Remote Sensor Booster II');self.assertEqual(len({r['object_key'] for r in self.rows()}),2)
        before=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,before)
        self.change('remove_projected_module');self.assertEqual(len(self.rows()),1)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
    def test_scram_and_rejected_inputs_and_failed_commit(self):
        self.edit('add_module',dict(fit_id=self.key,item_id=self.item('5MN Microwarpdrive II')))
        position=next(i for i,m in enumerate(self.session._fits[self.key].modules) if not m.isEmpty and m.item.name=='5MN Microwarpdrive II')
        self.edit('set_module_states',dict(fit_id=self.key,module_indices=[position],state='ACTIVE'))
        before=deepcopy(self.session._records)
        self.add('Warp Scrambler II')
        self.assertEqual(self.session._records[self.key]['spec']['modules'][position]['state'],'ONLINE')
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
        self.add('Remote Sensor Booster II');row=self.rows()[0]
        args=dict(fit_id=self.key,position=0,object_key=row['object_key'])
        for bad in (-1,True,'0'):
            self.reject('set_projected_module_range',dict(args,range_m=bad))
        self.reject('set_projected_module_charge',dict(args,charge_id=self.item('Antimatter Charge S')))
        self.reject('remove_projected_module',dict(args,object_key='0'*32))
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic')):
            self.reject('set_projected_module_range',dict(args,range_m=1000))
        self.assertEqual(self.rows()[0]['object_key'],row['object_key'])
    def test_legacy_environment_and_empty_optional_presence(self):
        value=spec();value['environments']=[dict(name='Class 1 Red Giant Effects',state='ONLINE')]
        result=self.edit('create_fit',dict(spec=value));self.key=result['fits'][0]['id']
        legacy=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,legacy)
        self.add('Remote Sensor Booster II');self.assertFalse(self.rows()[0]['editable']);self.assertTrue(self.rows()[1]['editable'])
        self.assertEqual(len(self.session._records[self.key]['inspection_ids']['projected_modules']),2)
        self.change('remove_projected_module',index=1)
        self.assertEqual(self.session._records[self.key]['spec']['projected_modules'],[])
        saved=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,saved)
        self.assertEqual(len(self.rows()),1)

    def test_spool_raw_override_copy_profile_refresh_and_export_loss(self):
        value=spec();value['projected_modules']=[dict(name='Heavy Mutadaptive Remote Armor Repairer II',
            state='ACTIVE',charge=None,range_m=0,spool_cycles=999)]
        self.key=self.edit('create_fit',dict(spec=value))['fits'][0]['id']
        row=self.session.projected_module_options(self.key,0)['spool']
        self.assertEqual(row['override_cycles'],999);self.assertLess(row['current_cycles'],999)
        self.change('set_projected_module_spool',cycles=0)
        self.assertEqual(self.session.projected_module_options(self.key,0)['spool']['current_cycles'],0)
        self.change('set_projected_module_spool',cycles=row['maximum_cycles'])
        self.change('set_projected_module_spool',cycles=None)
        self.assertIsNone(self.session.projected_module_options(self.key,0)['spool']['override_cycles'])
        self.edit('undo',dict(fit_id=self.key))
        ids=deepcopy(self.session._records[self.key]['inspection_ids'])
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        self.assertEqual(self.session._records[self.key]['inspection_ids'],ids)
        old=set(self.session._fits);self.edit('duplicate_fit',dict(fit_id=self.key,name='Copied projectors'))
        other=next(k for k in self.session._fits if k not in old)
        self.assertEqual(self.session._records[self.key]['spec']['projected_modules'],self.session._records[other]['spec']['projected_modules'])
        self.assertNotEqual(self.session._records[other]['inspection_ids']['projected_modules'],ids['projected_modules'])
        for op,args in [('add_projection',dict(source_id=self.key,target_id=other,range_m=0,active=True,amount=1)),
                        ('remove_projection',dict(source_id=self.key,target_id=other)),
                        ('add_command',dict(source_id=self.key,target_id=other,active=True)),
                        ('remove_command',dict(source_id=self.key,target_id=other)),
                        ('add_command_fit',dict(source_id=self.key,target_id=other))]:
            self.edit(op,args);self.assertEqual(self.session._records[self.key]['inspection_ids'],ids)
        request=dict(version=1,request_id='projector-export',context=self.session.context(),fit_id=self.key,
                     revision=self.session._revisions[self.key],options=dict.fromkeys(('loaded_charges','cargo','implants','boosters','mutations'),True))
        exported=json.loads(self.session.export_preview(json.dumps(request)));self.assertTrue(exported['ok'],exported)
        self.assertIn('projected_modules_lost',{r['code'] for r in exported['diagnostics']})
        before=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,before)

    def test_strict_projector_spec_and_equipment_refusals(self):
        self.assertFalse(self.session.projected_module_add_options(self.key,self.item('Antimatter Charge S'))['enabled'])
        self.reject('add_projected_module',dict(fit_id=self.key,item_id=self.item('Damage Control II')))
        base=dict(name='Remote Sensor Booster II',state='ACTIVE',charge=None,range_m=None)
        for bad in (dict(base,rah_pattern=None),dict(base,range_m=-1),dict(base,spool_cycles=0),dict(base,name='Damage Control II')):
            self.reject('create_fit',dict(spec=dict(spec(),projected_modules=[bad])))
        self.reject('create_fit',dict(spec=dict(spec(),ship='Fortizar',projected_modules=[base])))
        self.add('Remote Sensor Booster II');row=self.rows()[0]
        for bad in (None,True,'', 'z'*32):
            self.reject('remove_projected_module',dict(fit_id=self.key,position=0,object_key=bad))
        stale=self.request('remove_projected_module',dict(fit_id=self.key,position=0,object_key=row['object_key']))
        self.edit('rename_fit',dict(fit_id=self.key,name='Updated'))
        before=self.path.read_bytes();result=json.loads(self.session.dispatch(json.dumps(stale)))
        self.assertEqual(result['status'],'error');self.assertEqual(self.path.read_bytes(),before)

    def test_range_json_types_survive_all_refresh_boundaries_and_replay(self):
        self.add('Remote Sensor Booster II')
        row=self.rows()[0]
        args=dict(fit_id=self.key,position=0,object_key=row['object_key'])
        for invalid in (9007199254740993,10**400):
            self.reject('set_projected_module_range',dict(args,range_m=invalid))
        other=self.edit('create_fit',dict(spec=dict(spec(),name='Range recipient')))['fits'][0]['id']
        for value in (0,-0.0,111,63.7,5e-324,9007199254740992):
            self.change('set_projected_module_range',range_m=value)
            saved=self.session._records[self.key]['spec']['projected_modules'][0]['range_m']
            self.assertIs(type(saved),float);self.assertEqual(saved,float(value))
            expected=json.dumps(self.session._records[self.key],sort_keys=True)
            for op,args in [('add_projection',dict(source_id=self.key,target_id=other,range_m=0,active=True,amount=1)),
                            ('remove_projection',dict(source_id=self.key,target_id=other)),
                            ('add_command',dict(source_id=self.key,target_id=other,active=True)),
                            ('remove_command',dict(source_id=self.key,target_id=other)),
                            ('add_command_fit',dict(source_id=self.key,target_id=other)),
                            ('remove_command_fit',dict(source_id=self.key,target_id=other))]:
                self.edit(op,args)
                self.assertEqual(json.dumps(self.session._records[self.key],sort_keys=True),expected)
            self.reopen();self.assertEqual(json.dumps(self.session._records[self.key],sort_keys=True),expected)

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(ProjectedModuleTests(name) for name in ProjectedModuleTests.__dict__ if name.startswith('test_'))
