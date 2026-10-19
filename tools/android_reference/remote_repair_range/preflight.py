#!/usr/bin/env python3
"""G05.1 independent original getter exporter; no Android calculations imported."""
import argparse
import ast
from collections import Counter
from copy import copy, deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
sys.dont_write_bytecode = True
import time
import traceback
from types import SimpleNamespace as NS
import uuid

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from tools.android_reference.multisource import oracle as plumbing
from tools.android_reference.remote_repair_range.cases import SUITES, fixtures, steps, requests
from tools.android_reference.reference import SOURCE_COMMIT, compare

PROGRESS = {}


def exact(a, b, label):
    encode = lambda v: json.dumps(v, sort_keys=True, allow_nan=False, separators=(',', ':'))
    assert encode(a) == encode(b), label


def finite(value, label):
    assert type(value) in (int, float) and math.isfinite(value), (label, value)
    return value


class Boundary:
    """Original-only finite fixtures never reset/run cap or iterate time cycles."""
    def __init__(self):
        self.saved = []; self.attempts = []; self.roots = Counter(); self.scans = Counter()
    def forbid(self, cls, name):
        old = getattr(cls, name); self.saved.append((cls, name, old))
        def blocked(*args, **kwargs):
            label = cls.__name__ + '.' + name
            self.attempts.append(label)
            raise AssertionError('Forbidden original G05.1 entry: ' + label)
        setattr(cls, name, property(blocked) if isinstance(old, property) else blocked)
    def install(self):
        from eos.saveddata.fit import Fit
        from eos.capSim import CapSimulator
        from eos.utils.cycles import CycleInfo, CycleSequence
        from eos.const import CalcType
        for name in ('simulateCap', '_Fit__runCapSim', '_Fit__generateDrain', 'getCapSimData', 'calculateSustainableTank'):
            self.forbid(Fit, name)
        for name in ('capUsed', 'capRecharge', 'capStable', 'capState', 'capDelta', 'tank', 'effectiveTank', 'sustainableTank', 'effectiveSustainableTank'):
            self.forbid(Fit, name)
        for name in ('reset', 'run'): self.forbid(CapSimulator, name)
        for cls in (CycleInfo, CycleSequence): self.forbid(cls, 'iterCycles')
        old = Fit.calculateModifiedAttributes; self.saved.append((Fit, 'calculateModifiedAttributes', old))
        def calculate(obj, *args, **kwargs):
            kind = kwargs.get('type', args[1] if len(args) > 1 else CalcType.LOCAL)
            self.roots[CalcType(kind).name] += 1
            return old(obj, *args, **kwargs)
        Fit.calculateModifiedAttributes = calculate
        for method, field in (('activeModulesIter', 'modules'), ('activeDronesIter', 'drones')):
            original = getattr(Fit, method); self.saved.append((Fit, method, original))
            def scan(obj, *args, original=original, method=method, field=field, **kwargs):
                self.scans[method + '_calls'] += 1
                self.scans[method + '_container_rows'] += len(getattr(obj, field))
                yield from original(obj, *args, **kwargs)
            setattr(Fit, method, scan)
        remote = Fit.getRemoteReps; self.saved.append((Fit, 'getRemoteReps', remote))
        def remote_reps(obj, spoolOptions=None):
            self.scans['source_getRemoteReps_calls'] += 1
            if spoolOptions not in obj._Fit__remoteRepMap:
                self.scans['source_getRemoteReps_cache_misses'] += 1
                self.scans['source_getRemoteReps_module_rows'] += len(obj.modules)
                self.scans['source_getRemoteReps_drone_rows'] += len(obj.drones)
            return remote(obj, spoolOptions=spoolOptions)
        Fit.getRemoteReps = remote_reps
    def close(self):
        for cls, name, value in reversed(self.saved): setattr(cls, name, value)


