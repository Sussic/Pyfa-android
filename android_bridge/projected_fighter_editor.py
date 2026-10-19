"""Source-policy proposals for independent incoming fighter squadrons.

The graph admits a complete proposal before applying one original GUI boundary.
No local hull/bay/tube rule or drone-style canBeApplied activation gate is added.
"""
from copy import deepcopy
from . import projected_fighter_records as records, fighter_records, fitting
from .inspection_identity import identity

OPERATIONS = {
    'add_projected_fighter': ('fit_id', 'item_id'),
    'set_projected_fighter_amount': ('fit_id', 'position', 'object_key', 'amount'),
    'set_projected_fighter_active': ('fit_id', 'position', 'object_key', 'active'),
    'toggle_projected_fighter_ability': ('fit_id', 'position', 'object_key', 'effect_id'),
    'set_projected_fighter_range': ('fit_id', 'position', 'object_key', 'range_m'),
    'change_projected_fighter_variation': ('fit_id', 'position', 'object_key', 'item_id'),
    'remove_projected_fighter': ('fit_id', 'position', 'object_key'),
}


def require_fit(engine, fit):
    engine._check_fit(fit)
    if fit.isStructure:
        raise ValueError('Individual projections are unavailable for structures')


def selected(fit, position, object_key=None):
    if type(position) is not int or not 0 <= position < len(fit.projectedFighters):
        raise ValueError('Choose a projected fighter squadron')
    fighter = fit.projectedFighters[position]
    if object_key is not None and (type(object_key) is not str or identity(fit, fighter) != object_key):
        raise ValueError('Projected fighter changed; reload its controls')
    if not records.eligible(fighter.item):
        raise ValueError('Unsupported projected fighter input')
    return fighter


def add_options(engine, fit, item_id):
    engine._check_fit(fit)
    item = fitting.item(engine, item_id)
    full = len(fit.projectedFighters) >= records.LIMIT
    enabled = records.eligible(item) and not fit.isStructure and not full
    reason = None if enabled else ('Individual projections are unavailable for structures' if fit.isStructure else
        'Projected fighter storage boundary reached' if full else 'This item cannot be projected')
    return dict(item_id=item.ID, is_fighter=item.category.name == 'Fighter',
                is_projectable=bool(item.isType('projected')), is_structure=fit.isStructure,
                enabled=enabled, unavailable_reason=reason)


def details(engine, fit):
    engine._check_fit(fit)
    rows = []
    for index, fighter in enumerate(fit.projectedFighters):
        editable = not fit.isStructure and records.eligible(fighter.item)
        rows.append(dict(index=index, object_key=identity(fit, fighter), item_id=fighter.itemID,
                         name=fighter.item.name, amount=fighter.amount, max_size=fighter.fighterSquadronMaxSize,
                         active=fighter.active, range_m=fighter.projectionRange, editable=editable,
                         unavailable_reason=None if editable else 'Unsupported projected fighter input'))
    return dict(is_structure=fit.isStructure, squadrons=rows)


def options(engine, fit, position):
    require_fit(engine, fit)
    fighter = selected(fit, position)
    from .variations import choices
    variations = choices(engine, fit, fighter.item, 'projected_fighter')
    abilities = [dict(effect_id=a.effectID, name=a.name, active=a.active)
                 for a in fighter.abilities if a.effect.isImplemented]
    if len(variations) > 8192 or len(abilities) > 128:
        raise ValueError('Too many projected fighter choices')
    return dict(index=position, object_key=identity(fit, fighter), item_id=fighter.itemID,
                abilities=abilities, variations=[{k: row[k] for k in ('id', 'name', 'enabled')} for row in variations])


