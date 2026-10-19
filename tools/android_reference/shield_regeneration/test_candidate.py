#!/usr/bin/env python3
"""Independent G04 durable-session comparison; default invocation is no-EOS tests.

Only --execute boots candidate production. Retained original receipts exclusively
supply numeric expectations. Instrumentation observes input state and work only.
"""
import argparse
import ast
from collections import Counter
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import fields, is_dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sqlite3
import sys
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import uuid

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO), str(REPO/'android/app/src/main/python')]
from tools.android_reference.shield_regeneration.cases import SUITES, FIELDS, fixtures, steps, requests, stage_names

REL_TOL, ABS_TOL = 1e-10, 1e-9
PROCESS_NONCE = uuid.uuid4().hex
PROGRESS = {}
PATTERN_FIELDS = ('em','thermal','kinetic','explosive')
GETTERS = ('Time2ShieldAmountGetter','Time2ShieldRegenGetter',
           'ShieldAmount2ShieldAmountGetter','ShieldAmount2ShieldRegenGetter')
SOURCE_ONLY = ('pattern_zero','pattern_zero_undo','pattern_zero_redo')
SKILL_INSPECTION_SHA='8c4c94fc5e015b2f31547821d9b3cec73067df3a83e90a96538d7cc306723bcb'


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def exact(expected, actual, label):
    assert encode(expected) == encode(actual), (label, expected, actual)


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value, exclusive=True):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')


def numeric(expected, actual, label):
    assert type(expected) in (int,float) and type(actual) in (int,float), label
    assert math.isfinite(expected) and math.isfinite(actual), label
    if expected == 0: assert actual == 0, (label,expected,actual)
    else: assert math.isclose(expected,actual,rel_tol=REL_TOL,abs_tol=ABS_TOL), (label,expected,actual)


def compare_curve(expected, actual, label):
    assert set(actual) == {'fit_id','revision','source','x','y'}, label
    assert type(actual['x']) is list and type(actual['y']) is list, label
    assert len(expected['x']) == len(expected['y']) == len(actual['x']) == len(actual['y']), label
    assert len(expected['x']) in (1,2,201), label
    for field in ('x','y'):
        assert all(type(v) in (int,float) and math.isfinite(v) for v in actual[field]), label
    # No tolerance, endpoint forcing, sorting or de-duplication, including EHP.
    exact(expected['x'],actual['x'],label+'.exact ordered source coordinates')
    for index,(left,right) in enumerate(zip(expected['y'],actual['y'])):
        numeric(left,right,label+'.y['+str(index)+']')
    xs=actual['x']
    assert all(a<=b for a,b in zip(xs,xs[1:])) or all(a>=b for a,b in zip(xs,xs[1:])), label


def compare_source(expected, actual, label):
    assert set(actual)=={'shield_capacity_hp','shield_recharge_seconds','damage_pattern'},label
    assert set(actual['damage_pattern'])==set(PATTERN_FIELDS),label
    exact('HP',expected['source_columns']['capacity']['unit'],label+' capacity unit')
    exact('s',expected['source_columns']['recharge']['unit'],label+' recharge unit')
    numeric(expected['source_columns']['capacity']['value'],actual['shield_capacity_hp'],label+' capacity')
    numeric(expected['source_columns']['recharge']['value'],actual['shield_recharge_seconds'],label+' recharge')
    for source,target in zip(FIELDS,PATTERN_FIELDS):
        numeric(expected['inputs']['damage_pattern'][source],actual['damage_pattern'][target],label+' '+target)


def frozen(value):
    if is_dataclass(value): return {f.name:frozen(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,dict): return {k:frozen(v) for k,v in value.items()}
    if isinstance(value,(set,frozenset)): return sorted(frozen(v) for v in value)
    if isinstance(value,(tuple,list)): return [frozen(v) for v in value]
    return value


def full_history(session):
    """Complete payloads plus sharing topology, not merely undo/redo counts."""
    legacy=session.graph._bridge._history; old_actions=[]; old_ids={}
    def old_ref(action):
        if id(action) not in old_ids:
            old_ids[id(action)]=len(old_actions); old_actions.append(frozen(action))
        return old_ids[id(action)]
    legacy_rows={key:dict(actions=[old_ref(a) for a in actions],cursor=cursor)
                 for key,(actions,cursor) in sorted(legacy.rows.items())}
    actions=[]; ids={}
    def action_ref(action):
        if id(action) not in ids:
            ids[id(action)]=len(actions); value=frozen(action)
            value['legacy_token_ref']=None if action.legacy_token is None else old_ref(action.legacy_token)
            actions.append(value)
        return ids[id(action)]
    rows={key:dict(actions=[action_ref(a) for a in values],cursor=cursor)
          for key,(values,cursor) in sorted(session.history.rows.items())}
    return dict(sequence=session.history.sequence,rows=rows,actions=actions,
                legacy_rows=legacy_rows,legacy_actions=old_actions)


def candidate_steps(suite):
    return [step for step in steps(suite) if step['name']!='pattern_zero']


def candidate_stages(suite):
    return [stage for stage in stage_names(suite) if stage not in SOURCE_ONLY]


def batches(order):
    return [order[index:index+8] for index in range(0,len(order),8)]


def wire_axes(row):
    return (dict(quantity='time' if row['x_handle']=='time' else 'shield_amount',unit=row['x_unit'],
                 input_unit='s' if row['x_handle']=='time' else '%',range=deepcopy(row['input_range'])),
            dict(quantity='shield_amount' if row['y_handle']=='shieldAmount' else 'shield_regen',unit=row['y_unit']))


def qualified_skill_difference(suite,stage,label,expected,actual):
    try:
        exact(expected,actual,'strict original/candidate skill inputs')
    except AssertionError:
        strict_mismatch=True
    else: return None
    assert suite=='history' and label in ('source_a','source_b'),'No general profile-history waiver'
    if stage=='management_four_undo':
        exact({'Capital Shield Operation':None},expected,'only original management-undo dependent artifact')
        exact({},actual,'candidate restores exact All-V management inputs')
        skill='Capital Shield Operation'
    else:
        assert stage=='operation_four_undo','No other stage qualification'
        exact({'Capital Shield Operation':None,'Caldari Defensive Systems':None},expected,'only original operation-undo dependent artifact')
        exact({'Capital Shield Operation':None},actual,'capital skill remains strictly aligned at operation undo')
        skill='Caldari Defensive Systems'
    return dict(stage=stage,fit=label,skill=skill,strict_comparison_failed=strict_mismatch,
                original=deepcopy(expected),candidate=deepcopy(actual),original_active_level=None,candidate_active_level=5)


def original_effective_level(source,active):
    path=Path(source)/'eos/saveddata/character.py'
    assert path.read_bytes()==(REPO/'eos/saveddata/character.py').read_bytes()
    cls=next(n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.ClassDef) and n.name=='Skill')
    node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='level')
    scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope)
    value=NS(character=NS(name='G04 original synthetic',alphaClone=None),activeLevel=active)
    return scope['level'].fget(value)


