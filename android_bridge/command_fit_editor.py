"""Saved command-fit UI policy, separate from exact replay-level helpers.

GPL-3.0-or-later, Pyfa contributors; see LICENSE. Adapted from original
calc/commandFit and gui/commandFit commands. The graph owns durable commits.
"""


def _finish(engine, target):
    import eos.db
    from .fitting import _fill
    # Unlike projected-fit actions, original command-fit wrappers do not invoke
    # checkStates. Preserve their flush / LOCAL recalc / fill boundary instead.
    eos.db.saveddata_session.flush()
    engine._recalculate(target)
    _fill(target)


def add(engine, source, target):
    engine._check_fit(source)
    engine._check_fit(target)
    changed = source not in target.commandFits and source.ID not in target.commandFitDict
    if changed:
        import eos.db
        from .inspection_identity import capture, restore
        from .module_rah import capture_overrides, restore_overrides
        identities, overrides = capture(source), capture_overrides(source)
        target.commandFitDict[source.ID] = source
        # Original calc addition refreshes its source (upstream issue #83).
        # Preserve Android-only durable identity/unmapped input bookkeeping and
        # invalidate derived caches without adding a pre-GUI target recalc.
        eos.db.saveddata_session.flush()
        from .projected_module_records import refresh_order, restore_refresh_order
        projected_order = refresh_order(source)
        from .projected_drone_records import refresh_order as drone_order, restore_refresh_order as restore_drones
        saved_drone_order = drone_order(source)
        from .projected_fighter_records import refresh_order as fighter_order, restore_refresh_order as restore_fighters
        saved_fighter_order = fighter_order(source)
        from .character_implants import refresh_order as implant_order, restore_refresh_order as restore_implants
        saved_implant_order = implant_order(source)
        eos.db.saveddata_session.refresh(source)
        engine._restore_security_inputs(source)
        restore_implants(source, saved_implant_order)
        restore_refresh_order(source, projected_order)
        restore_drones(source, saved_drone_order)
        restore_fighters(source, saved_fighter_order)
        restore_overrides(source, overrides)
        source.clear()
        restore(source, identities)
    _finish(engine, target)
    return changed


def active(engine, source, target, value):
    if type(value) is not bool:
        raise ValueError('Command fit active state must be boolean')
    info = engine._command(source, target)
    changed = info.active != value
    # This is the original single-row toggle's captured desired/forced state.
    info.active = value
    _finish(engine, target)
    return changed


def remove(engine, source, target):
    engine._command(source, target)
    del target.commandFitDict[source.ID]
    _finish(engine, target)
    return True
