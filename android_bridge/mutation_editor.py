"""Exact numeric edits of existing local mutations, inside BridgeSession commits.

Conversion, randomization and slider/unit conversion remain separate C10 work.
No module/drone is replaced; stack counts, states, charges and identities stay.
"""
from .mutation_records import attributes


def validate_request(arguments):
    if arguments['kind'] not in ('module', 'drone'):
        raise ValueError('Choose a local module or drone stack')
    position = arguments['position']
    if type(position) is not int or not 0 <= position <= 2**31 - 1:
        raise ValueError('Choose a current item position')
    key = arguments['object_key']
    if (type(key) is not str or len(key) != 32 or
            any(c not in '0123456789abcdef' for c in key)):
        raise ValueError('Invalid mutation item identity')
    attributes(arguments['attributes'])


def _bounds(mutator):
    endpoints = [mutator.minValue, mutator.maxValue]
    # Use EOS endpoints, sorting because negative-base attributes invert them.
    attributes([dict(attribute_id=1, value=value) for value in endpoints[:1]])
    attributes([dict(attribute_id=1, value=value) for value in endpoints[1:]])
    return min(endpoints), max(endpoints)


def _row(fit, thing, kind, position):
    from .inspection_identity import identity
    from .mutation_records import capture
    saved = capture(thing)['mutation']
    rolls = []
    for roll in saved['attributes']:
        mutator = thing.mutators[roll['attribute_id']]
        low, high = _bounds(mutator)
        if not low <= roll['value'] <= high:
            raise ValueError('Current roll is outside the dataset bounds')
        attribute = mutator.attribute
        # Fresh mutators retain Attribute; ORM reconstruction retains AttributeInfo.
        info = getattr(attribute, 'info', attribute)
        unit_id = getattr(info, 'unitID', None)
        if unit_id is not None and (type(unit_id) is not int or unit_id < 0):
            raise ValueError('Invalid mutation unit identity')
        high_is_good = mutator.highIsGood
        if type(high_is_good) is not bool:
            raise ValueError('Mutation direction is unavailable')
        rolls.append(dict(roll, label=getattr(info, 'displayName', None) or info.name,
            unit_id=unit_id, minimum=low, maximum=high, high_is_good=high_is_good))
    return dict(kind=kind, position=position, object_key=identity(fit, thing),
        name=thing.fullName, base_item_id=saved['base_item_id'],
        mutaplasmid_id=saved['mutaplasmid_id'], attributes=rolls)


def details(engine, fit):
    engine._check_fit(fit)
    return dict(items=[_row(fit, thing, kind, position)
        for kind, values in (('module', fit.modules), ('drone', fit.drones))
        for position, thing in enumerate(values) if thing.isMutated])


def change(engine, fit, arguments):
    engine._check_fit(fit)
    validate_request(arguments)
    kind, position = arguments['kind'], arguments['position']
    values = fit.modules if kind == 'module' else fit.drones
    if position >= len(values):
        raise ValueError('Mutation item was removed')
    thing = values[position]
    from .inspection_identity import identity
    if identity(fit, thing) != arguments['object_key'] or not thing.isMutated:
        raise ValueError('Mutation item changed; reload its exact values')
    rolls = arguments['attributes']
    if [row['attribute_id'] for row in rolls] != sorted(thing.mutators):
        raise ValueError('Provide the complete current roll set')
    # Prevalidate every row before touching EOS: one bad field changes nothing.
    for row in rolls:
        low, high = _bounds(thing.mutators[row['attribute_id']])
        if not low <= row['value'] <= high:
            raise ValueError('Rolled value is outside its EOS range')
    if all(thing.mutators[r['attribute_id']].value == r['value'] for r in rolls):
        return []
    for row in rolls:
        mutator = thing.mutators[row['attribute_id']]
        mutator.value = row['value']
        if mutator.value != row['value']:
            raise ValueError('EOS would change the requested exact roll')
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    from .fitting import _fill
    _fill(fit)
    return []  # An edit does not promote a recently-used market item.
