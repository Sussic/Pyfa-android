#!/usr/bin/env python3
"""D02.1 original-only command/EOS exporter; never imports android_bridge.

The source is the retained reconstructed pinned-lineage checkout, not a clean
checkout of the semantic pin. Read-only existing supplemental game data is used.
Real original AST command bodies, original InternalCommandHistory and service
getFit/recalc/fill/checkStates are executed. Only wx command storage/event/window
plumbing and Market's pure item lookups are replaced with documented small shims.
Each sample explicitly invokes original service.recalc (LOCAL); ordinary desktop
getFit does not itself guarantee LOCAL cache context after projection evaluation.
"""
import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.abc
import json
import math
from pathlib import Path
import sqlite3
import sys
from time import time
from types import ModuleType, SimpleNamespace as NS, MethodType
from weakref import WeakSet
import uuid
PROCESS_NONCE=uuid.uuid4().hex
NETWORK_ATTEMPTS=[]
def network_guard(event,values):
    if event in {'socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo'}:
        NETWORK_ATTEMPTS.append(event)
        raise AssertionError('Original offline proof: '+event)
sys.addaudithook(network_guard)

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from tools.android_reference.reference import snapshot, compare, SOURCE_COMMIT, REL_TOL, ABS_TOL
from tools.android_reference.multisource.cases import fixtures, scenario, assert_witnesses, LABELS, DAMP, SKILL


class NeverAdapter(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'android_bridge', 'mobile_runtime'}:
            raise AssertionError('Original oracle must never import ' + fullname)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def original_source(source):
    sys.meta_path.insert(0, NeverAdapter())
    sys.path.insert(0, str(source))
    import eos.config
    database = Path(ARGS.database).resolve()
    eos.config.saveddata_connectionstring = 'sqlite:///:memory:'
    eos.config.gamedata_connectionstring = lambda:sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)
    eos.config.gamedataCache = False
    eos.config.set_lang('en')
    import eos.db
    return eos.config


