"""Pure target catalogue, raw representation, wire and authoritative history.

No EOS imports/bootstrap/database; originals are unchanged catalogue AST only.
"""
import ast
from collections import OrderedDict
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest

from android_bridge.offline import target_profiles as target
from android_bridge.offline.graph_history import GraphHistory, inputs
from android_bridge.offline.profiles import ProfileError

ROOT=Path(__file__).resolve().parents[3]
F='a'*32
G='b'*32
CONTEXT=dict(session_id='c'*32,dataset_sha256='d'*64,generation=1)


def raw(**updates):
    return dict(emAmount=0.0,thermalAmount=0.25,kineticAmount=0.5,explosiveAmount=1.0,
                maxVelocity=None,signatureRadius=None,radius=None,hp=None,**{}) | updates


def state():
    return dict(kind='pyfa.profile-fit-graph',version=1,
        fit_graph=dict(records={key:dict(spec=dict(name=key,target_profile=None,skill_level=5),skills={},projections=[],commands=[]) for key in (F,G)},
            fit_order=[F,G],sample_id=F,format=1,revisions={F:1,G:1},modified={F:0,G:0},recent=[]),
        profiles=dict(profiles={},bindings={}))


def wire(op='read',args=None,**updates):
    return dict(version=1,request_id='target-test',context=deepcopy(CONTEXT),fit_id=F,
        view=dict(query='',offset=0,limit=50,selected_target_id=None,bound_offset=0),
        operation=op,arguments=args or {}) | updates


