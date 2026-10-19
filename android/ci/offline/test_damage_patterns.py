"""Pure D05.2 authority/wire tests; no EOS imports, DB sessions or calculations."""
import ast
from collections import OrderedDict
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest

from android_bridge.offline import damage_patterns as damage
from android_bridge.offline.graph_history import GraphHistory, inputs
from android_bridge.offline.profiles import ProfileError

ROOT=Path(__file__).resolve().parents[3]
F='a'*32
G='b'*32
CONTEXT=dict(session_id='c'*32,dataset_sha256='d'*64,generation=1)


def raw(**updates):
    return dict(emAmount=3.0,thermalAmount=7.0,kineticAmount=11.0,explosiveAmount=19.0)|updates


def zero():return dict.fromkeys(damage.DAMAGE_FIELDS,0.0)


def state(version=1):
    value=dict(kind='pyfa.profile-fit-graph',version=version,
        fit_graph=dict(records={key:dict(spec=dict(name=key,target_profile=None,damage_pattern=deepcopy(damage.CATALOGUE[damage.UNIFORM]['values']),skill_level=5,modules=[]),skills={},projections=[],commands=[]) for key in (F,G)},
            fit_order=[F,G],sample_id=F,format=1,revisions={F:1,G:1},modified={F:0,G:0},recent=[]),
        profiles=dict(profiles={},bindings={}))
    if version>=2:value['imports']={}
    if version>=3:value['targets']=dict(version=1,profiles={},bindings={})
    if version>=4:value['damage_patterns']=dict(version=2 if version>=7 else 1,patterns={},bindings={})
    if version>=5:
        for row in value['fit_graph']['records'].values():row.update(implant_source='FIT',character_implants=[])
    if version>=6:value['implant_sets']=dict(version=1,sets={})
    return value


def wire(op='read',args=None,**updates):
    return dict(version=3,request_id='damage-test',context=deepcopy(CONTEXT),fit_id=F,
        view=dict(query='',offset=0,limit=50,selected_pattern_id=None,bound_offset=0,module_offset=0),
        operation=op,arguments=args or {})|updates


