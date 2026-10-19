"""Fit-local implant commands adapted from original calc/gui implant commands.

GPL-3.0-or-later; Pyfa contributors, see LICENSE. EOS owns all bonuses.
"""
OPERATIONS = frozenset(('fit_implant', 'toggle_implants', 'remove_implants'))


def require_editable(fit):
    from eos.const import ImplantLocation
    if fit.isStructure:
        raise ValueError('Structures do not support the implant editor')
    if fit.implantLocation != ImplantLocation.FIT:
        raise ValueError('Choose fit-local implants; character implants are not editable here')


def positions(fit, values, allow_empty=False):
    if (type(values) is not list or (not values and not allow_empty) or len(values) > 1024
            or any(type(p) is not int or not 0 <= p < len(fit.implants) for p in values)
            or len(set(values)) != len(values)):
        raise ValueError('Choose valid distinct implants')
    return list(values)


def change(engine, fit, operation, args):
    engine._check_fit(fit)
    if operation != 'fit_implant': require_editable(fit)
    elif fit.isStructure: raise ValueError('Structures do not support the implant editor')
    used=[]
    if operation == 'fit_implant':
        from .fitting import item
        from eos.saveddata.implant import Implant
        value=item(engine,args['item_id'])
        if not value.isImplant:
            raise ValueError('Choose an implant')
        from eos.const import ImplantLocation
        switching = fit.implantLocation != ImplantLocation.FIT
        duplicate = any(i.itemID == value.ID for i in fit.implants)
        if duplicate and not switching: raise ValueError('This implant is already fitted')
        fit.implantLocation = ImplantLocation.FIT
        if duplicate:
            import eos.db
            eos.db.saveddata_session.flush()
            engine._recalculate(fit)
            from .fitting import _fill
            _fill(fit)
            return [value.ID]
        new=Implant(value)
        occupied=next((i for i in fit.implants if i.slot == new.slot),None)
        if occupied is not None:
            occupied.itemID=0  # Original HandledImplantList.makeRoom ORM workaround.
            fit.implants.remove(occupied)
        fit.implants.append(new)
        if new not in fit.implants:
            raise ValueError('EOS rejected the implant')
        used.append(value.ID)
    elif operation == 'toggle_implants':
        ps=positions(fit,args['positions'],True)
        main=positions(fit,[args['main_position']])[0]
        if main not in ps: ps.append(main)
        active=not fit.implants[main].active
        for p in ps: fit.implants[p].active=active
    elif operation == 'remove_implants':
        for p in sorted(positions(fit,args['positions']),reverse=True):
            used.append(fit.implants[p].itemID)
            fit.implants.remove(fit.implants[p])
    else:
        raise ValueError('Unknown implant edit')
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    from .fitting import _fill
    _fill(fit)
    return used


def details(engine, fit):
    from eos.const import ImplantLocation
    from .inspection_identity import identity
    engine._check_fit(fit)
    return dict(is_structure=fit.isStructure,location=ImplantLocation(fit.implantLocation).name,
                implants=[dict(index=i,object_key=identity(fit,obj),item_id=obj.itemID,
                    name=obj.item.name,slot=obj.slot,active=obj.active) for i,obj in enumerate(fit.implants)])


def add_options(engine, fit, item_id):
    from eos.const import ImplantLocation
    from eos.saveddata.implant import Implant
    from .fitting import item
    from .inspection_identity import identity
    engine._check_fit(fit)
    value=item(engine,item_id)
    slot=Implant(value).slot if value.isImplant else None
    occupant=next(((i,obj) for i,obj in enumerate(fit.implants) if value.isImplant and obj.slot==slot),None)
    return dict(item_id=value.ID,is_implant=value.isImplant,is_structure=fit.isStructure,
                location=ImplantLocation(fit.implantLocation).name,slot=slot,
                occupant=None if occupant is None else dict(index=occupant[0],object_key=identity(fit,occupant[1]),
                    item_id=occupant[1].itemID,name=occupant[1].item.name),
                already_fitted=value.isImplant and any(i.itemID==value.ID for i in fit.implants))
