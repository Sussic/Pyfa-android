"""Pure host time-axis source replay and admission tests, without EOS fits/DB."""
import ast
import hashlib
import itertools
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from android_bridge.contract import _json
from android_bridge.offline.remote_repair_samples import sample_remote_repair
from android_bridge.offline.remote_repair_time_math import (
    CheckedTimeCache, CheckedXTimeMixin, CheckedTime2RpsGetter,
    CheckedTime2RepAmountGetter)
from android_bridge.offline.remote_repair_time_output import TimeOutput, MAX_POINTS
from android_bridge.offline.remote_repair_resource import RepairReservation
from android_bridge.projected_drone_admission import AdmissionRejected
from test_remote_repair_selected_time import request, fit, Module, Drone, CONTEXT


def time_request(amount=False, bounds=(0, 3), distance=None):
    value = request(None)
    value['x'] = dict(quantity='time', unit='s', range=list(bounds))
    value['distance'] = distance
    if amount: value['y'] = dict(quantity='repair_amount', unit='HP')
    return value


class TimeAxisTests(unittest.TestCase):
    def sample(self, request=None, source=None, **kwargs):
        source = source or fit(Module(), (Drone(),))
        return sample_remote_repair(request or time_request(), resolve_fit=lambda k:(source,1),
                                   current_context=lambda:CONTEXT, clock=lambda:0, **kwargs)

    def test_both_modes_source_columns_and_encoding(self):
        for amount in (False, True):
            out = self.sample(time_request(amount))
            self.assertTrue(out['ok'], out)
            self.assertEqual(out['effective'], dict(x_range=[0,3],time=None,distance=None))
            self.assertEqual(out['series'][0]['source_rates'],dict(shield=3,armor=99,hull=2))
            text = self.sample(time_request(amount), encode=_json)
            self.assertIsInstance(text,str)
            self.assertEqual(json.loads(text),out)

    def test_empty_and_clamps(self):
        for amount in (False,True):
            for requested, effective, xs in (([-1,2501],[0,2500],[0,2500]),
                    ([-3,-1],[0,0],[0]),([2501,3000],[2500,2500],[2500,2500])):
                out = self.sample(time_request(amount,requested), source=fit())
                self.assertTrue(out['ok'],out)
                self.assertEqual(out['x']['range'],requested)
                self.assertEqual(out['effective']['x_range'],effective)
                self.assertEqual(out['series'][0]['x'],xs)

    def test_null_zero_range_distinct(self):
        source=fit(Module()); source.modules[0].maxRange=-1; source.modules[0].falloff=0
        for amount in (False,True):
            null=self.sample(time_request(amount,distance=None),source=source)
            zero=self.sample(time_request(amount,distance=0),source=source)
            self.assertTrue(null['ok'],null);self.assertTrue(zero['ok'],zero)
            self.assertNotEqual(null['series'][0]['y'],zero['series'][0]['y'])

    def test_invalid_before_preparation(self):
        cases=[]
        for amount in (False,True):
            for distance in (True,-1,float('inf'),float('nan'),'1',10**308):
                cases.append(time_request(amount,distance=distance))
            for bounds in ((1,0),(True,1),(0,float('inf')),('0',1)):
                cases.append(time_request(amount,bounds))
            r=time_request(amount);r['time']=0;cases.append(r)
            r=time_request(amount);r['x']['unit']='ms';cases.append(r)
        for r in cases:
            out=self.sample(r,prepare_fit=lambda f:self.fail('invalid preparation'))
            self.assertEqual(out['error']['code'],'invalid_request',out)

    def test_exact_pair_boundary_both_modes(self):
        for cls in (CheckedTime2RpsGetter,CheckedTime2RepAmountGetter):
            for digits, success in ((61,True),(62,False),(101,False)):
                value=10**(digits-1)
                with patch.object(cls,'_prepareTimeCache'), patch.object(cls,'_getTimeCacheData',return_value={0:value}), \
                     patch('android_bridge.offline.remote_repair_time_math.checked_apply_time',side_effect=lambda c,m,a:m):
                    out=self.sample(time_request(cls is CheckedTime2RepAmountGetter,(0,0)))
                self.assertEqual(out['ok'],success,out)
                if not success:self.assertEqual(out['error']['code'],'resource_exhausted');self.assertNotIn('series',out)

    def test_encoding_failure_cancellation_cleanup_and_recovery(self):
        for amount in (False,True):
            clean=[]; original=CheckedTimeCache.clearAll
            def clear(cache):
                original(cache);clean.append(not(cache._data or cache._schedules or cache._active))
            with patch.object(CheckedTimeCache,'clearAll',clear):
                out=self.sample(time_request(amount),encode=lambda r:'x'*100000)
            self.assertEqual(out['error']['code'],'resource_exhausted');self.assertEqual(clean,[True])
            cancel=[False]
            def encode(r):cancel[0]=True;return _json(r)
            out=self.sample(time_request(amount),encode=encode,cancelled=lambda:cancel[0])
            self.assertEqual(out['error']['code'],'cancelled')
            self.assertTrue(self.sample(time_request(amount))['ok'])

    def test_every_reservation_failure_complete(self):
        kinds=set()
        ledger=RepairReservation()
        self.assertTrue(self.sample(time_reserve=lambda k,n:(kinds.add(k),ledger(k,n)))['ok'])
        for kind in kinds:
            def reserve(k,n):
                if k==kind:raise AdmissionRejected('injected')
            out=self.sample(time_reserve=reserve)
            self.assertEqual(out['error']['code'],'resource_exhausted',(kind,out));self.assertNotIn('series',out)

    def test_native_actual_encoding_once_and_metres(self):
        from android_bridge.offline.native_session import NativeSession
        source=fit(Module());calls=[]
        fake=NS(graph=NS(_ready=lambda:None,_verify_durable=lambda:None),
                _fits={'fit':source},_revisions={'fit':1},context=lambda:CONTEXT,
                engine=NS(prepare_read=lambda f:None))
        for amount in (False,True):
            calls.clear()
            def encoder(value):calls.append(value);return _json(value)
            with patch('android_bridge.offline.native_session._json',side_effect=encoder):
                text=NativeSession.remote_repair_samples(fake,_json(time_request(amount,distance=12.5)))
            out=json.loads(text)
            self.assertTrue(out['ok'],out);self.assertEqual(len(calls),1)
            self.assertEqual(out['distance'],12.5);self.assertEqual(out['effective']['distance'],12500)

    def test_interruptions_during_sort_aggregate_append_and_encoding(self):
        for amount in (False,True):
            for target in ('sort_slot','rr_value','output_point','serialization_unit'):
                for mode in ('cancelled','deadline_exceeded','stale_context'):
                    interrupted=[False];seen=[0]
                    def reserve(kind,count):
                        if kind==target:
                            seen[0]+=1
                            if target!='serialization_unit' or seen[0]>2:interrupted[0]=True
                    kwargs={'cancelled':lambda:interrupted[0]} if mode=='cancelled' else {}
                    # Invoke sampler directly to override clock/context cleanly.
                    source=fit(Module())
                    out=sample_remote_repair(time_request(amount),resolve_fit=lambda k:(source,1),
                        current_context=lambda:({**CONTEXT,'generation':1} if mode=='stale_context' and interrupted[0] else CONTEXT),
                        clock=lambda:20 if mode=='deadline_exceeded' and interrupted[0] else 0,
                        time_reserve=reserve,**kwargs)
                    self.assertEqual(out['error']['code'],mode,(target,mode,out))
                    self.assertNotIn('series',out)

    def test_point_ceiling_before_append(self):
        output=TimeOutput(RepairReservation(),lambda:None);output.count=MAX_POINTS
        xs=[];ys=[]
        with self.assertRaises(AdmissionRejected):output.append(xs,ys,0,0)
        self.assertEqual((xs,ys),([],[]))


class OriginalTimeReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=Path(__file__).resolve().parents[5]/'cloud-source-receipts/pyfa/reconstructed-source/graphs/data/fitRemoteReps/getter.py'
        if not source.exists():raise unittest.SkipTest('Independent pinned source not available')
        assert hashlib.sha256(source.read_bytes()).hexdigest()=='6531618b3dc875602f1230b396bf6cf634a74aa58a27dad43bec62b21c0ff263'
        node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='XTimeMixin')
        scope={'PointGetter':object,'getApplicationPerKey':lambda **kw:{},'applyReps':lambda rrMap,applicationMap:rrMap}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),scope)
        cls.original=scope['XTimeMixin']

    def test_exhaustive_ordered_scalar_maps(self):
        cases=0
        for length in range(4):
            for times in itertools.combinations((0,1,3,6),length):
                for values in itertools.product((0,2,5),repeat=length):
                    data=dict(zip(times,values))
                    for low,high in ((0,0),(0,1),(0,3),(1,1),(1,3),(2,3),(6,6),(7,8)):
                        orig=self.original();orig._prepareTimeCache=lambda **kw:None;orig._getTimeCacheData=lambda **kw:data
                        expected=orig.getRange((low,high),{'ancReload':False,'distance':None},None,None)
                        reserve=RepairReservation();cache=NS(reserve=reserve)
                        candidate=CheckedXTimeMixin(NS(_timeCache=cache,_timeOutput=TimeOutput(reserve,lambda:None)))
                        candidate._prepareTimeCache=lambda **kw:None;candidate._getTimeCacheData=lambda **kw:data
                        with patch('android_bridge.offline.remote_repair_time_math.checked_application',return_value={}), \
                             patch('android_bridge.offline.remote_repair_time_math.checked_apply_time',side_effect=lambda c,m,a:m):
                            actual=candidate.getRange((low,high),{'ancReload':False,'distance':None},None,None)
                        self.assertEqual(actual,expected,(data,low,high));cases+=1
        self.assertEqual(cases,1400)


