"""Worker-owned booster inputs for fitted inspection and durable graph replay.

EOS owns booster validity, slots, side effects and all calculations. These
operations supply the C03 inspector's edit/history/restart prerequisite; C08
owns the user-facing addition editor.
"""


def validate_records(records):
    """Complete optional record representation; never infer missing effects."""
    if type(records) is not list or not records:
        raise ValueError('Saved booster records must be a nonempty list')
    slots = set()
    for row in records:
        if type(row) is not dict or set(row) != {'name', 'slot', 'active', 'side_effects'}:
            raise ValueError('Invalid saved booster fields')
        if type(row['name']) is not str or not row['name']:
            raise ValueError('Choose a known booster')
        if type(row['slot']) is not int or not 1 <= row['slot'] <= 2**31 - 1 or row['slot'] in slots:
            raise ValueError('Invalid or duplicate booster slot')
        slots.add(row['slot'])
        if type(row['active']) is not bool or type(row['side_effects']) is not list:
            raise ValueError('Invalid saved booster state')
        identities = []
        for effect in row['side_effects']:
            if type(effect) is not dict or set(effect) != {'effect_id', 'active'}:
                raise ValueError('Invalid saved booster side effect fields')
            if type(effect['effect_id']) is not int or not 1 <= effect['effect_id'] <= 2**31 - 1 or type(effect['active']) is not bool:
                raise ValueError('Invalid saved booster side effect state')
            identities.append(effect['effect_id'])
        if identities != sorted(set(identities)):
            raise ValueError('Duplicate or unordered booster side effects')


def capture(fit):
    return [dict(name=obj.item.name, slot=obj.slot, active=obj.active,
                 side_effects=[dict(effect_id=effect.effectID, active=effect.active)
                               for effect in sorted(obj.sideEffects, key=lambda effect: effect.effectID)])
            for obj in fit.boosters]


def restore(engine, fit, records):
    engine._check_fit(fit)
    validate_records(records)
    from eos.saveddata.booster import Booster
    prepared = []
    for row in records:
        obj = Booster(engine._item(row['name']))
        if obj.slot != row['slot']:
            raise ValueError('Saved booster slot differs from EOS')
        expected = {effect.effectID: effect for effect in obj.sideEffects}
        if set(expected) != {effect['effect_id'] for effect in row['side_effects']}:
            raise ValueError('Saved booster side effects differ from EOS')
        obj.active = row['active']
        for effect in row['side_effects']:
            expected[effect['effect_id']].active = effect['active']
        prepared.append(obj)
    occupied = {obj.slot for obj in fit.boosters}
    if occupied & {obj.slot for obj in prepared}:
        raise ValueError('Booster slot is occupied')
    for obj in prepared:
        fit.boosters.append(obj)
        if obj not in fit.boosters:
            raise ValueError('EOS rejected the restored booster')
    engine._recalculate(fit)


def change(engine, fit, operation, arguments):
    engine._check_fit(fit)
    if operation == 'add_booster':
        from .fitting import item
        from eos.saveddata.booster import Booster
        if type(arguments['active']) is not bool:
            raise ValueError('Booster active state must be boolean')
        obj = Booster(item(engine, arguments['item_id']))
        if any(existing.slot == obj.slot for existing in fit.boosters):
            raise ValueError('Booster slot is occupied')
        obj.active = arguments['active']
        fit.boosters.append(obj)
        if obj not in fit.boosters:
            raise ValueError('EOS rejected the booster')
    else:
        from .engine import _integer
        position = arguments['position']
        _integer(position, 0, 2**31 - 1)
        if position >= len(fit.boosters):
            raise ValueError('Booster was removed')
        obj = fit.boosters[position]
        if operation == 'remove_booster':
            fit.boosters.remove(obj)
        elif operation in ('set_booster_active', 'set_booster_side_effect'):
            if type(arguments['active']) is not bool:
                raise ValueError('Booster active state must be boolean')
            if operation == 'set_booster_active':
                obj.active = arguments['active']
            else:
                _integer(arguments['effect_id'], 1, 2**31 - 1)
                effect = next((effect for effect in obj.sideEffects if effect.effectID == arguments['effect_id']), None)
                if effect is None:
                    raise ValueError('Choose an original booster side effect')
                effect.active = arguments['active']
        else:
            raise ValueError('Unknown booster operation')
    # The transaction clears its complete affected graph before calculating
    # snapshots. Calculating here would advance a newly fitted booster past
    # EOS's original first-pass metadata before that boundary can observe it.
    fit.clear()
