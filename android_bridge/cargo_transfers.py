"""Cargo/fitting transfers adapted from the pinned original GUI commands.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source 8b04f3b271e614b3e103853b44a7851a63d79d0e:
gui/fitCommands/gui/localModuleCargo and calc/module/localReplace.
EOS supplies quantities, states and legality. Rejected edits remain atomic.
"""
from copy import deepcopy
from . import cargo, fitting


def _position(fit, position):
    if type(position) is not int or not 0 <= position < len(fit.modules):
        raise ValueError('Choose a fitting position')
    return fit.modules[position]


def _stack(fit, identity):
    return next((stack for stack in fit.cargo if stack.itemID == identity), None)


def _add(fit, item, amount):
    # Transfers use CalcAddCargo, not the market's structure/category restriction.
    from eos.saveddata.cargo import Cargo
    if type(amount) is not int or not 0 < amount <= cargo.MAX_QUANTITY:
        raise ValueError('Cargo transfer quantity must be positive')
    stack = _stack(fit, item.ID)
    if stack is None:
        stack = Cargo(item); stack.amount = amount; fit.cargo.append(stack)
        if stack not in fit.cargo:
            raise ValueError('This item cannot enter cargo')
    else:
        if stack.amount > cargo.MAX_QUANTITY - amount:
            raise ValueError('Cargo quantity is too large')
        stack.amount += amount


def _take(fit, identity, amount):
    stack = _stack(fit, identity)
    if stack is None:
        return
    stack.amount -= min(stack.amount, amount)
    if stack.amount <= 0:
        fit.cargo.remove(stack)


def _base(module):
    return module.baseItem if module.isMutated else module.item


def _replace(engine, fit, position, item):
    """Attempt the original replacement, restoring fit-wide states on failure."""
    import eos.db
    from eos.saveddata.module import Module
    from .bulk_edits import _inputs
    old = fit.modules[position]
    new = Module(item)
    if new.slot != old.slot:
        return False
    new.state = old.state if new.isValidState(old.state) else new.getMaxState(proposedState=old.state)
    new.spoolType, new.spoolAmount = old.spoolType, old.spoolAmount
    new.rahPatternOverride, new.charge = old.rahPatternOverride, old.charge
    restored, before = deepcopy(old), _inputs(fit)
    fit.modules.replace(position, new)
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    fitting.check_states(fit, new)
    if new not in fit.modules or not new.fits(fit):
        fit.modules.free(position)
        fit.modules.replace(position, restored)
        for entries in before:
            for thing, value in entries:
                if thing is old:
                    continue
                if hasattr(thing, 'state'):
                    thing.state = value
                else:
                    thing.amountActive = value
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
        return False
    unloaded = not new.isValidCharge(new.charge)
    old_charge, old_amount = old.charge, old.numCharges
    if unloaded:
        new.charge = None
    # Original command adds the displaced module before its charge adjustments.
    if not old.isEmpty:
        _add(fit, _base(old), 1)
    if old_charge is not None:
        if unloaded:
            _add(fit, old_charge, old_amount)
        else:
            extra = new.numCharges - old_amount
            if extra > 0:
                _take(fit, old_charge.ID, extra)
            elif extra < 0:
                _add(fit, old_charge, -extra)
    return True


def _from_cargo(engine, fit, position, identity, copy):
    stack = _stack(fit, identity)
    if stack is None:
        raise ValueError('The cargo stack is no longer present')
    old = fit.modules[position]
    item = stack.item
    if item.isCharge and not old.isEmpty:
        if old.chargeID == identity:
            return
        if not old.isValidCharge(item):
            raise ValueError('Choose a compatible charge')
        if not copy:
            _take(fit, identity, old.getNumCharges(item))
        if old.charge is not None:
            _add(fit, old.charge, old.numCharges)
        old.charge = item
        fitting._reconcile(engine, fit, None)
    elif item.isModule:
        if old.itemID == identity:
            return
        # Remove first so original successful stack order and merges are retained.
        if not copy:
            _take(fit, identity, 1)
        if not _replace(engine, fit, position, item):
            raise ValueError('The cargo module cannot replace this fitting position')
    else:
        raise ValueError('Choose a cargo module or a compatible loaded-charge target')


def _to_cargo(engine, fit, position, identity, copy):
    old = fit.modules[position]
    if old.isEmpty:
        return
    target = _stack(fit, identity)
    if not copy and target is not None and target.item.isModule:
        if old.itemID == identity:
            return
        # Attempt replacement before consuming target; a failed swap falls back
        # to dumping the original module, with no failed-edit cargo corruption.
        target_item = target.item
        if _replace(engine, fit, position, target_item):
            _take(fit, identity, 1)
            return
        old = fit.modules[position]
    _add(fit, _base(old), 1)
    if old.charge is not None:
        _add(fit, old.charge, old.numCharges)
    if not copy:
        fit.modules.free(position)
        fitting._reconcile(engine, fit, None)


def transfer(engine, fit, direction, positions, item_id, copy):
    engine._check_fit(fit)
    if direction not in ('TO_CARGO', 'FROM_CARGO') or type(copy) is not bool:
        raise ValueError('Choose a cargo transfer direction and copy option')
    if (type(positions) is not list or not positions or
            any(type(value) is not int for value in positions) or len(set(positions)) != len(positions)):
        raise ValueError('Choose distinct fitting positions')
    if item_id is not None and (type(item_id) is not int or item_id <= 0):
        raise ValueError('Choose a cargo item')
    for position in positions:
        _position(fit, position)
    if direction == 'FROM_CARGO' and (len(positions) != 1 or item_id is None):
        raise ValueError('Choose one destination and a cargo stack')
    if item_id is not None and _stack(fit, item_id) is None:
        raise ValueError('The cargo stack is no longer present')
    method = _to_cargo if direction == 'TO_CARGO' else _from_cargo
    # Descending positions keep earlier references stable if a subsystem changes
    # available slots. The enclosing bridge transaction makes the batch atomic.
    for position in sorted(positions, reverse=True):
        method(engine, fit, position, item_id, copy)
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    fitting._fill(fit)
    # Original transfers do not promote market recent use.


def details(engine, fit):
    from eos.const import FittingModuleState, FittingSlot
    engine._check_fit(fit)
    return {**cargo.details(engine, fit), 'modules': [
        {'index': i, 'id': m.itemID, 'name': m.item.name if m.item else None,
         'slot': FittingSlot(m.slot).name, 'state': FittingModuleState(m.state).name,
         'charge_id': m.chargeID, 'charge': m.charge.name if m.charge else None,
         'charge_amount': m.numCharges, 'legal': None if m.isEmpty else m.fits(fit)}
        for i, m in enumerate(fit.modules)]}
