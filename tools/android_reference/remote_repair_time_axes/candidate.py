#!/usr/bin/env python3
"""Both time modes through real production adapter; frozen originals only."""
import argparse,hashlib,json,os,resource,sys,time,uuid
from pathlib import Path
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import patch
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(REPO),str(REPO/'android/app/src/main/python')]
from tools.android_reference.remote_repair_amount_distance.candidate import Candidate as Amount
from tools.android_reference.remote_repair_range.test_candidate import frozen,exact,sha,write
from tools.android_reference.remote_repair_range.cases import steps
from tools.android_reference.remote_repair_time_axes.compare import curve,envelope,numeric,selected_samples

class Candidate(Amount):
    def request_time(self,label,c,sample):
        return dict(version=2,request_id='g052cd-'+self.stage,context=self.session.context(),fits=[dict(fit_id=self.ids[label],revision=self.session._revisions[self.ids[label]])],x=dict(quantity='time',unit='s',range=c['range']),y=dict(quantity='repair_amount' if c['ordinate']=='amount' else 'repair_rate',unit='HP' if c['ordinate']=='amount' else 'HP/s'),time=None,distance=None if c.get('distance_m') is None else c['distance_m']/1000,ancillary_reload=sample['anc_reload'],ignore_lock_range=sample['options']['ignoreLockRange'],ignore_drone_control_range=sample['options']['ignoreDCR'],budget_ms=10000)
    def read(self,request,cancelled=lambda:False,inject=None,overrides=None,allowance=None,phase_trigger=None,reservation_override=None):
        from android_bridge.offline import remote_repair_samples as module
        from android_bridge.offline.remote_repair_resource import RepairReservation
        ledger=RepairReservation() if allowance is None else RepairReservation(allowance);by_fit={};active=[None];phases={};preparations=[];self.active_phase='request';caches=[]
        assert allowance is not None or ledger.allowance==100663296
        from tools.android_reference.remote_repair_amount_distance.observe import snapshots
        original=module.sample_remote_repair;counts=Counter();attempts=Counter();rejected=[];before=self.state();before_bytes=self.args.store.read_bytes()
        def reserve(kind,count):
            if reservation_override:kind,count=reservation_override(kind,count)
            assert type(count) is int and count>=0
            attempts[kind]+=count
            previous=ledger.used
            try:ledger(kind,count)
            except Exception:
                rejected.append(dict(kind=kind,count=count,used_before=previous,phase=self.active_phase,fit_id=active[0]));raise
            assert ledger.used>=previous
            counts[kind]+=count
            key=active[0] or 'request';by_fit.setdefault(key,Counter())[kind]+=count
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
        from android_bridge.offline.remote_repair_time_math import CheckedTimeCache, CheckedXTimeMixin
        from android_bridge.offline import remote_repair_time_math as maths
        from android_bridge.offline.remote_repair_time_output import TimeOutput
        def phase_wrapper(name,original):
            def wrapped(*args,**kwargs):
                old=self.active_phase;self.active_phase=name
                try:
                    if phase_trigger:phase_trigger(name)
                    return original(*args,**kwargs)
                finally:self.active_phase=old
            return wrapped
        initialized=CheckedTimeCache.__init__
        def init(cache,*args,**kwargs):initialized(cache,*args,**kwargs);caches.append(cache)
        with ExitStack() as stack:
            stack.enter_context(patch.object(CheckedTimeCache,'__init__',init))
            for cls,method,name in ((CheckedTimeCache,'_generateInternalForm','generation'),(CheckedTimeCache,'prepareRepAmountData','amount_conversion'),(CheckedTimeCache,'prepareRpsData','rate_conversion'),(CheckedXTimeMixin,'getRange','traversal'),(maths,'checked_apply','aggregation'),(maths,'checked_apply_time','aggregation'),(TimeOutput,'append','append'),(TimeOutput,'encode','encoding')):
                stack.enter_context(patch.object(cls,method,phase_wrapper(name,getattr(cls,method))))
            observed=stack.enter_context(snapshots())
            stack.enter_context(patch.object(module,'sample_remote_repair',sampled))
            verified=stack.enter_context(patch.object(self.session.graph,'_verify_durable',wraps=verify))
            started=time.monotonic()
            encoded=self.runtime.offline_remote_repair_samples(json.dumps(request,allow_nan=True),NS(get=cancelled))
            response=json.loads(encoded)
            elapsed=time.monotonic()-started
        assert all(not c._data and not c._schedules and not c._active for c in caches), 'leaked cache'
        assert verified.call_count==2
        exact(before,self.state(),'complete read-only state');assert before_bytes==self.args.store.read_bytes()
        self.last_snapshots=observed
        safe_request=json.loads(json.dumps(request),parse_constant=lambda value:'nonfinite:'+value)
        self.reads.append(dict(request=safe_request,result=response,reservations=dict(counts),reservation_attempts=dict(attempts),rejected_reservations=rejected,per_fit_reservations={k:dict(v) for k,v in by_fit.items()},nominal_used=ledger.used,nominal_allowance=ledger.allowance,durable_checks=verified.call_count,phase_reservations={k:dict(v) for k,v in phases.items()},production_preparations=preparations,all_caches_cleared=True,encoded_chars=len(encoded),elapsed_seconds=elapsed))
        with self.args.output.with_suffix('.reads.jsonl').open('a') as stream:stream.write(json.dumps(self.reads[-1],sort_keys=True,allow_nan=False)+'\n')
        return response
    def compare_internal(self,sample,mode,actual=None):
        if actual is None:
            assert len(self.last_snapshots)==1
            actual=self.last_snapshots[0]
        expected=sample['internal'][0]
        assert expected['horizon']==actual['horizon'],'exact fresh horizon'
        for key in ('internal_rates','internal_amounts'):exact(expected[key],actual[key],'internal '+key)
        exact([{k:v for k,v in row.items() if k!='cycle_bound'} for row in expected['cycles']],actual['cycles'],'cloned cycle streams')
        selected='finalRps' if mode=='rate' else 'finalRepAmount'
        other='finalRepAmount' if mode=='rate' else 'finalRps'
        exact(sample['maps'][selected],actual[selected],'ordered final maps')
        assert actual[other]==[], 'Unselected conversion unexpectedly prepared'
        assert actual['cleared']
        self.checks.append(dict(stage=self.stage,mode=mode,internal_original_match=True,clone_stream_match=True,cache_cleared=True,sha256=hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest()))
    def observe(self,stage):
        self.stage=stage;expected=self.oracle['states'][stage];self.verify_raw(stage);found={}
        for label,want in expected['fits'].items():
            rows=[]
            for index,sample,c in selected_samples(want):
                request=self.request_time(label,c,sample);response=self.read(request);assert response['ok'],response
                envelope(request,response);curve(c,response['series'][0],stage+'.'+label);self.compare_internal(sample,c['ordinate'])
                for layer,column in want['columns'].items():numeric(column['value'],response['series'][0]['source_rates'][layer],'current '+layer)
                rows.append(response)
            found[label]=rows
        self.states[stage]=found
        self.distance_regressions(expected)

    def distance_regressions(self,expected):
        from tools.android_reference.remote_repair_amount_distance.compare import curve as distance_curve,envelope as distance_envelope
        for label,want in expected['fits'].items():
            for sample in want['samples']:
                if sample['distance_m'] is not None:continue
                for original in sample['curves']:
                    if original['axis']!='distance':continue
                    request=self.request_selected(label,original['time'],sample)
                    if original['ordinate']=='rate':request['y']=dict(quantity='repair_rate',unit='HP/s')
                    got=self.read(request);assert got['ok'];distance_envelope(request,got);distance_curve(original,got['series'][0],self.stage+'.distance.'+label)
            if self.stage=='initial':
                sample=want['samples'][0];r=self.request_selected(label,None,sample);r['y']=dict(quantity='repair_rate',unit='HP/s')
                v2=self.read(r);assert v2['ok'];distance_envelope(r,v2)
                r['version']=1;del r['distance'];v1=self.read(r);assert v1['ok'];distance_envelope(r,v1)
                normalized={k:v for k,v in v2.items() if k not in ('distance','effective')};normalized['version']=1;exact(v1,normalized,'current rate v1/v2 regression')

    def fresh(self):
        self.oracle['states']={'initial':{'raw':{label:fit['raw'] for label,fit in self.oracle['fits'].items()}}};self.verify_raw('initial')
        for label,want in self.oracle['fits'].items():
            self.stage=label
            for c in want['curves']:
                request=self.request_time(label,c,c);response=self.read(request);assert response['ok'],response
                envelope(request,response);curve(c,response['series'][0],label)
                key='finalRps' if c['ordinate']=='rate' else 'finalRepAmount'
                exact(c['maps'][key],self.last_snapshots[0][key],'fresh original map');assert self.last_snapshots[0]['cleared']
                for layer,column in want['columns'].items():numeric(column['value'],response['series'][0]['source_rates'][layer],'current column')
                if c['range']==[0,0]:
                    for bounds in ([-123,-1],[-0.0,0.0]):
                        request['x']['range']=bounds;clamped=self.read(request);assert clamped['ok'],clamped;envelope(request,clamped)
                        from tools.android_reference.remote_repair_time_axes.replay import OriginalReplay
                        effective=[min(max(v,0),2500) for v in bounds]
                        xs,ys=OriginalReplay(Path(os.environ['PYFA_REFERENCE_SOURCE'])).curve(c['maps'][key],c['cache_horizon'],effective)
                        curve(dict(x=xs,y=ys),clamped['series'][0],label+' clamp')
        self.failures_matrix()

    def resource(self):
        from tools.android_reference.remote_repair_time_axes.replay import OriginalReplay
        replay=OriginalReplay(Path(os.environ['PYFA_REFERENCE_SOURCE']))
        for stage,want in self.oracle['states'].items():
            self.stage=stage;self.verify_raw(stage);labels=list(self.ids);sample=want['fits'][labels[0]]['samples'][0]
            for mode in ('rate','amount'):
                c=next(c for _,_,c in selected_samples(want['fits'][labels[0]]) if c['ordinate']==mode)
                request=self.request_time(labels[0],c,sample);request['fits']=[dict(fit_id=self.ids[k],revision=self.session._revisions[self.ids[k]]) for k in labels]
                assert request['x']['range']==[0,2500] and len(request['fits'])==8
                assert request['ancillary_reload']==(stage=='ancillary_reload_true') and stage in ('ancillary_reload_true','ancillary_reload_false')
                response=self.read(request);envelope(request,response)
                if not response['ok']:
                    self.failures.append(dict(expected='mandatory_resource_refusal',mode=mode,stage=stage,response=response));continue
                observed=self.last_snapshots
                before=self.state();before_bytes=self.args.store.read_bytes()
                plain_started=time.monotonic()
                plain_encoded=self.runtime.offline_remote_repair_samples(json.dumps(request),NS(get=lambda:False));plain=json.loads(plain_encoded)
                envelope(request,plain);exact(response,plain,'unmodified production complete JSON');exact(before,self.state(),'unmodified read-only');assert before_bytes==self.args.store.read_bytes()
                self.checks.append(dict(stage=stage,mode=mode,unmodified_default_production_route=True,encoded_chars=len(plain_encoded),elapsed_seconds=time.monotonic()-plain_started,complete_encoded_response_equal=True))
                assert len(observed)==8 and len(self.reads[-1]['production_preparations'])==8
                for label,series,snapshot in zip(labels,response['series'],observed):
                    _,sample,c=next(row for row in selected_samples(want['fits'][label]) if row[2]['ordinate']==mode)
                    self.compare_internal(sample,mode,snapshot);curve(c,series,stage+label)
                    for layer,column in want['fits'][label]['columns'].items():numeric(column['value'],series['source_rates'][layer],'resource source '+layer)
                if self.args.resource_first:continue
                clamp=deepcopy(request);clamp['x']['range']=[-1,2501];got=self.read(clamp);assert got['ok'];envelope(clamp,got)
                exact(response['series'],got['series'],'independent lower upper clamps')
                single=deepcopy(request);single['x']['range']=[2501,3000];got=self.read(single);assert got['ok'];envelope(single,got)
                for label,series in zip(labels,got['series']):
                    sample=want['fits'][label]['samples'][0];key='finalRps' if mode=='rate' else 'finalRepAmount'
                    xs,ys=replay.curve(sample['maps'][key],2500,[2500,2500]);curve(dict(x=xs,y=ys),series,'2500 one-point requested window')
    def resource_clamps(self):
        from tools.android_reference.remote_repair_time_axes.replay import OriginalReplay
        replay=OriginalReplay(Path(os.environ['PYFA_REFERENCE_SOURCE']))
        for stage,want in self.oracle['states'].items():
            self.stage=stage;self.verify_raw(stage);labels=list(self.ids)
            for mode in ('rate','amount'):
                sample=want['fits'][labels[0]]['samples'][0]
                for requested,effective in (([-1,2501],[0,2500]),([2501,3000],[2500,2500])):
                    request=self.request_time(labels[0],dict(ordinate=mode,range=requested,distance_m=None),sample)
                    request['fits']=[dict(fit_id=self.ids[k],revision=self.session._revisions[self.ids[k]]) for k in labels]
                    assert len(request['fits'])==8 and request['ancillary_reload']==(stage=='ancillary_reload_true')
                    got=self.read(request);assert got['ok'],got;envelope(request,got)
                    for label,series,snapshot in zip(labels,got['series'],self.last_snapshots):
                        sample=want['fits'][label]['samples'][0];key='finalRps' if mode=='rate' else 'finalRepAmount'
                        self.compare_internal(sample,mode,snapshot)
                        xs,ys=replay.curve(sample['maps'][key],2500,effective);curve(dict(x=xs,y=ys),series,'full8fit clamp/onepoint')
                        for layer,column in want['fits'][label]['columns'].items():numeric(column['value'],series['source_rates'][layer],'clamp current '+layer)

    def failures_matrix(self):
        from android_bridge.projected_drone_admission import AdmissionRejected
        label=next(k for k in self.ids if 'mixed' in k)
        sample=dict(anc_reload=True,options=dict(ignoreLockRange=True,ignoreDCR=False))
        for mode in ('rate','amount'):
            base=self.request_time(label,dict(ordinate=mode,range=[0,80],distance_m=None),sample)
            baseline_index=len(self.reads);baseline=self.read(base);assert baseline['ok'];envelope(base,baseline)
            cases=[]
            for field,value in [('time',0),('distance',True),('distance',-1),('distance',float('inf')),('distance',1e308),('y',dict(quantity='repair_amount',unit='HP/s')),('x',dict(quantity='time',unit='km',range=[0,10]))]:
                r=deepcopy(base);r[field]=value;cases.append(('invalid_request',r))
            for bounds in ([True,1],[0,float('nan')],[2,1],['0',1],[0]):
                r=deepcopy(base);r['x']['range']=bounds;cases.append(('invalid_request',r))
            r=deepcopy(base);del r['distance'];r['request_id']=None;cases.append(('invalid_request',r))
            r=deepcopy(base);r['fits'][0]['revision']+=1;cases.append(('stale_fit',r))
            r=deepcopy(base);r['context']['session_id']='stale';cases.append(('stale_context',r))
            for code,r in cases:
                response=self.read(r);assert not response['ok'] and response['error']['code']==code,(code,response)
                envelope(r,response)
                if code=='invalid_request':assert not self.reads[-1]['production_preparations']
                self.failures.append(dict(mode=mode,expected=code,response=response))
            low=self.read(base,allowance=0);assert low['error']['code']=='resource_exhausted';envelope(base,low)
            self.failures.append(dict(mode=mode,expected='zero_allowance',response=low))
            for phase in ('generation',mode+'_conversion','sorted_traversal','aggregation','append','encoding'):
                for failure in ('resource_exhausted','cancelled','deadline_exceeded','stale_context'):
                    token=[False];ticks=[0.0]
                    def trigger(name):
                        if name!=phase:return
                        token[0]=True
                        if failure=='resource_exhausted':raise AdmissionRejected('phase refusal '+phase)
                        if failure=='deadline_exceeded':ticks[0]=11.0
                    def reserve_trigger(kind,count):
                        if phase=='sorted_traversal' and kind=='sort_work' and self.active_phase=='traversal':trigger(phase)
                    context=lambda:dict(self.session.context(),session_id='late-stale') if token[0] and failure=='stale_context' else self.session.context()
                    response=self.read(base,cancelled=lambda:token[0] and failure=='cancelled',inject=reserve_trigger,phase_trigger=trigger,overrides=dict(clock=lambda:ticks[0],current_context=context))
                    assert token[0] and not response['ok'] and response['error']['code']==failure,(phase,failure,response)
                    envelope(base,response);self.failures.append(dict(mode=mode,phase=phase,expected=failure,response=response))
                    recovered=self.read(base);assert recovered['ok'],recovered;envelope(base,recovered)
                    exact(baseline,recovered,'complete same-request phase recovery')
                    self.checks.append(dict(mode=mode,phase=phase,recovery_read_index=len(self.reads)-1,baseline_read_index=baseline_index,complete_output_equal=True))
            for guard,count,message in (
                ('counter',2**63-1,'Invalid remote repair resource reservation'),
                ('arithmetic',2**62,'Remote repair resource accounting overflow')):
                def overflow(kind,original_count):
                    return (kind,count) if kind=='output_point' else (kind,original_count)
                response=self.read(base,reservation_override=overflow)
                assert response['error']['code']=='resource_exhausted' and response['error']['message']==message,response
                envelope(base,response)
                assert self.reads[-1]['rejected_reservations'][0]['count']==count
                self.failures.append(dict(mode=mode,expected=guard+'_overflow_after_generation',response=response))
                recovered=self.read(base);assert recovered['ok'];envelope(base,recovered)
                exact(baseline,recovered,'complete '+guard+' overflow recovery')
                self.checks.append(dict(mode=mode,phase=guard+'_overflow',recovery_read_index=len(self.reads)-1,baseline_read_index=baseline_index,complete_output_equal=True))

