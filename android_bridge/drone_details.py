"""Read-only drone stack details from EOS, including per-drone health/recharge."""
import math
from .inspection_identity import identity
from .number_format import formatAmount

ATTRIBUTES = (
    ('volume', 'Volume per drone', 'm3'), ('droneBandwidthUsed', 'Bandwidth per active drone', 'Mbit/s'),
    ('trackingSpeed', 'Tracking', 'rad/s'), ('maxVelocity', 'Maximum velocity', 'm/s'),
    ('signatureRadius', 'Signature radius', 'm'), ('duration', 'Effect duration', 'ms'),
    ('ECMDuration', 'ECM duration', 'ms'), ('energyNeutralizerDuration', 'Neutralizer duration', 'ms'),
    ('accessDifficultyBonus', 'Salvage access bonus', '%'),
    ('scanGravimetricStrengthBonus', 'Gravimetric ECM strength', 'points'),
    ('scanLadarStrengthBonus', 'Ladar ECM strength', 'points'),
    ('scanMagnetometricStrengthBonus', 'Magnetometric ECM strength', 'points'),
    ('scanRadarStrengthBonus', 'Radar ECM strength', 'points'),
    ('speedFactor', 'Velocity effect', '%'), ('signatureRadiusBonus', 'Target signature effect', '%'),
    ('trackingSpeedBonus', 'Tracking effect', '%'), ('maxRangeBonus', 'Optimal range effect', '%'),
    ('falloffBonus', 'Falloff effect', '%'), ('scanResolutionBonus', 'Scan resolution effect', '%'),
    ('maxTargetRangeBonus', 'Targeting range effect', '%'),
    ('energyNeutralizerAmount', 'Capacitor neutralized per cycle', 'GJ'),
)


def metrics(drone, fit):
    rows = []
    def add(key, label, unit, value):
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value)):
            raise ValueError('EOS returned a nonfinite drone detail')
        rows.append(dict(key=key, label=label, unit=unit, value=value,
                         text=None if value is None else formatAmount(value,3,0,0)))
    for key, values, unit in (('hp',drone.hp,'HP'), ('ehp',drone.ehp,'EHP')):
        for layer in ('shield','armor','hull'):
            add(key+'_'+layer, layer.capitalize()+' '+unit+' per drone',unit,values[layer])
    recharge = drone.getModifiedItemAttr('shieldRechargeRate')
    regen = drone.calculateShieldRecharge() if recharge is not None and recharge > 0 else None
    effective = (fit.damagePattern.effectivify(drone,regen,'shield')
                 if regen is not None and fit.damagePattern is not None else regen)
    add('shield_regen','Peak shield regeneration per drone','HP/s',regen)
    add('effective_shield_regen','Effective peak shield regeneration per drone','EHP/s',effective)
    for key, damage, unit in (('dps',drone.getDps(fit.targetProfile),'HP/s'),
                              ('volley',drone.getVolley(fit.targetProfile),'HP')):
        for kind in ('em','thermal','kinetic','explosive','total'):
            add(key+'_'+kind, kind.capitalize()+' stack '+key,unit,
                getattr(damage,kind) if drone.dealsDamage else None)
    add('mining_yield','Stack mining yield','m3/s',drone.getMiningYPS() if drone.mines else None)
    add('mining_drain','Stack mining depletion','m3/s',drone.getMiningDPS() if drone.mines else None)
    remote = drone.getRemoteReps()
    for kind in ('shield','armor','hull','capacitor'):
        attr = dict(shield='shieldBonus',armor='armorDamageAmount',hull='structureDamageAmount',capacitor='powerTransferAmount')[kind]
        add('remote_'+kind,'Stack remote '+kind,'GJ/s' if kind=='capacitor' else 'HP/s',
            getattr(remote,kind) if drone.getModifiedItemAttr(attr) is not None else None)
    add('range','Optimal / maximum range','m',drone.maxRange)
    add('falloff','Falloff','m',drone.falloff)
    for key,label,unit in ATTRIBUTES:
        add(key,label,unit,drone.getModifiedItemAttr(key))
    return rows


def details(engine, fit):
    engine._check_fit(fit)
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    from .drone_records import capture
    rows = []
    for index,drone in enumerate(fit.drones):
        mutation = capture(drone).get('mutation')
        if mutation is not None:
            mutation = dict(mutation,base_name=drone.baseItem.name,mutaplasmid_name=drone.mutaplasmid.item.name)
        rows.append(dict(index=index,object_key=identity(fit,drone),item_id=drone.itemID,
            name=drone.fullName,group=drone.item.group.name,amount=drone.amount,active=drone.amountActive,
            mutation=mutation,metrics=metrics(drone,fit)))
    return dict(stacks=rows,active=fit.activeDrones,active_limit=fit.extraAttributes['maxActiveDrones'],
                bay_used=fit.droneBayUsed,bay_capacity=fit.ship.getModifiedItemAttr('droneCapacity'),
                bandwidth_used=fit.droneBandwidthUsed,bandwidth_capacity=fit.ship.getModifiedItemAttr('droneBandwidth'))
