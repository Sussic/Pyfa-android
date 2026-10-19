"""G04 wire/source/lifecycle guards; scalar doubles are not legal-fit EOS proof."""
import ast
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from android_bridge.offline.shield_regeneration_samples import sample_shield_regeneration
from android_bridge.offline import shield_regeneration_math as calculation

REPO = Path(__file__).resolve().parents[3]
CONTEXT = dict(session_id='shield', dataset_sha256='a'*64, generation=0)

def request(x='time', y='shield_amount', effective=False, bounds=(0,300), start=0):
    hp='EHP' if effective else 'HP'
    return dict(version=1,request_id='shield-test',context=deepcopy(CONTEXT),fits=[dict(fit_id='fit',revision=1)],
        x=dict(quantity='time' if x=='time' else 'shield_amount',unit='s' if x=='time' else '%' if x=='percent' else hp,
               input_unit='s' if x=='time' else '%',range=list(bounds)),
        y=dict(quantity=y,unit=hp+('/s' if y=='shield_regen' else '')),effective=effective,
        starting_shield_percent=start if x=='time' else None,budget_ms=10000)

def fit(capacity=1000.,recharge=100.,pattern=(25.,25.,25.,25.),resonances=(1.,.8,.6,.5)):
    attrs=dict(shieldCapacity=capacity,shieldRechargeRate=recharge*1000)
    attrs.update(dict(zip(('shieldEmDamageResonance','shieldThermalDamageResonance','shieldKineticDamageResonance','shieldExplosiveDamageResonance'),resonances)))
    scope={};tree=ast.parse((REPO/'eos/saveddata/damagePattern.py').read_bytes())
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='effectivify')
    exec(compile(ast.Module(body=[method],type_ignores=[]),'original-effectivify','exec'),scope)
    damage=NS(DAMAGE_TYPES=('em','thermal','kinetic','explosive'),**dict(zip(('emAmount','thermalAmount','kineticAmount','explosiveAmount'),pattern)))
    damage.effectivify=lambda item,amount,kind:scope['effectivify'](damage,item,amount,kind)
    return NS(ID=1,ship=NS(getModifiedItemAttr=lambda key:attrs[key]),damagePattern=damage)

