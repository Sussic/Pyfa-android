"""Scoped pre-simulation admission using original EOS grouping, never its run.

These native resource boundaries are not game rules. They apply only when the
caller enables projected-drone evaluation. No drain, event or curve is truncated.
"""
from contextlib import contextmanager
import math
from .projected_drone_admission import AdmissionRejected
from collections import Counter

HORIZON_MS = 6 * 60 * 60 * 1000
MAX_DRAINS = 4096
MAX_EVENTS = 262144
MAX_WORK = 2097152
MAX_REQUEST_WORK = 268435456
MAX_SIMULATIONS_PER_FIT = 8
MAX_IMPORT_SIMULATIONS_PER_FIT = 35


def refuse(reason):
    raise AdmissionRejected('Projected-drone capacitor evaluation budget: ' + reason)


def estimate(drains, factor_reload):
    if type(drains) not in (list, tuple) or len(drains) > MAX_DRAINS:
        refuse('too many complete drain inputs')
    normalized = []
    for row in drains:
        if type(row) not in (list, tuple) or len(row) != 6:
            refuse('unsupported drain metadata')
        duration, need, clip, disable, reload, injector = row
        if type(duration) is not int or not 0 < duration <= 2**31 - 1:
            refuse('unsupported cycle duration')
        if type(need) not in (int, float) or not math.isfinite(need):
            refuse('nonfinite drain amount')
        if type(disable) is not bool or type(injector) is not bool:
            refuse('unsupported drain flags')
        if not factor_reload and not injector:
            clip, reload = 0, 0  # Exact reset normalization, before grouping.
        if type(clip) not in (int, float) or not math.isfinite(clip) or clip < 0 or int(clip) != clip:
            refuse('unsupported clip size')
        if type(reload) not in (int, float) or not math.isfinite(reload) or reload < 0:
            refuse('unsupported reload delay')
        normalized.append((duration, need, clip, disable, reload, injector))
    groups = Counter(normalized)
    # Certify source float LCM intermediates remain exactly integral. Merely
    # bounding a product below float overflow is insufficient: rounded periods
    # can make the source float Euclidean remainder produce a fractional GCD.
    period = 1
    for (duration, need, clip, disable, reload, injector), amount in groups.items():
        if injector: continue
        effective = int(duration / amount) if not disable and clip == 0 else duration
        if effective <= 0:
            refuse('grouped capacitor cycle would have zero duration')
        product = period * effective
        if product > 2**53:
            refuse('unsupported exact capacitor period arithmetic')
        period = product // math.gcd(period, effective)
        if disable and not math.isfinite(need * amount):
            refuse('grouped drain amount would overflow')
        if clip and not math.isfinite((duration * clip + reload) / (amount * clip)):
            refuse('stagger offset would overflow')
    from eos.capSim import CapSimulator
    simulator = CapSimulator()
    simulator.init(drains)
    simulator.stagger, simulator.scale = True, False
    simulator.reload, simulator.t_max = factor_reload, HORIZON_MS
    simulator.reset()  # Reuse exact source grouping; never run or change a fit.
    if not math.isfinite(simulator.period) or simulator.period <= 0:
        refuse('unsupported capacitor period')
    events = 0
    injectors = 0
    for when, step, need, shot, clip, reload, injector in simulator.state:
        if not all(type(v) in (int, float) and math.isfinite(v) for v in (when, step, need, reload)) or when < 0 or step <= 0 or reload < 0:
            refuse('invalid effective capacitor cycle')
        # Ignore positive start delays/reloads and early depletion/repeat exits.
        # Add one for the initial or terminal pop; all pushes advance >= step.
        events += math.ceil(HORIZON_MS / step) + 1
        injectors += int(injector)
        if events > MAX_EVENTS:
            refuse('six-hour event reservation exceeded')
    # Pending-injector branches can scan a list for each chosen injector, twice
    # per event. Heap accounting includes both pop and push at source state size.
    heap = max(1, math.ceil(math.log2(len(simulator.state) + 1)))
    sort = max(1, math.ceil(math.log2(events + 1)))
    work = events * (4 + 2 * heap + sort + 4 * injectors + 2 * injectors * injectors)
    if work > MAX_WORK:
        refuse('capacitor event/list-work reservation exceeded')
    return dict(drains=len(drains), states=len(simulator.state), events=events,
                work=work, horizon_ms=HORIZON_MS)


def check(fit, fit_count=1, *, simulations_per_fit=MAX_SIMULATIONS_PER_FIT):
    # Call after LOCAL effects, before any capacitor/tank/statistics consumer.
    if type(simulations_per_fit) is not int or not MAX_SIMULATIONS_PER_FIT <= simulations_per_fit <= MAX_IMPORT_SIMULATIONS_PER_FIT:
        refuse('unsupported simulation-call reservation')
    for name in ('capacitorCapacity', 'rechargeRate'):
        value = fit.ship.getModifiedItemAttr(name)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            refuse('capacitor capacity and recharge must be positive and finite')
    drains, _, _ = fit._Fit__generateDrain()
    result = estimate(drains, fit.factorReload)
    if result['work'] * simulations_per_fit * max(1, fit_count) > MAX_REQUEST_WORK:
        refuse('complete-request capacitor reservation exceeded')
    return result


def request_factor(engine):
    return getattr(engine, '_projected_drone_cap_factor', MAX_SIMULATIONS_PER_FIT)


@contextmanager
def import_scope(engine, documents):
    """Private serialized scope; survives storage resets and always restores."""
    engine._check_thread()
    if type(documents) is not int or not 1 <= documents <= 16:
        refuse('unsupported import document count')
    missing = object()
    previous = getattr(engine, '_projected_drone_cap_factor', missing)
    current = MAX_SIMULATIONS_PER_FIT if previous is missing else previous
    engine._projected_drone_cap_factor = max(current, 2 * documents + 3)
    try:
        yield
    finally:
        if previous is missing:
            del engine._projected_drone_cap_factor
        else:
            engine._projected_drone_cap_factor = previous
