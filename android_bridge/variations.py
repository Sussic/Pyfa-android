"""Worker-only variation policy adapted from pinned desktop Pyfa commands.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source 8b04f3b271e614b3e103853b44a7851a63d79d0e: itemVariationChange,
localModule/localDrone changeMetas, implant changeMeta and their calc commands.
EOS owns family eligibility, restrictions, states and every calculation.
"""
from . import fitting

CONTEXTS = ('module', 'drone', 'implant')


def choices(engine, fit, item, context, policy=None):
    engine._check_fit(fit)
    from .market_policy import MarketPolicy
    if context not in CONTEXTS:
        raise ValueError('Choose modules, drones or fit implants')
    policy = policy or MarketPolicy()
    family = policy.getVariationsByItems((item,))
    if len(family) < 2:
        return []
    items = [value for value in family if policy.getMetaGroupIdByItem(value) != 15]
    items.sort(key=lambda value: value.name)
    if context != 'implant':
        items.sort(key=lambda value: value.metaLevel or 0)
        remap = {5: 6, 6: 5, 54: 52, 52: 54}
        items.sort(key=lambda value: remap.get(policy.getMetaGroupIdByItem(value), policy.getMetaGroupIdByItem(value)))
    result = []
    for value in items:
        meta = policy.getMetaGroupByItem(value)
        group = None if context == 'implant' else (
            value.marketGroup.marketGroupName if 'subSystem' in value.effects else meta.name if meta else 'Tech I')
        result.append({'id': value.ID, 'name': value.name, 'group': group, 'enabled': fit.canFit(value)})
    return result


def options(engine, fit):
    engine._check_fit(fit)
    from .bulk_edits import family_options
    from .market_policy import MarketPolicy
    from eos.const import FittingModuleState, ImplantLocation
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    policy, targets = MarketPolicy(), []
    for context, things in (('module', fit.modules), ('drone', fit.drones), ('implant', fit.implants)):
        for index, thing in enumerate(things):
            if getattr(thing, 'isEmpty', False):
                continue
            if context == 'module' and thing.slot not in fitting.SLOTS.values():
                continue
            current = ({'state': FittingModuleState(thing.state).name, 'charge_id': thing.chargeID}
                if context == 'module' else {'amount': thing.amount, 'active': thing.amountActive}
                if context == 'drone' else {'slot': thing.slot, 'active': thing.active,
                                           'location': ImplantLocation(fit.implantLocation).name})
            targets.append({'context': context, 'index': index, 'item_id': thing.itemID, 'name': thing.item.name,
                            'current': current, 'choices': choices(engine, fit, thing.item, context, policy)})
    return {'targets': targets, 'module_families': family_options(engine, fit)}


def change(engine, fit, context, position, identity):
    engine._check_fit(fit)
    if context not in CONTEXTS:
        raise ValueError('Choose modules, drones or fit implants')
    things = {'module': fit.modules, 'drone': fit.drones, 'implant': fit.implants}[context]
    if type(position) is not int or not 0 <= position < len(things):
        raise ValueError('Choose an item in this fit')
    old = fitting._position(fit, position, occupied=True) if context == 'module' else things[position]
    item = fitting.item(engine, identity)
    if not any(row['id'] == identity and row['enabled'] for row in choices(engine, fit, old.item, context)):
        raise ValueError('Choose an enabled variation of this item')
    if old.itemID == identity:
        if context != 'implant':
            fitting._fill(fit)
        return
    import eos.db
    if context == 'module':
        module = fitting.new_module(engine, identity)
        if module.slot != old.slot:
            raise ValueError('Variation requires the same slot type')
        module.state = old.state if module.isValidState(old.state) else module.getMaxState(proposedState=old.state)
        module.spoolType, module.spoolAmount = old.spoolType, old.spoolAmount
        module.rahPatternOverride, module.charge = old.rahPatternOverride, old.charge
        fit.modules.replace(position, module)
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
        changed = fitting.check_states(fit, module)
        if module not in fit.modules or not module.fits(fit):
            raise ValueError('The variation exceeds a fitting restriction')
        if not module.isValidCharge(module.charge):
            module.charge = None
            changed = True
        if changed:
            eos.db.saveddata_session.flush()
            engine._recalculate(fit)
    elif context == 'drone':
        from eos.saveddata.drone import Drone
        drone = Drone(item)
        drone.amount, drone.amountActive = old.amount, old.amountActive
        fit.drones.remove(old)
        fit.drones.append(drone)
        if drone not in fit.drones:
            raise ValueError('The variation could not replace this drone stack')
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
    else:
        from eos.const import ImplantLocation
        from eos.saveddata.implant import Implant
        if fit.implantLocation != ImplantLocation.FIT:
            raise ValueError('Choose a fit-local implant')
        implant = Implant(item)
        implant.active = old.active
        if any(existing.itemID == identity for existing in fit.implants):
            raise ValueError('This implant is already fitted')
        # Original HandledImplantList.makeRoom imports desktop GUI helpers. Keep
        # its slot-removal/ORM identity behavior here without importing the UI.
        occupant = next((value for value in fit.implants if value.slot == implant.slot), None)
        if occupant is not None:
            occupant.itemID = 0
            fit.implants.remove(occupant)
        fit.implants.append(implant)
        if implant not in fit.implants:
            raise ValueError('The variation could not replace this implant')
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
    fitting._fill(fit)
    # Unlike ordinary module replacement, variations never promote recent use.
