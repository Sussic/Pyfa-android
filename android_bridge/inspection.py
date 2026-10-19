"""Worker-owned C03.2 inspection of original EOS objects.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Attribute ordering/visibility/formatting follows pinned itemAttributes.py and
attributeGrouping.py. EOS owns effective base, modified values and units.
"""
import math
import re
from collections.abc import Mapping
from enum import Enum
from types import SimpleNamespace

from .inspection_groups import (AttrGroupDict, AttrGroups, CategoryGroups,
                                GroupedAttributes, GuiAttrGroup, RequiredSkillAttrs)
from .number_format import formatAmount


def _number(value):
    value = getattr(value, 'value', value)
    if type(value) not in (bool, int, float) or not math.isfinite(value):
        raise ValueError('Inspection attribute must be a finite EOS number or boolean')
    return value


def _formatted(value, info):
    if info is not None and info.unit is not None:
        transformed, unit = info.unit.PreformatValue(value)
        text = formatAmount(transformed, 3, 0, 0) if isinstance(transformed, (int, float)) else transformed
        return str(text) + (f' {unit}' if unit is not None else '')
    return formatAmount(value, 3, 0, 0)


def attributes(stuff, item, charge=False):
    """Complete raw rows plus separate original normal/raw group orders."""
    values = item.attributes if stuff is None else (
        stuff.chargeModifiedAttributes if charge else stuff.itemModifiedAttributes)
    rows = {}
    for name in values:
        info = item.attributes.get(name)
        current = _number(values[name])
        base = getattr(info, 'value', None)
        if stuff is not None:
            getter = stuff.getChargeBaseAttrValue if charge else stuff.getItemBaseAttrValue
            base = getter(name, base)
        base = current if base is None else _number(base)
        normal = not ((name not in GroupedAttributes and not (current or base)) or
                      info is None or not info.published or name in RequiredSkillAttrs)
        unit = info.unit if info is not None else None
        rows[name] = dict(name=name, id=None if info is None else info.ID,
                          label=info.displayName if info is not None and info.displayName else name,
                          metadata=info is not None, published=bool(info is not None and info.published),
                          current=current, base=base, raw_current=str(current), raw_base=str(base),
                          display_current=_formatted(current, info) if normal else None,
                          display_base=_formatted(base, info) if normal else None,
                          normal=bool(normal), unit=None if unit is None else dict(
                              id=unit.ID, name=unit.name, display=unit.displayName))

    def ordered(raw):
        seen, result = set(), []

        def add(name, path, override=None):
            if name in rows and name not in seen and (raw or rows[name]['normal']):
                result.append(dict(name=name, groups=path, label=name if raw else override or rows[name]['label']))
                seen.add(name)

        def group(name, path):
            if isinstance(name, tuple):
                add(name[0], path, name[1])
            elif name in GroupedAttributes:
                members, heading = next(entry for entry in AttrGroups if name in entry[0])
                for member in members:
                    add(member, path + [heading])
            else:
                add(name, path)

        order = CategoryGroups.get(item.category.name, [GuiAttrGroup.FITTING, GuiAttrGroup.SHIP_GROUP])
        for key in order:
            definition = AttrGroupDict[key]
            for name in definition['attributes']:
                group(name, [definition['label']])
        for name in sorted(rows):
            group(name, [])
        expected = set(rows) if raw else {name for name, row in rows.items() if row['normal']}
        if seen != expected:
            raise ValueError('Incomplete inspector grouping')
        return result

    return dict(rows=[rows[name] for name in sorted(rows)], normal=ordered(False), raw=ordered(True))


def effects(item):
    result = []
    for name in sorted(item.effects):
        effect = item.effects[name]
        implemented = bool(effect.isImplemented)
        result.append(dict(id=effect.ID, name=effect.name, implemented=implemented,
                           active=bool(effect.activeByDefault) if implemented else None,
                           types=list(effect.type or ()), runtime=effect.runTime if implemented else None,
                           published=bool(effect.published), description=effect.description))
    return result


