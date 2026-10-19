"""Read-only local fighter selection adapted from getSimilarFighters.

GPL-3.0-or-later; Pyfa contributors, see LICENSE. Source Market.getGroupByItem
returns item.group for fighters: its pinned forced-group overrides are ships.
Selection uses every ability ID, not only abilities implemented/displayed by UI.
"""


def similar(fighters, main):
    group = getattr(main.item.group, 'ID', None)
    abilities = {ability.effectID for ability in main.abilities}
    result = []
    for fighter in fighters:
        if fighter is main:
            result.append(fighter)
            continue
        if fighter.itemID is None:
            continue
        if fighter.itemID == main.itemID:
            result.append(fighter)
            continue
        candidate_group = getattr(fighter.item.group, 'ID', None)
        candidate_abilities = {ability.effectID for ability in fighter.abilities}
        if candidate_group is not None and candidate_group == group and candidate_abilities and candidate_abilities == abilities:
            result.append(fighter)
    return result


def selection(engine, fit, position):
    engine._check_fit(fit)
    if type(position) is not int or not 0 <= position < len(fit.fighters):
        raise ValueError('Choose a current fighter squadron')
    main = fit.fighters[position]
    matches = similar(fit.fighters, main)
    if len(matches) > 1024:
        raise ValueError('Select at most 1024 squadrons per edit')
    from .inspection_identity import identity
    def row(index, fighter):
        return dict(index=index, object_key=identity(fit, fighter), item_id=fighter.itemID)
    matched = {id(fighter) for fighter in matches}
    return dict(main=row(position, main), matches=[row(index, fighter)
                for index, fighter in enumerate(fit.fighters) if id(fighter) in matched])
