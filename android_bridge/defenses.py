"""C01.3.1 EOS defenses with pinned resistance-view presentation.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Presentation: gui/builtinStatsViews/resistancesViewFull.py at
8b04f3b271e614b3e103853b44a7851a63d79d0e. Fitting calculations stay in EOS.
"""
from .number_format import formatAmount
from .resources import _number

DAMAGE=('em','thermal','kinetic','explosive')


def scalar(value,unit,display,detail):
    return dict(value=value,value_type=_number(value),unit=unit,
        display=None if value is None else display,detail=None if value is None else detail)


def details(engine,fit):
    engine._check_fit(fit)
    if not fit.calculated:fit.calculateModifiedAttributes()
    raw,effective=fit.hp,fit.ehp
    layers={}
    for layer in ('shield','armor','hull'):
        values={}
        for name,source in (('hp',raw),('ehp',effective)):
            value=source[layer]
            values[name]=scalar(value,'HP',None if value is None else formatAmount(value,3,0,9),
                None if value is None else '%d'%value)
        multiplier=None if raw[layer] is None or effective[layer] is None or raw[layer]==0 else effective[layer]/raw[layer]
        values['multiplier']=scalar(multiplier,'x',None if multiplier is None else '%.2f'%multiplier,
            None if multiplier is None else '%.2f'%multiplier)
        values['resistances']={}
        for kind in DAMAGE:
            attribute=('%s%sDamageResonance'%('' if layer=='hull' else layer,kind.capitalize()))
            attribute=attribute[0].lower()+attribute[1:]
            resonance=fit.ship.getModifiedItemAttr(attribute)
            value=None if resonance is None else (1-resonance)*100
            values['resistances'][kind]=scalar(value,'%',None if value is None else '%.1f'%max(0,value),
                None if value is None else '%.2f'%value)
        layers[layer]=values
    totals={}
    for name,source in (('hp',raw),('ehp',effective)):
        value=None if any(v is None for v in source.values()) else sum(source.values())
        totals[name]=scalar(value,'HP',None if value is None else formatAmount(value,3,0,9),
            None if value is None else '%d'%value)
    amounts={kind:getattr(fit.damagePattern,kind+'Amount') for kind in DAMAGE}
    total=sum(amounts.values())
    pattern={kind:dict(amount=float(amounts[kind]),percentage=amounts[kind]/total*100,
        display='%.1f'%(amounts[kind]/total*100)) for kind in DAMAGE}
    return dict(defenses=dict(layers=layers,total=totals,pattern=pattern))