class DamagePatternsTests(unittest.TestCase):
    def setUp(self):self.state=state()
    def create(self,name='Shared',value=None):
        return damage.mutate(self.state,'create',dict(name=name,values=raw() if value is None else value),None)[0]
    def assign(self,key,fit=F):
        return damage.mutate(self.state,'assign',dict(pattern_id=key,revision=damage.resolve(self.state.get('damage_patterns',damage.empty()),key)['revision'],fit_revision=1),fit)
    def test_all118_original_names_order_raw_kinds_and_provenance(self):
        tree=ast.parse((ROOT/'eos/saveddata/damagePattern.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_t','_c') or
               isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BUILTINS' for t in n.targets)]
        namespace={'OrderedDict':OrderedDict};exec(compile(ast.Module(body=nodes,type_ignores=[]),'original-damage-constant-ast','exec'),namespace)
        original=namespace['BUILTINS'];self.assertEqual(list(original),list(range(-1,-119,-1)))
        self.assertEqual(list(damage.CATALOGUE),[damage.builtin_id(k) for k in original])
        for number,row in original.items():
            candidate=damage.CATALOGUE[damage.builtin_id(number)]
            self.assertEqual(candidate['name'],row[0]);self.assertEqual(candidate['revision'],0)
            self.assertTrue(damage.exact(candidate['values'],dict(zip(damage.DAMAGE_FIELDS,row[1:]))))
        import hashlib
        self.assertIn(hashlib.sha256((ROOT/'eos/saveddata/damagePattern.py').read_bytes()).hexdigest(),(ROOT/'android_bridge/offline/damage_catalogue.py').read_text())
    def test_uniform_fractional_large_and_subnormal_numbers(self):
        self.assertTrue(damage.exact(damage.CATALOGUE[damage.UNIFORM]['values'],dict.fromkeys(damage.DAMAGE_FIELDS,25)))
        self.assertTrue(damage.exact(damage.CATALOGUE[damage.builtin_id(-17)]['values'],dict(zip(damage.DAMAGE_FIELDS,(7.7,7.7,0,0)))))
        for value in (raw(emAmount=80206.0),raw(emAmount=5e-324),raw(emAmount=-0.0),dict.fromkeys(damage.DAMAGE_FIELDS,damage.MAX_INT)):
            self.assertTrue(damage.exact(damage.values(value),value))
        self.assertFalse(damage.exact(0,0.0));self.assertFalse(damage.exact(0.0,-0.0))
    def test_percentages_divide_first_scale_zero_and_fixed_order(self):
        huge=dict.fromkeys(damage.DAMAGE_FIELDS,1e307)
        self.assertEqual(damage.percentages(damage.values(huge)),dict.fromkeys(damage.DAMAGE_FIELDS,25.0))
        scaled={k:v*10 for k,v in raw().items()}
        self.assertEqual(damage.percentages(raw()),damage.percentages(scaled))
        self.assertEqual(damage.percentages(zero()),zero())
        for result in damage.percentages(zero()).values():self.assertIs(type(result),float)
        reversed_input=dict(reversed(list(raw().items())))
        self.assertEqual(list(damage.percentages(reversed_input)),list(damage.DAMAGE_FIELDS))
        self.assertEqual(damage.total(reversed_input),damage.total(raw()))
    def test_values_reject_wrong_keys_kinds_negative_nonfinite_overflow(self):
        damage.values(zero(),editor=True)
        for field in damage.DAMAGE_FIELDS:
            for invalid in (None,True,'0',-1.0,float('nan'),float('inf'),10**400,damage.MAX_INT+1):
                with self.subTest(field=field,invalid=repr(invalid)),self.assertRaises(ProfileError):damage.values(raw(**{field:invalid}))
            with self.assertRaises(ProfileError):damage.values(raw(**{field:0}),editor=True)
        for invalid in ({},dict(raw(),extra=0.0),dict.fromkeys(damage.DAMAGE_FIELDS,1e308)):
            with self.assertRaises(ProfileError):damage.values(invalid)
    def test_names_unicode_exact_reserved_and_case_sensitive_uniqueness(self):
        self.assertEqual(damage.name('\u2000[Mine]|Threat\u2000'),'[Mine]|Threat')
        self.assertEqual(len(damage.name('😀'*200)),200)
        for invalid in ('', ' \t ', 'x'*201,'😀'*201,'a\nname','a\x85name','x\ud800'):
            with self.subTest(invalid=repr(invalid)),self.assertRaises(ProfileError):damage.name(invalid)
        for reserved in ('Uniform',' Selected Ammo '):
            with self.assertRaises(ProfileError) as caught:damage.name(reserved)
            self.assertEqual(caught.exception.code,'reserved_name')
        self.create('uniform');self.create('selected ammo');self.create('[Generic]EM')
        with self.assertRaises(ProfileError):self.create(' uniform ')
    def test_duplicate_keeps_source_types_signs_and_independent_id(self):
        key=self.create(value=raw(emAmount=-0.0));self.assign(key)
        copied,_=damage.mutate(self.state,'duplicate',dict(pattern_id=key,revision=1,name='Copy'),None)
        self.assertNotEqual(copied,key);self.assertTrue(damage.exact(damage.resolve(self.state['damage_patterns'],copied)['values'],raw(emAmount=-0.0)))
        damage.mutate(self.state,'update_values',dict(pattern_id=copied,revision=1,values=raw()),None)
        self.assertTrue(damage.exact(damage.resolve(self.state['damage_patterns'],key)['values'],raw(emAmount=-0.0)))
        builtin,_=damage.mutate(self.state,'duplicate',dict(pattern_id=damage.UNIFORM,revision=0,name='Uniform copy'),None)
        self.assertTrue(all(type(v) is int for v in damage.resolve(self.state['damage_patterns'],builtin)['values'].values()))
    def test_zero_record_create_duplicate_validate_and_unassignable(self):
        key=self.create(value=zero());damage.validate(self.state['damage_patterns'],self.state['fit_graph']['records'])
        copied,_=damage.mutate(self.state,'duplicate',dict(pattern_id=key,revision=1,name='Zero copy'),None)
        self.assertTrue(damage.exact(damage.resolve(self.state['damage_patterns'],copied)['values'],zero()))
        before=deepcopy(self.state)
        with self.assertRaises(ProfileError) as caught:self.assign(key)
        self.assertEqual(caught.exception.code,'unassignable');self.assertTrue(damage.exact(before,self.state))
        detail=damage.state_view(self.state,CONTEXT,F,wire()['view']|{'selected_pattern_id':key},GraphHistory())['detail']
        self.assertFalse(detail['assignable']);self.assertEqual(detail['unassignable_reason'],'zero_total');self.assertEqual(detail['percentages'],zero())
    def test_bound_zero_update_refuses_atomically(self):
        key=self.create();self.assign(key);self.assign(key,G);before=deepcopy(self.state)
        with self.assertRaises(ProfileError) as caught:damage.mutate(self.state,'update_values',dict(pattern_id=key,revision=1,values=zero()),None)
        self.assertEqual(caught.exception.code,'unassignable');self.assertTrue(damage.exact(before,self.state))
    def test_shared_live_values_rename_and_unchanged_anonymous_control(self):
        key=self.create();self.assign(key);control=deepcopy(self.state['fit_graph']['records'][G])
        damage.mutate(self.state,'update_values',dict(pattern_id=key,revision=1,values=raw(emAmount=-0.0)),None)
        self.assertTrue(damage.exact(self.state['fit_graph']['records'][F]['spec']['damage_pattern'],raw(emAmount=-0.0)))
        self.assertTrue(damage.exact(self.state['fit_graph']['records'][G],control))
        damage.mutate(self.state,'rename',dict(pattern_id=key,revision=2,name='New'),None)
        self.assertEqual(self.state['damage_patterns']['bindings'][F]['revision'],3)
        damage.validate(self.state['damage_patterns'],self.state['fit_graph']['records'])
    def test_identity_only_detach_preserves_exact_saved_projection(self):
        key=self.create(value=raw(emAmount=-0.0));self.assign(key)
        before=deepcopy(self.state['fit_graph']['records'][F]['spec']['damage_pattern'])
        damage.mutate(self.state,'detach_to_anonymous',dict(pattern_id=key,revision=1,binding_revision=1,fit_revision=1),F)
        self.assertNotIn(F,self.state['damage_patterns']['bindings'])
        self.assertTrue(damage.exact(before,self.state['fit_graph']['records'][F]['spec']['damage_pattern']))
        with self.assertRaises(ProfileError) as caught:damage.mutate(self.state,'detach_to_anonymous',dict(pattern_id=key,revision=1,binding_revision=1,fit_revision=1),F)
        self.assertEqual(caught.exception.code,'stale_binding')
    def test_reset_and_delete_explicitly_bind_integer_uniform(self):
        key=self.create();self.assign(key);self.assign(key,G)
        damage.mutate(self.state,'reset_uniform',dict(fit_revision=1),F)
        damage.mutate(self.state,'delete',dict(pattern_id=key,revision=1,bound_fit_count=1,bound_module_count=0,affected_fit_count=1),None)
        self.assertNotIn(key,self.state['damage_patterns']['patterns'])
        for f in (F,G):
            self.assertEqual(self.state['damage_patterns']['bindings'][f]['pattern_id'],damage.UNIFORM)
            self.assertTrue(damage.exact(self.state['fit_graph']['records'][f]['spec']['damage_pattern'],damage.CATALOGUE[damage.UNIFORM]['values']))
    def test_exact_projection_corruption_refuses_kinds_and_signedzero(self):
        key=self.create(value=raw(emAmount=-0.0));self.assign(key)
        for changed in (0.0,0,1.0):
            candidate=deepcopy(self.state);candidate['fit_graph']['records'][F]['spec']['damage_pattern']['emAmount']=changed
            with self.assertRaises(ProfileError):damage.validate(candidate['damage_patterns'],candidate['fit_graph']['records'])
    def test_corruption_rejects_names_ids_revisions_bound_zero_and_extra_keys(self):
        key=self.create();self.assign(key)
        changes=[lambda s:s['damage_patterns'].update(extra=1),lambda s:s['damage_patterns']['patterns'][key].update(extra=1),
            lambda s:s['damage_patterns']['patterns'][key].update(name='Uniform'),lambda s:s['damage_patterns']['patterns'][key].update(name=' Untrimmed'),
            lambda s:s['damage_patterns']['patterns'][key].update(values=zero()),lambda s:s['damage_patterns']['patterns'][key].update(revision=True),
            lambda s:s['damage_patterns']['bindings'][F].update(pattern_id='damage:'+'0'*32),lambda s:s['fit_graph']['records'].pop(F),
            lambda s:s['damage_patterns']['patterns'].update({damage.UNIFORM:deepcopy(damage.CATALOGUE[damage.UNIFORM])})]
        for change in changes:
            candidate=deepcopy(self.state);change(candidate)
            with self.assertRaises(ProfileError):damage.validate(candidate['damage_patterns'],candidate['fit_graph']['records'])
    def test_builtin_and_custom_paging_order_crossing_filter_and_bounds(self):
        ids=[]
        for offset,size in ((0,50),(50,50),(100,18)):
            page=damage.state_view(self.state,CONTEXT,F,wire()['view']|dict(offset=offset),GraphHistory())['page']
            self.assertEqual(len(page['entries']),size);ids.extend(v['pattern_id'] for v in page['entries'])
        self.assertEqual(ids,list(damage.CATALOGUE))
        c=self.create('zz');b=self.create('aa');a=self.create('AA')
        page=damage.state_view(self.state,CONTEXT,F,wire()['view']|dict(offset=115),GraphHistory())['page']
        self.assertEqual([v['pattern_id'] for v in page['entries']],list(damage.CATALOGUE)[115:]+[a,b,c])
        page=damage.state_view(self.state,CONTEXT,None,wire()['view']|dict(query='pLASmA'),GraphHistory())['page']
        self.assertEqual([v['pattern_id'] for v in page['entries']],[k for k,v in damage.CATALOGUE.items() if 'plasma' in v['name'].casefold()])
        self.assertEqual(damage.state_view(self.state,CONTEXT,None,wire()['view']|dict(offset=damage.MAX_INT),GraphHistory())['page']['entries'],[])
    def test_detail_selection_exact_shapes_and_bound_fit_order(self):
        key=self.create();self.assign(key,G);self.assign(key,F)
        result=damage.state_view(self.state,CONTEXT,F,wire()['view']|dict(selected_pattern_id=key),GraphHistory())
        self.assertEqual(result['selection'],dict(kind='named',pattern_id=key,pattern_revision=1,binding_revision=1))
        self.assertEqual([r['fit_id'] for r in result['detail']['bound_fits']['entries']],[F,G])
        self.assertEqual(set(result),{'version','context','fit_id','fit_revision','selection','page','detail','history','item','module'})
        self.assertEqual(set(result['detail']),{'pattern_id','kind','name','revision','bound_fit_count','assignable','unassignable_reason','values','percentages','bound_fits','bound_modules','bound_module_count','affected_fit_count'})
        self.assertEqual(damage.state_view(self.state,CONTEXT,None,wire()['view'],GraphHistory())['selection'],dict(kind='no_fit',pattern_id=None,pattern_revision=None,binding_revision=None))
    def test_request_duplicate_keys_namespaces_wrong_types_and_size_bounds(self):
        def check(r):return damage.request(damage.parse(json.dumps(r)),CONTEXT,self.state['fit_graph']['records'],damage.empty())
        check(wire())
        invalid=[wire(version=1),wire(version=2),wire(version=True),wire(extra=1),wire(context=CONTEXT|{'generation':2}),wire(fit_id='bad'),wire(request_id='bad\n'),wire(operation='clear')]
        invalid += [wire(view=wire()['view']|{k:v}) for k,v in [('limit',0),('limit',51),('offset',-1),('offset',True),('bound_offset',2**63),('query','😀'*201),('query','x\ud800'),('selected_pattern_id','damage:builtin:-119')]]
        for r in invalid:
            with self.subTest(r=repr(r)),self.assertRaises(ProfileError):check(r)
        for key in ('target:builtin:-1','builtin:all5','damage:builtin:-01','damage:builtin:0','damage:builtin:-119','damage:'+'A'*32):
            with self.assertRaises(ProfileError):damage.identity(key)
        for text in ('{"x":1,"x":2}','{"x":{"a":1,"a":1}}','{"x":NaN}',' '*16385,'😀'*5000,'{'):
            with self.assertRaises(ProfileError):damage.parse(text)
    def test_detach_request_rejects_values_replacements_and_nullable_binding(self):
        args=dict(pattern_id=damage.UNIFORM,revision=0,binding_revision=1,fit_revision=1)
        damage.request(wire('detach_to_anonymous',args),CONTEXT,self.state['fit_graph']['records'],damage.empty())
        for invalid in (args|{'values':raw()},args|{'pattern':raw()},args|{'binding_revision':None},args|{'pattern_id':None}):
            with self.assertRaises(ProfileError):damage.request(wire('detach_to_anonymous',invalid),CONTEXT,self.state['fit_graph']['records'],damage.empty())
    def test_history_keeps_anonymous_authority_and_strips_only_named_projection(self):
        key=self.create();self.assign(key);before=deepcopy(self.state)
        damage.mutate(self.state,'update_values',dict(pattern_id=key,revision=1,values=raw(emAmount=-0.0)),None)
        history=GraphHistory().record(before,self.state,'Edit damage',{'library',F})
        projected=inputs(self.state)
        self.assertNotIn('damage_pattern',projected['records'][F]['spec']);self.assertIn('damage_pattern',projected['records'][G]['spec'])
        self.assertNotIn('revision',projected['damage_patterns']['patterns'][key]);self.assertNotIn('revision',projected['damage_patterns']['bindings'][F])
        replayed,_,_=history.replay('library',False,self.state);self.assertTrue(damage.exact(replayed,inputs(before)))
    def test_revision_capacity_and_delete_count_fail_before_partial_mutation(self):
        key=self.create();self.assign(key);self.assign(key,G)
        for op,args,extra in (
            ('rename',dict(pattern_id=key,revision=1,name='New'),dict(binding_floor={G:damage.MAX_INT})),
            ('delete',dict(pattern_id=key,revision=1,bound_fit_count=2,bound_module_count=0,affected_fit_count=2),dict(binding_floor={G:damage.MAX_INT})),
            ('delete',dict(pattern_id=key,revision=1,bound_fit_count=1,bound_module_count=0,affected_fit_count=1),{}),
            ('assign',dict(pattern_id=damage.UNIFORM,revision=0,fit_revision=2),{})):
            before=deepcopy(self.state)
            with self.assertRaises(ProfileError):damage.mutate(self.state,op,args,F,**extra)
            self.assertTrue(damage.exact(self.state,before))


if __name__=='__main__':unittest.main()