class Original(plumbing.Original):
    def __init__(self, source):
        super().__init__(source)
        self.scope['Market'].getInstance().storeRecentlyUsed = lambda *a, **k: None
        self.fixture_reload = {}
        for path, name in (
            ('gui/fitCommands/calc/module/changeSpool.py', 'CalcChangeModuleSpoolCommand'),
            ('gui/fitCommands/gui/localModule/changeSpool.py', 'GuiChangeLocalModuleSpoolCommand'),
            ('gui/fitCommands/calc/drone/localChangeAmount.py', 'CalcChangeLocalDroneAmountCommand')):
            self.extract(path, name, self.scope)
    def configure(self, key):
        self.service.serviceFittingOptions['useGlobalForceReload'] = self.fixture_reload[key]
        return dict(self.service.serviceFittingOptions)
    def make(self, key, spec):
        self.fixture_reload[key] = spec['factor_reload']
        self.configure(key)
        super().make(key, spec)
        assert self.fits[key].factorReload is spec['factor_reload'], 'Original service setting/input mismatch'
    def raw(self, fit):
        value = super().raw(fit)
        value.update(factor_reload=fit.factorReload, character_id=fit.character.ID,
                     module_spool=[dict(type=m.spoolType, amount=m.spoolAmount, force_reload=m.forceReload)
                                   for m in fit.modules if not m.isEmpty],
                     projection_iteration=[next(k for k, f in self.fits.items() if f is source) for source in fit.projectedFits])
        return value
    def apply(self, step):
        op, args = step['op'], step['args']; fit = self.fits.get(args.get('fit'))
        if fit is not None: self.configure(args['fit'])
        if op in ('state', 'charge'):
            index = next(i for i, m in enumerate(fit.modules) if not m.isEmpty and m.item.name == args['item'])
            if op == 'state':
                from eos.const import FittingModuleState
                command = self.run_command('GuiChangeLocalModuleStatesCommand', fitID=fit.ID, mainPosition=index, positions=[index], click='left')
                assert fit.modules[index].state == FittingModuleState[args['state']]
                return command
            charge = self.item(args['charge']).ID if args['charge'] else None
            return self.run_command('GuiChangeLocalModuleChargesCommand', fitID=fit.ID, positions=[index], chargeItemID=charge)
        if op == 'spool':
            from eos.const import SpoolType
            kind = SpoolType[args['spool_type']] if args['spool_type'] else None
            index = next(i for i, m in enumerate(fit.modules) if not m.isEmpty)
            return self.run_command('GuiChangeLocalModuleSpoolCommand', fitID=fit.ID, position=index, spoolType=kind, spoolAmount=args['amount'])
        if op == 'drone_amount':
            return self.run_command('CalcChangeLocalDroneAmountCommand', fitID=fit.ID, position=args['index'], amount=args['amount'])
        if op == 'repair_skill':
            skill = self.shared.getSkill(self.item('Remote Armor Repair Systems')); previous = skill.activeLevel
            def change(level):
                skill.setLevel(level, persist=True)
                for key in ('source_a', 'source_b'): self.service.recalc(self.fits[key])
            change(args['level'])
            return NS(Undo=lambda: change(previous), Do=lambda: change(args['level']))
        return super().apply(step)


