"""G06 strict boundary and real EOS read-only session regression tests."""
import json
import math
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from test_native_session import NativeSessionTests
from android_bridge.offline.locktime_samples import sample_locktime

CONTEXT=dict(session_id='session',dataset_sha256='a'*64,generation=0)
def request():
    return dict(version=1,request_id='lock-test',context=deepcopy(CONTEXT),fits=[dict(fit_id='fit',revision=0)],
                x=dict(quantity='signature_radius',unit='m',range=[25,500]),
                y=dict(quantity='lock_time',unit='s'),resolution=200,budget_ms=10000)

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fit=SimpleNamespace(ship=SimpleNamespace(getModifiedItemAttr=lambda key:100),calculateLockTime=lambda radius:100/radius)
    def run_sample(self,r=None,**kw):
        args=dict(resolve_fit=lambda key:(self.fit,0),current_context=lambda:CONTEXT,clock=lambda:0)
        args.update(kw);return sample_locktime(request() if r is None else r,**args)
    def test_grid_and_singleton(self):
        out=self.run_sample();self.assertTrue(out['ok'],out)
        self.assertEqual(out['total_points'],201);self.assertEqual(out['series'][0]['x'],[25+(475/200)*i for i in range(201)])
        r=request();r['x']['range']=[25,25];out=self.run_sample(r)
        self.assertEqual(out['series'][0]['x'],[25]);self.assertEqual(out['series'][0]['y'],[4])
    def test_invalid_requests_never_return_curves(self):
        cases=[]
        for field,value in [('version',True),('resolution',0),('resolution',1025),('budget_ms',10001),('fits',[]),('request_id','')]:
            r=request();r[field]=value;cases.append(r)
        for bounds in ([0,1],[30,25],[25,float('nan')],[25,float('inf')],[25,True],[1,1e9+1]):
            r=request();r['x']['range']=bounds;cases.append(r)
        r=request();r['fits']*=2;cases.append(r)
        r=request();r['fits'][0]['revision']=False;cases.append(r)
        r=request();r['x']['unit']='km';cases.append(r)
        r=request();r['unexpected']=1;cases.append(r)
        for r in cases:
            with self.subTest(request=r):
                out=self.run_sample(r);self.assertFalse(out['ok']);self.assertNotIn('series',out)
    def test_cancel_deadline_clock_and_stale(self):
        for args,code in [({'cancelled':lambda:True},'cancelled'),({'clock':iter([0,10]).__next__},'deadline_exceeded'),
                          ({'clock':iter([1,0]).__next__},'clock_error'),({'current_context':lambda:dict(CONTEXT,generation=1)},'stale_context'),
                          ({'resolve_fit':lambda key:(self.fit,1)},'stale_fit')]:
            out=self.run_sample(**args);self.assertEqual(out['error']['code'],code);self.assertNotIn('series',out)
    def test_midway_cancel_and_handle_replacement(self):
        n=[0]
        def cancelled():n[0]+=1;return n[0]>10
        self.assertEqual(self.run_sample(cancelled=cancelled)['error']['code'],'cancelled')
        other=deepcopy(self.fit);handles=iter([self.fit,other])
        self.assertEqual(self.run_sample(resolve_fit=lambda key:(next(handles),0))['error']['code'],'stale_fit')
    def test_invalid_engine_and_fallback_metadata(self):
        for value in (None,-1,float('inf'),float('nan'),True):
            self.fit.calculateLockTime=lambda radius,v=value:v
            out=self.run_sample();self.assertEqual(out['error']['code'],'invalid_engine_data');self.assertNotIn('series',out)
        self.fit.calculateLockTime=lambda radius:5
        for scan in (None,0,-1):
            self.fit.ship.getModifiedItemAttr=lambda key,s=scan:s
            self.assertTrue(self.run_sample()['ok'])
    def test_bounded_maximum(self):
        r=request();r['resolution']=1024;r['fits']=[dict(fit_id=str(i),revision=0) for i in range(8)]
        out=self.run_sample(r);self.assertEqual(out['total_points'],8200)

class SessionTests(NativeSessionTests):
    def lock_request(self):
        r=request();r['context']=self.session.context();r['fits']=[dict(fit_id=self.key,revision=self.session._revisions[self.key])];return r
    def sample(self,r=None):return json.loads(self.session.locktime_samples(json.dumps(self.lock_request() if r is None else r)))
    def test_real_eos_values_and_readonly_restart(self):
        before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history_details(self.key)
        out=self.sample();self.assertTrue(out['ok'],out)
        fit=self.session._fits[self.key]
        self.assertEqual(out['series'][0]['y'],[fit.calculateLockTime(radius=x) for x in out['series'][0]['x']])
        self.assertGreater(out['series'][0]['y'][0],out['series'][0]['y'][-1])
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph.snapshot());self.assertEqual(history,self.session.history_details(self.key))
        old=self.lock_request();self.reopen();self.assertFalse(self.sample(old)['ok']);self.assertEqual(out['series'][0]['y'],self.sample()['series'][0]['y'])
    def test_profile_edit_invalidates_and_changes_eos(self):
        r=self.lock_request();before=self.sample()['series'][0]['y']
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        self.assertEqual(self.sample(r)['error']['code'],'stale_context');self.assertNotEqual(before,self.sample()['series'][0]['y'])
    def test_scan_speed_fallback_real_eos(self):
        fit=self.session._fits[self.key];original=fit.ship.getModifiedItemAttr
        for scan in (None,0,-10):
            def attr(name,*args,**kw):return scan if name=='scanResolution' else 7500 if name=='scanSpeed' else original(name,*args,**kw)
            with patch.object(fit.ship,'getModifiedItemAttr',side_effect=attr):
                out=self.sample();self.assertTrue(out['ok'],out);self.assertEqual(set(out['series'][0]['y']),{7.5})
    def test_external_writer_and_invalid_json(self):
        out=json.loads(self.session.locktime_samples('{"version":1,"version":1}'));self.assertFalse(out['ok'])
        with patch.object(self.session.graph,'_verify_durable',side_effect=RuntimeError('injected')):
            out=self.sample();self.assertFalse(out['ok']);self.assertNotIn('series',out)

def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(BoundaryTests)
    for name in SessionTests.__dict__:
        if name.startswith('test_'):suite.addTest(SessionTests(name))
    return suite
