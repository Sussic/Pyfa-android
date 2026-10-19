"""Strict G09 EWAR distance boundary around the unchanged original getters."""
import json
import math
import time
from copy import deepcopy
from types import SimpleNamespace
from android_bridge.history import _same
from android_bridge.projected_drone_admission import AdmissionRejected
from .capacitor_samples import SamplingError, _keys, _number, _integer, _text, _context
from .ewar_resource import (EwarReservation, MAX_WIRE_CHARS, WIRE_HEADER_CHARS,
                            WIRE_POINT_CHARS, reserve_graph, live_contributions, count)
from .ewar_math import (graph_settings, Distance2NeutingStrGetter, Distance2WebbingStrGetter,
    Distance2EcmStrMaxGetter, Distance2DampStrLockRangeGetter, Distance2TdStrOptimalGetter,
    Distance2GdStrRangeGetter, Distance2TpStrGetter)

MODES = {
    'neutStr': (None, Distance2NeutingStrGetter),
    'webStr': ('%', Distance2WebbingStrGetter),
    'ecmStrMax': (None, Distance2EcmStrMaxGetter),
    'dampStrLockRange': ('%', Distance2DampStrLockRangeGetter),
    'tdStrOptimal': ('%', Distance2TdStrOptimalGetter),
    'gdStrRange': ('%', Distance2GdStrRangeGetter),
    'tpStr': ('%', Distance2TpStrGetter),
}
MAX_REQUEST_CHARS = 16384
MAX_NUMBER_CHARS = 310


def fail(code, message):
    raise SamplingError(code, message)


def identity(value, label):
    _text(value, label)
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        fail('invalid_request', label + ' must contain valid Unicode')


def parse_request(text):
    """Raw and numeric-token guards run before expensive numeric conversion."""
    if type(text) is not str or len(text) > MAX_REQUEST_CHARS:
        fail('invalid_request', 'Invalid EWAR request size')
    def numeric(token, integer):
        if len(token) > MAX_NUMBER_CHARS: fail('invalid_request', 'EWAR numeric token is too long')
        value = int(token) if integer else float(token)
        return _number(value, -math.inf, math.inf, 'numeric token')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: fail('invalid_request', 'Duplicate EWAR request field')
            result[key] = value
        return result
    def constant(token):
        fail('invalid_request', 'EWAR numeric values must be finite')
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_int=lambda t:numeric(t, True),
                          parse_float=lambda t:numeric(t, False), parse_constant=constant)
    except SamplingError:
        raise
    except (ValueError, TypeError, RecursionError):
        fail('invalid_request', 'Malformed EWAR request')


ERROR_MESSAGES = {
    'invalid_request': 'Invalid EWAR request; no partial graph was returned',
    'invalid_engine_data': 'Original EWAR calculation is undefined or overflowed; no partial graph was returned',
    'stale_context': 'The fitting graph changed; sample again',
    'stale_fit': 'A selected fit changed; sample again',
    'fit_not_found': 'A selected fit no longer exists',
    'cancelled': 'EWAR sampling was cancelled',
    'deadline_exceeded': 'The cooperative sampling budget expired',
    'resource_exhausted': 'EWAR request exceeds its reviewed resource admission; no partial graph was returned',
    'clock_error': 'The monotonic clock is invalid',
    'engine_error': 'EWAR samples unavailable; no partial graph was returned',
    'reopen_required': 'Reopen the fitting session after a durable-state mismatch',
    'engine_unavailable': 'The fitting engine is unavailable; reopen the session',
}


def error_result(request_id, code, message=None):
    # Only this bounded static catalogue crosses the wire, including when a
    # trusted callback raises SamplingError with an unexpected diagnostic.
    if type(code) is not str or code not in ERROR_MESSAGES: code = 'engine_error'
    return dict(version=1, request_id=request_id, ok=False,
                error=dict(code=code, message=ERROR_MESSAGES[code]))


