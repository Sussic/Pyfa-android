"""G03's isolated, versioned read-only capacitor range-sampling boundary.

The trusted serialized engine wrapper supplies resolve_fit(id) -> (handle, rev)
and current_context() -> {session_id, dataset_sha256, generation}. Generation
MUST advance on any relevant settings, skill/profile, projection or fit-graph
change, including changes that invalidate a selected fit indirectly. Session IDs
must not be reused after reopen. Resolver callbacks are read-only. Request data
alone cannot establish trusted revisions or provenance.

Cancellation/deadlines are COOPERATIVE. EOS attribute calculation and
getCapSimData have no cancellation callback. The latter always computes up to
3600 simulated seconds; both may populate derived caches.
No deadline, event limit or point limit here bounds that call's internal time or
allocation. Use a separately bounded process for hard resource enforcement.
The caller must use this on the EOS creating thread, off the UI thread.

Successful output is complete; all failures omit series, never partial curves.
No persistence, history, input edits, bridge integration or plotting is performed.
Range/event semantics follow the reference Time2CapAmountGetter.getRange, not
getPoint (which differs at the exact final event). Adapted from Pyfa's GPL graph
getter; original Copyright (C) 2010 Diego Duclos and Pyfa contributors.
"""
from android_bridge.projected_drone_admission import AdmissionRejected

import math
import re
import time

from .capacitor_math import calculateCapAmount, calculateCapRegen

VERSION = 1
MAX_FITS = 8
MAX_RESOLUTION = 1024
MAX_POINTS = 16384
MAX_EVENTS = 32768
MAX_BUDGET_MS = 10000
MAX_TIME_SECONDS = 3600
MAX_REVISION = 2**63 - 1


class SamplingError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def _fail(code, message):
    raise SamplingError(code, message)


def _keys(value, fields, name):
    if type(value) is not dict or set(value) != set(fields):
        _fail('invalid_request', name + ' has missing or unsupported fields')


def _number(value, low, high, name, code='invalid_request'):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and low <= value <= high
    except OverflowError:
        valid = False
    if not valid:
        _fail(code, name + ' must be finite and within its documented range')
    return value


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        _fail('invalid_request', name + ' must be an integer within its documented range')


def _text(value, name):
    if type(value) is not str or not value or len(value) > 128:
        _fail('invalid_request', name + ' must contain 1–128 characters')