class OriginalGraph:
    """Loads exact independent source bodies; GUI/settings shims do no arithmetic."""
    def __init__(self, original, boundary):
        import eos.config
        from abc import ABCMeta, abstractmethod
        from eos.calc import calculateRangeFactor
        from eos.utils.float import floatUnerr
        from eos.utils.spoolSupport import SpoolOptions, SpoolType
        from eos.utils.stats import RRTypes
        self.original, self.boundary = original, boundary
        self.options = {}; self.point_calls = 0; self.application_calls = 0
        self.scope = dict(math=math, ABCMeta=ABCMeta, abstractmethod=abstractmethod,
                          eos=eos, RRTypes=RRTypes, SpoolOptions=SpoolOptions,
                          SpoolType=SpoolType, copy=copy, floatUnerr=floatUnerr,
                          calculateRangeFactor=calculateRangeFactor,
                          GraphSettings=NS(getInstance=lambda: self.options), GraphColumn=object)
        for path, names in (
            ('graphs/data/base/getter.py', ('PointGetter', 'SmoothPointGetter')),
            ('graphs/data/base/cache.py', ('FitDataCache',)),
            ('graphs/calc.py', ('checkLockRange', 'checkDroneControlRange')),
            ('graphs/data/fitRemoteReps/calc.py', ('getApplicationPerKey',)),
            ('graphs/data/fitRemoteReps/cache.py', ('TimeCache',)),
            ('graphs/data/fitRemoteReps/getter.py', ('applyReps', 'YRpsMixin', 'XDistanceMixin', 'Distance2RpsGetter')),
            ('gui/builtinViewColumns/attributeDisplayGraph.py', ('ShieldRRColumn', 'ArmorRRColumn', 'HullRRColumn'))):
            for name in names: original.extract(path, name, self.scope)
        for name in ('_generateInternalForm', 'getRpsData', 'getRpsDataPoint', 'prepareRepAmountData', 'getRepAmountData', 'getRepAmountDataPoint'):
            boundary.forbid(self.scope['TimeCache'], name)
        self.cache = self.scope['TimeCache']()
        self.getter = self.scope['Distance2RpsGetter'](NS(_timeCache=self.cache))
        self.original_point = self.getter._calculatePoint
        def point(*args, **kwargs):
            self.point_calls += 1
            return self.original_point(*args, **kwargs)
        self.getter._calculatePoint = point
        original_application = self.scope['getApplicationPerKey']
        def application(*args, **kwargs):
            self.application_calls += 1
            return original_application(*args, **kwargs)
        self.scope['getApplicationPerKey'] = application
        path = 'graphs/data/fitRemoteReps/graph.py'
        data = (original.source / path).read_bytes(); original.hashes[path] = plumbing.sha(original.source / path)
        assert data == (REPO / path).read_bytes()
        cls = next(n for n in ast.parse(data).body if isinstance(n, ast.ClassDef) and n.name == 'FitRemoteRepsGraph')
        nodes = [n for n in cls.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('_normalizers', '_denormalizers') for t in n.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(original.source / path), 'exec'), self.scope)
        self.normalizer = self.scope['_normalizers'][('distance', 'km')]
        self.denormalizer = self.scope['_denormalizers'][('distance', 'km')]
    def columns(self, fit):
        result = {}
        for layer in ('Shield', 'Armor', 'Hull'):
            cls = self.scope[layer + 'RRColumn']
            value, unit = cls._getValue(object.__new__(cls), fit)
            result[layer.lower()] = dict(value=finite(value, layer), unit=unit)
        return result
    def sample(self, fit, request):
        assert request['time'] is None
        self.options = {name: request[name] for name in ('ignoreLockRange', 'ignoreDCR')}
        src = NS(item=fit); misc = dict(time=None, ancReload=request['ancReload'])
        normalized = [self.normalizer(v, src, None) for v in request['distance_km']]
        before_points, before_apps = self.point_calls, self.application_calls
        xs, ys = self.getter.getRange(normalized, misc, src, None)
        assert 1 <= len(xs) == len(ys) <= 201
        assert all(math.isfinite(v) for v in xs + ys)
        assert all(a <= b for a, b in zip(xs, xs[1:])), xs
        out = dict(request=deepcopy(request), distance_m=xs,
                   distance_km=[self.denormalizer(v, src, None) for v in xs],
                   repair_hp_s=ys, point_calls=self.point_calls-before_points,
                   application_calls=self.application_calls-before_apps)
        assert out['point_calls'] == out['application_calls'] == len(xs)
        # Original getPoint is separate source execution, exposing exact gates.
        probes = {0.0, fit.maxTargetRange, fit.maxTargetRange + 1,
                  fit.extraAttributes['droneControlRange'], fit.extraAttributes['droneControlRange'] + 1}
        for mod in fit.modules:
            if not mod.isEmpty and mod.isRemoteRepping():
                optimal, falloff = mod.maxRange or 0, mod.falloff or 0
                probes.update((optimal, optimal + 1, optimal + falloff, optimal + 3*falloff, optimal + 3*falloff + 1))
        out['probes'] = [dict(distance_m=x, repair_hp_s=finite(self.getter.getPoint(x, misc, src, None), 'probe')) for x in sorted(probes)]
        rr_map = self.getter._getRepsPerKey(src, request['ancReload'], None)
        applications = self.scope['getApplicationPerKey'](src, 0)
        out['zero_distance_parts'] = [dict(kind='module' if key in fit.modules else 'drone', item_id=key.item.ID,
                    name=key.item.name, repair={name: finite(getattr(value, name), name) for name in ('shield', 'armor', 'hull', 'capacitor')},
                    application=applications[key]) for key, value in rr_map.items()]
        assert self.cache._data == {}, 'Null-time path populated the time cache'
        return out


