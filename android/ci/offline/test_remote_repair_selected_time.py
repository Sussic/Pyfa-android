"""Pure G05.2a schedule, allocation and complete-wire tests (no DB)."""
import math
import unittest
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import patch
from eos.utils.cycles import CycleInfo, CycleSequence
from eos.utils.stats import RRTypes
from android_bridge.projected_drone_admission import AdmissionRejected
from android_bridge.offline.remote_repair_schedule import capture_schedule, reconstruct_schedule
from android_bridge.offline.remote_repair_time_math import CheckedTimeCache
from android_bridge.offline.remote_repair_samples import sample_remote_repair

CONTEXT = dict(session_id='selected', dataset_sha256='a'*64, generation=0)

class Module:
    def __init__(self, ancillary=False):
        self.item = NS(effects={'shipModuleAncillaryRemoteArmorRepairer'} if ancillary else set())
        self.schedule = CycleInfo(1000, 0, math.inf, False)
        self.numShots = 2
        self.charge = True
        self.maxRange = 10000
        self.falloff = 10000
        self.calls = []
    def isRemoteRepping(self): return True
    def getCycleParameters(self, reloadOverride=None):
        self.calls.append(reloadOverride)
        return self.schedule
    def getRepAmountParameters(self, spoolOptions=None):
        return {1000: RRTypes(0, 12, 0, 0)}
    def getModifiedItemAttr(self, name, default=0): return 3 if name == 'chargedArmorDamageMultiplier' else default
    def getRemoteReps(self, **kwargs): return RRTypes(0, 99, 0, 0)

class Drone:
    def __init__(self): self.schedule = CycleInfo(1000,0,math.inf,False)
    def isRemoteRepping(self): return True
    def getCycleParameters(self, reloadOverride=None): return self.schedule
    def getRepAmountParameters(self): return {0: RRTypes(3,0,0,0),1000:RRTypes(0,0,2,0)}
    def getRemoteReps(self): return RRTypes(3,0,2,0)

def fit(module=None, drones=()):
    modules=[] if module is None else [module]
    return NS(ID=1, modules=modules, drones=list(drones), maxTargetRange=50000,
              extraAttributes={'droneControlRange':50000}, activeModulesIter=lambda:iter(modules),
              activeDronesIter=lambda:iter(drones), getRemoteReps=lambda **kw:RRTypes(3,99,2,0))

def request(time=2):
    return dict(version=2,request_id='selected-test',context=deepcopy(CONTEXT),fits=[dict(fit_id='fit',revision=1)],
                x=dict(quantity='distance',unit='km',range=[0,0]),y=dict(quantity='repair_rate',unit='HP/s'),
                time=time,distance=None,ancillary_reload=False,ignore_lock_range=True,
                ignore_drone_control_range=True,budget_ms=10000)

