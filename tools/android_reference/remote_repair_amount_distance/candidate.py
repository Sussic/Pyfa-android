#!/usr/bin/env python3
"""Bounded candidate numerical/state lane. Only --execute boots EOS."""
import argparse
import hashlib
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import resource
import sqlite3
import sys
import time
from types import SimpleNamespace as NS
from unittest.mock import patch
import uuid
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(REPO),str(REPO/'android/app/src/main/python')]
from tools.android_reference.remote_repair_range.test_candidate import Candidate as Base, frozen, exact, sha, write, compare_curve
from tools.android_reference.remote_repair_range.cases import steps
from tools.android_reference.remote_repair_amount_distance.compare import curve,envelope,numeric,selected_samples,load_original

class Candidate(Base):
    def __init__(self,args,oracle):
        oracle.setdefault('source',os.environ['PYFA_REFERENCE_SOURCE']);self.args,self.oracle=args,oracle;self.stage='initial';self.states={};self.reads=[];self.checks=[];self.failures=[];self.raw_differences=[];self.network_attempts=[];self.spool_proof=None
        def network(event,values):
            if event in {'socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo'}:
                self.network_attempts.append(event);raise AssertionError('network forbidden '+event)
        sys.addaudithook(network)
        import mobile_runtime as runtime
        self.runtime=runtime;database=Path(os.environ['PYFA_DATABASE']).resolve()
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as connection:metadata=dict(connection.execute('SELECT field_name,field_value FROM metadata'))
        self.current=json.loads(args.current_original.read_text()) if args.current_original else None
        self.specs=deepcopy(oracle['inputs']);self.order=list(self.specs)
        states=oracle.get('states',{})
        raw=(states.get('initial') or next(iter(states.values()),{})).get('raw',{})
        if args.fresh:raw={label:fit['raw'] for label,fit in oracle['fits'].items()}
        for label,spec in self.specs.items():
            if label in raw:spec['modules']=deepcopy(raw[label]['modules'])
        runtime.boot(str(database),json.dumps(dict(dataset_metadata=metadata,database_logical_sha256=os.environ['PYFA_DATASET_SHA'])),json.dumps(dict(self.specs[self.order[0]],edit={})),str(args.store))
        boot=json.loads(runtime.bridge_bootstrap());assert boot['status']=='ok',boot
        self.session=runtime._bridge
        names={spec['name']:label for label,spec in self.specs.items()}
        self.ids={names[row['name']]:row['id'] for row in boot['fits']}
        if args.phase=='seed':
            for label in self.order[1:]:self.ids[label]=self.edit('create_fit',dict(spec=self.specs[label]))['fits'][0]['id']
        self.labels={value:key for key,value in self.ids.items()}
        exact(sorted(self.ids),sorted(self.order),'fit identities')
    def request_selected(self,label,time_value,sample):
        return dict(version=2,request_id='g052b-'+self.stage,context=self.session.context(),fits=[dict(fit_id=self.ids[label],revision=self.session._revisions[self.ids[label]])],x=dict(quantity='distance',unit='km',range=[0,100]),y=dict(quantity='repair_amount',unit='HP'),time=time_value,distance=None,ancillary_reload=sample['anc_reload'],ignore_lock_range=sample['options']['ignoreLockRange'],ignore_drone_control_range=sample['options']['ignoreDCR'],budget_ms=10000)
    def read(self,request,cancelled=lambda:False,inject=None,overrides=None,allowance=None):
        from android_bridge.offline import remote_repair_samples as module
        from android_bridge.offline.remote_repair_resource import RepairReservation
        ledger=RepairReservation() if allowance is None else RepairReservation(allowance);by_fit={};active=[None];phases={};preparations=[];self.active_phase='request';caches=[]
        assert allowance is not None or ledger.allowance==100663296
        from tools.android_reference.remote_repair_amount_distance.observe import snapshots
        original=module.sample_remote_repair;counts=Counter();before=self.state();before_bytes=self.args.store.read_bytes()
        def reserve(kind,count):
            assert type(count) is int and count>=0
            counts[kind]+=count
            key=active[0] or 'request';by_fit.setdefault(key,Counter())[kind]+=count
            previous=ledger.used;ledger(kind,count);assert ledger.used>=previous
            phases.setdefault(self.active_phase,Counter())[kind]+=count
            if inject:inject(kind,count)
        def sampled(*args,**kwargs):
            kwargs['time_reserve']=reserve
            prepare=kwargs['prepare_fit']
            def prepared(fit):
                active[0]=next(k for k,v in self.session._fits.items() if v is fit)
                preparations.append(active[0]);return prepare(fit)
            kwargs['prepare_fit']=prepared
            if overrides:kwargs.update(overrides)
            return original(*args,**kwargs)
        verify=self.session.graph._verify_durable
        from android_bridge.offline.remote_repair_time_math import CheckedTimeCache, CheckedDistance2RepAmountGetter
        def phase_wrapper(name,original):
            def wrapped(*args,**kwargs):
                old=self.active_phase;self.active_phase=name
                try:return original(*args,**kwargs)
                finally:self.active_phase=old
            return wrapped
        initialized=CheckedTimeCache.__init__
        def init(cache,*args,**kwargs):initialized(cache,*args,**kwargs);caches.append(cache)
        with ExitStack() as stack:
            stack.enter_context(patch.object(CheckedTimeCache,'__init__',init))
            for cls,method,name in ((CheckedTimeCache,'_generateInternalForm','generation'),(CheckedTimeCache,'prepareRepAmountData','amount_conversion'),(CheckedTimeCache,'_getDataPoint','lookup'),(CheckedDistance2RepAmountGetter,'_calculatePoint','adaptive')):
                stack.enter_context(patch.object(cls,method,phase_wrapper(name,getattr(cls,method))))
            observed=stack.enter_context(snapshots())
            stack.enter_context(patch.object(module,'sample_remote_repair',sampled))
            verified=stack.enter_context(patch.object(self.session.graph,'_verify_durable',wraps=verify))
            response=json.loads(self.runtime.offline_remote_repair_samples(json.dumps(request,allow_nan=True),NS(get=cancelled)))
        assert all(not c._data and not c._schedules and not c._active for c in caches), 'leaked cache'
        assert verified.call_count==2
        exact(before,self.state(),'complete read-only state');assert before_bytes==self.args.store.read_bytes()
        self.last_snapshots=observed
        safe_request=json.loads(json.dumps(request),parse_constant=lambda value:'nonfinite:'+value)
        self.reads.append(dict(request=safe_request,result=response,reservations=dict(counts),per_fit_reservations={k:dict(v) for k,v in by_fit.items()},nominal_used=ledger.used,nominal_allowance=ledger.allowance,durable_checks=verified.call_count,phase_reservations={k:dict(v) for k,v in phases.items()},production_preparations=preparations,all_caches_cleared=True))
        with self.args.output.with_suffix('.reads.jsonl').open('a') as stream:stream.write(json.dumps(self.reads[-1],sort_keys=True,allow_nan=False)+'\n')
        return response
    def compare_internal(self,sample,actual=None):
        if actual is None:
            assert len(self.last_snapshots)==1
            actual=self.last_snapshots[0]
        expected=sample['internal'][0]
        assert type(actual['horizon']) in (int,float) and expected['horizon']==actual['horizon'],'exact numeric effective horizon'
        for key in ('internal_rates','internal_amounts'):exact(expected[key],actual[key],'original internal '+key)
        exact([{k:v for k,v in row.items() if k!='cycle_bound'} for row in expected['cycles']],actual['cycles'],'original versus frozen-clone streams')
        exact(sample['maps']['finalRepAmount'],actual['finalRepAmount'],'ordered final amount maps')
        assert actual['finalRps']==[], 'Amount-only request prepared rate data'
        assert actual['cleared']
        self.checks.append(dict(stage=self.stage,internal_original_match=True,clone_stream_match=True,cache_cleared=True,sha256=hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest()))
    def observe(self,stage):
        self.stage=stage;expected=self.oracle['states'][stage]
        self.verify_raw(stage)
        found={}
        for label,want in expected['fits'].items():
            rows=[]
            for index,sample,c in selected_samples(want):
                request=self.request_selected(label,c['time'],sample);response=self.read(request);assert response['ok'],response
                envelope(request,response);curve(c,response['series'][0],stage+'.'+label);self.compare_internal(sample)
                for layer,column in want['columns'].items():numeric(column['value'],response['series'][0]['source_rates'][layer],'current '+layer)
                rows.append(response)
                rate_curve=next(rc for rc in sample['curves'] if rc['axis']=='distance' and rc['ordinate']=='rate')
                rate_request=deepcopy(request);rate_request['y']=dict(quantity='repair_rate',unit='HP/s')
                rate=self.read(rate_request);assert rate['ok'],rate;envelope(rate_request,rate);curve(rate_curve,rate['series'][0],stage+'.'+label+'.v2 rate')
                current=deepcopy(rate_request);current.update(version=1,time=None);del current['distance']
                v1=self.read(current);assert v1['ok'],v1;envelope(current,v1)
                v2=self.read(dict(current,version=2,distance=None));envelope(dict(current,version=2,distance=None),v2)
                normalized={k:v for k,v in v2.items() if k not in ('distance','effective')};normalized['version']=1;exact(v1,normalized,'v1/v2 current rate regression')
            found[label]=rows
        self.states[stage]=found
        current_stage='shared_repair_skill_five' if self.args.suite=='linked' and self.args.phase=='reopen' and stage=='initial' else stage
        if self.current and current_stage in self.current['states']:
            trace=next(row['requests'] for row in self.current['request_trace'] if row['stage']==current_stage)
            for label,want in self.current['states'][current_stage]['fits'].items():
                if label not in self.ids:continue
                for index,row in enumerate(trace):
                    request=Base.request(self,row,[label]);response=self.read(request);assert response['ok'],response
                    envelope(request,response);compare_curve(want['curves'][index],response['series'][0],'v1 current')
                    request2=dict(request,version=2,distance=None);response2=self.read(request2);envelope(request2,response2)
                    normalized={k:v for k,v in response2.items() if k not in ('distance','effective')};normalized['version']=1
                    exact(response,normalized,'v1 versus v2 null current')
    def failures_matrix(self):
        label=next(iter(self.ids));sample=dict(anc_reload=True,options=dict(ignoreLockRange=True,ignoreDCR=False));base=self.request_selected(label,0,sample)
        cases=[]
        for field,value in [('time',True),('time','0'),('time',float('inf')),('distance',0),('time',None),('y',dict(quantity='repair_amount',unit='HP/s')),('x',dict(quantity='time',unit='s',range=[0,10]))]:
            r=deepcopy(base);r[field]=value;cases.append(('invalid_request',r,None,None))
        r=deepcopy(base);del r['time'];cases.append(('invalid_request',r,None,None))
        r=deepcopy(base);r['version']=1;del r['distance'];cases.append(('invalid_request',r,None,None))
        r=deepcopy(base);r['fits'][0]['revision']+=1;cases.append(('stale_fit',r,None,None))
        r=deepcopy(base);r['context']['session_id']='stale';cases.append(('stale_context',r,None,None))
        cases.append(('cancelled',base,lambda:True,None))
        from android_bridge.projected_drone_admission import AdmissionRejected
        def reject(kind,count):raise AdmissionRejected('test injected resource rejection')
        cases.append(('resource_exhausted',base,None,reject))
        for code,r,cancel,inject in cases:
            result=self.read(r,cancel or (lambda:False),inject);assert result['ok'] is False and result['error']['code']==code,result
            envelope(dict(r,request_id=None) if 'time' not in r else r,result)
            if code=='invalid_request':assert not self.reads[-1]['production_preparations']
            self.failures.append(dict(expected=code,response=result))
        ticks=iter(i/1000 for i in range(100000));r=dict(base,budget_ms=10)
        result=self.read(r,overrides=dict(clock=lambda:next(ticks)))
        assert not result['ok'] and result['error']['code']=='deadline_exceeded',result
        envelope(r,result);self.failures.append(dict(expected='deadline_exceeded',response=result))
        def late_reject(kind,count):
            if kind=='output_slot':raise AdmissionRejected('late output refusal witness')
        result=self.read(base,inject=late_reject);assert not result['ok'] and result['error']['code']=='resource_exhausted',result
        envelope(base,result);self.failures.append(dict(expected='resource_exhausted_after_points',response=result))
        token=[False]
        def cancel_cycle(kind,count):
            if kind=='cycle':token[0]=True
        result=self.read(base,cancelled=lambda:token[0],inject=cancel_cycle)
        assert not result['ok'] and result['error']['code']=='cancelled' and token[0],result
        envelope(base,result);self.failures.append(dict(expected='cancelled_during_cycles',response=result))
        calls=[0]
        def late_resolve(key):
            calls[0]+=1
            return self.session._fits[key],self.session._revisions[key]+(1 if calls[0]>1 else 0)
        result=self.read(base,overrides=dict(resolve_fit=late_resolve))
        assert not result['ok'] and result['error']['code']=='stale_fit' and calls[0]>1,result
        envelope(base,result);self.failures.append(dict(expected='stale_fit_after_points',response=result))
        low=self.read(base,allowance=0);assert low['error']['code']=='resource_exhausted';envelope(base,low)
        self.failures.append(dict(expected='zero_allowance',response=low))
        for phase in ('generation','amount_conversion','lookup','adaptive','publication'):
            for failure in ('resource_exhausted','cancelled','deadline_exceeded','stale_context'):
                token=[False];ticks=[0.0]
                def trigger(kind,count):
                    hit=(self.active_phase==phase and (phase!='amount_conversion' or kind=='copy_slot')) or (phase=='publication' and kind=='output_slot')
                    if not hit:return
                    token[0]=True
                    if failure=='resource_exhausted':raise AdmissionRejected('phase refusal '+phase)
                    if failure=='deadline_exceeded':ticks[0]=11.0
                context=lambda: dict(self.session.context(),session_id='late-stale') if token[0] and failure=='stale_context' else self.session.context()
                result=self.read(base,cancelled=lambda:token[0] and failure=='cancelled',inject=trigger,overrides=dict(clock=lambda:ticks[0],current_context=context))
                assert token[0] and not result['ok'] and result['error']['code']==failure,(phase,failure,result)
                envelope(base,result);self.failures.append(dict(phase=phase,expected=failure,response=result))
                recovered=self.read(base);assert recovered['ok'],recovered;envelope(base,recovered)