def capture_inputs(fit):
    from eos.const import FittingSlot, FittingHardpoint
    assert fit.fits and not fit.ignoreRestrictions
    assert not fit.fighters and not fit.projectedDrones and not fit.projectedFighters
    assert not fit.commandFits and not fit.implants and not fit.boosters
    modules = [m for m in fit.modules if not m.isEmpty]
    assert all(m.fits(fit) and m.isValidCharge(m.charge) for m in modules)
    assert all(m.item.published and (m.charge is None or m.charge.published) for m in modules)
    assert all(d.item.published and 0 <= d.amountActive <= d.amount for d in fit.drones)
    resources = {}
    for attr, out in (('cpu', 'cpuOutput'), ('power', 'powerOutput')):
        used, available = fit.getItemAttrOnlineSum(fit.modules, attr), fit.ship.getModifiedItemAttr(out)
        assert 0 <= finite(used, attr) <= finite(available, out)
        resources[attr] = dict(used=used, available=available)
    for label, used, available in (
        ('bandwidth', fit.droneBandwidthUsed, fit.ship.getModifiedItemAttr('droneBandwidth')),
        ('drone_bay', fit.droneBayUsed, fit.ship.getModifiedItemAttr('droneCapacity')),
        ('active_drones', sum(d.amountActive for d in fit.drones), fit.extraAttributes['maxActiveDrones'])):
        assert 0 <= finite(used, label) <= finite(available, label)
        resources[label] = dict(used=used, available=available)
    slots = {slot.name: fit.getSlotsFree(slot.value, False) for slot in FittingSlot}
    assert all(v >= 0 for v in slots.values())
    for hardpoint in (FittingHardpoint.TURRET, FittingHardpoint.MISSILE): assert fit.getHardpointsFree(hardpoint) >= 0
    rows = []
    for family, values in (('module', modules), ('drone', fit.drones)):
        for index, value in enumerate(values):
            if not value.isRemoteRepping(): continue
            cycle = value.getCycleParameters()
            assert cycle and finite(cycle.averageTime, 'average cycle') > 0
            rows.append(dict(family=family, index=index, item_id=value.item.ID, name=value.item.name,
                             average_cycle_ms=cycle.averageTime, active_amount=getattr(value, 'amountActive', 1),
                             capacitor_need=value.getModifiedItemAttr('capacitorNeed', 0)))
    return dict(legal=True, resources=resources, free_slots=slots,
                local_module_container_rows=len(fit.modules), occupied_local_modules=len(modules),
                local_drone_container_rows=len(fit.drones), active_remote_rows=rows,
                lock_range_m=fit.maxTargetRange, drone_control_range_m=fit.extraAttributes['droneControlRange'])


def raw_all(original):
    return {key: original.raw(fit) for key, fit in original.fits.items()}


def observe(original, graph, boundary, request_rows, order):
    raw_before = deepcopy(raw_all(original)); observations = {}; work = []
    for key in order:
        if key not in original.fits: continue
        fit = original.fits[key]
        roots_before = Counter(boundary.roots); scans_before = Counter(boundary.scans)
        service_options = original.configure(key)
        original.service.recalc(fit)
        assert fit.factorReload is original.fixture_reload[key], 'Original service setting/input mismatch'
        inputs = capture_inputs(fit)
        inputs.update(declared_factor_reload=original.fixture_reload[key], effective_factor_reload=fit.factorReload)
        columns = graph.columns(fit)
        observations[key] = dict(inputs=inputs, source_service_options=service_options, source_columns=columns,
                                 curves=[graph.sample(fit, request) for request in request_rows])
        work.append(dict(fit=key, roots=dict(boundary.roots-roots_before), scans=dict(boundary.scans-scans_before)))
    exact(raw_before, raw_all(original), 'Sampling changed original raw inputs')
    assert not boundary.attempts
    return dict(fits=observations, raw=raw_before), work