def frozen_inputs(oracle_path):
    product=list((REPO/'android_bridge').rglob('*.py'))+[REPO/'android/app/src/main/python/mobile_runtime.py']
    harness=[Path(__file__),Path(__file__).with_name('verify_candidate.py')]
    inspection=REPO.parent/'CANDIDATE-SKILL-DEPENDENCY-INSPECTION.json'
    assert sha(inspection)==SKILL_INSPECTION_SHA,'reviewed dependency-inspection bytes'
    return dict(oracle_sha256=sha(oracle_path),product_files={str(p.relative_to(REPO)):sha(p) for p in sorted(product)},
                harness_files={str(p.relative_to(REPO)):sha(p) for p in harness},skill_inspection_sha256=sha(inspection))


class ReadBoundary:
    def __init__(self,owner):
        self.owner=owner; self.rows=[]; self.active=None; self.depth=0; self.forbidden=[]

    @contextmanager
    def install(self):
        from eos.saveddata.fit import Fit
        from eos.capSim import CapSimulator
        from eos.utils.cycles import CycleInfo, CycleSequence
        from eos.const import CalcType
        from android_bridge.offline import shield_regeneration_math as graph
        saved_calc=Fit.calculateModifiedAttributes
        saved_prepare=self.owner.session.engine.prepare_read
        saved_range=graph.SmoothPointGetter.getRange
        def blocked(label):
            def stop(*args,**kwargs):
                self.forbidden.append(label); raise AssertionError('Forbidden G04 graph read: '+label)
            return stop
        def calculated(fit,*args,**kwargs):
            row=self.active; kind=kwargs.get('type',args[1] if len(args)>1 else CalcType.LOCAL)
            row['calculation_kinds'][CalcType(kind).name]+=1
            if self.depth==0: row['top_calculations'].append(dict(handle=id(fit),kind=CalcType(kind).name))
            self.depth+=1
            try: return saved_calc(fit,*args,**kwargs)
            finally: self.depth-=1
        def prepared(fit):
            row=self.active; before=len(row['top_calculations'])
            value=saved_prepare(fit)
            exact([dict(handle=id(fit),kind='LOCAL')],row['top_calculations'][before:],'one LOCAL preparation')
            row['prepares'].append(id(fit)); row['ready_handle']=id(fit)
            row['events'].append(dict(event='prepared',handle=id(fit)))
            return value
        def column(name,original):
            def value(column,fit):
                row=self.active; assert row['ready_handle']==id(fit),'source read before prepare'
                result=original(column,fit)
                row['events'].append(dict(event='source',column=name,handle=id(fit)))
                return result
            return value
        def ranged(getter,*args,**kwargs):
            src=kwargs.get('src',args[2] if len(args)>2 else None); fit=src.item; row=self.active
            assert row['ready_handle']==id(fit),'curve before same-fit preparation'
            assert len(row['prepares'])==len(row['curves'])+1,'exactly one prepare per curve'
            exact([dict(handle=h,kind='LOCAL') for h in row['prepares']],row['top_calculations'],'no hidden top-level recalculation')
            source_events=row['events'][-3:]
            assert source_events[0]==dict(event='prepared',handle=id(fit))
            exact(['capacity','recharge'],sorted(e['column'] for e in source_events[1:]),'both source columns before curve')
            before=row['point_calls']; value=saved_range(getter,*args,**kwargs)
            row['curves'].append(dict(handle=id(fit),getter=type(getter).__name__,points=len(value[0]),point_calls=row['point_calls']-before))
            assert row['curves'][-1]['point_calls']==len(value[0])
            row['ready_handle']=None
            return value
        with ExitStack() as stack:
            for cls,names in ((Fit,('simulateCap','_Fit__runCapSim','getCapSimData','calculateSustainableTank')),
                              (CapSimulator,('run',)),(CycleInfo,('iterCycles',)),(CycleSequence,('iterCycles',))):
                for name in names: stack.enter_context(patch.object(cls,name,blocked(cls.__name__+'.'+name)))
            for name in ('capUsed','capRecharge','capStable','capState','capDelta','tank','effectiveTank','sustainableTank','effectiveSustainableTank'):
                stack.enter_context(patch.object(Fit,name,property(blocked('Fit.'+name))))
            for cls,name in ((Fit,'_Fit__generateDrain'),(CapSimulator,'reset')):
                original=getattr(cls,name)
                def counted(*args,original=original,name=name,**kwargs):
                    self.active['admission_work'][name]+=1
                    return original(*args,**kwargs)
                stack.enter_context(patch.object(cls,name,counted))
            stack.enter_context(patch.object(Fit,'calculateModifiedAttributes',calculated))
            stack.enter_context(patch.object(self.owner.session.engine,'prepare_read',prepared))
            stack.enter_context(patch.object(graph.SmoothPointGetter,'getRange',ranged))
            for name in GETTERS:
                cls=getattr(graph,name); original=cls._calculatePoint
                def pointed(*args,original=original,**kwargs):
                    self.active['point_calls']+=1
                    return original(*args,**kwargs)
                stack.enter_context(patch.object(cls,'_calculatePoint',pointed))
            for name,column_name in (('ShieldAmountColumn','capacity'),('ShieldTimeColumn','recharge')):
                cls=getattr(graph,name)
                stack.enter_context(patch.object(cls,'_getValue',column(column_name,cls._getValue)))
            yield

    @contextmanager
    def measure(self,request):
        assert self.active is None
        row=dict(stage=self.owner.stage,request=deepcopy(request),prepares=[],top_calculations=[],
                 calculation_kinds=Counter(),admission_work=Counter(),events=[],curves=[],ready_handle=None,point_calls=0)
        self.active=row; started=time.monotonic()
        try:
            with self.install(): yield row
        finally:
            row['elapsed_seconds']=time.monotonic()-started; self.rows.append(row); self.active=None