def affectors(stuff, item, charge=False, source_resolver=None):
    if stuff is None:
        return []
    values = stuff.chargeModifiedAttributes if charge else stuff.itemModifiedAttributes
    result = []
    for name in sorted(values.iterAfflictions()):
        changed = values[name] != values.getOriginal(name, 0)
        for source_fit, entries in values.getAfflictions(name).items():
            for source, operator, stacking, before, after, used in entries:
                source_item = getattr(source, 'item', None)
                if source is stuff and getattr(source, 'charge', None) is not None:
                    source_item = source.charge
                source_key, source_target = (source_resolver(source_fit, source, source_item) if source_resolver is not None
                                            else (None, _source_target(source_fit, source, source_item)))
                result.append(dict(attribute=name, changed=bool(changed), used=bool(used),
                    source_type=type(source).__name__, source_id=getattr(source, 'ID', None),
                    source_fit_id=source_fit.ID, source_fit_name=source_fit.name,
                    source_ship_id=source_fit.ship.item.ID,
                    item_id=None if source_item is None else source_item.ID,
                    item_name=None if source_item is None else source_item.name,
                    source_fit_key=source_key, source_target=source_target,
                    projected=bool(getattr(source, 'projected', False)), operator=operator.name,
                    stacking=None if stacking is None else _property_value(stacking),
                    before=_number(before), after=_number(after)))
    return result


def _source_target(fit, source, item):
    if item is None:
        return None
    if source is fit.ship:
        return dict(context='ship', index=0, item_id=item.ID)
    if source is fit.mode:
        return dict(context='mode', index=0, item_id=item.ID)
    for context, things in (('module', fit.modules), ('drone', fit.drones), ('fighter', fit.fighters),
                           ('implant', fit.implants), ('booster', fit.boosters)):
        for index, candidate in enumerate(things):
            if candidate is source:
                is_charge = context == 'module' and candidate.charge is not None and candidate.charge == item
                return dict(context='charge' if is_charge else context, index=index, item_id=item.ID)
    return None


def _property_value(value, depth=0):
    """Stable values/identities, never an object's process-dependent repr."""
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if math.isinf(value):
            return dict(number_kind='positive_infinity' if value > 0 else 'negative_infinity')
        return _number(value)
    if isinstance(value, Enum):
        return dict(enum=type(value).__name__, name=value.name, value=value.value)
    if depth >= 4:
        raise ValueError('Nested property requires object inspection')
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError('Property mapping has non-string keys')
        return {key: _property_value(value[key], depth+1) for key in sorted(value)}
    if isinstance(value, tuple) and hasattr(value, '_fields'):
        return {name: _property_value(getattr(value, name), depth+1) for name in value._fields}
    if isinstance(value, (list, tuple)):
        return [_property_value(entry, depth+1) for entry in value]
    if type(value).__module__.startswith('eos.') and hasattr(value, 'ID'):
        identity = value.ID
        if type(identity) is int:
            return dict(object_type=type(value).__name__, id=identity,
                        name=getattr(value, 'name', None))
    raise ValueError('Object property is not a supported value or identity')


def properties(stuff, item):
    owner = item if stuff is None else stuff
    rows = []
    for name in sorted(dir(owner), key=lambda value: (value.title(), value)):
        if name.startswith('__') and name.endswith('__'):
            continue
        # SQLAlchemy embeds id(association_proxy) in its private cache key.
        # Keep the diagnostic member but never publish a process address as
        # an apparently stable property name.
        stable_name = re.sub(r'^(_AssociationProxy_.+)_\d+_inst$', r'\1_inst', name)
        row = dict(name=stable_name, label=stable_name.title(), available=False, value=None, reason=None, display=None)
        if name.startswith('_'):
            row['reason'] = 'Private diagnostic member'
        else:
            try:
                value = getattr(owner, name)
                if callable(value):
                    row['reason'] = 'Callable diagnostic member'
                else:
                    row['value'] = _property_value(value)
                    row['available'] = True
                    if value is None or type(value) in (bool, int, float, str):
                        row['display'] = str(value)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as error:
                row['reason'] = f'Unavailable property ({type(error).__name__})'
        rows.append(row)
    rows.sort(key=lambda row: (row['label'], row['name']))
    if len({row['name'] for row in rows}) != len(rows):
        raise ValueError('Ambiguous normalized property names')
    return rows


