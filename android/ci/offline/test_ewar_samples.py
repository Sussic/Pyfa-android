"""Pure G09 protocol/math/source checks. No EOS database or fit construction."""
import ast
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from android_bridge.offline import ewar_math as maths
from android_bridge.offline.ewar_samples import MODES, parse_request, sample_ewar
from android_bridge.offline.ewar_resource import (EwarReservation, CONTRIBUTORS,
    MAX_WIRE_CHARS, WIRE_HEADER_CHARS, WIRE_POINT_CHARS, live_contributions)
from android_bridge.offline.capacitor_samples import SamplingError

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = dict(session_id='ewar', dataset_sha256='a'*64, generation=0)


def request(mode='webStr'):
    return dict(version=1, request_id='ewar-test', context=deepcopy(CONTEXT),
        fits=[dict(fit_id='fit', revision=1)], x=dict(quantity='distance', unit='km', range=[0,100]),
        y=dict(quantity=mode, unit=MODES[mode][0]), resistance_percent=0,
        ignore_lock_range=True, ignore_drone_control_range=False, budget_ms=10000)


def module(effects=('remoteWebifierFalloff',), strength=-60, optimal=10000, falloff=10000):
    attrs = dict(speedFactor=strength, maxTargetRangeBonus=strength, maxRangeBonus=strength,
        missileVelocityBonus=strength, explosionDelayBonus=strength/2,
        signatureRadiusBonus=abs(strength), energyNeutralizerAmount=60, powerTransferAmount=30,
        nosOverride=False, doomsdayAOERange=5000,
        scanGravimetricStrengthBonus=3, scanLadarStrengthBonus=5,
        scanMagnetometricStrengthBonus=4, scanRadarStrengthBonus=2)
    return NS(item=NS(effects=dict.fromkeys(effects)), maxRange=optimal, falloff=falloff,
              getModifiedItemAttr=attrs.get, getCycleParameters=lambda:NS(averageTime=10000))


def fit(modules=(), drones=(), fighters=()):
    return NS(maxTargetRange=20000, extraAttributes={'droneControlRange':40000},
        activeModulesIter=lambda:iter(modules), activeDronesIter=lambda:iter(drones),
        activeFighterAbilityIter=lambda:iter(fighters))


