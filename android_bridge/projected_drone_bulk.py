"""Selected incoming stacks: preflight and admit once, then one GUI boundary.

GPL-3.0-or-later, Pyfa contributors. Source policies are the projected drone
calc commands and their selected GUI wrappers. No per-stack recalculation.
"""
from copy import deepcopy
from . import projected_drone_editor as single
from . import projected_drone_records as records
from . import fitting

OPERATIONS = {
    'set_projected_drones_active': ('fit_id', 'selection', 'active'),
    'set_projected_drone_ranges': ('fit_id', 'selection', 'range_m'),
    'remove_projected_drones': ('fit_id', 'selection'),
}


def selected(fit, selection):
    """Capture all identities before constructing or applying any changes."""
    if type(selection) is not list or not 1 <= len(selection) <= records.MAX_STACKS:
        raise ValueError('Choose one or more projected drone stacks')
    positions, keys, result = set(), set(), []
    for row in selection:
        if type(row) is not dict or set(row) != {'position', 'object_key'}:
            raise ValueError('Invalid projected drone selection')
        position, key = row['position'], row['object_key']
        if (type(position) is not int or type(key) is not str or len(key) != 32
                or any(c not in '0123456789abcdef' for c in key)):
            raise ValueError('Invalid projected drone selection')
        if position in positions or key in keys:
            raise ValueError('Choose each projected drone stack once')
        drone = single.selected(fit, position, key)
        positions.add(position); keys.add(key)
        result.append((position, drone))
    return result


def proposal(engine, fit, operation, args):
    single.require_fit(engine, fit)
    chosen = selected(fit, args['selection'])
    spec = {}
    records.capture(fit, spec)
    rows = deepcopy(spec.get('projected_drones', []))
    if operation == 'set_projected_drones_active':
        active = args['active']
        if type(active) is not bool:
            raise ValueError('Choose an active state')
        for position, drone in chosen:
            row = rows[position]
            if active != (row['active'] > 0) and (not active or drone.canBeApplied(fit)):
                row['active'] = row['amount'] if active else 0
    elif operation == 'set_projected_drone_ranges':
        value = records.range_value(args['range_m'])
        for position, _ in chosen:
            rows[position]['range_m'] = value
    elif operation == 'remove_projected_drones':
        positions = {position for position, _ in chosen}
        rows = [row for position, row in enumerate(rows) if position not in positions]
    else:
        raise ValueError('Unknown selected projected drone operation')
    records.validate(rows)
    return rows


def apply_admitted(engine, fit, operation, args, rows):
    """Only after complete proposal admission; preserve captured source order."""
    import eos.db
    chosen = selected(fit, args['selection'])
    proposed = {row['name']: row for row in rows}
    for _, drone in chosen:
        if operation == 'remove_projected_drones':
            # Original full-stack calc removal zeroes the captured object first.
            drone.amount = 0
            fit.projectedDrones.remove(drone)
        elif operation == 'set_projected_drones_active':
            value = proposed[drone.item.name]['active']
            if drone.amountActive != value:
                drone.amountActive = value
        elif operation == 'set_projected_drone_ranges':
            value = proposed[drone.item.name]['range_m']
            if drone.projectionRange != value:
                drone.projectionRange = value
        else:
            raise ValueError('Unknown selected projected drone operation')
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    fitting._fill(fit)