class Candidate:
    def __init__(self,args,oracle):
        self.args=args; self.oracle=oracle; self.stage='startup'; self.states={}; self.failures=[]
        self.checks=[]; self.history_proof=[]; self.network_attempts=[]; self.raw_identity=[]; self.skill_differences=[]
        def network(event,values):
            if event in {'socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo'}:
                self.network_attempts.append(event); raise AssertionError('Offline candidate: '+event)
        sys.addaudithook(network)
        import mobile_runtime as runtime
        self.runtime=runtime; database=Path(os.environ['PYFA_DATABASE']).resolve()
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as connection:
            metadata=dict(connection.execute('SELECT field_name,field_value FROM metadata'))
        self.order=oracle['input_order']; self.specs=fixtures(args.suite)
        for label,spec in self.specs.items(): spec['modules']=deepcopy(oracle['states']['initial']['raw'][label]['modules'])
        runtime.boot(str(database),json.dumps(dict(dataset_metadata=metadata,database_logical_sha256=os.environ['PYFA_DATASET_SHA'])),
                     json.dumps(dict(self.specs[self.order[0]],edit={})),str(args.store))
        boot=json.loads(runtime.bridge_bootstrap()); assert boot['status']=='ok',boot
        self.session=runtime._bridge
        from android_bridge.offline.native_session import NativeSession
        assert type(self.session) is NativeSession,'durable public NativeSession required'
        self.ids={r['name'].removeprefix('G04 original '):r['id'] for r in boot['fits']}
        if args.phase=='seed':
            for label in self.order[1:]:
                result=self.edit('create_fit',dict(spec=self.specs[label])); self.ids[label]=result['fits'][0]['id']
        exact(sorted(self.order),sorted(self.ids),'all durable fixture identities')
        self.labels={value:key for key,value in self.ids.items()}; self.boundary=ReadBoundary(self)

    def item(self,name):
        import eos.db
        value=eos.db.getItem(name); assert value is not None,name
        return value.ID

    def edit(self,operation,arguments,success=True):
        ids={arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}
        request=dict(version=1,request_id='g04-'+operation,session_id=self.session.session_id,operation=operation,
                     arguments=arguments,expected_revisions={key:self.session._revisions[key] for key in ids})
        result=json.loads(self.runtime.bridge_dispatch(json.dumps(request)))
        if success: assert result['status']=='ok',(operation,result)
        else: assert result['status']=='error',(operation,result)
        return result

    def feature(self,operation,arguments):
        request=dict(version=1,request_id='g04-'+operation,context=self.session.context(),operation=operation,
                     arguments=arguments,anchor_fit_id=self.ids['source_a'])
        result=json.loads(self.runtime.offline_feature_dispatch(json.dumps(request)))
        assert result['ok'],(operation,result)
        return result

    def apply(self,step):
        op,args=step['op'],step['args']; key=self.ids.get(args.get('fit'))
        if op=='state':
            rows=self.session._records[key]['spec']['modules']
            index=next(i for i,row in enumerate(rows) if row.get('name')==args['item'])
            return self.edit('set_module_states',dict(fit_id=key,module_indices=[index],state=args['state']))
        if op=='share_profile':
            self.feature('create_profile',dict(name='G04 shared all V',source='builtin:all5'))
            profile=next(row['profile_id'] for row in self.session.feature_state()['profiles'] if row['name']=='G04 shared all V')
            for label in ('source_a','source_b'): result=self.feature('assign_profile',dict(fit_id=self.ids[label],profile_id=profile))
            return result
        if op=='skill':
            profile=self.session.feature_state()['bindings'][self.ids['source_a']]['profile_id']
            row=next(row for row in self.session.feature_state()['profiles'] if row['profile_id']==profile)
            return self.feature('set_profile_skill',dict(profile_id=profile,revision=row['revision'],skill_id=self.item(args['skill']),level=args['level']))
        if op=='pattern': return self.edit('set_damage_pattern',dict(fit_id=key,pattern=dict(zip(FIELDS,args['values']))))
        raise AssertionError(op)

    def raw(self,label):
        from eos.const import FittingModuleState,FittingSlot
        fit=self.session.graph._bridge._fits[self.ids[label]]
        assert not any((fit.projectedModules,fit.projectedDrones,fit.projectedFighters,fit.projectedFits,fit.commandFits,fit.implants,fit.boosters,fit.fighters))
        modules=[dict(empty_slot=FittingSlot(m.slot).name) if m.isEmpty else dict(name=m.item.name,
                 state=FittingModuleState(m.state).name,charge=m.charge.name if m.charge else None) for m in fit.modules]
        return dict(name=fit.name,ship=fit.ship.item.name,modules=modules,
            drones=[dict(name=d.item.name,amount=d.amount,active=d.amountActive) for d in fit.drones],
            projected_modules=[],projected_drones=[],projected_fighters=[],projections=[],
            skills={s.item.name:s.activeLevel for s in fit.character.skills if s.activeLevel!=5},
            damage_pattern={name:getattr(fit.damagePattern,name) for name in FIELDS},
            factor_reload=fit.factorReload,character_id=fit.character.ID)

    def verify_raw(self,stage):
        expected=self.oracle['states'][stage]['raw']; actual={label:self.raw(label) for label in self.order}
        exact(sorted(expected),sorted(actual),'raw fit set '+stage)
        for label,want in expected.items():
            got=actual[label]; exact(sorted(want),sorted(got),'raw keys '+stage+'.'+label)
            for field in set(want)-{'character_id','skills'}: exact(want[field],got[field],stage+'.'+label+'.'+field)
            difference=qualified_skill_difference(self.args.suite,stage,label,want['skills'],got['skills'])
            if difference is not None:
                difference.update(self.skill_qualification(label,difference['skill']))
                self.skill_differences.append(difference)
            assert type(got['character_id']) is int and got['character_id']>0
            self.raw_identity.append(dict(stage=stage,fit=label,original_character_id=want['character_id'],candidate_character_id=got['character_id']))
        if self.args.suite=='history' and stage not in ('initial','hardener_online','hardener_online_undo','hardener_online_redo','hardener_active','extender_offline','extender_offline_undo','extender_offline_redo','extender_online'):
            bindings=self.session.feature_state()['bindings']
            exact(bindings[self.ids['source_a']]['profile_id'],bindings[self.ids['source_b']]['profile_id'],'shared durable profile identity')
            assert bindings[self.ids['unrelated']]['profile_id']!=bindings[self.ids['source_a']]['profile_id']
        return actual

    def skill_qualification(self,label,skill_name):
        """Live narrow-source proof; does not claim equivalence of profile histories."""
        path=REPO.parent/'CANDIDATE-SKILL-DEPENDENCY-INSPECTION.json'
        assert sha(path)==SKILL_INSPECTION_SHA
        inspection=json.loads(path.read_text())
        exact(self.oracle['dataset_sha256'],inspection['database_file_sha256'],'dependency evidence database bytes')
        for relative,digest in inspection['source_files'].items():
            assert sha(REPO/relative)==sha(Path(self.oracle['source'])/relative)==digest,relative
        fit=self.session._fits[self.ids[label]]; rows={row['type_id']:row for row in inspection['types']}
        occupied=[fit.ship.item]+[module.item for module in fit.modules if not module.isEmpty]
        exact([626,2281] if label=='source_a' else [626,3841],[item.ID for item in occupied],'exact qualified hull/occupied module identities')
        live=[]; consumer_effects={3964,3976,6941,6945,6947}
        for item in occupied:
            effects=sorted((effect.ID,effect.name) for effect in item.effects.values())
            requirements={str(skill.ID):level for skill,level in item.requiredSkills.items()}
            exact(rows[item.ID]['effects'],effects,'live effects match exact source database')
            exact(rows[item.ID]['required_skills'] or {},requirements,'live requirements match exact source database')
            assert not item.requiresSkill('Capital Shield Operation') and not item.requiresSkill('Caldari Defensive Systems')
            assert not consumer_effects.intersection(effect.ID for effect in item.effects.values())
            live.append(dict(type_id=item.ID,name=item.name,effects=effects,required_skills=requirements))
        from eos import effects
        for identity,disposition in inspection['skill_effect_implementation'].items():
            implemented=getattr(effects,'Effect'+identity,None) is not None
            assert implemented==(disposition=='implemented'),identity
        assert inspection['skill_effect_implementation']['1634']=='implemented'
        skill=fit.character.getSkill(skill_name)
        exact(rows[skill.item.ID]['effects'],sorted((effect.ID,effect.name) for effect in skill.item.effects.values()),'live qualified skill effect set')
        exact(rows[skill.item.ID]['required_skills'],{str(item.ID):level for item,level in skill.item.requiredSkills.items()},'live qualified skill prerequisites')
        assert skill.activeLevel==skill.level==5
        exact(0,original_effective_level(self.oracle['source'],None),'source unlearned effective level')
        exact(5,original_effective_level(self.oracle['source'],5),'source restored effective level')
        return dict(original_effective_level=0,candidate_effective_level=skill.level,
                    source_files=inspection['source_files'],inspection_sha256=SKILL_INSPECTION_SHA,live_occupied=live,
                    qualification='Only these two Vexor/module fixtures: exact typed-input candidate undo restores dependent skill; original setLevel restoration leaves it unlearned. The relevant original skill effect is absent from occupied effects or changes only capacitorNeed on absent capital-requiring modules. This is not profile-history equivalence.')

    def state(self,identities=True):
        graph=self.session.graph; bridge=graph._bridge
        result=dict(graph=deepcopy(graph._state),snapshots=deepcopy(bridge._snapshots),records=deepcopy(bridge._records),
            revisions=deepcopy(bridge._revisions),modified=deepcopy(bridge._modified),recent=deepcopy(bridge._recent),
            sample_id=bridge.sample_id,store_current=frozen(graph._store.current),file_sha256=sha(self.args.store),
            full_history=full_history(self.session),session_id=bridge.session_id,revision_floor=deepcopy(graph._revision_floor),
            profile_floor=deepcopy(self.session._profile_floor),binding_floor=deepcopy(self.session._binding_floor),
            raw={label:self.raw(label) for label in self.order})
        if identities:
            result['live_identities']=dict(fits={k:id(v) for k,v in bridge._fits.items()},engine_fits=[id(v) for v in self.session.engine._fits],
                modules={k:[id(m) for m in v.modules] for k,v in bridge._fits.items()},
                characters={k:id(v.character) for k,v in bridge._fits.items()},
                integrated_actions={k:[id(a) for a in actions] for k,(actions,_) in self.session.history.rows.items()},
                legacy_actions={k:[id(a) for a in actions] for k,(actions,_) in bridge._history.rows.items()})
        return result

    def durable(self):
        return dict(graph=deepcopy(self.session.graph._state),snapshots=deepcopy(self.session.graph._bridge._snapshots),
                    store_current=frozen(self.session._store.current),file_sha256=sha(self.args.store))

    def captured(self):
        from android_bridge.offline.graph_history import inputs
        return inputs(self.session.graph._state)

    def request(self,row,order):
        x,y=wire_axes(row)
        return dict(version=1,request_id='g04-'+self.stage+'-'+row['name'],context=self.session.context(),
            fits=[dict(fit_id=self.ids[label],revision=self.session._revisions[self.ids[label]]) for label in order],
            x=x,y=y,effective=row['effective'],starting_shield_percent=row['starting_shield_percent'],budget_ms=10000)

    def read(self,request,cancelled=lambda:False,stable=True,checks=2):
        before=self.state(); raw_bytes=self.args.store.read_bytes(); verify=self.session.graph._verify_durable
        with self.boundary.measure(request) as measured,patch.object(self.session.graph,'_verify_durable',wraps=verify) as verified:
            text=request if type(request) is str else json.dumps(request)
            response=json.loads(self.runtime.offline_shield_regeneration_samples(text,NS(get=cancelled)))
        measured['durable_checks']=verified.call_count; measured['result_ok']=response['ok']
        assert verified.call_count==checks,('durable pre/post verification count',verified.call_count,checks)
        if stable:
            exact(before,self.state(),'read preserved complete raw/history/identity/store state')
            assert self.args.store.read_bytes()==raw_bytes
        assert not self.boundary.forbidden
        return response,measured

    def observe(self,stage,record=True):
        self.stage=stage; expected=self.oracle['states'][stage]; raw=self.verify_raw(stage)
        rows=requests(self.args.suite,stage=='initial')
        exact(rows,next(row['requests'] for row in self.oracle['request_trace'] if row['stage']==stage),'original request schedule')
        forward={}
        for direction,order in (('forward',self.order),('reverse',list(reversed(self.order)))):
            curves={label:[] for label in order}
            for index,row in enumerate(rows):
                for batch in batches(order):
                    request=self.request(row,batch); response,work=self.read(request)
                    assert response['ok'],response
                    assert set(response)=={'version','request_id','ok','context','x','y','effective','starting_shield_percent','total_points','series','error'}
                    exact(1,response['version'],'version'); exact(request['request_id'],response['request_id'],'request id')
                    for field in ('context','x','y','effective','starting_shield_percent'): exact(request[field],response[field],'echo '+field)
                    assert response['error'] is None and len(response['series'])==len(batch)
                    exact([self.ids[label] for label in batch],[series['fit_id'] for series in response['series']],'selected order')
                    exact(sum(len(series['x']) for series in response['series']),response['total_points'],'complete point count')
                    exact([id(self.session._fits[self.ids[label]]) for label in batch],work['prepares'],'one LOCAL prepare per selected fit')
                    assert len(work['curves'])==len(batch)
                    for label,series in zip(batch,response['series']):
                        want=expected['fits'][label]
                        exact(self.session._revisions[self.ids[label]],series['revision'],'revision identity')
                        compare_source(want,series['source'],stage+'.'+label)
                        compare_curve(want['curves'][index],series,stage+'.'+label+'.'+row['name'])
                        curves[label].append(series)
            if direction=='forward': forward=curves
            else: exact(forward,curves,'reverse fit/batch order independence '+stage)
        value=dict(fits=forward,raw=raw,durable=self.durable(),history=full_history(self.session))
        if record: self.states[stage]=value
        self.checks.append(dict(stage=stage,forward_reverse_equal=True,exact_read_state_preserved=True))
        print('CANDIDATE G04',self.args.suite,stage,flush=True)
        return value

    def failures_matrix(self):
        from android_bridge.offline import shield_regeneration_math as graph
        from android_bridge.offline import shield_regeneration_samples as sampling
        from android_bridge.projected_drone_admission import AdmissionRejected
        label=self.order[0]; baseline=self.request(requests(self.args.suite)[0],[label])
        def rejected(name,request,code,cancelled=lambda:False,checks=2):
            response,work=self.read(request,cancelled,checks=checks)
            assert set(response)=={'version','request_id','ok','error'} and response['ok'] is False,response
            exact(code,response['error']['code'],name)
            self.failures.append(dict(kind=name,result=response,durable_checks=work['durable_checks'],point_calls=work['point_calls'],state_preserved=True))
            return work
        value=deepcopy(baseline); value['context']['generation']+=1
        rejected('stale_context',value,'stale_context')
        value=deepcopy(baseline); value['fits'][0]['revision']+=1
        rejected('stale_revision',value,'stale_fit')
        value=deepcopy(baseline); value['fits'][0]['fit_id']='missing-synthetic-fit'
        rejected('missing_fit',value,'fit_not_found')
        value=deepcopy(baseline); value['unexpected']=True
        rejected('unknown_field',value,'invalid_request')
        value=deepcopy(baseline); value['fits']*=2
        rejected('duplicate_fit',value,'invalid_request')
        value=deepcopy(baseline); value['x']['range'][0]=True
        rejected('boolean_endpoint',value,'invalid_request')
        value=deepcopy(baseline); value['effective']=not value['effective']
        rejected('effectivity_unit_mismatch',value,'invalid_request')
        rejected('duplicate_json_key',json.dumps(baseline)[:-1]+',"version":1}','invalid_request',checks=0)
        rejected('cancelled_before_prepare',baseline,'cancelled',lambda:True)
        # Standard time request ensures a multi-point curve even for boundary suites.
        standard=self.request(requests('history')[0],[label])
        work=rejected('cancelled_during_points',standard,'cancelled',lambda:self.boundary.active is not None and self.boundary.active['point_calls']>=3)
        assert work['point_calls']==3 and len(work['prepares'])==1 and not work['curves']
        multiple=self.request(requests('history')[0],self.order[:2])
        work=rejected('cancelled_second_fit_after_completed_first',multiple,'cancelled',
                      lambda:self.boundary.active is not None and self.boundary.active['point_calls']>=204)
        assert work['point_calls']==204 and len(work['prepares'])==2 and len(work['curves'])==1
        original_sampler=sampling.sample_shield_regeneration
        def expired(*args,**kwargs):
            kwargs['clock']=lambda:1.0 if self.boundary.active['point_calls']>=2 else 0.0
            return original_sampler(*args,**kwargs)
        value=deepcopy(standard); value['budget_ms']=1
        with patch.object(sampling,'sample_shield_regeneration',expired):
            work=rejected('deadline_during_points',value,'deadline_exceeded')
        assert work['point_calls']==2 and len(work['prepares'])==1 and not work['curves']
        with patch.object(graph.Time2ShieldRegenGetter,'_calculatePoint',side_effect=RuntimeError('Injected graph calculation error')):
            rejected('point_engine_error',standard,'engine_error')
        with patch.object(self.session.engine,'_recalculate',side_effect=RuntimeError('Injected prepare error')):
            rejected('prepare_error',standard,'engine_error')
        with patch.object(self.session.engine,'_recalculate',side_effect=AdmissionRejected('Injected inherited admission refusal')):
            rejected('admission_resource_refusal',standard,'resource_exhausted')
        original_point=graph.Time2ShieldRegenGetter._calculatePoint
        def second_fit_error(*args,**kwargs):
            if len(self.boundary.active['prepares'])==2: raise RuntimeError('Injected error after first complete fit')
            return original_point(*args,**kwargs)
        with patch.object(graph.Time2ShieldRegenGetter,'_calculatePoint',second_fit_error):
            work=rejected('second_fit_error_no_partial_publication',multiple,'engine_error')
        assert work['point_calls']==202 and len(work['prepares'])==2 and len(work['curves'])==1
        value=deepcopy(standard); value['x']['range']=[-1e308,-1e308]
        rejected('source_arithmetic_overflow',value,'invalid_engine_data')
        for name in ('replaced_handle','missing_handle_during_read','revision_during_read','context_during_read'):
            before=self.state(); raw_bytes=self.args.store.read_bytes(); key=self.ids[label]
            fits=self.session.graph._bridge._fits; revisions=self.session.graph._bridge._revisions
            handle,revision=fits[key],revisions[key]; context=self.session.context
            original_range=graph.SmoothPointGetter.getRange; changed=[]
            def ranged(*args,**kwargs):
                result=original_range(*args,**kwargs)
                if name=='replaced_handle': fits[key]=object()
                elif name=='missing_handle_during_read': del fits[key]
                elif name=='revision_during_read': revisions[key]+=1
                changed.append(name); return result
            def current_context():
                value=context()
                return dict(value,generation=value['generation']+1) if changed else value
            try:
                with ExitStack() as injection:
                    if name=='context_during_read': injection.enter_context(patch.object(self.session,'context',current_context))
                    injection.enter_context(patch.object(graph.SmoothPointGetter,'getRange',ranged))
                    response,work=self.read(standard,stable=False)
                assert response['ok'] is False and set(response)=={'version','request_id','ok','error'},response
                code='stale_context' if name=='context_during_read' else 'fit_not_found' if name=='missing_handle_during_read' else 'stale_fit'
                exact(code,response['error']['code'],name); exact([name],changed,'controlled injection executed')
            finally:
                fits[key]=handle; revisions[key]=revision
                if 'context' in self.session.__dict__: del self.session.__dict__['context']
            exact(before,self.state(),'injection restored exact state'); assert self.args.store.read_bytes()==raw_bytes
            self.failures.append(dict(kind=name,result=response,state_preserved_after_restoring_injection=True))
        self.checks.append(dict(failure_matrix=True,no_partial_results=True))

    def rejected_mutations(self):
        label=self.order[0]; key=self.ids[label]; before=self.state(); raw_bytes=self.args.store.read_bytes()
        zero=self.edit('set_damage_pattern',dict(fit_id=key,pattern=dict.fromkeys(FIELDS,0)),success=False)
        exact(before,self.state(),'zero-total rejection preserved complete state'); assert self.args.store.read_bytes()==raw_bytes
        self.failures.append(dict(kind='zero_total_mutation_remains_unsupported',result=zero,state_preserved=True))
        # This must be a genuine save rejection after mutation/rebuild work, not invalid-input rejection.
        before=self.state(identities=False); raw_bytes=self.args.store.read_bytes()
        with patch.object(self.session._store,'write',side_effect=OSError('Injected before durable commit')) as writing:
            result=self.edit('set_damage_pattern',dict(fit_id=key,pattern=dict(zip(FIELDS,[2,3,5,7]))),success=False)
        assert writing.call_count==1 and self.session._available,'rollback must recover the existing session'
        after=self.state(identities=False)
        # EOS database character IDs are process-local reconstructed objects, never persisted fit input.
        for state in (before,after):
            for row in state['raw'].values(): row.pop('character_id')
        exact(before,after,'failed supported edit restored complete logical state/history')
        assert self.args.store.read_bytes()==raw_bytes
        self.failures.append(dict(kind='rejected_durable_mutation',result=result,write_calls=writing.call_count,exact_logical_state_history_bytes_preserved=True))
        self.observe('initial',record=False)

    def terminal_durable_failure(self):
        from android_bridge.offline import shield_regeneration_math as graph
        from android_bridge.offline import shield_regeneration_samples as sampling
        # All six allowed processes own one terminal case, after useful persisted work.
        cases={('defenses','seed'):('success',1),('defenses','reopen'):('success',2),
               ('boundaries','seed'):('cancelled',1),('boundaries','reopen'):('cancelled',2),
               ('history','seed'):('engine_error',1),('history','reopen'):('engine_error',2)}
        mode,fail_on=cases[self.args.suite,self.args.phase]
        request=self.request(requests('history')[0],[self.order[0]])
        original_sampler=sampling.sample_shield_regeneration; results=[]
        def sample(*args,**kwargs):
            result=original_sampler(*args,**kwargs); results.append(deepcopy(result)); return result
        original_read=self.session._store._read; calls=[]
        def failed():
            calls.append(len(calls)+1)
            if len(calls)==fail_on: raise OSError('Injected durable read verification failure')
            return original_read()
        before=self.state(); raw_bytes=self.args.store.read_bytes()
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.session._store,'_read',side_effect=failed))
            stack.enter_context(patch.object(sampling,'sample_shield_regeneration',sample))
            if mode=='engine_error': stack.enter_context(patch.object(graph.Time2ShieldRegenGetter,'_calculatePoint',side_effect=RuntimeError('Injected graph point error')))
            with self.boundary.measure(request) as work:
                response=json.loads(self.runtime.offline_shield_regeneration_samples(json.dumps(request),NS(get=lambda:mode=='cancelled')))
        assert response['ok'] is False and set(response)=={'version','request_id','ok','error'},response
        exact('reopen_required',response['error']['code'],'durable verification failure')
        if fail_on==1:
            assert not results and work['point_calls']==0 and not work['curves'],'no sampler after failed precheck'
        else:
            assert len(results)==1
            if mode=='success': assert results[0]['ok'] is True and work['point_calls']>0 and len(work['curves'])==1
            else:
                exact(mode,results[0]['error']['code'],'underlying sampler result')
                assert work['point_calls']==(1 if mode=='engine_error' else 0) and not work['curves']
        assert len(calls)==fail_on and not self.session._available
        exact(before,self.state(),'terminal durable failure preserves complete state'); assert self.args.store.read_bytes()==raw_bytes
        self.failures.append(dict(kind='terminal_durable_read',underlying_result=mode,fail_on_check=fail_on,
            actual_read_calls=calls,result=response,sampler_results=results,disabled=True,exact_state_and_bytes_preserved=True,
            point_calls=work['point_calls'],completed_curves=len(work['curves'])))


