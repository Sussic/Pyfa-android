"""Single-row projected module GUI/calc policy; durable commit belongs to bridge.

GPL-3.0-or-later, Pyfa contributors. Source commands: projectedAdd/Remove,
projectedChangeStates/ProjectionRange, changeCharges and projected changeMetas.
"""
from . import fitting, projected_module_records as records
from .inspection_identity import identity, enable_projected

OPERATIONS = {
    'add_projected_module': ('fit_id','item_id'),
    'set_projected_module_state': ('fit_id','position','object_key','state'),
    'set_projected_module_charge': ('fit_id','position','object_key','charge_id'),
    'change_projected_module_variation': ('fit_id','position','object_key','item_id'),
    'set_projected_module_range': ('fit_id','position','object_key','range_m'),
    'set_projected_module_spool': ('fit_id','position','object_key','cycles'),
    'remove_projected_module': ('fit_id','position','object_key'),
}


def require_fit(engine, fit):
    engine._check_fit(fit)
    if fit.isStructure: raise ValueError('Individual projections are unavailable for structures')


def selected(fit, position, object_key=None):
    if type(position) is not int or not records.prefix(fit) <= position < len(fit.projectedModules):
        raise ValueError('Choose an editable projected module')
    module = fit.projectedModules[position]
    if object_key is not None and (type(object_key) is not str or identity(fit,module) != object_key):
        raise ValueError('Projected module changed; reload its controls')
    if not records.eligible(module.item): raise ValueError('Unsupported projected module')
    return module


def add_options(engine, fit, item_id):
    engine._check_fit(fit)
    item = fitting.item(engine,item_id)
    enabled = records.eligible(item) and not fit.isStructure and len(fit.projectedModules) < records.LIMIT
    reason = None if enabled else ('Individual projections are unavailable for structures' if fit.isStructure else
        'Projected module limit reached' if len(fit.projectedModules) >= records.LIMIT else 'This item cannot be projected')
    return dict(item_id=item.ID,is_module=bool(item.isModule),is_projectable=bool(item.isType('projected')),
                is_structure=fit.isStructure,enabled=enabled,unavailable_reason=reason)


def details(engine, fit):
    engine._check_fit(fit)
    from eos.const import FittingModuleState
    prefix=records.prefix(fit)
    if len(fit.projectedModules)>records.LIMIT: raise ValueError('Too many projected modules')
    rows=[]
    for index,module in enumerate(fit.projectedModules):
        editable=index>=prefix and not fit.isStructure and records.eligible(module.item)
        rows.append(dict(index=index,object_key=identity(fit,module),item_id=module.itemID,name=module.item.name,
                         state=FittingModuleState(module.state).name,charge_id=module.chargeID,
                         charge_name=None if module.charge is None else module.charge.name,
                         range_m=module.projectionRange,editable=editable,
                         unavailable_reason=None if editable else 'Legacy environment (read only)'))
    return dict(is_structure=fit.isStructure,modules=rows)


def proposals(module):
    from eos.const import FittingModuleState as S
    from eos.saveddata.module import Module
    return {name:Module.getProposedState(module,None,state) for name,state in
            (('inactive',S.OFFLINE),('active',S.ACTIVE),('overheat',S.OVERHEATED))}


def options(engine, fit, position):
    require_fit(engine,fit)
    module=selected(fit,position)
    from .charges import compatible
    from .variations import choices
    from .module_spool import GROUPS, row
    charges=sorted(compatible(module),key=lambda item:(item.name,item.ID))
    variations=choices(engine,fit,module.item,'projected_module')
    if len(charges)>8192 or len(variations)>8192: raise ValueError('Too many projected choices')
    return dict(index=position,object_key=identity(fit,module),item_id=module.itemID,
                state_actions=[dict(id=name,label=name.capitalize(),enabled=state!=module.state)
                               for name,state in proposals(module).items()],
                charges=[dict(id=item.ID,name=item.name) for item in charges],
                variations=[{key:value[key] for key in ('id','name','enabled')} for value in variations],
                spool=row(fit,module,position) if module.item.group.name in GROUPS else None)


def inner(engine,fit,base,flush=False):
    if flush:
        import eos.db
        eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    return fitting.check_states(fit,base)


def finish(engine,fit,recalculate):
    if recalculate:
        import eos.db
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
    fitting._fill(fit)


def append(engine,fit,module):
    allowed=module.canHaveState(module.state,projectedOnto=fit)
    if allowed is not True: module.state=allowed
    if not module.isValidCharge(module.charge): module.charge=None
    fit.projectedModules.makeRoom(module)
    fit.projectedModules.append(module)
    if module not in fit.projectedModules: raise ValueError('Projected module was refused')
    return inner(engine,fit,module,flush=True)


def change(engine,fit,operation,args):
    require_fit(engine,fit)
    from eos.const import FittingModuleState, SpoolType
    from eos.saveddata.module import Module
    if operation=='add_projected_module':
        if not add_options(engine,fit,args['item_id'])['enabled']: raise ValueError('Choose a projectable module')
        module=Module(fitting.item(engine,args['item_id']))
        if module.isValidState(FittingModuleState.ACTIVE): module.state=FittingModuleState.ACTIVE
        enable_projected(fit)
        finish(engine,fit,append(engine,fit,module))
        return
    module=selected(fit,args['position'],args['object_key'])
    need=True
    if operation=='remove_projected_module':
        del fit.projectedModules[args['position']]
        need=inner(engine,fit,None,flush=True)
    elif operation=='set_projected_module_state':
        values=proposals(module)
        if type(args['state']) is not str or args['state'] not in values: raise ValueError('Choose a projected state action')
        state=values[args['state']]
        if state!=module.state:
            module.state=state
            need=inner(engine,fit,None)
    elif operation=='set_projected_module_range':
        range_m=records.range_value(args['range_m'])
        if range_m!=module.projectionRange:
            module.projectionRange=range_m
            need=inner(engine,fit,module)
    elif operation=='set_projected_module_charge':
        charge=None if args['charge_id'] is None else fitting.item(engine,args['charge_id'])
        if (charge is not None and not charge.isCharge) or not module.isValidCharge(charge): raise ValueError('Choose a compatible projected charge')
        if module.chargeID!=args['charge_id']:
            module.charge=charge
            need=inner(engine,fit,None)
    elif operation=='set_projected_module_spool':
        from .module_spool import GROUPS,validate,row
        cycles=args['cycles']
        if module.item.group.name not in GROUPS: raise ValueError('Choose a supported projected spool module')
        if cycles is not None:
            validate(cycles)
            if cycles not in row(fit,module,args['position'])['choices']: raise ValueError('Choose a source spool option')
        module.spoolType=None if cycles is None else SpoolType.CYCLES
        module.spoolAmount=cycles
    elif operation=='change_projected_module_variation':
        if not any(r['id']==args['item_id'] and r['enabled'] for r in options(engine,fit,args['position'])['variations']):
            raise ValueError('Choose an enabled projected variation')
        need=False
        if args['item_id']!=module.itemID:
            new=Module(fitting.item(engine,args['item_id']))
            new.state=module.state if new.isValidState(module.state) else new.getMaxState(proposedState=module.state)
            new.charge=module.charge
            new.spoolType,new.spoolAmount=module.spoolType,module.spoolAmount
            del fit.projectedModules[args['position']]
            inner(engine,fit,None,flush=True)
            need=append(engine,fit,new)
    else: raise ValueError('Unknown projected module operation')
    finish(engine,fit,need)
