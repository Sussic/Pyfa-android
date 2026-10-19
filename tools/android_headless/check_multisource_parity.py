#!/usr/bin/env python3
"""D02.1 actual mobile_runtime/NativeSession finite multi-source parity.

The numerical oracle must have been produced in another original-only process.
All mutations and fitting reads use public runtime dispatch/read APIs. Internal
records are inspected only for exact persistence/identity/history assertions and
failure injection, never used as expected numerical outputs.
"""
import argparse
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch
import uuid
PROCESS_NONCE=uuid.uuid4().hex

REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO),str(REPO/'android/app/src/main/python')]
from tools.android_reference.reference import compare
from tools.android_reference.multisource.cases import fixtures,scenario,assert_witnesses,LABELS,DAMP,SKILL


def canonical(value):return json.loads(json.dumps(value,sort_keys=True,allow_nan=False))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


class Candidate:
    def __init__(self,args):
        self.args=args;self.steps=[];self.budgets=[];self.previews={};self.checks=[];self.network_attempts=[];self.edge_orders={};self._measured_requests=None;self._active_measurement=None
        def network_guard(event,values):
            if event in {'socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo'}:
                self.network_attempts.append(event)
                raise AssertionError('Offline proof: '+event)
        sys.addaudithook(network_guard)
        import mobile_runtime as runtime
        self.runtime=runtime
        database=Path(os.environ['PYFA_DATABASE']).resolve()
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as connection:metadata=dict(connection.execute('SELECT field_name,field_value FROM metadata'))
        order=list(reversed(LABELS)) if args.reverse else list(LABELS)
        self.order=order
        specs=fixtures(args.suite);self.specs=specs
        runtime.boot(str(database),json.dumps(dict(dataset_metadata=metadata,database_logical_sha256=os.environ['PYFA_DATASET_SHA'])),json.dumps(dict(specs[order[0]],edit={})),str(args.store))
        boot=json.loads(runtime.bridge_bootstrap());assert boot['status']=='ok',boot
        self.session=runtime._bridge
        self.ids={row['name'].removeprefix('D02.1 '):row['id'] for row in boot['fits']}
        if args.phase=='candidate':
            for key in order[1:]:
                value=self.edit('create_fit',dict(spec=specs[key]));self.ids[key]=value['fits'][0]['id']
        assert set(self.ids)==set(LABELS) or args.phase=='reopen'
        self.labels={value:key for key,value in self.ids.items()}

    def item(self,name):
        import eos.db
        value=eos.db.getItem(name);assert value is not None,name
        return value.ID

    def request(self,operation,args):
        ids={args[k] for k in ('fit_id','source_id','target_id') if k in args}
        return dict(version=1,request_id='d02-'+operation,session_id=self.session.session_id,operation=operation,arguments=args,expected_revisions={k:self.session._revisions[k] for k in ids})

    def edit(self,operation,args):
        with self.measure_request(operation):
            result=json.loads(self.runtime.bridge_dispatch(json.dumps(self.request(operation,args))))
        assert result['status']=='ok',(operation,result)
        return result

    def feature(self,operation,args,anchor='source_a'):
        request=dict(version=1,request_id='d02-'+operation,context=self.session.context(),operation=operation,arguments=args,anchor_fit_id=self.ids[anchor])
        with self.measure_request(operation):
            result=json.loads(self.runtime.offline_feature_dispatch(json.dumps(request)))
        assert result['ok'],(operation,result)
        return result

    def rows(self,label,family):
        fn=getattr(self.runtime,'projected_'+family+'_details');field={'module':'modules','drone':'stacks','fighter':'squadrons'}[family]
        return json.loads(fn(self.ids[label]))[field]

    def selection(self,label,family,index):
        row=self.rows(label,family)[index]
        return dict(position=row['index'],object_key=row['object_key'])

    def source_module(self,label):
        rows=self.edit('snapshot',dict(fit_ids=[self.ids[label]]))['fits'][0]['modules']
        return next(row['index'] for row in rows if row.get('name')==DAMP)

    def mapped(self,step):
        op,args=step['op'],step['args'];fit_id=self.ids.get(args.get('fit'))
        if op in ('add_link','link_amount','link_range','link_active','remove_link'):
            operation={'add_link':'add_projected_fit','link_amount':'set_projected_fit_amount','link_range':'set_projected_fit_range','link_active':'set_projected_fit_active','remove_link':'remove_projected_fit'}[op]
            return operation,dict(source_id=self.ids[args['source']],target_id=self.ids[args['target']],**{k:v for k,v in args.items() if k in ('amount','range_m','active')})
        if op=='local_charge':return 'set_module_charge',dict(fit_id=fit_id,position=self.source_module(args['fit']),charge_id=self.item(args['charge']))
        if op=='local_active':return 'set_module_states',dict(fit_id=fit_id,module_indices=[self.source_module(args['fit'])],state='ACTIVE' if args['active'] else 'ONLINE')
        if op in ('add_module','add_drone','add_fighter'):return 'add_projected_'+op[4:],dict(fit_id=fit_id,item_id=self.item(args['item']))
        if op=='selected_charges':
            request=dict(main=self.selection(args['fit'],'module',args['main']),selection=[self.selection(args['fit'],'module',i) for i in args['selection']],scope=args['scope'],charge_id=None if args['charge'] is None else self.item(args['charge']))
            before=self.state()
            preview=json.loads(self.runtime.projected_module_charge_preview(fit_id,json.dumps(request)))
            assert self.state()==before,'Preview mutated inputs/history'
            self.previews[step['name']]=preview
            pair=lambda row:dict(position=row['index'],object_key=row['object_key'])
            return 'set_projected_module_charges',dict(fit_id=fit_id,**request,expected_targets=[pair(r) for r in preview['targets']],expected_changes=[pair(r) for r in preview['targets'] if r['status']=='change'])
        if op=='remove_projector':return 'remove_projected_'+args['family'],dict(fit_id=fit_id,**self.selection(args['fit'],args['family'],args['index']),**({'amount':1} if args['family']=='drone' else {}))
        if op=='fighter_amount':return 'set_projected_fighter_amount',dict(fit_id=fit_id,**self.selection(args['fit'],'fighter',args['index']),amount=args['amount'])
        if op=='fighter_ability':
            options=json.loads(self.runtime.projected_fighter_options(fit_id,args['index']))
            # Select by the original effect identity, not translated UI name.
            from eos.saveddata.fighter import Fighter
            import eos.db
            effect=next(a.effectID for a in Fighter(eos.db.getItem('Dromi I')).abilities if a.effect.isImplemented and 'Web' in a.effect.name)
            assert effect in {a['effect_id'] for a in options['abilities']}
            return 'toggle_projected_fighter_ability',dict(fit_id=fit_id,**self.selection(args['fit'],'fighter',args['index']),effect_id=effect)
        if op in ('projector_range','projector_active'):
            field='range' if op=='projector_range' else 'active';key='range_m' if field=='range' else 'active'
            return 'set_projected_'+args['family']+'_'+field,dict(fit_id=fit_id,**self.selection(args['fit'],args['family'],args['index']),**{key:args[key]})
        if op=='delete_source':return 'delete_fit',dict(fit_id=fit_id,resolve_references=True)
        raise AssertionError(op)

    def profile(self):return self.session.feature_state()['bindings'][self.ids['source_a']]['profile_id']

    def apply(self,step):
        op,args=step['op'],step['args']
        if op=='share_profile':
            self.feature('create_profile',dict(name='D02 shared all V',source='builtin:all5'))
            profile=next(row['profile_id'] for row in self.session.feature_state()['profiles'] if row['name']=='D02 shared all V')
            for label in ('source_a','source_b'):self.feature('assign_profile',dict(fit_id=self.ids[label],profile_id=profile))
            return
        if op=='shared_skill':
            profile=self.profile();row=next(row for row in self.session.feature_state()['profiles'] if row['profile_id']==profile)
            return self.feature('set_profile_skill',dict(profile_id=profile,revision=row['revision'],skill_id=self.item(SKILL),level=args['level']))
        operation,values=self.mapped(step)
        if op=='delete_source':
            deleted=self.ids[args['fit']]
            old_sequence=self.session.history.sequence
            expected_history={}
            for key,(actions,cursor) in self.session.history.rows.items():
                if key!=deleted:
                    expected_history[key]=(tuple(action for action in actions if deleted not in action.participants),
                        sum(deleted not in action.participants for action in actions[:cursor]))
        result=self.edit(operation,values)
        if op=='delete_source':
            old=self.ids.pop(args['fit']);self.labels.pop(old)
            assert all(all(edge['source_id']!=old for edge in row['projections']) for row in self.session._records.values())
            assert old not in self.session._records and old not in self.session.history.rows
            assert self.session.history.sequence==old_sequence,'NON_HISTORY deletion created an action'
            assert self.session.history.rows==expected_history,'Deletion did not exactly prune affected history'
            self.checks.append('source deletion NON_HISTORY with exact reference and affected-action pruning')
        return result

    def raw(self,label):
        record=self.session._records[self.ids[label]];spec=record['spec']
        original=self.specs[label]
        projected={'projected_modules','projected_drones','projected_fighters'}
        assert set(original)<=set(spec)<=set(original)|projected,'Unexpected durable spec keys: '+label
        for key,value in original.items():
            if key not in projected|{'modules'}:
                assert json.dumps(spec[key],sort_keys=True,allow_nan=False)==json.dumps(value,sort_keys=True,allow_nan=False),'Unrelated durable input changed: '+label+'.'+key
        modules=[]
        for m in spec['modules']:
            modules.append(dict(empty_slot=m['empty_slot']) if 'empty_slot' in m else dict(name=m['name'],state=m['state'],charge=m.get('charge')))
        return dict(name=spec['name'],ship=spec['ship'],modules=modules,drones=deepcopy(spec['drones']),
            projected_modules=deepcopy(spec.get('projected_modules',[])),projected_drones=deepcopy(spec.get('projected_drones',[])),projected_fighters=deepcopy(spec.get('projected_fighters',[])),
            skills=deepcopy(record['skills']),projections=sorted([dict(edge,source_id=self.labels[edge['source_id']]) for edge in record['projections']],key=lambda row:row['source_id']))

    def sample(self,order=None):
        order=[label for label in (order or self.order) if label in self.ids]
        response=self.edit('snapshot',dict(fit_ids=[self.ids[key] for key in order]))
        stats={self.labels[row['id']]:row['stats'] for row in response['fits']}
        assert all(len(value)==39 for value in stats.values())
        return dict(stats=stats,raw={key:self.raw(key) for key in self.ids})

    def captured(self):
        authority=deepcopy(self.session.graph.snapshot()['graph']['profiles'])
        # Input authority and binding identity must survive history exactly; only
        # monotonic publication revisions intentionally advance on undo/redo.
        for collection in ('profiles','bindings'):
            for value in authority[collection].values():value.pop('revision')
        return canonical(dict(records=self.session._records,profile_authority=authority,stats=self.sample()['stats']))

    def state(self):
        return canonical(dict(graph=self.session.graph.snapshot(),records=self.session._records,revisions=self.session._revisions,
            histories={key:self.session.history_details(key) for key in self.session._fits},library=self.session.feature_state()['history'],
            recent=json.loads(self.runtime.recent_items()),context=self.session.context(),file_sha256=sha(self.args.store)))

    def durable(self):
        feature=self.session.feature_state()
        return canonical(dict(graph=self.session.graph.snapshot(),profiles=feature['profiles'],bindings=feature['bindings'],recent=json.loads(self.runtime.recent_items()),
            rows={label:{family:self.rows(label,family) for family in ('module','drone','fighter')} for label in self.ids},generation=self.session.context()['generation'],file_sha256=sha(self.args.store)))

    def interleave(self):
        before=self.state();samples=self.sample()
        entries=[dict(fit_id=self.ids[k],revision=self.session._revisions[self.ids[k]]) for k in self.order if k in self.ids]
        base=dict(version=1,request_id='d02-interleaved',context=self.session.context(),fits=entries,resolution=16,budget_ms=10000)
        requests=[('offline_capacitor_samples',dict(base,x=dict(quantity='time',unit='s',range=[0,30]),y=dict(quantity='cap_amount',unit='GJ'),starting_cap_percent=100,use_simulation=True)),
            ('offline_locktime_samples',dict(base,x=dict(quantity='signature_radius',unit='m',range=[25,500]),y=dict(quantity='lock_time',unit='s'))),
            ('offline_mobility_samples',dict(base,x=dict(quantity='time',unit='s',range=[0,30]),y=dict(quantity='speed',unit='m/s'),target_mass_mkg=None,target_inertia=None))]
        for method,request in requests:
            result=json.loads(getattr(self.runtime,method)(json.dumps(request)));assert result['ok'],(method,result)
        for key in reversed(entries):
            for method in ('capacitor_details','targeting_details','output_details','resource_details'):
                json.loads(getattr(self.runtime,method)(key['fit_id']))
        compare(samples,self.sample(list(reversed(self.order))),'read_interleaving')
        assert self.state()==before,'Reads changed durable graph, Recent, history or generation'
        self.checks.append('capacitor/lock/mobility/details interleaving exact inputs and all 39 stats')

    def failures(self):
        from android_bridge.offline.profile_store import StoreWriteRejected
        # Both sources and recipients now exist with a shared profile and links.
        before=self.state();profile=self.profile()
        row=next(row for row in self.session.feature_state()['profiles'] if row['profile_id']==profile)
        args=dict(profile_id=profile,revision=row['revision'],skill_id=self.item(SKILL),level=0)
        request=dict(version=1,request_id='d02-failed-profile',context=self.session.context(),operation='set_profile_skill',arguments=args,anchor_fit_id=self.ids['source_a'])
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('D02 injected durable write rejection')) as write:
            result=json.loads(self.runtime.offline_feature_dispatch(json.dumps(request)))
        assert write.call_count==1 and not result['ok'] and not result['committed'],result
        assert self.state()==before and self.session._available,'Rejected profile edit did not exactly recover'
        self.sample();self.checks.append('failed shared-profile durable write exact graph/identity/history/revision recovery')
        # prepare is reached only after admission, complete restore and response serialization.
        step=dict(op='local_charge',args=dict(fit='source_a',charge='Scan Resolution Dampening Script'))
        operation,values=self.mapped(step);before=self.state()
        with patch.object(self.session._store,'prepare',side_effect=ValueError('D02 admitted late-prewrite failure')) as prepare:
            result=json.loads(self.runtime.bridge_dispatch(json.dumps(self.request(operation,values))))
        assert prepare.call_count==1 and result['status']=='error',result
        assert self.state()==before and self.session._available,'Late failure did not exactly recover'
        self.sample();self.checks.append('admitted source edit late prepare failure exact recovery')
        # Endpoint revision mismatch and stale object identity both precede writes.
        operation,values=self.mapped(dict(op='link_range',args=dict(source='source_a',target='target_a',range_m=1234)))
        stale=self.request(operation,values);stale['expected_revisions'][self.ids['source_a']]-=1
        before=self.state();result=json.loads(self.runtime.bridge_dispatch(json.dumps(stale)))
        assert result['status']=='error' and result['error']['code']=='REVISION_CONFLICT';assert self.state()==before
        # Invalid object token against an existing source-side direct module is covered in composition.
        self.checks.append('stale source endpoint revision rejected atomically')

    def stale_object(self):
        if not self.rows('target_a','module'):return
        args=dict(fit_id=self.ids['target_a'],**self.selection('target_a','module',0),range_m=1234)
        args['object_key']='0'*32;before=self.state()
        result=json.loads(self.runtime.bridge_dispatch(json.dumps(self.request('set_projected_module_range',args))))
        assert result['status']=='error' and self.state()==before
        self.checks.append('stale direct object identity rejected atomically')

    @contextmanager
    def measure_request(self,operation):
        if self._measured_requests is None or operation=='snapshot':
            yield
            return
        row=dict(operation=operation,actual_roots=0,actual_calculation_calls=0,actual_cap_runs=0,admissions=[],capacitor_scopes=[])
        self._measured_requests.append(row)
        assert self._active_measurement is None
        self._active_measurement=row
        try:yield
        finally:self._active_measurement=None

    @contextmanager
    def observe(self,stage):
        from android_bridge import projected_drone_budget as budget, projected_drone_cap_budget as cap
        from eos.saveddata.fit import Fit
        from eos.capSim import CapSimulator
        original_admit,original_check=budget.admit,cap.check
        original_calc,original_run=Fit.calculateModifiedAttributes,CapSimulator.run
        requests=[];depth=0
        self._measured_requests=requests
        def admitted(*args,**kwargs):
            value=original_admit(*args,**kwargs)
            if self._active_measurement is not None:self._active_measurement['admissions'].append(canonical(value))
            return value
        def checked(fit,fit_count=1,**kwargs):
            value=original_check(fit,fit_count,**kwargs)
            if self._active_measurement is not None:self._active_measurement['capacitor_scopes'].append(dict(fit_count=fit_count,simulations_per_fit=kwargs.get('simulations_per_fit',cap.MAX_SIMULATIONS_PER_FIT),work=value['work']))
            return value
        def calculated(fit,*args,**kwargs):
            nonlocal depth
            if self._active_measurement is not None:
                self._active_measurement['actual_calculation_calls']+=1
                if depth==0:self._active_measurement['actual_roots']+=1
            depth+=1
            try:return original_calc(fit,*args,**kwargs)
            finally:depth-=1
        def simulated(simulator,*args,**kwargs):
            if self._active_measurement is not None:self._active_measurement['actual_cap_runs']+=1
            return original_run(simulator,*args,**kwargs)
        try:
            with patch.object(budget,'admit',side_effect=admitted),patch.object(cap,'check',side_effect=checked),patch.object(Fit,'calculateModifiedAttributes',new=calculated),patch.object(CapSimulator,'run',new=simulated):yield
        finally:self._measured_requests=None
        unique=lambda rows:[json.loads(value) for value in sorted({json.dumps(row,sort_keys=True) for row in rows})]
        for row in requests:
            admissions=row['admissions'];scopes=row['capacitor_scopes']
            row['actual_admission_calls']=len(admissions);row['actual_cap_checks']=len(scopes)
            row['admissions']=unique(admissions);row['capacitor_scopes']=unique(scopes)
            enabled=[v for v in admissions if v.get('enabled')]
            if enabled:
                row['admitted_max_roots']=max(v['request_phases']*v['root_calls_per_phase'] for v in enabled)
                assert row['actual_roots']<=row['admitted_max_roots'],row
            if scopes:
                row['admitted_max_cap_runs']=max(v['fit_count']*v['simulations_per_fit'] for v in scopes)
                assert row['actual_cap_runs']<=row['admitted_max_cap_runs'],row
        self.budgets.append(dict(stage=stage,measurement_scope='each actual mutation dispatch only; excludes preview, snapshot and later observation reads',requests=requests))

    def edge_order(self,stage):
        orders={}
        for label,key in self.ids.items():
            edges=self.session._records[key]['projections']
            ids=[row['source_id'] for row in edges]
            assert ids==sorted(ids),'Saved edge canonical order changed'
            orders[label]=[self.labels[value] for value in ids]
        self.edge_orders[stage]=orders


