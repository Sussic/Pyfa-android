"""C05 local squadron commands adapted from pinned Pyfa; no implicit merging.

GPL-3.0-or-later; original Pyfa contributors, see LICENSE. Sources:
gui/fitCommands/{calc/fighter,gui/localFighter} and FighterInfo.
"""
import math
OPERATIONS=frozenset(('add_fighter','set_fighter_amount','remove_fighters','toggle_fighters','toggle_fighter_ability','change_fighter_variations'))
SLOTS=('F_LIGHT','F_SUPPORT','F_HEAVY','FS_LIGHT','FS_SUPPORT','FS_HEAVY')
def positions(fit,values,allow_empty=False):
    if type(values) is not list or (not values and not allow_empty) or len(values)>1024 or any(type(p) is not int or not 0<=p<len(fit.fighters) for p in values) or len(set(values))!=len(values):
        raise ValueError('Choose valid distinct fighter squadrons')
    return list(values)
def choices(engine,fit,item):
    from .variations import choices as original_choices
    return [{key:row[key] for key in ('id','name','enabled')} for row in original_choices(engine,fit,item,'fighter')]

def change(engine,fit,operation,args):
    engine._check_fit(fit)
    from eos.saveddata.fighter import Fighter
    from .fitting import item,_fill,FittingRejected
    from .engine import _integer
    used=[]
    if operation=='add_fighter':
        value=item(engine,args['item_id']);fighter=Fighter(value)
        if not fighter.fits(fit):raise FittingRejected('This hull does not support that fighter category',value.ID)
        total=fit.fighterTubesTotal;category=fit.getNumSlots(fighter.slot)
        if total is None or category is None:raise ValueError('Fighter tube capacity is unavailable')
        fighter.active=fit.fighterTubesUsed<total and fit.getSlotsUsed(fighter.slot)<category
        fit.fighters.append(fighter)
        if fighter not in fit.fighters:raise FittingRejected('EOS rejected this fighter',value.ID)
        used.append(value.ID)
    elif operation=='set_fighter_amount':
        p=positions(fit,[args['position']])[0];amount=args['amount'];_integer(amount,0,2**31-1)
        if amount==0:fit.fighters.remove(fit.fighters[p])
        else:fit.fighters[p].amount=min(amount,fit.fighters[p].fighterSquadronMaxSize)
    elif operation=='remove_fighters':
        for p in sorted(positions(fit,args['positions']),reverse=True):
            used.append(fit.fighters[p].itemID)
            fit.fighters.remove(fit.fighters[p])
    else:
        ps=positions(fit,args['positions'],True);main=positions(fit,[args['main_position']])[0]
        if main not in ps:ps.append(main)
        primary=fit.fighters[main]
        if operation=='toggle_fighters':
            active=not primary.active
            for p in ps:fit.fighters[p].active=active
        elif operation=='toggle_fighter_ability':
            effect=args['effect_id'];ability=next((a for a in primary.abilities if a.effectID==effect),None)
            if ability is None or not ability.effect.isImplemented:raise ValueError('Choose an implemented fighter ability')
            active=not ability.active
            for p in ps:
                a=next((a for a in fit.fighters[p].abilities if a.effectID==effect),None)
                if a is not None and a.effect.isImplemented:a.active=active
        elif operation=='change_fighter_variations':
            selected=args['item_id'];rows=choices(engine,fit,primary.item)
            if not any(r['id']==selected and r['enabled'] for r in rows):raise ValueError('Choose an enabled variation')
            family={r['id'] for r in rows};value=item(engine,selected)
            for p in sorted(ps,reverse=True):
                old=fit.fighters[p]
                if old.itemID not in family or old.itemID==selected:continue
                fighter=Fighter(value);fighter.amount=old.amount;fighter.active=old.active
                old_states={a.effectID:a.active for a in old.abilities}
                for a in fighter.abilities:a.active=old_states.get(a.effectID,a.active)
                fit.fighters.remove(old);fit.fighters.append(fighter)
                if fighter not in fit.fighters:raise ValueError('EOS rejected fighter replacement')
        else:raise ValueError('Unknown fighter edit')
    import eos.db
    eos.db.saveddata_session.flush();engine._recalculate(fit);_fill(fit)
    return used
def details(engine,fit):
    engine._check_fit(fit)
    if not fit.calculated:fit.calculateModifiedAttributes()
    from eos.const import FittingSlot
    from .inspection_identity import identity
    def number(x):
        if x is not None and (type(x) not in (int,float) or not math.isfinite(x) or x<0):raise ValueError('Invalid fighter resource value')
        return x
    categories=[dict(slot=name,name=name.replace('FS_','Structure ').replace('F_','').title(),
                     used=number(fit.getSlotsUsed(getattr(FittingSlot,name))),total=number(fit.getNumSlots(getattr(FittingSlot,name)))) for name in SLOTS]
    rows=[]
    for index,fighter in enumerate(fit.fighters):
        rows.append(dict(index=index,object_key=identity(fit,fighter),item_id=fighter.itemID,name=fighter.item.name,
                         group=fighter.item.group.name,slot=FittingSlot(fighter.slot).name,amount=fighter.amount,
                         max_size=fighter.fighterSquadronMaxSize,active=fighter.active,
                         abilities=[dict(effect_id=a.effectID,name=a.name,active=a.active) for a in fighter.abilities if a.effect.isImplemented],
                         variations=choices(engine,fit,fighter.item)))
    return dict(bay_used=number(fit.fighterBayUsed),bay_capacity=number(fit.ship.getModifiedItemAttr('fighterCapacity')),
                tubes_used=number(fit.fighterTubesUsed),tubes_total=number(fit.fighterTubesTotal),categories=categories,squadrons=rows)