class BoundaryTests(unittest.TestCase):
    def setUp(self):self.fit=fit()
    def sample(self,r=None,**kw):
        args=dict(resolve_fit=lambda k:(self.fit,1),current_context=lambda:CONTEXT,clock=lambda:0)
        args.update(kw)
        return sample_shield_regeneration(request() if r is None else r,**args)
    def good(self,r=None,**kw):
        out=self.sample(r,**kw);self.assertTrue(out['ok'],out);return out
    def bad(self,r=None,code='invalid_request',**kw):
        out=self.sample(r,**kw);self.assertEqual(out['error']['code'],code,out);self.assertNotIn('series',out);return out
    def test_all_twelve_modes_and_source_columns(self):
        modes=set()
        for effective in (False,True):
            for x in ('time','shield_amount','percent'):
                for y in ('shield_amount','shield_regen'):
                    r=request(x,y,effective,bounds=(0,100));o=self.good(r);row=o['series'][0]
                    self.assertEqual(o['x'],r['x']);self.assertEqual(o['y'],r['y']);self.assertEqual(o['total_points'],201)
                    self.assertEqual(row['source'],dict(shield_capacity_hp=1000.,shield_recharge_seconds=100.,
                        damage_pattern=dict(em=25.,thermal=25.,kinetic=25.,explosive=25.)))
                    modes.add((x,y,effective))
        self.assertEqual(len(modes),12)
    def test_exact_copied_source_ast(self):
        candidate=ast.parse(Path(calculation.__file__).read_bytes())
        def definitions(tree):return {n.name:n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
        dest=definitions(candidate)
        for path,names in [('graphs/data/base/getter.py',('PointGetter','SmoothPointGetter')),
            ('graphs/data/fitShieldRegen/getter.py',('Time2ShieldAmountGetter','Time2ShieldRegenGetter','ShieldAmount2ShieldAmountGetter','ShieldAmount2ShieldRegenGetter','calculateShieldAmount','calculateShieldRegen'))]:
            original=definitions(ast.parse((REPO/path).read_bytes()))
            for name in names:self.assertEqual(ast.dump(original[name]),ast.dump(dest[name]),name)
        for path,name in [('graphs/data/base/graph.py','FitGraph'),('graphs/data/fitShieldRegen/graph.py','FitShieldRegenGraph'),
                          ('gui/builtinViewColumns/attributeDisplayGraph.py','ShieldAmountColumn'),('gui/builtinViewColumns/attributeDisplayGraph.py','ShieldTimeColumn')]:
            original=definitions(ast.parse((REPO/path).read_bytes()))[name]
            for child in dest[name].body:
                name_or_field=getattr(child,'name',None) or child.targets[0].id
                matches=[n for n in original.body if getattr(n,'name',None)==name_or_field or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name_or_field for t in n.targets)]
                self.assertEqual(len(matches),1);self.assertEqual(ast.dump(child),ast.dump(matches[0]),name_or_field)
    def test_starts_null_zero_quarter_full_and_clamping(self):
        for start,wanted in ((None,0),(0,0),(25,250),(100,1000),(-25,0),(150,1000)):
            self.assertEqual(self.good(request(start=start))['series'][0]['y'][0],wanted)
    def test_reversed_clamped_and_per_fit_hp_ranges(self):
        r=request('shield_amount',bounds=(150,-50));r['fits'].append(dict(fit_id='other',revision=1));other=fit(3500)
        out=self.good(r,resolve_fit=lambda k:(self.fit if k=='fit' else other,1))
        self.assertEqual(out['x']['range'],[150,-50])
        self.assertEqual([row['x'][-1] for row in out['series']],[1000,3500])
        self.assertEqual([row['x'][0] for row in out['series']],[0,0])
    def test_signed_time_retains_above_capacity_and_negative_rate(self):
        amount=self.good(request(bounds=(-100,-100)))['series'][0]['y'][0]
        rate=self.good(request(y='shield_regen',bounds=(-100,-100)))['series'][0]['y'][0]
        self.assertGreater(amount,1000);self.assertLess(rate,0)
    def test_singleton_underflow_and_201_duplicate_samples(self):
        for bounds in ((25,25),(0,math.ulp(0.))):self.assertEqual(self.good(request(bounds=bounds))['total_points'],1)
        row=self.good(request(bounds=(1e12,math.nextafter(1e12,math.inf))))['series'][0]
        self.assertEqual(len(row['x']),201);self.assertLess(len(set(row['x'])),201)
    def test_huge_finite_input_intermediate_overflow_is_preserved(self):
        self.assertEqual(set(self.good(request(bounds=(1e308,1.1e308)))['series'][0]['y']),{1000})
        self.assertEqual(self.good(request('shield_amount',bounds=(1e308,1.1e308)))['series'][0]['x'],[1000])
        self.assertEqual(set(self.good(request(start=1e308))['series'][0]['y']),{1000})
    def test_zero_capacity_identity_percent_fallback(self):
        self.fit=fit(0)
        for bounds in ((-50,150),(25,25)):
            row=self.good(request('percent',bounds=bounds))['series'][0]
            self.assertEqual(row['x'],list(bounds));self.assertEqual(row['y'],[0,0])
        self.assertEqual(self.good(request('shield_amount'))['total_points'],1)
        self.bad(request(),code='invalid_engine_data')
        self.bad(request('percent','shield_regen'),code='invalid_engine_data')
    def test_zero_recharge_getter_specific_handling(self):
        self.fit=fit(recharge=0)
        self.good(request('shield_amount'))
        self.bad(request(),code='invalid_engine_data');self.bad(request('shield_amount','shield_regen'),code='invalid_engine_data')
    def test_signed_source_identity_and_zero_pattern_are_read_semantics(self):
        self.fit=fit(-1000,pattern=(0,0,0,0))
        row=self.good(request('percent',effective=True,bounds=(0,100)))['series'][0]
        self.assertEqual(row['x'][0],100);self.assertEqual(row['x'][-1],0)
        self.assertEqual(row['y'][0],-1000);self.assertEqual(row['y'][-1],0)
    def test_zero_resonance_divider_falls_back_to_raw(self):
        self.fit=fit(resonances=(0,0,0,0))
        self.assertEqual(self.good(request('shield_amount',effective=True,bounds=(25,25)))['series'][0]['y'],[250])
    def test_nonfinite_final_or_source_data_is_atomic_error(self):
        for r in (request(bounds=(-1e308,-1e308)),request(bounds=(-1e308,1e308))):self.bad(r,code='invalid_engine_data')
        for value in (math.nan,math.inf):
            self.fit=fit(value);self.bad(code='invalid_engine_data')
        self.fit=fit(pattern=(math.nan,1,1,1));self.bad(code='invalid_engine_data')
    def test_all_eight_fit_results_preserve_order(self):
        r=request();r['fits']=[dict(fit_id=str(i),revision=1) for i in range(8)]
        out=self.good(r);self.assertEqual(out['total_points'],1608);self.assertEqual([v['fit_id'] for v in out['series']],[str(i) for i in range(8)])
    def test_strict_request_rejections(self):
        cases=[]
        for key,value in [('version',True),('effective',1),('budget_ms',0),('fits',[]),('starting_shield_percent','25')]:
            r=request();r[key]=value;cases.append(r)
        for bounds in ([None,1],[False,1],[0,math.inf],[0,math.nan],[0],['0',1]):
            r=request();r['x']['range']=bounds;cases.append(r)
        for axis,key,value in [('x','input_unit','HP'),('x','unit','EHP'),('y','unit','%'),('y','quantity','repair_rate')]:
            r=request();r[axis][key]=value;cases.append(r)
        r=request();r['fits']*=2;cases.append(r)
        r=request();r['resolution']=200;cases.append(r)
        r=request('percent');r['starting_shield_percent']=0;cases.append(r)
        for r in cases:
            with self.subTest(r=r):self.bad(r)
    def test_cancel_deadline_clock_context_revision_and_handle(self):
        for kw,code in [({'cancelled':lambda:True},'cancelled'),({'clock':iter([0,10]).__next__},'deadline_exceeded'),
                       ({'clock':iter([1,0]).__next__},'clock_error'),({'clock':lambda:math.nan},'clock_error'),
                       ({'current_context':lambda:dict(CONTEXT,generation=1)},'stale_context'),({'resolve_fit':lambda k:(self.fit,2)},'stale_fit')]:
            self.bad(code=code,**kw)
        def missing(key):raise KeyError(key)
        self.bad(code='fit_not_found',resolve_fit=missing)
        handles=iter([self.fit,fit()]);self.bad(code='stale_fit',resolve_fit=lambda k:(next(handles),1))
    def test_midcurve_cancel_deadline_and_stale_drop_all_results(self):
        original=calculation.Time2ShieldAmountGetter._calculatePoint
        for kind in ('cancelled','deadline_exceeded','stale_context'):
            calls=[]
            def point(*args,**kw):calls.append(1);return original(*args,**kw)
            extra={'cancelled':lambda:len(calls)>=4} if kind=='cancelled' else {'clock':lambda:10 if len(calls)>=4 else 0} if kind=='deadline_exceeded' else {'current_context':lambda:dict(CONTEXT,generation=int(len(calls)>=4))}
            with patch.object(calculation.Time2ShieldAmountGetter,'_calculatePoint',point):self.bad(code=kind,**extra)
            self.assertEqual(len(calls),4)
    def test_prepare_is_causal_and_exceptions_are_atomic(self):
        def prepare(value):value.ship=fit(2500).ship
        self.assertEqual(self.good(prepare_fit=prepare)['series'][0]['source']['shield_capacity_hp'],2500)
        def failed(value):raise RuntimeError('injected')
        self.bad(code='engine_error',prepare_fit=failed)

    def test_second_fit_error_never_returns_first_curve(self):
        r=request();r['fits'].append(dict(fit_id='other',revision=1))
        other=fit(recharge=0)
        self.bad(r,code='invalid_engine_data',resolve_fit=lambda k:(self.fit if k=='fit' else other,1))
    def test_admission_rejection_retains_resource_error(self):
        from android_bridge.projected_drone_admission import AdmissionRejected
        def refused(value):raise AdmissionRejected('bounded preparation unavailable')
        self.bad(code='resource_exhausted',prepare_fit=refused)
        with patch.object(calculation.Time2ShieldAmountGetter,'_calculatePoint',side_effect=AdmissionRejected('bounded calculation unavailable')):
            self.bad(code='resource_exhausted')