def main(args):
    oracle=json.loads(args.oracle.read_text());assert oracle['suite']==args.suite and oracle['reverse']==args.reverse
    assert oracle['process_nonce']!=PROCESS_NONCE,'Expected distinct original and candidate processes'
    compare(oracle['inputs'],fixtures(args.suite),'fixture_inputs')
    if args.phase=='candidate':assert not args.store.exists()
    candidate=Candidate(args);runtime=candidate.runtime
    compare(oracle['eos_settings'],candidate.session.engine.settings,'eos_settings')
    compare(oracle['dataset_metadata'],candidate.session.engine.metadata,'dataset_metadata')
    for name,identity in oracle['resolved_item_ids'].items():compare(identity,candidate.item(name),'resolved_item.'+name)
    steps=scenario(args.suite,args.reverse)
    cut=next(i for i,step in enumerate(steps) if step['op']=='remove_projector' or step['name']=='remove_a')
    receipt=Path(str(args.store)+'.receipt.json')
    if args.phase=='reopen':
        saved=json.loads(receipt.read_text());assert saved['phase']=='populated_checkpoint'
        assert saved['process_nonce']!=PROCESS_NONCE and saved['session_id']!=candidate.session.session_id
        assert candidate.durable()==saved['durable'],'Fresh process durable restoration differs'
        compare(saved['checkpoint'],candidate.sample(),'fresh_process_populated_checkpoint')
        for key in candidate.session._fits:
            row=candidate.session.history_details(key);assert row['undo_count']==row['redo_count']==0
        row=candidate.session.feature_state()['history'];assert row['undo_count']==row['redo_count']==0
        assert not runtime._forbidden and not candidate.network_attempts
        states=saved['states'];candidate.checks=list(saved['checks'])+['fresh-process complete populated inputs/identities/order/charges/profiles/stats restored before mutation','all per-fit and library history reset before mutation']
        selected=steps[cut:]
        print('PASS POPULATED REOPEN',args.suite,flush=True)
    else:
        states={'initial':candidate.sample()};compare(oracle['states']['initial'],states['initial'],'initial')
        selected=steps[:cut]
    for step in selected:
        before=candidate.captured();old_counts={k:candidate.session.history_details(v)['undo_count'] for k,v in candidate.ids.items()}
        if step['name']=='shared_skill_zero':candidate.failures()
        with candidate.observe(step['name']):candidate.apply(step)
        candidate.edge_order(step['name'])
        states[step['name']]=candidate.sample();compare(oracle['states'][step['name']],states[step['name']],step['name'])
        compare(states[step['name']],candidate.sample(list(reversed(candidate.order))),'candidate_read_order.'+step['name'])
        if step['args'].get('history'):
            after=candidate.captured();owner=step['args'].get('fit',step['args'].get('target','source_a'));fit_id=candidate.ids[owner]
            assert candidate.session.history_details(fit_id)['undo_count']==old_counts[owner]+1,(step['name'],'not exactly one action')
            candidate.edit('undo',dict(fit_id=fit_id));assert candidate.captured()==before,'Undo did not restore exact captured inputs/stats: '+step['name']
            states[step['name']+'_undo']=candidate.sample();compare(oracle['states'][step['name']+'_undo'],states[step['name']+'_undo'],step['name']+'_undo')
            candidate.edit('redo',dict(fit_id=fit_id));assert candidate.captured()==after,'Redo did not restore exact captured inputs/stats: '+step['name']
            states[step['name']+'_redo']=candidate.sample();compare(oracle['states'][step['name']+'_redo'],states[step['name']+'_redo'],step['name']+'_redo')
        if step['name']=='similar_scan':candidate.stale_object()
        if step['name'] in ('similar_scan','source_fighter_ability_off','shared_skill_zero','outgoing_far'):candidate.interleave()
        print('CANDIDATE',args.suite,step['name'],flush=True)
    candidate.interleave()
    assert not runtime._forbidden and not candidate.network_attempts
    if args.suite=='composition':assert 'stale direct object identity rejected atomically' in candidate.checks
    complete=args.phase=='reopen'
    if complete:
        compare(oracle['states'],states,'all_completed_stages')
        assert_witnesses(args.suite,states,compare)
    else:
        saved=dict(phase='populated_checkpoint',suite=args.suite,pid=os.getpid(),process_nonce=PROCESS_NONCE,session_id=candidate.session.session_id,states=states,checkpoint=candidate.sample(),durable=candidate.durable(),checks=candidate.checks)
        write(receipt,saved)
    write(args.output,dict(schema_version=1,phase='completed_after_reopen_cleanup' if complete else 'populated_checkpoint',suite=args.suite,pid=os.getpid(),process_nonce=PROCESS_NONCE,oracle_sha256=sha(args.oracle),states=states,budgets=candidate.budgets,checks=candidate.checks,previews=candidate.previews,canonical_edge_order=candidate.edge_orders,network_attempts=candidate.network_attempts,
        no_desktop_imports=not runtime._forbidden,strict_stats_per_fit=39,store_receipt=str(receipt),remaining_steps=[] if complete else steps[cut:]))
    print('PASS COMPLETE' if complete else 'PASS CHECKPOINT',args.suite,len(states),'stages',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',required=True,choices=('composition','incoming','outgoing','publication'))
    parser.add_argument('--oracle',type=Path,required=True);parser.add_argument('--store',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=('candidate','reopen'),required=True);parser.add_argument('--reverse',action='store_true')
    main(parser.parse_args())
