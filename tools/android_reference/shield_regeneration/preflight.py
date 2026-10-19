#!/usr/bin/env python3
"""G04 independent full original graph pipeline; no candidate calculation imports."""
import argparse
import ast
from abc import ABCMeta, abstractmethod
from collections import Counter, OrderedDict, namedtuple
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import sys
import time
import traceback
from types import MethodType, SimpleNamespace as NS
import uuid
sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from tools.android_reference.shield_regeneration.cases import SUITES, FIELDS, fixtures, requests, steps, stage_names

PROGRESS = {}
# Exact retained binding from protected G05.1 DATASET-VERIFY.json; logical ID is not a file digest.
PHYSICAL_DATABASE_SHA256 = '68fb9ea965cb046e426f7c068c7508b55a4e82d2a3dceeed3cb948585d6e7203'
LOGICAL_DATASET_SHA256 = '5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def exact(a, b, label):
    encode = lambda value: json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))
    assert encode(a) == encode(b), label

def classified(value):
    if isinstance(value,float) and not math.isfinite(value): return {'nonfinite':repr(value)}
    if isinstance(value,(list,tuple)): return [classified(v) for v in value]
    if isinstance(value,dict): return {k:classified(v) for k,v in value.items()}
    return value

def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')


class Source:
    """Extract unchanged named source AST; import nothing from candidate product."""
    def __init__(self, source): self.source, self.hashes = Path(source), {}
    def extract(self, path, name, scope):
        data = (self.source/path).read_bytes(); self.hashes[path] = sha(self.source/path)
        assert data == (REPO/path).read_bytes(), 'Original upstream body differs: ' + path
        nodes = [n for n in ast.walk(ast.parse(data)) if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name]
        assert len(nodes) == 1, (path, name)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(self.source/path), 'exec'), scope)
    def bind(self, path):
        assert (self.source/path).read_bytes() == (REPO/path).read_bytes(), path
        self.hashes[path] = sha(self.source/path)