class SelectedTimeTests(unittest.TestCase):
    def sample(self, r=None, source=None, reserve=None, **kwargs):
        source=source or fit(Module())
        return sample_remote_repair(request() if r is None else r,resolve_fit=lambda k:(source,1),
            current_context=lambda:CONTEXT,clock=lambda:0,time_reserve=reserve,**kwargs)
    def test_default_policy_and_null_time(self):
        out=self.sample();self.assertTrue(out['ok'],out);self.assertEqual(out['version'],2)
        out=self.sample(request(None));self.assertTrue(out['ok'],out);self.assertIsNone(out['effective']['time'])
    def test_requested_effective_and_current_columns(self):
        for requested,effective in ((-4,0),(0,0),(2,2),(3000,2500)):
            out=self.sample(request(requested),reserve=lambda *a:None)
            self.assertTrue(out['ok'],out);self.assertEqual(out['time'],requested);self.assertEqual(out['effective']['time'],effective)
            self.assertEqual(out['series'][0]['source_rates'],dict(shield=3,armor=99,hull=2))
            self.assertEqual(out['series'][0]['y'],[12])
    def test_original_ancillary_no_reload_depletion(self):
        source=fit(Module(True))
        for t,expected in ((0,12),(1,12),(2,4),(4,4)):
            out=self.sample(request(t),source=source,reserve=lambda *a:None)
            self.assertTrue(out['ok'],out);self.assertEqual(out['series'][0]['y'],[expected])
        self.assertEqual(source.modules[0].calls,[False]*4)
        source=fit(Module());self.sample(source=source,reserve=lambda *a:None)
        self.assertEqual(source.modules[0].calls,[True])
    def test_exact_invalid_versions_modes_and_values(self):
        for key,value in [('time',True),('time',float('nan')),('time',float('inf')),('distance',0),('extra',1),('y',dict(quantity='repair_amount',unit='HP/s')),('x',dict(quantity='time',unit='s',range=[0,1]))]:
            r=request();r[key]=value;out=self.sample(r,reserve=lambda *a:None)
            self.assertEqual(out['version'],2);self.assertEqual(out['error']['code'],'invalid_request');self.assertNotIn('series',out)
        for version in (True,2.0,3,None):
            r=request();r['version']=version;out=self.sample(r,reserve=lambda *a:None)
            self.assertEqual(out['version'],1);self.assertFalse(out['ok'])
    def test_fail_each_allocation_kind_and_discard(self):
        events=Counter()
        def reserve(kind,count): events[kind]+=count
        source=fit(Module(True),(Drone(),))
        self.assertTrue(self.sample(source=source,reserve=reserve)['ok'])
        original=CheckedTimeCache.clearAll
        cleared=[]
        def clear(cache):
            original(cache);cleared.append((len(cache._data),len(cache._schedules),len(cache._active)))
        for target in events:
            def reject(kind,count):
                if kind==target: raise AdmissionRejected('Injected '+target)
            with patch.object(CheckedTimeCache,'clearAll',clear):
                out=self.sample(source=source,reserve=reject)
            self.assertEqual(out['error']['code'],'resource_exhausted',(target,out));self.assertNotIn('series',out)
        self.assertTrue(cleared);self.assertEqual(set(cleared),{(0,0,0)})
    def test_cancel_each_allocation_phase(self):
        for target in ('cycle','copy_slot','sort_slot','output_point','output_slot'):
            cancel=[False]
            def reserve(kind,count):
                if kind==target:cancel[0]=True
            out=self.sample(source=fit(Module(True),(Drone(),)),reserve=reserve,cancelled=lambda:cancel[0])
            self.assertEqual(out['error']['code'],'cancelled',(target,out));self.assertNotIn('series',out)
    def test_snapshot_mutation_cannot_change_execution(self):
        source=fit(Module())
        def reserve(kind,count):
            if kind=='schedule_clone':source.modules[0].schedule.activeTime=0
        out=self.sample(source=source,reserve=reserve)
        self.assertTrue(out['ok'],out);self.assertEqual(out['series'][0]['y'],[12])
    def test_capacitor_work_without_hp_and_event_overwrites(self):
        module=Module();module.getRepAmountParameters=lambda **kw:{1000:RRTypes(0,0,0,20)}
        events=Counter()
        out=self.sample(source=fit(module),reserve=lambda k,n:events.update({k:n}))
        self.assertTrue(out['ok'],out);self.assertEqual(out['series'][0]['y'],[0]);self.assertEqual(events['cycle'],4)
    def test_multi_fit_late_failure_is_whole_request(self):
        r=request();r['fits']=[dict(fit_id='a',revision=1),dict(fit_id='b',revision=1)]
        cycles=[0]
        def reserve(k,n):
            if k=='cycle':
                cycles[0]+=n
                if cycles[0]>4:raise AdmissionRejected('second fit')
        out=self.sample(r,reserve=reserve);self.assertEqual(out['error']['code'],'resource_exhausted');self.assertNotIn('series',out)

class ScheduleTests(unittest.TestCase):
    def capture(self,s):return capture_schedule(s,10,lambda:None,lambda *a:None)
    def test_original_clone_exact_finite_stream_and_fractional_quantity(self):
        for root in (CycleInfo(1000,2,2.5,False),CycleSequence([CycleInfo(3,1,2,False),CycleInfo(4,5,1,True)],2.5)):
            frozen,bound=self.capture(root);clone=reconstruct_schedule(frozen,lambda:None,lambda *a:None)
            self.assertEqual(list(root.iterCycles()),list(clone.iterCycles()));self.assertEqual(bound,len(list(root.iterCycles())))
    def test_reject_nonadvancing_empty_unreachable_unknown_boolean(self):
        roots=[CycleInfo(0,1,math.inf,False),CycleInfo(1,-1,1,False),CycleInfo(1,0,0,False),CycleInfo(1e-300,0,math.inf,False),CycleInfo(True,0,1,False),CycleSequence([],1),CycleSequence([CycleInfo(1,0,math.inf,False),CycleInfo(1,0,1,False)],1)]
        for root in roots:
            with self.assertRaises(AdmissionRejected):self.capture(root)
    def test_accounting_overflow(self):
        c=CheckedTimeCache(lambda:None,lambda *a:None)
        with self.assertRaises(AdmissionRejected):c.reserve('test',2**63)
        with self.assertRaises(AdmissionRejected):c.reserve('test',True)


