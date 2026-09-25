"""Bulk selection policy adapted from pinned desktop helpers and charge commands.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source: 8b04f3b271e614b3e103853b44a7851a63d79d0e. EOS supplies all compatibility,
states and calculations; the bridge provides one atomic durable user action.
"""
from . import charges, fitting


def similar(modules, main, policy):
    # The pin's forced group substitutions apply to hulls only; fitted modules
    # use their original game group. Market-group substitutions still apply.
    main_group = getattr(main.item, 'groupID', None)
    main_market = getattr(policy.getMarketGroupByItem(main.item), 'ID', None)
    main_effects = set(getattr(main.item, 'effects', ()))
    result = []
    for index, module in enumerate(modules):
        if module.isEmpty:
            continue
        if module is main or module.itemID == main.itemID:
            result.append(index)
            continue
        group = getattr(module.item, 'groupID', None)
        market = getattr(policy.getMarketGroupByItem(module.item), 'ID', None)
        if (group is not None and group == main_group and market is not None and market == main_market
                and set(getattr(module.item, 'effects', ())) == main_effects):
            result.append(index)
    return result


def options(engine, fit):
    from .market_policy import MarketPolicy
    value = charges.options(engine, fit)
    policy = MarketPolicy()
    sets = [set(row['charge_ids']) for row in value['modules']]
    for row, module in zip(value['modules'], fit.modules):
        row['selection_candidates'] = [] if module.isEmpty else [i for i, other in enumerate(fit.modules)
            if not other.isEmpty and sets[i].issubset(sets[row['index']])]
        row['similar_candidates'] = [] if module.isEmpty else similar(fit.modules, module, policy)
    return value


def change_charges(engine, fit, main_position, module_indices, scope, charge_id):
    engine._check_fit(fit)
    main = fitting._position(fit, main_position, occupied=True)
    if type(module_indices) is not list or not module_indices or len(set(module_indices)) != len(module_indices):
        raise ValueError('Select modules without duplicate positions')
    for position in module_indices:
        fitting._position(fit, position, occupied=True)
    if main_position not in module_indices:
        raise ValueError('Include the reference module in the selection')
    if scope not in ('SELECTED', 'SIMILAR'):
        raise ValueError('Choose selection only or all similar modules')
    main_charges = charges.compatible(main)
    if not main_charges:
        raise ValueError('Choose a reference module with compatible charges')
    charge = None if charge_id is None else fitting.item(engine, charge_id)
    if charge is not None and charge not in main_charges:
        raise ValueError('Choose a compatible charge for the reference module')
    if scope == 'SIMILAR':
        from .market_policy import MarketPolicy
        positions = similar(fit.modules, main, MarketPolicy())
    else:
        positions = [i for i, module in enumerate(fit.modules)
                     if i in module_indices and charges.compatible(module).issubset(main_charges)]
    changed = False
    for position in positions:
        module = fit.modules[position]
        if module.chargeID != charge_id and module.isValidCharge(charge):
            module.charge = charge
            changed = True
    if changed:
        fitting._reconcile(engine, fit, None)
    fitting._fill(fit)
    # Scope filtering is desktop behavior; storage failure rolls back every edit.
    # Charges do not promote recent equipment history.
