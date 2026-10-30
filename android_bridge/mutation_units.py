"""EOS-backed display units for sparse edits of existing exact mutation rolls.

The original raw query, action and stored representation remain authoritative.
No conversion formula or formatted value is used as a saved raw expectation.
"""
import math

from .mutation_records import attributes


_NONNUMERIC_UNITS = frozenset(('Sizeclass', 'Boolean', 'typeID', 'groupID', 'attributeID'))
_DIRECTION_OVERRIDES = {
    ('Stasis Web', 'speedFactor'): False,
    ('Damage Control', 'duration'): True,
    ('Siege Module', 'siegeLocalLogisticsDurationBonus'): False,
}


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _unavailable(reason):
    return dict(available=False, value=None, minimum=None, maximum=None,
                slider_base=None, unit_label=None, higher_is_better=None, reason=reason)


def _presentation(thing, mutator):
    from .mutation_editor import _bounds
    try:
        low, high = _bounds(mutator)
        value, base = mutator.value, mutator.baseValue
        if not _finite(value) or not _finite(base) or not low <= value <= high:
            return _unavailable('Mutation values or base are not finite and within EOS bounds'), None
        attribute = mutator.attribute
        info = getattr(attribute, 'info', attribute)
        unit_id = getattr(info, 'unitID', None)
        unit = getattr(attribute, 'unit', None)
        if unit is None:
            unit = getattr(info, 'unit', None)
        if unit_id is not None and (type(unit_id) is not int or unit_id < 0):
            return _unavailable('The EOS unit identity is invalid'), None
        if unit is None and unit_id is not None:
            return _unavailable('The declared EOS unit data is unavailable'), None
        # These original Unit overrides produce strings/bools or have no inverse.
        # Refuse before invoking ID callbacks, which may otherwise query the database.
        if unit is not None and unit.name in _NONNUMERIC_UNITS:
            return _unavailable('This EOS unit has no numeric converted editor'), None
        if unit is None:
            simplify = lambda number: number
            complicate = lambda number: number
            label = ''
        else:
            translation = unit.translations.get(unit.name)
            if translation is not None and not callable(translation[3]):
                return _unavailable('This EOS unit has no inverse numeric conversion'), None
            simplify, complicate = unit.SimplifyValue, unit.ComplicateValue
            if not callable(simplify) or not callable(complicate):
                return _unavailable('This EOS unit has no reversible numeric conversion'), None
            formatted = unit.PreformatValue(value)
            if not isinstance(formatted, tuple) or len(formatted) != 2:
                return _unavailable('The EOS unit label is unavailable'), None
            label = '' if formatted[1] is None else formatted[1]
            if type(label) is not str:
                return _unavailable('The EOS unit label is not text'), None
        raw_anchor = min(high, max(low, base))
        displayed = simplify(value)
        first, second = simplify(low), simplify(high)
        anchor = simplify(raw_anchor)
        if not all(_finite(number) for number in (displayed, first, second, anchor)):
            return _unavailable('The EOS unit does not provide finite numeric display values'), None
        minimum, maximum = min(first, second), max(first, second)
        if not minimum <= displayed <= maximum or not minimum <= anchor <= maximum:
            return _unavailable('The EOS display values do not preserve the mutation range'), None
        if low != high and first == second:
            return _unavailable('The EOS display range cannot distinguish its raw endpoints'), None
        # Prove this live unit accepts numeric display inputs without publishing any
        # round-tripped value. Omitted rolls always keep their original raw objects.
        if not all(_finite(complicate(number)) for number in (displayed, first, second, anchor)):
            return _unavailable('The EOS unit does not provide a finite numeric inverse'), None
        group = getattr(getattr(getattr(thing, 'item', None), 'group', None), 'name', None)
        direction = _DIRECTION_OVERRIDES.get((group, info.name), mutator.highIsGood)
        if type(direction) is not bool:
            return _unavailable('The mutation direction is unavailable'), None
        higher_is_better = direction if first <= second else not direction
        display = dict(available=True, value=displayed, minimum=minimum, maximum=maximum,
                       slider_base=anchor, unit_label=label,
                       higher_is_better=higher_is_better, reason=None)
        return display, (unit, low, high, first, second)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return _unavailable('The EOS unit conversion is unavailable or nonnumeric'), None


def display_metadata(thing, mutator):
    """Return the version-1 display object without altering a roll or its identity."""
    return _presentation(thing, mutator)[0]