def verify_oracle(args,oracle):
    assert oracle['status']=='passed' and oracle['suite']==args.suite and oracle['process_nonce']!=PROCESS_NONCE
    exact(fixtures(args.suite),oracle['inputs'],'same original declared input specs')
    exact(steps(args.suite),oracle['steps'],'same complete original schedule')
    exact(list(SOURCE_ONLY) if args.suite=='history' else [],oracle['source_only_stages'],'explicit source-only stages')
    exact(sorted(stage_names(args.suite)),sorted(oracle['states']),'complete original stage oracle')
    assert oracle['network_attempts']==oracle['forbidden_attempts']==[]
    for path,digest in {**oracle['source_files'],**oracle['original_imports']}.items():
        assert sha(Path(oracle['source'])/path)==sha(REPO/path)==digest,path
    for path,digest in {**oracle['harness_files'],**oracle['fixture_files']}.items(): assert sha(REPO/path)==digest,path
    for trace in oracle['request_trace']: exact(requests(args.suite,trace['stage']=='initial'),trace['requests'],'original request schedule')


def run(args):
    started=time.monotonic(); oracle=json.loads(args.oracle.read_text()); verify_oracle(args,oracle); input_binding=frozen_inputs(args.oracle)
    assert resource.getrlimit(resource.RLIMIT_AS)[0]==1024**3
    database=Path(os.environ['PYFA_DATABASE']).resolve(); before_database=sha(database)
    # The original receipt distinguishes retained dataset physical bytes from its logical identity.
    expected_database=oracle['dataset_sha256']
    exact(oracle['logical_dataset_sha256'],os.environ['PYFA_DATASET_SHA'],'same retained logical dataset identity')
    assert before_database==expected_database,'same read-only retained game database bytes'
    if args.phase=='seed': assert not args.store.exists()
    before_store=args.store.read_bytes() if args.store.exists() else None
    checkpoint=Path(str(args.store)+'.checkpoint.json')
    if args.phase=='reopen':
        saved=json.loads(checkpoint.read_text()); exact(input_binding,saved['input_binding'],'reopen exact product/harness/oracle/inspection bytes')
    candidate=Candidate(args,oracle)
    PROGRESS.update(states=candidate.states,failures=candidate.failures,checks=candidate.checks,reads=candidate.boundary.rows)
    exact(oracle['settings'],candidate.session.engine.settings,'EOS settings')
    exact(oracle['dataset_metadata'],candidate.session.engine.metadata,'dataset metadata')
    for name,item_id in oracle['resolved_item_ids'].items(): exact(item_id,candidate.item(name),'resolved source identity '+name)
    schedule=candidate_steps(args.suite)
    cut=next(i for i,step in enumerate(schedule) if step['name']=='management_four')+1 if schedule else 0
    checkpoint=Path(str(args.store)+'.checkpoint.json')
    if args.phase=='seed':
        candidate.observe('initial'); candidate.failures_matrix(); candidate.rejected_mutations()
        chosen=schedule[:cut]; previous='initial'
    else:
        saved=json.loads(checkpoint.read_text())
        assert saved['process_nonce']!=PROCESS_NONCE and saved['session_id']!=candidate.session.session_id
        assert args.store.read_bytes()==before_store
        exact(saved['durable'],candidate.durable(),'fresh process exact durable graph/snapshots/store bytes')
        assert candidate.session.history.sequence==0 and not candidate.session.history.rows and not candidate.session.graph._bridge._history.rows
        for key in candidate.ids.values():
            assert candidate.session.history_details(key)['undo_count']==candidate.session.history_details(key)['redo_count']==0
        response,_=candidate.read(saved['last_request']); assert response['ok'] is False and response['error']['code']=='stale_context'
        candidate.states.update(saved['states']); candidate.history_proof.extend(saved['history_proof']); candidate.raw_identity.extend(saved['raw_identity']); candidate.skill_differences.extend(saved['skill_differences'])
        candidate.observe(saved['last_stage'],record=False)
        candidate.checks.append(dict(fresh_process_reopen=True,exact_durable_graph_and_bytes=True,old_session_request_rejected=True,
                                    session_identity_changed=True,transient_histories_empty=True))
        chosen=schedule[cut:]; previous=saved['last_stage']
    for step in chosen:
        name=step['name']; details=step['args']; owner=details.get('fit','source_a'); fit_id=candidate.ids[owner]
        old_request=candidate.request(requests(args.suite)[0],[candidate.order[0]])
        before=candidate.captured(); count=candidate.session.history_details(fit_id)['undo_count'] if details.get('history') else None
        candidate.apply(step); after=candidate.captured(); candidate.observe(name)
        response,_=candidate.read(old_request)
        assert response['ok'] is False and response['error']['code']=='stale_context','pre-edit result request is stale'
        if details.get('history'):
            assert candidate.session.history_details(fit_id)['undo_count']==count+1,'exactly one integrated history action'
            candidate.edit('undo',dict(fit_id=fit_id)); exact(before,candidate.captured(),'complete input undo '+name)
            candidate.observe(name+'_undo')
            candidate.edit('redo',dict(fit_id=fit_id)); exact(after,candidate.captured(),'complete input redo '+name)
            candidate.observe(name+'_redo')
            candidate.history_proof.append(dict(stage=name,owner=owner,one_action=True,typed_input_undo_redo=True,before=before,after=after))
            previous=name+'_redo'
        else: previous=name
        write(str(args.output)+'.partial.json',dict(stage=previous,states=candidate.states,reads=candidate.boundary.rows,
              failures=candidate.failures,history_proof=candidate.history_proof),exclusive=False)
    if args.phase=='seed':
        write(checkpoint,dict(process_nonce=PROCESS_NONCE,session_id=candidate.session.session_id,durable=candidate.durable(),
            last_stage=previous,states=candidate.states,history_proof=candidate.history_proof,raw_identity=candidate.raw_identity,
            skill_differences=candidate.skill_differences,input_binding=input_binding,
            last_request=candidate.request(requests(args.suite)[0],[candidate.order[0]])))
    else: exact(sorted(candidate_stages(args.suite)),sorted(candidate.states),'all supported original stages compared')
    candidate.terminal_durable_failure()
    assert not candidate.runtime._forbidden and not candidate.network_attempts and not candidate.boundary.forbidden
    assert sha(database)==before_database,'retained read-only database unchanged'
    curves=sum(len(rows) for state in candidate.states.values() for rows in state['fits'].values())
    points=sum(len(curve['x']) for state in candidate.states.values() for rows in state['fits'].values() for curve in rows)
    if args.phase=='reopen':
        wanted=[oracle['states'][stage] for stage in candidate_stages(args.suite)]
        exact(sum(len(fit['curves']) for state in wanted for fit in state['fits'].values()),curves,'all supported curves')
        exact(sum(len(curve['x']) for state in wanted for fit in state['fits'].values() for curve in fit['curves']),points,'all supported coordinates')
    exact(input_binding,frozen_inputs(args.oracle),'frozen code and oracle unchanged throughout process')
    result=dict(status='passed',suite=args.suite,phase=args.phase,pid=os.getpid(),process_nonce=PROCESS_NONCE,
        oracle_sha256=sha(args.oracle),original_process_nonce=oracle['process_nonce'],states=candidate.states,
        checks=candidate.checks,failures=candidate.failures,history_proof=candidate.history_proof,
        process_local_character_identities=candidate.raw_identity,original_skill_undo_differences=oracle['skill_undo_differences'],
        qualified_skill_differences=candidate.skill_differences,skill_inspection_sha256=SKILL_INSPECTION_SHA,
        checkpoint_path=str(checkpoint.resolve()),checkpoint_sha256=sha(checkpoint),input_binding=input_binding,
        reads=candidate.boundary.rows,recorded_stages=len(candidate.states),
        recorded_fit_observations=sum(len(state['fits']) for state in candidate.states.values()),recorded_curves=curves,recorded_points=points,
        actual_point_calls=sum(row['point_calls'] for row in candidate.boundary.rows),
        network_attempts=candidate.network_attempts,forbidden_attempts=candidate.boundary.forbidden,no_desktop_imports=not candidate.runtime._forbidden,
        source_qualification=oracle['source_kind'],dataset_file_sha256=before_database,dataset_after_file_sha256=sha(database),
        product_files=input_binding['product_files'],harness_files=input_binding['harness_files'],
        tolerance=dict(coordinates='exact typed binary64 values, all EHP endpoints/interiors, order, duplicate occurrences and count',
                       relative=REL_TOL,absolute=ABS_TOL,zero='exact'),
        limits=dict(address_space_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],external_timeout_seconds=180,per_request_budget_ms=10000,max_fits=8,max_points_per_fit=201),
        coverage_limitations=['Finite synthetic inputs; no universal gameplay or engine-work bound',
            'Original pattern_zero stages are source-only; positive-total mutation contract unchanged',
            'Process-local character numeric IDs differ; persisted profile sharing is checked',
            'Two named original skill-undo stages retain exact qualified dependent-skill differences; no profile-history equivalence',
            'Transient undo/redo history intentionally starts empty after a fresh process reopen',
            'Read instrumentation excludes fixture boot/mutation snapshots; inherited admission reset/drain are counted',
            'Clean-pin dataset, Android execution and release qualification remain open'],
        elapsed_seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    write(args.output,result)
    print('PASS G04',args.phase,args.suite,len(candidate.states),'stages',curves,'curves',points,'points',flush=True)


