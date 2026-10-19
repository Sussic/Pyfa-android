"""No EOS/DB imports: execute full original graph and original UI input AST."""
import ast
import json
import math
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace as NS
import unittest

sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO))
from tools.android_reference.shield_regeneration.preflight import Source, OriginalGraph
from tools.android_reference.shield_regeneration.cases import request, requests
SOURCE=Source(Path(os.environ['PYFA_REFERENCE_SOURCE']))
GRAPH=OriginalGraph(SOURCE)
EVIDENCE=[]


def fit(capacity=1000.0,recharge=100.0,pattern=(25,25,25,25),resonances=(1.0,0.8,0.6,0.5)):
    attrs={'shieldCapacity':capacity,'shieldRechargeRate':recharge*1000}
    attrs.update(dict(zip(('shieldEmDamageResonance','shieldThermalDamageResonance','shieldKineticDamageResonance','shieldExplosiveDamageResonance'),resonances)))
    ship=NS(getModifiedItemAttr=lambda key:attrs[key])
    scope={}; SOURCE.extract('eos/saveddata/damagePattern.py','effectivify',scope)
    damage=NS(DAMAGE_TYPES=('em','thermal','kinetic','explosive'),**dict(zip(('emAmount','thermalAmount','kineticAmount','explosiveAmount'),pattern)))
    damage.effectivify=lambda item,amount,kind:scope['effectivify'](damage,item,amount,kind)
    return NS(ID=1,ship=ship,damagePattern=damage)


def sample(label,value=None,**kwargs):
    value=value or fit(); req=request(label,**kwargs)
    result=GRAPH.sample(value,req)
    EVIDENCE.append(dict(label=label,request=req,result=result))
    return result


def ui_box(kind,text,previous='0'):
    scope={'wx':NS(TextCtrl=object,ID_ANY=0),'re':re}
    SOURCE.extract('gui/utils/inputs.py','strToFloat',scope)
    SOURCE.extract('gui/utils/inputs.py',kind,scope)
    obj=object.__new__(scope[kind]); state={'value':text}; obj._storedValue=previous
    obj.GetValue=lambda:state['value']
    obj.ChangeValue=lambda value:state.update(value=value)
    obj.updateColor=lambda:None
    obj.OnText(NS(Skip=lambda:None))
    result=obj.GetValueRange() if kind=='FloatRangeBox' else obj.GetValueFloat()
    EVIDENCE.append(dict(label='ui_'+kind+'_'+text,typed=text,accepted_text=state['value'],parsed=result))
    return state['value'],result


