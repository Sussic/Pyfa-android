"""Strategic-cruiser subsystem choices and pinned local module command order."""

from .fitting import FittingRejected, _fill, _reconcile, check_states


KINDS = {125: 'Core', 126: 'Defensive', 127: 'Offensive', 128: 'Propulsion'}


def _kind(module):
    from eos.const import FittingSlot
    if module.isEmpty or module.slot != FittingSlot.SUBSYSTEM:
        return None
    value = module.getModifiedItemAttr('subSystemSlot')
    return int(value) if value in KINDS else None


def _choices(engine, fit):
    import eos.db
    from eos.saveddata.module import Module
    engine._check_fit(fit)
    result = {kind: [] for kind in KINDS}
    if fit.ship.item.group.name != 'Strategic Cruiser':
        return result
    for item in eos.db.getItemsByCategory('Subsystem'):
        if fit.canFit(item):
            module = Module(item)
            kind = _kind(module)
            if kind is not None:
                result[kind].append({'id': item.ID, 'name': item.name})
    for rows in result.values():
        rows.sort(key=lambda row: row['id'])
    return result


def options(engine, fit):
    from eos.const import FittingSlot
    choices = _choices(engine, fit)
    capacity = int(fit.getNumSlots(FittingSlot.SUBSYSTEM.value))
    if not any(choices.values()):
        return {'capacity': capacity, 'groups': []}
    groups = []
    for kind, name in KINDS.items():
        current = next((module.itemID for module in fit.modules
                        if module.slot == FittingSlot.SUBSYSTEM and _kind(module) == kind), None)
        groups.append({'kind': kind, 'name': name, 'current': current, 'choices': choices[kind]})
    return {'capacity': capacity, 'groups': groups}


def change(engine, fit, kind, item_id):
    from eos.const import FittingModuleState, FittingSlot
    from eos.saveddata.module import Module
    import eos.db
    engine._check_fit(fit)
    if type(kind) is not int or kind not in KINDS or item_id is not None and type(item_id) is not int:
        raise ValueError('Choose a subsystem type and item for this hull')
    choices = _choices(engine, fit)[kind]
    if not choices:
        raise ValueError('This hull has no selectable subsystems')
    position = next((index for index, module in enumerate(fit.modules)
                     if module.slot == FittingSlot.SUBSYSTEM and _kind(module) == kind), None)
    previous = fit.modules[position].itemID if position is not None else None
    if previous == item_id:
        return []
    if item_id is None:
        if position is None:
            return []
        fit.modules.free(position)
        _reconcile(engine, fit, None)
        _fill(fit)
        return [previous]
    if item_id not in {row['id'] for row in choices}:
        raise ValueError('Choose a subsystem supported by this hull and type')
    item = eos.db.getItem(item_id)
    module = Module(item)
    module.state = FittingModuleState.ONLINE
    if position is None:
        fit.fill()
        fit.modules.append(module)
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
        if module not in fit.modules or not module.fits(fit):
            raise FittingRejected('The subsystem exceeds a hull or fitting restriction.', item_id)
        if check_states(fit, module):
            engine._recalculate(fit)
    else:
        fit.modules.replace(position, module)
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
        changed = check_states(fit, module)
        if module not in fit.modules or not module.fits(fit):
            raise FittingRejected('The subsystem exceeds a hull or fitting restriction.', item_id)
        if changed:
            eos.db.saveddata_session.flush()
            engine._recalculate(fit)
    _fill(fit)
    return [item_id]
