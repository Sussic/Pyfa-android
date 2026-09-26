"""Hull-compatible structure service choices; EOS remains the fitting authority."""


def options(engine, fit):
    import eos.db
    from eos.const import FittingSlot
    from eos.saveddata.module import Module

    engine._check_fit(fit)
    is_structure = fit.ship.item.category.name == 'Structure'
    if not is_structure:
        return {'is_structure': False, 'capacity': 0, 'choices': []}
    choices = []
    for item in eos.db.getItemsByCategory('Structure Module'):
        if not item.published or not fit.canFit(item):
            continue
        try:
            module = Module(item)
        except ValueError:
            continue
        if not module.isInvalid and module.slot == FittingSlot.SERVICE:
            choices.append({'id': item.ID, 'name': item.name})
    choices.sort(key=lambda row: row['id'])
    return {'is_structure': True,
            'capacity': int(fit.getNumSlots(FittingSlot.SERVICE.value)),
            'choices': choices}
