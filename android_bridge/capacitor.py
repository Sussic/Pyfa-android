"""C01.2 capacitor details from EOS and the pinned desktop presentation.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Presentation expressions follow gui/builtinStatsViews/capacitorViewFull.py at
8b04f3b271e614b3e103853b44a7851a63d79d0e. EOS owns the simulation.
"""
from .number_format import formatAmount
from .resources import _number


def details(engine, fit):
    engine._check_fit(fit)
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    capacity = fit.ship.getModifiedItemAttr('capacitorCapacity')
    # Read simulation-backed getters before capDelta (which reads cached values).
    recharge, used = fit.capRecharge, fit.capUsed
    resistance = fit.ship.getModifiedItemAttr('energyWarfareResistance', 1)
    delta = fit.capDelta
    effective = resistance is not None and 0 < round(resistance, 4) < 1
    rounded_delta = None if recharge is None or used is None else round(recharge - used, 3)
    rows = (
        ('capacity', capacity, 'GJ', 9, False),
        ('effective_capacity', capacity / resistance if effective and capacity is not None and capacity > 0 else None, 'GJ', 9, False),
        ('recharge', recharge, 'GJ/s', 3, False),
        ('use', used, 'GJ/s', 3, False),
        ('delta', delta, 'GJ/s', 0, True),
        ('effective_excess', rounded_delta / resistance if effective and rounded_delta is not None and rounded_delta > 0 else None, 'GJ/s', 3, True),
        ('neutralizer_resistance', None if resistance is None else (1 - resistance) * 100, '%', 0, False),
    )
    values = {name: dict(value=value, value_type=_number(value), unit=unit,
        display=None if value is None else formatAmount(value, 3, 0, highest, forceSign=signed),
        detail=None if value is None else '%.1f' % value) for name, value, unit, highest, signed in rows}
    state, stable = fit.capState, fit.capStable
    if type(stable) is not bool:
        raise ValueError('Capacitor stability must be a boolean')
    if isinstance(state, tuple):
        if not stable or len(state) != 2 or any(_number(v) == 'unavailable' for v in state) or not 0 <= state[0] <= state[1] <= 100:
            raise ValueError('Invalid stable capacitor range')
        stability = dict(kind='stable_range', unit='%', values=list(state),
            value_types=[_number(v) for v in state], display=f'{state[0]}%-{state[1]}%')
    else:
        kind = _number(state)
        if state is not None and (state < 0 or stable and state > 100):
            raise ValueError('Invalid capacitor state')
        display = None if state is None else ('%.1f%%' % state if stable else
            '%dm%ds' % divmod(state, 60) if state > 60 else '%ds' % state)
        stability = dict(kind='unavailable' if state is None else 'stable' if stable else 'depletion',
            unit='%' if stable else 's', values=[state], value_types=[kind], display=display)
    return dict(capacitor=values, stability=stability)
