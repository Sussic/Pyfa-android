"""Ordered independent incoming squadrons, with complete ability states.

Duplicate item types are distinct objects. Incoming squadrons do not consume the
recipient's local fighter bay or tubes. Evaluation admission is separate.
"""
from .projected_module_records import range_value
from . import fighter_records

LIMIT = 1024


def eligible(item):
    return bool(item is not None and item.category.name == 'Fighter' and item.isType('projected'))


def validate(rows):
    if type(rows) is not list or len(rows) > LIMIT:
        raise ValueError('Too many projected fighter squadrons')
    for row in rows:
        if type(row) is not dict or set(row) != {'name', 'amount', 'active', 'range_m', 'abilities'}:
            raise ValueError('Invalid projected fighter fields')
        fighter_records.validate({k: row[k] for k in ('name', 'amount', 'active', 'abilities')})
        if len(row['name']) > 512:
            raise ValueError('Invalid projected fighter name')
        range_value(row['range_m'])


def row(fighter):
    return dict(name=fighter.item.name, amount=fighter.amount, active=fighter.active,
                range_m=range_value(fighter.projectionRange), abilities=fighter_records.states(fighter))


def make(engine, value):
    from eos.saveddata.fighter import Fighter
    validate([value])
    item = engine._item(value['name'])
    if not eligible(item):
        raise ValueError('Choose an eligible projected fighter')
    fighter = Fighter(item)
    if value['amount'] > fighter.fighterSquadronMaxSize:
        raise ValueError('Projected fighter quantity exceeds its squadron size')
    fighter.amount = value['amount']
    fighter.active = value['active']
    fighter.projectionRange = range_value(value['range_m'])
    fighter_records.restore_states(fighter, value)
    return fighter


def setup(engine, fit, spec):
    rows = spec.get('projected_fighters', [])
    validate(rows)
    if rows and fit.isStructure:
        raise ValueError('Individual projections are unavailable for structures')
    if 'projected_fighters' in spec:
        from .inspection_identity import enable_projected_fighters
        enable_projected_fighters(fit)
    for value in rows:
        fighter = make(engine, value)
        fit.projectedFighters.append(fighter)
        if fighter not in fit.projectedFighters:
            raise ValueError('Projected fighter was refused')


def capture(fit, spec):
    from .inspection_identity import projected_fighters_enabled
    rows = []
    for fighter in fit.projectedFighters:
        if not eligible(fighter.item):
            raise ValueError('Unsupported projected fighter input')
        rows.append(row(fighter))
    validate(rows)
    if rows or 'projected_fighters' in spec or projected_fighters_enabled(fit):
        spec['projected_fighters'] = rows


def refresh_order(fit):
    order = tuple(fighter.groupID for fighter in fit.projectedFighters)
    if any(type(key) is not int or key <= 0 for key in order) or len(set(order)) != len(order):
        raise ValueError('Cannot preserve projected fighter order across refresh')
    return order


def restore_refresh_order(fit, order):
    fighters = fit.projectedFighters
    current = [fighter.groupID for fighter in fighters]
    if len(current) != len(order) or len(set(current)) != len(current) or set(current) != set(order):
        raise ValueError('Projected fighter membership changed during refresh')
    ordinal = {key: index for index, key in enumerate(order)}
    list.sort(fighters, key=lambda fighter: ordinal[fighter.groupID])
