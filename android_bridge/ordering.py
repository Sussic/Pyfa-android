"""Worker-only rack ordering, retaining original desktop module objects.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source: localSwap.py, localModule/swap.py and fittingView.py at
8b04f3b271e614b3e103853b44a7851a63d79d0e. Heat uses the unchanged desktop
Thermodynamics class; EOS supplies all modified attributes and slot behavior.
"""
import math
from . import fitting


def swap(engine, fit, from_position, to_position):
    engine._check_fit(fit)
    first = fitting._position(fit, from_position, occupied=True)
    second = fitting._position(fit, to_position)
    if first.slot != second.slot:
        raise ValueError('Choose a destination in the same rack')
    if from_position == to_position:
        return
    fit.modules.free(from_position)
    fit.modules.free(to_position)
    fit.modules.replace(to_position, first)
    if fit.modules[to_position] is not first:
        raise ValueError('The module could not move to that position')
    fit.modules.replace(from_position, second)
    if fit.modules[from_position] is not second:
        raise ValueError('The modules could not exchange positions')
    # The enclosing bridge transaction rolls back every input on rejection.
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    # Desktop swap does not promote recent item use or recreate the modules.


def details(engine, fit):
    engine._check_fit(fit)
    from eos.const import FittingModuleState, FittingSlot
    from .thermodynamics import Thermodynamics
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    rows = []
    for index, mod in enumerate(fit.modules):
        heat = None
        if mod.state == FittingModuleState.OVERHEATED:
            try:
                thermo = Thermodynamics(fit)
                cycles = thermo.calcBurnCycles(mod)
                # Preserve the original display's duration-before-speed choice.
                cycle_time = (mod.getModifiedItemAttr('duration') or mod.getModifiedItemAttr('speed')) / 1000
                seconds = cycles * cycle_time
                probabilities = [{'seconds': t, 'value': thermo.calcDamageProbability(mod, t), 'unit': 'probability'}
                                 for t in (1.0, 10.0, 60.0, 600.0)]
                if cycles < 0 or not math.isfinite(seconds) or seconds < 0 or any(
                        not math.isfinite(row['value']) or not 0 <= row['value'] <= 1 for row in probabilities):
                    raise ValueError('Unavailable heat estimate')
                heat = {'cycles': {'value': cycles, 'unit': 'cycles'},
                        'seconds': {'value': seconds, 'unit': 's'}, 'probabilities': probabilities}
            except (ArithmeticError, ValueError, TypeError, IndexError):
                # A failed original estimate is visibly unavailable, never zero.
                heat = {'cycles': {'value': None, 'unit': 'cycles'},
                        'seconds': {'value': None, 'unit': 's'}, 'probabilities': []}
        rows.append({'index': index, 'id': mod.itemID, 'name': mod.item.name if mod.item else None,
                     'slot': FittingSlot(mod.slot).name, 'state': FittingModuleState(mod.state).name,
                     'charge_id': mod.chargeID, 'charge': mod.charge.name if mod.charge else None, 'heat': heat})
    return {'modules': rows}
