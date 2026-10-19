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




# G04 headless original graph methods; AST correspondence is tested.
import math
from abc import ABCMeta, abstractmethod
from eos.utils.float import floatUnerr


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
        for x in self._xIterLinear(xRange):
            y = self._calculatePoint(x=x, miscParams=miscParams, src=src, tgt=tgt, commonData=commonData)
            if prevX is not None and prevY is not None:
                addExtraPoints(x1=prevX, y1=prevY, x2=x, y2=y, depth=self._extraDepth)
            prevX = x
            prevY = y
            xs.append(x)
            ys.append(y)
        return (xs, ys)

    def getPoint(self, x, miscParams, src, tgt):
        commonData = self._getCommonData(miscParams=miscParams, src=src, tgt=tgt)
        return self._calculatePoint(x=x, miscParams=miscParams, src=src, tgt=tgt, commonData=commonData)

    def _xIterLinear(self, xRange):
        xLow = min(xRange)
        xHigh = max(xRange)
        step = (xHigh - xLow) / self._baseResolution
        if step == 0 or math.isnan(step):
            yield xLow
        else:
            for i in range(self._baseResolution + 1):
                yield (xLow + step * i)

    def _getCommonData(self, miscParams, src, tgt):
        return {}

    @abstractmethod
    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        raise NotImplementedError

class FitGraph:
    def _calcPlotPoints(self, mainInput, miscInputs, xSpec, ySpec, src, tgt):
        mainParamRange = self._normalizeMain(mainInput=mainInput, src=src, tgt=tgt)
        miscParams = self._normalizeMisc(miscInputs=miscInputs, src=src, tgt=tgt)
        mainParamRange = self._limitMain(mainParamRange=mainParamRange, src=src, tgt=tgt)
        miscParams = self._limitMisc(miscParams=miscParams, src=src, tgt=tgt)
        xs, ys = self._getPlotPoints(xRange=mainParamRange[1], miscParams=miscParams, xSpec=xSpec, ySpec=ySpec, src=src, tgt=tgt)
        ys = self._denormalizeValues(values=ys, axisSpec=ySpec, src=src, tgt=tgt)
        try:
            xs = self._denormalizeValues(values=xs, axisSpec=xSpec, src=src, tgt=tgt)
        except ZeroDivisionError:
            if mainInput.unit == xSpec.unit == '%' and len(set((floatUnerr(y) for y in ys))) == 1:
                xs = [min(mainInput.value), max(mainInput.value)]
                ys = [ys[0], ys[0]]
            else:
                raise
        else:
            if mainInput.unit == xSpec.unit == '%' and all((math.isnan(x) for x in xs)):
                xs = [min(mainInput.value), max(mainInput.value)]
                ys = [ys[0], ys[0]]
        return (xs, ys)
    def _normalizeMain(self, mainInput, src, tgt):
        key = (mainInput.handle, mainInput.unit)
        if key in self._normalizers:
            normalizer = self._normalizers[key]
            mainParamRange = (mainInput.handle, tuple((normalizer(v, src, tgt) for v in mainInput.value)))
        else:
            mainParamRange = (mainInput.handle, mainInput.value)
        return mainParamRange
    def _normalizeMisc(self, miscInputs, src, tgt):
        miscParams = {}
        for miscInput in miscInputs:
            key = (miscInput.handle, miscInput.unit)
            if key in self._normalizers:
                normalizer = self._normalizers[key]
                miscParams[miscInput.handle] = normalizer(miscInput.value, src, tgt)
            else:
                miscParams[miscInput.handle] = miscInput.value
        return miscParams
    def _limitMain(self, mainParamRange, src, tgt):
        mainHandle, mainValue = mainParamRange
        if mainHandle in self._limiters:
            limiter = self._limiters[mainHandle]
            mainParamRange = (mainHandle, tuple((self.__limitToRange(v, limiter(src, tgt)) for v in mainValue)))
        return mainParamRange
    def _limitMisc(self, miscParams, src, tgt):
        for miscHandle in miscParams:
            if miscHandle in self._limiters:
                limiter = self._limiters[miscHandle]
                miscValue = miscParams[miscHandle]
                miscParams[miscHandle] = self.__limitToRange(miscValue, limiter(src, tgt))
        return miscParams
    @staticmethod
    def __limitToRange(val, limitRange):
        if val is None:
            return None
        val = max(val, min(limitRange))
        val = min(val, max(limitRange))
        return val
    def _getPlotPoints(self, xRange, miscParams, xSpec, ySpec, src, tgt):
        try:
            getterClass = self._getters[xSpec.handle, ySpec.handle]
        except KeyError:
            return ([], [])
        else:
            getter = getterClass(graph=self)
            return getter.getRange(xRange=xRange, miscParams=miscParams, src=src, tgt=tgt)
    def _denormalizeValues(self, values, axisSpec, src, tgt):
        key = (axisSpec.handle, axisSpec.unit)
        if key in self._denormalizers:
            denormalizer = self._denormalizers[key]
            values = [denormalizer(v, src, tgt) for v in values]
        return values