def details(engine, fit):
    """Add display metadata to a fresh legacy raw-details result."""
    from .mutation_editor import details as raw_details
    result = raw_details(engine, fit)
    for row in result['items']:
        thing = (fit.modules if row['kind'] == 'module' else fit.drones)[row['position']]
        for attribute in row['attributes']:
            attribute['display'] = display_metadata(thing, thing.mutators[attribute['attribute_id']])
    return result


def validate_request(arguments):
    """Validate only declarative input; live identity/unit/range checks precede edits."""
    if (type(arguments) is not dict or
            not {'kind', 'position', 'object_key', 'edits'} <= arguments.keys() or
            arguments.keys() - {'fit_id', 'kind', 'position', 'object_key', 'edits'}):
        raise ValueError('Malformed mutation display edit')
    edits = arguments['edits']
    if type(edits) is not list or not edits:
        raise ValueError('Provide a nonempty ordered subset of mutation edits')
    rows = []
    for edit in edits:
        if type(edit) is not dict or set(edit) != {'attribute_id', 'value', 'representation'}:
            raise ValueError('Malformed mutation display attribute')
        if type(edit['representation']) is not str or edit['representation'] not in ('raw', 'display'):
            raise ValueError('Choose raw or display mutation values')
        rows.append(dict(attribute_id=edit['attribute_id'], value=edit['value']))
    attributes(rows)  # Finite exact numeric types; positive, unique, sorted IDs.
    from .mutation_editor import validate_request as validate_raw
    validate_raw(dict(kind=arguments['kind'], position=arguments['position'],
                      object_key=arguments['object_key'], attributes=rows))


def _display_to_raw(thing, mutator, value):
    display, conversion = _presentation(thing, mutator)
    if not display['available']:
        raise ValueError('Converted mutation editing is unavailable: ' + display['reason'])
    if not display['minimum'] <= value <= display['maximum']:
        raise ValueError('Displayed mutation value is outside its EOS range')
    unit, low, high, first, second = conversion
    try:
        raw = value if unit is None else unit.ComplicateValue(value)
    except (AttributeError, TypeError, ValueError, OverflowError, ZeroDivisionError) as error:
        raise ValueError('The live EOS unit could not convert this mutation value') from error
    if not _finite(raw):
        raise ValueError('The live EOS unit returned a nonfinite or nonnumeric raw value')
    # EOS Simplify/Complicate can introduce binary rounding at exact boundaries.
    # The query's exact endpoint maps back to its original EOS endpoint, never
    # to a recomputed approximation just outside the permissible raw range.
    if value == first:
        return low
    if value == second:
        return high
    if value == display['value']:
        return mutator.value
    return raw


def _exact(value):
    return (type(value), value.hex() if type(value) is float else value)


def change(engine, fit, arguments):
    """Resolve every sparse edit before the existing complete-set atomic edit path."""
    from . import mutation_editor
    from .inspection_identity import identity
    engine._check_fit(fit)
    validate_request(arguments)
    kind, position = arguments['kind'], arguments['position']
    values = fit.modules if kind == 'module' else fit.drones
    if position >= len(values):
        raise ValueError('Mutation item was removed')
    thing = values[position]
    if not thing.isMutated or identity(fit, thing) != arguments['object_key']:
        raise ValueError('Mutation item changed; reload its exact values')
    mutators = thing.mutators
    requested = {edit['attribute_id']: edit for edit in arguments['edits']}
    if requested.keys() - mutators.keys():
        raise ValueError('A requested mutation attribute no longer exists')
    complete = []
    untouched = {}
    for attribute_id, mutator in sorted(mutators.items()):
        raw = mutator.value
        edit = requested.get(attribute_id)
        if edit is None:
            untouched[attribute_id] = _exact(raw)
        elif edit['representation'] == 'raw':
            raw = edit['value']
        else:
            raw = _display_to_raw(thing, mutator, edit['value'])
        low, high = mutation_editor._bounds(mutator)
        if not _finite(raw) or not low <= raw <= high:
            raise ValueError('Rolled value is outside its EOS range')
        complete.append(dict(attribute_id=attribute_id, value=raw))
    attributes(complete)
    prepared = {key: value for key, value in arguments.items() if key != 'edits'}
    prepared['attributes'] = complete
    result = mutation_editor.change(engine, fit, prepared)
    if any(_exact(mutators[key].value) != original for key, original in untouched.items()):
        # BridgeSession owns recovery: never publish an edit which silently
        # reformats or retypes an omitted raw roll during EOS reconstruction.
        raise ValueError('An untouched exact mutation roll changed representation')
    return result