class OriginalShieldTests(unittest.TestCase):
    def test_offered_twelve_modes_and_no_percentage_y(self):
        modes=set()
        for effective in (False,True):
            graph=GRAPH.fresh(effective)
            self.assertEqual(len(graph.xDefs),3); self.assertEqual(len(graph.yDefs),2)
            self.assertEqual(graph.srcExtraCols,('ShieldAmount','ShieldTime'))
            for x in graph.xDefs:
                for y in graph.yDefs: modes.add((effective,x.handle,x.unit,y.handle,y.unit))
        self.assertEqual(len(modes),12)
        for req in requests('defenses'): self.assertNotEqual(req['y_unit'],'%')
    def test_all_modes_execute_original_pipeline(self):
        for req in requests('defenses'):
            row=GRAPH.sample(fit(),req); EVIDENCE.append(dict(label='mode_'+req['name'],result=row))
            self.assertEqual(len(row['x']),201); self.assertEqual(row['point_calls'],201)
    def test_start_zero_quarter_full_and_null(self):
        for start in (0.0,25.0,100.0,None):
            row=sample('start_'+str(start),y='shieldAmount',start=start)
            self.assertEqual(row['y'][0],{0.0:0.0,25.0:250.0,100.0:1000.0,None:0.0}[start])
    def test_requested_main_clamps_per_capacity(self):
        for capacity in (1000.0,3500.0):
            for span,limited in (((-50.0,150.0),(0.0,capacity)),((-50.0,-10.0),(0.0,0.0)),((150.0,200.0),(capacity,capacity))):
                row=sample('clamp_'+str(capacity)+'_'+str(span),fit(capacity),x='shieldAmount',y='shieldAmount',span=span)
                self.assertEqual(row['effective_main'][1],limited)
    def test_start_clamps_negative_and_above_capacity(self):
        for start,expected in ((-25.0,0.0),(150.0,1000.0)):
            row=sample('start_clamp_'+str(start),y='shieldAmount',start=start)
            self.assertEqual(row['effective_misc']['shieldAmountT0'],expected)
            self.assertEqual(row['y'][0],expected)
    def test_equal_and_underflow_singletons(self):
        for span in ((25.0,25.0),(0.0,math.ulp(0.0))):
            row=sample('single_'+str(span),span=span)
            self.assertEqual(len(row['x']),1); self.assertEqual(row['point_calls'],1)
    def test_reverse_preserves_request_and_sorts_source(self):
        row=sample('reverse',span=(300.0,0.0))
        self.assertEqual(row['effective_input_range'],[300.0,0.0]); self.assertEqual(row['x'][0],0); self.assertEqual(row['x'][-1],300)
    def test_adjacent_retains_201_duplicates_without_refinement(self):
        row=sample('adjacent',span=(1e12,math.nextafter(1e12,math.inf)))
        self.assertEqual(len(row['x']),201); self.assertLess(len(set(row['x'])),201)
    def test_negative_time_is_source_api_behavior(self):
        amount=sample('negative_time_amount',y='shieldAmount',span=(-100.0,-100.0))
        rate=sample('negative_time_rate',span=(-100.0,-100.0))
        self.assertGreater(amount['y'][0],1000); self.assertLess(rate['y'][0],0)
    def test_huge_percent_overflows_then_original_clamps(self):
        row=sample('huge_percent',x='shieldAmount',y='shieldAmount',span=(1e308,1.7e308))
        self.assertTrue(all(math.isinf(v) for v in row['normalized_main'][1]))
        self.assertEqual(row['effective_main'][1],(1000.0,1000.0)); self.assertEqual(row['y'],[1000.0])
        row=sample('huge_start',y='shieldAmount',start=1.7e308)
        self.assertTrue(math.isinf(row['normalized_misc']['shieldAmountT0']))
        self.assertEqual(row['y'][0],1000.0)
    def test_zero_capacity_raw_amount_valid(self):
        row=sample('zero_capacity_hp',fit(0),x='shieldAmount',y='shieldAmount',span=(0.0,100.0))
        self.assertEqual(row['x'],[0.0]); self.assertEqual(row['y'],[0.0])
    def test_zero_capacity_percent_base_fallback_keeps_requested_endpoints(self):
        for span in ((0.0,100.0),(-50.0,150.0),(150.0,-50.0),(25.0,25.0)):
            row=sample('zero_capacity_percent_'+str(span),fit(0),x='percent',y='shieldAmount',span=span)
            self.assertEqual(row['x'],sorted(span)); self.assertEqual(row['y'],[0.0,0.0]); self.assertEqual(row['point_calls'],1)
    def test_zero_capacity_rate_or_time_undefined(self):
        for x,y in (('time','shieldAmount'),('time','shieldRegen'),('shieldAmount','shieldRegen')):
            with self.assertRaises(ZeroDivisionError): sample('zero_capacity_undefined',fit(0),x=x,y=y)
            EVIDENCE.append(dict(label='zero_capacity_'+x+'_'+y,error='ZeroDivisionError'))
    def test_zero_recharge_amount_valid_others_undefined(self):
        row=sample('zero_recharge_amount',fit(recharge=0),x='shieldAmount',y='shieldAmount',span=(0.0,100.0))
        self.assertEqual(row['x'],row['y'])
        for x,y in (('time','shieldAmount'),('time','shieldRegen'),('shieldAmount','shieldRegen')):
            with self.assertRaises(ZeroDivisionError): sample('zero_recharge_undefined',fit(recharge=0),x=x,y=y)
            EVIDENCE.append(dict(label='zero_recharge_'+x+'_'+y,error='ZeroDivisionError'))
    def test_zero_damage_or_resonance_divider_retains_identity(self):
        for value in (fit(pattern=(0,0,0,0)),fit(resonances=(0,0,0,0))):
            raw=sample('zero_divider_raw',value)
            effective=sample('zero_divider_effective',value,effective=True)
            self.assertEqual(raw['y'],effective['y'])
    def test_tiny_divider_produces_nonfinite_effective_output(self):
        row=sample('tiny_divider',fit(pattern=(1,0,0,0),resonances=(math.ulp(0.0),1,1,1)),x='shieldAmount',y='shieldAmount',effective=True,span=(100.0,100.0))
        self.assertTrue(math.isinf(row['x'][0])); self.assertTrue(math.isinf(row['y'][0]))
    def test_huge_positive_time_finite_despite_intermediate_infinity(self):
        row=sample('huge_time',y='shieldAmount',span=(1e308,1e308))
        self.assertEqual(row['y'],[1000.0])
    def test_finite_signed_range_overflow_is_not_valid_zero(self):
        row=sample('overflow_range',y='shieldAmount',span=(-1e308,1e308))
        self.assertTrue(any(not math.isfinite(v) for v in row['x']+row['y']))
    def test_original_scalar_ui_unsigned_and_blank(self):
        self.assertEqual(ui_box('FloatBox','-25'),('0',0.0))
        self.assertEqual(ui_box('FloatBox','25.5'),('25.5',25.5))
        self.assertEqual(ui_box('FloatBox',''),('',None))
        self.assertEqual(ui_box('FloatBox','.'),('.',None))
        self.assertEqual(ui_box('FloatBox','1e3'),('0',0.0))
    def test_original_range_ui_negative_is_missing_not_negative(self):
        self.assertEqual(ui_box('FloatRangeBox','-5'),('-5',(None,5.0)))
        self.assertEqual(ui_box('FloatRangeBox','-5-0'),('0',(0.0,0.0)))
        self.assertEqual(ui_box('FloatRangeBox','300-0'),('300-0',(300.0,0.0)))
        self.assertEqual(ui_box('FloatRangeBox','25'),('25',(25.0,25.0)))
    def test_source_columns_always_raw_hp_and_seconds(self):
        self.assertEqual(GRAPH.columns(fit()),{'capacity':{'value':1000.0,'unit':'HP'},'recharge':{'value':100.0,'unit':'s'}})
    def test_zero_capacity_effective_identity_stays_valid(self):
        row=sample('zero_capacity_effective',fit(0),x='shieldAmount',y='shieldAmount',effective=True,span=(0.0,100.0))
        self.assertEqual(row['x'],[0.0]); self.assertEqual(row['y'],[0.0])
    def test_negative_capacity_and_recharge_source_only_semantics(self):
        row=sample('negative_capacity_identity',fit(-1000),x='shieldAmount',y='shieldAmount',span=(0.0,100.0))
        self.assertEqual(row['x'],row['y']); self.assertEqual((row['x'][0],row['x'][-1]),(-1000.0,0.0))
        row=sample('negative_recharge_rate',fit(recharge=-100),x='shieldAmount',span=(25.0,25.0))
        self.assertLess(row['y'][0],0)
        row=sample('negative_recharge_time',fit(recharge=-100),y='shieldAmount',span=(100.0,100.0))
        self.assertGreater(row['y'][0],1000)
    def test_null_main_endpoint_fails_original_range(self):
        req=request('null_main'); req['input_range']=[None,100.0]
        with self.assertRaises(TypeError): GRAPH.sample(fit(),req)
        EVIDENCE.append(dict(label='null_main',error='TypeError'))
    def test_exponential_and_power_overflow_are_explicit_errors(self):
        for name,span in (('exponential_overflow',(-1e6,-1e6)),('power_overflow',(-10000.0,-10000.0))):
            with self.assertRaises(OverflowError): sample(name,y='shieldAmount',span=span)
            EVIDENCE.append(dict(label=name,error='OverflowError'))
    def test_no_eos_or_candidate_imports(self):
        self.assertFalse(any(name.split('.')[0] in {'eos','android_bridge','mobile_runtime'} for name in sys.modules))


def json_safe(value):
    if isinstance(value,float) and not math.isfinite(value): return {'nonfinite':repr(value)}
    if isinstance(value,(list,tuple)): return [json_safe(v) for v in value]
    if isinstance(value,dict): return {k:json_safe(v) for k,v in value.items()}
    return value


if __name__=='__main__':
    output=os.environ.get('G04_PURE_EVIDENCE')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OriginalShieldTests))
    if output:
        from tools.android_reference.shield_regeneration.preflight import dump,sha
        dump(output,dict(status='passed' if result.wasSuccessful() else 'failed',tests=result.testsRun,
                         source=str(SOURCE.source),source_files=SOURCE.hashes,
                         harness_files={str(Path(__file__).relative_to(REPO)):sha(__file__),
                             'tools/android_reference/shield_regeneration/preflight.py':sha(Path(__file__).with_name('preflight.py')),
                             'tools/android_reference/shield_regeneration/cases.py':sha(Path(__file__).with_name('cases.py'))},
                         no_eos_or_database=True,observations=json_safe(EVIDENCE)))
    sys.exit(not result.wasSuccessful())
