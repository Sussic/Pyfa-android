"""Local module fill and clone policy from the pinned desktop commands.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source: gui/fitCommands/{calc/module/localAdd,calc/module/localClone,
gui/localModule/fillAdd,gui/localModule/fillClone}.py at
8b04f3b271e614b3e103853b44a7851a63d79d0e.
EOS owns legality and calculations; the bridge saves each request atomically.
"""
from copy import deepcopy

from . import fitting


def _sources(fit, positions):
    if type(positions) is not list or not positions or len(set(positions)) != len(positions):
        raise ValueError('Select fitted modules without duplicate positions')
    return [fitting._position(fit, position, occupied=True) for position in positions]


def _vacancies(fit, slot):
    return [index for index, module in enumerate(fit.modules)
            if module.isEmpty and module.slot == slot]


def item_options(engine, fit, identity):
    engine._check_fit(fit)
    from eos.const import FittingSlot
    from eos.saveddata.module import Module

    value = fitting.item(engine, identity)
    module = Module(value)
    if module.slot not in fitting.SLOTS.values() or value.isAbyssal:
        raise ValueError('This item needs a different fitting editor')
    return {'item_id': identity, 'slot': FittingSlot(module.slot).name,
            'vacancies': max(0, int(fit.getSlotsFree(module.slot))),
            'ignore_restrictions': bool(fit.ignoreRestrictions)}


def vacancy_options(engine, fit):
    engine._check_fit(fit)
    from eos.const import FittingSlot

    # Mirror EOS Fit.fill's slot/dummy ordering without mutating a read. This
    # includes subsystem positions, which can shift later service positions.
    rows = [{'slot': module.slot, 'empty': module.isEmpty} for module in fit.modules]
    for slot in (FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH,
                 FittingSlot.RIG, FittingSlot.SUBSYSTEM, FittingSlot.SERVICE):
        slot_id = slot.value
        amount = fit.getSlotsFree(slot_id, True)
        if amount > 0:
            rows.extend({'slot': slot_id, 'empty': True} for _ in range(int(amount)))
        elif amount < 0:
            while amount < 0:
                position = next((i for i, row in enumerate(rows)
                                 if row['empty'] and row['slot'] == slot_id), None)
                if position is None:
                    break
                rows.pop(position)
                amount += 1
    return {'vacancies': [{'index': index, 'slot': FittingSlot(row['slot']).name}
                          for index, row in enumerate(rows)
                          if row['empty'] and row['slot'] in fitting.SLOTS.values()]}


def _make_from_fitted(source):
    # ModuleInfo.fromModule/toModule creates a new local module with these
    # persisted inputs. Mutated-module inputs remain in C10's dedicated editor.
    from eos.saveddata.module import Module

    if source.item.isAbyssal or getattr(source, 'mutation', None) is not None:
        raise ValueError('Mutated modules need the mutation editor')
    result = Module(source.item)
    result.state = source.state
    result.charge = source.charge
    return result


def _append(engine, fit, module):
    import eos.db

    fit.modules.append(module)
    if module not in fit.modules:
        return False
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    if not module.fits(fit):
        fit.modules.free(fit.modules.index(module))
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
        return False
    if fitting.check_states(fit, module):
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
    return True


def fill_item(engine, fit, identity):
    engine._check_fit(fit)
    sample = fitting.new_module(engine, identity)
    fit.fill()
    capacity = len(_vacancies(fit, sample.slot))
    added = 0
    for _ in range(capacity):
        if not _append(engine, fit, fitting.new_module(engine, identity)):
            break
        added += 1
    fitting._fill(fit)
    if not added:
        # The original fill-add command records even an unsuccessful market
        # attempt. BridgeSession persists that history via FittingRejected.
        raise fitting.FittingRejected('No compatible vacant slot accepts this module.', identity)
    return [identity]


def fill_clone(engine, fit, source_position):
    engine._check_fit(fit)
    source = fitting._position(fit, source_position, occupied=True)
    fit.fill()
    capacity = len(_vacancies(fit, source.slot))
    added = 0
    for _ in range(capacity):
        if not _append(engine, fit, _make_from_fitted(source)):
            break
        added += 1
    fitting._fill(fit)
    if not added:
        raise ValueError('No compatible vacant slot accepts this clone')
    return []  # Original fill-clone does not promote recent market use.


def _clone_at(engine, fit, source, destination):
    import eos.db

    target = fitting._position(fit, destination)
    if not target.isEmpty or target.slot != source.slot:
        raise ValueError('Choose a vacant slot in the source module’s rack')
    copy = deepcopy(source)
    # Original CalcClone checks fits before replacing the destination.
    if not copy.fits(fit):
        raise ValueError('The clone exceeds a fitting restriction')
    fit.modules.replace(destination, copy)
    if copy not in fit.modules:
        raise ValueError('The clone could not occupy its destination')
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    if fitting.check_states(fit, copy):
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)


def clone_at(engine, fit, source_position, destination_position):
    engine._check_fit(fit)
    source = fitting._position(fit, source_position, occupied=True)
    if source_position == destination_position:
        raise ValueError('Choose a different vacant destination')
    fit.fill()
    _clone_at(engine, fit, source, destination_position)
    fitting._fill(fit)
    return []


def clone_selected(engine, fit, source_positions):
    engine._check_fit(fit)
    sources = _sources(fit, source_positions)
    fit.fill()
    # Resolve all destinations before mutation. Each source takes the first
    # still-vacant position in its own rack, in fit order.
    available = {slot: _vacancies(fit, slot) for slot in fitting.SLOTS.values()}
    ordered = sorted(zip(source_positions, sources), key=lambda row: row[0])
    destinations = []
    for _, source in ordered:
        if not available[source.slot]:
            raise ValueError('Select at most one source for each available slot')
        destinations.append(available[source.slot].pop(0))
    for (_, source), destination in zip(ordered, destinations):
        _clone_at(engine, fit, source, destination)
    fitting._fill(fit)
    return []  # Original single clone does not promote recent market use.