def proposal(engine, fit, operation, args):
    require_fit(engine, fit)
    from eos.saveddata.fighter import Fighter
    spec = {}
    records.capture(fit, spec)
    rows = deepcopy(spec.get('projected_fighters', []))
    if operation == 'add_projected_fighter':
        if not add_options(engine, fit, args['item_id'])['enabled']:
            raise ValueError('Choose an eligible projected fighter')
        rows.append(records.row(Fighter(fitting.item(engine, args['item_id']))))
    else:
        fighter = selected(fit, args['position'], args['object_key'])
        position, row = args['position'], rows[args['position']]
        if operation == 'set_projected_fighter_amount':
            value = args['amount']
            if type(value) is not int or not 0 <= value <= 2**31 - 1:
                raise ValueError('Invalid projected fighter quantity')
            if value == 0: rows.pop(position)
            else: row['amount'] = min(value, fighter.fighterSquadronMaxSize)
        elif operation == 'remove_projected_fighter':
            rows.pop(position)
        elif operation == 'set_projected_fighter_active':
            if type(args['active']) is not bool:
                raise ValueError('Choose a fighter active state')
            row['active'] = args['active']
        elif operation == 'toggle_projected_fighter_ability':
            effect_id = args['effect_id']
            if type(effect_id) is not int:
                raise ValueError('Choose an implemented fighter ability')
            ability = next((a for a in fighter.abilities if a.effectID == effect_id and a.effect.isImplemented), None)
            if ability is None:
                raise ValueError('Choose an implemented fighter ability')
            next(a for a in row['abilities'] if a['effect_id'] == effect_id)['active'] = not ability.active
        elif operation == 'set_projected_fighter_range':
            row['range_m'] = records.range_value(args['range_m'])
        elif operation == 'change_projected_fighter_variation':
            item_id = args['item_id']
            if not any(v['id'] == item_id and v['enabled'] for v in options(engine, fit, position)['variations']):
                raise ValueError('Choose an enabled projected fighter variation')
            if fighter.itemID != item_id:
                replacement = Fighter(fitting.item(engine, item_id))
                replacement.amount, replacement.active = fighter.amount, fighter.active
                old = {a.effectID: a.active for a in fighter.abilities}
                for ability in replacement.abilities:
                    ability.active = old.get(ability.effectID, ability.active)
                rows.pop(position)
                rows.append(records.row(replacement))
        else:
            raise ValueError('Unknown projected fighter operation')
    records.validate(rows)
    return rows


def apply_admitted(engine, fit, operation, args, rows):
    """No effects before admission. Preserve object identity for in-place edits."""
    import eos.db
    from .inspection_identity import enable_projected_fighters
    if operation == 'add_projected_fighter':
        added = records.make(engine, rows[-1])
        fit.projectedFighters.append(added)
        if added not in fit.projectedFighters: raise ValueError('Projected fighter was refused')
    else:
        fighter = selected(fit, args['position'], args['object_key'])
        position = args['position']
        if operation == 'remove_projected_fighter' or (operation == 'set_projected_fighter_amount' and args['amount'] == 0):
            fit.projectedFighters.remove(fighter)
        elif operation == 'change_projected_fighter_variation':
            if fighter.itemID != args['item_id']:
                replacement = records.make(engine, rows[-1])
                fit.projectedFighters.remove(fighter)
                fit.projectedFighters.append(replacement)
                if replacement not in fit.projectedFighters: raise ValueError('Projected fighter was refused')
        elif operation == 'set_projected_fighter_amount':
            if fighter.amount != rows[position]['amount']: fighter.amount = rows[position]['amount']
        elif operation == 'set_projected_fighter_active':
            if fighter.active != rows[position]['active']: fighter.active = rows[position]['active']
        elif operation == 'set_projected_fighter_range':
            if fighter.projectionRange != rows[position]['range_m']: fighter.projectionRange = rows[position]['range_m']
        elif operation == 'toggle_projected_fighter_ability':
            effect = args['effect_id']
            ability = next(a for a in fighter.abilities if a.effectID == effect)
            ability.active = next(a['active'] for a in rows[position]['abilities'] if a['effect_id'] == effect)
        else:
            raise ValueError('Unknown projected fighter operation')
    enable_projected_fighters(fit)
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    fitting._fill(fit)
