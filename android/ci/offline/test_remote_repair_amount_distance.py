"""G05.2b pure synthetic amount route tests; no database or EOS fit execution."""
import ast
import hashlib
import math
import unittest
from collections import Counter
from copy import copy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from eos.utils.float import floatUnerr
from eos.utils.spoolSupport import SpoolOptions, SpoolType
from eos.utils.stats import RRTypes
from android_bridge.offline.remote_repair_time_math import (
    CheckedTimeCache, CheckedDistance2RpsGetter, CheckedDistance2RepAmountGetter,
    YRepAmountMixin)
from android_bridge.offline.remote_repair_resource import RepairReservation
from android_bridge.projected_drone_admission import AdmissionRejected
from test_remote_repair_selected_time import Module, Drone, fit, request, CONTEXT
from android_bridge.offline.remote_repair_samples import sample_remote_repair


def amount_request(time=2):
    r = request(time)
    r['y'] = dict(quantity='repair_amount', unit='HP')
    return r


class AmountDistanceTests(unittest.TestCase):
    def sample(self, r=None, source=None, **kwargs):
        source = source or fit(Module(), (Drone(),))
        return sample_remote_repair(amount_request() if r is None else r,
            resolve_fit=lambda k: (source, 1), current_context=lambda: CONTEXT,
            clock=lambda: 0, **kwargs)

    def test_original_mixin_and_guarded_application_resolution(self):
        self.assertIs(CheckedDistance2RepAmountGetter._calculatePoint,
                      CheckedDistance2RpsGetter._calculatePoint)
        for name in ('_getRepsPerKey', '_prepareTimeCache', '_getTimeCacheData', '_getTimeCacheDataPoint'):
            self.assertIs(getattr(CheckedDistance2RepAmountGetter, name), getattr(YRepAmountMixin, name))
        with patch.object(CheckedTimeCache, 'prepareRpsData', side_effect=AssertionError('rate route')):
            out = self.sample()
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['series'][0]['y'], [33])  # 24 armor + 3 start-offset shield events (coincident hull overwritten).

    def test_required_time_and_exact_units_reject_before_preparation(self):
        cases = [amount_request(t) for t in (None, True, False, math.inf, -math.inf, math.nan, '2')]
        missing = amount_request(); del missing['time']; cases.append(missing)
        for y in (dict(quantity='repair_amount', unit='HP/s'), dict(quantity='repair_rate', unit='HP'),
                  dict(quantity='amount', unit='HP')):
            r = amount_request(); r['y'] = y; cases.append(r)
        r = amount_request(); r['distance'] = 0; cases.append(r)
        for ordinate in ('repair_rate', 'repair_amount'):
            r = amount_request(); r['x'] = dict(quantity='time', unit='s', range=[0, 2])
            r['y'] = dict(quantity=ordinate, unit='HP/s' if ordinate == 'repair_rate' else 'HP'); cases.append(r)
        for r in cases:
            with self.subTest(request=r):
                out = self.sample(r, prepare_fit=lambda f: self.fail('prepared invalid request'),
                                  time_reserve=lambda *a: self.fail('reserved invalid request'))
                self.assertFalse(out['ok']); self.assertEqual(out['error']['code'], 'invalid_request')
                self.assertEqual(set(out), {'version','request_id','ok','error'})

    def test_v1_unchanged_and_v2_null_rate(self):
        for version in (1, 2):
            r = request(None); r['version'] = version
            if version == 1: del r['distance']
            out = self.sample(r)
            self.assertTrue(out['ok'], out); self.assertEqual(out['series'][0]['y'], [104])
            r['y'] = dict(quantity='repair_amount', unit='HP')
            self.assertEqual(self.sample(r)['error']['code'], 'invalid_request')
        r = amount_request(2); r['version'] = 1; del r['distance']
        self.assertEqual(self.sample(r)['error']['code'], 'invalid_request')

    def test_zero_signed_zero_and_independent_clamps_echo(self):
        for entered, effective, expected in ((-4,0,3),(0,0,3),(-0.0,-0.0,3),(2,2,33),(3000,2500,37503)):
            out = self.sample(amount_request(entered))
            self.assertTrue(out['ok'], out)
            self.assertEqual(out['time'], entered)
            self.assertEqual(math.copysign(1, out['time']), math.copysign(1, entered))
            self.assertEqual(out['effective'], dict(x_range=[0,0],time=effective,distance=None))
            self.assertEqual(out['y'], dict(quantity='repair_amount',unit='HP'))
            self.assertEqual(out['series'][0]['y'], [expected])
            self.assertEqual(out['series'][0]['source_rates'], dict(shield=3,armor=99,hull=2))

    def test_capacitor_excluded_but_generation_charged(self):
        mod = Module(); mod.getRepAmountParameters = lambda **kw: {0: RRTypes(0,0,0,50)}
        counts = Counter()
        out = self.sample(source=fit(mod), time_reserve=lambda k,n: counts.update({k:n}))
        self.assertTrue(out['ok'], out); self.assertEqual(out['series'][0]['y'], [0])
        self.assertEqual(counts['cycle'], 4)

    def test_amount_only_cache_retains_internal_rate_and_clears(self):
        snapshots = []; original = CheckedTimeCache.clearAll
        def clear(cache):
            snapshots.append(set(cache._data[1][False]))
            original(cache)
            self.assertFalse(cache._data or cache._schedules or cache._active)
        with patch.object(CheckedTimeCache, 'clearAll', clear): out = self.sample()
        self.assertTrue(out['ok'], out)
        self.assertEqual(snapshots, [{'maxTime','internalRps','finalRepAmount'}])

    def test_monotonic_default_ledger_across_fresh_fit_caches(self):
        r = amount_request(); r['fits'] = [dict(fit_id=str(i),revision=1) for i in range(2)]
        ledger = RepairReservation(); used = []
        def reserve(k,n): ledger(k,n); used.append(ledger.used)
        out = self.sample(r, time_reserve=reserve)
        self.assertTrue(out['ok'], out); self.assertEqual(len(out['series']), 2)
        self.assertEqual(used, sorted(used)); self.assertGreater(used[-1], used[0])
        self.assertEqual(ledger.allowance, 100663296)

    def test_all_allocation_failures_complete_and_next_request_recovers(self):
        counts = Counter(); self.assertTrue(self.sample(time_reserve=lambda k,n: counts.update({k:n}))['ok'])
        cleared = []; original = CheckedTimeCache.clearAll
        def clear(cache):
            original(cache); cleared.append(not (cache._data or cache._schedules or cache._active))
        for target in counts:
            def reserve(k,n):
                if k == target: raise AdmissionRejected('injected ' + target)
            with patch.object(CheckedTimeCache, 'clearAll', clear): out = self.sample(time_reserve=reserve)
            self.assertEqual(out['error']['code'], 'resource_exhausted', (target,out))
            self.assertEqual(set(out), {'version','request_id','ok','error'})
        self.assertTrue(cleared); self.assertTrue(all(cleared)); self.assertTrue(self.sample()['ok'])

    def test_cancel_conversion_lookup_adaptive_output_and_complete_error(self):
        for target in ('cycle','copy_slot','sort_slot','list_slot','output_point','output_slot'):
            flag = [False]
            def reserve(k,n):
                if k == target: flag[0] = True
            out = self.sample(time_reserve=reserve, cancelled=lambda:flag[0])
            self.assertEqual(out['error']['code'], 'cancelled', (target,out)); self.assertNotIn('series',out)

    def test_deadline_stale_and_late_fit_failures_discard_every_series(self):
        for code in ('deadline_exceeded', 'stale_context'):
            flag = [False]
            def reserve(k,n):
                if k == 'copy_slot': flag[0] = True
            out = sample_remote_repair(amount_request(), resolve_fit=lambda k:(fit(Module()),1),
                current_context=lambda:dict(CONTEXT,generation=1) if flag[0] and code == 'stale_context' else CONTEXT,
                clock=lambda:11 if flag[0] and code == 'deadline_exceeded' else 0,
                time_reserve=reserve)
            self.assertEqual(out['error']['code'], code, out); self.assertNotIn('series',out)
        r = amount_request(); r['fits'] = [dict(fit_id=k,revision=1) for k in ('a','b')]
        calls = [0]
        def reserve(k,n):
            if k == 'cycle':
                calls[0] += n
                if calls[0] > 8: raise AdmissionRejected('second fit')
        out = self.sample(r,time_reserve=reserve)
        self.assertEqual(out['error']['code'],'resource_exhausted'); self.assertNotIn('series',out)
        source = fit(Module())
        resolves = [0]
        def resolve(k):
            resolves[0] += 1
            return source, 1 if resolves[0] == 1 else 2
        out = sample_remote_repair(amount_request(),resolve_fit=resolve,current_context=lambda:CONTEXT,clock=lambda:0)
        self.assertEqual(out['error']['code'],'stale_fit'); self.assertNotIn('series',out)
        self.assertTrue(self.sample()['ok'])


class IndependentAmountSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[5] / 'cloud-source-receipts/pyfa/reconstructed-source'
        cls.getter_path = root / 'graphs/data/fitRemoteReps/getter.py'
        cls.cache_path = root / 'graphs/data/fitRemoteReps/cache.py'
        for path, digest in ((cls.getter_path,'6531618b3dc875602f1230b396bf6cf634a74aa58a27dad43bec62b21c0ff263'),
                             (cls.cache_path,'16e5b4ed5e01b1ea1adc70dcb48ef1f918aad533afd71cfbad1a51302c57de4d')):
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise AssertionError('Independent source binding changed')

    def test_original_amount_mixin_ast_is_exact(self):
        original = next(n for n in ast.parse(self.getter_path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == 'YRepAmountMixin')
        import inspect
        self.assertEqual(ast.dump(original), ast.dump(ast.parse(inspect.getsource(YRepAmountMixin)).body[0]))

    def original(self):
        node = next(n for n in ast.parse(self.cache_path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == 'TimeCache')
        class Base:
            def __init__(self): self._data = {}
        scope = dict(FitDataCache=Base,copy=copy,floatUnerr=floatUnerr,SpoolOptions=SpoolOptions,SpoolType=SpoolType,RRTypes=RRTypes)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(self.cache_path),'exec'),scope)
        return scope['TimeCache']()

    def test_fresh_amount_first_maps_and_event_boundaries_match_independent_original(self):
        for horizon in (0,0.9999999999999999,1,2,10):
            src = NS(item=fit(Module(), (Drone(),)))
            original = self.original(); checked = CheckedTimeCache(lambda:None,lambda *a:None)
            for cache in (original, checked): cache.prepareRepAmountData(src,False,horizon)
            self.assertEqual(original._data, checked._data)
            self.assertEqual(list(original.getRepAmountData(src,False)), list(checked.getRepAmountData(src,False)))
            for time in (0,0.999,0.9999999999999999,1,1.001,horizon):
                self.assertEqual(original.getRepAmountDataPoint(src,False,time), checked.getRepAmountDataPoint(src,False,time))
            for cache in (original, checked): cache.prepareRpsData(src,False,horizon)
            self.assertEqual(original._data, checked._data)
            reverse = self.original(); reverse.prepareRpsData(src,False,horizon); reverse.prepareRepAmountData(src,False,horizon)
            self.assertEqual(original._data, reverse._data)
            checked.clearAll(); self.assertFalse(checked._data or checked._schedules or checked._active)


if __name__ == '__main__': unittest.main()