class Original:
    def __init__(self, source):
        import eos.db
        from logbook import Logger
        from eos.const import FittingModuleState, FittingSlot
        from eos.saveddata.module import Module
        from eos.saveddata.drone import Drone
        from eos.saveddata.fighter import Fighter
        from eos.saveddata.fit import Fit as EosFit
        self.source, self.hashes, self.fits, self.resolved, self.trace = source, {}, {}, {}, []
        self.sample_evidence=[]
        noop = lambda *a, **k:None
        class Command:
            def __init__(self, *args, **kwargs): pass
        class Processor:
            def __init__(self, *args, **kwargs): self.Commands = []
            def Submit(self, command):
                ok = command.Do()
                if ok: self.Commands.append(command)
                return ok
            def Undo(self):
                if not self.Commands: return False
                command = self.Commands[-1]
                ok = command.Undo()
                if ok: self.Commands.pop()
                return ok
            def ClearCommands(self): self.Commands.clear()
        market = NS(getItem=lambda key,**kw:eos.db.getItem(key),
                    getGroupByItem=lambda item:item.group, getMarketGroupByItem=lambda item:item.marketGroup)
        service = NS(_loadedFits=WeakSet(), serviceFittingOptions={'useGlobalForceReload':False}, processors={})
        self.service = service
        common = dict(wx=NS(Command=Command, CommandProcessor=Processor, PostEvent=noop),
                      eos=eos, math=math, time=time, Logger=Logger, pyfalog=NS(debug=noop, info=noop, warning=noop),
                      FittingModuleState=FittingModuleState, FittingSlot=FittingSlot,
                      Module=Module, Drone=Drone, Fighter=Fighter,
                      EosModule=Module, EosDrone=Drone, EosFighter=Fighter, EosFit=EosFit,
                      gui=NS(mainFrame=NS(MainFrame=NS(getInstance=noop))), GE=NS(FitChanged=noop),
                      Market=NS(getInstance=lambda:market), Fit=NS(getInstance=lambda:service,processors={}),
                      makeReprStr=lambda obj, fields:str(type(obj)))
        self.scope = common
        # Retain original publication and market-group policy for script selection.
        market_path='service/market.py'
        market_tree=ast.parse((source/market_path).read_bytes())
        self.hashes[market_path]=sha(source/market_path)
        assert (source/market_path).read_bytes()==(REPO/market_path).read_bytes()
        for field in ('ITEMS_FORCEPUBLISHED','ITEMS_FORCEDMARKETGROUP','ROOT_MARKET_GROUPS'):
            node=next(n for n in ast.walk(market_tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr==field for t in n.targets))
            setattr(market,field,ast.literal_eval(node.value))
        force_group=next(n for n in ast.walk(market_tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='ITEMS_FORCEGROUP' for t in n.targets))
        forced_names={ast.literal_eval(key) for key in force_group.value.keys}
        def ordinary_group(item):
            assert item.typeName not in forced_names,'Fixture needs original forced-group setup'
            return item.group
        market.getGroupByItem=ordinary_group
        market.SHOWN_MARKET_GROUPS=eos.db.getMarketTreeNodeIds(market.ROOT_MARKET_GROUPS)
        market.getMarketGroup=eos.db.getMarketGroup
        for name in ('getPublicityByItem','getMarketGroupByItem'):
            self.extract(market_path,name,common)
            setattr(market,name,MethodType(common[name],market))
        for name in ('getFit','recalc','fill','checkStates'):
            self.extract('service/fit.py',name,common)
            setattr(service,name,MethodType(common[name],service))
        self.extract('service/fit.py','deleteFit',common)
        delete=common['deleteFit']; self.delete = delete.__func__ if isinstance(delete,staticmethod) else delete
        for name in ('InternalCommandHistory','ModuleInfo','DroneInfo','FighterInfo','restoreCheckedStates','restoreRemovedDummies','getSimilarModPositions'):
            self.extract('gui/fitCommands/helpers.py', name, common)
        self.extract('service/ammo.py','getModuleFlatAmmo',common)
        if isinstance(common['getModuleFlatAmmo'],staticmethod):common['getModuleFlatAmmo']=common['getModuleFlatAmmo'].__func__
        package = ModuleType('_d02_original');package.__path__=[];sys.modules[package.__name__]=package
        calc = {
            'projectedFit':['add','changeAmount','changeState','changeProjectionRange','remove'],
            'module':['projectedAdd','projectedRemove','projectedChangeStates','projectedChangeProjectionRange','changeCharges','localChangeStates'],
            'drone':['projectedAdd','projectedRemove','projectedChangeState','projectedChangeProjectionRange','projectedChangeAmount'],
            'fighter':['projectedAdd','projectedRemove','projectedChangeState','projectedChangeProjectionRange','changeAmount','abilityToggleStates'],
        }
        self.loaded=[]
        for family,files in calc.items():
            parent=ModuleType(package.__name__+'.'+family);parent.__path__=[];sys.modules[parent.__name__]=parent
            for filename in files:
                module=ModuleType(parent.__name__+'.'+filename);module.__package__=parent.__name__
                module.__dict__.update(common)
                relative='gui/fitCommands/calc/'+family+'/'+filename+'.py'
                self.extract_all(relative,module.__dict__)
                sys.modules[module.__name__]=module;self.loaded.append(module)
                common.update({k:v for k,v in module.__dict__.items() if k.startswith('Calc')})
        for module in self.loaded:
            module.__dict__.update({k:v for k,v in common.items() if k.startswith('Calc')})
        for relative in (
            'projectedFit/add','projectedFit/changeAmount','projectedChangeStates','projectedChangeProjectionRange','projectedRemove',
            'projectedModule/add','projectedModule/changeCharges','projectedDrone/add','projectedDrone/changeAmount',
            'projectedFighter/add','projectedFighter/changeAmount','projectedFighter/abilityToggleState',
            'localModule/changeCharges','localModule/changeStates'):
            self.extract_all('gui/fitCommands/gui/'+relative+'.py',common)

    def extract(self,path,name,scope):
        value=(self.source/path).read_bytes();self.hashes[path]=sha(self.source/path)
        assert value==(REPO/path).read_bytes(), 'Original/candidate source differs: '+path
        nodes=[n for n in ast.walk(ast.parse(value)) if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==name]
        assert len(nodes)==1,(path,name)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(self.source/path),'exec'),scope)

    def extract_all(self,path,scope):
        value=(self.source/path).read_bytes();self.hashes[path]=sha(self.source/path)
        assert value==(REPO/path).read_bytes(),path
        nodes=[n for n in ast.parse(value).body if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.Assign))]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(self.source/path),'exec'),scope)

    def item(self,name):
        import eos.db
        value=eos.db.getItem(name)
        assert value is not None,name
        self.resolved[name]=value.ID
        return value

    def make(self,key,spec):
        import eos.db
        from eos.const import FittingModuleState,FitSystemSecurity,ImplantLocation,FittingSlot
        from eos.saveddata.character import Character
        from eos.saveddata.damagePattern import DamagePattern
        from eos.saveddata.fit import Fit
        from eos.saveddata.ship import Ship
        from eos.saveddata.module import Module
        from eos.saveddata.drone import Drone
        fit=Fit(Ship(self.item(spec['ship'])),name=spec['name'])
        fit.character=Character('D02 original synthetic all V',defaultLevel=5)
        fit.damagePattern=DamagePattern(**spec['damage_pattern']);fit.targetProfile=None
        fit.factorReload=spec['factor_reload'];fit.implantLocation=ImplantLocation.FIT
        fit.systemSecurity=FitSystemSecurity[spec['security']['system']];fit.pilotSecurity=spec['security']['pilot'];fit.ignoreRestrictions=False
        for row in spec['modules']:
            if 'empty_slot' in row:
                fit.modules.appendIgnoreEmpty(Module.buildEmpty(FittingSlot[row['empty_slot']].value))
                continue
            module=Module(self.item(row['name']));module.owner=fit;module.state=FittingModuleState[row['state']]
            if row.get('charge'):module.charge=self.item(row['charge'])
            fit.modules.appendIgnoreEmpty(module)
        for row in spec['drones']:
            drone=Drone(self.item(row['name']));drone.owner=fit;drone.amount=row['amount'];drone.amountActive=row['active'];fit.drones.append(drone)
        eos.db.saveddata_session.add(fit);eos.db.saveddata_session.flush()
        self.service.recalc(fit)
        assert fit.fits and all(m.isEmpty or m.fits(fit) for m in fit.modules),key
        assert fit.droneBandwidthUsed<=fit.ship.getModifiedItemAttr('droneBandwidth'),key
        self.service.fill(fit);eos.db.commit();fit.inited=True
        self.fits[key]=fit

    def run_command(self,name,**kwargs):
        command=self.scope[name](**kwargs)
        result=command.Do()
        self.trace.append(dict(command=name,arguments=kwargs,changed=bool(result)))
        return command

    def apply(self,step):
        op,args=step['op'],step['args'];fit=self.fits.get(args.get('fit'));cmd=None
        if op=='share_profile':
            from eos.saveddata.character import Character
            self.shared=Character('D02 shared synthetic all V',defaultLevel=5)
            for key in ('source_a','source_b'):self.fits[key].character=self.shared
            return
        if op=='shared_skill':
            skill=self.shared.getSkill(self.item(SKILL));previous=skill.activeLevel
            def change(level):
                skill.setLevel(level,persist=True)
                for key in ('source_a','source_b'):self.service.recalc(self.fits[key])
            change(args['level'])
            return NS(Undo=lambda:change(previous),Do=lambda:change(args['level']))
        if op=='delete_source':
            self.delete(fit.ID);del self.fits[args['fit']];return
        if op in ('add_link','link_amount','link_range','link_active','remove_link'):
            source,target=self.fits[args['source']],self.fits[args['target']]
            if op=='add_link':return self.run_command('GuiAddProjectedFitsCommand',fitID=target.ID,projectedFitIDs=[source.ID],amount=1)
            if op=='link_amount':return self.run_command('GuiChangeProjectedFitAmountCommand',fitID=target.ID,projectedFitID=source.ID,amount=args['amount'])
            if op=='link_range':return self.run_command('GuiChangeProjectedItemsProjectionRangeCommand',fitID=target.ID,items=[source],projectionRange=args['range_m'])
            if op=='link_active':
                assert source.getProjectionInfo(target.ID).active != args['active']
                return self.run_command('GuiChangeProjectedItemStatesCommand',fitID=target.ID,mainItem=source,items=[source],click='left')
            return self.run_command('GuiRemoveProjectedItemsCommand',fitID=target.ID,items=[source],amount=math.inf)
        if op in ('local_charge','local_active'):
            index=next(i for i,m in enumerate(fit.modules) if not m.isEmpty and m.item.name==DAMP)
            if op=='local_charge':return self.run_command('GuiChangeLocalModuleChargesCommand',fitID=fit.ID,positions=[index],chargeItemID=self.item(args['charge']).ID)
            return self.run_command('GuiChangeLocalModuleStatesCommand',fitID=fit.ID,mainPosition=index,positions=[index],click='left')
        if op.startswith('add_'):
            name={'add_module':'GuiAddProjectedModuleCommand','add_drone':'GuiAddProjectedDroneCommand','add_fighter':'GuiAddProjectedFighterCommand'}[op]
            return self.run_command(name,fitID=fit.ID,itemID=self.item(args['item']).ID)
        if op=='selected_charges':
            modules=fit.projectedModules;main=modules[args['main']]
            positions=self.scope['getSimilarModPositions'](modules,main) if args['scope']=='SIMILAR' else [i for i,m in enumerate(modules) if i in args['selection'] and self.scope['getModuleFlatAmmo'](m).issubset(self.scope['getModuleFlatAmmo'](main))]
            return self.run_command('GuiChangeProjectedModuleChargesCommand',fitID=fit.ID,positions=positions,chargeItemID=None if args['charge'] is None else self.item(args['charge']).ID)
        if op=='remove_projector':
            obj={'module':fit.projectedModules,'drone':fit.projectedDrones,'fighter':fit.projectedFighters}[args['family']][args['index']]
            return self.run_command('GuiRemoveProjectedItemsCommand',fitID=fit.ID,items=[obj],amount=math.inf)
        if op=='fighter_amount':return self.run_command('GuiChangeProjectedFighterAmountCommand',fitID=fit.ID,position=args['index'],amount=args['amount'])
        if op=='fighter_ability':
            fighter=fit.projectedFighters[args['index']]
            ability=next(a for a in fighter.abilities if a.effect.isImplemented and 'Web' in a.effect.name)
            return self.run_command('GuiToggleProjectedFighterAbilityStateCommand',fitID=fit.ID,mainPosition=args['index'],positions=[args['index']],effectID=ability.effectID)
        container={'drone':fit.projectedDrones,'fighter':fit.projectedFighters,'module':fit.projectedModules}[args['family']]
        obj=container[args['index']]
        if op=='projector_range':return self.run_command('GuiChangeProjectedItemsProjectionRangeCommand',fitID=fit.ID,items=[obj],projectionRange=args['range_m'])
        if op=='projector_active':return self.run_command('GuiChangeProjectedItemStatesCommand',fitID=fit.ID,mainItem=obj,items=[obj],click='left')
        raise AssertionError(op)

    def raw(self,fit):
        from eos.const import FittingModuleState,FittingSlot
        names={f.ID:key for key,f in self.fits.items()}
        modules=lambda rows:[dict(empty_slot=FittingSlot(m.slot).name) if m.isEmpty else dict(name=m.item.name,state=FittingModuleState(m.state).name,charge=m.charge.name if m.charge else None) for m in rows]
        projected=modules(fit.projectedModules)
        for row,mod in zip(projected,fit.projectedModules):row['range_m']=mod.projectionRange
        return dict(name=fit.name,ship=fit.ship.item.name,modules=modules(fit.modules),
            drones=[dict(name=d.item.name,amount=d.amount,active=d.amountActive) for d in fit.drones],
            projected_modules=projected,
            projected_drones=[dict(name=d.item.name,amount=d.amount,active=d.amountActive,range_m=d.projectionRange) for d in fit.projectedDrones],
            projected_fighters=[dict(name=f.item.name,amount=f.amount,active=f.active,range_m=f.projectionRange,abilities=[dict(effect_id=a.effectID,active=a.active) for a in sorted(f.abilities,key=lambda a:a.effectID)]) for f in fit.projectedFighters],
            skills={s.item.name:s.activeLevel for s in fit.character.skills if s.activeLevel!=5},
            projections=sorted([dict(source_id=names[s.ID],range_m=s.getProjectionInfo(fit.ID).projectionRange,active=s.getProjectionInfo(fit.ID).active,amount=s.getProjectionInfo(fit.ID).amount) for s in fit.projectedFits],key=lambda r:r['source_id']))

    def sample(self,order):
        stats={};strengths={}
        for key in order:
            if key not in self.fits:continue
            fit=self.fits[key]
            self.service.recalc(fit)
            value=snapshot(fit);value['scan_resolution']=dict(value=fit.ship.getModifiedItemAttr('scanResolution'),unit='mm')
            assert len(value)==39
            stats[key]=value
            if key.startswith('source'):
                damp=next(m for m in fit.modules if not m.isEmpty and m.item.name==DAMP)
                strengths[key]={name:damp.getModifiedItemAttr(name) for name in ('maxTargetRangeBonus','scanResolutionBonus')}
        self.sample_evidence.append(dict(order=order,source_strengths=strengths,projection_iteration={key:[next(label for label,value in self.fits.items() if value is source) for source in fit.projectedFits] for key,fit in self.fits.items()}))
        return dict(stats=stats,raw={key:self.raw(fit) for key,fit in self.fits.items()})


