"""Pinned desktop selected/similar module variation and removal commands.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Original selection and GUI/calc commands at 8b04f3b271e614b3e103853b44a7851a63d79d0e.
The bridge supplies one serialized, atomic durable action; EOS owns fitting.
"""
from . import fitting, variations
from .bulk import similar


def _selection(engine, fit, main_position, indices, scope):
    engine._check_fit(fit)
    main = fitting._position(fit, main_position, occupied=True)
    if type(indices) is not list or not indices or len(set(indices)) != len(indices):
        raise ValueError('Select fitted modules without duplicate positions')
    for position in indices:
        fitting._position(fit, position, occupied=True)
    if main_position not in indices:
        raise ValueError('Include the reference module in the selection')
    if scope not in ('SELECTED', 'SIMILAR'):
        raise ValueError('Choose selection only or all similar modules')
    return main


def positions(engine, fit, main_position, indices, scope, kind):
    from .market_policy import MarketPolicy
    main = _selection(engine, fit, main_position, indices, scope)
    policy = MarketPolicy()
    if scope == 'SIMILAR':
        return similar(fit.modules, main, policy)
    if kind == 'remove':
        return list(indices)
    family = policy.getVariationsByItems((main.item,))
    return [index for index in indices if index == main_position or
            policy.getVariationsByItems((fit.modules[index].item,)) == family]


def family_options(engine, fit):
    """Read-only exact-family previews, evaluating each distinct item once."""
    engine._check_fit(fit)
    from .market_policy import MarketPolicy
    policy = MarketPolicy()
    modules = [(index, module) for index, module in enumerate(fit.modules)
               if not module.isEmpty and module.slot in fitting.SLOTS.values()]
    families = {}
    for _, module in modules:
        if module.itemID not in families:
            families[module.itemID] = policy.getVariationsByItems((module.item,))
    return [{'index': index, 'candidates': [other_index for other_index, other in modules
                if families[other.itemID] == families[module.itemID]]}
            for index, module in modules]


def _inputs(fit):
    # Original CalcReplace.Undo restores fit-wide states after an unsuccessful
    # replacement. Preserve the same inputs before attempting the next position.
    return ([(module, module.state) for module in fit.modules if not module.isEmpty],
            [(module, module.state) for module in fit.projectedModules],
            [(drone, drone.amountActive) for drone in fit.projectedDrones])


def _restore(engine, fit, position, old, before):
    from eos.saveddata.module import Module
    # SQLAlchemy marks the displaced object deleted during replace(). The
    # pinned CalcReplace.Undo reconstructs ModuleInfo rather than reattaching
    # that object; do the same with EOS data and retain its declarative inputs.
    restored = Module(old.item)
    restored.state = old.state
    restored.spoolType, restored.spoolAmount = old.spoolType, old.spoolAmount
    restored.rahPatternOverride, restored.charge = old.rahPatternOverride, old.charge
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
    fitting._reconcile(engine, fit, restored)


def change_variations(engine, fit, main_position, indices, scope, item_id):
    import eos.db
    selected = positions(engine, fit, main_position, indices, scope, 'variation')
    main = fit.modules[main_position]
    if not any(row['id'] == item_id and row['enabled'] for row in
               variations.choices(engine, fit, main.item, 'module')):
        raise ValueError('Choose an enabled variation of the reference module')
    changed = False
    for position in selected:
        old = fit.modules[position]
        if old.isEmpty or old.itemID == item_id:
            continue
        candidate = fitting.new_module(engine, item_id)
        if candidate.slot != old.slot:
            continue
        before = _inputs(fit)
        candidate.state = old.state if candidate.isValidState(old.state) else candidate.getMaxState(proposedState=old.state)
        candidate.spoolType, candidate.spoolAmount = old.spoolType, old.spoolAmount
        candidate.rahPatternOverride, candidate.charge = old.rahPatternOverride, old.charge
        fit.modules.replace(position, candidate)
        if candidate not in fit.modules:
            _restore(engine, fit, position, old, before)
            continue
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
        fitting.check_states(fit, candidate)
        if not candidate.fits(fit):
            _restore(engine, fit, position, old, before)
            continue
        if not candidate.isValidCharge(candidate.charge):
            candidate.charge = None
        changed = True
    # Original GUI command fills and commits once, including unchanged commands.
    if changed:
        fitting._reconcile(engine, fit, None)
    fitting._fill(fit)
    return []  # Variation never promotes recent use.


def remove_modules(engine, fit, main_position, indices, scope):
    selected = positions(engine, fit, main_position, indices, scope, 'remove')
    removed = {position: fit.modules[position].itemID for position in selected
               if not fit.modules[position].isEmpty}
    for position in selected:
        fit.modules.free(position)
    fitting._reconcile(engine, fit, None)
    fitting._fill(fit)
    # Desktop GUI promotes ordinary modules in descending slot position.
    return [removed[position] for position in sorted(removed, reverse=True)]
