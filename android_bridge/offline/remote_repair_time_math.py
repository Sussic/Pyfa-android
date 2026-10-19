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


from copy import copy

from eos.utils.float import floatUnerr
from eos.utils.spoolSupport import SpoolOptions, SpoolType
from eos.utils.stats import RRTypes
from android_bridge.projected_drone_admission import AdmissionRejected
from .remote_repair_schedule import capture_schedule, reconstruct_schedule
import math


class CheckedTimeCache:
    """Original cache arithmetic with request-local isolation and checked hooks.

    Reservations monotonically charge the whole request, not inferred live bytes.
    An individual EOS method cannot be cooperatively preempted. Its known bounded
    constructor/map allocations are reserved before entry; every surrounding scan,
    insertion, copy and yielded cycle has a cooperative boundary.
    """
    def __init__(self, check, reserve):
        self.check = check
        self._reserve = reserve
        self._charged = 0
        self.reserve('container', 3)
        self._data = {}
        self._schedules = {}
        self._active = {}

    def reserve(self, kind, count=1):
        self.check()
        if type(count) is not int or count < 0 or count > 2**63 - 1 - self._charged:
            raise AdmissionRejected('Remote repair resource accounting overflow')
        self._reserve(kind, count)
        self._charged += count

    def clearAll(self):
        self._data.clear()
        self._schedules.clear()
        self._active.clear()

    def _capture(self, src, ancReload, horizon):
        self.check()
        for family, rows in (('module', src.item.modules), ('drone', src.item.drones)):
            for row in rows:
                self.reserve('container_row', 1)
        for family, rows in (('module', src.item.activeModulesIter()), ('drone', src.item.activeDronesIter())):
            self.reserve('container', 1)
            active = []
            for row in rows:
                self.reserve('scan', 1)
                if not row.isRemoteRepping():
                    continue
                self.reserve('list_slot', 1)
                active.append(row)
                ancillary = family == 'module' and (
                    'shipModuleAncillaryRemoteShieldBooster' in row.item.effects or
                    'shipModuleAncillaryRemoteArmorRepairer' in row.item.effects)
                # EOS module constructors allocate at most one sequence/two leaves.
                self.reserve('schedule_constructor', 3 if family == 'module' else 1)
                schedule = row.getCycleParameters(reloadOverride=ancReload if ancillary else True)
                if schedule is None:
                    frozen = None
                else:
                    frozen, bound = capture_schedule(schedule, horizon, self.check, self.reserve, module=family == 'module')
                    frozen = (frozen, bound)
                self.reserve('mapping_slot', 1)
                self._schedules[row] = frozen
            self.reserve('mapping_slot', 1)
            self._active[family] = active

    def _schedule(self, row):
        frozen = self._schedules[row]
        if frozen is None:
            return None
        schedule, bound = frozen
        clone = reconstruct_schedule(schedule, self.check, self.reserve)
        owner = self
        class CheckedCycles:
            def iterCycles(self):
                count = 0
                for cycle in clone.iterCycles():
                    owner.reserve('cycle', 1)
                    count += 1
                    if count > bound:
                        raise AdmissionRejected('Remote repair schedule exceeded its validated bound')
                    yield cycle
        return CheckedCycles()

    def _repair_parameters(self, row, module=False, **kwargs):
        # Bound comes from the pinned EOS constructors: module <=1 offset,
        # drone <=2 offsets. Reserve their maps, RRTypes and temporary scalars
        # before the indivisible original call, then check the returned shape.
        self.reserve('repair_parameter_call', 1)
        if module:
            self.reserve('container', 1)
            self.reserve('mapping_slot', 7)  # original remoteModuleGroups per call
        maximum = 1 if module else 2
        self.reserve('container', 2)
        self.reserve('mapping_slot', 2 * maximum)
        self.reserve('rr_value', 2 * maximum)
        values = row.getRepAmountParameters(**kwargs)
        if type(values) is not dict or len(values) > maximum:
            raise AdmissionRejected('Unsupported remote repair offset structure')
        for offset, amount in values.items():
            self.reserve('scan', 1)
            if type(offset) not in (int, float) or not math.isfinite(offset):
                raise ValueError('Invalid repair offset')
            if not isinstance(amount, RRTypes) or any(type(v) not in (int, float) or not math.isfinite(v) for v in amount):
                raise ValueError('Invalid repair amount')
        return values


    # Whole data getters
    def getRpsData(self, src, ancReload):
        """Return RPS data in {time: {key: rps}} format."""
        return self._data[src.item.ID][ancReload]['finalRps']

    def getRepAmountData(self, src, ancReload):
        """Return rep amount data in {time: {key: amount}} format."""
        return self._data[src.item.ID][ancReload]['finalRepAmount']

    # Specific data point getters
    def getRpsDataPoint(self, src, ancReload, time):
        """Get RPS data by specified time in {key: rps} format."""
        return self._getDataPoint(src=src, ancReload=ancReload, time=time, dataFunc=self.getRpsData)

    def getRepAmountDataPoint(self, src, ancReload, time):
        """Get rep amount data by specified time in {key: amount} format."""
        return self._getDataPoint(src=src, ancReload=ancReload, time=time, dataFunc=self.getRepAmountData)

    # Preparation functions
    def prepareRpsData(self, src, ancReload, maxTime):
        # Time is none means that time parameter has to be ignored,
        # we do not need cache for that
        if maxTime is None:
            return True
        self._generateInternalForm(src=src, ancReload=ancReload, maxTime=maxTime)
        fitCache = self._data[src.item.ID][ancReload]
        # Final cache has been generated already, don't do anything
        if 'finalRps' in fitCache:
            return
        # Convert cache from segments with assigned values into points
        # which are located at times when rps value changes
        self.reserve('container', 1)
        pointCache = {}
        self.check()
        for key, rpsList in fitCache['internalRps'].items():
            self.check()
            self.reserve('container', 1)
            self.reserve('mapping_slot', 1)
            pointData = pointCache[key] = {}
            prevRps = None
            prevTimeEnd = None
            self.check()
            for timeStart, timeEnd, rps in rpsList:
                self.check()
                # First item
                if not pointData:
                    self.reserve('mapping_slot', 1)
                    pointData[timeStart] = rps
                # Gap between items
                elif floatUnerr(prevTimeEnd) < floatUnerr(timeStart):
                    self.reserve('mapping_slot', 1)
                    self.reserve('rr_value', 1)
                    pointData[prevTimeEnd] = RRTypes(0, 0, 0, 0)
                    self.reserve('mapping_slot', 1)
                    pointData[timeStart] = rps
                # Changed value
                elif rps != prevRps:
                    self.reserve('mapping_slot', 1)
                    pointData[timeStart] = rps
                prevRps = rps
                prevTimeEnd = timeEnd
        # We have data in another form, do not need old one any longer
        del fitCache['internalRps']
        self.reserve('container', 1)
        changesByTime = {}
        self.check()
        for key, rpsMap in pointCache.items():
            self.check()
            for time in rpsMap:
                self.check()
                self.reserve('mapping_slot', 1)
                self.reserve('list_slot', 1)
                self.reserve('container', 1)
                changesByTime.setdefault(time, []).append(key)
        # Here we convert cache to following format:
        # {time: {key: rps}
        self.reserve('container', 1)
        self.reserve('mapping_slot', 1)
        finalRpsCache = fitCache['finalRps'] = {}
        self.reserve('container', 1)
        timeRpsData = {}
        self.reserve('container', 1)
        self.reserve('sort_slot', len(changesByTime))
        self.reserve('sort_work', len(changesByTime) * max(1, len(changesByTime).bit_length()))
        self.check()
        for time in sorted(changesByTime):
            self.check()
            self.reserve('container', 1)
            self.reserve('copy_slot', len(timeRpsData))
            timeRpsData = copy(timeRpsData)
            self.check()
            for key in changesByTime[time]:
                self.check()
                self.reserve('mapping_slot', 1)
                timeRpsData[key] = pointCache[key][time]
            self.reserve('mapping_slot', 1)
            finalRpsCache[time] = timeRpsData

    def prepareRepAmountData(self, src, ancReload, maxTime):
        # Time is none means that time parameter has to be ignored,
        # we do not need cache for that
        if maxTime is None:
            return
        self._generateInternalForm(src=src, ancReload=ancReload, maxTime=maxTime)
        fitCache = self._data[src.item.ID][ancReload]
        # Final cache has been generated already, don't do anything
        if 'finalRepAmount' in fitCache:
            return
        intCache = fitCache['internalRepAmount']
        self.reserve('container', 1)
        changesByTime = {}
        self.check()
        for key, remAmountMap in intCache.items():
            self.check()
            for time in remAmountMap:
                self.check()
                self.reserve('mapping_slot', 1)
                self.reserve('list_slot', 1)
                self.reserve('container', 1)
                changesByTime.setdefault(time, []).append(key)
        # Here we convert cache to following format:
        # {time: {key: hp repaired by key at this time}}
        self.reserve('container', 1)
        self.reserve('mapping_slot', 1)
        finalCache = fitCache['finalRepAmount'] = {}
        self.reserve('container', 1)
        timeRepAmountData = {}
        self.reserve('container', 1)
        self.reserve('sort_slot', len(changesByTime))
        self.reserve('sort_work', len(changesByTime) * max(1, len(changesByTime).bit_length()))
        self.check()
        for time in sorted(changesByTime):
            self.check()
            self.reserve('container', 1)
            self.reserve('copy_slot', len(timeRepAmountData))
            timeRepAmountData = copy(timeRepAmountData)
            self.check()
            for key in changesByTime[time]:
                self.check()
                keyRepAmount = intCache[key][time]
                if key in timeRepAmountData:
                    self.reserve('mapping_slot', 1)
                    self.reserve('rr_value', 1)
                    timeRepAmountData[key] = timeRepAmountData[key] + keyRepAmount
                else:
                    self.reserve('mapping_slot', 1)
                    timeRepAmountData[key] = keyRepAmount
            self.reserve('mapping_slot', 1)
            finalCache[time] = timeRepAmountData
        # We do not need internal cache once we have final
        del fitCache['internalRepAmount']

    # Private stuff
    def _generateInternalForm(self, src, ancReload, maxTime):
        if self._isTimeCacheValid(src=src, ancReload=ancReload, maxTime=maxTime):
            return
        self._capture(src, ancReload, maxTime)
        self.reserve('container', 1)
        self.reserve('mapping_slot', 3)
        self.reserve('container', 1)
        fitCache = self._data.setdefault(src.item.ID, {})[ancReload] = {'maxTime': maxTime}
        self.reserve('container', 1)
        self.reserve('mapping_slot', 1)
        intCacheRps = fitCache['internalRps'] = {}
        self.reserve('container', 1)
        self.reserve('mapping_slot', 1)
        intCacheRepAmount = fitCache['internalRepAmount'] = {}

        def addRps(rrKey, addedTimeStart, addedTimeFinish, addedRepAmounts):
            if not addedRepAmounts:
                return
            self.reserve('rr_value', 1 + len(addedRepAmounts))
            self.reserve('scan', len(addedRepAmounts))
            repAmountSum = sum(addedRepAmounts, RRTypes(0, 0, 0, 0))
            if repAmountSum.shield > 0 or repAmountSum.armor > 0 or repAmountSum.hull > 0:
                self.reserve('rr_value', 1)
                addedRps = repAmountSum / (addedTimeFinish - addedTimeStart)
                self.reserve('mapping_slot', 1)
                self.reserve('container', 1)
                rrCacheRps = intCacheRps.setdefault(rrKey, [])
                self.reserve('list_slot', 1)
                self.reserve('segment', 1)
                rrCacheRps.append((addedTimeStart, addedTimeFinish, addedRps))

        def addRepAmount(rrKey, addedTime, addedRepAmount):
            if addedRepAmount.shield > 0 or addedRepAmount.armor > 0 or addedRepAmount.hull > 0:
                self.reserve('mapping_slot', 2)
                self.reserve('container', 1)
                intCacheRepAmount.setdefault(rrKey, {})[addedTime] = addedRepAmount

        # Modules
        self.check()
        for mod in self._active['module']:
            self.check()
            if not mod.isRemoteRepping():
                continue
            isAncShield = 'shipModuleAncillaryRemoteShieldBooster' in mod.item.effects
            isAncArmor = 'shipModuleAncillaryRemoteArmorRepairer' in mod.item.effects
            if isAncShield or isAncArmor:
                cycleParams = self._schedule(mod)
            else:
                cycleParams = self._schedule(mod)
            if cycleParams is None:
                continue
            currentTime = 0
            nonstopCycles = 0
            cyclesWithoutReload = 0
            cyclesUntilReload = mod.numShots
            self.check()
            for cycleTimeMs, inactiveTimeMs, isInactivityReload in cycleParams.iterCycles():
                self.check()
                cyclesWithoutReload += 1
                self.reserve('container', 1)
                cycleRepAmounts = []
                repAmountParams = self._repair_parameters(mod, module=True, spoolOptions=SpoolOptions(SpoolType.CYCLES, nonstopCycles, True))
                self.check()
                for repTimeMs, repAmount in repAmountParams.items():
                    self.check()
                    # Loaded ancillary armor rep can keep running at less efficiency if we decide to not reload
                    if isAncArmor and mod.charge and not ancReload and cyclesWithoutReload > cyclesUntilReload:
                        self.reserve('rr_value', 1)
                        repAmount = repAmount / mod.getModifiedItemAttr('chargedArmorDamageMultiplier', 1)
                    self.reserve('list_slot', 1)
                    cycleRepAmounts.append(repAmount)
                    addRepAmount(mod, currentTime + repTimeMs / 1000, repAmount)
                addRps(mod, currentTime, currentTime + cycleTimeMs / 1000, cycleRepAmounts)
                if inactiveTimeMs > 0:
                    nonstopCycles = 0
                else:
                    nonstopCycles += 1
                if isInactivityReload:
                    cyclesWithoutReload = 0
                if currentTime > maxTime:
                    break
                currentTime += cycleTimeMs / 1000 + inactiveTimeMs / 1000
        # Drones
        self.check()
        for drone in self._active['drone']:
            self.check()
            if not drone.isRemoteRepping():
                continue
            cycleParams = self._schedule(drone)
            if cycleParams is None:
                continue
            currentTime = 0
            repAmountParams = self._repair_parameters(drone)
            self.check()
            for cycleTimeMs, inactiveTimeMs, isInactivityReload in cycleParams.iterCycles():
                self.check()
                self.reserve('container', 1)
                cycleRepAmounts = []
                self.check()
                for repTimeMs, repAmount in repAmountParams.items():
                    self.check()
                    self.reserve('list_slot', 1)
                    cycleRepAmounts.append(repAmount)
                    addRepAmount(drone, currentTime + repTimeMs / 1000, repAmount)
                addRps(drone, currentTime, currentTime + cycleTimeMs / 1000, cycleRepAmounts)
                if currentTime > maxTime:
                    break
                currentTime += cycleTimeMs / 1000 + inactiveTimeMs / 1000

    def _isTimeCacheValid(self, src, ancReload, maxTime):
        try:
            cacheMaxTime = self._data[src.item.ID][ancReload]['maxTime']
        except KeyError:
            return False
        return maxTime <= cacheMaxTime

    def _getDataPoint(self, src, ancReload, time, dataFunc):
        data = dataFunc(src=src, ancReload=ancReload)
        self.reserve('container', 1)
        timesBefore = []
        self.check()
        for t in data:
            self.check()
            self.reserve('scan', 1)
            if floatUnerr(t) <= floatUnerr(time):
                self.reserve('list_slot', 1)
                timesBefore.append(t)
        self.reserve('scan', len(timesBefore))
        try:
            time = max(timesBefore)
        except ValueError:
            self.reserve('container', 1)
            return {}
        else:
            return data[time]


