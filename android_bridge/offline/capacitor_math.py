"""Unchanged capacitor expressions from the pinned Pyfa graph getter.

Source: graphs/data/fitCapacitor/getter.py, calculateCapAmount / calculateCapRegen.
Reference: 8b04f3b271e614b3e103853b44a7851a63d79d0e.
Copyright (C) 2010 Diego Duclos; Pyfa contributors.
GPL-3.0-or-later. This is part of Pyfa, distributed without any warranty.
See the accompanying LICENSE for the full license.

These are source expressions, not independently approximated capacitor physics.
The boundary validates their domain before calling them.
"""
import math


def calculateCapAmount(maxCapAmount, capRegenTime, capAmountT0, time):
    return maxCapAmount * (1 + math.exp(5 * -time / capRegenTime) * (math.sqrt(capAmountT0 / maxCapAmount) - 1)) ** 2


def calculateCapRegen(maxCapAmount, capRegenTime, currentCapAmount):
    return 10 * maxCapAmount / capRegenTime * (math.sqrt(currentCapAmount / maxCapAmount) - currentCapAmount / maxCapAmount)