class OriginalGraph:
    """Whole original range workflow, definitions, getter classes and column methods."""
    def __init__(self, source):
        self.source = source; self.point_calls = 0; self.effective = False
        frame = NS(statsPane=NS(nameViewMap={'resistancesViewFull': NS()}))
        # This property is the only GUI state read by original graph construction.
        self.view = frame.statsPane.nameViewMap['resistancesViewFull']
        self.scope = dict(math=math, sys=sys, re=re, ABCMeta=ABCMeta, abstractmethod=abstractmethod,
                          OrderedDict=OrderedDict, namedtuple=namedtuple, GraphColumn=object,
                          _t=lambda value:value, keepDigits=int(sys.float_info.dig/2),
                          gui=NS(mainFrame=NS(MainFrame=NS(getInstance=lambda:frame))),
                          GraphCacheCleanupReason=NS())
        for path, names in (
            ('eos/utils/float.py', ('floatUnerr',)),
            ('graphs/data/base/defs.py', ('Input', 'XDef', 'YDef')),
            ('graphs/data/base/getter.py', ('PointGetter', 'SmoothPointGetter')),
            ('graphs/data/base/graph.py', ('FitGraph',)),
            ('graphs/data/fitShieldRegen/getter.py', ('calculateShieldAmount', 'calculateShieldRegen',
                'Time2ShieldAmountGetter', 'Time2ShieldRegenGetter', 'ShieldAmount2ShieldAmountGetter', 'ShieldAmount2ShieldRegenGetter')),
            ('graphs/data/fitShieldRegen/graph.py', ('FitShieldRegenGraph',)),
            ('gui/builtinViewColumns/attributeDisplayGraph.py', ('ShieldAmountColumn', 'ShieldTimeColumn'))):
            for name in names: source.extract(path, name, self.scope)
        for name in ('Time2ShieldAmountGetter', 'Time2ShieldRegenGetter', 'ShieldAmount2ShieldAmountGetter', 'ShieldAmount2ShieldRegenGetter'):
            cls = self.scope[name]; old = cls._calculatePoint
            assert cls._baseResolution == 200 and cls._extraDepth == 0
            def count(obj, *args, original=old, **kwargs):
                self.point_calls += 1; return original(obj, *args, **kwargs)
            cls._calculatePoint = count
        # Bind control-to-parser wiring as well as executing parser bodies in pure tests.
        for path in ('graphs/gui/ctrlPanel.py', 'gui/utils/inputs.py', 'eos/saveddata/damagePattern.py'):
            source.bind(path)
    def fresh(self, effective):
        self.view.showEffective = effective
        return self.scope['FitShieldRegenGraph']()
    def columns(self, fit):
        result = {}
        for name, key in (('ShieldAmountColumn', 'capacity'), ('ShieldTimeColumn', 'recharge')):
            cls = self.scope[name]; value, unit = cls._getValue(object.__new__(cls), fit)
            assert math.isfinite(value)
            result[key] = dict(value=value, unit=unit)
        return result
    def sample(self, fit, request):
        graph = self.fresh(request['effective']); src = NS(item=fit)
        x = graph.xDefMap[(request['x_handle'], request['x_unit'])]
        y = graph.yDefMap[(request['y_handle'], request['y_unit'])]
        main = NS(handle=x.mainInput[0], unit=x.mainInput[1], value=tuple(request['input_range']))
        misc = [NS(handle='shieldAmountT0', unit='%', value=request['starting_shield_percent'])] if x.handle == 'time' else []
        normalized_main = graph._normalizeMain(main, src, None)
        normalized_misc = graph._normalizeMisc(misc, src, None)
        limited_main = graph._limitMain(normalized_main, src, None)
        limited_misc = graph._limitMisc(deepcopy(normalized_misc), src, None)
        try:
            effective_range = graph._denormalizeValues(list(limited_main[1]), NS(handle=main.handle, unit=main.unit), src, None)
            effective_range_error = None
        except ZeroDivisionError:
            # Recording effective inputs must not preempt the full base Graph fallback.
            effective_range, effective_range_error = None, 'ZeroDivisionError'
        raw = {}; original_get = graph._getPlotPoints
        def capture(**kwargs):
            xs, ys = original_get(**kwargs); raw.update(x=list(xs), y=list(ys)); return xs, ys
        graph._getPlotPoints = capture
        before = self.point_calls
        xs, ys = graph.getPlotPoints(main, misc, x, y, src)
        assert 1 <= len(xs) == len(ys) <= 201
        return dict(request=deepcopy(request), normalized_main=list(normalized_main), normalized_misc=normalized_misc,
                    effective_main=list(limited_main), effective_misc=limited_misc,
                    effective_input_range=effective_range, effective_input_range_error=effective_range_error, getter_x=raw['x'], getter_y=raw['y'],
                    x=xs, y=ys, point_calls=self.point_calls-before)


class Boundary:
    """No graph capacitor/reset/cycle work. Source-only boundary, not production claim."""
    def __init__(self): self.saved=[]; self.attempts=[]; self.roots=Counter()
    def forbid(self, cls, name):
        old=getattr(cls,name); self.saved.append((cls,name,old))
        def blocked(*args, **kwargs):
            label=cls.__name__+'.'+name; self.attempts.append(label)
            raise AssertionError('Forbidden original G04 entry: '+label)
        setattr(cls,name,property(blocked) if isinstance(old,property) else blocked)
    def install(self):
        from eos.saveddata.fit import Fit
        from eos.capSim import CapSimulator
        from eos.utils.cycles import CycleInfo, CycleSequence
        from eos.const import CalcType
        for name in ('simulateCap','_Fit__runCapSim','_Fit__generateDrain','getCapSimData','calculateSustainableTank'):
            self.forbid(Fit,name)
        for name in ('capUsed','capRecharge','capStable','capState','capDelta','tank','effectiveTank','sustainableTank','effectiveSustainableTank'):
            self.forbid(Fit,name)
        for name in ('reset','run'): self.forbid(CapSimulator,name)
        for cls in (CycleInfo,CycleSequence): self.forbid(cls,'iterCycles')
        old=Fit.calculateModifiedAttributes; self.saved.append((Fit,'calculateModifiedAttributes',old))
        def calculate(obj,*args,**kwargs):
            kind=kwargs.get('type',args[1] if len(args)>1 else CalcType.LOCAL)
            self.roots[CalcType(kind).name]+=1; return old(obj,*args,**kwargs)
        Fit.calculateModifiedAttributes=calculate
    def close(self):
        for cls,name,value in reversed(self.saved): setattr(cls,name,value)


