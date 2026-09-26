"""Cargo stacks use EOS objects and the pinned desktop stack semantics."""

MAX_QUANTITY = 2**63 - 1


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
