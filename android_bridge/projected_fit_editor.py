"""Saved-fit projection UI policy, separate from exact replay-level link helpers.

GPL-3.0-or-later, Pyfa contributors; see LICENSE. Adapted from
GUI/calc projectedFit commands and service.fit.checkStates. The outer bridge
transaction alone commits durable state and records dependent-input history.
"""


def _finish(engine, target, check, *, always_recalculate=False):
    import eos.db
    from .fitting import check_states, _fill
    # Replay helpers already perform the calc command's initial recalc. Check
    # immediately afterward; the GUI's outer recalc follows any changed states.
    changed_states = check_states(target, None) if check else False
    if always_recalculate or changed_states:
        eos.db.saveddata_session.flush()
        engine._recalculate(target)
    _fill(target)


def add(engine, source, target):
    engine._check_fit(source)
    engine._check_fit(target)
    if source.ID in target.projectedFitDict:
        info = engine._projection(source, target)
        amount = min(20, max(1, info.amount + 1))
        changed = amount != info.amount
        if changed:
            engine.configure_projection(source, target, range_m=info.projectionRange,
                                        active=info.active, amount=amount)
    else:
        engine.add_projection(source, target, range_m=None, active=True, amount=1)
        changed = True
    _finish(engine, target, changed, always_recalculate=True)


def amount(engine, source, target, value):
    if type(value) is not int or not 0 <= value <= 2**31 - 1:
        raise ValueError('Choose a whole projection quantity from 0 to 20')
    info = engine._projection(source, target)
    if value == 0:
        engine.remove_projection(source, target)
        _finish(engine, target, True, always_recalculate=True)
    else:
        desired = min(20, value)
        if desired != info.amount:
            info.amount = desired
        # Original positive change-amount has no state-check side effect.
        _finish(engine, target, False, always_recalculate=True)


def option(engine, source, target, *, field, value):
    info = engine._projection(source, target)
    range_m = value if field == 'range' else info.projectionRange
    active = value if field == 'active' else info.active
    engine._projection_values(range_m, active, info.amount)
    previous = info.projectionRange if field == 'range' else info.active
    changed = value != previous
    if changed:
        engine.configure_projection(source, target, range_m=range_m,
                                    active=active, amount=info.amount)
    _finish(engine, target, changed, always_recalculate=not changed)


def remove(engine, source, target):
    engine.remove_projection(source, target)
    _finish(engine, target, True)
