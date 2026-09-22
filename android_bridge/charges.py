"""Charge policy adapted from pinned desktop commands and service/ammo.py.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source: 8b04f3b271e614b3e103853b44a7851a63d79d0e. EOS owns compatibility and
calculation; the serialized bridge owns atomic recovery and durable inputs.
"""
from . import fitting


def compatible(module):
    from .market_policy import MarketPolicy
    if module.isEmpty:
        return set()
    policy = MarketPolicy()
    return {item for item in module.getValidCharges() if policy.getPublicityByItem(item)}


def options(engine, fit):
    engine._check_fit(fit)
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    items, modules = {}, []
    for index, module in enumerate(fit.modules):
        choices = compatible(module)
        items.update((item.ID, item) for item in choices)
        modules.append({'index': index, 'item_id': module.itemID, 'charge_id': module.chargeID,
                        'charge_ids': sorted(item.ID for item in choices)})
    return {'modules': modules, 'items': [{'id': identity, 'name': items[identity].name}
                                        for identity in sorted(items)]}


def change(engine, fit, position, charge_id):
    engine._check_fit(fit)
    module = fitting._position(fit, position, occupied=True)
    charge = None if charge_id is None else fitting.item(engine, charge_id)
    if charge is not None and not charge.isCharge or not module.isValidCharge(charge):
        raise ValueError('Choose a compatible charge')
    if module.chargeID != charge_id:
        module.charge = charge
        fitting._reconcile(engine, fit, None)
    fitting._fill(fit)
    # Original charge changes do not promote recent-use items.
