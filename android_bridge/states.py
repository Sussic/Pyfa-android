"""Bulk local-module state policy from the pinned desktop state command.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
EOS owns transitions, state limits and calculations. The bridge owns one atomic
durable action and recovery.
"""
from . import fitting
from .bulk import similar
from .market_policy import MarketPolicy


CLICKS = ('left', 'right', 'ctrl')


def options(engine, fit):
    engine._check_fit(fit)
    from eos.const import FittingModuleState
    from eos.saveddata.module import Module

    if not fit.calculated:
        fit.calculateModifiedAttributes()
    policy = MarketPolicy()
    rows = []
    for index, module in enumerate(fit.modules):
        if module.isEmpty:
            rows.append({'index': index, 'item_id': None, 'state': None,
                         'editable': False, 'similar_candidates': [],
                         'click_states': {}, 'supported_states': {}})
            continue
        editable = module.slot in fitting.SLOTS.values()
        rows.append({'index': index, 'item_id': module.itemID,
                     'state': FittingModuleState(module.state).name,
                     'editable': editable,
                     'similar_candidates': [i for i in similar(fit.modules, module, policy)
                                            if fit.modules[i].slot in fitting.SLOTS.values()] if editable else [],
                     'click_states': {click: FittingModuleState(Module.getProposedState(module, click)).name
                                      for click in CLICKS},
                     'supported_states': {state.name: FittingModuleState(module.getMaxState(proposedState=state)).name
                                          for state in FittingModuleState}})
    return {'modules': rows}


def change(engine, fit, main_position, module_indices, scope, click):
    engine._check_fit(fit)
    from eos.saveddata.module import Module

    main = fitting._position(fit, main_position, occupied=True)
    if type(module_indices) is not list or not module_indices or len(set(module_indices)) != len(module_indices):
        raise ValueError('Select modules without duplicate positions')
    for position in module_indices:
        fitting._position(fit, position, occupied=True)
    if main_position not in module_indices:
        raise ValueError('Include the reference module in the selection')
    if scope not in ('SELECTED', 'SIMILAR') or click not in CLICKS:
        raise ValueError('Choose a supported state action and scope')
    positions = ([i for i in similar(fit.modules, main, MarketPolicy())
                  if fit.modules[i].slot in fitting.SLOTS.values()] if scope == 'SIMILAR'
                 else [i for i in range(len(fit.modules)) if i in module_indices])
    proposed = Module.getProposedState(main, click)
    changed = main.state != proposed
    main.state = proposed
    for position in positions:
        if position == main_position:
            continue
        module = fit.modules[position]
        state = Module.getProposedState(module, click, proposed)
        if module.state != state:
            module.state = state
            changed = True
    if changed:
        # The original checkStates skips the reference while reconciling limits
        # on other local/projected modules and drones after recalculation.
        fitting._reconcile(engine, fit, main)
    fitting._fill(fit)
    # State clicks do not promote recent equipment history.