def original_type(plumbing):
    class Original(plumbing.Original):
        def __init__(self, source):
            super().__init__(source); self.reload={}
            self.scope['Market'].getInstance().storeRecentlyUsed=lambda *a,**k:None
        def bind(self,path):
            assert (self.source/path).read_bytes()==(REPO/path).read_bytes(),path
            self.hashes[path]=sha(self.source/path)
        def configure(self,key):
            self.service.serviceFittingOptions['useGlobalForceReload']=self.reload[key]
            return dict(self.service.serviceFittingOptions)
        def make(self,key,spec):
            assert spec['skill_level']==5
            self.reload[key]=spec['factor_reload']; self.configure(key); super().make(key,spec)
        def raw(self,fit):
            result=super().raw(fit)
            result.update(damage_pattern={name:getattr(fit.damagePattern,name) for name in FIELDS},
                          factor_reload=fit.factorReload, character_id=fit.character.ID)
            return result
        def apply(self,step):
            op,args=step['op'],step['args']; fit=self.fits.get(args.get('fit'))
            if fit is not None: self.configure(args['fit'])
            if op=='state':
                from eos.const import FittingModuleState
                index=next(i for i,m in enumerate(fit.modules) if not m.isEmpty and m.item.name==args['item'])
                cmd=self.run_command('GuiChangeLocalModuleStatesCommand',fitID=fit.ID,mainPosition=index,positions=[index],click=args.get('click','left'))
                assert fit.modules[index].state==FittingModuleState[args['state']]
                return cmd
            if op=='skill':
                skill=self.shared.getSkill(self.item(args['skill'])); previous=skill.activeLevel
                affected=set()
                def downstream(item,level):
                    for dependent,required in item.requiredFor.items():
                        if dependent.group.category.ID==16 and (level is None or level<required) and dependent.name not in affected:
                            affected.add(dependent.name); downstream(dependent,None)
                downstream(skill.item,args['level'])
                def change(level):
                    skill.setLevel(level,persist=True)
                    assert skill.activeLevel==level, 'Target skill did not take requested level'
                    for key in ('source_a','source_b'): self.configure(key); self.service.recalc(self.fits[key])
                change(args['level']); self.trace.append(dict(api='Character.getSkill.setLevel',arguments=args))
                return NS(Undo=lambda:change(previous),Do=lambda:change(args['level']),
                          affectedSkillNames=sorted(affected),previousLevel=previous,targetSkill=args['skill'])
            if op=='pattern':
                from eos.saveddata.damagePattern import DamagePattern
                previous=fit.damagePattern; replacement=DamagePattern(**dict(zip(FIELDS,args['values'])))
                def change(value): fit.damagePattern=value; self.service.recalc(fit)
                change(replacement); self.trace.append(dict(api='Fit.damagePattern replacement',arguments=args,
                    qualification='Direct original property/API restoration; not desktop GUI pattern undo proof'))
                return NS(Undo=lambda:change(previous),Do=lambda:change(replacement))
            return super().apply(step)
    return Original


