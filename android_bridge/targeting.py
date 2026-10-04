"""C03.1 EOS targeting/navigation with pinned desktop presentation.

GPL-3.0-or-later; see LICENSE. Presentation follows targetingMiscViewMinimal
at 8b04f3b271e614b3e103853b44a7851a63d79d0e. EOS owns all fitting formulas.
"""
from .defenses import scalar
from .number_format import formatAmount

HOLDS = (
 ('fleetHangarCapacity','Fleet hangar'),('shipMaintenanceBayCapacity','Maintenance bay'),
 ('specialColonyResourcesHoldCapacity','Infrastructure hold'),('specialAmmoHoldCapacity','Ammo hold'),
 ('specialFuelBayCapacity','Fuel bay'),('specialShipHoldCapacity','Ship hold'),
 ('specialSmallShipHoldCapacity','Small ship hold'),('specialMediumShipHoldCapacity','Medium ship hold'),
 ('specialLargeShipHoldCapacity','Large ship hold'),('specialIndustrialShipHoldCapacity','Industrial ship hold'),
 ('generalMiningHoldCapacity','Mining hold'),('specialIceHoldCapacity','Ice hold'),
 ('specialGasHoldCapacity','Gas hold'),('specialMineralHoldCapacity','Mineral hold'),
 ('specialMaterialBayCapacity','Material bay'),('specialSalvageHoldCapacity','Salvage hold'),
 ('specialCommandCenterHoldCapacity','Command center hold'),('specialPlanetaryCommoditiesHoldCapacity','Planetary goods hold'),
 ('specialQuafeHoldCapacity','Quafe hold'),('specialMobileDepotHoldCapacity','Mobile depot hold'),
 ('specialExpeditionHoldCapacity','Expedition hold'))
RADII = (('Pod',25),('Interceptor',33),('Frigate',38),('Destroyer',83),
         ('Cruiser',130),('Battlecruiser',265),('Battleship',420),('Carrier',3000))


def amount(value,unit,precision=3):
    text=None if value is None else formatAmount(value,precision,0,0)
    return scalar(value,unit,text,text)


def details(engine,fit):
    engine._check_fit(fit)
    if not fit.calculated:fit.calculateModifiedAttributes()
    ship=fit.ship.getModifiedItemAttr
    sensor,jam=fit.scanStrength,fit.jamChance
    jam_rounded=round(jam,1)
    locks=[dict(name=name,radius=radius,time=scalar(fit.calculateLockTime(radius),'s',
           '%.1fs'%fit.calculateLockTime(radius),'%.1fs'%fit.calculateLockTime(radius))) for name,radius in RADII]
    lock_tip='Lock Times'.center(30)+'\n'+''.join('%5s\t%s [%d]\n'%(row['time']['display'],row['name'],row['radius']) for row in locks)
    mass,agility=ship('mass'),ship('agility') or 0
    align_tip='Align:\t%.3fs\nMass:\t{:,.0f}kg\nAgility:\t%.3fx'.format(mass)%(fit.alignTime,agility)
    core=-ship('warpScrambleStatus') if ship('warpScrambleStatus') else 0
    warp_tip='Max Warp Distance: %.1f AU\nWarp Core Strength: %.1f'%(fit.maxWarpDistance,core)
    holds=[dict(attribute=key,name=name,present=(ship(key,default=None) or 0)>0,
                capacity=amount(ship(key,default=None),'m³',4)) for key,name in HOLDS]
    # The original aggregate includes every listed hold, including maintenance.
    # Preserve EOS's actual zero/default and expose absence separately, like the original tooltip.
    additional=sum(row['capacity']['value'] or 0 for row in holds)
    cargo=ship('capacity')
    cargo_label=formatAmount(cargo,4,0,9)+('+'+formatAmount(additional,4,0,9) if additional>0 else '')+' m³'
    cargo_tip='Cargohold: {:,.2f}m³ / {:,.2f}m³'.format(fit.cargoBayUsed,cargo)
    cargo_tip+=''.join('\n{}: {:,.2f}m³'.format(row['name'],row['capacity']['value']) for row in holds if (row['capacity']['value'] or 0)>0)
    sensor_label=formatAmount(sensor,3,0,0)+(' ({}%)'.format(formatAmount(jam_rounded,3,0,0)) if jam_rounded else '')
    sensor_tip='Type: '+fit.scanType+('\n{}% chance to be jammed'.format(formatAmount(jam_rounded,3,0,0)) if jam_rounded>0 else '')
    rows=(('targets',fit.maxTargets,'count',fit.maxTargets,'',0,'%.1f'%fit.maxTargets),
          ('range',fit.maxTargetRange,'m',fit.maxTargetRange/1000,'km',0,'%.1f'%(fit.maxTargetRange/1000)),
          ('scan_resolution',ship('scanResolution'),'mm',ship('scanResolution'),'mm',0,lock_tip),
          ('drone_range',fit.extraAttributes['droneControlRange'],'m',fit.extraAttributes['droneControlRange']/1000,'km',0,'%.1f'%(fit.extraAttributes['droneControlRange']/1000)),
          ('speed',fit.maxSpeed,'m/s',fit.maxSpeed,'m/s',0,'%.1f'%fit.maxSpeed),
          ('align',fit.alignTime,'s',fit.alignTime,'s',0,align_tip),
          ('signature',ship('signatureRadius'),'m',ship('signatureRadius'),'',9,'Probe Size: %.3f'%(fit.probeSize or 0)),
          ('warp_speed',fit.warpSpeed,'AU/s',fit.warpSpeed,'AU/s',0,warp_tip))
    main={key:scalar(raw,unit,formatAmount(display,3,0,highest)+' '+suffix,tip) for key,raw,unit,display,suffix,highest,tip in rows}
    main['sensor']=scalar(sensor,'points',sensor_label,sensor_tip)
    main['cargo']=scalar(cargo,'m³',cargo_label,cargo_tip)
    return dict(targeting=dict(main=main,lock_times=locks,sensor_type=fit.scanType,jam_chance=amount(jam,'%'),
        mass=amount(mass,'kg'),agility=amount(agility,'x'),probe_size=amount(fit.probeSize,'x'),
        warp_distance=amount(fit.maxWarpDistance,'AU'),warp_core=amount(core,'points'),
        cargo_used=amount(fit.cargoBayUsed,'m³',4),additional_cargo=amount(additional,'m³',4),holds=holds))
