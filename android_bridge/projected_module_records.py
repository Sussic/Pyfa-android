"""Optional ordered individual projector inputs; legacy environments replay once."""
import math
from weakref import WeakKeyDictionary

_layout = WeakKeyDictionary()
LIMIT = 1024


def range_value(value):
    if value is None: return None
    if type(value) not in (int, float):
        raise ValueError('Projection range must be blank or finite nonnegative metres')
    try: canonical = float(value)
    except OverflowError as error:
        raise ValueError('Projection range exceeds the native numeric boundary') from error
    if not math.isfinite(canonical) or canonical < 0:
        raise ValueError('Projection range must be blank or finite nonnegative metres')
    if type(value) is int and canonical != value:
        raise ValueError('Integer projection range cannot be represented exactly')
    # Match EOS Float storage and native Double before history capture, without
    # silently rounding an integral JSON input during an ORM refresh.
    return 0.0 if canonical == 0 else canonical


def validate(rows):
    if type(rows) is not list or len(rows) > LIMIT:
        raise ValueError('Too many projected modules')
    from .module_spool import validate as spool
    for row in rows:
        if type(row) is not dict or not {'name','state','charge','range_m'} <= row.keys() or set(row) - {'name','state','charge','range_m','spool_cycles'}:
            raise ValueError('Invalid projected module record')
        for key in ('name','state'):
            if type(row[key]) is not str or not row[key] or len(row[key]) > 512:
                raise ValueError('Invalid projected module name or state')
        if row['charge'] is not None and (type(row['charge']) is not str or not row['charge'] or len(row['charge']) > 512):
            raise ValueError('Invalid projected charge')
        range_value(row['range_m'])
        if 'spool_cycles' in row: spool(row['spool_cycles'])


def eligible(item):
    return bool(item.isModule and item.isType('projected') and not item.isAbyssal)


def setup(engine, fit, spec):
    from eos.saveddata.module import Module
    from eos.const import FittingModuleState
    from .module_spool import restore
    rows = spec.get('projected_modules', [])
    validate(rows)
    if len(spec['environments']) + len(rows) > LIMIT:
        raise ValueError('Too many projected modules')
    _layout[fit] = tuple(row['name'] for row in spec['environments'])
    if 'projected_modules' in spec:
        from .inspection_identity import enable_projected
        enable_projected(fit)
    for row in rows:
        item = engine._item(row['name'])
        if not eligible(item) or fit.isStructure:
            raise ValueError('This item cannot be projected onto this fit')
        module = Module(item)
        try: state = FittingModuleState[row['state']]
        except (KeyError, TypeError) as error: raise ValueError('Invalid projected state') from error
        if not module.isValidState(state): raise ValueError('Invalid projected state')
        module.state, module.projectionRange = state, range_value(row['range_m'])
        if row['charge'] is not None:
            charge = engine._item(row['charge'])
            if not charge.isCharge or not module.isValidCharge(charge): raise ValueError('Invalid projected charge')
            module.charge = charge
        restore(module, row)
        fit.projectedModules.append(module)
        if module not in fit.projectedModules: raise ValueError('Projected module was refused')


def prefix(fit):
    names = _layout.get(fit)
    if names is None: raise ValueError('Projected module layout is unavailable')
    if len(fit.projectedModules) < len(names) or tuple(m.item.name for m in list(fit.projectedModules)[:len(names)]) != names:
        raise ValueError('Legacy environment order changed')
    return len(names)


def capture(fit, spec):
    from eos.const import FittingModuleState
    from .module_spool import capture as spool
    from .inspection_identity import projected_enabled
    count = prefix(fit)
    modules = list(fit.projectedModules)
    if len(modules) > LIMIT: raise ValueError('Too many projected modules')
    for module in modules:
        if module.rahPatternOverride is not None or getattr(module, 'isMutated', False):
            raise ValueError('Projected mutation or reactive armor overrides are unsupported')
    for module in modules[:count]:
        if module.charge is not None or module.projectionRange is not None or spool(module):
            raise ValueError('Unsupported legacy environment input')
    spec['environments'] = [dict(name=m.item.name,state=FittingModuleState(m.state).name) for m in modules[:count]]
    rows = []
    for module in modules[count:]:
        if not eligible(module.item): raise ValueError('Unsupported individual projected object')
        rows.append(dict(name=module.item.name,state=FittingModuleState(module.state).name,
                         charge=module.charge.name if module.charge else None,
                         range_m=range_value(module.projectionRange),**spool(module)))
    validate(rows)
    if rows or 'projected_modules' in spec or projected_enabled(fit): spec['projected_modules'] = rows


def refresh_order(fit):
    """Called after the existing flush, before refresh expires ORM objects."""
    order = tuple(module.ID for module in fit.projectedModules)
    if any(type(key) is not int or key <= 0 for key in order) or len(set(order)) != len(order):
        raise ValueError('Cannot preserve projected module order across refresh')
    return order


def restore_refresh_order(fit, order):
    modules = fit.projectedModules
    current = [module.ID for module in modules]
    if len(current) != len(order) or len(set(current)) != len(current) or set(current) != set(order):
        raise ValueError('Projected module membership changed during refresh')
    ordinal = {key:index for index,key in enumerate(order)}
    # This ORM relationship has no order_by or managed position. Reorder only
    # the verified unchanged objects in memory, before numerical recalculation
    # and position-based logical identity restoration. No relationship mutation.
    list.sort(modules,key=lambda module:ordinal[module.ID])