class ScalarApplicationTests(unittest.TestCase):
    def test_actual_identity_key_fast_path_exact_arithmetic(self):
        from eos.utils.stats import RRTypes
        from android_bridge.offline.remote_repair_time_math import checked_apply, checked_apply_time
        cache=NS(reserve=lambda *args:None)
        vectors=((0,0,0,0),(0.0,-0.0,0.0,-0.0),(1,2,3,4),
                 (1e20,1e-20,-1e20,1e100),(2**53+1,2**53-1,10**100,-10**100),
                 (1,2,3,float('inf')),(1,2,3,float('nan')))
        for vector in vectors:
            for factor in (0,1,0.0,1.0,-0.0,0.1):
                keys=[object(),object()]
                data={keys[0]:RRTypes(*vector),keys[1]:RRTypes(*vector)}
                application={key:factor for key in keys}
                expected=checked_apply(cache,data,application)
                with patch('android_bridge.offline.remote_repair_time_math.checked_apply',side_effect=AssertionError('unexpected fallback')):
                    actual=checked_apply_time(cache,data,application)
                self.assertIs(type(actual),type(expected))
                self.assertEqual(actual.hex() if type(actual) is float else actual,
                                 expected.hex() if type(expected) is float else expected)

    def test_subclass_fallback_no_extra_property_reads(self):
        from eos.utils.stats import RRTypes
        from android_bridge.offline.remote_repair_time_math import checked_apply, checked_apply_time
        reads=[]
        class Special(RRTypes):
            def __getattribute__(self,name):
                if name in ('shield','armor','hull','capacitor'):reads.append(name)
                return super().__getattribute__(name)
        key=object();value=Special(1,2,3,4);cache=NS(reserve=lambda *a:None)
        expected=checked_apply(cache,{key:value},{key:0.5});original_reads=reads[:];reads.clear()
        actual=checked_apply_time(cache,{key:value},{key:0.5})
        self.assertEqual(actual,expected);self.assertEqual(reads,original_reads)

    def test_custom_key_fallback_no_extra_hashes(self):
        from eos.utils.stats import RRTypes
        from android_bridge.offline.remote_repair_time_math import checked_apply, checked_apply_time
        calls=[]
        class Key:
            def __hash__(self):calls.append('hash');return 5
        key=Key();data={key:RRTypes(1,2,3,4)};application={key:0.5};cache=NS(reserve=lambda *a:None)
        calls.clear();expected=checked_apply(cache,data,application);old=calls[:]
        calls.clear();actual=checked_apply_time(cache,data,application)
        self.assertEqual(actual,expected);self.assertEqual(calls,old)

    def test_oversized_builtin_inputs_refuse_without_fallback(self):
        from eos.utils.stats import RRTypes
        from android_bridge.offline.remote_repair_time_math import checked_apply_time
        cache=NS(reserve=lambda *a:None);key=object()
        for data,application in (({key:RRTypes(1<<1024,0,0,0)},{key:1}),
                                 ({key:RRTypes(1,0,0,0)},{key:1<<1024})):
            with patch('android_bridge.offline.remote_repair_time_math.checked_apply',side_effect=AssertionError('unbounded fallback')):
                with self.assertRaises(AdmissionRejected):checked_apply_time(cache,data,application)
        value=(1<<1024)-1
        out=checked_apply_time(cache,{key:RRTypes(value,value,value,value)},{key:value})
        self.assertEqual(out,3*value*value)

    def test_fixed_workspace_charge_and_no_rr_in_fast_apply(self):
        from collections import Counter
        from eos.utils.stats import RRTypes
        from android_bridge.offline.remote_repair_time_math import checked_apply_time
        counts=Counter();cache=NS(reserve=lambda k,n:counts.update({k:n}));key=object()
        checked_apply_time(cache,{key:RRTypes(1,2,3,4)},{key:1})
        self.assertEqual(set(counts),{'scan'})
        counts.clear();source=fit(Module())
        out=sample_remote_repair(time_request(),resolve_fit=lambda k:(source,1),current_context=lambda:CONTEXT,
                                 clock=lambda:0,time_reserve=lambda k,n:counts.update({k:n}))
        self.assertTrue(out['ok'],out)
        self.assertEqual(counts['output_slot'],84+2*out['total_points'])
