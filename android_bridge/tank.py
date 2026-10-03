"""C01.3.2 tank values from EOS and pinned recharge-view presentation.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Formatting follows gui/builtinStatsViews/rechargeViewFull.py at
8b04f3b271e614b3e103853b44a7851a63d79d0e. No fitting formula lives here.
"""
from .defenses import scalar
from .number_format import formatAmount

REPAIRS = ('shieldRepair', 'armorRepair', 'hullRepair')


def details(engine, fit):
    engine._check_fit(fit)
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    modes = {}
    for mode, unit, reinforced, sustained in (
        ('raw', 'HP/s', fit.tank, fit.sustainableTank),
        ('effective', 'EHP/s', fit.effectiveTank, fit.effectiveSustainableTank),
    ):
        value = reinforced['passiveShield']
        passive = scalar(value, unit, None if value is None else formatAmount(value, 3, 0, 9),
                         None if value is None else '%.3f' % value)
        rows = {}
        for stability, source in (('reinforced', reinforced), ('sustained', sustained)):
            pre, full = source['armorRepairPreSpool'], source['armorRepairFullSpool']
            indication = (pre is not None and full is not None and round(pre, 1) != round(full, 1))
            repairs = {}
            for name in REPAIRS:
                value = source[name]
                display = None if value is None else '{:.1f}{}'.format(value, '\u02e2' if name == 'armorRepair' and indication else '')
                repairs[name] = scalar(value, unit, display, None if value is None else '{:.1f}'.format(value))
            spool = {}
            for name, value in (('pre', pre), ('full', full)):
                spool[name] = scalar(value, unit, None if value is None else '{:.1f}'.format(value),
                                     None if value is None else '{:.1f}'.format(value))
            rows[stability] = dict(repairs=repairs, armor_spool=dict(
                **spool, indicated=indication,
                tooltip='Spool up: {:.1f}-{:.1f}'.format(pre, full) if indication else ''))
        modes[mode] = dict(passive_shield=passive, **rows)
    return dict(tank=modes)
