# =============================================================================
# Copyright (C) 2010 Diego Duclos
#
# This file is part of pyfa.
#
# pyfa is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyfa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyfa.  If not, see <http://www.gnu.org/licenses/>.
# =============================================================================


# G05.1 headless copies of original graph calculations. AST bodies are unchanged.
# GUI settings are request-local; null-time cache entry cannot generate cycles.
import math
from abc import ABCMeta, abstractmethod
from contextvars import ContextVar
from contextlib import contextmanager
import eos.config
from eos.calc import calculateRangeFactor
from eos.utils.float import floatUnerr
from eos.utils.spoolSupport import SpoolOptions, SpoolType
from eos.utils.stats import RRTypes

_settings = ContextVar('remote_repair_graph_settings')

class GraphSettings:
    @staticmethod
    def getInstance():
        return _settings.get()

@contextmanager
def graph_settings(ignore_lock_range, ignore_drone_control_range):
    if type(ignore_lock_range) is not bool or type(ignore_drone_control_range) is not bool:
        raise ValueError('Graph settings must be explicit booleans')
    token = _settings.set({'ignoreLockRange': ignore_lock_range, 'ignoreDCR': ignore_drone_control_range})
    try:
        yield
    finally:
        _settings.reset(token)

class CurrentRateCache:
    def prepareRpsData(self, src, ancReload, maxTime):
        if maxTime is not None:
            raise ValueError('Only current remote repair rates are supported')
        return True

class PointGetter(metaclass=ABCMeta):

    def __init__(self, graph):
        self.graph = graph

    @abstractmethod
    def getRange(self, xRange, miscParams, src, tgt):
        raise NotImplementedError

    @abstractmethod
    def getPoint(self, x, miscParams, src, tgt):
        raise NotImplementedError


class SmoothPointGetter(PointGetter, metaclass=ABCMeta):

    _baseResolution = 200
    _extraDepth = 0

    def getRange(self, xRange, miscParams, src, tgt):
        xs = []
        ys = []
        commonData = self._getCommonData(miscParams=miscParams, src=src, tgt=tgt)

        def addExtraPoints(x1, y1, x2, y2, depth):
            if depth <= 0 or y1 == y2:
                return
            newX = (x1 + x2) / 2
            newY = self._calculatePoint(x=newX, miscParams=miscParams, src=src, tgt=tgt, commonData=commonData)
            addExtraPoints(x1=prevX, y1=prevY, x2=newX, y2=newY, depth=depth - 1)
            xs.append(newX)
            ys.append(newY)
            addExtraPoints(x1=newX, y1=newY, x2=x2, y2=y2, depth=depth - 1)

        prevX = None
        prevY = None
        # Go through X points defined by our resolution setting
        for x in self._xIterLinear(xRange):
            y = self._calculatePoint(x=x, miscParams=miscParams, src=src, tgt=tgt, commonData=commonData)
            if prevX is not None and prevY is not None:
                # And if Y values of adjacent data points are not equal, add extra points
                # depending on extra depth setting
                addExtraPoints(x1=prevX, y1=prevY, x2=x, y2=y, depth=self._extraDepth)
            prevX = x
            prevY = y
            xs.append(x)
            ys.append(y)
        return xs, ys

    def getPoint(self, x, miscParams, src, tgt):
        commonData = self._getCommonData(miscParams=miscParams, src=src, tgt=tgt)
        return self._calculatePoint(x=x, miscParams=miscParams, src=src, tgt=tgt, commonData=commonData)

    def _xIterLinear(self, xRange):
        xLow = min(xRange)
        xHigh = max(xRange)
        # Resolution defines amount of ranges between points here,
        # not amount of points
        step = (xHigh - xLow) / self._baseResolution
        if step == 0 or math.isnan(step):
            yield xLow
        else:
            for i in range(self._baseResolution + 1):
                yield xLow + step * i

    def _getCommonData(self, miscParams, src, tgt):
        return {}

    @abstractmethod
    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        raise NotImplementedError


def checkLockRange(src, distance):
    if distance is None:
        return True
    if GraphSettings.getInstance().get('ignoreLockRange'):
        return True
    return distance <= src.item.maxTargetRange


def checkDroneControlRange(src, distance):
    if distance is None:
        return True
    if GraphSettings.getInstance().get('ignoreDCR'):
        return True
    return distance <= src.item.extraAttributes['droneControlRange']