class PureCandidateTests(unittest.TestCase):
    def curve(self,n=201):
        expected=dict(x=[float(i) for i in range(n)],y=[float(i)/10 for i in range(n)])
        actual=dict(fit_id='synthetic',revision=1,source=dict(shield_capacity_hp=100.0,
                    shield_recharge_seconds=50.0,damage_pattern=dict.fromkeys(PATTERN_FIELDS,25.0)),
                    x=deepcopy(expected['x']),y=deepcopy(expected['y']))
        return expected,actual

    def test_exact_preserves_numeric_type_and_boolean(self):
        for actual in (0,False,1e-15):
            with self.assertRaises(AssertionError): exact(0.0,actual,'raw')

    def test_all_twelve_modes_and_start_witnesses(self):
        rows=requests('defenses'); self.assertEqual(len(rows),20)
        modes={(r['effective'],r['x_unit'],r['y_unit'],r['x_handle'],r['y_handle']) for r in rows}
        self.assertEqual(len(modes),12)
        for row in rows:
            x,y=wire_axes(row); self.assertNotEqual(y['unit'],'%')
            self.assertEqual(x['input_unit'],'s' if x['quantity']=='time' else '%')
        self.assertEqual({r['starting_shield_percent'] for r in rows if r['x_handle']=='time'},{0.0,25.0,100.0})

    def test_source_only_zero_pattern_is_explicitly_excluded(self):
        self.assertEqual(len(candidate_stages('history')),24)
        self.assertEqual(set(stage_names('history'))-set(candidate_stages('history')),set(SOURCE_ONLY))
        self.assertFalse(any(step['name']=='pattern_zero' for step in candidate_steps('history')))
        self.assertEqual(sum(len(candidate_stages(suite)) for suite in SUITES),26)

    def test_defense_batches_preserve_full_order_and_reverse(self):
        order=list(fixtures('defenses')); self.assertEqual(len(order),14)
        self.assertEqual([len(b) for b in batches(order)],[8,6])
        for values in (order,list(reversed(order))): self.assertEqual([x for batch in batches(values) for x in batch],values)

    def test_all_coordinates_are_exact_including_ehp_endpoints_and_interior(self):
        expected,actual=self.curve(); compare_curve(expected,actual,'good EHP')
        for index in (0,1,100,199,200):
            value=deepcopy(actual); value['x'][index]=math.nextafter(value['x'][index],math.inf)
            with self.assertRaises(AssertionError): compare_curve(expected,value,'perturbed EHP x '+str(index))

    def test_ehp_y_endpoint_and_interior_corruption_rejected(self):
        expected,actual=self.curve()
        for index in (0,100,200):
            value=deepcopy(actual); value['y'][index]+=0.001
            with self.assertRaises(AssertionError): compare_curve(expected,value,'perturbed EHP y '+str(index))

    def test_occurrences_order_shape_and_finite_values(self):
        expected,actual=self.curve(); expected['x']=[1.0]*100+[2.0]*101; actual['x']=deepcopy(expected['x'])
        compare_curve(expected,actual,'duplicates')
        for mutate in (lambda r:r['x'].pop(),lambda r:r['y'].pop(),lambda r:r['x'].reverse(),
                       lambda r:r['x'].__setitem__(100,math.inf),lambda r:r['y'].__setitem__(100,True)):
            value=deepcopy(actual); mutate(value)
            with self.assertRaises(AssertionError): compare_curve(expected,value,'bad occurrence/shape')

    def test_singleton_two_point_and_signed_coordinates(self):
        for n in (1,2,201):
            expected,actual=self.curve(n); compare_curve(expected,actual,'source cardinality')
        expected,actual=self.curve(); expected['x']=[-v for v in expected['x']]; actual['x']=deepcopy(expected['x'])
        expected['y']=[-v for v in expected['y']]; actual['y']=deepcopy(expected['y']); compare_curve(expected,actual,'signed descending')
        expected,actual=self.curve(3)
        with self.assertRaises(AssertionError): compare_curve(expected,actual,'unsupported cardinality')

    def test_rate_tolerance_and_exact_zero(self):
        numeric(1.0,1.0+1e-10,'explicit tolerance')
        for expected,actual in ((0.0,1e-12),(1.0,1.01),(1.0,True),(1.0,math.inf)):
            with self.assertRaises(AssertionError): numeric(expected,actual,'bad numeric')

    def test_source_columns_and_current_pattern_are_compared(self):
        _,actual=self.curve(); expected=dict(source_columns=dict(capacity=dict(value=100.0,unit='HP'),
            recharge=dict(value=50.0,unit='s')),inputs=dict(damage_pattern=dict.fromkeys(FIELDS,25.0)))
        compare_source(expected,actual['source'],'good')
        for field in ('shield_capacity_hp','shield_recharge_seconds'):
            value=deepcopy(actual['source']); value[field]+=1
            with self.assertRaises(AssertionError): compare_source(expected,value,'wrong source')
        for field in PATTERN_FIELDS:
            value=deepcopy(actual['source']); value['damage_pattern'][field]+=1
            with self.assertRaises(AssertionError): compare_source(expected,value,'wrong current pattern')

    def test_full_history_preserves_payload_and_shared_action_identity(self):
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class Action:
            label: str
            changes: tuple
            legacy_token: object=None
        old=Action('legacy',(('x',None,0.0),)); shared=Action('shared',(),old)
        session=NS(history=NS(sequence=2,rows={'a':((shared,),1),'b':((shared,),1)}),
                   graph=NS(_bridge=NS(_history=NS(rows={'a':((old,),1)}))))
        before=full_history(session); self.assertEqual(before['rows']['a'],before['rows']['b'])
        session.history.rows['b']=((deepcopy(shared),),1)
        with self.assertRaises(AssertionError): exact(before,full_history(session),'shared identity drift')
        session.history.rows['b']=((shared,),0)
        with self.assertRaises(AssertionError): exact(before,full_history(session),'cursor drift')

    def test_boundary_witnesses_cover_source_cases(self):
        rows={r['name']:r for r in requests('boundaries')}; self.assertEqual(len(rows),20)
        for name in ('time_reversed','time_subnormal','time_adjacent','start_null','api_negative_time_rate',
                     'api_crossing_shield','api_below_shield','huge_shield_percent','huge_start_percent'):
            self.assertIn(name,rows)
        for row in rows.values():
            x,y=wire_axes(row); exact(row['input_range'],x['range'],'request keeps endpoint order')
        self.assertIsNone(rows['start_null']['starting_shield_percent'])

    def test_original_receipts_full_supported_matrix(self):
        names=dict(defenses='PREFLIGHT-DEFENSES-V2.json',boundaries='PREFLIGHT-BOUNDARIES-V1.json',history='PREFLIGHT-HISTORY-V1.json')
        total=[0,0,0,0]
        for suite,name in names.items():
            path=REPO.parent/name
            self.assertTrue(path.is_file(),name)
            oracle=json.loads(path.read_text()); verify_oracle(NS(suite=suite),oracle)
            for stage in candidate_stages(suite):
                total[0]+=1
                for fit in oracle['states'][stage]['fits'].values():
                    total[1]+=1; total[2]+=len(fit['curves']); total[3]+=sum(len(c['x']) for c in fit['curves'])
        self.assertEqual(total,[26,88,608,119008])

    def test_skill_qualification_is_exact_and_stage_specific(self):
        for label in ('source_a','source_b'):
            value=qualified_skill_difference('history','management_four_undo',label,{'Capital Shield Operation':None},{})
            self.assertTrue(value['strict_comparison_failed'])
            value=qualified_skill_difference('history','operation_four_undo',label,{'Capital Shield Operation':None,'Caldari Defensive Systems':None},{'Capital Shield Operation':None})
            self.assertEqual(value['skill'],'Caldari Defensive Systems')
        for suite,stage,label,left,right in (
            ('defenses','management_four_undo','source_a',{'Capital Shield Operation':None},{}),
            ('history','management_four_undo','unrelated',{'Capital Shield Operation':None},{}),
            ('history','management_four','source_a',{'Capital Shield Operation':None},{}),
            ('history','management_four_undo','source_a',{'Capital Shield Operation':None},{'Capital Shield Operation':0}),
            ('history','operation_four_undo','source_a',{'Capital Shield Operation':None,'Caldari Defensive Systems':None},{}),
            ('history','operation_four_undo','source_a',{'Capital Shield Operation':None},{})
        ):
            with self.assertRaises(AssertionError):qualified_skill_difference(suite,stage,label,left,right)
        self.assertIsNone(qualified_skill_difference('defenses','initial','any',{},{}))
        self.assertEqual(original_effective_level(REPO,None),0)
        self.assertEqual(original_effective_level(REPO,5),5)

    def test_no_eos_or_candidate_import_in_pure_suite(self):
        self.assertFalse(any(name.startswith(('eos.','android_bridge.','mobile_runtime')) for name in sys.modules))


if __name__=='__main__':
    if '--execute' not in sys.argv: unittest.main()
    else:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--execute',action='store_true'); parser.add_argument('--suite',choices=SUITES,required=True)
        parser.add_argument('--phase',choices=('seed','reopen'),required=True)
        for name in ('oracle','store','output'): parser.add_argument('--'+name,type=Path,required=True)
        args=parser.parse_args()
        try: run(args)
        except BaseException as error:
            import traceback
            if not args.output.exists(): write(args.output,dict(status='failed',suite=args.suite,phase=args.phase,error=repr(error),traceback=traceback.format_exc(),partial=PROGRESS))
            raise