class Time2ShieldAmountGetter(SmoothPointGetter):

    def _getCommonData(self, miscParams, src, tgt):
        return {'maxShieldAmount': src.item.ship.getModifiedItemAttr('shieldCapacity'), 'shieldRegenTime': src.item.ship.getModifiedItemAttr('shieldRechargeRate') / 1000}

    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        time = x
        shieldAmount = calculateShieldAmount(maxShieldAmount=commonData['maxShieldAmount'], shieldRegenTime=commonData['shieldRegenTime'], shieldAmountT0=miscParams['shieldAmountT0'] or 0, time=time)
        return shieldAmount

class Time2ShieldRegenGetter(SmoothPointGetter):

    def _getCommonData(self, miscParams, src, tgt):
        return {'maxShieldAmount': src.item.ship.getModifiedItemAttr('shieldCapacity'), 'shieldRegenTime': src.item.ship.getModifiedItemAttr('shieldRechargeRate') / 1000}

    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        time = x
        shieldAmount = calculateShieldAmount(maxShieldAmount=commonData['maxShieldAmount'], shieldRegenTime=commonData['shieldRegenTime'], shieldAmountT0=miscParams['shieldAmountT0'] or 0, time=time)
        shieldRegen = calculateShieldRegen(maxShieldAmount=commonData['maxShieldAmount'], shieldRegenTime=commonData['shieldRegenTime'], currentShieldAmount=shieldAmount)
        return shieldRegen

class ShieldAmount2ShieldAmountGetter(SmoothPointGetter):

    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        shieldAmount = x
        return shieldAmount

class ShieldAmount2ShieldRegenGetter(SmoothPointGetter):

    def _getCommonData(self, miscParams, src, tgt):
        return {'maxShieldAmount': src.item.ship.getModifiedItemAttr('shieldCapacity'), 'shieldRegenTime': src.item.ship.getModifiedItemAttr('shieldRechargeRate') / 1000}

    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        shieldAmount = x
        shieldRegen = calculateShieldRegen(maxShieldAmount=commonData['maxShieldAmount'], shieldRegenTime=commonData['shieldRegenTime'], currentShieldAmount=shieldAmount)
        return shieldRegen

def calculateShieldAmount(maxShieldAmount, shieldRegenTime, shieldAmountT0, time):
    return maxShieldAmount * (1 + math.exp(5 * -time / shieldRegenTime) * (math.sqrt(shieldAmountT0 / maxShieldAmount) - 1)) ** 2

def calculateShieldRegen(maxShieldAmount, shieldRegenTime, currentShieldAmount):
    return 10 * maxShieldAmount / shieldRegenTime * (math.sqrt(currentShieldAmount / maxShieldAmount) - currentShieldAmount / maxShieldAmount)

class FitShieldRegenGraph(FitGraph):
    _normalizers = {('shieldAmount', '%'): lambda v, src, tgt: v / 100 * src.item.ship.getModifiedItemAttr('shieldCapacity'), ('shieldAmountT0', '%'): lambda v, src, tgt: None if v is None else v / 100 * src.item.ship.getModifiedItemAttr('shieldCapacity'), ('shieldAmount', 'EHP'): lambda v, src, tgt: v / src.item.damagePattern.effectivify(src.item.ship, 1, 'shield')}
    _limiters = {'shieldAmount': lambda src, tgt: (0, src.item.ship.getModifiedItemAttr('shieldCapacity')), 'shieldAmountT0': lambda src, tgt: (0, src.item.ship.getModifiedItemAttr('shieldCapacity'))}
    _getters = {('time', 'shieldAmount'): Time2ShieldAmountGetter, ('time', 'shieldRegen'): Time2ShieldRegenGetter, ('shieldAmount', 'shieldAmount'): ShieldAmount2ShieldAmountGetter, ('shieldAmount', 'shieldRegen'): ShieldAmount2ShieldRegenGetter}
    _denormalizers = {('shieldAmount', '%'): lambda v, src, tgt: v * 100 / src.item.ship.getModifiedItemAttr('shieldCapacity'), ('shieldAmount', 'EHP'): lambda v, src, tgt: src.item.damagePattern.effectivify(src.item.ship, v, 'shield'), ('shieldRegen', 'EHP/s'): lambda v, src, tgt: src.item.damagePattern.effectivify(src.item.ship, v, 'shield')}

class ShieldAmountColumn:
    def _getValue(self, fit):
        return (fit.ship.getModifiedItemAttr('shieldCapacity'), 'HP')

class ShieldTimeColumn:
    def _getValue(self, fit):
        return (fit.ship.getModifiedItemAttr('shieldRechargeRate') / 1000, 's')