class TargetProfilesTests(unittest.TestCase):
    def setUp(self):self.state=state()
    def create(self, name='Target', value=None):
        key,_=target.mutate(self.state,'create',dict(name=name,values=raw() if value is None else value),None)
        return key
    def assign(self,key,fit=F):
        target.mutate(self.state,'assign',dict(target_id=key,revision=target.resolve(self.state['targets'],key)['revision'],fit_revision=1),fit)
    def test_all195_original_builtin_values_names_and_kinds(self):
        tree=ast.parse((ROOT/'eos/saveddata/targetProfile.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_t','_c') or
               isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BUILTINS' for t in n.targets)]
        namespace={'OrderedDict':OrderedDict};exec(compile(ast.Module(body=nodes,type_ignores=[]),'original-builtin-ast','exec'),namespace)
        self.assertEqual(set(namespace['BUILTINS']),set(range(-195,0)))
        self.assertEqual(len(target.CATALOGUE),195)
        for identity,row in namespace['BUILTINS'].items():
            actual=target.CATALOGUE[target.builtin_id(identity)]
            expected=dict(zip(target.PROFILE_FIELDS,(*row[1:],*([None]*(9-len(row))))))
            self.assertTrue(target.exact(actual['values'],expected),(identity,actual,expected))
            self.assertEqual(actual['name'],row[0]);self.assertEqual(actual['revision'],0)
        self.assertIs(type(target.CATALOGUE[target.builtin_id(-149)]['values']['explosiveAmount']),int)
        for key in ('target:builtin:0','target:builtin:-196','target:builtin:-01'):
            with self.assertRaises(ProfileError):target.identity(key)
    def test_raw_null_zero_float_integer_and_signedzero(self):
        for v in (None,0,0.0,-0.0,0.5):
            value=raw(maxVelocity=v,radius=v,signatureRadius=v,hp=v)
            projected=target.effective(value)
            self.assertTrue(target.exact(value,raw(maxVelocity=v,radius=v,signatureRadius=v,hp=v)))
            self.assertTrue(target.exact(projected['hp'],v));self.assertTrue(target.exact(projected['signatureRadius'],v))
            if not v:
                self.assertIs(type(projected['maxVelocity']),int);self.assertEqual(projected['maxVelocity'],0)
                self.assertIs(type(projected['radius']),int)
        self.assertFalse(target.exact(0,0.0));self.assertFalse(target.exact(0.0,-0.0))
    def test_explicit_editor_float_domain_and_all_null_boundaries(self):
        target.values(raw(),editor=True)
        for field in target.PROFILE_FIELDS:
            for invalid in (True,float('nan'),float('inf'),-1.0,10**400):
                with self.subTest(field=field,invalid=str(invalid)),self.assertRaises(ProfileError):target.values(raw(**{field:invalid}),editor=True)
            with self.assertRaises(ProfileError):target.values(raw(**{field:0}),editor=True)
        for field in target.PROFILE_FIELDS[:4]:
            for invalid in (None,1.01):
                with self.assertRaises(ProfileError):target.values(raw(**{field:invalid}),editor=True)
        for field in target.PROFILE_FIELDS[4:]:
            for valid in (None,0.0,-0.0,5e-324):target.values(raw(**{field:valid}),editor=True)
    def test_named_integer_domain_matches_wire_without_restricting_floats(self):
        for field in target.PROFILE_FIELDS[4:]:
            target.values(raw(**{field:target.MAX_INT}))
            target.values(raw(**{field:float(target.MAX_INT+1)}))
            for invalid in (target.MAX_INT+1,2**100):
                with self.assertRaises(ProfileError):target.values(raw(**{field:invalid}))
        key=self.create();candidate=deepcopy(self.state)
        candidate['targets']['profiles'][key]['values']['maxVelocity']=target.MAX_INT+1
        with self.assertRaises(ProfileError):target.validate(candidate['targets'],candidate['fit_graph']['records'])

    def test_name_unicode_trim_duplicate_and_builtin_namespace(self):
        self.assertEqual(target.name(' \u2000[Mine] Target \u2000 '),'[Mine] Target')
        self.assertEqual(len(target.name('😀'*200)),200)
        for invalid in ('',' \t ', 'x'*201,'😀'*201,'x\nname','x\x7fname','x\x85name','x\ud800'):
            with self.subTest(invalid=repr(invalid)),self.assertRaises(ProfileError):target.name(invalid)
        a=self.create('  All 5  ');b=self.create('all 5');c=self.create('Uniform (25%)')
        self.assertEqual(self.state['targets']['profiles'][a]['name'],'All 5')
        with self.assertRaises(ProfileError):self.create('All 5')
        target.mutate(self.state,'rename',dict(target_id=b,revision=1,name='all 5'),None)
        self.assertEqual(self.state['targets']['profiles'][b]['revision'],1)
    def test_duplicate_preserves_all_eight_fields_and_independence(self):
        key=self.create(value=raw(hp=1234.0,maxVelocity=-0.0));self.assign(key)
        duplicate,_=target.mutate(self.state,'duplicate',dict(target_id=key,revision=1,name='Copy'),None)
        self.assertNotEqual(key,duplicate)
        self.assertTrue(target.exact(target.resolve(self.state['targets'],key)['values'],target.resolve(self.state['targets'],duplicate)['values']))
        target.mutate(self.state,'update_values',dict(target_id=duplicate,revision=1,values=raw(hp=0.0)),None)
        self.assertEqual(target.resolve(self.state['targets'],key)['values']['hp'],1234.0)
        builtin=target.builtin_id(-149)
        copy,_=target.mutate(self.state,'duplicate',dict(target_id=builtin,revision=0,name='Built-in copy'),None)
        self.assertTrue(target.exact(target.resolve(self.state['targets'],copy)['values'],target.CATALOGUE[builtin]['values']))
    def test_live_binding_inline_control_delete_and_exact_projection(self):
        key=self.create();self.assign(key)
        self.state['fit_graph']['records'][G]['spec']['target_profile']=target.effective(raw())
        target.mutate(self.state,'update_values',dict(target_id=key,revision=1,values=raw(hp=0.0)),None)
        self.assertIs(type(self.state['fit_graph']['records'][F]['spec']['target_profile']['hp']),float)
        self.assertEqual(self.state['fit_graph']['records'][F]['spec']['target_profile']['hp'],0.0)
        self.assertIsNone(self.state['fit_graph']['records'][G]['spec']['target_profile']['hp'])
        target.validate(self.state['targets'],self.state['fit_graph']['records'])
        corrupt=deepcopy(self.state);corrupt['fit_graph']['records'][F]['spec']['target_profile']['hp']=0
        with self.assertRaisesRegex(ProfileError,'disagree'):target.validate(corrupt['targets'],corrupt['fit_graph']['records'])
        target.mutate(self.state,'delete',dict(target_id=key,revision=2,bound_fit_count=1),None)
        self.assertEqual(self.state['targets'],target.empty());self.assertIsNone(self.state['fit_graph']['records'][F]['spec']['target_profile'])
        self.assertIsNotNone(self.state['fit_graph']['records'][G]['spec']['target_profile'])
    def test_revision_stale_protected_and_overflow_failures(self):
        key=self.create();self.assign(key)
        for op,args in (
            ('rename',dict(target_id=key,revision=0,name='No')),
            ('assign',dict(target_id=key,revision=1,fit_revision=2)),
            ('delete',dict(target_id=key,revision=1,bound_fit_count=0)),
            ('rename',dict(target_id=target.builtin_id(-1),revision=0,name='No'))):
            old=deepcopy(self.state)
            with self.assertRaises(ProfileError):target.mutate(self.state,op,args,F)
            self.assertTrue(target.exact(self.state,old))
        row=self.state['targets']['profiles'][key];row['revision']=target.MAX_INT
        with self.assertRaises(ProfileError):target.mutate(self.state,'rename',dict(target_id=key,revision=target.MAX_INT,name='New'),None)
    def test_pages_selected_detail_and_all_builtins_reachable(self):
        key=self.create();self.assign(key);self.assign(key,G)
        seen=[]
        for offset in range(0,200,50):
            view=wire()['view']|dict(offset=offset,selected_target_id=key)
            actual=target.state_view(self.state,CONTEXT,F,view,GraphHistory())
            seen.extend(r['target_id'] for r in actual['page']['entries'])
            self.assertEqual(actual['detail']['bound_fit_count'],2)
            self.assertEqual([r['fit_id'] for r in actual['detail']['bound_fits']['entries']],[F,G])
            self.assertEqual(actual['selection']['kind'],'named')
        self.assertEqual(len(seen),196);self.assertEqual(len(set(seen)),196)
        view=wire()['view']|dict(query='uNiFoRm',offset=1000)
        self.assertEqual(target.state_view(self.state,CONTEXT,None,view,GraphHistory())['page']['entries'],[])
        self.assertEqual(target.state_view(self.state,CONTEXT,None,view,GraphHistory())['page']['total'],4)
    def test_strict_request_keys_kinds_bounds_and_duplicates(self):
        def check(r):target.request(target.parse(json.dumps(r)),CONTEXT,self.state['fit_graph']['records'],target.empty())
        check(wire())
        invalid=[wire(version=True),wire(extra=1),wire(context=CONTEXT|{'generation':2}),wire(fit_id='unknown'),wire(request_id='bad\n'),wire(operation='unknown')]
        invalid.extend(wire(view=wire()['view']|{k:v}) for k,v in [('limit',0),('limit',51),('offset',-1),('offset',True),('bound_offset',2**63),('query','😀'*201),('selected_target_id','target:builtin:0')])
        for r in invalid:
            with self.subTest(r=r),self.assertRaises(ProfileError):check(r)
        for malformed in ('{"version":1,"version":1}', '{"x":NaN}', ' '*16385, '😀'*5000, '{'):
            with self.assertRaises(ProfileError):target.parse(malformed)
    def test_target_history_excludes_revisions_and_projection(self):
        key=self.create();self.assign(key)
        before=deepcopy(self.state)
        target.mutate(self.state,'update_values',dict(target_id=key,revision=1,values=raw(hp=0.0)),None)
        history=GraphHistory().record(before,self.state,'Values',{'library',F})
        projected=inputs(self.state)
        self.assertNotIn('revision',projected['targets']['profiles'][key]);self.assertNotIn('revision',projected['targets']['bindings'][F])
        self.assertNotIn('target_profile',projected['records'][F]['spec'])
        result,undone,action=history.replay('library',False,self.state)
        self.assertTrue(target.exact(result,inputs(before)));self.assertEqual(undone.details(F)['redo_count'],1)
    def test_signedzero_history_and_later_participant_branch(self):
        key=self.create(value=raw(hp=0.0));self.assign(key)
        before=deepcopy(self.state)
        target.mutate(self.state,'update_values',dict(target_id=key,revision=1,values=raw(hp=-0.0)),None)
        history=GraphHistory().record(before,self.state,'Signed zero',{'library',F})
        self.assertEqual(history.details(F)['undo_count'],1)
        result,undone,_=history.replay(F,False,self.state)
        self.assertEqual(math.copysign(1,result['targets']['profiles'][key]['values']['hp']),1)
        blocked=history.record_legacy('Later',F,object())
        with self.assertRaises(ValueError):blocked.replay('library',False,self.state)
        branched=undone.record_legacy('Branch',F,object())
        self.assertEqual(branched.details('library')['redo_count'],0)
    def test_corruption_unknown_ids_fields_names_and_dangling_bindings(self):
        key=self.create();self.assign(key)
        mutations=[lambda s:s['targets'].update(extra=1),lambda s:s['targets']['profiles'][key].update(extra=1),
            lambda s:s['targets']['profiles'][key].update(revision=True),
            lambda s:s['targets']['bindings'][F].update(target_id='target:'+'0'*32),
            lambda s:s['fit_graph']['records'].pop(F),
            lambda s:s['targets']['profiles'].update({target.builtin_id(-1):deepcopy(target.CATALOGUE[target.builtin_id(-1)])})]
        for mutation in mutations:
            candidate=deepcopy(self.state);mutation(candidate)
            with self.assertRaises(ProfileError):target.validate(candidate['targets'],candidate['fit_graph']['records'])


if __name__=='__main__':unittest.main()
