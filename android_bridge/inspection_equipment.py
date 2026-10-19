"""Original pinned equipment presentation, isolated from desktop services.

Copyright (C) 2010 Diego Duclos and Pyfa contributors.
GPL-3.0-or-later; see LICENSE.
From gui/builtinViewColumns at8b04f3b271e614b3e103853b44a7851a63d79d0e.
Only service fit/item lookups are replaced by the worker-owned fit and EOS DB;
UI/registration code is omitted. Formula and presentation bodies are retained.
"""
import eos.config
import eos.db
from eos.saveddata.mode import Mode
from eos.utils.float import floatUnerr
from eos.utils.spoolSupport import SpoolType, SpoolOptions
from .number_format import formatAmount, roundToPrec

regenGroups = ('Capacitor Battery', 'Structure Capacitor Battery', 'Capacitor Power Relay', 'Structure Capacitor Power Relay', 'Capacitor Recharger', 'Power Diagnostic System', 'Capacitor Flux Coil', 'Rig Core', 'Shield Power Relay')

def formatList(words):
    """Transforms ("a", "b", "c") into "a, b and c" string"""
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    last = words[-1:][0]
    beginning = ", ".join(words[:-1])
    return "{0} and {1}".format(beginning, last)


class EquipmentColumns:
    def attribute_text(self, mod):
        if hasattr(mod, 'item'):
            attr = mod.getModifiedItemAttr(self.info.name, None)
        else:
            if self.direct:
                info = self.directInfo
                attr = info.get(mod.ID, '') if info else ''
            else:
                attr = mod.getAttribute(self.info.name)
        if not attr:
            return ''
        if self.info.name == 'volume':
            if getattr(mod, 'amount', 1) != 1:
                attr = '{} m³ ({} m³)'.format(formatAmount(attr, 3, 0, 6), formatAmount(attr * mod.amount, 3, 0, 6))
            else:
                attr = '{} m³'.format(formatAmount(attr, 3, 0, 6))
        if isinstance(attr, (float, int)):
            attr = formatAmount(attr, 3, 0, 3)
        return attr

    def property_text(self, stuff):
        attr = getattr(stuff, self.propertyName, None)
        if attr:
            return formatAmount(attr, 3, 0, 3)
        else:
            return ''

    def misc(self, stuff):
        item = stuff.item
        if item is None:
            return ('', None)
        itemGroup = item.group.name
        itemCategory = item.category.name
        if itemGroup == 'Ship Modifiers':
            return ('', None)
        elif itemGroup == 'Booster':
            stuff.getModifiedItemAttr('boosterDuration')
            text = '{0} min'.format(formatAmount(stuff.getModifiedItemAttr('boosterDuration') / 1000 / 60, 3, 0, 3))
            return (text, 'Booster Duration')
        elif itemGroup in ('Super Weapon', 'Structure Doomsday Weapon'):
            volleyParams = stuff.getVolleyParameters(ignoreState=True)
            dmg = sum((dt.total for dt in volleyParams.values()))
            duration = (max(volleyParams) - min(volleyParams)) / 1000
            if dmg <= 0:
                text = ''
                tooltip = ''
            elif duration > 0:
                text = '{} over {}s'.format(formatAmount(dmg, 3, 0, 6), formatAmount(duration, 0, 0, 0))
                tooltip = 'Raw damage done over time'
            else:
                text = '{} dmg'.format(formatAmount(dmg, 3, 0, 6))
                tooltip = 'Raw damage done'
            return (text, tooltip)
        elif itemGroup in ('Energy Weapon', 'Hybrid Weapon', 'Projectile Weapon', 'Fighter Drone'):
            trackingSpeed = stuff.getModifiedItemAttr('trackingSpeed')
            optimalSig = stuff.getModifiedItemAttr('optimalSigRadius')
            if not trackingSpeed or not optimalSig:
                return ('', None)
            normalizedTracking = trackingSpeed * 40000 / optimalSig
            text = '{0}'.format(formatAmount(normalizedTracking, 3, 0, 3))
            tooltip = 'Tracking speed'
            return (text, tooltip)
        elif itemGroup == 'Combat Drone':
            text_parts = []
            tooltip_parts = []
            trackingSpeed = stuff.getModifiedItemAttr('trackingSpeed')
            optimalSig = stuff.getModifiedItemAttr('optimalSigRadius')
            if trackingSpeed and optimalSig:
                normalizedTracking = trackingSpeed * 40000 / optimalSig
                text_parts.append('{0}'.format(formatAmount(normalizedTracking, 3, 0, 3)))
                tooltip_parts.append('Tracking speed')
            if 'entityEnergyNeutralizerFalloff' in item.effects:
                neutAmount = stuff.getModifiedItemAttr('energyNeutralizerAmount')
                cycleTime = stuff.getModifiedItemAttr('energyNeutralizerDuration')
                if neutAmount and cycleTime:
                    capPerSec = float(-neutAmount) * 1000 / cycleTime
                    text_parts.append('{0}/s'.format(formatAmount(capPerSec, 3, 0, 3)))
                    tooltip_parts.append('Energy neutralization per second')
            if 'npcEntityWeaponDisruptor' in item.effects:
                falloffRangeBonus = stuff.getModifiedItemAttr('falloffBonus')
                optimalRangeBonus = stuff.getModifiedItemAttr('maxRangeBonus')
                trackingSpeedBonus = stuff.getModifiedItemAttr('trackingSpeedBonus')
                if falloffRangeBonus or optimalRangeBonus or trackingSpeedBonus:
                    display = 0
                    for bonus in (falloffRangeBonus, optimalRangeBonus, trackingSpeedBonus):
                        if abs(bonus) > abs(display):
                            display = bonus
                    if display:
                        ttEntries = []
                        if display == optimalRangeBonus:
                            ttEntries.append('optimal range')
                        if display == falloffRangeBonus:
                            ttEntries.append('falloff range')
                        if display == trackingSpeedBonus:
                            ttEntries.append('tracking speed')
                        text_parts.append('{0}%'.format(formatAmount(display, 3, 0, 3), forceSign=True))
                        tooltip_parts.append('{0} disruption'.format(formatList(ttEntries)).capitalize())
            if 'entityECMFalloff' in item.effects:
                grav = stuff.getModifiedItemAttr('scanGravimetricStrengthBonus')
                ladar = stuff.getModifiedItemAttr('scanLadarStrengthBonus')
                radar = stuff.getModifiedItemAttr('scanRadarStrengthBonus')
                magnet = stuff.getModifiedItemAttr('scanMagnetometricStrengthBonus')
                if grav is not None and ladar is not None and (radar is not None) and (magnet is not None):
                    display = max(grav, ladar, radar, magnet)
                    if not display:
                        return ('', None)
                    ttEntries = []
                    if display == grav:
                        ttEntries.append('gravimetric')
                    if display == ladar:
                        ttEntries.append('ladar')
                    if display == magnet:
                        ttEntries.append('magnetometric')
                    if display == radar:
                        ttEntries.append('radar')
                    plu = '' if len(ttEntries) == 1 else 's'
                    text_parts.append('{0}'.format(formatAmount(display, 3, 0, 3)))
                    tooltip_parts.append('{0} strength{1}'.format(formatList(ttEntries), plu).capitalize())
            if 'remoteSensorDampEntity' in item.effects:
                lockRangeBonus = stuff.getModifiedItemAttr('maxTargetRangeBonus')
                scanResBonus = stuff.getModifiedItemAttr('scanResolutionBonus')
                if lockRangeBonus or scanResBonus:
                    display = 0
                    for bonus in (lockRangeBonus, scanResBonus):
                        if abs(bonus) > abs(display):
                            display = bonus
                    if display:
                        ttEntries = []
                        if display == lockRangeBonus:
                            ttEntries.append('lock range')
                        if display == scanResBonus:
                            ttEntries.append('scan resolution')
                        text_parts.append('{0}%'.format(formatAmount(display, 3, 0, 3, forceSign=True)))
                        tooltip_parts.append('{0} dampening'.format(formatList(ttEntries)).capitalize())
            if 'remoteWebifierEntity' in item.effects:
                speedFactor = stuff.getModifiedItemAttr('speedFactor')
                if speedFactor:
                    text_parts.append('{0}%'.format(formatAmount(speedFactor, 3, 0, 3)))
                    tooltip_parts.append('Speed reduction')
            if 'remoteTargetPaintEntity' in item.effects:
                sigRadBonus = stuff.getModifiedItemAttr('signatureRadiusBonus')
                if sigRadBonus:
                    text_parts.append('{0}%'.format(formatAmount(sigRadBonus, 3, 0, 3, forceSign=True)))
                    tooltip_parts.append('Signature radius increase')
            return (' | '.join(text_parts), '\n'.join(tooltip_parts))
        elif itemGroup == 'Precursor Weapon':
            info = []
            trackingSpeed = stuff.getModifiedItemAttr('trackingSpeed')
            if trackingSpeed:
                text = '{0}'.format(formatAmount(trackingSpeed, 3, 0, 3))
                tooltip = 'tracking speed'
                info.append((text, tooltip))
            defaultSpoolValue = eos.config.settings['globalDefaultSpoolupPercentage']
            spoolTime = stuff.getSpoolData(spoolOptions=SpoolOptions(SpoolType.SPOOL_SCALE, defaultSpoolValue, False))[1]
            if spoolTime:
                text = '{0}s'.format(formatAmount(spoolTime, 3, 0, 3))
                tooltip = 'spool up time'
                info.append((text, tooltip))
            if not info:
                return ('', None)
            text = ' | '.join((i[0] for i in info))
            tooltip = ' and '.join((i[1] for i in info)).capitalize()
            return (text, tooltip)
        elif itemGroup == 'Vorton Projector':
            cloudSize = stuff.getModifiedItemAttr('aoeCloudSize')
            aoeVelocity = stuff.getModifiedItemAttr('aoeVelocity')
            if not cloudSize or not aoeVelocity:
                return ('', None)
            text = '{0}{1} | {2}{3}'.format(formatAmount(cloudSize, 3, 0, 3), 'm', formatAmount(aoeVelocity, 3, 0, 3), 'm/s')
            tooltip = 'Explosion radius and explosion velocity'
            return (text, tooltip)
        elif itemCategory == 'Subsystem':
            slots = ('hi', 'med', 'low')
            info = []
            for slot in slots:
                n = int(stuff.getModifiedItemAttr('%sSlotModifier' % slot))
                if n > 0:
                    info.append('{0}{1}'.format(n, slot[0].upper()))
            return ('+ ' + ', '.join(info), 'Slot Modifiers')
        elif itemGroup in ('Energy Neutralizer', 'Structure Energy Neutralizer') or (itemGroup in ('Structure Burst Projector', 'Burst Projectors') and 'doomsdayAOENeut' in item.effects):
            neutAmount = stuff.getModifiedItemAttr('energyNeutralizerAmount')
            cycleParams = stuff.getCycleParameters()
            if cycleParams is None:
                return ('', None)
            cycleTime = cycleParams.averageTime
            if not neutAmount or not cycleTime:
                return ('', None)
            capPerSec = float(-neutAmount) * 1000 / cycleTime
            text = '{0}/s'.format(formatAmount(capPerSec, 3, 0, 3))
            tooltip = 'Energy neutralization per second'
            return (text, tooltip)
        elif itemGroup == 'Energy Nosferatu':
            neutAmount = stuff.getModifiedItemAttr('powerTransferAmount')
            cycleParams = stuff.getCycleParameters()
            if cycleParams is None:
                return ('', None)
            cycleTime = cycleParams.averageTime
            if not neutAmount or not cycleTime:
                return ('', None)
            capPerSec = float(-neutAmount) * 1000 / cycleTime
            text = '{0}/s'.format(formatAmount(capPerSec, 3, 0, 3))
            tooltip = 'Energy neutralization per second'
            return (text, tooltip)
        elif itemGroup in ('Salvager', 'Salvage Drone'):
            chance = stuff.getModifiedItemAttr('accessDifficultyBonus')
            if not chance:
                return ('', None)
            text = '{0}%'.format(formatAmount(chance, 3, 0, 3))
            tooltip = 'Item retrieval chance'
            return (text, tooltip)
        elif itemGroup == 'Data Miners':
            strength = stuff.getModifiedItemAttr('virusStrength')
            coherence = stuff.getModifiedItemAttr('virusCoherence')
            if not strength or not coherence:
                return ('', None)
            text = '{0} | {1}'.format(formatAmount(strength, 3, 0, 3), formatAmount(coherence, 3, 0, 3))
            tooltip = 'Virus strength and coherence'
            return (text, tooltip)
        elif itemGroup == 'Damage Control':
            duration = stuff.getModifiedItemAttr('duration')
            if not duration:
                return ('', None)
            text = '{0}s'.format(formatAmount(duration / 1000, 3, 0, 0))
            tooltip = 'Assault ability duration'
            return (text, tooltip)
        elif itemGroup in ('Warp Scrambler', 'Warp Core Stabilizer', 'Structure Warp Scrambler'):
            scramStr = stuff.getModifiedItemAttr('warpScrambleStrength')
            if not scramStr:
                return ('', None)
            text = '{0}'.format(formatAmount(-scramStr, 3, 0, 3, forceSign=True))
            tooltip = 'Warp core strength modification'
            return (text, tooltip)
        elif itemGroup in ('Stasis Web', 'Stasis Grappler', 'Stasis Webifying Drone', 'Structure Stasis Webifier') or (itemGroup in ('Structure Burst Projector', 'Burst Projectors') and 'doomsdayAOEWeb' in item.effects):
            speedFactor = stuff.getModifiedItemAttr('speedFactor')
            if not speedFactor:
                return ('', None)
            text = '{0}%'.format(formatAmount(speedFactor, 3, 0, 3))
            tooltip = 'Speed reduction'
            return (text, tooltip)
        elif itemGroup == 'Target Painter' or (itemGroup == 'Structure Disruption Battery' and 'structureModuleEffectTargetPainter' in item.effects) or (itemGroup in ('Structure Burst Projector', 'Burst Projectors') and 'doomsdayAOEPaint' in item.effects):
            sigRadBonus = stuff.getModifiedItemAttr('signatureRadiusBonus')
            if not sigRadBonus:
                return ('', None)
            text = '{0}%'.format(formatAmount(sigRadBonus, 3, 0, 3, forceSign=True))
            tooltip = 'Signature radius increase'
            return (text, tooltip)
        elif itemGroup == 'Sensor Dampener' or (itemGroup == 'Structure Disruption Battery' and 'structureModuleEffectRemoteSensorDampener' in item.effects) or (itemGroup in ('Structure Burst Projector', 'Burst Projectors') and 'doomsdayAOEDamp' in item.effects):
            lockRangeBonus = stuff.getModifiedItemAttr('maxTargetRangeBonus')
            scanResBonus = stuff.getModifiedItemAttr('scanResolutionBonus')
            if lockRangeBonus is None or scanResBonus is None:
                return ('', None)
            display = 0
            for bonus in (lockRangeBonus, scanResBonus):
                if abs(bonus) > abs(display):
                    display = bonus
            if not display:
                return ('', None)
            text = '{0}%'.format(formatAmount(display, 3, 0, 3, forceSign=True))
            ttEntries = []
            if display == lockRangeBonus:
                ttEntries.append('lock range')
            if display == scanResBonus:
                ttEntries.append('scan resolution')
            tooltip = '{0} dampening'.format(formatList(ttEntries)).capitalize()
            return (text, tooltip)
        elif itemGroup in ('Weapon Disruptor', 'Structure Disruption Battery') or (itemGroup in ('Structure Burst Projector', 'Burst Projectors') and 'doomsdayAOETrack' in item.effects):
            optimalRangeBonus = stuff.getModifiedItemAttr('maxRangeBonus')
            falloffRangeBonus = stuff.getModifiedItemAttr('falloffBonus')
            trackingSpeedBonus = stuff.getModifiedItemAttr('trackingSpeedBonus')
            trackingDisruptorAttributes = {'optimal range': optimalRangeBonus, 'falloff range': falloffRangeBonus, 'tracking speed': trackingSpeedBonus}
            isTrackingDisruptor = any([x is not None and x != 0 for x in list(trackingDisruptorAttributes.values())])
            explosionVelocityBonus = stuff.getModifiedItemAttr('aoeVelocityBonus')
            explosionRadiusBonus = stuff.getModifiedItemAttr('aoeCloudSizeBonus')
            flightTimeBonus = stuff.getModifiedItemAttr('explosionDelayBonus')
            missileVelocityBonus = stuff.getModifiedItemAttr('missileVelocityBonus')
            guidanceDisruptorAttributes = {'explosion velocity': explosionVelocityBonus, 'explosion radius': explosionRadiusBonus, 'flight time': flightTimeBonus, 'missile velocity': missileVelocityBonus}
            isGuidanceDisruptor = any([x is not None and x != 0 for x in list(guidanceDisruptorAttributes.values())])
            if not isTrackingDisruptor and (not isGuidanceDisruptor):
                return ('', None)
            texts = []
            ttSegments = []
            for status, attributes in ((isTrackingDisruptor, trackingDisruptorAttributes), (isGuidanceDisruptor, guidanceDisruptorAttributes)):
                if not status:
                    continue
                display = max(list(attributes.values()), key=lambda x: abs(x))
                texts.append('{0}%'.format(formatAmount(display, 3, 0, 3, forceSign=True)))
                ttEntries = []
                for attributeName, attributeValue in list(attributes.items()):
                    if abs(attributeValue) == abs(display):
                        ttEntries.append(attributeName)
                ttSegments.append('{0} disruption'.format(formatList(ttEntries)).capitalize())
            return (' | '.join(texts), '\n'.join(ttSegments))
        elif itemGroup in ('Gyrostabilizer', 'Magnetic Field Stabilizer', 'Heat Sink', 'Ballistic Control System', 'Structure Weapon Upgrade', 'Entropic Radiation Sink', 'Vorton Projector Upgrade'):
            attrMap = {'Gyrostabilizer': ('damageMultiplier', 'speedMultiplier', 'Projectile weapon'), 'Magnetic Field Stabilizer': ('damageMultiplier', 'speedMultiplier', 'Hybrid weapon'), 'Heat Sink': ('damageMultiplier', 'speedMultiplier', 'Energy weapon'), 'Ballistic Control System': ('missileDamageMultiplierBonus', 'speedMultiplier', 'Missile'), 'Structure Weapon Upgrade': ('missileDamageMultiplierBonus', 'speedMultiplier', 'Missile'), 'Entropic Radiation Sink': ('damageMultiplier', 'speedMultiplier', 'Precursor weapon'), 'Vorton Projector Upgrade': ('damageMultiplier', 'speedMultiplier', 'Vorton projector')}
            dmgAttr, rofAttr, weaponName = attrMap[itemGroup]
            dmg = stuff.getModifiedItemAttr(dmgAttr)
            rof = stuff.getModifiedItemAttr(rofAttr)
            if not dmg or not rof:
                return ('', None)
            texts = []
            tooltips = []
            cumulative = (dmg / rof - 1) * 100
            texts.append('{}%'.format(formatAmount(cumulative, 3, 0, 3, forceSign=True)))
            tooltips.append('{} DPS boost'.format(weaponName))
            droneDmg = stuff.getModifiedItemAttr('droneDamageBonus')
            if droneDmg:
                texts.append('{}%'.format(formatAmount(droneDmg, 3, 0, 3, forceSign=True)))
                tooltips.append('drone DPS boost'.format(weaponName))
            return (' | '.join(texts), ' and '.join(tooltips))
        elif itemGroup == 'Drone Damage Modules':
            dmg = stuff.getModifiedItemAttr('droneDamageBonus')
            if not dmg:
                return
            text = '{}%'.format(formatAmount(dmg, 3, 0, 3, forceSign=True))
            tooltip = 'Drone DPS boost'
            return (text, tooltip)
        elif itemGroup in ('ECM', 'Burst Jammer', 'Structure ECM Battery') or (itemGroup in ('Structure Burst Projector', 'Burst Projectors') and 'doomsdayAOEECM' in item.effects):
            grav = stuff.getModifiedItemAttr('scanGravimetricStrengthBonus')
            ladar = stuff.getModifiedItemAttr('scanLadarStrengthBonus')
            radar = stuff.getModifiedItemAttr('scanRadarStrengthBonus')
            magnet = stuff.getModifiedItemAttr('scanMagnetometricStrengthBonus')
            displayMax = max(grav, ladar, radar, magnet)
            displayMin = min(grav, ladar, radar, magnet)
            if grav is None or ladar is None or radar is None or (magnet is None) or (displayMax is None):
                return ('', None)
            if displayMax == displayMin or displayMin is None:
                text = '{0}'.format(formatAmount(displayMax, 3, 0, 3))
            else:
                text = '{0} | {1}'.format(formatAmount(displayMax, 3, 0, 3), formatAmount(displayMin, 3, 0, 3))
            tooltip = 'ECM Jammer Strength:\n{0} Gravimetric | {1} Ladar | {2} Magnetometric | {3} Radar'.format(formatAmount(grav, 3, 0, 3), formatAmount(ladar, 3, 0, 3), formatAmount(magnet, 3, 0, 3), formatAmount(radar, 3, 0, 3))
            return (text, tooltip)
        elif itemGroup in ('Remote Sensor Booster', 'Sensor Booster', 'Signal Amplifier', 'Structure Signal Amplifier'):
            textLines = []
            tooltipLines = []
            scanResBonus = stuff.getModifiedItemAttr('scanResolutionBonus')
            if scanResBonus:
                textLines.append('{}%'.format(formatAmount(scanResBonus, 3, 0, 3)))
                tooltipLines.append('{}% scan resolution'.format(formatAmount(scanResBonus, 3, 0, 3)))
            lockRangeBonus = stuff.getModifiedItemAttr('maxTargetRangeBonus')
            if lockRangeBonus:
                textLines.append('{}%'.format(formatAmount(lockRangeBonus, 3, 0, 3)))
                tooltipLines.append('{}% lock range'.format(formatAmount(lockRangeBonus, 3, 0, 3)))
            gravBonus = stuff.getModifiedItemAttr('scanGravimetricStrengthPercent')
            if gravBonus:
                textLines.append('{}%'.format(formatAmount(gravBonus, 3, 0, 3)))
                tooltipLines.append('{}% sensor strength'.format(formatAmount(gravBonus, 3, 0, 3)))
            if not textLines:
                return ('', None)
            text = ' | '.join(textLines)
            tooltip = 'Applied bonuses:\n{}'.format(' | '.join(tooltipLines))
            return (text, tooltip)
        elif itemGroup in ('Projected ECCM', 'ECCM', 'Sensor Backup Array'):
            grav = stuff.getModifiedItemAttr('scanGravimetricStrengthPercent')
            ladar = stuff.getModifiedItemAttr('scanLadarStrengthPercent')
            radar = stuff.getModifiedItemAttr('scanRadarStrengthPercent')
            magnet = stuff.getModifiedItemAttr('scanMagnetometricStrengthPercent')
            if grav is None or ladar is None or radar is None or (magnet is None):
                return ('', None)
            display = max(grav, ladar, radar, magnet)
            if not display:
                return ('', None)
            text = '{0}%'.format(formatAmount(display, 3, 0, 3, forceSign=True))
            ttEntries = []
            if display == grav:
                ttEntries.append('gravimetric')
            if display == ladar:
                ttEntries.append('ladar')
            if display == magnet:
                ttEntries.append('magnetometric')
            if display == radar:
                ttEntries.append('radar')
            plu = '' if len(ttEntries) == 1 else 's'
            tooltip = '{0} strength{1} bonus'.format(formatList(ttEntries), plu).capitalize()
            return (text, tooltip)
        elif itemGroup == 'Cloaking Device':
            recalibration = stuff.getModifiedItemAttr('cloakingTargetingDelay')
            if recalibration is None:
                return ('', None)
            text = '{0}s'.format(formatAmount(float(recalibration) / 1000, 3, 0, 3))
            tooltip = 'Sensor recalibration time'
            return (text, tooltip)
        elif itemGroup == 'Remote Armor Repairer':
            rps = stuff.getRemoteReps(ignoreState=True).armor
            if not rps:
                return ('', None)
            text = '{0}/s'.format(formatAmount(rps, 3, 0, 3, forceSign=True))
            tooltip = 'Armor repaired per second'
            return (text, tooltip)
        elif itemGroup == 'Mutadaptive Remote Armor Repairer':
            defaultSpoolValue = eos.config.settings['globalDefaultSpoolupPercentage']
            spoolOptDefault = SpoolOptions(SpoolType.SPOOL_SCALE, defaultSpoolValue, False)
            spoolOptPre = SpoolOptions(SpoolType.SPOOL_SCALE, 0, True)
            spoolOptFull = SpoolOptions(SpoolType.SPOOL_SCALE, 1, True)
            rps = stuff.getRemoteReps(spoolOptions=spoolOptDefault, ignoreState=True).armor
            rpsPre = stuff.getRemoteReps(spoolOptions=spoolOptPre, ignoreState=True).armor
            rpsFull = stuff.getRemoteReps(spoolOptions=spoolOptFull, ignoreState=True).armor
            if not rps:
                return ('', None)
            text = []
            tooltip = []
            text.append('{}/s'.format(formatAmount(rps, 3, 0, 3, forceSign=True)))
            tooltip.append('Armor repaired per second')
            spoolTime = stuff.getSpoolData(spoolOptDefault)[1]
            if spoolTime:
                text.append('{}s'.format(formatAmount(spoolTime, 3, 0, 3)))
                tooltip.append('spool up time')
            text = ' | '.join(text)
            tooltip = ' and '.join(tooltip)
            spoolTimePre = stuff.getSpoolData(spoolOptPre)[1]
            spoolTimeFull = stuff.getSpoolData(spoolOptFull)[1]
            if spoolTimePre != spoolTimeFull:
                tooltip = '{}\nSpool up: {}-{} over {}s'.format(tooltip, formatAmount(rpsPre, 3, 0, 3), formatAmount(rpsFull, 3, 0, 3), formatAmount(spoolTimeFull - spoolTimePre, 3, 0, 3))
            return (text, tooltip)
        elif itemGroup == 'Remote Shield Booster':
            rps = stuff.getRemoteReps(ignoreState=True).shield
            if not rps:
                return ('', None)
            text = '{0}/s'.format(formatAmount(rps, 3, 0, 3, forceSign=True))
            tooltip = 'Shield transferred per second'
            return (text, tooltip)
        elif itemGroup == 'Remote Capacitor Transmitter':
            rps = stuff.getRemoteReps(ignoreState=True).capacitor
            if not rps:
                return ('', None)
            text = '{0}/s'.format(formatAmount(rps, 3, 0, 3, forceSign=True))
            tooltip = 'Energy transferred per second'
            return (text, tooltip)
        elif itemGroup == 'Remote Hull Repairer':
            rps = stuff.getRemoteReps(ignoreState=True).hull
            if not rps:
                return ('', None)
            text = '{0}/s'.format(formatAmount(rps, 3, 0, 3, forceSign=True))
            tooltip = 'Structure repaired per second'
            return (text, tooltip)
        elif itemGroup == 'Gang Coordinator':
            command = stuff.getModifiedItemAttr('commandBonus') or stuff.getModifiedItemAttr('commandBonusHidden')
            if not command:
                return ('', None)
            text = '{0}%'.format(formatAmount(command, 3, 0, 3, forceSign=True))
            tooltip = 'Gang bonus strength'
            return (text, tooltip)
        elif itemGroup == 'Electronic Warfare Drone':
            sigRadBonus = stuff.getModifiedItemAttr('signatureRadiusBonus')
            lockRangeBonus = stuff.getModifiedItemAttr('maxTargetRangeBonus')
            scanResBonus = stuff.getModifiedItemAttr('scanResolutionBonus')
            falloffRangeBonus = stuff.getModifiedItemAttr('falloffBonus')
            optimalRangeBonus = stuff.getModifiedItemAttr('maxRangeBonus')
            trackingSpeedBonus = stuff.getModifiedItemAttr('trackingSpeedBonus')
            grav = stuff.getModifiedItemAttr('scanGravimetricStrengthBonus')
            ladar = stuff.getModifiedItemAttr('scanLadarStrengthBonus')
            radar = stuff.getModifiedItemAttr('scanRadarStrengthBonus')
            magnet = stuff.getModifiedItemAttr('scanMagnetometricStrengthBonus')
            if sigRadBonus:
                text = '{0}%'.format(formatAmount(sigRadBonus, 3, 0, 3, forceSign=True))
                tooltip = 'Signature radius increase'
                return (text, tooltip)
            if lockRangeBonus or scanResBonus:
                display = 0
                for bonus in (lockRangeBonus, scanResBonus):
                    if abs(bonus) > abs(display):
                        display = bonus
                if not display:
                    return ('', None)
                text = '{0}%'.format(formatAmount(display, 3, 0, 3, forceSign=True))
                ttEntries = []
                if display == lockRangeBonus:
                    ttEntries.append('lock range')
                if display == scanResBonus:
                    ttEntries.append('scan resolution')
                tooltip = '{0} dampening'.format(formatList(ttEntries)).capitalize()
                return (text, tooltip)
            if falloffRangeBonus or optimalRangeBonus or trackingSpeedBonus:
                display = 0
                for bonus in (falloffRangeBonus, optimalRangeBonus, trackingSpeedBonus):
                    if abs(bonus) > abs(display):
                        display = bonus
                if not display:
                    return ('', None)
                text = '{0}%'.format(formatAmount(display, 3, 0, 3), forceSign=True)
                ttEntries = []
                if display == optimalRangeBonus:
                    ttEntries.append('optimal range')
                if display == falloffRangeBonus:
                    ttEntries.append('falloff range')
                if display == trackingSpeedBonus:
                    ttEntries.append('tracking speed')
                tooltip = '{0} disruption'.format(formatList(ttEntries)).capitalize()
                return (text, tooltip)
            if grav is not None and ladar is not None and (radar is not None) and (magnet is not None):
                display = max(grav, ladar, radar, magnet)
                if not display:
                    return ('', None)
                text = '{0}'.format(formatAmount(display, 3, 0, 3))
                ttEntries = []
                if display == grav:
                    ttEntries.append('gravimetric')
                if display == ladar:
                    ttEntries.append('ladar')
                if display == magnet:
                    ttEntries.append('magnetometric')
                if display == radar:
                    ttEntries.append('radar')
                plu = '' if len(ttEntries) == 1 else 's'
                tooltip = '{0} strength{1}'.format(formatList(ttEntries), plu).capitalize()
                return (text, tooltip)
            else:
                return ('', None)
        elif itemGroup == 'Fighter Bomber':
            optimalSig = stuff.getModifiedItemAttr('optimalSigRadius')
            if not optimalSig:
                return ('', None)
            text = '{0}m'.format(formatAmount(optimalSig, 3, 0, 3))
            tooltip = 'Optimal signature radius'
            return (text, tooltip)
        elif itemGroup in ('Frequency Mining Laser', 'Strip Miner', 'Mining Laser', 'Gas Cloud Scoops', 'Mining Drone', 'Gas Cloud Harvesters'):
            yps = stuff.getMiningYPS(ignoreState=True)
            if not yps:
                return ('', None)
            yph = yps * 3600
            dps = stuff.getMiningDPS(ignoreState=True)
            dph = dps * 3600
            try:
                efficiency = yps / dps
            except ZeroDivisionError:
                efficiency = 0
            textParts = []
            tipLines = []
            textParts.append('{} m³/s'.format(formatAmount(yps, 3, 0, 3)))
            tipLines.append('{} m³ mining yield per second ({} m³ per hour)'.format(formatAmount(yps, 3, 0, 3), formatAmount(yph, 3, 0, 3)))
            tipLines.append('{} m³ mining drain per second ({} m³ per hour)'.format(formatAmount(dps, 3, 0, 3), formatAmount(dph, 3, 0, 3)))
            if floatUnerr(efficiency) != 1:
                eff_text = '{}%'.format(formatAmount(efficiency * 100, 4, 0, 0))
                textParts.append(eff_text)
                tipLines.append(f'{eff_text} mining efficiency')
            text = '{}'.format(' | '.join(textParts))
            tooltip = '\n'.join(tipLines)
            return (text, tooltip)
        elif itemGroup == 'Logistic Drone':
            rpsData = stuff.getRemoteReps(ignoreState=True)
            rrType = None
            rps = None
            if rpsData.shield:
                rps = rpsData.shield
                rrType = 'Shield'
            elif rpsData.armor:
                rps = rpsData.armor
                rrType = 'Armor'
            elif rpsData.hull:
                rps = rpsData.hull
                rrType = 'Hull'
            if not rrType or not rps:
                return ('', None)
            text = '{}/s'.format(formatAmount(rps, 3, 0, 3))
            tooltip = '{} HP repaired per second\n{} HP/s per drone'.format(rrType, formatAmount(rps / stuff.amount, 3, 0, 3))
            return (text, tooltip)
        elif itemGroup == 'Energy Neutralizer Drone':
            neutAmount = stuff.getModifiedItemAttr('energyNeutralizerAmount')
            cycleTime = stuff.getModifiedItemAttr('energyNeutralizerDuration')
            if not neutAmount or not cycleTime:
                return ('', None)
            capPerSec = float(-neutAmount) * 1000 / cycleTime
            text = '{0}/s'.format(formatAmount(capPerSec, 3, 0, 3))
            tooltip = 'Energy neutralization per second'
            return (text, tooltip)
        elif itemGroup in ('Micro Jump Drive', 'Micro Jump Field Generators', 'Capital Mobility Modules'):
            cycleTime = stuff.getModifiedItemAttr('duration') / 1000
            text = '{0}s'.format(formatAmount(cycleTime, 3, 0, 3))
            tooltip = 'Spoolup time'
            return (text, tooltip)
        elif itemGroup in ('Siege Module', 'Cynosural Field Generator'):
            amt = stuff.getModifiedItemAttr('consumptionQuantity')
            if amt:
                typeID = stuff.getModifiedItemAttr('consumptionType')
                item = eos.db.getItem(int(typeID))
                text = '{0} units'.format(formatAmount(amt, 3, 0, 3))
                return (text, item.name)
            else:
                return ('', None)
        elif itemGroup in ('Ancillary Armor Repairer', 'Ancillary Shield Booster', 'Capacitor Booster', 'Ancillary Remote Armor Repairer', 'Ancillary Remote Shield Booster'):
            if 'Armor' in itemGroup or 'Shield' in itemGroup:
                boosted_attribute = 'HP'
                reload_time = stuff.getModifiedItemAttr('reloadTime', 0) / 1000
            elif 'Capacitor' in itemGroup:
                boosted_attribute = 'Cap'
                reload_time = 10
            else:
                boosted_attribute = ''
                reload_time = 0
            cycles = max(stuff.numShots, 0)
            cycleTime = max(stuff.rawCycleTime, 0)
            stuff_hp = max(stuff.hpBeforeReload, 0)
            armor_hp = stuff.getModifiedItemAttr('armorDamageAmount', 0)
            capacitor_hp = stuff.getModifiedChargeAttr('capacitorBonus', 0)
            shield_hp = stuff.getModifiedItemAttr('shieldBonus', 0)
            hp = max(stuff_hp, armor_hp * cycles, capacitor_hp * cycles, shield_hp * cycles, 0)
            nonChargedMap = {'Ancillary Remote Armor Repairer': ('armor', 'Armor repaired per second'), 'Ancillary Remote Shield Booster': ('shield', 'Shield transferred per second')}
            if not cycles and itemGroup in nonChargedMap:
                rps = stuff.getRemoteReps(ignoreState=True)
                rps = getattr(rps, nonChargedMap[itemGroup][0])
                if not rps:
                    return ('', None)
                text = '{0}/s'.format(formatAmount(rps, 3, 0, 3, forceSign=True))
                tooltip = nonChargedMap[itemGroup][1]
                return (text, tooltip)
            if not hp or not cycleTime or (not cycles):
                return ('', None)
            fit = self.fit
            ehpTotal = fit.ehp
            hpTotal = fit.hp
            try:
                useEhp = self.mainFrame.statsPane.nameViewMap['resistancesViewFull'].showEffective
            except KeyError:
                useEhp = False
            tooltip = '{0} restored over duration using charges (plus reload)'.format(boosted_attribute)
            if useEhp and boosted_attribute == 'HP' and ('Remote' not in itemGroup):
                if 'Ancillary Armor Repairer' in itemGroup:
                    hpRatio = ehpTotal['armor'] / hpTotal['armor']
                else:
                    hpRatio = ehpTotal['shield'] / hpTotal['shield']
                tooltip = 'E{0}'.format(tooltip)
            else:
                hpRatio = 1
            if 'Ancillary' in itemGroup and 'Armor' in itemGroup:
                hpRatio *= stuff.getModifiedItemAttr('chargedArmorDamageMultiplier', 1)
            ehp = hp * hpRatio
            duration = cycles * cycleTime / 1000
            for number_of_cycles in {5, 10, 25}:
                tooltip = '{0}\n{1} charges lasts {2} seconds ({3} cycles)'.format(tooltip, formatAmount(number_of_cycles * cycles, 3, 0, 3), formatAmount((duration + reload_time) * number_of_cycles, 3, 0, 3), formatAmount(number_of_cycles, 3, 0, 3))
            text = '{0} / {1}s (+{2}s)'.format(formatAmount(ehp, 3, 0, 9), formatAmount(duration, 3, 0, 3), formatAmount(reload_time, 3, 0, 3))
            return (text, tooltip)
        elif itemGroup == 'Armor Resistance Shift Hardener':
            itemArmorResistanceShiftHardenerEM = (1 - stuff.getModifiedItemAttr('armorEmDamageResonance')) * 100
            itemArmorResistanceShiftHardenerTherm = (1 - stuff.getModifiedItemAttr('armorThermalDamageResonance')) * 100
            itemArmorResistanceShiftHardenerKin = (1 - stuff.getModifiedItemAttr('armorKineticDamageResonance')) * 100
            itemArmorResistanceShiftHardenerExp = (1 - stuff.getModifiedItemAttr('armorExplosiveDamageResonance')) * 100
            text = '{0}% | {1}% | {2}% | {3}%'.format(formatAmount(itemArmorResistanceShiftHardenerEM, 3, 0, 3), formatAmount(itemArmorResistanceShiftHardenerTherm, 3, 0, 3), formatAmount(itemArmorResistanceShiftHardenerKin, 3, 0, 3), formatAmount(itemArmorResistanceShiftHardenerExp, 3, 0, 3))
            tooltip = 'Resistances shifted to damage profile:\n{0}% EM | {1}% Therm | {2}% Kin | {3}% Exp'.format(formatAmount(itemArmorResistanceShiftHardenerEM, 3, 0, 3), formatAmount(itemArmorResistanceShiftHardenerTherm, 3, 0, 3), formatAmount(itemArmorResistanceShiftHardenerKin, 3, 0, 3), formatAmount(itemArmorResistanceShiftHardenerExp, 3, 0, 3))
            return (text, tooltip)
        elif itemGroup in ('Cargo Scanner', 'Ship Scanner'):
            duration = stuff.getModifiedItemAttr('duration')
            if not duration:
                return ('', None)
            text = '{}s'.format(formatAmount(duration / 1000, 3, 0, 0))
            tooltip = 'Scan duration'
            return (text, tooltip)
        elif itemGroup == 'Command Burst':
            textSections = []
            tooltipSections = []
            buffMap = {}
            for seq in (1, 2, 3, 4):
                buffId = stuff.getModifiedChargeAttr(f'warfareBuff{seq}ID')
                if not buffId:
                    continue
                buffValue = stuff.getModifiedItemAttr(f'warfareBuff{seq}Value')
                buffMap[buffId] = buffValue
                if buffId == 10:
                    textSections.append(f'{formatAmount(-buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('shield resistance')
                elif buffId == 11:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('shield RR duration & capacictor use')
                elif buffId == 12:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('shield HP')
                elif buffId == 13:
                    textSections.append(f'{formatAmount(-buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('armor resistance')
                elif buffId == 14:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('armor RR duration & capacitor use')
                elif buffId == 15:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('armor HP')
                elif buffId == 16:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('scan resolution')
                elif buffId == 26:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('targeting range')
                elif buffId == 17:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('electronic warfare modules range & strength')
                elif buffId == 18:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('sensor strength')
                elif buffId == 19:
                    textSections.append(f'{formatAmount(-buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('sensor dampener & weapon disruption resistance')
                elif buffId == 20:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('signature radius')
                elif buffId == 60:
                    textSections.append(f'{formatAmount(-buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('agility')
                elif buffId == 21:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('warp disruption & stasis web range')
                elif buffId == 22:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('AB/MWD speed increase')
                elif buffId == 23:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('mining module range')
                elif buffId == 24:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('mining module duration & capacitor use')
                elif buffId == 25:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('mining crystal volatility')
                elif buffId == 2464:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('scan probe strength')
                elif buffId == 2465:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('dscan, hacking & salvaging range')
                elif buffId == 2466:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('scan probe deviation')
                elif buffId == 2468:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}')
                    tooltipSections.append('virus coherence')
                elif buffId == 2481:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('salvager cycle time')
                elif buffId == 2516:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('crit chance')
                elif buffId == 2517:
                    textSections.append(f'{formatAmount(buffValue, 3, 0, 3, forceSign=True)}%')
                    tooltipSections.append('waste chance')
            if not textSections:
                return ('', None)
            text = ' | '.join(textSections)
            tooltip = '{} bonus'.format(' | '.join(tooltipSections))
            if tooltip:
                tooltip = tooltip[0].capitalize() + tooltip[1:]
            return (text, tooltip)
        elif stuff.charge is not None:
            chargeGroup = stuff.charge.group.name
            if chargeGroup.endswith('Rocket') or chargeGroup.endswith('Missile') or chargeGroup.endswith('Torpedo'):
                cloudSize = stuff.getModifiedChargeAttr('aoeCloudSize')
                aoeVelocity = stuff.getModifiedChargeAttr('aoeVelocity')
                if not cloudSize or not aoeVelocity:
                    return ('', None)
                text = '{0}{1} | {2}{3}'.format(formatAmount(cloudSize, 3, 0, 3), 'm', formatAmount(aoeVelocity, 3, 0, 3), 'm/s')
                tooltip = 'Explosion radius and explosion velocity'
                return (text, tooltip)
            elif chargeGroup in ('Bomb', 'Guided Bomb'):
                cloudSize = stuff.getModifiedChargeAttr('aoeCloudSize')
                if not cloudSize:
                    return ('', None)
                text = '{0}{1}'.format(formatAmount(cloudSize, 3, 0, 3), 'm')
                tooltip = 'Explosion radius'
                return (text, tooltip)
            elif chargeGroup in ('Scanner Probe',):
                scanStr = stuff.getModifiedChargeAttr('baseSensorStrength')
                baseRange = stuff.getModifiedChargeAttr('baseScanRange')
                if not scanStr or not baseRange:
                    return ('', None)
                text = '{}'.format(formatAmount(scanStr, 4, 0, 3))
                tooltip = 'Scan strength at {} AU scan range'.format(formatAmount(baseRange, 3, 0, 0))
                return (text, tooltip)
            elif chargeGroup in ('SCARAB Breacher Pods',):
                duration = stuff.getModifiedChargeAttr('dotDuration') / 1000
                dmgAbs = stuff.getModifiedChargeAttr('dotMaxDamagePerTick')
                dmgRel = stuff.getModifiedChargeAttr('dotMaxHPPercentagePerTick')
                text = '{}/{}% over {}s'.format(formatAmount(dmgAbs * duration, 3, 0, 6), formatAmount(dmgRel * duration, 3, 0, 6), formatAmount(duration, 0, 0, 0))
                fullDmgHp = dmgAbs / (dmgRel / 100)
                tooltip = 'Pure damage inflicted over time, minimum of absolute / relative\nFull DPS from {} target HP'.format(formatAmount(fullDmgHp, 3, 0, 6))
                return (text, tooltip)
            else:
                return ('', None)
        else:
            return ('', None)

    def range_text(self, stuff):
        if isinstance(stuff, Mode):
            return ''
        maxRange = stuff.maxRange if hasattr(stuff, 'maxRange') else stuff.getModifiedItemAttr('maxRange', None)
        falloff = stuff.falloff
        if falloff and falloff >= 5:
            falloff = '+%sm' % formatAmount(falloff, 3, 0, 3)
        else:
            falloff = ''
        if maxRange:
            return '%sm%s' % (formatAmount(maxRange, 3, 0, 3), falloff)
        else:
            return '' + falloff

    def range_tooltip(self, mod):
        lines = []
        missileRangeData = mod.missileMaxRangeData if hasattr(mod, 'missileMaxRangeData') else None
        if missileRangeData is not None:
            lines.append('Missile flight range')
            lowerRange, higherRange, higherChance = missileRangeData
            if roundToPrec(higherChance, 3) not in (0, 1):
                lines.append('{}% chance to fly {}m'.format(formatAmount((1 - higherChance) * 100, prec=3, lowest=0, highest=0), formatAmount(lowerRange, prec=3, lowest=0, highest=3)))
                lines.append('{}% chance to fly {}m'.format(formatAmount(higherChance * 100, prec=3, lowest=0, highest=0), formatAmount(higherRange, prec=3, lowest=0, highest=3)))
        else:
            lines.append('Optimal + Falloff')
        return '\n'.join(lines)

    def capacitor_text(self, mod):
        if isinstance(mod, Mode):
            return ''
        fit = self.fit
        if fit is None:
            return ''
        capUse = mod.capUse
        if mod.item is not None and mod.item.group.name in regenGroups:
            capRegenDiff = fit.getCapRegenGainFromMod(mod)
        else:
            capRegenDiff = 0
        capDiff = floatUnerr(capRegenDiff - capUse)
        if capDiff:
            return formatAmount(capDiff, 3, 0, 3, forceSign=True)
        else:
            return ''

    def capacitor_tooltip(self, mod):
        if isinstance(mod, Mode):
            return ''
        if mod.item is not None and mod.item.group.name in regenGroups:
            return 'Effect on peak capacitor regeneration'
        if mod.capUse:
            return 'Capacitor usage'
        return ''