def equipment(stuff, fit, effective=False):
    from .inspection_equipment import EquipmentColumns
    if stuff is None:
        return None
    # Ship/base metadata has no equipment column; its complete attributes and
    # properties remain available. Each applicable column calls original EOS.
    if type(stuff).__name__ not in ('Module', 'Drone', 'Fighter', 'Booster', 'Mode'):
        return None
    view = EquipmentColumns()
    view.fit = fit
    view.mainFrame = SimpleNamespace(statsPane=SimpleNamespace(nameViewMap={
        'resistancesViewFull': SimpleNamespace(showEffective=effective)}))
    misc = view.misc(stuff)
    result = dict(misc=None if misc is None else dict(display=misc[0], detail=misc[1]),
                  range=None, capacitor=None, effective=effective)
    if hasattr(stuff, 'falloff'):
        result['range'] = dict(display=view.range_text(stuff), detail=view.range_tooltip(stuff))
    if hasattr(stuff, 'capUse'):
        result['capacitor'] = dict(display=view.capacitor_text(stuff), detail=view.capacitor_tooltip(stuff))
    return result


def variations(item):
    """Original differing base columns; no network or price-object creation."""
    import eos.db
    from .inspection_compare import TranslateValueUnit
    from .market_policy import MarketPolicy
    items = sorted(MarketPolicy().getVariationsByItems([item]),
                   key=lambda value: (value.metaLevel or 0, value.name))
    metadata = {}
    for member in items:
        for name in member.attributes:
            info = member.attributes[name].info
            if info.displayName:
                metadata[name] = info
    differing = []
    for name, info in metadata.items():
        values = [None if name not in member.attributes else member.attributes[name].value for member in items]
        if any(value != values[0] for value in values[1:]):
            differing.append(dict(name=name, id=info.ID, label=info.displayName))
    rows = []
    for member in items:
        values = []
        for column in differing:
            name = column['name']
            attribute = member.attributes.get(name)
            if attribute is None:
                values.append(dict(name=name, available=False, value=None, raw=None, display=None))
                continue
            value, info = _number(attribute), metadata[name]
            display = (TranslateValueUnit(value, info.unit.displayName, info.unit.name)
                       if info.unit is not None else formatAmount(value, 3, 0, 0))
            values.append(dict(name=name, available=True, value=value, raw=str(value), display=display))
        cached = eos.db.getPrice(member.ID)
        price = None if cached is None or not cached.price else _number(cached.price)
        timestamp = None if price is None or not cached.time else cached.time
        rows.append(dict(id=member.ID, name=member.name, meta=member.metaLevel or 0, selected=member.ID == item.ID,
                         values=values, price=dict(available=price is not None, value=price, currency='ISK',
                         timestamp=timestamp, display=None if price is None else formatAmount(price, 3, 3, 9, currency=True))))
    return dict(columns=differing, rows=rows)


def stack(stuff, item, charge=False):
    """Original AttributeDisplay volume/stack-volume presentation in Python."""
    amount = getattr(stuff, 'amount', 1) if stuff is not None and not charge else 1
    if type(amount) is not int or amount < 0:
        raise ValueError('Invalid EOS inspection stack amount')
    if stuff is None:
        value = item.attributes.get('volume')
    else:
        getter = stuff.getModifiedChargeAttr if charge else stuff.getModifiedItemAttr
        value = getter('volume', None)
    volume = None if value is None else _number(value)
    total = None if volume is None else volume * amount
    display = None if volume is None else '{} m³'.format(formatAmount(volume, 3, 0, 6))
    if display is not None and amount != 1:
        display += ' ({} m³)'.format(formatAmount(total, 3, 0, 6))
    if volume:
        from .inspection_equipment import EquipmentColumns
        column = EquipmentColumns()
        column.info = SimpleNamespace(name='volume')
        display = column.attribute_text(SimpleNamespace(item=item, amount=amount,
            getModifiedItemAttr=lambda name, default=None: volume))
    return dict(amount=amount, volume=volume, total_volume=total, unit='m³', display=display)


def object_key(fit, context, thing):
    """Logical identity is stored separately from SQL IDs and public properties."""
    from .inspection_identity import identity
    return identity(fit, thing)