def sample_ewar(request, *, resolve_fit, current_context, prep_admit=None,
                cancelled=lambda: False, clock=time.monotonic, prepare_fit=None,
                reserve=None, encode=None):
    request_id = None
    try:
        _keys(request, ('version','request_id','context','fits','x','y','resistance_percent',
                        'ignore_lock_range','ignore_drone_control_range','budget_ms'), 'request')
        _integer(request['version'], 1, 1, 'version')
        identity(request['request_id'], 'request_id'); request_id = request['request_id']
        _context(request['context']); identity(request['context']['session_id'], 'session_id')
        _keys(request['x'], ('quantity','unit','range'), 'x')
        _keys(request['y'], ('quantity','unit'), 'y')
        mode = request['y']['quantity']
        if type(mode) is not str or mode not in MODES or request['y']['unit'] != MODES[mode][0]:
            fail('invalid_request', 'Select an EWAR quantity and its original unit')
        if (request['x']['quantity'], request['x']['unit']) != ('distance','km'):
            fail('invalid_request', 'EWAR x must be distance in km')
        bounds = request['x']['range']
        if type(bounds) is not list or len(bounds) != 2: fail('invalid_request', 'Provide two ordered distance endpoints')
        low, high = bounds
        _number(low, 0, math.inf, 'lower distance'); _number(high, low, math.inf, 'upper distance')
        normalized = [low * 1000, high * 1000]
        for value in normalized: _number(value, 0, math.inf, 'normalized distance')
        requested = request['resistance_percent']
        resistance = None
        if requested is not None:
            _number(requested, -math.inf, math.inf, 'resistance_percent')
            resistance = min(max(requested / 100, 0), 1)
        for key in ('ignore_lock_range','ignore_drone_control_range'):
            if type(request[key]) is not bool: fail('invalid_request', key + ' must be boolean')
        _integer(request['budget_ms'], 1, 10000, 'budget_ms')
        rows = request['fits']
        if type(rows) is not list or not 1 <= len(rows) <= 8: fail('invalid_request', 'Select one to eight fits')
        ids = set()
        for row in rows:
            _keys(row, ('fit_id','revision'), 'fit'); identity(row['fit_id'], 'fit_id')
            _integer(row['revision'], 1, 2**63-1, 'revision')
            if row['fit_id'] in ids: fail('invalid_request', 'Select each fit once')
            ids.add(row['fit_id'])
        if not callable(prep_admit): fail('resource_exhausted', 'EWAR requires authoritative preparation admission')
        started = clock(); _number(started, -math.inf, math.inf, 'clock', 'clock_error'); previous = started
        def check():
            nonlocal previous
            if cancelled(): fail('cancelled', 'EWAR sampling was cancelled')
            tick = clock(); _number(tick, previous, math.inf, 'clock', 'clock_error'); previous = tick
            elapsed = tick - started
            if not math.isfinite(elapsed): fail('clock_error', 'The monotonic clock is invalid')
            if elapsed * 1000 >= request['budget_ms']: fail('deadline_exceeded', 'The cooperative sampling budget expired')
            if not _same(current_context(), request['context']): fail('stale_context', 'The fitting graph changed; sample again')
        def resolve(row):
            try: fit, revision = resolve_fit(row['fit_id'])
            except KeyError: fail('fit_not_found', 'A selected fit no longer exists')
            if type(revision) is not int or revision != row['revision']: fail('stale_fit', 'A selected fit changed; sample again')
            return fit
        supplied = EwarReservation() if reserve is None else reserve
        charged = 0
        def reserve(kind, amount):
            nonlocal charged
            from .ewar_resource import add, PRICES
            check()
            if kind not in PRICES: raise AdmissionRejected('Unknown EWAR resource price')
            next_charged = add(charged, amount)
            supplied(kind, amount)
            charged = next_charged
        # The fixed schema/raw-token bound also covers parse/request/response
        # coexistence and bounded <=8-handle bookkeeping before proportional work.
        reserve('serialization_unit', MAX_WIRE_CHARS)
        check()
        handles = [resolve(row) for row in rows]
        estimates = prep_admit(rows, handles, mode, reserve, check)
        point_bound = 1 if normalized[0] == normalized[1] else 201
        reserve_graph(reserve, mode, estimates, point_bound)
        check()
        if len(estimates) != len(rows): raise AdmissionRejected('Missing EWAR contributor reservation')
        series = []; total = 0
        base = MODES[mode][1]
        with graph_settings(request['ignore_lock_range'], request['ignore_drone_control_range']):
            for row, fit, estimate in zip(rows, handles, estimates):
                check()
                if resolve(row) is not fit: fail('stale_fit', 'A selected fit was replaced; sample again')
                if prepare_fit is not None: prepare_fit(fit)
                check()
                class CheckedGetter(base):
                    points = 0
                    def _getCommonData(self, miscParams, src, tgt):
                        actual, duration_calls = live_contributions(src.item, mode, check)
                        if actual > estimate[0] or duration_calls > estimate[1]:
                            raise AdmissionRejected('EWAR contributors changed before materialization')
                        check()
                        value = super()._getCommonData(miscParams, src, tgt)
                        if type(value) is not dict or len(value) != 1:
                            fail('invalid_engine_data', 'Unexpected original EWAR common data')
                        if len(next(iter(value.values()))) > estimate[0]:
                            fail('invalid_engine_data', 'Original EWAR contributor ceiling exceeded')
                        check()
                        return value
                    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
                        check(); _number(x, 0, math.inf, 'sample distance', 'invalid_engine_data')
                        self.points += 1
                        if self.points > point_bound: fail('invalid_engine_data', 'Original EWAR sample ceiling exceeded')
                        value = super()._calculatePoint(x, miscParams, src, tgt, commonData)
                        _number(value, -math.inf, math.inf, 'EWAR sample', 'invalid_engine_data')
                        check()
                        return value
                getter = CheckedGetter(None)
                try:
                    xs, ys = getter.getRange(normalized, {'resist':resistance}, SimpleNamespace(item=fit), None)
                except AdmissionRejected:
                    raise
                except (ArithmeticError, ValueError):
                    fail('invalid_engine_data', 'Original EWAR calculation is undefined or overflowed')
                if not 1 <= len(xs) == len(ys) == getter.points <= point_bound:
                    fail('invalid_engine_data', 'Invalid original EWAR samples')
                total += len(xs)
                if total > 1608: fail('invalid_engine_data', 'Original EWAR total sample ceiling exceeded')
                series.append(dict(fit_id=row['fit_id'], revision=row['revision'], x=[x / 1000 for x in xs], y=ys))
                check()
        check()
        for row, fit in zip(rows, handles):
            if resolve(row) is not fit: fail('stale_fit', 'A selected fit was replaced; sample again')
        result = dict(version=1, request_id=request_id, ok=True, context=deepcopy(request['context']),
            x=deepcopy(request['x']), y=deepcopy(request['y']), resistance_percent=requested,
            ignore_lock_range=request['ignore_lock_range'], ignore_drone_control_range=request['ignore_drone_control_range'],
            effective=dict(distance_range_m=normalized, resistance_fraction=resistance), total_points=total,
            series=series, error=None)
        if encode is None: return result
        check()
        wire = encode(result)
        if type(wire) is not str or len(wire) > WIRE_HEADER_CHARS + WIRE_POINT_CHARS * total:
            fail('invalid_engine_data', 'Encoded EWAR response exceeds its reserved bound')
        check()
        for row, fit in zip(rows, handles):
            if resolve(row) is not fit: fail('stale_fit', 'A selected fit was replaced; sample again')
        return wire
    except SamplingError as error:
        return error_result(request_id, error.code)
    except AdmissionRejected:
        return error_result(request_id, 'resource_exhausted', 'EWAR request exceeds its reviewed resource admission; no partial graph was returned')
    except Exception:
        return error_result(request_id, 'engine_error', 'EWAR samples unavailable; no partial graph was returned')
