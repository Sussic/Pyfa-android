"""G04 read-only complete original shield graph, with cooperative request checks.

Original arithmetic and normalization live in shield_regeneration_math. No cap
simulation or event generation is used by this graph. Source preparation remains
an inherited, non-interruptible EOS call; the budget is cooperative, not a hard
memory/CPU guarantee. Failures never publish partial comparison curves.
"""
import math
import time
from copy import deepcopy
from types import SimpleNamespace as NS
from android_bridge.history import _same
from android_bridge.projected_drone_admission import AdmissionRejected
from .capacitor_samples import SamplingError, _keys, _number, _integer, _text, _context
from .shield_regeneration_math import FitShieldRegenGraph, ShieldAmountColumn, ShieldTimeColumn


def sample_shield_regeneration(request, *, resolve_fit, current_context,
                               cancelled=lambda: False, clock=time.monotonic,
                               prepare_fit=None):
    request_id = None
    def fail(code, message):
        raise SamplingError(code, message)
    try:
        _keys(request, ('version', 'request_id', 'context', 'fits', 'x', 'y',
                        'effective', 'starting_shield_percent', 'budget_ms'), 'request')
        _integer(request['version'], 1, 1, 'version')
        _text(request['request_id'], 'request_id'); request_id = request['request_id']
        _context(request['context'])
        _keys(request['x'], ('quantity', 'unit', 'input_unit', 'range'), 'x')
        _keys(request['y'], ('quantity', 'unit'), 'y')
        if type(request['effective']) is not bool:
            fail('invalid_request', 'effective must be boolean')
        hp = 'EHP' if request['effective'] else 'HP'
        x, y = request['x'], request['y']
        if x['quantity'] == 'time' and x['unit'] == x['input_unit'] == 's':
            x_handle = 'time'
        elif x['quantity'] == 'shield_amount' and x['unit'] in (hp, '%') and x['input_unit'] == '%':
            x_handle = 'shieldAmount'
        else:
            fail('invalid_request', 'Unsupported shield graph X axis or input unit')
        if y == {'quantity': 'shield_amount', 'unit': hp}:
            y_handle = 'shieldAmount'
        elif y == {'quantity': 'shield_regen', 'unit': hp + '/s'}:
            y_handle = 'shieldRegen'
        else:
            fail('invalid_request', 'Unsupported shield graph Y axis or effectivity')
        bounds = x['range']
        if type(bounds) is not list or len(bounds) != 2:
            fail('invalid_request', 'Provide two finite range endpoints')
        for value in bounds: _number(value, -math.inf, math.inf, 'range endpoint')
        start = request['starting_shield_percent']
        if start is not None: _number(start, -math.inf, math.inf, 'starting shield percentage')
        if x_handle != 'time' and start is not None:
            fail('invalid_request', 'Starting shield applies only to the time axis')
        _integer(request['budget_ms'], 1, 10000, 'budget_ms')
        rows = request['fits']
        if type(rows) is not list or not 1 <= len(rows) <= 8:
            fail('invalid_request', 'Select one to eight fits')
        ids = set()
        for row in rows:
            _keys(row, ('fit_id', 'revision'), 'fit'); _text(row['fit_id'], 'fit_id')
            _integer(row['revision'], 1, 2**63 - 1, 'revision')
            if row['fit_id'] in ids: fail('invalid_request', 'Select each fit once')
            ids.add(row['fit_id'])
        started = clock(); _number(started, -math.inf, math.inf, 'clock', 'clock_error')
        previous = started
        def check():
            nonlocal previous
            if cancelled(): fail('cancelled', 'Shield sampling was cancelled')
            tick = clock(); _number(tick, previous, math.inf, 'clock', 'clock_error'); previous = tick
            if (tick - started) * 1000 >= request['budget_ms']:
                fail('deadline_exceeded', 'The cooperative shield sampling budget expired')
            if not _same(current_context(), request['context']):
                fail('stale_context', 'The fitting graph changed; sample again')
        def resolve(row):
            try: fit, revision = resolve_fit(row['fit_id'])
            except KeyError: fail('fit_not_found', 'A selected fit no longer exists')
            if type(revision) is not int or revision != row['revision']:
                fail('stale_fit', 'A selected fit changed; sample again')
            return fit
        class CheckedGraph(FitShieldRegenGraph):
            count = 0
            def _getPlotPoints(self, xRange, miscParams, xSpec, ySpec, src, tgt):
                base = self._getters[(xSpec.handle, ySpec.handle)]
                graph = self
                class CheckedGetter(base):
                    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
                        check(); graph.count += 1
                        if graph.count > 201:
                            fail('invalid_engine_data', 'Original shield sample ceiling exceeded')
                        value = super()._calculatePoint(x, miscParams, src, tgt, commonData)
                        check()
                        return value
                return CheckedGetter(self).getRange(xRange, miscParams, src, tgt)
        check(); series = []; handles = []; total = 0
        for row in rows:
            check(); fit = resolve(row); handles.append((row, fit))
            if prepare_fit is not None: prepare_fit(fit)
            check()
            capacity, capacity_unit = ShieldAmountColumn()._getValue(fit)
            recharge, recharge_unit = ShieldTimeColumn()._getValue(fit)
            _number(capacity, -math.inf, math.inf, 'source shield capacity', 'invalid_engine_data')
            _number(recharge, -math.inf, math.inf, 'source shield recharge', 'invalid_engine_data')
            if (capacity_unit, recharge_unit) != ('HP', 's'):
                fail('invalid_engine_data', 'Unexpected original shield source units')
            pattern = {}
            for name in ('em', 'thermal', 'kinetic', 'explosive'):
                value = getattr(fit.damagePattern, name + 'Amount')
                _number(value, -math.inf, math.inf, 'source damage contribution', 'invalid_engine_data')
                pattern[name] = value
            graph = CheckedGraph()
            main = NS(handle=x_handle, unit=x['input_unit'], value=tuple(bounds))
            misc = [NS(handle='shieldAmountT0', unit='%', value=start)] if x_handle == 'time' else []
            try:
                xs, ys = graph._calcPlotPoints(main, misc, NS(handle=x_handle, unit=x['unit']),
                                              NS(handle=y_handle, unit=y['unit']), NS(item=fit), None)
            except AdmissionRejected:
                raise
            except (ArithmeticError, ValueError):
                fail('invalid_engine_data', 'Original shield calculation is undefined or overflowed')
            fallback = capacity == 0 and x['unit'] == '%' and y_handle == 'shieldAmount'
            if graph.count not in (1, 201) or len(xs) != len(ys) or len(xs) != (2 if fallback else graph.count):
                fail('invalid_engine_data', 'Invalid original shield sample shape')
            for value in xs + ys:
                _number(value, -math.inf, math.inf, 'shield sample', 'invalid_engine_data')
            check(); total += len(xs)
            series.append(dict(fit_id=row['fit_id'], revision=row['revision'],
                source=dict(shield_capacity_hp=capacity, shield_recharge_seconds=recharge, damage_pattern=pattern),
                x=list(xs), y=list(ys)))
        check()
        for row, fit in handles:
            if resolve(row) is not fit:
                fail('stale_fit', 'A selected fit was replaced; sample again')
        echoed = {key: deepcopy(request[key]) for key in
                  ('context', 'x', 'y', 'effective', 'starting_shield_percent')}
        return dict(version=1, request_id=request_id, ok=True, error=None,
                    total_points=total, series=series, **echoed)
    except SamplingError as error:
        return dict(version=1, request_id=request_id, ok=False,
                    error=dict(code=error.code, message=str(error)))
    except AdmissionRejected as error:
        return dict(version=1, request_id=request_id, ok=False,
                    error=dict(code='resource_exhausted', message=str(error)))
    except Exception:
        return dict(version=1, request_id=request_id, ok=False,
                    error=dict(code='engine_error', message='Shield samples unavailable; no partial graph was returned'))