class EnvelopeTests(unittest.TestCase):
    def test_malformed_duplicate_and_oversized_requests(self):
        from android_bridge.offline.native_session import NativeSession
        fake=NS(graph=NS(_ready=lambda:None))
        for text in (None,' '*16385,'{"version":1,"version":1}','{'):
            out=json.loads(NativeSession.shield_regeneration_samples(fake,text))
            self.assertEqual(out['error']['code'],'invalid_request');self.assertNotIn('series',out)

from test_native_session import NativeSessionTests
class SessionTests(NativeSessionTests):
    def sample_request(self):
        r=request();r['context']=self.session.context()
        r['fits']=[dict(fit_id=self.key,revision=self.session._revisions[self.key])]
        return r
    def sample(self,r=None):
        return json.loads(self.session.shield_regeneration_samples(json.dumps(self.sample_request() if r is None else r)))
    def test_durable_read_restart_and_stale_identity(self):
        before=self.path.read_bytes();graph=self.session.graph.snapshot();history=self.session.history_details(self.key)
        old=self.sample_request();out=self.sample(old);self.assertTrue(out['ok'],out)
        self.assertEqual(out['total_points'],201);self.assertGreater(out['series'][0]['y'][-1],0)
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(graph,self.session.graph.snapshot())
        self.assertEqual(history,self.session.history_details(self.key))
        self.reopen();self.assertEqual(self.sample(old)['error']['code'],'stale_context')
        self.assertEqual(out['series'],self.sample()['series'])
    def test_cancel_and_durable_failure_return_no_partial_data(self):
        before=self.path.read_bytes();r=json.dumps(self.sample_request())
        out=json.loads(self.session.shield_regeneration_samples(r,cancelled=lambda:True))
        self.assertEqual(out['error']['code'],'cancelled');self.assertEqual(before,self.path.read_bytes())
        with patch.object(self.session.graph,'_verify_durable',side_effect=RuntimeError('injected')):
            out=self.sample();self.assertFalse(out['ok']);self.assertNotIn('series',out)
        self.assertEqual(before,self.path.read_bytes())
    def test_profile_edit_undo_redo_invalidates_and_changes_source_capacity(self):
        old=self.sample_request();capacity=self.sample()['series'][0]['source']['shield_capacity_hp']
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        self.assertEqual(self.sample(old)['error']['code'],'stale_context')
        before=self.path.read_bytes();history=self.session.history_details(self.key)
        lower=self.sample();self.assertTrue(lower['ok'],lower)
        self.assertLess(lower['series'][0]['source']['shield_capacity_hp'],capacity)
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(history,self.session.history_details(self.key))
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.sample()['series'][0]['source']['shield_capacity_hp'],capacity)
        self.edit('redo',dict(fit_id=self.key))
        self.assertEqual(self.sample()['series'][0]['source']['shield_capacity_hp'],lower['series'][0]['source']['shield_capacity_hp'])
    def test_incoming_projected_drone_admission_without_graph_simulation(self):
        from eos.capSim import CapSimulator
        from eos.saveddata.fit import Fit
        item=self.engine._item('Warrior SW-300').ID
        self.edit('add_projected_drone',dict(fit_id=self.key,item_id=item))
        before=self.path.read_bytes();history=self.session.history_details(self.key)
        resets=[];drains=[];old_reset=CapSimulator.reset;old_drain=Fit._Fit__generateDrain
        def reset(obj,*a,**kw):resets.append(True);return old_reset(obj,*a,**kw)
        def drain(obj,*a,**kw):drains.append(True);return old_drain(obj,*a,**kw)
        with patch.object(CapSimulator,'reset',reset),patch.object(Fit,'_Fit__generateDrain',drain), \
             patch.object(CapSimulator,'run',side_effect=AssertionError('No graph cap simulation')), \
             patch.object(Fit,'getCapSimData',side_effect=AssertionError('No graph cap result')):
            out=self.sample()
        self.assertTrue(out['ok'],out);self.assertTrue(resets);self.assertTrue(drains)
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(history,self.session.history_details(self.key))

def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(BoundaryTests);suite.addTests(loader.loadTestsFromTestCase(EnvelopeTests))
    for name in SessionTests.__dict__:
        if name.startswith('test_'):suite.addTest(SessionTests(name))
    return suite

if __name__=='__main__':unittest.main()