from .remote_repair_math import (Distance2RpsGetter, checkLockRange,
                                 checkDroneControlRange, calculateRangeFactor)


class CheckedDistance2RpsGetter(Distance2RpsGetter):
    """Source point arithmetic/order with guarded application and aggregation."""
    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        cache = self.graph._timeCache
        cache.reserve('output_point', 1)
        applicationMap = checked_application(cache, src, x)
        return checked_apply(cache, commonData['rrMap'], applicationMap)


# Original graphs/data/fitRemoteReps/getter.py amount methods, unchanged.
# SHA-256: 6531618b3dc875602f1230b396bf6cf634a74aa58a27dad43bec62b21c0ff263
class YRepAmountMixin:

    def _getRepsPerKey(self, src, ancReload, time):
        # Total reps given makes no sense without time specified
        if time is None:
            raise ValueError
        return self._getTimeCacheDataPoint(src=src, ancReload=ancReload, time=time)

    def _prepareTimeCache(self, src, ancReload, maxTime):
        self.graph._timeCache.prepareRepAmountData(src=src, ancReload=ancReload, maxTime=maxTime)

    def _getTimeCacheData(self, src, ancReload):
        return self.graph._timeCache.getRepAmountData(src=src, ancReload=ancReload)

    def _getTimeCacheDataPoint(self, src, ancReload, time):
        return self.graph._timeCache.getRepAmountDataPoint(src=src, ancReload=ancReload, time=time)