class BoundaryTests(unittest.TestCase):
    def setUp(self): self.fit=fit([module()])
    def sample(self, r=None, **kw):
        def prep(rows, handles, mode, reserve, check):
            return [live_contributions(handle, mode, check) for handle in handles]
        args=dict(resolve_fit=lambda key:(self.fit,1), current_context=lambda:CONTEXT,
                  prep_admit=prep, clock=lambda:0)
        args.update(kw)
        return sample_ewar(request() if r is None else r, **args)
    def test_seven_original_modes_and_nullable_units(self):
        for mode, (predicates, drone, fighter, lists) in CONTRIBUTORS.items():
            with self.subTest(mode=mode):
                self.fit=fit([module((predicates[0],))]); r=request(mode)
                out=self.sample(r)
                self.assertTrue(out['ok'],out);self.assertGreater(out['series'][0]['y'][0],0)
                self.assertEqual(out['y'],r['y']);self.assertEqual(out['series'][0]['y'][-1],0)
    def test_exact_success_schema_and_effective_fields(self):
        out=self.sample()
        self.assertEqual(set(out),{'version','request_id','ok','context','x','y','resistance_percent',
            'ignore_lock_range','ignore_drone_control_range','effective','total_points','series','error'})
        self.assertEqual(set(out['series'][0]),{'fit_id','revision','x','y'})
        self.assertEqual(out['effective'],dict(distance_range_m=[0,100000],resistance_fraction=0))
        self.assertEqual(out['context']['generation'],0)
    def test_resistance_null_signed_and_clamped_echo(self):
        zero=None
        for value,effective in [(None,None),(0,0),(100,1),(-200,0),(200,1),(-0.0,-0.0)]:
            r=request();r['resistance_percent']=value;out=self.sample(r)
            self.assertTrue(out['ok'],out);self.assertEqual(out['resistance_percent'],value)
            self.assertEqual(out['effective']['resistance_fraction'],effective)
            if effective in (None,0):
                if zero is None:zero=out['series']
                self.assertEqual(out['series'],zero)
            else:self.assertEqual(set(out['series'][0]['y']),{0})
    def test_missing_admission_fails_before_prepare(self):
        calls=[];out=self.sample(prep_admit=None,prepare_fit=lambda f:calls.append(f))
        self.assertEqual(out['error']['code'],'resource_exhausted');self.assertEqual(calls,[])
    def test_all_resolve_and_admit_once_before_first_prepare(self):
        r=request();r['fits']=[dict(fit_id=str(i),revision=1) for i in range(8)]
        calls=[]
        def prep(rows,handles,mode,reserve,check):
            calls.append('admit');self.assertEqual(len(handles),8)
            return [(1,0)]*8
        def prepare(f):calls.append('prepare')
        out=self.sample(r,prep_admit=prep,prepare_fit=prepare)
        self.assertTrue(out['ok'],out);self.assertEqual(calls,['admit']+['prepare']*8)
    def test_singleton_underflow_and_repeated_coordinates(self):
        for bounds in ([5,5],[0,math.nextafter(0,1)/1000]):
            r=request();r['x']['range']=bounds;out=self.sample(r)
            self.assertTrue(out['ok'],out);self.assertEqual(out['total_points'],1)
        r=request();r['x']['range']=[1e9,math.nextafter(1e9,math.inf)]
        out=self.sample(r);self.assertTrue(out['ok'],out)
        self.assertEqual(out['total_points'],51);self.assertLess(len(set(out['series'][0]['x'])),51)
    def test_original_full_ceiling_all_fits(self):
        r=request();r['fits']=[dict(fit_id=str(i),revision=1) for i in range(8)]
        with patch.object(maths,'calculateRangeFactor',side_effect=lambda **kw:kw['distance']/100000):
            out=self.sample(r)
        self.assertTrue(out['ok'],out);self.assertEqual(out['total_points'],1608)
    def test_original_recursion_cancellation_and_recovery(self):
        calls=[]
        def factor(**kw):calls.append(kw['distance']);return kw['distance']/100000
        with patch.object(maths,'calculateRangeFactor',side_effect=factor):
            out=self.sample(cancelled=lambda:len(calls)>=4)
        self.assertEqual(out['error']['code'],'cancelled');self.assertEqual(calls,[0,2000,1000,500])
        self.assertNotIn('series',out);self.assertTrue(self.sample()['ok'])
        with self.assertRaises(LookupError):maths.GraphSettings.getInstance()
    def test_lock_range_gate_and_aoe_exception(self):
        r=request();r['x']['range']=[20,20];r['ignore_lock_range']=False
        self.assertGreater(self.sample(r)['series'][0]['y'][0],0)
        r['x']['range']=[20.001,20.001];self.assertEqual(self.sample(r)['series'][0]['y'],[0])
        self.fit=fit([module(('doomsdayAOEWeb',),optimal=50000)])
        self.assertGreater(self.sample(r)['series'][0]['y'][0],0)
    def test_six_repeated_drone_modes_and_dcr(self):
        for mode, (_, drone_effect, _, _) in CONTRIBUTORS.items():
            if drone_effect is None:continue
            m=module();values=dict(speedFactor=-20,maxTargetRangeBonus=-20,maxRangeBonus=-20,
                signatureRadiusBonus=20,energyNeutralizerAmount=3,energyNeutralizerDuration=1000,
                scanGravimetricStrengthBonus=1,scanLadarStrengthBonus=2,scanMagnetometricStrengthBonus=3,scanRadarStrengthBonus=4)
            drone=NS(item=NS(effects={drone_effect:None}),amountActive=3,getModifiedItemAttr=values.get)
            self.fit=fit(drones=[drone]);r=request(mode);r['x']['range']=[40,40]
            out=self.sample(r);self.assertTrue(out['ok'],out);self.assertGreater(out['series'][0]['y'][0],0)
            r['x']['range']=[40.001,40.001];self.assertEqual(self.sample(r)['series'][0]['y'],[0])
            r['ignore_drone_control_range']=True;self.assertGreater(self.sample(r)['series'][0]['y'][0],0)
            with maths.graph_settings(True,True):
                common=MODES[mode][1](None)._getCommonData({'resist':None},NS(item=self.fit),None)
            values=next(iter(common.values()));self.assertEqual(len(values),3);self.assertIs(values[0],values[1])
    def test_fighter_amount_scales_one_contributor(self):
        for mode, (_,_,effect,_) in CONTRIBUTORS.items():
            if effect is None:continue
            attrs=dict(fighterAbilityEnergyNeutralizerAmount=9,fighterAbilityStasisWebifierSpeedPenalty=-10,
                fighterAbilityECMStrengthGravimetric=1,fighterAbilityECMStrengthLadar=2,
                fighterAbilityECMStrengthMagnetometric=3,fighterAbilityECMStrengthRadar=4)
            f=NS(amount=3,getModifiedItemAttr=attrs.get);a=NS(effect=NS(name=effect),cycleTime=3000)
            self.fit=fit(fighters=[(f,a)]);r=request(mode);r['x']['range']=[0,0]
            self.assertTrue(self.sample(r)['ok']);self.assertEqual(live_contributions(self.fit,mode,lambda:None),(1,0))
    def test_guidance_runs_two_original_multiplier_lists(self):
        self.fit=fit([module(('shipModuleGuidanceDisruptor',))]);r=request('gdStrRange');r['x']['range']=[0,0]
        with patch.object(maths,'calculateMultiplier',wraps=maths.calculateMultiplier) as calculate:
            out=self.sample(r)
        self.assertTrue(out['ok'],out);self.assertEqual(calculate.call_count,2)
        self.assertAlmostEqual(out['series'][0]['y'][0],72)
    def test_mixed_bonus_penalty_and_unity_preserve_original(self):
        self.fit=fit([module(strength=v) for v in (-60,20,0,-30)]);r=request();r['x']['range']=[0,0]
        expected=(1-maths.calculateMultiplier({'default':[(1+v/100,None) for v in (-60,20,0,-30)]}))*100
        self.assertEqual(self.sample(r)['series'][0]['y'],[expected])
    def test_module_overlap_and_nos_override(self):
        m=module(CONTRIBUTORS['neutStr'][0]);self.fit=fit([m]);r=request('neutStr');r['x']['range']=[0,0]
        self.assertEqual(live_contributions(self.fit,'neutStr',lambda:None),(4,4))
        self.assertEqual(self.sample(r)['series'][0]['y'],[18])
        old=m.getModifiedItemAttr;m.getModifiedItemAttr=lambda name:True if name=='nosOverride' else old(name)
        self.assertEqual(self.sample(r)['series'][0]['y'],[21])
    def test_before_materialization_authority_count_refusal(self):
        out=self.sample(prep_admit=lambda *args:[(0,0)])
        self.assertEqual(out['error']['code'],'resource_exhausted');self.assertNotIn('series',out)
    def test_whole_request_admission_precedes_prepare(self):
        calls=[];out=self.sample(reserve=EwarReservation(1),prepare_fit=lambda f:calls.append(f))
        self.assertEqual(out['error']['code'],'resource_exhausted');self.assertEqual(calls,[])
    def test_nonfinite_original_and_midpoint_overflow(self):
        with patch.object(maths,'calculateRangeFactor',return_value=math.inf):out=self.sample()
        self.assertEqual(out['error']['code'],'invalid_engine_data');self.assertNotIn('series',out)
        r=request();r['x']['range']=[1e305,1.1e305]
        with patch.object(maths,'calculateRangeFactor',side_effect=lambda **kw:kw['distance']/1e308):out=self.sample(r)
        self.assertEqual(out['error']['code'],'invalid_engine_data')
    def test_stale_missing_cancel_deadline_clock(self):
        def missing(k):raise KeyError(k)
        cases=[({'resolve_fit':missing},'fit_not_found'),({'resolve_fit':lambda k:(self.fit,2)},'stale_fit'),
            ({'current_context':lambda:dict(CONTEXT,generation=1)},'stale_context'),({'cancelled':lambda:True},'cancelled'),
            ({'clock':iter([0,10]).__next__},'deadline_exceeded'),({'clock':iter([1,0]).__next__},'clock_error'),
            ({'clock':lambda:math.nan},'clock_error')]
        for kw,code in cases:
            out=self.sample(**kw);self.assertEqual(out['error']['code'],code);self.assertNotIn('series',out)
    def test_same_revision_replacement_fails_publication(self):
        calls=[0]
        def resolve(k):
            calls[0]+=1
            return (self.fit if calls[0]<3 else fit(),1)
        out=self.sample(resolve_fit=resolve);self.assertEqual(out['error']['code'],'stale_fit')
    def test_settings_reset_nested_failure_and_recovery(self):
        with maths.graph_settings(False,True):
            self.assertTrue(self.sample()['ok']);self.assertFalse(maths.GraphSettings.getInstance()['ignoreLockRange'])
            def bad(f):raise RuntimeError('not exposed')
            out=self.sample(prepare_fit=bad);self.assertEqual(out['error']['code'],'engine_error')
            self.assertNotIn('not exposed',str(out));self.assertFalse(maths.GraphSettings.getInstance()['ignoreLockRange'])
        with self.assertRaises(LookupError):maths.GraphSettings.getInstance()
    def test_invalid_shape_types_identities_and_units(self):
        cases=[]
        for key,val in [('version',True),('version',1.0),('request_id',''),('request_id','x'*129),('request_id','\ud800'),
                        ('resistance_percent',False),('resistance_percent',math.inf),('ignore_lock_range',1),
                        ('ignore_drone_control_range',None),('budget_ms',0),('budget_ms',10001),('fits',[])]:
            r=request();r[key]=val;cases.append(r)
        for bounds in ([-1,0],[2,1],[0,math.nan],[0,math.inf],[0,1e308],[True,2]):
            r=request();r['x']['range']=bounds;cases.append(r)
        for val in (0,True,1.0,2**63):
            r=request();r['fits'][0]['revision']=val;cases.append(r)
        for val in (-1,True,1.0,2**63):
            r=request();r['context']['generation']=val;cases.append(r)
        for unit in ('null','%',0):
            r=request('neutStr');r['y']['unit']=unit;cases.append(r)
        r=request();r['fits']*=2;cases.append(r)
        r=request();r['extra']=0;cases.append(r)
        for r in cases:
            with self.subTest(r=r):
                out=self.sample(r);self.assertEqual(out['error']['code'],'invalid_request');self.assertNotIn('series',out)
    def test_generic_integer_beyond_long_is_finite_scalar(self):
        r=request();r['resistance_percent']=10**100
        out=self.sample(parse_request(json.dumps(r)));self.assertTrue(out['ok'],out)
        self.assertEqual(out['resistance_percent'],10**100);self.assertEqual(out['effective']['resistance_fraction'],1)
    def test_encoded_success_bound_and_encoding_failure(self):
        out=self.sample(encode=lambda value:json.dumps(value,ensure_ascii=True,allow_nan=False))
        value=json.loads(out);self.assertLessEqual(len(out),WIRE_HEADER_CHARS+WIRE_POINT_CHARS*value['total_points'])
        out=self.sample(encode=lambda value:'x'*(MAX_WIRE_CHARS+1))
        self.assertEqual(out['error']['code'],'invalid_engine_data')
    def test_encode_time_replacement_is_not_published(self):
        handle=[self.fit]
        def encode(value):
            handle[0]=fit()
            return json.dumps(value)
        out=self.sample(encode=encode,resolve_fit=lambda key:(handle[0],1))
        self.assertEqual(out['error']['code'],'stale_fit');self.assertNotIn('series',out)
    def test_callback_errors_are_static_bounded_and_recognized(self):
        for code in ('invalid_engine_data','unsupported_external_code'):
            def prep(*args):raise SamplingError(code,'secret'+'x'*2000)
            out=self.sample(prep_admit=prep)
            self.assertEqual(out['error']['code'],code if code=='invalid_engine_data' else 'engine_error')
            self.assertLessEqual(len(out['error']['message']),1024)
            self.assertNotIn('secret',out['error']['message'])


