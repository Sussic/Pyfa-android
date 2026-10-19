"""Optional ordered incoming drone stacks; no local bay or bandwidth policy.

Evaluation admission is separate from record validation: a valid quantity is not
permission to run that many projected effects. Callers must admit before EOS.
"""
from .projected_module_records import range_value

MAX_STACKS = 1024
MAX_AMOUNT = 2**31 - 1


def validate(rows):
    if type(rows) is not list or len(rows) > MAX_STACKS:
        raise ValueError('Too many projected drone stacks')
    names = set()
    for row in rows:
        if type(row) is not dict or set(row) != {'name', 'amount', 'active', 'range_m'}:
            raise ValueError('Invalid projected drone record')
        name = row['name']
        if type(name) is not str or not name or len(name) > 512 or name in names:
            raise ValueError('Projected drone names must be nonempty and unique')
        names.add(name)
        if type(row['amount']) is not int or not 1 <= row['amount'] <= MAX_AMOUNT:
            raise ValueError('Invalid projected drone quantity')
        if type(row['active']) is not int or not 0 <= row['active'] <= row['amount']:
            raise ValueError('Invalid active projected drone quantity')
        range_value(row['range_m'])


def eligible(item):
    return bool(item.isDrone and item.isType('projected') and not item.isAbyssal)


def setup(engine, fit, spec):
    from eos.saveddata.drone import Drone
    rows = spec.get('projected_drones', [])
    validate(rows)
    if rows and fit.isStructure:
        raise ValueError('Individual projections are unavailable for structures')
    if 'projected_drones' in spec:
        from .inspection_identity import enable_projected_drones
        enable_projected_drones(fit)
    seen = set()
    for row in rows:
        item = engine._item(row['name'])
        if not eligible(item) or item.ID in seen:
            raise ValueError('Choose distinct eligible projected drone types')
        seen.add(item.ID)
        drone = Drone(item)
        drone.amount, drone.amountActive = row['amount'], row['active']
        drone.projectionRange = range_value(row['range_m'])
        fit.projectedDrones.append(drone)
        if drone not in fit.projectedDrones:
            raise ValueError('Projected drone was refused')


def capture(fit, spec):
    from .inspection_identity import projected_drones_enabled
    rows, seen = [], set()
    for drone in fit.projectedDrones:
        if (not eligible(drone.item) or drone.isMutated or drone.charge is not None or
                drone.itemID in seen):
            raise ValueError('Unsupported or duplicate projected drone input')
        seen.add(drone.itemID)
        rows.append(dict(name=drone.item.name, amount=drone.amount,
                         active=drone.amountActive, range_m=range_value(drone.projectionRange)))
    validate(rows)
    if rows or 'projected_drones' in spec or projected_drones_enabled(fit):
        spec['projected_drones'] = rows


def refresh_order(fit):
    order = tuple(drone.ID for drone in fit.projectedDrones)
    if any(type(key) is not int or key <= 0 for key in order) or len(set(order)) != len(order):
        raise ValueError('Cannot preserve projected drone order across refresh')
    return order


def restore_refresh_order(fit, order):
    drones = fit.projectedDrones
    current = [drone.ID for drone in drones]
    if len(current) != len(order) or len(set(current)) != len(current) or set(current) != set(order):
        raise ValueError('Projected drone membership changed during refresh')
    ordinal = {key: index for index, key in enumerate(order)}
    list.sort(drones, key=lambda drone: ordinal[drone.ID])