class CheckedDistance2RepAmountGetter(YRepAmountMixin, CheckedDistance2RpsGetter):
    """Amount cache dispatch with the unchanged guarded distance application body.

    The amount mixin precedes inherited YRpsMixin in the MRO. XDistanceMixin
    supplies the original adaptive sampling and common-data preparation.
    """
    pass


def checked_application(cache, src, distance):
    inLockRange = checkLockRange(src=src, distance=distance)
    inDroneRange = checkDroneControlRange(src=src, distance=distance)
    cache.reserve('container', 1)
    applicationMap = {}
    for mod in src.item.activeModulesIter():
        cache.reserve('scan', 1)
        if not mod.isRemoteRepping():
            continue
        cache.reserve('mapping_slot', 1)
        if not inLockRange:
            applicationMap[mod] = 0
        else:
            applicationMap[mod] = calculateRangeFactor(
                srcOptimalRange=mod.maxRange or 0,
                srcFalloffRange=mod.falloff or 0,
                distance=distance)
    for drone in src.item.activeDronesIter():
        cache.reserve('scan', 1)
        if not drone.isRemoteRepping():
            continue
        cache.reserve('mapping_slot', 1)
        if not inLockRange or not inDroneRange:
            applicationMap[drone] = 0
        else:
            applicationMap[drone] = 1
    for k, v in applicationMap.items():
        cache.reserve('scan', 1)
        applicationMap[k] = floatUnerr(v)
    return applicationMap


