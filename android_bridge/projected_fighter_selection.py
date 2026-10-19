"""Bounded metadata-only incoming selection using the original fighter predicate."""
from .fighter_selection import similar
from .projected_fighter_editor import require_fit, selected
from .projected_fighter_records import LIMIT, eligible
from .inspection_identity import identity


def selection(engine, fit, position):
    require_fit(engine, fit)
    fighters = fit.projectedFighters
    # Bound the entire scan before deriving membership; an output cap alone
    # would not bound work for a container whose rows rarely match.
    if len(fighters) > LIMIT:
        raise ValueError('Select at most 1024 squadrons per edit')
    main = selected(fit, position)
    for fighter in fighters:
        if not eligible(fighter.item) or len(fighter.abilities) > 128:
            raise ValueError('Unsupported projected fighter selection input')
    matches = {id(fighter) for fighter in similar(fighters, main)}
    def row(index, fighter):
        return dict(index=index, object_key=identity(fit, fighter), item_id=fighter.itemID)
    return dict(main=row(position, main), matches=[row(index, fighter)
                for index, fighter in enumerate(fighters) if id(fighter) in matches])