def main(args):
    cfg=original_source(args.source)
    original=Original(args.source)
    values=fixtures(args.suite);order=list(reversed(LABELS)) if args.reverse else list(LABELS)
    for key in order:original.make(key,values[key])
    states={'initial':original.sample(order)};stage_evidence={'initial':deepcopy(original.sample_evidence[-1])}
    for step in scenario(args.suite,args.reverse):
        before=original.sample(order);command=original.apply(step)
        states[step['name']]=original.sample(order)
        stage_evidence[step['name']]=deepcopy(original.sample_evidence[-1])
        opposite=original.sample(list(reversed(order)))
        compare(states[step['name']],opposite,'original_read_order.'+step['name'])
        if step['args'].get('history'):
            command.Undo();states[step['name']+'_undo']=original.sample(order)
            compare(before,states[step['name']+'_undo'],'original_undo.'+step['name'])
            command.Do();states[step['name']+'_redo']=original.sample(order)
            compare(states[step['name']],states[step['name']+'_redo'],'original_redo.'+step['name'])
        print('ORIGINAL',args.suite,step['name'],flush=True)
    assert_witnesses(args.suite,states,compare)
    if args.suite=='publication':
        for key in ('source_a','source_b'):
            assert states['shared_skill_zero']['raw'][key]['skills'][SKILL]==0
            before=stage_evidence['shared_profile']['source_strengths'][key]
            after=stage_evidence['shared_skill_zero']['source_strengths'][key]
            assert before['maxTargetRangeBonus'] < after['maxTargetRangeBonus'],(key,before,after)
    imports={}
    for name,module in list(sys.modules.items()):
        assert name.split('.')[0] not in {'android_bridge','mobile_runtime'}
        path=getattr(module,'__file__',None)
        if path and name.split('.')[0] in {'eos','utils'}:
            relative=Path(path).resolve().relative_to(args.source).as_posix()
            assert Path(path).read_bytes()==(REPO/relative).read_bytes(),relative
            imports[relative]=sha(path)
    import eos.db
    assert not NETWORK_ATTEMPTS
    dump(args.output,dict(schema_version=1,suite=args.suite,reverse=args.reverse,pid=__import__('os').getpid(),process_nonce=PROCESS_NONCE,network_attempts=NETWORK_ATTEMPTS,
        source_commit=SOURCE_COMMIT,source_kind='retained reconstructed pinned-lineage; supplemental existing dataset',
        original_source=str(args.source),stage_source_evidence=stage_evidence,states=states,inputs=values,steps=scenario(args.suite,args.reverse),
        source_files=original.hashes,original_imports=imports,resolved_item_ids=original.resolved,eos_settings=dict(cfg.settings),
        dataset_metadata=dict(eos.db.gamedata_session.execute('SELECT field_name,field_value FROM metadata').fetchall()),
        preserved_projection_sha256=sha(REPO/'tools/android_reference/fixtures/projection.json'),
        comparator_tolerance=dict(relative=REL_TOL,absolute=ABS_TOL),
        plumbing='wx Command/CommandProcessor storage and event/window no-ops; Market pure item lookup. Original AST and original InternalCommandHistory unchanged.',
        read_schedule='Original service.recalc immediately before each 39-field LOCAL snapshot; forward/reverse independently sampled.'))
    print('PASS ORIGINAL',args.suite,len(states),'stages',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--database',required=True)
    parser.add_argument('--suite',choices=('composition','incoming','outgoing','publication'),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reverse',action='store_true')
    ARGS=parser.parse_args();ARGS.source=ARGS.source.resolve();main(ARGS)
