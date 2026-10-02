"""C01.1 read-only fitting resources from EOS and pinned desktop display policy.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source: gui/builtinStatsViews/resourcesViewFull.py at
8b04f3b271e614b3e103853b44a7851a63d79d0e. No fitting formula is recalculated here.
"""
import math
from .number_format import formatAmount


def _number(value):
    if value is None:
        return 'unavailable'
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Resource value must be a finite number or explicit null')
    return 'integer' if type(value) is int else 'decimal'


def details(engine, fit):
    engine._check_fit(fit)
    from eos.const import FittingHardpoint
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    ship = fit.ship.getModifiedItemAttr
    rows = (
        ('turret_hardpoints', fit.getHardpointsUsed(FittingHardpoint.TURRET), ship('turretSlotsLeft'), 'count', 0, 0),
        ('launcher_hardpoints', fit.getHardpointsUsed(FittingHardpoint.MISSILE), ship('launcherSlotsLeft'), 'count', 0, 0),
        ('active_drones', fit.activeDrones, fit.extraAttributes['maxActiveDrones'], 'count', 0, 0),
        ('fighter_tubes', fit.fighterTubesUsed, fit.fighterTubesTotal, 'count', 3, 9),
        ('calibration', fit.calibrationUsed, ship('upgradeCapacity'), 'points', 0, 0),
        ('cpu', fit.cpuUsed, ship('cpuOutput'), 'tf', 4, 9),
        ('powergrid', fit.pgUsed, ship('powerOutput'), 'MW', 4, 9),
        ('drone_bay', fit.droneBayUsed, ship('droneCapacity'), 'm³', 3, 9),
        ('fighter_bay', fit.fighterBayUsed, ship('fighterCapacity'), 'm³', 3, 9),
        ('drone_bandwidth', fit.droneBandwidthUsed, ship('droneBandwidth'), 'Mbit/s', 3, 9),
        ('cargo_bay', fit.cargoBayUsed, ship('capacity'), 'm³', 3, 9),
    )
    result = {}
    for name, used, total, unit, precision, highest in rows:
        used_type, total_type = _number(used), _number(total)
        result[name] = dict(used=used, total=total, used_type=used_type, total_type=total_type,
            unit=unit, overloaded=None if used is None or total is None else used > total,
            used_display=None if used is None else formatAmount(used, precision, 0, highest),
            total_display=None if total is None else formatAmount(total, precision, 0, highest),
            used_detail=None if used is None else '%.1f' % used,
            total_detail=None if total is None else '%.1f' % total)
    return {'resources': result}