def witnesses(suite, states):
    initial = states['initial']['fits']
    def zero(key, state='initial', curve=0):
        return next(p['repair_hp_s'] for p in states[state]['fits'][key]['curves'][curve]['probes'] if p['distance_m'] == 0)
    if suite == 'ordinary':
        assert zero('mixed') > 0 and zero('empty') == zero('capacitor_only') == 0
        c = initial['mixed']['source_columns']; assert all(v['value'] > 0 for v in c.values())
        assert math.isclose(zero('mixed'), sum(v['value'] for v in c.values()), rel_tol=1e-12)
        assert initial['capacitor_only']['curves'][0]['zero_distance_parts'][0]['repair']['capacitor'] > 0
        ys = initial['mixed']['curves'][0]['repair_hp_s']; assert max(ys) > min(ys)
        assert len(ys) > 51
        adjacent = initial['mixed']['curves'][2]['distance_m']; assert len(adjacent) > len(set(adjacent))
        assert len(initial['mixed']['curves'][1]['distance_m']) == 1
        for layer in ('shield', 'armor', 'hull'):
            assert zero('mixed', layer+'_online') < zero('mixed')
            assert zero('mixed', layer+'_active') == zero('mixed')
    elif suite == 'drones':
        assert all(v['value'] > 0 for v in initial['maintenance']['source_columns'].values())
        assert zero('maintenance', 'shield_partial_two') > zero('maintenance')
        curves = initial['maintenance']['curves']
        assert any(p['repair_hp_s'] == 0 for p in curves[0]['probes'])
        assert all(p['repair_hp_s'] > 0 for p in curves[3]['probes'])
    elif suite == 'spool':
        assert zero('mutadaptive') > zero('mutadaptive', 'spool_three_cycles') > zero('mutadaptive', 'spool_zero') > 0
        assert zero('mutadaptive', 'spool_reset') == zero('mutadaptive')
    elif suite == 'ancillary':
        assert zero('reload_off', curve=0) < zero('reload_off', curve=1)
        for key in ('reload_off', 'reload_on'):
            total = sum(v['value'] for v in initial[key]['source_columns'].values())
            assert total == zero(key, curve=1 if key == 'reload_off' else 0), (key, total, zero(key, curve=0), zero(key, curve=1), states['initial']['raw'][key])
            assert zero(key, key+'_armor_unloaded', 1) < zero(key, curve=1)
    else:
        assert zero('source_a') > 0 and zero('unrelated') == 0
        assert zero('source_a', 'a_shield_online') < zero('source_a')
        assert zero('source_b', 'shared_repair_skill_four') == zero('source_b', 'shared_profile')
        def armor_cap(state):
            return next(row['capacitor_need'] for row in states[state]['fits']['source_b']['inputs']['active_remote_rows'] if row['name'] == 'Medium Remote Armor Repairer II')
        assert armor_cap('shared_repair_skill_four') > armor_cap('shared_profile')
        assert 'source_a' not in states['delete_source_a']['fits']