def checked_apply(cache, rrMap, applicationMap):
    cache.reserve('rr_value', 1)
    totalAmount = RRTypes(shield=0, armor=0, hull=0, capacitor=0)
    for key, repAmount in rrMap.items():
        cache.reserve('scan', 1)
        cache.reserve('rr_value', 1)
        totalAmount += repAmount * applicationMap.get(key, 0)
    totalReps = totalAmount.shield + totalAmount.armor + totalAmount.hull
    return totalReps


def _identity_keys(cache, mapping):
    for key in mapping:
        cache.reserve('scan', 1)
        cls = type(key)
        if type(cls) is not type or cls.__hash__ is not object.__hash__ or cls.__eq__ is not object.__eq__:
            return False
    return True


def _bounded_scalar_input(value):
    if type(value) is int and value.bit_length() > 1024:
        raise AdmissionRejected('Remote repair scalar input exceeds reserved scratch')


def checked_apply_time(cache, rrMap, applicationMap):
    """Time-only RR-container removal with a pre-reserved coexistence workspace.

    Sampler reserves 32 output_slot + 4 container once per request before entry.
    Exact integer inputs <=1024 bits and <=2**63-1 terms imply product <=2048,
    accumulator <=2111 and final <=2113 bits (308 host bytes, slot price320).
    At most13 arithmetic/guard scalar slots coexist;32 also cover caller values.
    This is bounded transient coexistence, not cumulative scalar-event pricing.
    Original distance/fallback RR allocation charging is unchanged.
    """
    if type(rrMap) is not dict or type(applicationMap) is not dict:
        return checked_apply(cache, rrMap, applicationMap)
    if not _identity_keys(cache, rrMap) or not _identity_keys(cache, applicationMap):
        return checked_apply(cache, rrMap, applicationMap)
    if len(rrMap) > 2**63 - 1:
        raise AdmissionRejected('Remote repair scalar term bound exceeded')
    # Never read subclass properties while deciding whether to use the fast path.
    for repAmount in rrMap.values():
        cache.reserve('scan', 1)
        if type(repAmount) is not RRTypes:
            return checked_apply(cache, rrMap, applicationMap)
    for repAmount in rrMap.values():
        cache.reserve('scan', 1)
        for name in ('shield', 'armor', 'hull', 'capacitor'):
            value = getattr(repAmount, name)
            if type(value) not in (int, float):
                return checked_apply(cache, rrMap, applicationMap)
            _bounded_scalar_input(value)
    # No .get in this pre-scan: the original lookup occurs exactly once per key.
    for value in applicationMap.values():
        cache.reserve('scan', 1)
        if type(value) not in (int, float):
            return checked_apply(cache, rrMap, applicationMap)
    shield = armor = hull = capacitor = 0
    for key, repAmount in rrMap.items():
        cache.reserve('scan', 1)
        factor = applicationMap.get(key, 0)
        _bounded_scalar_input(factor)
        # Preserve __mul__'s four evaluations BEFORE __iadd__'s four evaluations.
        productShield = repAmount.shield * factor
        productArmor = repAmount.armor * factor
        productHull = repAmount.hull * factor
        productCapacitor = repAmount.capacitor * factor
        shield += productShield
        armor += productArmor
        hull += productHull
        capacitor += productCapacitor
    return shield + armor + hull


