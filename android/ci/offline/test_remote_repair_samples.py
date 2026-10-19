"""G05.1 protocol, cancellation, preparation and isolated settings checks."""
import ast
import json
import math
from pathlib import Path
import unittest
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import patch
from android_bridge.offline.remote_repair_samples import sample_remote_repair
from android_bridge.offline.remote_repair_math import GraphSettings, graph_settings, CurrentRateCache
from eos.utils.stats import RRTypes

CONTEXT=dict(session_id='repair',dataset_sha256='a'*64,generation=0)
def request():
    return dict(version=1,request_id='repair-test',context=deepcopy(CONTEXT),fits=[dict(fit_id='fit',revision=1)],
                x=dict(quantity='distance',unit='km',range=[0,100]),y=dict(quantity='repair_rate',unit='HP/s'),
                time=None,ancillary_reload=True,ignore_lock_range=True,ignore_drone_control_range=False,budget_ms=10000)

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.drone=NS()
        class Drone:
            def isRemoteRepping(self): return True
            def getRemoteReps(self): return RRTypes(10,5,2,100)
        self.drone=Drone()
        self.fit=NS(maxTargetRange=20000,extraAttributes={'droneControlRange':40000},
                    activeModulesIter=lambda:iter(()),activeDronesIter=lambda:iter((self.drone,)),
                    getRemoteReps=lambda **kw:RRTypes(10,5,2,100))
    def sample(self,r=None,**kw):
        args=dict(resolve_fit=lambda key:(self.fit,1),current_context=lambda:CONTEXT,clock=lambda:0)
        args.update(kw)
        return sample_remote_repair(request() if r is None else r,**args)
    def test_source_layers_capacitor_exclusion_and_range_options(self):
        out=self.sample();self.assertTrue(out['ok'],out);s=out['series'][0]
        self.assertEqual(s['source_rates'],dict(shield=10,armor=5,hull=2))
        self.assertEqual(s['y'][0],17);self.assertEqual(s['y'][-1],0)
        r=request();r['ignore_drone_control_range']=True
        out=self.sample(r);self.assertEqual(set(out['series'][0]['y']),{17});self.assertEqual(out['total_points'],51)
        r['ignore_lock_range']=False
        out=self.sample(r);self.assertEqual(out['series'][0]['y'][-1],0)
    def test_prepare_local_has_causal_lock_range_effect(self):
        r=request();r['ignore_lock_range']=False;r['ignore_drone_control_range']=True;r['x']['range']=[30,30]
        self.assertEqual(self.sample(r)['series'][0]['y'],[0])
        def prepare(fit):fit.maxTargetRange=50000
        self.assertEqual(self.sample(r,prepare_fit=prepare)['series'][0]['y'],[17])
    def test_singleton_and_adjacent_rounded_coordinates(self):
        for bounds in ([5,5],[0,math.nextafter(0,1)/1000]):
            r=request();r['x']['range']=bounds;out=self.sample(r)
            self.assertTrue(out['ok'],out);self.assertEqual(out['total_points'],1)
        r=request();r['x']['range']=[1e9,math.nextafter(1e9,math.inf)]
        out=self.sample(r);self.assertTrue(out['ok'],out);self.assertEqual(out['total_points'],51)
        self.assertLess(len(set(out['series'][0]['x'])),51)
    def test_max_fits_and_full_original_adaptive_ceiling(self):
        r=request();r['fits']=[dict(fit_id=str(i),revision=1) for i in range(8)]
        with patch('android_bridge.offline.remote_repair_math.getApplicationPerKey',side_effect=lambda src,distance:{self.drone:distance}):
            out=self.sample(r)
        self.assertTrue(out['ok'],out);self.assertEqual(out['total_points'],1608)
    def test_invalid_requests(self):
        cases=[]
        for key,value in [('version',True),('time',0),('ancillary_reload',1),('ignore_lock_range',None),('ignore_drone_control_range','false'),('budget_ms',0),('fits',[])]:
            r=request();r[key]=value;cases.append(r)
        for bounds in ([-1,1],[3,2],[0,float('nan')],[0,float('inf')],[0,1e308]):
            r=request();r['x']['range']=bounds;cases.append(r)
        r=request();r['fits']*=2;cases.append(r)
        r=request();r['fits'][0]['revision']=0;cases.append(r)
        r=request();r['resolution']=50;cases.append(r)
        for r in cases:
            with self.subTest(r=r):
                out=self.sample(r);self.assertEqual(out['error']['code'],'invalid_request');self.assertNotIn('series',out)
    def test_cancellation_deadline_clock_stale_and_replacement(self):
        for kw,code in [({'cancelled':lambda:True},'cancelled'),({'clock':iter([0,10]).__next__},'deadline_exceeded'),
                        ({'clock':iter([1,0]).__next__},'clock_error'),({'clock':lambda:float('nan')},'clock_error'),
                        ({'resolve_fit':lambda k:(self.fit,2)},'stale_fit'),({'current_context':lambda:dict(CONTEXT,generation=1)},'stale_context')]:
            out=self.sample(**kw);self.assertEqual(out['error']['code'],code);self.assertNotIn('series',out)
        def missing(key):raise KeyError(key)
        self.assertEqual(self.sample(resolve_fit=missing)['error']['code'],'fit_not_found')
        handles=iter([self.fit,deepcopy(self.fit)])
        self.assertEqual(self.sample(resolve_fit=lambda k:(next(handles),1))['error']['code'],'stale_fit')
    def test_midpoint_overflow_is_error_without_partial_samples(self):
        r=request();r['x']['range']=[1e305,1.1e305]
        with patch('android_bridge.offline.remote_repair_math.getApplicationPerKey',side_effect=lambda src,distance:{self.drone:distance/1e308}):
            out=self.sample(r)
        self.assertEqual(out['error']['code'],'invalid_engine_data');self.assertNotIn('series',out)
    def test_cancel_and_deadline_during_refinement_drop_all_series(self):
        for mode in ('cancel','deadline'):
            calls=[]
            def application(src,distance):
                calls.append(distance)
                return {self.drone:distance}
            kw={'cancelled':lambda:len(calls)>=4} if mode=='cancel' else {'clock':lambda:10 if len(calls)>=4 else 0}
            with patch('android_bridge.offline.remote_repair_math.getApplicationPerKey',side_effect=application):
                out=self.sample(**kw)
            self.assertEqual(out['error']['code'],'cancelled' if mode=='cancel' else 'deadline_exceeded')
            self.assertEqual(len(calls),4);self.assertNotIn('series',out)
            # Fourth calculation is an adaptive quarter, not a pre-start refusal.
            self.assertEqual(calls,[0,2000,1000,500])
            with self.assertRaises(LookupError):GraphSettings.getInstance()

    def test_invalid_source_rate_or_curve(self):
        self.fit.getRemoteReps=lambda **kw:RRTypes(float('nan'),0,0,0)
        self.assertEqual(self.sample()['error']['code'],'invalid_engine_data')
    def test_settings_missing_nested_and_error_cleanup(self):
        with self.assertRaises(LookupError):GraphSettings.getInstance()
        with graph_settings(False,True):
            self.assertEqual(GraphSettings.getInstance(),dict(ignoreLockRange=False,ignoreDCR=True))
            self.assertTrue(self.sample()['ok'])
            self.assertFalse(GraphSettings.getInstance()['ignoreLockRange'])
            def bad(fit):raise RuntimeError('injected')
            self.assertEqual(self.sample(prepare_fit=bad)['error']['code'],'engine_error')
            self.assertFalse(GraphSettings.getInstance()['ignoreLockRange'])
        with self.assertRaises(LookupError):GraphSettings.getInstance()
        with self.assertRaises(ValueError):
            with graph_settings(1,False):pass
    def test_null_time_cache_is_exact_and_fail_closed(self):
        self.assertIs(CurrentRateCache().prepareRpsData(None,True,None),True)
        for t in (0,1,False):
            with self.assertRaises(ValueError):CurrentRateCache().prepareRpsData(None,True,t)