def run(args):
    started = time.monotonic(); dataset_sha = plumbing.sha(args.database)
    assert 0 < resource.getrlimit(resource.RLIMIT_AS)[0] <= 1024**3
    plumbing.ARGS = args; config = plumbing.original_source(args.source)
    boundary = Boundary(); boundary.install()
    original = Original(args.source); graph = OriginalGraph(original, boundary)
    inputs = fixtures(args.suite); schedule = steps(args.suite); order = list(inputs)
    for key in order: original.make(key, inputs[key])
    states = {}; trace = []; request_trace = []
    PROGRESS.update(dataset_sha256=dataset_sha, source_files=original.hashes, inputs=inputs, input_order=order, steps=schedule, states=states, work_trace=trace, request_trace=request_trace, forbidden_attempts=boundary.attempts, command_trace=original.trace)
    def take(name, initial=False):
        reqs = requests(args.suite, initial)
        forward, work = observe(original, graph, boundary, reqs, order)
        reverse, other_work = observe(original, graph, boundary, reqs, list(reversed(order)))
        compare(forward, reverse, 'original read order.' + name)
        states[name] = forward; request_trace.append(dict(stage=name, requests=reqs))
        trace.append(dict(stage=name, forward=work, reverse=other_work))
        print('ORIGINAL G05.1', args.suite, name, flush=True)
    take('initial', True)
    for step in schedule:
        before = deepcopy(raw_all(original)); command = original.apply(step); take(step['name'])
        if step['args'].get('history'):
            after = deepcopy(raw_all(original))
            if step['args'].get('fit'): original.configure(step['args']['fit'])
            command.Undo(); take(step['name']+'_undo')
            # Character.setLevel materializes prerequisite records, as in D02.2.
            if step['op'] != 'repair_skill': exact(before, raw_all(original), 'command undo raw')
            if step['args'].get('fit'): original.configure(step['args']['fit'])
            command.Do(); take(step['name']+'_redo'); exact(after, raw_all(original), 'command redo raw')
    witnesses(args.suite, states)
    imports = {}
    for name, module in list(sys.modules.items()):
        assert name.split('.')[0] not in {'android_bridge', 'mobile_runtime'}
        path = getattr(module, '__file__', None)
        if path:
            resolved = Path(path).resolve()
            try:
                relative = resolved.relative_to(args.source).as_posix()
            except ValueError:
                assert name.split('.')[0] not in {'eos', 'utils'}, ('Original module outside source', name, path)
            else:
                assert resolved.read_bytes() == (REPO / relative).read_bytes(), relative
                imports[relative] = plumbing.sha(resolved)
    import eos.db
    assert not boundary.attempts and not plumbing.NETWORK_ATTEMPTS
    assert dataset_sha == plumbing.sha(args.database)
    harness = [Path(__file__), Path(__file__).with_name('cases.py'), REPO/'tools/android_reference/multisource/oracle.py', REPO/'tools/android_reference/multisource/cases.py', REPO/'tools/android_reference/reference.py']
    result = dict(status='passed', suite=args.suite, pid=os.getpid(), process_nonce=uuid.uuid4().hex,
        source_commit=SOURCE_COMMIT, source_kind='retained reconstructed pinned-lineage; existing supplemental game data',
        source=str(args.source), source_files=original.hashes, original_imports=imports,
        dataset_sha256=dataset_sha, dataset_metadata=dict(eos.db.gamedata_session.execute('SELECT field_name,field_value FROM metadata').fetchall()),
        harness_files={str(p.relative_to(REPO)):plumbing.sha(p) for p in harness},
        fixture_files={'tools/android_reference/fixtures/output.json':plumbing.sha(REPO/'tools/android_reference/fixtures/output.json')},
        settings=dict(config.settings), inputs=inputs, input_order=order, steps=schedule,
        request_trace=request_trace, states=states, work_trace=trace, resolved_item_ids=original.resolved,
        command_trace=original.trace, original_point_calls=graph.point_calls,
        original_application_calls=graph.application_calls, roots=dict(boundary.roots),
        container_scans=dict(boundary.scans), forbidden_attempts=boundary.attempts,
        network_attempts=plumbing.NETWORK_ATTEMPTS, time_cache_empty=graph.cache._data == {},
        elapsed_seconds=time.monotonic()-started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        limits=dict(address_space_bytes=resource.getrlimit(resource.RLIMIT_AS)[0], external_timeout_seconds=180))
    boundary.close(); plumbing.dump(args.output, result)
    print('PASS G05.1', args.suite, len(states), 'stages', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'database', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--suite', choices=SUITES, required=True)
    args = parser.parse_args(); args.source = args.source.resolve(); args.database = args.database.resolve()
    try:
        run(args)
    except BaseException as error:
        if not args.output.exists():
            plumbing.dump(args.output, dict(status='failed', suite=args.suite, error=repr(error), traceback=traceback.format_exc(), partial_evidence=PROGRESS))
        raise