class SessionEnvelopeTests(unittest.TestCase):
    def test_v2_readiness_and_store_uncertainty_correlation(self):
        import json
        from android_bridge.offline.native_session import NativeSession
        from android_bridge.offline.profiles import ProfileError
        from android_bridge.offline.profile_store import StoreUncertain
        for failure in (ProfileError('reopen_required','Reopen'),StoreUncertain('uncertain')):
            for stage in ('_ready','_verify_durable'):
                def bad():raise failure
                disabled=[]
                fake=NS(graph=NS(_ready=bad if stage=='_ready' else lambda:None,
                               _verify_durable=bad if stage=='_verify_durable' else lambda:None),
                        _disable=lambda:disabled.append(True))
                out=json.loads(NativeSession.remote_repair_samples(fake,json.dumps(request())))
                self.assertEqual(out['version'],2);self.assertEqual(out['request_id'],'selected-test')
                self.assertEqual(out['error']['code'],'reopen_required');self.assertNotIn('series',out)
                self.assertEqual(bool(disabled),isinstance(failure,StoreUncertain))
    def test_malformed_and_v1_failure_keep_legacy_version(self):
        import json
        from android_bridge.offline.native_session import NativeSession
        from android_bridge.offline.profiles import ProfileError
        def bad():raise ProfileError('reopen_required','Reopen')
        fake=NS(graph=NS(_ready=bad))
        for text in ('{',' '*16385,'{"version":2,"version":2}',json.dumps(dict(request(),version=True)),json.dumps(dict(request(),version=1))):
            out=json.loads(NativeSession.remote_repair_samples(fake,text))
            self.assertEqual(out['version'],1);self.assertIsNone(out['request_id']);self.assertEqual(out['error']['code'],'reopen_required')

class ReservationTests(unittest.TestCase):
    def test_unknown_overflow_boolean_and_small_allowance(self):
        from android_bridge.offline.remote_repair_resource import RepairReservation
        for kind,count in (('unknown',1),('cycle',True),('cycle',-1),('cycle',2**63),('cycle',2**62)):
            with self.assertRaises(AdmissionRejected):RepairReservation()(kind,count)
        ledger=RepairReservation(128);ledger('container',1)
        with self.assertRaises(AdmissionRejected):ledger('container',1)
        self.assertEqual(ledger.used,128)
    def test_tiny_budget_returns_complete_error(self):
        from android_bridge.offline.remote_repair_resource import RepairReservation
        out=SelectedTimeTests().sample(reserve=RepairReservation(1))
        self.assertFalse(out['ok']);self.assertEqual(out['error']['code'],'resource_exhausted');self.assertNotIn('series',out)

class OriginalCacheTests(unittest.TestCase):
    @staticmethod
    def original():
        import ast
        from pathlib import Path
        from copy import copy
        from eos.utils.float import floatUnerr
        from eos.utils.spoolSupport import SpoolOptions, SpoolType
        source=Path(__file__).resolve().parents[3]/'graphs/data/fitRemoteReps/cache.py'
        node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='TimeCache')
        class Base:
            def __init__(self):self._data={}
        scope=dict(FitDataCache=Base,copy=copy,floatUnerr=floatUnerr,SpoolOptions=SpoolOptions,SpoolType=SpoolType,RRTypes=RRTypes)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),scope)
        return scope['TimeCache']()
    def test_ordered_source_internal_and_final_maps(self):
        for ancillary in (False,True):
            for horizon in (0,0.9999999999999999,1,2,3,10):
                module=Module(ancillary)
                module.schedule=CycleSequence([CycleInfo(1000,0,2,False),CycleInfo(1000,2000,1,True)],math.inf)
                source=NS(item=fit(module,(Drone(),)))
                original=self.original();candidate=CheckedTimeCache(lambda:None,lambda *a:None)
                for cache in (original,candidate):cache._generateInternalForm(source,False,horizon)
                self.assertEqual(original._data,candidate._data)
                for cache in (original,candidate):
                    cache.prepareRpsData(source,False,horizon)
                    cache.prepareRepAmountData(source,False,horizon)
                self.assertEqual(list(original.getRpsData(source,False)),list(candidate.getRpsData(source,False)))
                self.assertEqual(original._data,candidate._data)
                for time in (0,1,2,horizon):
                    self.assertEqual(original.getRpsDataPoint(source,False,time),candidate.getRpsDataPoint(source,False,time))
                    self.assertEqual(original.getRepAmountDataPoint(source,False,time),candidate.getRepAmountDataPoint(source,False,time))
                candidate.clearAll();self.assertFalse(candidate._data)
    def test_source_overwrite_and_post_horizon_cycle(self):
        module=Module()
        module.getRepAmountParameters=lambda **kwargs:{1000:RRTypes(0,12,0,0)}
        source=NS(item=fit(module))
        cache=CheckedTimeCache(lambda:None,lambda *a:None)
        cache._generateInternalForm(source,False,2)
        internal=cache._data[1][False]
        self.assertEqual([a for a,b,r in internal['internalRps'][module]],[0,1,2,3])
        self.assertEqual(list(internal['internalRepAmount'][module]),[1,2,3,4])

if __name__=='__main__':unittest.main()