def run(args):
    started=time.monotonic();assert 0<resource.getrlimit(resource.RLIMIT_AS)[0]<=1024**3
    oracle=json.loads(args.oracle.read_text());assert oracle['status']=='passed'
    assert sha(os.environ['PYFA_DATABASE'])==oracle['dataset_physical_sha256']
    checkpoint=Path(str(args.store)+'.g052-time-checkpoint.json')
    saved=json.loads(checkpoint.read_text()) if args.phase=='reopen' else None
    before_boot=sha(args.store) if args.phase=='reopen' else None
    candidate=Candidate(args,oracle)
    if saved:
        assert sha(args.store)==before_boot;exact(saved['durable'],candidate.durable(),'reopened durable bytes/state')
        assert saved['session_id']!=candidate.session.session_id
        assert not candidate.session.history.rows and candidate.session.history.sequence==0
        assert not candidate.session.graph._bridge._history.rows
        stale=candidate.read(saved['last_request']);assert not stale['ok'] and stale['error']['code']=='stale_context'
        candidate.checks.append(dict(fresh_process_reopen=True,durable_bytes_equal=True,old_session_rejected=True,history_empty=True))
    if args.fresh:candidate.fresh()
    elif args.suite=='resource':
        if args.resource_clamps_only:candidate.resource_clamps()
        else:candidate.resource()
    else:
        candidate.observe('initial');schedule=steps(args.suite)
        if args.suite=='linked':schedule=[s for s in schedule if (s['op']=='delete_source')==(args.phase=='reopen')]
        for step in schedule:
            owner=step['args'].get('fit',step['args'].get('target','source_a'))
            old=candidate.request_time(next(iter(candidate.ids)),dict(ordinate='rate',range=[0,0]),dict(anc_reload=True,options=dict(ignoreLockRange=True,ignoreDCR=False)))
            candidate.apply(step)
            stale=candidate.read(old);assert not stale['ok'] and stale['error']['code'] in ('stale_context','stale_fit','fit_not_found'),stale
            candidate.observe(step['name'])
            if step['args'].get('history'):
                candidate.edit('undo',dict(fit_id=candidate.ids[owner]));candidate.observe(step['name']+'_undo')
                candidate.edit('redo',dict(fit_id=candidate.ids[owner]));candidate.observe(step['name']+'_redo')
    if args.suite=='linked' and args.phase=='seed':write(checkpoint,dict(durable=candidate.durable(),session_id=candidate.session.session_id,last_request=candidate.reads[-1]['request']))
    assert not candidate.network_attempts and not candidate.runtime._forbidden
    actual_imports={}
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path:
            path=Path(path).resolve()
            if path.is_relative_to(REPO) and path.suffix=='.py':actual_imports[str(path)]=sha(path)
    result=dict(actual_imports=actual_imports,status='resource_acceptance_blocked' if any(f['expected']=='mandatory_resource_refusal' for f in candidate.failures) else 'passed',suite=args.suite,phase=args.phase,process_nonce=uuid.uuid4().hex,original_process_nonce=oracle['process_nonce'],oracle_sha256=sha(args.oracle),states=candidate.states,checks=candidate.checks,reads=candidate.reads,failures=candidate.failures,raw_differences=candidate.raw_differences,spool_proof=candidate.spool_proof,reservation_policy='actual production RepairReservation; nominal allocation units NOT Android heap',read_count=len(candidate.reads),curve_count=sum(len(r['result'].get('series',[])) for r in candidate.reads),point_count=sum(r['result'].get('total_points',0) for r in candidate.reads),elapsed_seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,durable=candidate.durable(),network_attempts=candidate.network_attempts,android_execution=False)
    write(args.output,result);print(result['status'].upper(),args.suite,args.phase,result['read_count'],result['curve_count'],result['point_count'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--fresh',action='store_true');p.add_argument('--resource-first',action='store_true');p.add_argument('--resource-clamps-only',action='store_true');p.add_argument('--current-original',type=Path);p.add_argument('--suite',required=True);p.add_argument('--phase',choices=('seed','reopen'),default='seed')
    for name in ('oracle','store','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();assert args.execute;run(args)