class CheckedXTimeMixin:
    """Original XTimeMixin.getRange order, including its initial overshoot.

    Only allocation/iteration guards are added. Cache times (not emitted points)
    are sorted, exactly as in the pinned source.
    """
    def __init__(self, graph):
        self.graph = graph

    def getRange(self, xRange, miscParams, src, tgt):
        cache = self.graph._timeCache
        output = self.graph._timeOutput
        cache.reserve('container', 2)
        xs = []
        ys = []
        minTime, maxTime = xRange
        self._prepareTimeCache(src=src, ancReload=miscParams['ancReload'], maxTime=maxTime)
        timeCache = self._getTimeCacheData(src=src, ancReload=miscParams['ancReload'])
        applicationMap = checked_application(cache, src, miscParams['distance'])
        size = len(timeCache)
        if size > (2**63 - 1 - 3) // 2:
            raise AdmissionRejected('Remote repair structural bound overflow')
        structural_bound = 2 * size + 3 if size else 2
        def append(x, y):
            if len(xs) >= structural_bound:
                raise AdmissionRejected('Remote repair structural output bound exceeded')
            output.append(xs, ys, x, y)
        currentRepAmount = None
        currentTime = None
        cache.reserve('container', 1)
        cache.reserve('sort_slot', size)
        cache.reserve('sort_work', size * max(1, size.bit_length()))
        for currentTime in sorted(timeCache):
            cache.reserve('scan', 1)
            prevRepAmount = currentRepAmount
            currentRepAmountData = timeCache[currentTime]
            currentRepAmount = checked_apply_time(cache, currentRepAmountData, applicationMap)
            if currentTime < minTime:
                continue
            if not xs:
                initialRepAmount = prevRepAmount or 0
                append(minTime, initialRepAmount)
                if currentTime > minTime:
                    append(currentTime, initialRepAmount)
                if currentRepAmount != prevRepAmount:
                    append(currentTime, currentRepAmount)
                continue
            if currentTime >= maxTime:
                append(maxTime, prevRepAmount)
                break
            if currentRepAmount != prevRepAmount:
                if prevRepAmount is not None:
                    append(currentTime, prevRepAmount)
                append(currentTime, currentRepAmount)
        if currentRepAmount is None and currentTime is None:
            append(minTime, 0)
        if maxTime > (currentTime or 0):
            append(maxTime, currentRepAmount or 0)
        return xs, ys


from .remote_repair_math import YRpsMixin


class CheckedTime2RpsGetter(CheckedXTimeMixin, YRpsMixin):
    pass


class CheckedTime2RepAmountGetter(CheckedXTimeMixin, YRepAmountMixin):
    pass