class EnvelopeTests(unittest.TestCase):
    def test_malformed_and_oversized_envelopes(self):
        from android_bridge.offline.native_session import NativeSession
        fake=NS(graph=NS(_ready=lambda:None))
        for text in (None, ' '*16385, '{"version":1,"version":1}', '{'):
            out=json.loads(NativeSession.remote_repair_samples(fake,text))
            self.assertFalse(out['ok']); self.assertNotIn('series',out)
            self.assertEqual(out['error']['code'],'invalid_request')

# Real durable integration cases are selected explicitly by load_tests.
from test_native_session import NativeSessionTests
class SessionTests(NativeSessionTests):
    def sample_request(self):
        r=request();r['context']=self.session.context()
        r['fits']=[dict(fit_id=self.key,revision=self.session._revisions[self.key])]
        return r
    def sample(self,r=None):
        return json.loads(self.session.remote_repair_samples(json.dumps(self.sample_request() if r is None else r)))
    def test_empty_fit_readonly_restart_and_stale_identity(self):
        before=self.path.read_bytes();graph=self.session.graph.snapshot();history=self.session.history_details(self.key)
        old=self.sample_request();out=self.sample(old);self.assertTrue(out['ok'],out)
        self.assertEqual(set(out['series'][0]['y']),{0});self.assertEqual(out['total_points'],51)
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(graph,self.session.graph.snapshot())
        self.assertEqual(history,self.session.history_details(self.key))
        self.reopen();self.assertEqual(self.sample(old)['error']['code'],'stale_context')
        self.assertEqual(out['series'],self.sample()['series'])
    def test_durable_failure_no_partial_and_cancel_has_no_mutation(self):
        before=self.path.read_bytes();r=json.dumps(self.sample_request())
        out=json.loads(self.session.remote_repair_samples(r,cancelled=lambda:True))
        self.assertEqual(out['error']['code'],'cancelled');self.assertEqual(before,self.path.read_bytes())
        with patch.object(self.session.graph,'_verify_durable',side_effect=RuntimeError('injected')):
            out=self.sample();self.assertFalse(out['ok']);self.assertNotIn('series',out)
        self.assertEqual(before,self.path.read_bytes())
    def test_projected_drone_admission_preserved_without_simulation(self):
        from eos.capSim import CapSimulator
        from eos.saveddata.fit import Fit
        item=self.engine._item('Warrior SW-300').ID
        self.edit('add_projected_drone',dict(fit_id=self.key,item_id=item))
        before=self.path.read_bytes();history=self.session.history_details(self.key)
        resets=[];drains=[];original_reset=CapSimulator.reset;original_drain=Fit._Fit__generateDrain
        def reset(obj,*a,**kw):resets.append(True);return original_reset(obj,*a,**kw)
        def drain(obj,*a,**kw):drains.append(True);return original_drain(obj,*a,**kw)
        with patch.object(CapSimulator,'reset',reset), patch.object(Fit,'_Fit__generateDrain',drain), \
             patch.object(CapSimulator,'run',side_effect=AssertionError('No graph capacitor simulation')), \
             patch.object(Fit,'getCapSimData',side_effect=AssertionError('No graph capacitor result')):
            out=self.sample()
        self.assertTrue(out['ok'],out);self.assertTrue(resets);self.assertTrue(drains)
        self.assertEqual(set(out['series'][0]['y']),{0})
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(history,self.session.history_details(self.key))

    def test_profile_edit_and_history_invalidate_old_request(self):
        old=self.sample_request()
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        self.assertEqual(self.sample(old)['error']['code'],'stale_context')
        before=self.path.read_bytes();history=self.session.history_details(self.key)
        self.assertTrue(self.sample()['ok']);self.assertEqual(before,self.path.read_bytes())
        self.assertEqual(history,self.session.history_details(self.key))
        self.edit('undo',dict(fit_id=self.key));self.assertTrue(self.sample()['ok'])
        self.edit('redo',dict(fit_id=self.key));self.assertTrue(self.sample()['ok'])

def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(BoundaryTests)
    suite.addTests(loader.loadTestsFromTestCase(EnvelopeTests))
    for name in SessionTests.__dict__:
        if name.startswith('test_'):suite.addTest(SessionTests(name))
    return suite

if __name__=='__main__':unittest.main()
