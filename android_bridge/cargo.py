"""Cargo policy adapted from pinned cargo commands and context menus.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source 8b04f3b271e614b3e103853b44a7851a63d79d0e: cargo changeAmount,
remove/changeMetas, cargoAddAmmo, cargoFill and itemVariationChange.
"""

MAX_QUANTITY = 2**63 - 1


def _selected(fit, item_ids):
    if (type(item_ids) is not list or not item_ids or
            any(type(value) is not int or value <= 0 for value in item_ids) or
            len(set(item_ids)) != len(item_ids)):
        raise ValueError('Choose distinct cargo stacks')
    lookup = {row.itemID: row for row in fit.cargo}
    if any(value not in lookup for value in item_ids):
        raise ValueError('A selected cargo stack is no longer in this fit')
    return [lookup[value] for value in item_ids]


def action_options(engine, fit, item_id, from_cargo):
    from .fitting import item as get_item
    from .variations import choices
    engine._check_fit(fit)
    if type(from_cargo) is not bool:
        raise ValueError('Choose a cargo or market item')
    item = get_item(engine, item_id)
    if from_cargo:
        _selected(fit, [item_id])
    preset = (8 if item.marketGroup and item.marketGroup.name == 'Scan Probes' else 1000
              ) if item.category.ID == 8 else None
    fill_visible = from_cargo or item.isCharge or item.isCommodity
    amount = 0
    if fill_visible:
        # Original context command uses base volume and integer truncation.
        volume = item.attributes['volume'].value
        available = fit.ship.getModifiedItemAttr('capacity') - fit.cargoBayUsed
        if volume is not None and volume > 0 and available > 0:
            amount = int(available / volume)
    return {'item_id': item_id, 'from_cargo': from_cargo,
            'preset_quantity': preset if not from_cargo else None,
            'fill_quantity': amount if fill_visible else None,
            'variations': choices(engine, fit, item, 'cargo') if from_cargo else []}


def selected_quantity(engine, fit, item_ids, amount):
    engine._check_fit(fit)
    rows = _selected(fit, item_ids)
    if type(amount) is not int or not 0 <= amount <= MAX_QUANTITY:
        raise ValueError('Cargo quantity must be a non-negative whole number')
    for row in rows:
        if amount == 0:
            fit.cargo.remove(row)
        else:
            row.amount = amount
    # Quantity changes, including zero-to-remove, do not promote recent use.


def remove_selected(engine, fit, item_ids):
    engine._check_fit(fit)
    for row in _selected(fit, item_ids):
        fit.cargo.remove(row)
    return item_ids


def preset(engine, fit, item_id):
    amount = action_options(engine, fit, item_id, False)['preset_quantity']
    if amount is None:
        raise ValueError('Choose ammunition for this preset')
    return change(engine, fit, 'add', item_id, amount)


def fill(engine, fit, item_id, from_cargo):
    amount = action_options(engine, fit, item_id, from_cargo)['fill_quantity']
    if amount is None:
        raise ValueError('This market item cannot fill cargo')
    if amount > 0:
        return change(engine, fit, 'add', item_id, amount)


def change_variations(engine, fit, main_item_id, item_ids, item_id):
    from .market_policy import MarketPolicy
    engine._check_fit(fit)
    rows = _selected(fit, item_ids)
    if main_item_id not in item_ids:
        raise ValueError('The main cargo stack must be selected')
    options = action_options(engine, fit, main_item_id, True)
    if not any(row['id'] == item_id and row['enabled'] for row in options['variations']):
        raise ValueError('Choose an enabled cargo variation')
    policy = MarketPolicy()
    main = next(row for row in rows if row.itemID == main_item_id)
    family = policy.getVariationsByItems((main.item,))
    for row in rows:
        if row.itemID == item_id or policy.getVariationsByItems((row.item,)) != family:
            continue
        amount = row.amount
        fit.cargo.remove(row)
        change(engine, fit, 'add', item_id, amount)
    # The enclosing graph transaction restores every stack if any addition fails.


def details(engine, fit):
    engine._check_fit(fit)
    capacity = fit.ship.getModifiedItemAttr('capacity')
    used = fit.cargoBayUsed
    return {'is_structure': fit.isStructure, 'capacity_m3': capacity, 'used_m3': used,
            'over_capacity': used > capacity,
            'cargo': [{'id': cargo.itemID, 'name': cargo.item.name,
                       'amount': cargo.amount,
                       'unit_volume_m3': cargo.getModifiedItemAttr('volume')}
                      for cargo in fit.cargo]}


def change(engine, fit, action, item_id, amount):
    import eos.db
    from eos.saveddata.cargo import Cargo

    engine._check_fit(fit)
    if type(amount) is not int or not 1 <= amount <= MAX_QUANTITY:
        raise ValueError('Cargo quantity must be positive')
    item = eos.db.getItem(item_id)
    if item is None or not item.published:
        raise ValueError('Cargo item is unavailable')
    if action == 'add' and fit.isStructure and item.category.ID != 8:
        raise ValueError('Only charges can be added to structure cargo')
    cargo = next((row for row in fit.cargo if row.itemID == item_id), None)
    if action == 'add':
        if cargo is None:
            cargo = Cargo(item)
            cargo.amount = amount
            fit.cargo.append(cargo)
            if cargo not in fit.cargo:
                raise ValueError('Cargo item could not be added')
        else:
            if cargo.amount > MAX_QUANTITY - amount:
                raise ValueError('Cargo quantity is too large')
            cargo.amount += amount
    elif action == 'set':
        if cargo is None:
            raise ValueError('Cargo item is not in this fit')
        if cargo.amount == amount:
            return None
        cargo.amount = amount
    elif action == 'remove':
        if cargo is None:
            raise ValueError('Cargo item is not in this fit')
        cargo.amount -= min(cargo.amount, amount)
        if cargo.amount == 0:
            fit.cargo.remove(cargo)
    else:
        raise ValueError('Unsupported cargo action')
    return [item_id]