def capture_inputs(fit):
    from eos.const import FittingSlot
    assert fit.fits and not fit.ignoreRestrictions
    assert not any((fit.drones,fit.fighters,fit.projectedModules,fit.projectedDrones,fit.projectedFighters,fit.projectedFits,fit.commandFits,fit.implants,fit.boosters))
    modules=[m for m in fit.modules if not m.isEmpty]
    assert all(m.fits(fit) and m.item.published and m.charge is None for m in modules)
    resources={}
    for attr,out in (('cpu','cpuOutput'),('power','powerOutput')):
        used=fit.getItemAttrOnlineSum(fit.modules,attr); available=fit.ship.getModifiedItemAttr(out)
        assert math.isfinite(used) and math.isfinite(available) and 0<=used<=available
        resources[attr]=dict(used=used,available=available)
    slots={slot.name:fit.getSlotsFree(slot.value,False) for slot in FittingSlot}
    assert min(slots.values())>=0
    attrs=('shieldCapacity','shieldRechargeRate','shieldEmDamageResonance','shieldThermalDamageResonance','shieldKineticDamageResonance','shieldExplosiveDamageResonance')
    values={name:fit.ship.getModifiedItemAttr(name) for name in attrs}
    assert all(math.isfinite(value) for value in values.values())
    return dict(legal=True,resources=resources,free_slots=slots,ship_attributes=values,
                damage_pattern={name:getattr(fit.damagePattern,name) for name in FIELDS},
                effective_factor_reload=fit.factorReload, module_container_rows=len(fit.modules))


def original_skill_level(original,key,name):
    return original.fits[key].character.getSkill(original.item(name)).activeLevel

def raw_all(original): return {key:original.raw(fit) for key,fit in original.fits.items()}


def observe(original,graph,boundary,rows,order):
    raw=deepcopy(raw_all(original)); observations={}; work=[]
    for key in order:
        fit=original.fits[key]; before=Counter(boundary.roots); options=original.configure(key)
        original.service.recalc(fit); inputs=capture_inputs(fit)
        assert inputs['effective_factor_reload'] is original.reload[key]
        inputs['declared_factor_reload']=original.reload[key]
        curves=[graph.sample(fit,row) for row in rows]
        for curve in curves:
            # Intermediate overflow is valid if original limiting yields finite outputs.
            for field in ('normalized_main','normalized_misc'):
                curve[field]=classified(curve[field])
        assert all(math.isfinite(value) for curve in curves for field in ('x','y','getter_x','getter_y') for value in curve[field])
        assert all(curve['point_calls']==len(curve['getter_x']) in (1,201) for curve in curves)
        observations[key]=dict(inputs=inputs,source_service_options=options,source_columns=graph.columns(fit),curves=curves)
        work.append(dict(fit=key,roots=dict(boundary.roots-before)))
    exact(raw,raw_all(original),'graph read changed original raw state'); assert not boundary.attempts
    return dict(fits=observations,raw=raw),work


def witnesses(suite,states):
    first=states['initial']['fits']
    def capacity(stage,key): return states[stage]['fits'][key]['source_columns']['capacity']['value']
    def recharge(stage,key): return states[stage]['fits'][key]['source_columns']['recharge']['value']
    if suite=='defenses':
        assert len(first)==14
        assert first['shield_extender']['source_columns']['capacity']['value']>first['uniform_incoming']['source_columns']['capacity']['value']
        effective=[r for r in first['hardener_active']['curves'] if r['request']['effective']]
        assert all(len(r['x'])==201 for r in effective)
        assert first['em_incoming']['curves'][10]['y']!=first['explosive_incoming']['curves'][10]['y']
    elif suite=='boundaries':
        for fit in first.values():
            curves={r['request']['name']:r for r in fit['curves']}
            assert len(curves['time_subnormal']['x'])==len(curves['shield_subnormal']['x'])==1
            assert len(curves['time_adjacent']['x'])==201 and len(set(curves['time_adjacent']['x']))<201
            assert curves['shield_above_100']['effective_input_range'][1]==100
            assert len(curves['shield_clamped_singleton']['x'])==1
            assert curves['start_above_100']['effective_misc']['shieldAmountT0']==fit['source_columns']['capacity']['value']
            assert curves['api_negative_time_amount']['y'][0]>fit['source_columns']['capacity']['value']
            assert curves['api_negative_time_rate']['y'][0]<0
            assert curves['api_crossing_shield']['effective_input_range']==[0.0,100.0]
            assert curves['api_below_shield']['effective_input_range']==[0.0,0.0]
            assert curves['api_negative_start']['effective_misc']['shieldAmountT0']==0.0
            assert curves['huge_shield_percent']['normalized_main'][1]==[{'nonfinite':'inf'},{'nonfinite':'inf'}]
            assert curves['huge_shield_percent']['effective_input_range']==[100.0,100.0]
            assert curves['huge_start_percent']['normalized_misc']['shieldAmountT0']=={'nonfinite':'inf'}
        assert first['empty']['curves'][9]['effective_main']!=first['extended']['curves'][9]['effective_main']
    else:
        assert capacity('extender_offline','source_b')<capacity('initial','source_b')
        assert capacity('management_four','source_a')<capacity('shared_profile','source_a')
        assert recharge('operation_four','source_a')>recharge('management_five','source_a')
        assert states['hardener_online']['fits']['source_a']['curves'][1]['y']!=first['source_a']['curves'][1]['y']
        assert states['pattern_zero']['fits']['source_a']['curves'][0]['y']==states['pattern_zero']['fits']['source_a']['curves'][1]['y']
        for name,state in states.items():
            exact(first['unrelated'],state['fits']['unrelated'],'Unrelated anchor changed at '+name)


