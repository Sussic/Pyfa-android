"""G07 boundary checks and real EOS durable-session regression."""
import json
import math
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from test_native_session import NativeSessionTests
from android_bridge.offline.mobility_samples import sample_mobility, MODES
CONTEXT=dict(session_id='mobility',dataset_sha256='a'*64,generation=0)
def request(mode='speed'):
    return dict(version=1,request_id='mobility-test',context=deepcopy(CONTEXT),fits=[dict(fit_id='fit',revision=0)],
                x=dict(quantity='time',unit='s',range=[0,30]),y=dict(quantity=mode,unit=MODES[mode][0]),
                target_mass_mkg=1300 if mode.startswith('bump') else None,
                target_inertia=.015 if mode=='bumpDistance' else None,resolution=200,budget_ms=10000)
class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.attrs=dict(maxVelocity=300,mass=1e6,agility=.4)
        self.fit=SimpleNamespace(ship=SimpleNamespace(getModifiedItemAttr=lambda k:self.attrs[k]),alignTime=1.0)
    def sample(self,r=None,**kw):
        args=dict(resolve_fit=lambda k:(self.fit,0),current_context=lambda:CONTEXT,clock=lambda:0);args.update(kw)
        return sample_mobility(request() if r is None else r,**args)
    def test_all_modes_units_and_grid(self):
        for mode in MODES:
            out=self.sample(request(mode));self.assertTrue(out['ok'],out);row=out['series'][0]
            self.assertEqual(row['x'],[.15*i for i in range(201)]);self.assertEqual(row['y'][0],0)
            self.assertEqual(row['max_velocity_mps'],300);self.assertEqual(row['align_time_s'],1)
            self.assertEqual(out['y']['unit'],MODES[mode][0]);self.assertGreater(row['y'][-1],0)
    def test_zero_target_mass_and_inertia_are_valid_source_inputs(self):
        r=request('bumpDistance');r['target_mass_mkg']=0;r['target_inertia']=0
        out=self.sample(r);self.assertTrue(out['ok'],out);self.assertEqual(set(out['series'][0]['y']),{0})
    def test_singleton_and_underflow_grid(self):
        for bounds in ([5,5],[0,math.nextafter(0,1)]):
            r=request();r['x']['range']=bounds;out=self.sample(r)
            self.assertTrue(out['ok'],out);self.assertEqual(out['total_points'],1)
    def test_invalid_requests(self):
        cases=[]
        for key,value in [('version',True),('resolution',0),('resolution',1025),('budget_ms',10001),('fits',[]),('target_mass_mkg',1),('target_inertia',1)]:
            r=request();r[key]=value;cases.append(r)
        for bounds in ([-1,30],[30,0],[0,float('nan')],[0,float('inf')]):
            r=request();r['x']['range']=bounds;cases.append(r)
        for key,value in [('target_mass_mkg',None),('target_mass_mkg',-1),('target_mass_mkg',1e308),('target_inertia',True)]:
            r=request('bumpDistance');r[key]=value;cases.append(r)
        r=request();r['fits']*=2;cases.append(r)
        r=request();r['y']['unit']='km';cases.append(r)
        for r in cases:
            with self.subTest(r=r):
                out=self.sample(r);self.assertFalse(out['ok']);self.assertNotIn('series',out)
    def test_invalid_source_data_and_overflow_return_no_curve(self):
        for key,value in [('mass',0),('agility',0),('mass',None),('maxVelocity',float('nan')),('agility',-1)]:
            old=self.attrs[key];self.attrs[key]=value;out=self.sample();self.attrs[key]=old
            self.assertEqual(out['error']['code'],'invalid_engine_data');self.assertNotIn('series',out)
        r=request('distance');r['x']['range']=[0,1e308]
        out=self.sample(r);self.assertFalse(out['ok']);self.assertNotIn('series',out)
    def test_cancel_budget_stale_and_replaced(self):
        for kw,code in [({'cancelled':lambda:True},'cancelled'),({'clock':iter([0,10]).__next__},'deadline_exceeded'),
                        ({'resolve_fit':lambda k:(self.fit,1)},'stale_fit'),({'current_context':lambda:dict(CONTEXT,generation=1)},'stale_context')]:
            out=self.sample(**kw);self.assertEqual(out['error']['code'],code);self.assertNotIn('series',out)
        handles=iter([self.fit,deepcopy(self.fit)])
        self.assertEqual(self.sample(resolve_fit=lambda k:(next(handles),0))['error']['code'],'stale_fit')
    def test_bounded_maximum(self):
        r=request();r['resolution']=1024;r['fits']=[dict(fit_id=str(i),revision=0) for i in range(8)]
        self.assertEqual(self.sample(r)['total_points'],8200)
class SessionTests(NativeSessionTests):
    def mobility_request(self,mode='speed'):
        r=request(mode);r['context']=self.session.context();r['fits']=[dict(fit_id=self.key,revision=self.session._revisions[self.key])];return r
    def sample(self,r=None):return json.loads(self.session.mobility_samples(json.dumps(self.mobility_request() if r is None else r)))
    def test_real_modes_readonly_and_restart(self):
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history_details(self.key)
        results={}
        for mode in MODES:
            out=self.sample(self.mobility_request(mode));self.assertTrue(out['ok'],out);results[mode]=out['series'][0]['y']
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph.snapshot());self.assertEqual(history,self.session.history_details(self.key))
        old=self.mobility_request();self.reopen();self.assertFalse(self.sample(old)['ok'])
        for mode in MODES:self.assertEqual(results[mode],self.sample(self.mobility_request(mode))['series'][0]['y'])
    def test_profile_edit_stales_and_recalculates(self):
        r=self.mobility_request();old=self.sample()['series'][0]['y']
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        self.assertEqual(self.sample(r)['error']['code'],'stale_context');self.assertNotEqual(old,self.sample()['series'][0]['y'])
    def test_transport_and_durable_validation(self):
        self.assertFalse(json.loads(self.session.mobility_samples('{"version":1,"version":1}'))['ok'])
        self.assertFalse(json.loads(self.session.mobility_samples(' '*16385))['ok'])
        with patch.object(self.session.graph,'_verify_durable',side_effect=RuntimeError('injected')):
            out=self.sample();self.assertFalse(out['ok']);self.assertNotIn('series',out)
def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(BoundaryTests)
    for name in SessionTests.__dict__:
        if name.startswith('test_'):suite.addTest(SessionTests(name))
    return suite
