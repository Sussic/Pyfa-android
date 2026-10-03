"""C02 EOS output and pinned desktop statistics presentation.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Presentation and bomb counts follow firepowerViewFull, miningyieldViewFull,
bombingViewFull and outgoingViewFull at
8b04f3b271e614b3e103853b44a7851a63d79d0e. No fitting formula lives in Kotlin.
"""
from copy import copy
import math

from .defenses import scalar
from .number_format import formatAmount, roundToPrec

DAMAGE = ('em', 'thermal', 'kinetic', 'explosive', 'pure')
REMOTE = ('capacitor', 'shield', 'armor', 'hull')
RED_GIANTS = tuple(f'Class {level} Red Giant Effects' for level in range(1, 7))


def amount(value, unit, precision=3):
    text = None if value is None else formatAmount(value, precision, 0, 0)
    return scalar(value, unit, text, text)


def damage_row(current, pre, full, unit):
    available = all(row is not None for row in (current, pre, full))
    indicated = available and roundToPrec(pre.total, 3) != roundToPrec(full.total, 3)
    parts = {}
    for name in DAMAGE:
        value = None if current is None else getattr(current, name)
        percentage = None if value is None else (value/current.total*100 if current.total else 0.0)
        parts[name] = dict(amount=amount(value, unit), share=amount(percentage, '%'))
    tooltip = []
    if indicated:
        tooltip.append('Spool up: {}-{}'.format(formatAmount(pre.total,3,0,0),formatAmount(full.total,3,0,0)))
    if current is not None and current.total:
        if indicated:
            tooltip.extend(('', 'Current: '+formatAmount(current.total,3,0,0)))
        for name in DAMAGE:
            value = getattr(current,name)
            if value:
                tooltip.append('{}{}: {}%'.format('  ' if indicated else '',name.capitalize(),formatAmount(value/current.total*100,3,0,0)))
    value = amount(None if current is None else current.total,unit)
    if indicated:
        value['display'] += '\u02e2'
    return dict(current=value,pre=amount(None if pre is None else pre.total,unit),
                full=amount(None if full is None else full.total,unit),
                indicated=bool(indicated),tooltip='\n'.join(tooltip),damage=parts)


def bomb_counts(fit):
    """Original bombingViewFull algorithm on EOS modified ship attributes."""
    import eos.db
    from eos.const import FittingModuleState
    modifier = 1.0
    for effect in fit.projectedModules:
        if effect.state == FittingModuleState.ONLINE and effect.fullName in RED_GIANTS:
            modifier *= effect.item.attributes['smartbombDamageMultiplier'].value
    signature = fit.ship.getModifiedItemAttr('signatureRadius')
    bombs = dict(em=27920,thermal=27916,kinetic=27912,explosive=27918)
    rows = []
    for level in range(6):
        cells = {}
        for kind, item_id in bombs.items():
            bomb = eos.db.getItem(item_id)
            ehp = 0.0
            for layer,hp in (('', 'hp'),('armor','armorHP'),('shield','shieldCapacity')):
                name = (layer+kind.capitalize()+'DamageResonance') if layer else kind+'DamageResonance'
                health = fit.ship.getModifiedItemAttr(hp)
                resonance = fit.ship.getModifiedItemAttr(name)
                if health is None or resonance is None or resonance <= 0:
                    ehp = None
                    break
                ehp += health/resonance
            base = sum(bomb.attributes[name+'Damage'].value for name in DAMAGE[:4])
            applied = None if signature is None else base*(1+0.05*level)*modifier*(min(bomb.attributes['signatureRadius'].value,signature)/bomb.attributes['signatureRadius'].value)
            count = None if ehp is None or applied is None or applied <= 0 else math.ceil((ehp/applied)*10)/10
            text = None if count is None else '{:.1f}'.format(count)
            cells[kind] = scalar(count,'bombs',text,text)
        rows.append(dict(covert_ops_level=level,counts=cells))
    return dict(signature=amount(signature,'m'),environment_multiplier=amount(modifier,'x'),levels=rows)


def details(engine, fit):
    engine._check_fit(fit)
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    import eos.config
    from eos.utils.spoolSupport import SpoolOptions, SpoolType
    default = eos.config.settings['globalDefaultSpoolupPercentage']
    options = [SpoolOptions(SpoolType.SPOOL_SCALE,value,force) for value,force in ((default,False),(0,True),(1,True))]
    sources = dict(weapon=[fit.getWeaponDps(spoolOptions=o) for o in options],
                   drone=[fit.getDroneDps()]*3,
                   total=[fit.getTotalDps(spoolOptions=o) for o in options],
                   volley=[fit.getTotalVolley(spoolOptions=o) for o in options])
    modes = {}
    for mode in ('raw','effective'):
        rows = {}
        for name, values in sources.items():
            # EOS TargetProfile.__deepcopy__ omits hp and spatial attributes.
            # Copy only the damage containers; their profile and breacher
            # inputs remain read-only, and cache invalidation stays on the copy.
            values = [copy(value) if value is not None else None for value in values]
            if mode == 'raw':
                for value in values:
                    if value is not None: value.profile = None
            rows[name] = damage_row(*values,'HP' if name=='volley' else 'DPS')
        modes[mode] = rows
    mining = {}
    for name,yield_value,drain in (('module',fit.minerYield,fit.minerDrain),
                                  ('drone',fit.droneYield,fit.droneDrain),
                                  ('total',fit.totalYield,fit.totalDrain)):
        efficiency = None if yield_value is None or drain is None else (yield_value/drain*100 if drain else 0.0)
        mining[name] = dict(yield_second=amount(yield_value,'m³/s'),drain_second=amount(drain,'m³/s'),
                            yield_hour=amount(None if yield_value is None else yield_value*3600,'m³/hour'),
                            drain_hour=amount(None if drain is None else drain*3600,'m³/hour'),
                            efficiency=amount(efficiency,'%',4))
    outgoing = {}
    values = [fit.getRemoteReps(spoolOptions=o) for o in options]
    for name in REMOTE:
        current,pre,full = [getattr(row,name) if row is not None else None for row in values]
        unit = 'GJ/s' if name=='capacitor' else 'HP/s'
        indicated = pre is not None and full is not None and roundToPrec(pre,3)!=roundToPrec(full,3)
        result = amount(current,unit)
        if indicated and result['display'] is not None:result['display'] += '\u02e2'
        label = dict(capacitor='Capacitor restored',shield='Shield restored',armor='Armor restored',hull='Hull restored')[name]
        tooltip = label if not indicated else '{}\nSpool up: {}-{}'.format(label,formatAmount(pre,3,0,0),formatAmount(full,3,0,0))
        outgoing[name] = dict(current=result,pre=amount(pre,unit),full=amount(full,unit),indicated=indicated,tooltip=tooltip)
    return dict(output=dict(firepower=modes,mining=mining,bombing=bomb_counts(fit),outgoing=outgoing,
                            effective=fit.targetProfile is not None,default_spool_percentage=float(default)*100))