def options(engine, fit):
    engine._check_fit(fit)
    result = [dict(context='ship', index=0, item_id=fit.ship.item.ID, name=fit.ship.item.name,
                   object_key=object_key(fit, 'ship', fit.ship))]
    collections = [('module', fit.modules), ('drone', fit.drones), ('fighter', fit.fighters),
                   ('implant', fit.implants), ('booster', fit.boosters), ('cargo', fit.cargo)]
    if fit.mode is not None:
        collections.append(('mode', [fit.mode]))
    for context, things in collections:
        for index, thing in enumerate(things):
            if thing.item is None:
                continue
            result.append(dict(context=context, index=index, item_id=thing.item.ID, name=thing.item.name,
                               object_key=object_key(fit, context, thing)))
            if context == 'module' and thing.charge is not None:
                result.append(dict(context='charge', index=index, item_id=thing.charge.ID, name=thing.charge.name,
                                   object_key=object_key(fit, 'charge', thing)))
    return result


def target(engine, fit, selection):
    """Resolve against the current fit, rejecting stale positional identities."""
    from .engine import _keys
    engine._check_fit(fit)
    _keys(selection, ('context', 'index', 'item_id'), ('object_key',))
    key = selection.get('object_key')
    if key is not None and (type(key) is not str or re.fullmatch('[0-9a-f]{32}', key) is None):
        raise ValueError('Invalid saved inspection identity')
    context, index, identity = (selection[key] for key in ('context', 'index', 'item_id'))
    if type(identity) is not int or identity <= 0:
        raise ValueError('Choose a known inspection item')
    if context == 'base':
        import eos.db
        if index is not None or key is not None:
            raise ValueError('Base inspection has no fit position')
        item = eos.db.getItem(identity)
        if item is None:
            raise ValueError('Unknown inspection item')
        return None, item, False
    if type(index) is not int or index < 0:
        raise ValueError('Choose an inspection position')
    if context == 'ship':
        things = [fit.ship]
    elif context == 'mode':
        things = [fit.mode] if fit.mode is not None else []
    else:
        names = dict(module='modules', charge='modules', drone='drones', fighter='fighters',
                     implant='implants', booster='boosters', cargo='cargo')
        if context not in names:
            raise ValueError('Unsupported inspection context')
        things = getattr(fit, names[context])
    if index >= len(things):
        raise ValueError('Inspection item was removed')
    stuff = things[index]
    if key is not None and object_key(fit, context, stuff) != key:
        raise ValueError('Inspection object was replaced or removed')
    item = getattr(stuff, 'charge' if context == 'charge' else 'item', None)
    if item is None or item.ID != identity:
        raise ValueError('Inspection item was replaced or removed')
    return stuff, item, context == 'charge'


def details(engine, fit, selection, effective=False, source_resolver=None):
    from .inspection_affectors import views
    engine._check_fit(fit)
    if type(effective) is not bool:
        raise ValueError('Choose raw or effective repair details')
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    stuff, item, charge = target(engine, fit, selection)
    return dict(selection=dict(selection), item=dict(id=item.ID, name=item.name,
                category=item.category.name, group=item.group.name,
                description=item.description, traits=None if item.traits is None else item.traits.display),
                attributes=attributes(stuff, item, charge), effects=effects(item),
                affectors=affectors(stuff, item, charge, source_resolver),
                affector_views=views(stuff, item, fit, source_resolver), properties=properties(stuff, item),
                equipment=equipment(stuff, fit, effective), variations=variations(item), stack=stack(stuff, item, charge))


def base_details(engine, identity):
    engine._check_thread()
    import eos.db
    if type(identity) is not int or identity <= 0:
        raise ValueError('Choose a known base inspection item')
    item = eos.db.getItem(identity)
    if item is None:
        raise ValueError('Unknown base inspection item')
    return dict(selection=dict(context='base', index=None, item_id=identity),
                item=dict(id=item.ID, name=item.name, category=item.category.name, group=item.group.name,
                          description=item.description, traits=None if item.traits is None else item.traits.display),
                attributes=attributes(None, item), effects=effects(item), affectors=[], affector_views=dict(source=[], attribute=[]),
                properties=properties(None, item), equipment=None, variations=variations(item), stack=stack(None, item))