def getApplicationPerKey(src, distance):
    inLockRange = checkLockRange(src=src, distance=distance)
    inDroneRange = checkDroneControlRange(src=src, distance=distance)
    applicationMap = {}
    for mod in src.item.activeModulesIter():
        if not mod.isRemoteRepping():
            continue
        if not inLockRange:
            applicationMap[mod] = 0
        else:
            applicationMap[mod] = calculateRangeFactor(
                srcOptimalRange=mod.maxRange or 0,
                srcFalloffRange=mod.falloff or 0,
                distance=distance)
    for drone in src.item.activeDronesIter():
        if not drone.isRemoteRepping():
            continue
        if not inLockRange or not inDroneRange:
            applicationMap[drone] = 0
        else:
            applicationMap[drone] = 1
    # Ensure consistent results - round off a little to avoid float errors
    for k, v in applicationMap.items():
        applicationMap[k] = floatUnerr(v)
    return applicationMap


def applyReps(rrMap, applicationMap):
    totalAmount = RRTypes(shield=0, armor=0, hull=0, capacitor=0)
    for key, repAmount in rrMap.items():
        totalAmount += repAmount * applicationMap.get(key, 0)
    # We do not want to include energy transfers into final value
    totalReps = totalAmount.shield + totalAmount.armor + totalAmount.hull
    return totalReps


class YRpsMixin:

    def _getRepsPerKey(self, src, ancReload, time):
        # Use data from time cache if time was not specified
        if time is not None:
            return self._getTimeCacheDataPoint(src=src, ancReload=ancReload, time=time)
        # Compose map ourselves using current fit settings if time is not specified
        rpsMap = {}
        defaultSpoolValue = eos.config.settings['globalDefaultSpoolupPercentage']
        for mod in src.item.activeModulesIter():
            if not mod.isRemoteRepping():
                continue
            isAncShield = 'shipModuleAncillaryRemoteShieldBooster' in mod.item.effects
            isAncArmor = 'shipModuleAncillaryRemoteArmorRepairer' in mod.item.effects
            rpsMap[mod] = mod.getRemoteReps(
                spoolOptions=SpoolOptions(SpoolType.SPOOL_SCALE, defaultSpoolValue, False),
                reloadOverride=ancReload if (isAncShield or isAncArmor) else None)
        for drone in src.item.activeDronesIter():
            if not drone.isRemoteRepping():
                continue
            rpsMap[drone] = drone.getRemoteReps()
        return rpsMap

    def _prepareTimeCache(self, src, ancReload, maxTime):
        self.graph._timeCache.prepareRpsData(src=src, ancReload=ancReload, maxTime=maxTime)

    def _getTimeCacheData(self, src, ancReload):
        return self.graph._timeCache.getRpsData(src=src, ancReload=ancReload)

    def _getTimeCacheDataPoint(self, src, ancReload, time):
        return self.graph._timeCache.getRpsDataPoint(src=src, ancReload=ancReload, time=time)


class XDistanceMixin(SmoothPointGetter):

    _baseResolution = 50
    _extraDepth = 2

    def _getCommonData(self, miscParams, src, tgt):
        # Prepare time cache here because we need to do it only once,
        # and this function is called once per point info fetch
        self._prepareTimeCache(src=src, ancReload=miscParams['ancReload'], maxTime=miscParams['time'])
        return {'rrMap': self._getRepsPerKey(src=src, ancReload=miscParams['ancReload'], time=miscParams['time'])}

    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        distance = x
        applicationMap = getApplicationPerKey(src=src, distance=distance)
        y = applyReps(
            rrMap=commonData['rrMap'],
            applicationMap=applicationMap)
        return y


class Distance2RpsGetter(XDistanceMixin, YRpsMixin):
    pass


class ShieldRRColumn:

    def _getValue(self, fit):
        defaultSpoolValue = eos.config.settings['globalDefaultSpoolupPercentage']
        return fit.getRemoteReps(spoolOptions=SpoolOptions(SpoolType.SPOOL_SCALE, defaultSpoolValue, False)).shield, 'HP/s'

class ArmorRRColumn:

    def _getValue(self, fit):
        defaultSpoolValue = eos.config.settings['globalDefaultSpoolupPercentage']
        return fit.getRemoteReps(spoolOptions=SpoolOptions(SpoolType.SPOOL_SCALE, defaultSpoolValue, False)).armor, 'HP/s'

class HullRRColumn:

    def _getValue(self, fit):
        defaultSpoolValue = eos.config.settings['globalDefaultSpoolupPercentage']
        return fit.getRemoteReps(spoolOptions=SpoolOptions(SpoolType.SPOOL_SCALE, defaultSpoolValue, False)).hull, 'HP/s'