def _context(value):
    _keys(value, ('session_id', 'dataset_sha256', 'generation'), 'context')
    _text(value['session_id'], 'session_id')
    if type(value['dataset_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', value['dataset_sha256']):
        _fail('invalid_request', 'dataset_sha256 must be a lowercase SHA-256 digest')
    _integer(value['generation'], 0, MAX_REVISION, 'generation')


def _validate(request):
    _keys(request, ('version', 'request_id', 'context', 'fits', 'x', 'y',
                    'starting_cap_percent', 'use_simulation', 'resolution', 'budget_ms'), 'request')
    if type(request['version']) is not int or request['version'] != VERSION:
        _fail('unsupported_version', 'Only capacitor sampling version 1 is supported')
    _text(request['request_id'], 'request_id')
    _context(request['context'])
    if type(request['fits']) is not list or not 1 <= len(request['fits']) <= MAX_FITS:
        _fail('invalid_request', 'Select 1–8 fits')
    ids = set()
    for row in request['fits']:
        _keys(row, ('fit_id', 'revision'), 'fit')
        _text(row['fit_id'], 'fit_id')
        _integer(row['revision'], 0, MAX_REVISION, 'revision')
        if row['fit_id'] in ids:
            _fail('invalid_request', 'Fit IDs must be unique')
        ids.add(row['fit_id'])
    _keys(request['x'], ('quantity', 'unit', 'range'), 'x')
    _keys(request['y'], ('quantity', 'unit'), 'y')
    x, y = request['x'], request['y']
    if (x['quantity'], x['unit']) not in (('time', 's'), ('cap_amount', 'GJ'), ('cap_amount', '%')):
        _fail('invalid_request', 'Unsupported x quantity/unit')
    if (y['quantity'], y['unit']) not in (('cap_amount', 'GJ'), ('cap_regen', 'GJ/s')):
        _fail('invalid_request', 'Unsupported y quantity/unit')
    if type(x['range']) is not list or len(x['range']) != 2:
        _fail('invalid_request', 'x.range must have two ordered endpoints')
    maximum = MAX_TIME_SECONDS if x['quantity'] == 'time' else 100 if x['unit'] == '%' else float('inf')
    low, high = x['range']
    _number(low, 0, maximum, 'x.range lower endpoint')
    _number(high, low, maximum, 'x.range upper endpoint')
    _number(request['starting_cap_percent'], 0, 100, 'starting_cap_percent')
    if type(request['use_simulation']) is not bool:
        _fail('invalid_request', 'use_simulation must be boolean')
    _integer(request['resolution'], 1, MAX_RESOLUTION, 'resolution')
    _integer(request['budget_ms'], 1, MAX_BUDGET_MS, 'budget_ms')


class _Guard:
    def __init__(self, request, resolve_fit, current_context, cancelled, clock):
        self.request = request
        self.resolve_fit = resolve_fit
        self.current_context = current_context
        self.cancelled = cancelled
        self.clock = clock
        self.started = clock()
        _number(self.started, -float('inf'), float('inf'), 'monotonic clock', 'clock_error')
        self.previous_tick = self.started
        self.handles = []
        self.points = 0

    def check(self, identity=False):
        if self.cancelled():
            _fail('cancelled', 'Capacitor sampling was cancelled')
        tick = self.clock()
        _number(tick, self.previous_tick, float('inf'), 'monotonic clock', 'clock_error')
        self.previous_tick = tick
        elapsed = tick - self.started
        if not math.isfinite(elapsed):
            _fail('clock_error', 'The monotonic clock is invalid')
        if elapsed * 1000 >= self.request['budget_ms']:
            _fail('deadline_exceeded', 'The cooperative work budget expired')
        if identity:
            if self.current_context() != self.request['context']:
                _fail('stale_context', 'Session, dataset or graph generation changed')
            for row, expected in self.handles:
                current, revision = self.resolve(row)
                if current is not expected:
                    _fail('stale_fit', 'A selected fit handle changed')

    def resolve(self, row):
        try:
            value = self.resolve_fit(row['fit_id'])
        except KeyError:
            _fail('fit_not_found', 'A selected fit is no longer available')
        if type(value) not in (tuple, list) or len(value) != 2:
            _fail('resolver_error', 'Fit resolver must return a handle and revision')
        fit, revision = value
        if type(revision) is not int or revision != row['revision']:
            _fail('stale_fit', 'A selected fit revision changed')
        return fit, revision

    def append(self, xs, ys, x, y):
        self.check()
        if self.points >= MAX_POINTS:
            _fail('sample_budget_exceeded', 'Complete curves exceed the total point budget')
        _number(x, 0, float('inf'), 'sample x', 'invalid_engine_data')
        # Preserve reference roundoff (e.g. a tiny negative regen value at a
        # floating-point 100% endpoint), rather than silently clipping physics.
        _number(y, -float('inf'), float('inf'), 'sample y', 'invalid_engine_data')
        xs.append(x)
        ys.append(y)
        self.points += 1


def _smooth(request, capacity, recharge, guard):
    low, high = request['x']['range']
    is_percent = request['x']['unit'] == '%'
    if is_percent:
        # Match reference graph normalization before interpolating the range.
        low, high = low / 100 * capacity, high / 100 * capacity
    step = (high - low) / request['resolution']
    xs, ys = [], []
    for index in range(1 if step == 0 else request['resolution'] + 1):
        x = low + step * index
        amount = (calculateCapAmount(capacity, recharge, request['starting_cap_percent'] / 100 * capacity, x)
                  if request['x']['quantity'] == 'time' else x)
        y = amount if request['y']['quantity'] == 'cap_amount' else calculateCapRegen(capacity, recharge, amount)
        guard.append(xs, ys, x * 100 / capacity if is_percent else x, y)
    return xs, ys


def _simulation(request, capacity, recharge, raw, guard):
    # EOS owns event generation and clipping depleted capacity to zero. Preserve
    # the reference range getter's terminal event, start-gap and duplicate-time
    # semantics. Never truncate a curve merely to satisfy the output budget.
    if type(raw) not in (list, tuple) or len(raw) > MAX_EVENTS:
        _fail('event_budget_exceeded', 'EOS event count exceeds the inspection budget')
    events = {}
    previous_time = -1
    for entry in raw:
        guard.check()
        if type(entry) not in (list, tuple) or len(entry) != 2:
            _fail('invalid_engine_data', 'Invalid capacitor simulation event')
        when, amount = entry
        _number(when, 0, MAX_TIME_SECONDS, 'event time', 'invalid_engine_data')
        _number(amount, 0, capacity, 'event capacity', 'invalid_engine_data')
        if when < previous_time:
            _fail('invalid_engine_data', 'Capacitor simulation events are unordered')
        previous_time = when
        events[when] = amount
    if not events:
        xs, ys = _smooth(request, capacity, recharge, guard)
        return xs, ys, 'recharge_only', None
    low, requested_high = request['x']['range']
    last_event = raw[-1][0]
    high = min(requested_high, last_event)
    if low > last_event:
        return [], [], 'range_exhausted', last_event
    max_spacing = (high - low) / request['resolution']
    if high > low and max_spacing == 0:
        _fail('invalid_request', 'Time range is too narrow for the selected resolution')
    prior = [when for when in events if when < low]
    previous_time = low
    previous_amount = (calculateCapAmount(capacity, recharge, events[prior[-1]], low - prior[-1]) if prior else
                       calculateCapAmount(capacity, recharge, request['starting_cap_percent'] / 100 * capacity, low))
    xs, ys = [], []
    guard.append(xs, ys, low, previous_amount)

    def regen_interval(start_time, start_amount, end_time):
        intervals = math.ceil((end_time - start_time) / max_spacing)
        if intervals > MAX_POINTS - guard.points:
            _fail('sample_budget_exceeded', 'Complete curves exceed the total point budget')
        length = (end_time - start_time) / intervals
        for index in range(1, intervals + 1):
            when = start_time + length * index
            amount = calculateCapAmount(capacity, recharge, start_amount, when - start_time)
            guard.append(xs, ys, when, amount)

    for when, amount in events.items():
        guard.check()
        if low <= when <= high:
            if when > previous_time:
                regen_interval(previous_time, previous_amount, when)
            guard.append(xs, ys, when, amount)
            previous_time, previous_amount = when, amount
    if high > previous_time:
        regen_interval(previous_time, previous_amount, high)
    return xs, ys, 'simulation', last_event


def sample_capacitor(engine, request, *, resolve_fit, current_context, cancelled=lambda: False, _clock=time.monotonic, prepare_fit=None):
    """Return a JSON-safe complete result or {ok: False, error: {code, message}}.

Required version-1 fields: request_id; context; fits [{fit_id, revision}];
    x {quantity: time|cap_amount, unit: s|GJ|%, range: [low, high]};
    y {quantity: cap_amount|cap_regen, unit: GJ|GJ/s};
    starting_cap_percent (0..100); use_simulation (bool);
    resolution (1..1024 intervals); budget_ms (1..10000 cooperative wall time).
Time range: 0..3600 s. Capacity: 0..100% or 0..each selected fit's capacity GJ.
Simulation applies only to time/amount, matching the desktop checkbox. Other
axis combinations return recharge-only curves, even when the toggle is true.
There are at most 8 fits, 32768 inspected EOS events per fit, and 16384 returned
points across all fits. Duplicate event x values must be rendered in order.
"""
    request_id = request.get('request_id') if type(request) is dict else None
    if type(request_id) is not str or len(request_id) > 128:
        request_id = None
    try:
        _validate(request)
        # Snapshot validated wire data before invoking any trusted callbacks.
        import copy
        request = copy.deepcopy(request)
        engine._check_thread()
        guard = _Guard(request, resolve_fit, current_context, cancelled, _clock)
        guard.check(identity=True)
        for row in request['fits']:
            fit, revision = guard.resolve(row)
            engine._check_fit(fit)
            if any(fit is old for _, old in guard.handles):
                _fail('invalid_request', 'Distinct fit IDs cannot alias one EOS handle')
            guard.handles.append((row, fit))
        # Validate every capacity/range before running any expensive simulation.
        prepared = []
        for row, fit in guard.handles:
            guard.check(identity=True)
            if prepare_fit is not None:
                prepare_fit(fit)
            elif not fit.calculated:
                fit.calculateModifiedAttributes()
            guard.check(identity=True)
            capacity = fit.ship.getModifiedItemAttr('capacitorCapacity')
            recharge_ms = fit.ship.getModifiedItemAttr('rechargeRate')
            _number(capacity, 0, float('inf'), 'capacitorCapacity', 'invalid_engine_data')
            _number(recharge_ms, 0, float('inf'), 'rechargeRate', 'invalid_engine_data')
            if capacity == 0 or recharge_ms == 0:
                _fail('invalid_engine_data', 'Capacitor capacity and recharge time must be positive')
            if request['x']['unit'] == 'GJ' and request['x']['range'][1] > capacity:
                _fail('invalid_request', 'GJ range exceeds a selected fit capacity')
            prepared.append((row, fit, capacity, recharge_ms / 1000))
        series = []
        applied = (request['use_simulation'] and request['x']['quantity'] == 'time'
                   and request['y']['quantity'] == 'cap_amount')
        for row, fit, capacity, recharge in prepared:
            guard.check(identity=True)
            if applied:
                if prepare_fit is not None:
                    prepare_fit(fit)
                    guard.check(identity=True)
                raw = fit.getCapSimData(startingCap=request['starting_cap_percent'] / 100 * capacity)
                guard.check(identity=True)
                xs, ys, mode, last_event = _simulation(request, capacity, recharge, raw, guard)
            else:
                xs, ys = _smooth(request, capacity, recharge, guard)
                mode, last_event = 'recharge_only', None
            series.append(dict(fit_id=row['fit_id'], revision=row['revision'], capacity_gj=capacity,
                               recharge_time_s=recharge, mode=mode, simulation_applied=mode in ('simulation', 'range_exhausted'),
                               simulation_end_s=last_event, x=xs, y=ys))
        guard.check(identity=True)
        return dict(version=VERSION, request_id=request_id, ok=True, context=request['context'],
                    x=request['x'], y=request['y'], starting_cap_percent=request['starting_cap_percent'],
                    use_simulation=request['use_simulation'], resolution=request['resolution'],
                    total_points=guard.points, series=series)
    except SamplingError as error:
        code, message = error.code, error.message
    except AdmissionRejected as error:
        code, message = 'resource_exhausted', str(error)
    except MemoryError:
        code, message = 'resource_exhausted', 'Capacitor sampling exhausted process memory'
    except Exception:
        # Do not expose private fit content or exception representations to UI.
        code, message = 'engine_error', 'The engine or trusted wrapper could not complete capacitor sampling'
    return dict(version=VERSION, request_id=request_id, ok=False, error=dict(code=code, message=message))
