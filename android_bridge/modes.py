"""Hull-specific EOS mode choices and the pinned desktop mode-change action."""


def options(engine, fit):
    engine._check_fit(fit)
    items = fit.ship.modeItems or ()
    return {'current': fit.mode.item.ID if fit.mode is not None else None,
            'choices': [{'id': item.ID, 'name': item.name} for item in items]}


def change(engine, fit, item_id):
    engine._check_fit(fit)
    if type(item_id) is not int:
        raise ValueError('Choose a mode supported by this hull')
    item = next((row for row in fit.ship.modeItems or () if row.ID == item_id), None)
    if item is None:
        raise ValueError('Choose a mode supported by this hull')
    if fit.mode is not None and fit.mode.item.ID == item_id:
        return []
    from eos.saveddata.mode import Mode
    from .fitting import _fill
    import eos.db
    fit.mode = Mode(item)
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    _fill(fit)
    return []
