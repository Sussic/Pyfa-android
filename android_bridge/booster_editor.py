"""C08 local booster commands, adapted from pinned Pyfa source.

GPL-3.0-or-later; original Pyfa contributors, see LICENSE.
Sources: calc/booster, gui/booster/changeMeta, BoosterInfo and itemVariationChange.
Each mutation runs inside the existing durable graph transaction.
"""
import math

OPERATIONS = frozenset(('fit_booster', 'toggle_boosters', 'remove_boosters', 'change_booster_variation'))


def choices(engine, fit, item):
    from .market_policy import MarketPolicy
    engine._check_fit(fit)
    policy = MarketPolicy()
    family = policy.getVariationsByItems((item,))
    if len(family) < 2:
        return []
    values = [v for v in family if policy.getMetaGroupIdByItem(v) != 15]
    values.sort(key=lambda v: v.name)
    if len(family) <= 7:
        values.sort(key=lambda v: v.attributes['boosterEffectChance1'].value if 'boosterEffectChance1' in v.attributes else 0)
    return [dict(id=v.ID, name=v.name, enabled=fit.canFit(v)) for v in values]


def positions(fit, values, allow_empty=False):
    if (type(values) is not list or (not values and not allow_empty) or len(values) > 1024
            or any(type(p) is not int or not 0 <= p < len(fit.boosters) for p in values)
            or len(set(values)) != len(values)):
        raise ValueError('Choose valid distinct boosters')
    return list(values)


def change(engine, fit, operation, args):
    engine._check_fit(fit)
    used = []
    if fit.isStructure:
        raise ValueError('Structures do not support the booster editor')
    if operation in ('fit_booster', 'change_booster_variation'):
        from .fitting import item
        from eos.saveddata.booster import Booster
        value = item(engine, args['item_id'])
        if not value.isBooster:
            raise ValueError('Choose a booster')
        if any(b.itemID == value.ID for b in fit.boosters):
            raise ValueError('This booster is already fitted')
        new = Booster(value)
        if operation == 'change_booster_variation':
            old = fit.boosters[positions(fit, [args['position']])[0]]
            if not any(v['id'] == value.ID and v['enabled'] for v in choices(engine, fit, old.item)):
                raise ValueError('Choose an enabled booster variation')
            new.active = old.active
            states = {e.effectID: e.active for e in old.sideEffects}
            for effect in new.sideEffects:
                effect.active = states.get(effect.effectID, effect.active)
        # Original makeRoom imports desktop BoosterInfo. Keep its mutation only;
        # ordinary durable history already captures the complete replaced row.
        occupied = next((b for b in fit.boosters if b.slot == new.slot), None)
        if occupied is not None:
            occupied.itemID = 0  # Original ORM removal workaround, GH #324.
            fit.boosters.remove(occupied)
        fit.boosters.append(new)
        if new not in fit.boosters:
            raise ValueError('EOS rejected the booster')
        if operation == 'fit_booster':
            used.append(value.ID)
    elif operation == 'remove_boosters':
        for p in sorted(positions(fit, args['positions']), reverse=True):
            used.append(fit.boosters[p].itemID)
            fit.boosters.remove(fit.boosters[p])
    elif operation == 'toggle_boosters':
        ps = positions(fit, args['positions'], True)
        main = positions(fit, [args['main_position']])[0]
        if main not in ps:
            ps.append(main)
        active = not fit.boosters[main].active
        for p in ps:
            fit.boosters[p].active = active
    else:
        raise ValueError('Unknown booster edit')
    # Original GUI order matters: calculate subsystem-added slots before fill.
    # The transaction subsequently recalculates the complete affected graph.
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    from .fitting import _fill
    _fill(fit)
    return used


def details(engine, fit):
    from .inspection_identity import identity
    from .number_format import formatAmount
    engine._check_fit(fit)
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    rows = []
    for index, obj in enumerate(fit.boosters):
        duration = obj.getModifiedItemAttr('boosterDuration')
        if duration is not None and (type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0):
            raise ValueError('Invalid booster duration')
        rows.append(dict(index=index, object_key=identity(fit, obj), item_id=obj.itemID,
                         name=obj.item.name, slot=obj.slot, active=obj.active,
                         duration_ms=duration,
                         duration_text=None if duration is None else formatAmount(duration / 1000 / 60, 3, 0, 3) + ' min',
                         side_effects=[dict(effect_id=e.effectID, name=e.name, active=e.active)
                                       for e in obj.sideEffects if e.effect.isImplemented],
                         variations=choices(engine, fit, obj.item)))
    return dict(is_structure=fit.isStructure, boosters=rows)


def add_options(engine, fit, item_id):
    from .fitting import item
    from .inspection_identity import identity
    from eos.saveddata.booster import Booster
    engine._check_fit(fit)
    value = item(engine, item_id)
    slot = Booster(value).slot if value.isBooster else None
    occupant = next(((i, b) for i, b in enumerate(fit.boosters) if b.slot == slot), None)
    return dict(item_id=value.ID, is_booster=value.isBooster, is_structure=fit.isStructure,
                slot=slot, occupant=None if occupant is None else dict(index=occupant[0],
                object_key=identity(fit, occupant[1]), item_id=occupant[1].itemID, name=occupant[1].item.name),
                already_fitted=any(b.itemID == value.ID for b in fit.boosters))