def run(args):
    started=time.monotonic();assert 0<resource.getrlimit(resource.RLIMIT_AS)[0]<=1024**3
    oracle=json.loads(args.oracle.read_text());assert oracle['status']=='passed'
    assert sha(os.environ['PYFA_DATABASE'])==oracle['dataset_physical_sha256']
    checkpoint=Path(str(args.store)+'.g052-checkpoint.json')
    saved=json.loads(checkpoint.read_text()) if args.phase=='reopen' else None
    before_boot=sha(args.store) if args.phase=='reopen' else None
    candidate=Candidate(args,oracle)
    if saved:
        assert sha(args.store)==before_boot
        exact(saved['durable'],candidate.durable(),'fresh process durable graph/snapshots/bytes')
        assert saved['session_id']!=candidate.session.session_id
        assert not candidate.session.history.rows and candidate.session.history.sequence==0
        assert not candidate.session.graph._bridge._history.rows
        stale=candidate.read(saved['last_request']);assert not stale['ok'] and stale['error']['code']=='stale_context',stale
        candidate.checks.append(dict(fresh_process_reopen=True,durable_bytes_equal=True,old_session_rejected=True,history_empty=True))
    if args.fresh:
        candidate.oracle['states']={'initial':{'raw':{label:fit['raw'] for label,fit in oracle['fits'].items()}}}
        candidate.verify_raw('initial')
        for label,want in oracle['fits'].items():
            candidate.stage=label
            for c in want['curves']:
                request=candidate.request_selected(label,c['time'],c);request['x']['range']=[v/1000 for v in c.get('range',[0,100000])];response=candidate.read(request);assert response['ok'],response
                envelope(request,response);curve(c,response['series'][0],label)
                exact(c['maps']['finalRepAmount'],candidate.last_snapshots[0]['finalRepAmount'],'fresh original amount map');assert candidate.last_snapshots[0]['cleared']
                for layer,column in want['columns'].items():numeric(column['value'],response['series'][0]['source_rates'][layer],'source column')
                if c['time']==0:
                    for entered in (-123,-0.0):
                        request['time']=entered;clamped=candidate.read(request);envelope(request,clamped);curve(c,clamped['series'][0],label+' zero/clamp')
        candidate.failures_matrix()
    elif args.suite=='resource':
        for stage,want in (list(oracle['states'].items())[:1] if args.diagnostic_first else oracle['states'].items()):
            candidate.stage=stage;candidate.verify_raw(stage);labels=list(candidate.ids);sample=want['fits'][labels[0]]['samples'][0]
            for requested in ((2500,) if args.diagnostic_first else (2500,3000)):
                request=candidate.request_selected(labels[0],requested,sample);request['fits']=[dict(fit_id=candidate.ids[k],revision=candidate.session._revisions[candidate.ids[k]]) for k in labels]
                response=candidate.read(request);envelope(request,response)
                if not response['ok']:
                    assert response['error']['code']=='resource_exhausted',response
                    candidate.failures.append(dict(expected='resource_acceptance_blocked',response=response));continue
                observed_snapshots=candidate.last_snapshots
                before=candidate.state();before_bytes=args.store.read_bytes()
                plain=json.loads(candidate.runtime.offline_remote_repair_samples(json.dumps(request),NS(get=lambda:False)))
                envelope(request,plain);exact(response,plain,'unmodified production default route and JSON encoding')
                exact(before,candidate.state(),'unmodified production read-only');assert before_bytes==args.store.read_bytes()
                candidate.checks.append(dict(stage=stage,time=requested,unmodified_default_production_route=True,complete_encoded_response_equal=True))
                assert len(candidate.last_snapshots)==len(labels)
                for label,series,observed in zip(labels,response['series'],candidate.last_snapshots):
                    candidate.compare_internal(next(selected_samples(want['fits'][label]))[1],observed)
                    curve(next(selected_samples(want['fits'][label]))[2],series,stage+label)
                    for layer,column in want['fits'][label]['columns'].items():numeric(column['value'],series['source_rates'][layer],stage+label+' current '+layer)
    else:
        candidate.observe('initial');schedule=steps(args.suite)
        if args.suite=='linked':schedule=[s for s in schedule if (s['op']=='delete_source')==(args.phase=='reopen')]
        for step in schedule:
            owner=step['args'].get('fit',step['args'].get('target','source_a'))
            old=candidate.request_selected(next(iter(candidate.ids)),0,dict(anc_reload=True,options=dict(ignoreLockRange=True,ignoreDCR=False)))
            candidate.apply(step)
            stale=candidate.read(old);assert not stale['ok'] and stale['error']['code'] in ('stale_context','stale_fit','fit_not_found'),stale
            candidate.observe(step['name'])
            if step['args'].get('history'):
                candidate.edit('undo',dict(fit_id=candidate.ids[owner]));candidate.observe(step['name']+'_undo')
                candidate.edit('redo',dict(fit_id=candidate.ids[owner]));candidate.observe(step['name']+'_redo')
    if args.suite=='linked' and args.phase=='seed':
        write(checkpoint,dict(durable=candidate.durable(),session_id=candidate.session.session_id,last_request=candidate.reads[-1]['request']))
    assert not candidate.network_attempts and not candidate.runtime._forbidden
    result=dict(status='resource_acceptance_blocked' if any(f['expected']=='resource_acceptance_blocked' for f in candidate.failures) else 'passed',suite=args.suite,phase=args.phase,process_nonce=uuid.uuid4().hex,original_process_nonce=oracle['process_nonce'],oracle_sha256=sha(args.oracle),states=candidate.states,checks=candidate.checks,reads=candidate.reads,failures=candidate.failures,raw_differences=candidate.raw_differences,spool_proof=candidate.spool_proof,reservation_policy='actual production RepairReservation forwarded through observation hook; nominal allocation units NOT Android heap',read_count=len(candidate.reads),curve_count=sum(len(r['result'].get('series',[])) for r in candidate.reads),point_count=sum(r['result'].get('total_points',0) for r in candidate.reads),elapsed_seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,durable=candidate.durable(),network_attempts=candidate.network_attempts,android_execution=False)
    write(args.output,result)
    print(result['status'].upper(),args.suite,args.phase,result['read_count'],result['curve_count'],result['point_count'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--fresh',action='store_true');p.add_argument('--diagnostic-first',action='store_true');p.add_argument('--current-original',type=Path);p.add_argument('--suite',required=True);p.add_argument('--phase',choices=('seed','reopen'),default='seed')
    for name in ('oracle','store','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();assert args.execute;run(args)
