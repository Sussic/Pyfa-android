#!/usr/bin/env python3
"""Independent G05.1 receipt comparison; default invocation is pure unit tests.

Only --execute boots the candidate. Original v2 receipts are immutable numerical
oracles. Internal observations measure identity/state/work, never expected rates.
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

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO), str(REPO/'android/app/src/main/python')]
from tools.android_reference.remote_repair_range.cases import SUITES, fixtures, steps, requests

REL_TOL, ABS_TOL = 1e-10, 1e-9
PROCESS_NONCE = uuid.uuid4().hex
CUTS = dict(ordinary='armor_active', drones='shield_partial_two', spool='spool_three_cycles',
            ancillary='reload_off_shield_reloaded', linked='shared_repair_skill_four')
PROGRESS = {}


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def exact(expected, actual, label):
    assert encode(expected) == encode(actual), (label, expected, actual)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, exclusive=True):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def numeric(expected, actual, label):
    assert type(expected) in (int, float) and type(actual) in (int, float), label
    assert math.isfinite(expected) and math.isfinite(actual), label
    if expected == 0: assert actual == 0, (label, expected, actual)
    else: assert math.isclose(expected, actual, rel_tol=REL_TOL, abs_tol=ABS_TOL), (label, expected, actual)


def compare_curve(expected, actual, label):
    assert set(actual) == {'fit_id','revision','source_rates','x','y'}
    xs, ys = expected['distance_km'], expected['repair_hp_s']
    exact(xs, actual['x'], label+'.exact ordered coordinates')
    assert len(xs) == len(ys) == len(actual['y']), label
    assert len(xs) == 1 or 51 <= len(xs) <= 201, label
    for index, (left, right) in enumerate(zip(ys, actual['y'])):
        numeric(left, right, label+'.y['+str(index)+']')
    assert all(a <= b for a,b in zip(actual['x'], actual['x'][1:]))


def frozen(value):
    if is_dataclass(value): return {f.name:frozen(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict): return {k:frozen(v) for k,v in value.items()}
    if isinstance(value, (set, frozenset)): return sorted(frozen(v) for v in value)
    if isinstance(value, (tuple, list)): return [frozen(v) for v in value]
    return value


def full_history(session):
    """Payload and shared object identity; same algorithm as D02.2 evidence."""
    legacy = session.graph._bridge._history
    legacy_actions, legacy_ids = [], {}
    def legacy_ref(action):
        if id(action) not in legacy_ids:
            legacy_ids[id(action)] = len(legacy_actions); legacy_actions.append(frozen(action))
        return legacy_ids[id(action)]
    legacy_rows = {key:dict(actions=[legacy_ref(a) for a in actions], cursor=cursor)
                   for key,(actions,cursor) in sorted(legacy.rows.items())}
    actions, ids = [], {}
    def action_ref(action):
        if id(action) not in ids:
            ids[id(action)] = len(actions); value = frozen(action)
            value['legacy_token_ref'] = None if action.legacy_token is None else legacy_ref(action.legacy_token)
            actions.append(value)
        return ids[id(action)]
    rows = {key:dict(actions=[action_ref(a) for a in values], cursor=cursor)
            for key,(values,cursor) in sorted(session.history.rows.items())}
    return dict(sequence=session.history.sequence, rows=rows, actions=actions,
                legacy_rows=legacy_rows, legacy_actions=legacy_actions)



def skill_history_difference(suite, stage, label, expected, actual):
    if encode(expected)==encode(actual): return None
    assert suite=='linked' and stage=='shared_repair_skill_four_undo' and label in ('source_a','source_b')
    exact({'Capital Remote Armor Repair Systems':None},expected,'precise original prerequisite history artifact')
    exact({},actual,'precise candidate typed-undo restoration')
    return dict(original=deepcopy(expected),candidate=deepcopy(actual))


def original_effective_skill(source, active_level):
    path=source/'eos/saveddata/character.py'
    assert path.read_bytes()==(REPO/'eos/saveddata/character.py').read_bytes()
    cls=next(n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.ClassDef) and n.name=='Skill')
    node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='level')
    scope={}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope)
    obj=NS(character=NS(name='G05.1 custom synthetic',alphaClone=None),activeLevel=active_level)
    return dict(active_level=active_level,effective_level=scope['level'].fget(obj),source_sha256=sha(path))


def original_spool_functions(source):
    """Execute exact retained original AST, with inert enum namespace only."""
    scope = dict(math=math, sys=sys, SpoolType=NS(SPOOL_SCALE=0, CYCLE_SCALE=1, TIME=2, CYCLES=3))
    paths = {'eos/utils/float.py': ('keepDigits', 'floatUnerr'),
             'eos/utils/spoolSupport.py': ('calculateSpoolup', 'resolveSpoolOptions')}
    for relative, names in paths.items():
        path = source/relative
        assert path.read_bytes() == (REPO/relative).read_bytes(), relative
        nodes = [node for node in ast.parse(path.read_bytes()).body
                 if isinstance(node, ast.FunctionDef) and node.name in names or
                 isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)]
        assert len(nodes) == len(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
    return scope, {name:sha(source/name) for name in paths}


def spool_zero_proof(source, parameters):
    scope, bindings = original_spool_functions(source)
    assert len(parameters) == 3 and all(type(x) in (int,float) and math.isfinite(x) and x > 0 for x in parameters)
    results = []
    for kind in (scope['SpoolType'].SPOOL_SCALE, scope['SpoolType'].CYCLES):
        options = NS(spoolType=scope['SpoolType'].SPOOL_SCALE, spoolAmount=1.0, force=False)
        resolved = scope['resolveSpoolOptions'](options, NS(spoolType=kind, spoolAmount=0.0))
        exact([kind, 0.0], list(resolved), 'original explicit zero beats default force=False')
        result = scope['calculateSpoolup'](*parameters, *resolved)
        assert result == (0, 0, 0), result
        results.append(dict(raw_type=kind, raw_amount=0.0, resolved=list(resolved), result=list(result)))
    exact(results[0]['result'], results[1]['result'], 'original zero spool equivalence')
    return dict(source_files=bindings, original_parameters=parameters, executions=results,
                qualification='Explicit equivalent-zero source proof; raw enum difference is retained')


class ReadBoundary:
    """Instrumentation is scoped to graph reads, never silently removes admission."""
    def __init__(self, owner):
        self.owner = owner; self.rows = []; self.active = None; self.forbidden = []
        self.depth = 0

    @contextmanager
    def install(self):
        from eos.saveddata.fit import Fit
        from eos.capSim import CapSimulator
        from eos.utils.cycles import CycleInfo, CycleSequence
        from eos.const import CalcType
        from android_bridge.offline import remote_repair_math as graph
        saved_calc = Fit.calculateModifiedAttributes
        saved_prepare = self.owner.session.engine.prepare_read
        saved_getter = graph.Distance2RpsGetter.getRange
        saved_point = graph.Distance2RpsGetter._calculatePoint
        saved_app = graph.getApplicationPerKey
        saved_cache = graph.CurrentRateCache.prepareRpsData
        def blocked(label):
            def stop(*args, **kwargs):
                self.forbidden.append(label); raise AssertionError('Forbidden graph read: '+label)
            return stop
        def calculated(fit, *args, **kwargs):
            row = self.active; assert row is not None
            kind = kwargs.get('type', args[1] if len(args)>1 else CalcType.LOCAL)
            row['calculation_kinds'][CalcType(kind).name] += 1
            if self.depth == 0: row['top_calculations'].append(dict(handle=id(fit), kind=CalcType(kind).name))
            self.depth += 1
            try: return saved_calc(fit, *args, **kwargs)
            finally: self.depth -= 1
        def prepared(fit):
            row = self.active; assert row is not None
            before = len(row['top_calculations'])
            value = saved_prepare(fit)
            exact([dict(handle=id(fit), kind='LOCAL')], row['top_calculations'][before:], 'exact LOCAL preparation')
            row['prepares'].append(id(fit)); row['ready_handle'] = id(fit)
            row['events'].append(dict(event='prepare_LOCAL_complete', handle=id(fit)))
            return value
        def columns(layer, original):
            def value(column, fit):
                row = self.active
                assert row['ready_handle'] == id(fit), 'source column before exact LOCAL prepare'
                row['events'].append(dict(event='source_column', layer=layer, handle=id(fit)))
                return original(column, fit)
            return value
        def ranged(getter, xRange, miscParams, src, tgt):
            row = self.active; fit = src.item
            assert row['ready_handle'] == id(fit), 'curve before exact LOCAL prepare'
            before = len(row['curves'])
            assert len(row['prepares']) == before+1, 'not exactly one prepare per curve'
            exact([dict(handle=handle,kind='LOCAL') for handle in row['prepares']],row['top_calculations'],'no extra top-level calculation between preparations/curves')
            assert row['events'][-4:] == [dict(event='prepare_LOCAL_complete',handle=id(fit))]+[
                dict(event='source_column',layer=layer,handle=id(fit)) for layer in ('shield','armor','hull')]
            record = self.owner.workload(fit)
            record.update(handle=id(fit), point_calls_before=row['point_calls'], application_calls_before=row['application_calls'])
            row['events'].append(dict(event='curve_start', handle=id(fit)))
            result = saved_getter(getter, xRange, miscParams, src, tgt)
            record.update(point_calls=row['point_calls']-record.pop('point_calls_before'),
                          application_calls=row['application_calls']-record.pop('application_calls_before'), points=len(result[0]))
            assert record['point_calls'] == record['application_calls'] == record['points']
            row['curves'].append(record); row['ready_handle'] = None
            return result
        def pointed(*args, **kwargs):
            self.active['point_calls'] += 1
            return saved_point(*args, **kwargs)
        def applied(*args, **kwargs):
            self.active['application_calls'] += 1
            return saved_app(*args, **kwargs)
        def cache_prepared(cache, src, ancReload, maxTime):
            assert maxTime is None, 'Graph entered a non-null time path'
            value = saved_cache(cache,src,ancReload,maxTime)
            assert value is True, 'Null-time adapter must preserve original True return'
            self.active['null_time_cache_calls'].append(dict(max_time=maxTime,ancillary_reload=ancReload,result=value))
            return value
        with ExitStack() as stack:
            for cls, names in ((Fit,('simulateCap','_Fit__runCapSim','getCapSimData','calculateSustainableTank')),
                               (CapSimulator,('run',)), (CycleInfo,('iterCycles',)), (CycleSequence,('iterCycles',))):
                for name in names: stack.enter_context(patch.object(cls,name,blocked(cls.__name__+'.'+name)))
            for cls,name,label in ((Fit,'_Fit__generateDrain','allowed_admission_drain'),(CapSimulator,'reset','allowed_admission_reset')):
                original = getattr(cls,name)
                def counted(*args, original=original, label=label, **kwargs):
                    self.active['scans'][label] += 1
                    return original(*args,**kwargs)
                stack.enter_context(patch.object(cls,name,counted))
            for name, field in (('activeModulesIter','modules'),('activeDronesIter','drones')):
                original = getattr(Fit,name)
                def scan(fit,*args,original=original,name=name,field=field,**kwargs):
                    self.active['scans'][name+'_calls'] += 1
                    self.active['scans'][name+'_container_rows'] += len(getattr(fit,field))
                    yield from original(fit,*args,**kwargs)
                stack.enter_context(patch.object(Fit,name,scan))
            original_remote = Fit.getRemoteReps
            def remote(fit, spoolOptions=None):
                self.active['scans']['source_getRemoteReps_calls'] += 1
                if spoolOptions not in fit._Fit__remoteRepMap:
                    self.active['scans']['source_cache_misses'] += 1
                    self.active['scans']['source_module_rows'] += len(fit.modules)
                    self.active['scans']['source_drone_rows'] += len(fit.drones)
                return original_remote(fit,spoolOptions=spoolOptions)
            stack.enter_context(patch.object(Fit,'getRemoteReps',remote))
            stack.enter_context(patch.object(Fit,'calculateModifiedAttributes',calculated))
            stack.enter_context(patch.object(self.owner.session.engine,'prepare_read',prepared))
            stack.enter_context(patch.object(graph.Distance2RpsGetter,'getRange',ranged))
            stack.enter_context(patch.object(graph.Distance2RpsGetter,'_calculatePoint',pointed))
            stack.enter_context(patch.object(graph,'getApplicationPerKey',applied))
            stack.enter_context(patch.object(graph.CurrentRateCache,'prepareRpsData',cache_prepared))
            for layer in ('Shield','Armor','Hull'):
                cls = getattr(graph,layer+'RRColumn')
                stack.enter_context(patch.object(cls,'_getValue',columns(layer.lower(),cls._getValue)))
            yield

    @contextmanager
    def measure(self, request):
        assert self.active is None
        row = dict(stage=self.owner.stage, request=deepcopy(request), prepares=[], top_calculations=[],
                   calculation_kinds=Counter(), scans=Counter(), events=[], curves=[], ready_handle=None,
                   point_calls=0, application_calls=0, null_time_cache_calls=[])
        self.active = row; started = time.monotonic()
        try:
            with self.install(): yield row
        finally:
            row['elapsed_seconds'] = time.monotonic()-started
            self.rows.append(row); self.active = None


class Candidate:
    def __init__(self, args, oracle):
        self.args, self.oracle = args, oracle
        self.stage = 'startup'; self.states = {}; self.failures = []; self.history_proof = []; self.raw_differences = []
        self.checks = []; self.network_attempts = []; self.spool_proof = None
        def network(event, values):
            if event in {'socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo'}:
                self.network_attempts.append(event); raise AssertionError('Offline request: '+event)
        sys.addaudithook(network)
        import mobile_runtime as runtime
        self.runtime = runtime
        database = Path(os.environ['PYFA_DATABASE']).resolve()
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as connection:
            metadata = dict(connection.execute('SELECT field_name,field_value FROM metadata'))
        self.order = oracle['input_order']; self.specs = fixtures(args.suite)
        for label, spec in self.specs.items():
            spec['modules'] = deepcopy(oracle['states']['initial']['raw'][label]['modules'])
        runtime.boot(str(database),json.dumps(dict(dataset_metadata=metadata,database_logical_sha256=os.environ['PYFA_DATASET_SHA'])),
                     json.dumps(dict(self.specs[self.order[0]],edit={})),str(args.store))
        boot = json.loads(runtime.bridge_bootstrap()); assert boot['status']=='ok',boot
        self.session = runtime._bridge
        self.ids = {row['name'].removeprefix('G05.1 original '):row['id'] for row in boot['fits']}
        if args.phase == 'seed':
            for label in self.order[1:]:
                result = self.edit('create_fit',dict(spec=self.specs[label])); self.ids[label] = result['fits'][0]['id']
        self.labels = {value:key for key,value in self.ids.items()}
        exact(sorted(self.order),sorted(self.ids),'all candidate fit identities')
        self.boundary = ReadBoundary(self)

    def item(self, name):
        import eos.db
        item = eos.db.getItem(name); assert item is not None,name
        return item.ID

    def edit(self, operation, arguments):
        ids = {arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}
        request = dict(version=1,request_id='g051-'+operation,session_id=self.session.session_id,
                       operation=operation,arguments=arguments,expected_revisions={k:self.session._revisions[k] for k in ids})
        result = json.loads(self.runtime.bridge_dispatch(json.dumps(request)))
        assert result['status']=='ok',(operation,result)
        return result

    def feature(self, operation, arguments):
        request = dict(version=1,request_id='g051-'+operation,context=self.session.context(),operation=operation,
                       arguments=arguments,anchor_fit_id=self.ids['source_a'])
        result = json.loads(self.runtime.offline_feature_dispatch(json.dumps(request)))
        assert result['ok'],(operation,result)
        return result

    def local_index(self, label, name=None):
        rows = self.session._records[self.ids[label]]['spec']['modules']
        return next(i for i,row in enumerate(rows) if row.get('name')==name or name is None and 'empty_slot' not in row)

    def profile(self):
        return self.session.feature_state()['bindings'][self.ids['source_a']]['profile_id']

    def apply(self, step):
        op,args = step['op'],step['args']; key = self.ids.get(args.get('fit'))
        if op == 'state': return self.edit('set_module_states',dict(fit_id=key,module_indices=[self.local_index(args['fit'],args['item'])],state=args['state']))
        if op == 'charge': return self.edit('set_module_charge',dict(fit_id=key,position=self.local_index(args['fit'],args['item']),charge_id=self.item(args['charge']) if args['charge'] else None))
        if op == 'drone_amount': return self.edit('set_drone_amount',dict(fit_id=key,position=args['index'],amount=args['amount']))
        if op == 'spool':
            amount = None if args['amount'] is None else int(args['amount'])
            assert args['amount'] is None or amount==args['amount']
            return self.edit('set_module_spool',dict(fit_id=key,position=self.local_index(args['fit']),cycles=amount))
        if op == 'add_link': return self.edit('add_projected_fit',dict(source_id=self.ids[args['source']],target_id=self.ids[args['target']]))
        if op == 'share_profile':
            self.feature('create_profile',dict(name='G05.1 shared all V',source='builtin:all5'))
            profile = next(row['profile_id'] for row in self.session.feature_state()['profiles'] if row['name']=='G05.1 shared all V')
            for label in ('source_a','source_b'): result = self.feature('assign_profile',dict(fit_id=self.ids[label],profile_id=profile))
            return result['bridge']
        if op == 'repair_skill':
            profile = self.profile(); row = next(r for r in self.session.feature_state()['profiles'] if r['profile_id']==profile)
            return self.feature('set_profile_skill',dict(profile_id=profile,revision=row['revision'],skill_id=self.item('Remote Armor Repair Systems'),level=args['level']))['bridge']
        if op == 'delete_source':
            result = self.edit('delete_fit',dict(fit_id=key,resolve_references=True))
            del self.ids[args['fit']]; del self.labels[key]
            assert key not in self.session._records and key not in self.session.history.rows
            assert all(row['source_id']!=key for record in self.session._records.values() for row in record['projections'])
            return result
        raise AssertionError(op)

    def state(self, identities=True):
        """No calculated getter; remains available for post-disable evidence."""
        bridge = self.session.graph._bridge; graph = self.session.graph
        result = dict(graph=deepcopy(graph._state), snapshots=deepcopy(bridge._snapshots),
            records=deepcopy(bridge._records), revisions=deepcopy(bridge._revisions),
            modified=deepcopy(bridge._modified), recent=deepcopy(bridge._recent), sample_id=bridge.sample_id,
            store_current=frozen(graph._store.current), file_sha256=sha(self.args.store),
            full_history=full_history(self.session), session_id=bridge.session_id,
            revision_floor=deepcopy(graph._revision_floor), profile_floor=deepcopy(self.session._profile_floor),
            binding_floor=deepcopy(self.session._binding_floor))
        if identities:
            result['live_identities'] = dict(fits={k:id(v) for k,v in bridge._fits.items()},
                engine_fits=[id(v) for v in self.session.engine._fits],
                modules={k:[id(m) for m in v.modules] for k,v in bridge._fits.items()},
                drones={k:[id(d) for d in v.drones] for k,v in bridge._fits.items()},
                characters={k:id(v.character) for k,v in bridge._fits.items()},
                integrated_actions={k:[id(a) for a in actions] for k,(actions,_) in self.session.history.rows.items()},
                legacy_actions={k:[id(a) for a in actions] for k,(actions,_) in bridge._history.rows.items()})
        return result

    def durable(self):
        graph = self.session.graph
        return dict(graph=deepcopy(graph._state),snapshots=deepcopy(graph._bridge._snapshots),
                    store_current=frozen(graph._store.current),file_sha256=sha(self.args.store))

    def captured(self):
        from android_bridge.offline.graph_history import inputs
        return inputs(self.session.graph._state)

    def raw(self, label):
        from eos.const import FittingModuleState,FittingSlot
        fit = self.session._fits[self.ids[label]]
        modules = [dict(empty_slot=FittingSlot(m.slot).name) if m.isEmpty else dict(name=m.item.name,
            state=FittingModuleState(m.state).name,charge=m.charge.name if m.charge else None) for m in fit.modules]
        names = {id(f):self.labels[key] for key,f in self.session._fits.items()}
        assert not fit.projectedModules and not fit.projectedDrones and not fit.projectedFighters
        return dict(name=fit.name,ship=fit.ship.item.name,modules=modules,
            drones=[dict(name=d.item.name,amount=d.amount,active=d.amountActive) for d in fit.drones],
            projected_modules=[],projected_drones=[],projected_fighters=[],
            skills={s.item.name:s.activeLevel for s in fit.character.skills if s.activeLevel!=5},
            projections=sorted([dict(source_id=names[id(s)],range_m=s.getProjectionInfo(fit.ID).projectionRange,
                active=s.getProjectionInfo(fit.ID).active,amount=s.getProjectionInfo(fit.ID).amount) for s in fit.projectedFits],key=lambda row:row['source_id']),
            factor_reload=fit.factorReload,character_id=fit.character.ID,
            module_spool=[dict(type=m.spoolType,amount=m.spoolAmount,force_reload=m.forceReload) for m in fit.modules if not m.isEmpty],
            projection_iteration=[names[id(s)] for s in fit.projectedFits])

    def verify_raw(self, stage):
        expected = self.oracle['states'][stage]['raw']; actual = {label:self.raw(label) for label in self.ids}
        exact(sorted(expected),sorted(actual),'raw endpoints '+stage)
        for label,want in expected.items():
            got = actual[label]
            for field in set(want)-{'character_id','module_spool','skills'}: exact(want[field],got[field],stage+'.'+label+'.'+field)
            skill_difference=skill_history_difference(self.args.suite,stage,label,want['skills'],got['skills'])
            assert type(got['character_id']) is int and got['character_id']>0
            differences = dict(stage=stage,fit=label,original_character_id=want['character_id'],candidate_character_id=got['character_id'],spool=[])
            if skill_difference is not None:
                fit=self.session._fits[self.ids[label]]
                modules=[dict(item_id=m.item.ID,name=m.item.name,requires_capital_skill=m.item.requiresSkill('Capital Remote Armor Repair Systems')) for m in fit.modules if not m.isEmpty]
                assert modules and all(row['requires_capital_skill'] is False for row in modules)
                candidate_skill=fit.character.getSkill('Capital Remote Armor Repair Systems')
                assert candidate_skill.activeLevel==candidate_skill.level==5
                source=Path(self.oracle['source'])
                skill_difference.update(original_resolution=original_effective_skill(source,None),candidate_resolution=original_effective_skill(source,candidate_skill.activeLevel),occupied_modules=modules,
                    qualification='Original undo leaves dependent skill unlearned; exact candidate undo restores All-V input. This difference is irrelevant only to these non-capital fixture modules; Effect2354 changes capacitorNeed only.')
                assert skill_difference['original_resolution']['effective_level']==0 and skill_difference['candidate_resolution']['effective_level']==5
                differences['skill_history']=skill_difference
            assert len(want['module_spool'])==len(got['module_spool'])
            for left,right in zip(want['module_spool'],got['module_spool']):
                if encode(left)==encode(right): continue
                assert self.args.suite=='spool' and label=='mutadaptive'
                assert left['force_reload'] is right['force_reload'] is None
                assert (left['type']==0 and left['amount']==0.0 and right['type']==3 and right['amount']==0) or (
                    left['type']==right['type']==3 and left['amount']==right['amount']==3)
                differences['spool'].append(dict(original=left,candidate=right))
            if differences['spool']:
                fit = self.session._fits[self.ids[label]]; module = next(m for m in fit.modules if not m.isEmpty)
                parameters = [module.getModifiedItemAttr('repairMultiplierBonusMax'),module.getModifiedItemAttr('repairMultiplierBonusPerCycle'),module.rawCycleTime/1000]
                self.spool_proof = spool_zero_proof(Path(self.oracle['source']),parameters)
            self.raw_differences.append(differences)
        if self.args.suite=='linked' and 'source_a' in self.ids and stage.startswith(('shared_','delete_')):
            bindings = self.session.feature_state()['bindings']
            exact(bindings[self.ids['source_a']]['profile_id'],bindings[self.ids['source_b']]['profile_id'],'shared profile identity')
        return actual

    def workload(self, fit):
        active = []
        for family,container in (('module',fit.modules),('drone',fit.drones)):
            for index,value in enumerate(container):
                if getattr(value,'isEmpty',False) or not value.isRemoteRepping(): continue
                active.append(dict(family=family,index=index,item_id=value.item.ID,name=value.item.name,
                    active_amount=getattr(value,'amountActive',1),capacitor_need=value.getModifiedItemAttr('capacitorNeed',0)))
        return dict(local_module_container_rows=len(fit.modules),occupied_local_modules=sum(not m.isEmpty for m in fit.modules),
                    local_drone_container_rows=len(fit.drones),active_remote_rows=active,
                    factor_reload=fit.factorReload,lock_range_m=fit.maxTargetRange,drone_control_range_m=fit.extraAttributes['droneControlRange'])

    def request(self, row, order):
        return dict(version=1,request_id='g051-'+self.stage+'-'+row['name'],context=self.session.context(),
            fits=[dict(fit_id=self.ids[label],revision=self.session._revisions[self.ids[label]]) for label in order],
            x=dict(quantity='distance',unit='km',range=deepcopy(row['distance_km'])),y=dict(quantity='repair_rate',unit='HP/s'),
            time=None,ancillary_reload=row['ancReload'],ignore_lock_range=row['ignoreLockRange'],
            ignore_drone_control_range=row['ignoreDCR'],budget_ms=10000)

    def read(self, request, cancelled=lambda:False, stable=True):
        before = self.state(); bytes_before = self.args.store.read_bytes()
        original_verify = self.session.graph._verify_durable
        with self.boundary.measure(request) as measured, patch.object(self.session.graph,'_verify_durable',wraps=original_verify) as verified:
            result = json.loads(self.runtime.offline_remote_repair_samples(json.dumps(request),NS(get=cancelled)))
        measured['durable_checks'] = verified.call_count; measured['result_ok'] = result['ok']
        assert verified.call_count==2, 'Read omitted durable pre/post check'
        if stable:
            exact(before,self.state(),'read preserved complete state'); assert self.args.store.read_bytes()==bytes_before
        assert not self.boundary.forbidden
        return result,measured

    def observe(self, stage, initial=False, record=True):
        self.stage = stage; expected = self.oracle['states'][stage]
        raw = self.verify_raw(stage); forward = {}
        original_requests = requests(self.args.suite,initial)
        exact(original_requests,next(r['requests'] for r in self.oracle['request_trace'] if r['stage']==stage),'original request assumptions')
        for direction, order in (('forward',[k for k in self.order if k in self.ids]),('reverse',[k for k in reversed(self.order) if k in self.ids])):
            curves = {label:[] for label in order}
            for index, row in enumerate(original_requests):
                request = self.request(row,order); response, measured = self.read(request)
                assert response['ok'],response
                assert set(response)=={'version','request_id','ok','context','x','y','time','ancillary_reload','ignore_lock_range','ignore_drone_control_range','total_points','series','error'}
                exact(1,response['version'],'response version'); exact(request['request_id'],response['request_id'],'request identity')
                for key in ('context','x','y','time','ancillary_reload','ignore_lock_range','ignore_drone_control_range'):
                    exact(request[key],response[key],'echo '+key)
                assert response['error'] is None and len(response['series'])==len(order)
                exact([self.ids[label] for label in order],[s['fit_id'] for s in response['series']],'series order')
                assert response['total_points']==sum(len(s['x']) for s in response['series'])
                exact([id(self.session._fits[self.ids[label]]) for label in order],measured['prepares'],'one prepare per selected fit')
                assert len(measured['curves'])==len(order)
                for label, series, work in zip(order,response['series'],measured['curves']):
                    want = expected['fits'][label]; exact(self.session._revisions[self.ids[label]],series['revision'],'revision identity')
                    assert set(series['source_rates'])=={'shield','armor','hull'}
                    for layer,value in want['source_columns'].items():
                        exact('HP/s',value['unit'],'source unit'); numeric(value['value'],series['source_rates'][layer],'source '+layer)
                    compare_curve(want['curves'][index],series,stage+'.'+label+'.'+row['name'])
                    for field in ('local_module_container_rows','occupied_local_modules','local_drone_container_rows'):
                        exact(want['inputs'][field],work[field],'work '+field)
                    exact(want['inputs']['effective_factor_reload'],work['factor_reload'],'effective factorReload')
                    assert want['source_service_options']['useGlobalForceReload'] is work['factor_reload']
                    numeric(want['inputs']['lock_range_m'],work['lock_range_m'],'lock range')
                    numeric(want['inputs']['drone_control_range_m'],work['drone_control_range_m'],'drone control range')
                    original_active = [{k:v for k,v in item.items() if k!='average_cycle_ms'} for item in want['inputs']['active_remote_rows']]
                    exact(original_active,work['active_remote_rows'],'active remote source rows')
                    curves[label].append(series)
            if direction=='forward': forward=curves
            else: exact(forward,curves,'reverse read order values '+stage)
        value = dict(fits=forward,raw=raw,durable=self.durable(),history=full_history(self.session))
        if record: self.states[stage]=value
        self.checks.append(dict(stage=stage,forward_reverse_equal=True,exact_read_state_preserved=True))
        print('CANDIDATE G05.1',self.args.suite,stage,flush=True)
        return value

    def failures_matrix(self):
        from android_bridge.offline import remote_repair_math as graph
        label = next(k for k in self.order if k in self.ids)
        baseline = self.request(requests(self.args.suite,False)[0],[label])
        def rejected(name, request, code, cancelled=lambda:False):
            response,work = self.read(request,cancelled)
            assert set(response)=={'version','request_id','ok','error'} and response['ok'] is False,response
            exact(code,response['error']['code'],name)
            self.failures.append(dict(kind=name,result=response,durable_checks=work['durable_checks'],state_preserved=True))
        value = deepcopy(baseline); value['context']['generation'] += 1
        rejected('stale_context',value,'stale_context')
        value = deepcopy(baseline); value['fits'][0]['revision'] += 1
        rejected('stale_revision',value,'stale_fit')
        value = deepcopy(baseline); value['fits'][0]['fit_id'] = 'missing-synthetic-fit'
        rejected('missing_fit',value,'fit_not_found')
        value = deepcopy(baseline); value['time'] = 1
        rejected('unsupported_time',value,'invalid_request')
        value = deepcopy(baseline); value['unexpected'] = True
        rejected('unknown_field',value,'invalid_request')
        rejected('cancelled',baseline,'cancelled',lambda:True)
        # Fail inside original point work so the normal LOCAL preparation still runs.
        with patch.object(graph,'getApplicationPerKey',side_effect=RuntimeError('injected graph calculation error')):
            rejected('point_error',baseline,'engine_error')
        # Patch the called _recalculate, keeping the normal prepare wrapper intact.
        with patch.object(self.session.engine,'_recalculate',side_effect=RuntimeError('injected prepare error')):
            rejected('prepare_error',baseline,'engine_error')
        for name in ('replaced_handle','missing_handle_during_read','revision_during_read'):
            before = self.state(); raw_bytes = self.args.store.read_bytes()
            key = self.ids[label]; fits = self.session.graph._bridge._fits; revisions = self.session.graph._bridge._revisions
            handle,revision = fits[key],revisions[key]
            saved_getter = graph.Distance2RpsGetter.getRange; mutations = []
            def changed(*args,**kwargs):
                output = saved_getter(*args,**kwargs)
                if name=='replaced_handle': fits[key]=object()
                elif name=='missing_handle_during_read': del fits[key]
                else: revisions[key]+=1
                mutations.append(name); return output
            try:
                with patch.object(graph.Distance2RpsGetter,'getRange',changed):
                    response,work = self.read(baseline,stable=False)
                assert response['ok'] is False and set(response)=={'version','request_id','ok','error'},response
                exact('fit_not_found' if name=='missing_handle_during_read' else 'stale_fit',response['error']['code'],name)
                assert mutations==[name]
            finally:
                fits[key]=handle; revisions[key]=revision
            exact(before,self.state(),'controlled injection restored exact state'); assert self.args.store.read_bytes()==raw_bytes
            self.failures.append(dict(kind=name,result=response,durable_checks=work['durable_checks'],state_preserved_after_restoring_injection=True))
        # A stale request retained across a real edit is tested in the main loop.
        self.checks.append(dict(failure_matrix=True,no_partial_results=True))

    def terminal_durable_failure(self):
        """Five reopen processes cover pre/post verification and all result kinds."""
        from android_bridge.offline import remote_repair_math as graph
        modes = dict(ordinary=('success',1),drones=('success',2),spool=('cancelled',2),
                     ancillary=('engine_error',2),linked=('cancelled',1))
        mode,fail_on = modes[self.args.suite]
        from android_bridge.offline import remote_repair_samples as sampling
        original_sampler = sampling.sample_remote_repair; sampler_results = []
        def sampled(*args,**kwargs):
            result = original_sampler(*args,**kwargs)
            sampler_results.append(deepcopy(result)); return result
        label = next(k for k in self.order if k in self.ids)
        request = self.request(requests(self.args.suite,False)[0],[label])
        before = self.state(); raw_bytes = self.args.store.read_bytes(); calls=[]
        original_read = self.session._store._read
        def fail_read():
            calls.append(len(calls)+1)
            if len(calls)==fail_on: raise OSError('Injected durable read failure')
            return original_read()
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.session._store,'_read',side_effect=fail_read))
            stack.enter_context(patch.object(sampling,'sample_remote_repair',sampled))
            if mode=='engine_error': stack.enter_context(patch.object(graph,'getApplicationPerKey',side_effect=RuntimeError('injected graph point error')))
            with self.boundary.measure(request) as work:
                response = json.loads(self.runtime.offline_remote_repair_samples(json.dumps(request),NS(get=lambda:mode=='cancelled')))
        exact('reopen_required',response['error']['code'],'durable read error')
        assert response['ok'] is False and set(response)=={'version','request_id','ok','error'}
        if fail_on==1 or mode=='cancelled': assert work['point_calls']==0 and not work['curves']
        elif mode=='engine_error': assert work['point_calls']==1 and not work['curves']
        else: assert work['point_calls']>0 and len(work['curves'])==1
        if fail_on==1: assert not sampler_results, 'Sampler entered after failed durable precheck'
        else:
            assert len(sampler_results)==1
            actual_result=sampler_results[0]
            if mode=='success': assert actual_result['ok'] is True and actual_result['error'] is None
            else: assert actual_result['ok'] is False and actual_result['error']['code']==mode
        assert len(calls)==fail_on and not self.session._available
        exact(before,self.state(),'terminal durable failure state'); assert self.args.store.read_bytes()==raw_bytes
        self.failures.append(dict(kind='terminal_durable_read',underlying_result=mode,fail_on_check=fail_on,
            actual_read_calls=calls,result=response,sampler_results=sampler_results,disabled=True,exact_state_and_bytes_preserved=True,
            point_calls=work['point_calls'],completed_curves=len(work['curves'])))


def run(args):
    started = time.monotonic(); oracle = json.loads(args.oracle.read_text())
    assert oracle['status']=='passed' and oracle['suite']==args.suite and oracle['process_nonce']!=PROCESS_NONCE
    assert 0 < resource.getrlimit(resource.RLIMIT_AS)[0] <= 1024**3
    exact(fixtures(args.suite),oracle['inputs'],'same declared inputs')
    exact(steps(args.suite),oracle['steps'],'same original schedule')
    if args.phase=='seed': assert not args.store.exists()
    before_store = args.store.read_bytes() if args.store.exists() else None
    candidate = Candidate(args,oracle)
    PROGRESS.update(states=candidate.states,failures=candidate.failures,checks=candidate.checks,reads=candidate.boundary.rows)
    exact(oracle['settings'],candidate.session.engine.settings,'EOS settings')
    exact(oracle['dataset_metadata'],candidate.session.engine.metadata,'dataset metadata')
    for name,item_id in oracle['resolved_item_ids'].items(): exact(item_id,candidate.item(name),'resolved item '+name)
    schedule = steps(args.suite); cut = next(i for i,s in enumerate(schedule) if s['name']==CUTS[args.suite])+1
    checkpoint = Path(str(args.store)+'.checkpoint.json')
    if args.phase=='seed':
        candidate.observe('initial',initial=True)
        candidate.failures_matrix()
        chosen = schedule[:cut]
    else:
        saved = json.loads(checkpoint.read_text())
        assert saved['process_nonce']!=PROCESS_NONCE and saved['session_id']!=candidate.session.session_id
        assert args.store.read_bytes()==before_store
        exact(saved['durable'],candidate.durable(),'fresh process exact durable graph/snapshots/bytes')
        assert all(candidate.session.history_details(key)['undo_count']==candidate.session.history_details(key)['redo_count']==0 for key in candidate.ids.values())
        assert candidate.session.history.sequence==0 and not candidate.session.history.rows and not candidate.session.graph._bridge._history.rows
        old = saved['last_request']; response,_ = candidate.read(old)
        assert response['ok'] is False and response['error']['code']=='stale_context'
        candidate.states.update(saved['states']); candidate.raw_differences.extend(saved['raw_differences'])
        candidate.history_proof.extend(saved['history_proof']); candidate.spool_proof = saved['spool_proof']
        candidate.observe(saved['last_stage'],record=False)
        candidate.checks.append(dict(fresh_process_reopen=True,bytes_graph_revisions_equal=True,
            old_session_request_rejected=True,session_identity_changed=True,transient_histories_empty=True))
        chosen = schedule[cut:]
    previous = 'initial' if args.phase=='seed' else saved['last_stage']
    for step in chosen:
        name = step['name']; args_step = step['args']
        owner = args_step.get('fit',args_step.get('target','source_a'))
        old_request = candidate.request(requests(args.suite,False)[0],[k for k in candidate.order if k in candidate.ids])
        before = candidate.captured(); count = candidate.session.history_details(candidate.ids[owner])['undo_count'] if args_step.get('history') else None
        candidate.apply(step); after = candidate.captured(); candidate.observe(name)
        response,_ = candidate.read(old_request)
        assert response['ok'] is False and response['error']['code']=='stale_context','retained pre-edit graph request should be stale'
        if args_step.get('history'):
            fit_id = candidate.ids[owner]
            assert candidate.session.history_details(fit_id)['undo_count']==count+1,'edit must add exactly one history action'
            candidate.edit('undo',dict(fit_id=fit_id)); exact(before,candidate.captured(),'typed complete input undo '+name)
            candidate.observe(name+'_undo')
            candidate.edit('redo',dict(fit_id=fit_id)); exact(after,candidate.captured(),'typed complete input redo '+name)
            candidate.observe(name+'_redo')
            candidate.history_proof.append(dict(stage=name,owner=owner,one_action=True,typed_input_undo_redo=True,before=before,after=after))
            previous = name+'_redo'
        else: previous=name
        write(Path(str(args.output)+'.partial.json'),dict(stage=previous,states=candidate.states,reads=candidate.boundary.rows,
            failures=candidate.failures,history_proof=candidate.history_proof),exclusive=False)
    if args.phase=='seed':
        write(checkpoint,dict(process_nonce=PROCESS_NONCE,session_id=candidate.session.session_id,durable=candidate.durable(),
            last_stage=previous,states=candidate.states,raw_differences=candidate.raw_differences,history_proof=candidate.history_proof,
            spool_proof=candidate.spool_proof,last_request=candidate.request(requests(args.suite,False)[0],[k for k in candidate.order if k in candidate.ids])))
    else:
        exact(sorted(oracle['states']),sorted(candidate.states),'all original stages covered')
        candidate.terminal_durable_failure()
    assert not candidate.runtime._forbidden and not candidate.network_attempts and not candidate.boundary.forbidden
    curves = sum(len(value) for state in candidate.states.values() for value in state['fits'].values())
    points = sum(len(row['x']) for state in candidate.states.values() for value in state['fits'].values() for row in value)
    if args.phase=='reopen':
        expected_curves = sum(len(fit['curves']) for stage in oracle['states'].values() for fit in stage['fits'].values())
        expected_points = sum(len(curve['distance_km']) for stage in oracle['states'].values() for fit in stage['fits'].values() for curve in fit['curves'])
        exact(expected_curves,curves,'complete original curve count'); exact(expected_points,points,'complete original coordinate count')
    result = dict(status='passed',suite=args.suite,phase=args.phase,pid=os.getpid(),process_nonce=PROCESS_NONCE,
        oracle_sha256=sha(args.oracle),original_process_nonce=oracle['process_nonce'],states=candidate.states,
        checks=candidate.checks,failures=candidate.failures,history_proof=candidate.history_proof,
        raw_representation_differences=candidate.raw_differences,original_zero_spool_proof=candidate.spool_proof,
        reads=candidate.boundary.rows,recorded_stages=len(candidate.states),
        recorded_fit_observations=sum(len(state['fits']) for state in candidate.states.values()),recorded_curves=curves,recorded_points=points,
        actual_point_calls=sum(row['point_calls'] for row in candidate.boundary.rows),
        actual_application_calls=sum(row['application_calls'] for row in candidate.boundary.rows),
        network_attempts=candidate.network_attempts,forbidden_attempts=candidate.boundary.forbidden,
        no_desktop_imports=not candidate.runtime._forbidden,source_qualification=oracle['source_kind'],
        tolerance=dict(coordinates='exact typed binary64 values, order, duplicate occurrences and count',relative_rate=REL_TOL,absolute_rate_hp_s=ABS_TOL,zero='exact'),
        limits=dict(address_space_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],external_timeout_seconds=180,
                    per_request_budget_ms=10000,max_fits=8,max_points_per_fit=201),
        coverage_limitations=['Finite synthetic suites; no general engine-work bound from point count',
            'Reciprocal links alone do not prove causal LOCAL numerical changes',
            'Read instrumentation excludes fixture boot/mutation snapshots, which use inherited engine behavior',
            'Original SPOOL_SCALE zero vs public CYCLES zero is explicitly retained and source-proved equivalent',
            'Clean-pin dataset, Android execution and release qualification remain open'],
        elapsed_seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    write(args.output,result)
    print('PASS G05.1',args.phase,args.suite,len(candidate.states),'stages',curves,'curves',points,'points',flush=True)


class PureCandidateTests(unittest.TestCase):
    def curve(self):
        expected=dict(distance_km=[1.0,1.0,2.0],repair_hp_s=[3.0,3.0,0.0])
        actual=dict(fit_id='a',revision=1,source_rates=dict(shield=3.0,armor=0.0,hull=0.0),x=[1.0]*50+[2.0],y=[3.0]*50+[0.0])
        expected.update(distance_km=deepcopy(actual['x']),repair_hp_s=deepcopy(actual['y']))
        return expected,actual

    def test_exact_raw_preserves_type(self):
        for value in (0,False,1e-15):
            with self.assertRaises(AssertionError): exact(0.0,value,'raw')

    def test_coordinate_occurrences_order_and_count_are_exact(self):
        expected,actual=self.curve(); compare_curve(expected,actual,'good')
        for mutate in (lambda r:r['x'].pop(), lambda r:r['x'].__setitem__(0,math.nextafter(1.0,math.inf)),
                       lambda r:r['x'].reverse(),lambda r:r['y'].pop()):
            value=deepcopy(actual); mutate(value)
            with self.assertRaises(AssertionError): compare_curve(expected,value,'bad')

    def test_rates_tolerance_is_explicit_and_zero_exact(self):
        numeric(1.0,1.0+1e-10,'rate')
        for expected,actual in ((0.0,1e-12),(1.0,1.01),(1.0,True),(1.0,math.inf)):
            with self.assertRaises(AssertionError): numeric(expected,actual,'bad')

    def test_original_zero_spool_source_equivalence(self):
        result=spool_zero_proof(REPO,[2.5,0.1,6.0])
        self.assertEqual(result['executions'][0]['result'],result['executions'][1]['result'])
        self.assertNotEqual(result['executions'][0]['raw_type'],result['executions'][1]['raw_type'])

    def test_full_history_preserves_shared_identity_and_payload(self):
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class Action:
            label: str
            changes: tuple
            legacy_token: object=None
        old=Action('legacy',(('x',None,0.0),)); shared=Action('shared',(),old)
        session=NS(history=NS(sequence=2,rows={'a':((shared,),1),'b':((shared,),1)}),
                   graph=NS(_bridge=NS(_history=NS(rows={'a':((old,),1)}))))
        first=full_history(session); self.assertEqual(first['rows']['a'],first['rows']['b'])
        session.history.rows['b']=((deepcopy(shared),),1)
        with self.assertRaises(AssertionError): exact(first,full_history(session),'identity drift')

    def test_linked_skill_undo_difference_is_narrow_and_retained(self):
        original={'Capital Remote Armor Repair Systems':None}
        result=skill_history_difference('linked','shared_repair_skill_four_undo','source_a',original,{})
        self.assertEqual(result,dict(original=original,candidate={}))
        self.assertIsNone(skill_history_difference('ordinary','initial','mixed',{},{}))
        for suite,stage,label,left,right in (
            ('ordinary','shared_repair_skill_four_undo','source_a',original,{}),
            ('linked','shared_repair_skill_five','source_a',original,{}),
            ('linked','shared_repair_skill_four_undo','unrelated',original,{}),
            ('linked','shared_repair_skill_four_undo','source_a',dict(original,other=0),{}),
            ('linked','shared_repair_skill_four_undo','source_a',original,{'Capital Remote Armor Repair Systems':0})):
            with self.assertRaises(AssertionError): skill_history_difference(suite,stage,label,left,right)
        self.assertEqual(original_effective_skill(REPO,None)['effective_level'],0)
        self.assertEqual(original_effective_skill(REPO,5)['effective_level'],5)

    def test_no_eos_or_candidate_import_in_pure_suite(self):
        self.assertFalse(any(name.startswith(('eos.','android_bridge.','mobile_runtime')) for name in sys.modules))

    def test_request_and_stage_schedule_matches_reviewed_receipts(self):
        total=[0,0,0,0]
        for suite in SUITES:
            oracle=json.loads((REPO.parent/'preflight-evidence'/(suite+'-v2.json')).read_text())
            exact(fixtures(suite),oracle['inputs'],'fixtures')
            exact(steps(suite),oracle['steps'],'steps')
            expected=['initial']
            for step in steps(suite):
                expected.append(step['name'])
                if step['args'].get('history'): expected.extend((step['name']+'_undo',step['name']+'_redo'))
            exact(sorted(expected),sorted(oracle['states']),'complete stages')
            for trace in oracle['request_trace']: exact(requests(suite,trace['stage']=='initial'),trace['requests'],'requests')
            total[0]+=len(oracle['states'])
            for stage in oracle['states'].values():
                total[1]+=len(stage['fits'])
                for fit in stage['fits'].values():
                    total[2]+=len(fit['curves']); total[3]+=sum(len(c['distance_km']) for c in fit['curves'])
        self.assertEqual(total,[39,87,129,8850])


if __name__ == '__main__':
    if '--execute' not in sys.argv:
        unittest.main()
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
