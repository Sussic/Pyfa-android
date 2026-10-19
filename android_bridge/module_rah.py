"""Local reactive armor modes; all adaptation calculations remain in EOS."""
import math

GROUP = 'Armor Resistance Shift Hardener'
CUSTOM_ERROR = 'Reactive armor override is not owned by the current graph'


def validate(record, allow_fit=False, allow_named=False):
    if type(record) is not dict:
        raise ValueError('Invalid reactive armor pattern')
    mode = record.get('mode')
    if mode in ('disabled', 'fit') and (mode != 'fit' or allow_fit):
        if set(record) != {'mode'}:
            raise ValueError('This reactive armor mode has no pattern ID')
    elif mode == 'builtin':
        from eos.saveddata.damagePattern import DamagePattern
        if set(record) != {'mode', 'pattern_id'} or type(record['pattern_id']) is not int:
            raise ValueError('Choose a built-in reactive armor pattern')
        if DamagePattern.getBuiltinById(record['pattern_id']) is None:
            raise ValueError('Unknown built-in reactive armor pattern')
    elif mode == 'named' and allow_named:
        from .offline.named_rah import named_id
        if set(record) != {'mode', 'pattern_id'}:
            raise ValueError('Invalid named reactive armor pattern')
        named_id(record['pattern_id'])
    else:
        raise ValueError('Invalid reactive armor mode')


def resolve(record, resolver=None):
    validate(record, allow_fit=True, allow_named=resolver is not None)
    if record['mode'] == 'named': return resolver.resolve(record['pattern_id'])
    if record['mode'] == 'fit': return None
    if record['mode'] == 'disabled': return 'disable'
    from eos.saveddata.damagePattern import DamagePattern
    return DamagePattern.getBuiltinById(record['pattern_id'])


def capture(module, resolver=None):
    value = module.rahPatternOverride
    if value is None: return {}
    if module.item.group.name != GROUP:
        raise ValueError('This module does not support reactive armor patterns')
    if value == 'disable': return {'rah_pattern': {'mode':'disabled'}}
    key = resolver.identify(value) if resolver is not None else None
    if key is not None: return {'rah_pattern': {'mode': 'named', 'pattern_id': key}}
    from eos.saveddata.damagePattern import DamagePattern
    # Identity matters: explicit Uniform is distinct from inheriting Uniform.
    if value is not DamagePattern.getBuiltinById(getattr(value, 'ID', None)):
        raise ValueError(CUSTOM_ERROR)
    return {'rah_pattern': {'mode':'builtin', 'pattern_id':value.ID}}


def restore(module, record, resolver=None):
    if 'rah_pattern' not in record: return
    validate(record['rah_pattern'], allow_named=resolver is not None)
    if module.item.group.name != GROUP:
        raise ValueError('This module does not support reactive armor patterns')
    module.rahPatternOverride = resolve(record['rah_pattern'], resolver)


def components(pattern):
    values = {name:getattr(pattern,name+'Amount') for name in ('em','thermal','kinetic','explosive')}
    if any(type(v) not in (int,float) or not math.isfinite(v) or v < 0 for v in values.values()) or not math.isfinite(sum(values.values())) or sum(values.values()) <= 0:
        raise ValueError('Reactive armor pattern components are unavailable')
    return values


def details(engine, fit):
    from eos.saveddata.damagePattern import DamagePattern
    from .inspection_identity import identity
    engine._check_fit(fit)
    rows=[]
    for index,module in enumerate(fit.modules):
        if module.isEmpty or module.item.group.name != GROUP: continue
        record=capture(module, getattr(fit, '_native_rah_resolver', None)).get('rah_pattern', {'mode':'fit'})
        rows.append(dict(index=index, object_key=identity(fit,module),item_id=module.itemID,
                         name=module.item.name,mode=record['mode'],pattern_id=record.get('pattern_id')))
    return dict(modules=rows, patterns=[dict(id=p.ID,name=p.fullName,components=components(p))
                for p in DamagePattern.getBuiltinList()],
                fit_pattern=dict(name='Fit pattern',components=components(fit.damagePattern)))


def change(engine, fit, position, record):
    from .fitting import _position
    engine._check_fit(fit)
    module=_position(fit,position,occupied=True)
    if module.item.group.name != GROUP:
        raise ValueError('Choose a reactive armor hardener')
    module.rahPatternOverride=resolve(record)
    engine._recalculate(fit)


def capture_overrides(fit):
    """Serialize unmapped inputs before an ORM refresh can collect modules."""
    from .inspection_identity import identity
    resolver = getattr(fit, '_native_rah_resolver', None)
    return [(module.itemID, module.slot, identity(fit, module), {} if module.isEmpty else capture(module, resolver))
            for module in fit.modules]


def restore_overrides(fit, records):
    modules = list(fit.modules)
    if len(modules) != len(records) or any((module.itemID, module.slot) != (item_id, slot) for module,(item_id,slot,_,_) in zip(modules,records)):
        raise ValueError('Module layout changed during reactive armor restoration')
    from .inspection_identity import capture as capture_ids, restore as restore_ids
    saved = capture_ids(fit)
    saved['modules'] = [key for _, _, key, _ in records]
    restore_ids(fit, saved)
    resolver = getattr(fit, '_native_rah_resolver', None)
    for module, (_, _, _, record) in zip(modules, records):
        module.rahPatternOverride = None
        restore(module, record, resolver)


def validate_carry(source, destination, resolver=None):
    record = capture(source, resolver) if not source.isEmpty else {}
    if record.get('rah_pattern', {}).get('mode') == 'named' and (
            destination.isEmpty or destination.item.group.name != GROUP):
        raise ValueError('A named reactive armor pattern cannot move to a non-reactive module')
