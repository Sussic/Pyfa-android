"""Projected single-stack proposals and source-policy application.

GPL-3.0-or-later, Pyfa contributors. Derived from calc/drone/projected* and
GUI projectedDrone commands. Graph ownership supplies admission and commits.
"""
from copy import deepcopy
from . import fitting, projected_drone_records as records
from .inspection_identity import identity

OPERATIONS = {
    'add_projected_drone': ('fit_id', 'item_id'),
    'set_projected_drone_amount': ('fit_id', 'position', 'object_key', 'amount'),
    'set_projected_drone_active': ('fit_id', 'position', 'object_key', 'active'),
    'set_projected_drone_range': ('fit_id', 'position', 'object_key', 'range_m'),
    'change_projected_drone_variation': ('fit_id', 'position', 'object_key', 'item_id'),
    'remove_projected_drone': ('fit_id', 'position', 'object_key', 'amount'),
}


def require_fit(engine, fit):
    engine._check_fit(fit)
    if fit.isStructure:
        raise ValueError('Individual projections are unavailable for structures')


def selected(fit, position, object_key=None):
    if type(position) is not int or not 0 <= position < len(fit.projectedDrones):
        raise ValueError('Choose a projected drone stack')
    drone = fit.projectedDrones[position]
    if object_key is not None and (type(object_key) is not str or identity(fit, drone) != object_key):
        raise ValueError('Projected drone changed; reload its controls')
    if not records.eligible(drone.item) or drone.isMutated or drone.charge is not None:
        raise ValueError('Unsupported projected drone input')
    return drone


def add_options(engine, fit, item_id):
    engine._check_fit(fit)
    item = fitting.item(engine, item_id)
    existing = next((d for d in fit.projectedDrones if d.itemID == item.ID), None)
    full = ((existing is None and len(fit.projectedDrones) >= records.MAX_STACKS) or
            (existing is not None and existing.amount >= records.MAX_AMOUNT))
    enabled = records.eligible(item) and not fit.isStructure and not full
    reason = None if enabled else ('Individual projections are unavailable for structures' if fit.isStructure else
        'Projected drone storage boundary reached' if full else 'This item cannot be projected')
    return dict(item_id=item.ID, is_drone=bool(item.isDrone), is_projectable=bool(item.isType('projected')),
                is_structure=fit.isStructure, enabled=enabled, unavailable_reason=reason)


def details(engine, fit):
    engine._check_fit(fit)
    rows = []
    for index, drone in enumerate(fit.projectedDrones):
        editable = not fit.isStructure and records.eligible(drone.item) and not drone.isMutated and drone.charge is None
        rows.append(dict(index=index, object_key=identity(fit, drone), item_id=drone.itemID,
                         name=drone.item.name, amount=drone.amount, active=drone.amountActive,
                         range_m=drone.projectionRange, editable=editable,
                         unavailable_reason=None if editable else 'Unsupported projected drone input'))
    return dict(is_structure=fit.isStructure, stacks=rows)


def options(engine, fit, position):
    require_fit(engine, fit)
    drone = selected(fit, position)
    from .variations import choices
    variations = choices(engine, fit, drone.item, 'projected_drone')
    if len(variations) > 8192:
        raise ValueError('Too many projected drone variations')
    allowed = bool(drone.canBeApplied(fit))
    return dict(index=position, object_key=identity(fit, drone), item_id=drone.itemID,
                activation_allowed=allowed,
                activation_unavailable_reason=None if allowed else 'This drone cannot be applied to this recipient',
                variations=[{k: row[k] for k in ('id', 'name', 'enabled')} for row in variations])


def proposal(engine, fit, operation, args):
    """No effects or live edits: caller must admit these complete proposed rows."""
    require_fit(engine, fit)
    spec = {}
    records.capture(fit, spec)
    rows = deepcopy(spec.get('projected_drones', []))
    if operation == 'add_projected_drone':
        if not add_options(engine, fit, args['item_id'])['enabled']:
            raise ValueError('Choose an eligible projected drone')
        item = fitting.item(engine, args['item_id'])
        index = next((i for i, d in enumerate(fit.projectedDrones) if d.itemID == item.ID), None)
        if index is None:
            rows.append(dict(name=item.name, amount=1, active=1, range_m=None))
        else:
            row = rows[index]
            row['amount'] += 1
            if row['active'] > 0: row['active'] += 1
    else:
        drone = selected(fit, args['position'], args['object_key'])
        index, row = args['position'], rows[args['position']]
        if operation == 'set_projected_drone_amount':
            value = args['amount']
            if type(value) is not int or not 0 <= value <= records.MAX_AMOUNT:
                raise ValueError('Invalid projected drone quantity')
            if value == 0:
                rows.pop(index)
            else:
                old = row['amount']; row['amount'] = value
                if row['active'] > 0: row['active'] = max(min(row['active'] + value - old, value), 0)
        elif operation == 'remove_projected_drone':
            value = args['amount']
            if type(value) is not int or not 1 <= value <= records.MAX_AMOUNT:
                raise ValueError('Choose a positive removal quantity')
            row['amount'] = max(row['amount'] - value, 0)
            row['active'] = min(row['active'], row['amount'])
            if row['amount'] == 0: rows.pop(index)
        elif operation == 'set_projected_drone_active':
            value = args['active']
            if type(value) is not bool: raise ValueError('Choose an active state')
            if value != (row['active'] > 0):
                if not value or drone.canBeApplied(fit):
                    row['active'] = row['amount'] if value else 0
                # Denied activation is the original false/no-change calc result;
                # its GUI wrapper still performs flush/recalc/fill.
        elif operation == 'set_projected_drone_range':
            row['range_m'] = records.range_value(args['range_m'])
        elif operation == 'change_projected_drone_variation':
            item_id = args['item_id']
            if not any(v['id'] == item_id and v['enabled'] for v in options(engine, fit, index)['variations']):
                raise ValueError('Choose an enabled projected drone variation')
            if drone.itemID != item_id:
                item = fitting.item(engine, item_id)
                rows.pop(index)
                destination = next((r for r in rows if r['name'] == item.name), None)
                if destination is None:
                    rows.append(dict(name=item.name, amount=row['amount'], active=row['active'], range_m=None))
                else:
                    destination['amount'] += row['amount']
                    if destination['active'] > 0: destination['active'] += row['amount']
        else:
            raise ValueError('Unknown projected drone operation')
    records.validate(rows)
    return rows


def apply_admitted(engine, fit, rows):
    """Apply an already-admitted proposal with exact source flush/recalc/fill."""
    from eos.saveddata.drone import Drone
    from .inspection_identity import enable_projected_drones
    import eos.db
    old = {drone.item.name: drone for drone in fit.projectedDrones}
    names = {row['name'] for row in rows}
    for drone in list(fit.projectedDrones):
        if drone.item.name not in names: fit.projectedDrones.remove(drone)
    for row in rows:
        drone = old.get(row['name'])
        if drone is None:
            drone = Drone(engine._item(row['name']))
            drone.amount, drone.amountActive = row['amount'], row['active']
            fit.projectedDrones.append(drone)
            if drone not in fit.projectedDrones: raise ValueError('Projected drone was refused')
        else:
            drone.amount, drone.amountActive = row['amount'], row['active']
        drone.projectionRange = row['range_m']
    enable_projected_drones(fit)
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    fitting._fill(fit)
