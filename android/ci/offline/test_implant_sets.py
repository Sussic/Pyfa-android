"""C07.3 pure recipe/wire/model contracts with explicit metadata doubles.

No EOS calculation, dataset catalogue or Android acceptance is claimed here.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from android_bridge import character_implants
from android_bridge.offline import implant_sets as sets
from android_bridge.offline.graph_history import GraphHistory, inputs
from android_bridge.offline.profile_graph import MemoryStore
from android_bridge.offline.profiles import Profiles, ProfileError

F='a'*32
P='profile:'+'b'*32
CONTEXT=dict(session_id='c'*32,dataset_sha256='d'*64,generation=1)
INFO={1:('One',6),2:('Two',6),3:('Three',7),4:('Four',8),79:('Auroral',79)}
B='builtin:implant-set:1'
CATALOGUE={B:dict(name='Grade-less',family='Grade-less',grade=None,revision=0,item_ids=[79,1,3])}


def fake_item(item_id):
    if type(item_id) is not int or item_id not in INFO:raise character_implants.IneligibleImplant('not an implant')
    name,slot=INFO[item_id]
    return SimpleNamespace(ID=item_id,name=name),slot


def wire(operation='read',args=None,**updates):
    return dict(version=1,request_id='set-test',context=deepcopy(CONTEXT),anchor_fit_id=F,
        view=dict(query='',offset=0,limit=50,selected_set_id=None,target_profile_id=None,history_target='library'),
        operation=operation,arguments={} if args is None else args)|updates


def state():
    model=Profiles('memory','d'*64,[1],store_type=lambda _:MemoryStore())
    pid=model.create('Pilot')['profile_id'];model.bind(F,pid)
    ledger=model.snapshot();ledger['profiles'][P]=ledger['profiles'].pop(pid);ledger['bindings'][F]['profile_id']=P
    record=dict(spec=dict(name='Fit',skill_level=5),skills={},implants=[],inspection_ids=dict(implants=[]),
                implant_source='FIT',character_implants=[],projections=[],commands=[])
    return dict(kind='pyfa.profile-fit-graph',version=7,profiles=ledger,implant_sets=sets.empty(),
                fit_graph=dict(records={F:record},fit_order=[F],revisions={F:1}))


class ImplantSetTests(unittest.TestCase):
    def setUp(self):
        self.stub=patch.object(character_implants,'catalogue',side_effect=fake_item)
        self.stub.start();self.addCleanup(self.stub.stop)
        self.names=patch.object(sets,'item_id_for_name',side_effect=lambda value:next(k for k,v in INFO.items() if v[0]==value))
        self.names.start();self.addCleanup(self.names.stop)
        self.ledger=sets.empty()
    def create(self,name='Mine'):
        return sets.mutate(self.ledger,'create',dict(name=name),CATALOGUE)
    def change(self,key,op,**kwargs):
        return sets.mutate(self.ledger,op,dict(set_id=key,revision=self.ledger['sets'][key]['revision'],**kwargs),CATALOGUE)
    def test_create_empty_trimmed_case_sensitive_names_and_no_reserved_names(self):
        for label in (' All 0 ','All 5','Uniform','Selected Ammo','Grade-less','mine'):
            self.create(label)
        key=self.create();self.assertEqual(self.ledger['sets'][key],dict(name='Mine',revision=1,item_ids=[]))
        self.assertEqual(next(iter(self.ledger['sets'].values()))['name'],'All 0')
        with self.assertRaises(ProfileError):self.create(' Mine ')
        sets.validate(self.ledger)
    def test_name_invalid_unicode_controls_and_length(self):
        self.assertEqual(sets.name('😀'*200),'😀'*200)
        self.assertEqual(sets.name('a\x85'),'a')
        with self.assertRaises(ProfileError):sets.request(wire('create',dict(name='a\x85')),CONTEXT,state())
        for value in ('','  ','a\nname','a\x7f','a\x85name','a\ud800','😀'*201,1,None):
            with self.subTest(value=repr(value)),self.assertRaises(ProfileError):sets.name(value)
    def test_legacy_label_scalar_validation_preserves_controls_and_source_profile(self):
        label='Historic \x7f \x85 profile'
        self.assertEqual(sets.legacy_label(label),label)
        for value in ('',None,123,'Bad \ud800','Bad \udfff'):
            with self.subTest(value=repr(value)),self.assertRaises(ProfileError):sets.legacy_label(value)
        authority=state();authority['profiles']['profiles'][P]['name']=label
        authority['fit_graph']['records'][F]['implant_source']='CHARACTER'
        view=wire()['view']|dict(target_profile_id=P)
        rendered=sets.state_view(authority,CONTEXT,F,view,GraphHistory(),CATALOGUE,lambda _:False)
        self.assertEqual(rendered['destination']['name'],label);self.assertEqual(rendered['save_source']['profile_name'],label)
        authority['profiles']['profiles'][P]['name']='Bad \ud800'
        # The source label is checked even if the requested preview is absent.
        view['target_profile_id']='profile:'+'f'*32
        with self.assertRaises(ProfileError):sets.state_view(authority,CONTEXT,F,view,GraphHistory(),CATALOGUE,lambda _:False)
    def test_rename_identity_and_same_name_noop_at_exhaustion(self):
        key=self.create();row=self.ledger['sets'][key];row['revision']=sets.MAX_INT
        before=deepcopy(self.ledger)
        self.change(key,'rename',name='Mine');self.assertEqual(self.ledger,before)
        with self.assertRaises(ProfileError):self.change(key,'rename',name='Other')
        self.assertEqual(self.ledger,before)
    def test_duplicate_detached_members_and_custom_only(self):
        key=self.create();self.change(key,'add_item',item_id=1,replace_item_id=None)
        copied=self.change(key,'duplicate',name='Copy');self.assertNotEqual(copied,key)
        self.change(copied,'remove_item',item_id=1)
        self.assertEqual(self.ledger['sets'][key]['item_ids'],[1]);self.assertEqual(self.ledger['sets'][copied]['item_ids'],[])
        with self.assertRaises(ProfileError):sets.mutate(self.ledger,'duplicate',dict(set_id=B,revision=0,name='Builtin copy'),CATALOGUE)
    def test_add_replace_remove_exact_occupant_and_order(self):
        key=self.create()
        for item in (1,79,3):self.change(key,'add_item',item_id=item,replace_item_id=None)
        self.change(key,'add_item',item_id=2,replace_item_id=1)
        self.assertEqual(self.ledger['sets'][key]['item_ids'],[79,3,2])
        before=deepcopy(self.ledger)
        with self.assertRaises(ProfileError):self.change(key,'add_item',item_id=1,replace_item_id=None)
        self.assertEqual(self.ledger,before)
        self.change(key,'remove_item',item_id=3);self.assertEqual(self.ledger['sets'][key]['item_ids'],[79,2])
    def test_readd_removes_then_appends_and_same_last_is_noop(self):
        key=self.create()
        for item in (1,79):self.change(key,'add_item',item_id=item,replace_item_id=None)
        self.change(key,'add_item',item_id=1,replace_item_id=1)
        self.assertEqual(self.ledger['sets'][key]['item_ids'],[79,1])
        self.ledger['sets'][key]['revision']=sets.MAX_INT;before=deepcopy(self.ledger)
        self.change(key,'add_item',item_id=1,replace_item_id=1);self.assertEqual(self.ledger,before)
    def test_delete_checks_floor_without_partial_mutation(self):
        key=self.create();before=deepcopy(self.ledger)
        with self.assertRaises(ProfileError):sets.mutate(self.ledger,'delete',dict(set_id=key,revision=1),CATALOGUE,revision_floor={key:sets.MAX_INT})
        self.assertEqual(self.ledger,before);self.change(key,'delete');self.assertNotIn(key,self.ledger['sets'])
    def test_revision_floor_rejects_boolean_float_string_without_coercion(self):
        key=self.create();before=deepcopy(self.ledger)
        for value in (True,1.0,'1',sets.MAX_INT+1):
            for operation,args in [('rename',dict(name='Changed')),('delete',{})]:
                with self.assertRaises(ProfileError):sets.mutate(self.ledger,operation,dict(set_id=key,revision=1,**args),CATALOGUE,revision_floor={key:value})
                self.assertEqual(self.ledger,before)
    def test_save_current_copies_order_and_uniqueness_without_source_alias(self):
        current=[79,1]
        key=sets.mutate(self.ledger,'save_current',dict(name='Saved'),CATALOGUE,current_ids=current)
        current.clear();self.assertEqual(self.ledger['sets'][key]['item_ids'],[79,1])
        for source in ([],[1]):
            before=deepcopy(self.ledger)
            with self.assertRaises(ProfileError):sets.mutate(self.ledger,'save_current',dict(name='Saved'),CATALOGUE,current_ids=source)
            self.assertEqual(self.ledger,before)
    def test_invalid_ledger_fields_kinds_slots_and_predefined_storage(self):
        key=self.create();valid=deepcopy(self.ledger)
        changes=(lambda x:x.update(extra=1),lambda x:x.update(version=True),lambda x:x.update(version=2),
            lambda x:x['sets'][key].update(item_ids=[1,2]),lambda x:x['sets'][key].update(item_ids=[999]),
            lambda x:x['sets'][key].update(item_ids=[True]),lambda x:x['sets'][key].update(item_ids=[1.0]),
            lambda x:x['sets'][key].update(active=True),lambda x:x['sets'][key].update(revision=0),
            lambda x:x['sets'][key].update(revision=True),lambda x:x['sets'][key].update(name=' Mine '),
            lambda x:x['sets'].update({B:x['sets'].pop(key)}))
        for change in changes:
            candidate=deepcopy(valid);change(candidate)
            with self.assertRaises((ProfileError,ValueError)):sets.validate(candidate)
    def test_fit_merge_preserves_inactive_duplicates_ids_source_and_other_families(self):
        record=state()['fit_graph']['records'][F]
        record['implants']=[dict(name='One',slot=6,active=False),dict(name='Four',slot=8,active=True)]
        record['inspection_ids']['implants']=['1'*32,'4'*32];record['implant_source']='CHARACTER'
        before=deepcopy(record)
        sets.merge_fit(record,[1,79,3],lambda value:next(k for k,v in INFO.items() if v[0]==value))
        self.assertEqual(record['implants'][:2],before['implants']);self.assertEqual(record['inspection_ids']['implants'][:2],before['inspection_ids']['implants'])
        self.assertEqual([r['slot'] for r in record['implants']],[6,8,79,7]);self.assertTrue(all(r['active'] for r in record['implants'][2:]))
        for key in record.keys()-{'implants','inspection_ids'}:self.assertEqual(record[key],before[key])
    def test_fit_duplicate_only_empty_and_replace_order(self):
        record=state()['fit_graph']['records'][F]
        record['implants']=[dict(name='One',slot=6,active=False),dict(name='Auroral',slot=79,active=True)]
        record['inspection_ids']['implants']=['1'*32,'f'*32]
        for incoming in ([],[1],[79,1]):
            before=deepcopy(record);sets.merge_fit(record,incoming,sets.item_id_for_name);self.assertEqual(record,before)
        sets.merge_fit(record,[2],sets.item_id_for_name)
        self.assertEqual([r['slot'] for r in record['implants']],[79,6]);self.assertEqual(record['inspection_ids']['implants'][0],'f'*32)
        self.assertNotEqual(record['inspection_ids']['implants'][1],'1'*32);self.assertTrue(record['implants'][1]['active'])
    def test_character_batch_one_save_fresh_ids_repeated_application_and_empty_noop(self):
        model=Profiles('memory','d'*64,[1],store_type=lambda _:MemoryStore());pid=model.create('Pilot')['profile_id']
        model.bind(F,pid)
        revision=lambda:model.snapshot()['profiles'][pid]['revision']
        with patch.object(model,'save',wraps=model.save) as save:model.merge_implants(pid,revision(),[1,79]);self.assertEqual(save.call_count,1)
        first=model.snapshot()['profiles'][pid]['implants'];generation=model.store.current.generation
        model.merge_implants(pid,revision(),[1]);second=model.snapshot()['profiles'][pid]['implants']
        self.assertEqual(second[0],first[1]);self.assertNotEqual(second[1]['implant_id'],first[0]['implant_id']);self.assertTrue(second[1]['active'])
        self.assertEqual(model.store.current.generation,generation+1)
        before=model.store.current;model.merge_implants(pid,revision(),[]);self.assertEqual(model.store.current,before)
        with self.assertRaises(ProfileError):model.merge_implants('builtin:all5',0,[])
    def test_character_profile_and_binding_counters_fail_before_commit(self):
        model=Profiles('memory','d'*64,[1],store_type=lambda _:MemoryStore());pid=model.create('Pilot')['profile_id'];model.bind(F,pid)
        initial=model.snapshot()
        for where,key in (('profiles',pid),('bindings',F)):
            model._state=deepcopy(initial);model._state[where][key]['revision']=sets.MAX_INT
            before=model.snapshot();stored=model.store.current
            with self.assertRaises(ProfileError):model.merge_implants(pid,model._state['profiles'][pid]['revision'],[1,79])
            self.assertEqual(model.snapshot(),before);self.assertEqual(model.store.current,stored)
            model.merge_implants(pid,model._state['profiles'][pid]['revision'],[]);self.assertEqual(model.snapshot(),before)
    def test_history_strips_only_revision_and_template_fit_independence(self):
        before=state();after=deepcopy(before)
        key=sets.mutate(after['implant_sets'],'create',dict(name='Mine'),CATALOGUE)
        history=GraphHistory().record(before,after,'Create implant set',{'library'})
        self.assertEqual(history.details(F)['undo_count'],0)
        reverted,_,_=history.replay('library',False,after);self.assertEqual(reverted,inputs(before))
        changed=deepcopy(after);changed['implant_sets']['sets'][key]['revision']=8
        self.assertEqual(inputs(after),inputs(changed))
        changed['implant_sets']['sets'][key]['item_ids']=[79,1];self.assertNotEqual(inputs(after),inputs(changed))
    def test_request_exact_fields_kinds_names_and_namespaces(self):
        authority=state();sets.request(wire(),CONTEXT,authority)
        for change in (lambda r:r.update(extra=True),lambda r:r.update(version=True),lambda r:r['context'].update(generation=1.0),
            lambda r:r['view'].update(limit=True),lambda r:r['view'].update(offset=-1),lambda r:r['view'].update(query='a\x85'),
            lambda r:r['view'].update(selected_set_id='builtin:implant-set:01'),lambda r:r['view'].update(selected_set_id='builtin:implant-set:2147483648'),
            lambda r:r['view'].update(target_profile_id='profile:no'),lambda r:r['view'].update(history_target='e'*32)):
            request=wire();change(request)
            with self.assertRaises(ProfileError):sets.request(request,CONTEXT,authority)
        with self.assertRaises(ProfileError):sets.request(wire('create',dict(name=' Mine ')),CONTEXT,authority)
    def test_request_missing_selected_is_readable_but_operation_targets_are_exact(self):
        missing='implant-set:'+'e'*32
        r=wire();r['view'].update(selected_set_id=missing,target_profile_id='profile:'+'e'*32)
        sets.request(r,CONTEXT,state())
        for op,args in [('rename',dict(set_id=missing,revision=1,name='Mine')),
                        ('apply_fit',dict(set_id=B,revision=0,fit_revision=1)),
                        ('apply_profile',dict(set_id=B,revision=0,profile_id=P,profile_revision=1))]:
            request=wire(op,args)
            with self.assertRaises(ProfileError):sets.request(request,CONTEXT,state())
    def test_parse_duplicate_trailing_nonfinite_oversize_and_surrogate_pair(self):
        for value in ('{"version":1,"version":1}','{} false','{"x":NaN}','{"x":Infinity}','x'*16385,'😀'*5000,'{"x":"\ud800"}'):
            with self.assertRaises(ProfileError):sets.parse(value)
        value=sets.parse('{"name":"\\ud83d\\ude00"}');self.assertEqual(value['name'],'😀')
    def test_state_page_order_nullable_deleted_selection_and_profile_no_fallback(self):
        authority=state()
        for name in ('a','Z','A'):sets.mutate(authority['implant_sets'],'create',dict(name=name),CATALOGUE)
        view=wire()['view'];view['selected_set_id']=B
        result=sets.state_view(authority,CONTEXT,F,view,GraphHistory(),CATALOGUE,lambda key:False)
        self.assertEqual([r['name'] for r in result['page']['entries']],['Grade-less','A','Z','a'])
        self.assertEqual([r['slot'] for r in result['detail']['items']],[79,6,7])
        view.update(selected_set_id='implant-set:'+'f'*32,target_profile_id='profile:'+'f'*32,offset=100)
        result=sets.state_view(authority,CONTEXT,F,view,GraphHistory(),CATALOGUE,lambda key:False)
        self.assertIsNone(result['detail']);self.assertIsNone(result['destination']);self.assertEqual(result['page']['entries'],[])
        self.assertEqual(result['page']['offset'],100);self.assertEqual(result['save_source']['fit_id'],F)
    def test_save_source_is_applied_authority_not_preview_profile(self):
        authority=state();record=authority['fit_graph']['records'][F]
        record['implants']=[dict(name='One',slot=6,active=False)];record['inspection_ids']['implants']=['1'*32]
        authority['profiles']['profiles'][P]['implants']=[dict(implant_id='2'*32,item_id=79,slot=79,active=False)]
        view=wire()['view'];view['target_profile_id']='builtin:all0'
        result=sets.state_view(authority,CONTEXT,F,view,GraphHistory(),CATALOGUE,lambda key:False)
        self.assertEqual(result['destination']['profile_id'],'builtin:all0');self.assertEqual(result['save_source']['source'],'FIT')
        self.assertEqual(sets.applied_ids(authority,F,sets.item_id_for_name),[1]);record['implant_source']='CHARACTER'
        result=sets.state_view(authority,CONTEXT,F,view,GraphHistory(),CATALOGUE,lambda key:False)
        self.assertEqual(result['save_source']['profile_id'],P);self.assertEqual(sets.applied_ids(authority,F,sets.item_id_for_name),[79])
    def test_replay_anchor_disappearance_falls_back_history_only(self):
        authority=state();authority['fit_graph']['records'].clear();view=wire()['view'];view['history_target']=F
        result=sets.state_view(authority,CONTEXT,F,view,GraphHistory(),CATALOGUE,lambda key:False)
        self.assertIsNone(result['anchor_fit_id']);self.assertIsNone(result['save_source']);self.assertIsNone(result['destination'])
        self.assertEqual(result['history']['target'],'library')


if __name__=='__main__':unittest.main()
