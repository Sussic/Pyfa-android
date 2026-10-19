"""Selected incoming squadrons: one proposal, admission and GUI boundary.

GPL-3.0-or-later, Pyfa contributors. Original selected fighter state/range/remove
and main-driven ability commands own ordering and missing-secondary semantics.
"""
from copy import deepcopy
from . import projected_fighter_editor as single, projected_fighter_records as records, fitting

OPERATIONS = {
    'set_projected_fighters_active': ('fit_id', 'selection', 'active'),
    'set_projected_fighter_ranges': ('fit_id', 'selection', 'range_m'),
    'remove_projected_fighters': ('fit_id', 'selection'),
    'toggle_projected_fighter_abilities': ('fit_id', 'main', 'selection', 'effect_id'),
}


def member(fit, value):
    if type(value) is not dict or set(value) != {'position', 'object_key'}:
        raise ValueError('Invalid projected fighter selection')
    position, key = value['position'], value['object_key']
    if (type(position) is not int or type(key) is not str or len(key) != 32
            or any(c not in '0123456789abcdef' for c in key)):
        raise ValueError('Invalid projected fighter selection')
    return position, single.selected(fit, position, key)


def selected(fit, selection):
    if type(selection) is not list or not 1 <= len(selection) <= records.LIMIT:
        raise ValueError('Choose one or more projected fighter squadrons')
    positions, keys, chosen = set(), set(), []
    for value in selection:
        position, fighter = member(fit, value)
        key = value['object_key']
        if position in positions or key in keys:
            raise ValueError('Choose each projected fighter squadron once')
        positions.add(position); keys.add(key); chosen.append((position, fighter))
    return chosen


def targets(fit, operation, args):
    chosen = selected(fit, args['selection'])
    if operation == 'toggle_projected_fighter_abilities':
        main_position, main = member(fit, args['main'])
        effect_id = args['effect_id']
        if type(effect_id) is not int or effect_id <= 0:
            raise ValueError('Choose an implemented main fighter ability')
        ability = next((a for a in main.abilities if a.effectID == effect_id), None)
        if ability is None or not ability.effect.isImplemented:
            raise ValueError('Choose an implemented main fighter ability')
        if main_position not in {position for position, _ in chosen}:
            chosen.append((main_position, main))
        if len(chosen) > records.LIMIT:
            raise ValueError('Too many selected projected fighter squadrons')
        return chosen, not ability.active
    return chosen, None


def proposal(engine, fit, operation, args):
    single.require_fit(engine, fit)
    chosen, direction = targets(fit, operation, args)
    spec = {}; records.capture(fit, spec)
    rows = deepcopy(spec.get('projected_fighters', []))
    if operation == 'set_projected_fighters_active':
        if type(args['active']) is not bool:
            raise ValueError('Choose an active state')
        for position, _ in chosen:
            rows[position]['active'] = args['active']
    elif operation == 'set_projected_fighter_ranges':
        value = records.range_value(args['range_m'])
        for position, _ in chosen:
            rows[position]['range_m'] = value
    elif operation == 'remove_projected_fighters':
        positions = {position for position, _ in chosen}
        rows = [row for position, row in enumerate(rows) if position not in positions]
    elif operation == 'toggle_projected_fighter_abilities':
        for position, _ in chosen:
            for ability in rows[position]['abilities']:
                if ability['effect_id'] == args['effect_id']:
                    ability['active'] = direction
    else:
        raise ValueError('Unknown selected projected fighter operation')
    records.validate(rows)
    return rows


def apply_admitted(engine, fit, operation, args, rows):
    """Apply only after joint admission; preserve original command target order."""
    import eos.db
    chosen, _ = targets(fit, operation, args)
    if operation == 'remove_projected_fighters':
        for _, fighter in sorted(chosen, key=lambda pair: pair[0], reverse=True):
            fit.projectedFighters.remove(fighter)
    else:
        for position, fighter in chosen:
            row = rows[position]
            if operation == 'set_projected_fighters_active':
                if fighter.active != row['active']: fighter.active = row['active']
            elif operation == 'set_projected_fighter_ranges':
                if fighter.projectionRange != row['range_m']: fighter.projectionRange = row['range_m']
            elif operation == 'toggle_projected_fighter_abilities':
                ability = next((a for a in fighter.abilities if a.effectID == args['effect_id']), None)
                if ability is not None:
                    value = next(a['active'] for a in row['abilities'] if a['effect_id'] == args['effect_id'])
                    if ability.active != value: ability.active = value
            else:
                raise ValueError('Unknown selected projected fighter operation')
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    fitting._fill(fit)