def run(args):
    from tools.android_reference.multisource import oracle as plumbing
    from tools.android_reference.reference import SOURCE_COMMIT, compare
    started=time.monotonic(); before_sha=sha(args.database)
    PROGRESS.update(database_path=str(args.database),physical_database_sha256=before_sha,logical_dataset_sha256=os.environ['PYFA_DATASET_SHA'])
    assert before_sha==PHYSICAL_DATABASE_SHA256 and args.database.stat().st_size==99897344, 'Unexpected retained dataset bytes'
    assert os.environ['PYFA_DATASET_SHA']==LOGICAL_DATASET_SHA256, 'Unexpected retained logical dataset identity'
    assert resource.getrlimit(resource.RLIMIT_AS)[0]==1024**3
    assert not args.output.exists(); plumbing.ARGS=args
    config=plumbing.original_source(args.source); boundary=Boundary(); boundary.install()
    original=original_type(plumbing)(args.source); graph=OriginalGraph(original)
    values=fixtures(args.suite); schedule=steps(args.suite); order=list(values)
    for key,spec in values.items(): original.make(key,spec)
    states={}; trace=[]; request_trace=[]; skill_undo_differences=[]
    PROGRESS.update(dataset_sha256=before_sha,source_files=original.hashes,inputs=values,steps=schedule,
                    states=states,work_trace=trace,request_trace=request_trace,forbidden_attempts=boundary.attempts,command_trace=original.trace)
    def take(name,initial=False):
        rows=requests(args.suite,initial)
        forward,work=observe(original,graph,boundary,rows,order)
        reverse,other=observe(original,graph,boundary,rows,list(reversed(order)))
        compare(forward,reverse,'read order.'+name); states[name]=forward
        trace.append(dict(stage=name,forward=work,reverse=other)); request_trace.append(dict(stage=name,requests=rows))
        print('ORIGINAL G04',args.suite,name,flush=True)
    take('initial',True)
    for step in schedule:
        raw_before=deepcopy(raw_all(original)); prior=deepcopy(states[next(reversed(states))])
        command=original.apply(step); take(step['name'])
        if step['args'].get('history'):
            raw_after=deepcopy(raw_all(original)); after=deepcopy(states[step['name']])
            command.Undo(); take(step['name']+'_undo')
            compare(prior['fits'],states[step['name']+'_undo']['fits'],'undo numeric '+step['name'])
            # Strict skill edits can clear source-metadata downstream skills; exclude only those exact names.
            if step['op']=='skill':
                expected=deepcopy(raw_before); actual=deepcopy(raw_all(original)); differences={}
                for key in expected:
                    for name in command.affectedSkillNames:
                        left=expected[key]['skills'].pop(name,'default_5'); right=actual[key]['skills'].pop(name,'default_5')
                        if left!=right: differences.setdefault(key,{})[name]=dict(before=left,after_undo=right)
                    if key in ('source_a','source_b'):
                        assert original_skill_level(original,key,command.targetSkill)==command.previousLevel
                exact(expected,actual,'skill undo raw excluding exact downstream source metadata '+step['name'])
                skill_undo_differences.append(dict(stage=step['name'],allowed_downstream_names=command.affectedSkillNames,actual_differences=differences))
            else: exact(raw_before,raw_all(original),'undo raw '+step['name'])
            command.Do(); take(step['name']+'_redo')
            exact(raw_after,raw_all(original),'redo raw '+step['name'])
            compare(after,states[step['name']+'_redo'],'redo complete '+step['name'])
    assert list(states)==stage_names(args.suite); witnesses(args.suite,states)
    imports={}
    for name,module in list(sys.modules.items()):
        assert name.split('.')[0] not in {'android_bridge','mobile_runtime'}
        path=getattr(module,'__file__',None)
        if not path: continue
        resolved=Path(path).resolve()
        try: relative=resolved.relative_to(args.source).as_posix()
        except ValueError:
            assert name.split('.')[0] not in {'eos','utils'},('Original import outside source',name,path)
        else:
            assert resolved.read_bytes()==(REPO/relative).read_bytes(),relative
            imports[relative]=sha(resolved)
    import eos.db
    assert not boundary.attempts and not plumbing.NETWORK_ATTEMPTS
    after_sha=sha(args.database); assert before_sha==after_sha
    harness=[Path(__file__),Path(__file__).with_name('cases.py'),REPO/'tools/android_reference/multisource/oracle.py',
             REPO/'tools/android_reference/multisource/cases.py',REPO/'tools/android_reference/reference.py']
    result=dict(status='passed',suite=args.suite,pid=os.getpid(),process_nonce=uuid.uuid4().hex,
        source_commit=SOURCE_COMMIT,source_kind='retained reconstructed pinned-lineage; existing supplemental game data',
        source=str(args.source),source_files=original.hashes,original_imports=imports,
        dataset_sha256=before_sha,dataset_after_sha256=after_sha,logical_dataset_sha256=LOGICAL_DATASET_SHA256,
        database_bytes=args.database.stat().st_size,
        database_connection='sqlite URI mode=ro; saveddata sqlite memory',
        dataset_metadata=dict(eos.db.gamedata_session.execute('SELECT field_name,field_value FROM metadata').fetchall()),
        harness_files={str(p.relative_to(REPO)):sha(p) for p in harness},
        fixture_files={'tools/android_reference/fixtures/defenses.json':sha(REPO/'tools/android_reference/fixtures/defenses.json')},
        settings=dict(config.settings),inputs=values,input_order=order,steps=schedule,request_trace=request_trace,
        states=states,source_only_stages=[name for name in states if name.startswith('pattern_zero')],
        source_only_qualification='Original zero-total damage behavior; production fit-local zero-total mutation is unsupported',
        skill_undo_differences=skill_undo_differences,work_trace=trace,resolved_item_ids=original.resolved,command_trace=original.trace,
        original_point_calls=graph.point_calls,roots=dict(boundary.roots),forbidden_attempts=boundary.attempts,
        network_attempts=plumbing.NETWORK_ATTEMPTS,
        prepare_qualification='Original service.recalc LOCAL only; candidate inherited admission reset is independently qualified elsewhere',
        elapsed_seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        limits=dict(address_space_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],external_timeout_seconds=180))
    boundary.close(); dump(args.output,result)
    print('PASS G04',args.suite,len(states),'stages',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--suite',choices=SUITES,required=True)
    args=parser.parse_args(); args.source=args.source.resolve(); args.database=args.database.resolve(strict=True)
    try: run(args)
    except BaseException as error:
        if not args.output.exists(): dump(args.output,dict(status='failed',suite=args.suite,error=repr(error),traceback=traceback.format_exc(),partial_evidence=PROGRESS))
        raise
