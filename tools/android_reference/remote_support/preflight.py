#!/usr/bin/env python3
"""Original-only D02.2 LOCAL capture and separately permitted measurement.

Data capture forbids all capacitor/tank getters and simulator entry points before
fit construction. The diagnostic does not import any adapter and is NOT a product
admission guard. Only finite no-reload, non-injector fixtures are in this proof.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
from types import ModuleType, SimpleNamespace as NS
import uuid

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO))
from tools.android_reference.multisource import oracle as original_harness
from tools.android_reference.remote_support.cases import (LABELS, SUITES, TRANSFER,
    SHIELD, ARMOR, HULL, NEUT, NOS, SKILL, fixtures, scenario)
from tools.android_reference.reference import snapshot, compare, digest_file, SOURCE_COMMIT

REPAIR_LISTS = ('_shieldRr','_armorRr','_armorRrPreSpool','_armorRrFullSpool','_hullRr')
HORIZONS = (6 * 60 * 60 * 1000, 60 * 60 * 1000)  # Original Fit.__runCapSim/getCapSimData.


def exact(expected,actual,label):
    # Canonical JSON retains int/float/bool distinctions and exact finite values;
    # it normalizes source tuples to their explicit serialized list representation.
    encode=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    assert encode(expected)==encode(actual),'Exact identity differs: '+label


def finite(value, label):
    assert type(value) in (int,float) and math.isfinite(value), (label,value)
    return value


def diagnostic(drains, factor_reload=False):
    """Source reset semantics, no reset/run and no product-budget dependency.

    This deliberately certifies only the stated ordinary no-reload/non-injector
    suite. Unknown semantics are an unqualified diagnostic case, not a product
    refusal. Positive delays/repeat exits/depletion are ignored for an upper bound.
    """
    assert factor_reload is False
    normalized=[]
    for row in drains:
        assert len(row)==6
        duration,need,clip,disable,reload,injector=row
        assert type(duration) is int and duration>0,(duration,row)
        finite(need,'need'); finite(clip,'clip'); finite(reload,'reload')
        assert type(disable) is bool and injector is False, row
        assert clip>=0 and reload>=0,row
        # Exact original no-reload, non-injector normalization before grouping.
        normalized.append((duration,need,0,disable,0,False))
    groups=Counter(normalized);period=1;states=[]
    for (duration,need,clip,disable,reload,injector),amount in groups.items():
        effective=int(duration/amount) if not disable else duration
        assert effective>0,('zero grouped cycle',duration,amount)
        if disable: need*=amount
        finite(need,'grouped need')
        product=period*effective
        assert product<=2**53,('source float LCM loses exact-integer certification',period,effective,product)
        period=product//math.gcd(period,effective)
        states.append([0,effective,need,0,0,0,False])
    estimates={}
    for horizon in HORIZONS:
        events=sum(math.ceil(horizon/row[1])+1 for row in states)
        heap=max(1,math.ceil(math.log2(len(states)+1)))
        sort=max(1,math.ceil(math.log2(events+1)))
        # No injector lists: per-event scalar work + pop/push heap + saved-event sort.
        work=events*(4+2*heap+sort)
        estimates[str(horizon)]=dict(events=events,event_list_work=work,
            scalar_steps=4*events,heap_steps=2*heap*events,saved_sort_steps=sort*events)
    return dict(drains=len(drains),groups=len(groups),states=states,period_ms=period,
                maximum_saved_events=estimates[str(HORIZONS[0])]['events'],horizons=estimates)


class Boundary:
    """Testable diagnostic permission boundary; never changes product source."""
    def __init__(self):
        self.allowed=False; self.attempts=[]; self.simulations=[]; self.context=None
        self.roots=Counter();self.effects=Counter();self.saved=[]
    def install(self):
        from eos.saveddata.fit import Fit
        from eos.capSim import CapSimulator
        def protect(cls,name):
            old=getattr(cls,name);self.saved.append((cls,name,old))
            def wrapper(obj,*args,**kwargs):
                if not self.allowed:
                    self.attempts.append(name)
                    raise AssertionError('Data-only preflight crossed simulation/tank boundary: '+name)
                if cls is CapSimulator and name=='run':
                    assert self.context_calls==0,'Extra simulator call outside the reviewed single-read schedule'
                    self.context_calls+=1
                    before=diagnostic(obj.modules,obj.reload)
                    result=old(obj,*args,**kwargs)
                    limit=before['horizons'][str(obj.t_max)]
                    assert obj.iterations<=limit['events']
                    assert len(obj.saved_changes)<=limit['events']
                    self.simulations.append(dict(context=self.context,t_max=obj.t_max,
                        iterations=obj.iterations,saved_events=len(obj.saved_changes),
                        states=len(obj.state),period_ms=obj.period,runtime=obj.runtime,
                        optimized_repeats=obj.result_optimized_repeats,estimate=limit))
                    return result
                return old(obj,*args,**kwargs)
            setattr(cls,name,wrapper)
        for name in ('simulateCap','_Fit__runCapSim','getCapSimData','calculateSustainableTank'):
            protect(Fit,name)
        for name in ('reset','run'):protect(CapSimulator,name)
        for name in ('capUsed','capRecharge','capStable','capState','capDelta','tank','effectiveTank','sustainableTank','effectiveSustainableTank'):
            old=getattr(Fit,name);self.saved.append((Fit,name,old))
            def getter(obj,old=old,name=name):
                if not self.allowed:
                    self.attempts.append(name)
                    raise AssertionError('Data-only preflight crossed getter boundary: '+name)
                return old.fget(obj)
            setattr(Fit,name,property(getter))
        old=Fit.calculateModifiedAttributes;self.saved.append((Fit,'calculateModifiedAttributes',old))
        def calculate(obj,*args,**kwargs):
            from eos.const import CalcType
            kind=kwargs.get('type',args[1] if len(args)>1 else CalcType.LOCAL)
            self.roots[CalcType(kind).name]+=1
            return old(obj,*args,**kwargs)
        Fit.calculateModifiedAttributes=calculate
        import eos.effects
        for effect_id in (6184,6185,6186,6187,6188,6197):
            cls=getattr(eos.effects,'Effect'+str(effect_id));handler=cls.handler
            self.saved.append((cls,'handler',staticmethod(handler)))
            def handle(*args,handler=handler,effect_id=effect_id,**kwargs):
                self.effects[str(effect_id)]+=1
                return handler(*args,**kwargs)
            cls.handler=staticmethod(handle)
    def close(self):
        for cls,name,value in reversed(self.saved):setattr(cls,name,value)
    @contextmanager
    def measurement(self,context):
        assert not self.allowed
        self.context=context;self.context_calls=0;self.allowed=True
        try:yield
        finally:self.allowed=False;self.context=None


def command_value(value, fits=None):
    if value is None or type(value) in (str,bool,int):return value
    if type(value) is float:return value if math.isfinite(value) else str(value)
    if isinstance(value,(list,tuple)):return [command_value(v,fits) for v in value]
    if isinstance(value,dict):return {k:command_value(v,fits) for k,v in value.items()}
    for key,fit in (fits or {}).items():
        if value is fit:return dict(source_key=key,original_type='Fit',database_id=fit.ID)
    return dict(original_type=type(value).__name__,id=getattr(value,'ID',None),item_id=getattr(value,'itemID',None))


class Original(original_harness.Original):
    def run_command(self,name,**kwargs):
        evidence=command_value(kwargs,self.fits)
        command=super().run_command(name,**kwargs)
        self.trace[-1]['arguments']=evidence
        return command
    def __init__(self,source):
        super().__init__(source)
        self.scope['Market'].getInstance().storeRecentlyUsed=lambda *a,**kw:None
        self.extract('gui/fitCommands/helpers.py','activeStateLimit',self.scope)
        for filename in ('localAdd','localRemove'):
            name='_d02_original.module.'+filename
            mod=ModuleType(name);mod.__package__='_d02_original.module';mod.__dict__.update(self.scope)
            self.extract_all('gui/fitCommands/calc/module/'+filename+'.py',mod.__dict__)
            sys.modules[name]=mod;self.loaded.append(mod)
            self.scope.update({k:v for k,v in mod.__dict__.items() if k.startswith('Calc')})
        for mod in self.loaded:mod.__dict__.update({k:v for k,v in self.scope.items() if k.startswith('Calc')})
        for filename in ('add','remove'):self.extract_all('gui/fitCommands/gui/localModule/'+filename+'.py',self.scope)
    def apply(self,step):
        op,args=step['op'],step['args'];fit=self.fits.get(args.get('fit'))
        if op=='local_state':
            from eos.const import FittingModuleState
            index=next(i for i,m in enumerate(fit.modules) if not m.isEmpty and m.item.name==args['item'])
            assert fit.modules[index].state!=FittingModuleState[args['state']]
            command=self.run_command('GuiChangeLocalModuleStatesCommand',fitID=fit.ID,mainPosition=index,positions=[index],click='left')
            assert fit.modules[index].state==FittingModuleState[args['state']],args
            return command
        if op=='local_remove':
            index=next(i for i,m in enumerate(fit.modules) if not m.isEmpty and m.item.name==args['item'])
            return self.run_command('GuiRemoveLocalModuleCommand',fitID=fit.ID,positions=[index])
        if op=='local_add':return self.run_command('GuiAddLocalModuleCommand',fitID=fit.ID,itemID=self.item(args['item']).ID)
        if op=='shared_skill':
            skill=self.shared.getSkill(self.item(SKILL));previous=skill.activeLevel
            def change(level):
                skill.setLevel(level,persist=True)
                for key in ('source_a','source_b'):self.service.recalc(self.fits[key])
            change(args['level'])
            return NS(Undo=lambda:change(previous),Do=lambda:change(args['level']))
        return super().apply(step)


def capture(fit):
    from eos.const import FittingSlot, FittingModuleState, FittingHardpoint
    assert not fit.drones and not fit.fighters and not fit.projectedDrones and not fit.projectedFighters
    assert not fit.commandFits and not fit.implants and not fit.boosters
    assert fit.fits and all(m.isEmpty or m.fits(fit) for m in fit.modules)
    resources={}
    for attr,out in (('cpu','cpuOutput'),('power','powerOutput')):
        used=finite(fit.getItemAttrOnlineSum(fit.modules,attr),attr)
        available=finite(fit.ship.getModifiedItemAttr(out),out)
        assert used<=available,(attr,used,available)
        resources[attr]=dict(used=used,available=available)
    slots={slot.name:fit.getSlotsFree(slot.value,False) for slot in FittingSlot}
    assert all(v>=0 for v in slots.values()),slots
    hardpoints={kind.name:fit.getHardpointsFree(kind) for kind in (FittingHardpoint.TURRET,FittingHardpoint.MISSILE)}
    assert all(v>=0 for v in hardpoints.values()),hardpoints
    repairs={name:deepcopy(getattr(fit,name)) for name in REPAIR_LISTS}
    for name,rows in repairs.items():
        for amount,duration in rows:
            finite(amount,name+' amount');finite(duration,name+' seconds')
            assert duration>0 and int(duration)>0,(name,amount,duration)
    extra=list(fit.iterDrains())
    for duration,need,clip,reload in extra:
        finite(duration,'extra drain duration');finite(need,'extra drain need')
        assert duration>0 and int(duration)>0,(duration,need)
    for name in ('capacitorCapacity','rechargeRate'):
        assert finite(fit.ship.getModifiedItemAttr(name),name)>0
    modules=[]
    for m in fit.modules:
        if m.isEmpty:continue
        row=dict(name=m.item.name,state=m.state,raw_cycle_ms=m.rawCycleTime,
                 attributes={n:m.getModifiedItemAttr(n) for n in ('capacitorNeed','duration','maxRange','falloffEffectiveness','powerTransferAmount','energyNeutralizerAmount','shieldBonus','armorDamageAmount','structureDamageAmount')})
        if m.state>=FittingModuleState.ACTIVE and row['attributes']['capacitorNeed']:
            finite(m.rawCycleTime,'local raw cycle');assert m.rawCycleTime>0
        modules.append(row)
    drains,used,added=fit._Fit__generateDrain()
    finite(used,'generated use');finite(added,'generated added')
    return dict(resources=resources,slots_free=slots,hardpoints_free=hardpoints,legal=True,module_inputs=modules,
        raw_extra_drains=extra,repair_pairs=repairs,generated_drains=drains,
        cap_used_per_second=used,cap_added_per_second=added,estimate=diagnostic(drains,fit.factorReload),
        incoming_drone_fighter_admission=dict(enabled=False,reason='no incoming drones or fighters; no production admission invoked'))


def resolve_ranges(original):
    rows={}
    for key in LABELS:
        fit=original.fits[key];original.service.recalc(fit)
        for m in fit.modules:
            if not m.isEmpty:rows[m.item.name]={n:m.getModifiedItemAttr(n) for n in ('maxRange','falloffEffectiveness','duration')}
    result={'source_attributes':rows,'transfer_max':rows[TRANSFER]['maxRange']}
    if ARMOR in rows:
        result['armor_falloff']=rows[ARMOR]['maxRange']+rows[ARMOR]['falloffEffectiveness']
        result['beyond_support']=max((r['maxRange'] or 0)+3*(r['falloffEffectiveness'] or 0) for r in rows.values())+1
        assert result['armor_falloff']==13500.0, result
    if NEUT in rows:
        result['neut_falloff']=rows[NEUT]['maxRange']+rows[NEUT]['falloffEffectiveness']
        result['neut_beyond']=rows[NEUT]['maxRange']+3*rows[NEUT]['falloffEffectiveness']+1
    return result


def observe(fit):
    stats=snapshot(fit);stats['scan_resolution']=dict(value=fit.ship.getModifiedItemAttr('scanResolution'),unit='mm')
    assert len(stats)==39
    remote=fit.getRemoteReps()
    return dict(stats=stats,tank={name:deepcopy(getattr(fit,name)) for name in ('tank','effectiveTank','sustainableTank','effectiveSustainableTank')},
        capacitor=dict(capacity=fit.ship.getModifiedItemAttr('capacitorCapacity'),recharge_time_ms=fit.ship.getModifiedItemAttr('rechargeRate'),
            used=fit.capUsed,recharge=fit.capRecharge,delta=fit.capDelta,stable=fit.capStable,state=fit.capState,
            state_unit='%' if fit.capStable else 's',neutralizer_resistance=fit.ship.getModifiedItemAttr('energyWarfareResistance',1)),
        outgoing={name:getattr(remote,name) for name in ('capacitor','shield','armor','hull')})


def harness_hashes():
    return {str(p.relative_to(REPO)):digest_file(p) for p in (Path(__file__),Path(__file__).with_name('cases.py'),REPO/'tools/android_reference/multisource/oracle.py',REPO/'tools/android_reference/reference.py')}


def fixture_hashes():
    return {name:digest_file(REPO/'tools/android_reference/fixtures'/name) for name in ('tank.json','output.json','capacitor.json')}


def run(args):
    started=time.monotonic();data_before=digest_file(args.database)
    assert 0<resource.getrlimit(resource.RLIMIT_AS)[0]<=1024**3,'Run in the existing one-GiB EOS process limit'
    original_harness.ARGS=args
    config=original_harness.original_source(args.source)
    boundary=Boundary();boundary.install()
    original=Original(args.source);inputs=fixtures(args.suite)
    order=list(reversed(LABELS)) if args.reverse else list(LABELS)
    for key in order:original.make(key,inputs[key])
    ranges=resolve_ranges(original);steps=scenario(args.suite,ranges,args.reverse)
    states={};trace=[];approved=None
    if args.measure:
        approved=json.loads(args.measure.read_text())
        assert approved['suite']==args.suite and approved['reverse']==args.reverse
        assert approved['mode']=='capture' and not approved['simulations'] and not approved['forbidden_attempts']
        assert approved['dataset_sha256']==data_before
        assert approved['source']==str(args.source)
        exact(approved['harness_files'],harness_hashes(),'capture program binding')
        exact(approved['fixture_files'],fixture_hashes(),'fixture binding')
        exact(approved['settings'],dict(config.settings),'settings binding')
        exact(approved['inputs'],inputs,'inputs binding')
        for relative,expected in {**approved['source_files'],**approved['original_imports']}.items():
            assert digest_file(args.source/relative)==expected,('source binding',relative)
        exact(approved['ranges'],ranges,'measurement ranges')
        exact(approved['steps'],steps,'measurement steps')
    for index,step in enumerate([dict(name='initial',op='initial',args={})]+steps):
        if index:original.apply(step)
        name=step['name'];entry={};raw_before={key:original.raw(original.fits[key]) for key in LABELS}
        # Every data-only sample has immediate original service LOCAL recalc.
        for key in order:
            original.service.recalc(original.fits[key]);entry[key]=capture(original.fits[key])
        opposite={}
        for key in reversed(order):
            original.service.recalc(original.fits[key]);opposite[key]=capture(original.fits[key])
        exact(entry,opposite,'LOCAL capture read order.'+name)
        projection_iteration={key:[next(label for label,value in original.fits.items() if value is source) for source in original.fits[key].projectedFits] for key in LABELS}
        stage=dict(capture=entry,raw=raw_before,projection_iteration=projection_iteration)
        if approved is not None:
            exact(approved['states'][name]['raw'],raw_before,'approved raw.'+name)
            exact(approved['states'][name]['projection_iteration'],projection_iteration,'approved iteration.'+name)
            exact(approved['states'][name]['capture'],json.loads(json.dumps(entry)),'approved capture.'+name)
            values={};reverse_values={};calls_before=len(boundary.simulations)
            for target,sequence in ((values,order),(reverse_values,list(reversed(order)))):
                for key in sequence:
                    fit=original.fits[key];original.service.recalc(fit);fresh=capture(fit)
                    exact(entry[key],fresh,'fresh measurement capture')
                    with boundary.measurement(name+'.'+key):target[key]=observe(fit)
            compare(values,reverse_values,'original numerical read order.'+name)
            assert len(boundary.simulations)-calls_before<=2*len(LABELS),'One cached cap run per fit/LOCAL read schedule'
            stage['values']=values
        exact(raw_before,{key:original.raw(original.fits[key]) for key in LABELS},'observations preserve raw.'+name)
        assert name not in states,'duplicate stage name: '+name
        states[name]=stage
        trace.append(dict(stage=name,root_calls=dict(boundary.roots),support_handler_calls=dict(boundary.effects),simulations=len(boundary.simulations)))
        print('MEASURE' if approved else 'CAPTURE',args.suite,name,flush=True)
    assert not boundary.attempts,boundary.attempts
    imports={}
    for name,mod in list(sys.modules.items()):
        assert name.split('.')[0] not in {'android_bridge','mobile_runtime'}
        path=getattr(mod,'__file__',None)
        if path and name.split('.')[0] in {'eos','utils'}:
            relative=Path(path).resolve().relative_to(args.source).as_posix()
            assert Path(path).read_bytes()==(REPO/relative).read_bytes(),relative
            imports[relative]=original_harness.sha(path)
    import eos.db
    assert not original_harness.NETWORK_ATTEMPTS
    assert data_before==digest_file(args.database)
    result=dict(suite=args.suite,reverse=args.reverse,mode='measure' if approved else 'capture',
        pid=os.getpid(),process_nonce=uuid.uuid4().hex,source_commit=SOURCE_COMMIT,
        source_kind='retained reconstructed pinned-lineage; supplemental existing dataset',source=str(args.source),
        dataset_sha256=data_before,dataset_metadata=dict(eos.db.gamedata_session.execute('SELECT field_name,field_value FROM metadata').fetchall()),
        inputs=inputs,ranges=ranges,steps=steps,states=states,source_files=original.hashes,original_imports=imports,
        harness_files=harness_hashes(),fixture_files=fixture_hashes(),
        settings=dict(config.settings),resolved_item_ids=original.resolved,command_trace=original.trace,
        work_trace=trace,simulations=boundary.simulations,forbidden_attempts=boundary.attempts,network_attempts=original_harness.NETWORK_ATTEMPTS,
        measurement_input_sha256=digest_file(args.measure) if args.measure else None,
        elapsed_seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        limits=dict(address_space_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],external_timeout_seconds=180),
        read_schedule='Immediate original service.recalc per endpoint before every capture/read; both endpoint orders. No graph getter in this preflight.')
    boundary.close();original_harness.dump(args.output,result)
    print('PASS',args.suite,len(states),'stages',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--suite',choices=SUITES,required=True);parser.add_argument('--reverse',action='store_true')
    parser.add_argument('--measure',type=Path,help='Reviewed successful capture receipt; measurement is separate and explicit')
    args=parser.parse_args();args.source=args.source.resolve();args.database=args.database.resolve()
    run(args)