class ParseTests(unittest.TestCase):
    def test_duplicate_size_malformed_nonfinite_and_long_token(self):
        for value in (None,' '*16385,'{','{"a":1,"a":2}','[NaN]','[Infinity]', '['+'1'*311+']','[1e999]'):
            with self.subTest(value=str(value)[:32]),self.assertRaises(SamplingError):parse_request(value)
    def test_number_token_bound_applies_before_conversion(self):
        with patch('builtins.int',side_effect=AssertionError('conversion before guard')):
            with self.assertRaises(SamplingError):parse_request('['+'9'*311+']')
    def test_large_finite_integers_and_signed_zero(self):
        self.assertEqual(parse_request('['+'1'+'0'*308+']'),[10**308])
        self.assertEqual(math.copysign(1,parse_request('[-0.0]')[0]),-1)
        self.assertEqual(parse_request('[1e-999]'),[0.0])
    def test_surrogate_pair_identity_decodes_as_codepoint(self):
        r=request();r['request_id']='😀'*128
        self.assertEqual(parse_request(json.dumps(r))['request_id'],r['request_id'])


class SourceTests(unittest.TestCase):
    def test_original_math_ast_bodies_unchanged(self):
        candidate=ast.parse((ROOT/'android_bridge/offline/ewar_math.py').read_text())
        candidate={n.name:n for n in candidate.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
        sources={'graphs/data/base/getter.py':('PointGetter','SmoothPointGetter'),
                 'graphs/calc.py':('checkLockRange','checkDroneControlRange'),
                 'graphs/data/fitEwarStats/getter.py':tuple(cls.__name__ for unit,cls in MODES.values())}
        for path,names in sources.items():
            original=ast.parse((ROOT/path).read_text())
            for node in original.body:
                if getattr(node,'name',None) in names:
                    self.assertEqual(ast.dump(node,include_attributes=False),ast.dump(candidate[node.name],include_attributes=False),node.name)
    def test_pinned_original_source_hashes(self):
        hashes={'graphs/data/fitEwarStats/getter.py':'3271b4ddcf193f8cee72936d11a484077f78436daea1212a49960dac59e80431',
                'graphs/data/base/getter.py':'eff583fa7da3adb7a40e88e0e9c20a4270d8b6d58923d8ce03914d583eb75199',
                'eos/calc.py':'bb8ef6c32681e538c3c09b640c3541d67cba9fc73fc361bf1e0daa70e9ec7652'}
        for path,digest in hashes.items():self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)


if __name__=='__main__':unittest.main()
