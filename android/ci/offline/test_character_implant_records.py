"""Pure C07.2 record/model tests. No EOS calculations or Android claims."""
from copy import deepcopy
from types import SimpleNamespace, ModuleType
import unittest
import sys
from unittest.mock import patch

from android_bridge import character_implants as implants
from android_bridge.offline.profiles import Profiles, ProfileError, BUILTINS, ALL_FIVE
from android_bridge.offline.profile_graph import MemoryStore
from android_bridge.offline.graph_history import GraphHistory, inputs


class CharacterImplantRecordTests(unittest.TestCase):
    def setUp(self):
        self.meta=patch.object(implants,'catalogue',side_effect=lambda item:(SimpleNamespace(ID=item,name='Implant '+str(item)),79 if item==79 else 6))
        self.meta.start();self.addCleanup(self.meta.stop)
        self.model=Profiles('memory','a'*64,[1,2],store_type=lambda _:MemoryStore())
        self.pid=self.model.create('Pilot',source=ALL_FIVE)['profile_id']
    def profile(self,pid=None):return self.model.snapshot()['profiles'][pid or self.pid]
    def add(self,item=1,replace=None):
        return self.model.add_implant(self.pid,self.profile()['revision'],item,replace)
    def test_replace_same_item_appends_fresh_active_identity_and_slot79(self):
        self.add();first=self.profile()['implants'][0]
        self.add(79);self.add(1,first['implant_id'])
        rows=self.profile()['implants'];self.assertEqual([r['slot'] for r in rows],[79,6])
        self.assertNotEqual(rows[1]['implant_id'],first['implant_id']);self.assertTrue(rows[1]['active'])
        self.model.remove_implant(self.pid,self.profile()['revision'],rows[0]['implant_id'])
        self.assertEqual(self.profile()['implants'],[rows[1]])
    def test_complete_create_copy_and_save_as_remap_without_aliases(self):
        self.add();draft=self.model.begin(self.pid);draft.values['implants'][0]['active']=False
        draft.values['levels']['1']=0;self.model.save(draft)
        original=self.profile();new=self.model.create('Copy',source=self.pid)['profile_id']
        copy=self.profile(new);self.assertEqual(copy['levels'],original['levels'])
        self.assertFalse(copy['implants'][0]['active']);self.assertNotEqual(copy['implants'][0]['implant_id'],original['implants'][0]['implant_id'])
        saved=self.model.save(self.model.begin(self.pid),save_as='Save as')['profile_id']
        self.assertNotEqual(self.profile(saved)['implants'][0]['implant_id'],original['implants'][0]['implant_id'])
        self.model.remove_implant(new,copy['revision'],copy['implants'][0]['implant_id'])
        self.assertEqual(self.profile(),original)
    def test_protected_builtins_and_stale_occupant_leave_ledger_exact(self):
        self.add();before=self.model.snapshot()
        for action in (lambda:self.model.add_implant(ALL_FIVE,0,1,None),lambda:self.model.remove_implant(ALL_FIVE,0,'c'*32),
                       lambda:self.model.delete(ALL_FIVE),lambda:self.model.add_implant(self.pid,self.profile()['revision'],1,None),
                       lambda:self.model.add_implant(self.pid,self.profile()['revision'],1,'d'*32),
                       lambda:self.model.remove_implant(self.pid,True,self.profile()['implants'][0]['implant_id'])):
            with self.assertRaises((ProfileError,ValueError)):action()
            self.assertEqual(self.model.snapshot(),before)
        copied=self.model.create('Builtin copy',source=ALL_FIVE)['profile_id'];self.assertEqual(self.profile(copied)['implants'],[])
    def test_strict_rows_kinds_slots_ids_and_cross_profile_uniqueness(self):
        self.add();valid=self.profile()['implants'];bad=[]
        for key,value in [('implant_id','A'*32),('item_id',True),('item_id',2**31),('slot',False),('active',1),('slot',7)]:
            rows=deepcopy(valid);rows[0][key]=value;bad.append(rows)
        bad.extend([valid+deepcopy(valid),[dict(valid[0],extra=1)]])
        for rows in bad:
            with self.assertRaises(ValueError):implants.validate(rows)
        state=self.model.snapshot();state['profiles']['profile:'+'e'*32]=dict(deepcopy(state['profiles'][self.pid]),name='Other')
        with self.assertRaises(ProfileError):self.model._validate(state)
    def test_format1_readonly_migration_noop_and_first_write_format3(self):
        legacy=self.model.snapshot();legacy['format']=1
        for row in legacy['profiles'].values():row.pop('implants');row.pop('sec_status')
        store=MemoryStore(legacy);before=store.current
        migrated=Profiles('memory','a'*64,[1,2],store_type=lambda _:store)
        self.assertEqual(store.current,before);self.assertEqual(migrated.snapshot()['format'],3)
        draft=migrated.begin(self.pid);migrated.save(draft);self.assertEqual(store.current,before)
        draft=migrated.begin(self.pid);draft.values['name']='Changed';migrated.save(draft)
        self.assertEqual(store.current.generation,before.generation+1);self.assertEqual(migrated.snapshot()['format'],3)
    def test_revision_binding_exhaustion_is_before_commit(self):
        self.model.bind('a'*32,self.pid);state=self.model.snapshot()
        state['bindings']['a'*32]['revision']=2**63-1;self.model._state=deepcopy(state)
        before=self.model.store.current
        with self.assertRaises(ProfileError):self.add()
        self.assertEqual(self.model.snapshot(),state);self.assertEqual(self.model.store.current,before)
    def test_history_owns_authority_not_projection_and_keeps_source_local_ids(self):
        ledger=self.model.snapshot();record=dict(spec=dict(skill_level=5),skills={},implants=[],inspection_ids={'implants':[]},implant_source='FIT',character_implants=[])
        old=dict(profiles=ledger,fit_graph=dict(records={'a':record},fit_order=['a']))
        new=deepcopy(old);new['fit_graph']['records']['a']['character_implants']=[{'derived':True}]
        self.assertEqual(inputs(old),inputs(new))
        new['fit_graph']['records']['a']['implant_source']='CHARACTER'
        history=GraphHistory().record(old,new,'Switch',{'a'})
        result,_,_=history.replay('a',False,new);self.assertEqual(result,inputs(old))
    def test_catalogue_complete_order_repeated_slots_no_fit_and_size_error(self):
        eos=ModuleType('eos');db=ModuleType('eos.db');eos.db=db
        values=[SimpleNamespace(ID=79,isImplant=True),SimpleNamespace(ID=2,isImplant=True),SimpleNamespace(ID=1,isImplant=True),SimpleNamespace(ID=9,isImplant=False)]
        db.getItemsByCategory=lambda name:values
        engine=SimpleNamespace(_check_thread=lambda:None,resolved_item_ids={123:'keep'})
        with patch.dict(sys.modules,{'eos':eos,'eos.db':db}):
            result=implants.catalog_response(engine,'a'*64)
            self.assertTrue(result['ok']);self.assertEqual([r['item_id'] for r in result['implants']],[1,2,79])
            self.assertEqual([r['slot'] for r in result['implants']],[6,6,79]);self.assertEqual(engine.resolved_item_ids,{123:'keep'})
            with patch('android_bridge.contract._json',return_value='x'*524289):
                rejected=implants.catalog_response(engine,'a'*64)
            self.assertFalse(rejected['ok']);self.assertEqual(rejected['implants'],[]);self.assertEqual(rejected['error']['code'],'response_size')
        unavailable=implants.catalog_response(None,None)
        self.assertIsNone(unavailable['dataset_sha256']);self.assertFalse(unavailable['ok']);self.assertEqual(set(unavailable),{'version','ok','dataset_sha256','implants','error'})
    def test_mixed_future_and_forged_builtin_ledgers_reject(self):
        for transform in (lambda state:state.update(format=4),
                          lambda state:state.update(format=1),
                          lambda state:state['profiles'][ALL_FIVE].update(implants=[dict(implant_id='f'*32,item_id=1,slot=6,active=True)])):
            state=self.model.snapshot();transform(state)
            with self.assertRaises((ProfileError,ValueError)):self.model._validate(state)

    def test_new_control_names_reject_but_historical_names_survive_migration(self):
        for control in ('\x7f','\x80','\x9f'):
            before=self.model.snapshot()
            with self.assertRaises(ProfileError):self.model.create('New'+control+'pilot')
            draft=self.model.begin(self.pid);draft.values['name']='Changed'+control+'pilot'
            with self.assertRaises(ProfileError):self.model.save(draft)
            self.assertEqual(self.model.snapshot(),before)
        legacy=self.model.snapshot();legacy['format']=1
        for row in legacy['profiles'].values():row.pop('implants');row.pop('sec_status')
        legacy['profiles'][self.pid]['name']='Old\x7f\x80\x9fpilot'
        store=MemoryStore(legacy);before=store.current
        migrated=Profiles('memory','a'*64,[1,2],store_type=lambda _:store)
        self.assertEqual(store.current,before)
        migrated.save(migrated.begin(self.pid));self.assertEqual(store.current,before)
        migrated.add_implant(self.pid,migrated.snapshot()['profiles'][self.pid]['revision'],1,None)
        self.assertEqual(migrated.snapshot()['profiles'][self.pid]['name'],'Old\x7f\x80\x9fpilot')
        draft=migrated.begin(self.pid);draft.values['name']='Safe name';migrated.save(draft)
        self.assertEqual(migrated.snapshot()['profiles'][self.pid]['name'],'Safe name')

    def test_history_sequence_exhaustion_never_wraps(self):
        old=dict(profiles=self.model.snapshot(),fit_graph=dict(records={},fit_order=[]));new=deepcopy(old)
        new['profiles']['profiles'][self.pid]['name']='Changed'
        with self.assertRaises(ProfileError):GraphHistory(sequence=2**63-1).record(old,new,'Rename',{'library'})


if __name__=='__main__':unittest.main()
