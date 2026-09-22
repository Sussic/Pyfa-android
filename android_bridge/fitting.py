"""Worker-only module editing policy adapted from pinned desktop Pyfa commands.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
Source: gui/fitCommands/{helpers,calc/module/localAdd,localReplace,localRemove}.py,
gui/fitCommands/gui/fitRestrictionToggle.py and service/{fit,character,market}.py
at 8b04f3b271e614b3e103853b44a7851a63d79d0e. EOS owns every calculation/restriction.
The bridge transaction restores all declarative inputs after a rejected edit.
"""
from itertools import chain


SLOTS = {'LOW': 1, 'MED': 2, 'HIGH': 3, 'RIG': 4, 'SERVICE': 8}
# EOS fill also retains strategic-cruiser subsystem positions. Their dedicated
# editor remains B06; preserving vacancies does not authorize subsystem edits.
VACANT_SLOTS = {**SLOTS, 'SUBSYSTEM': 5}
ONLINE_EFFECTS = frozenset((
    'moduleBonusAssaultDamageControl', 'moduleBonusIndustrialInvulnerability',
    'microJumpDrive', 'microJumpPortalDrive', 'emergencyHullEnergizer',
    'cynosuralGeneration', 'jumpPortalGeneration', 'jumpPortalGenerationBO',
    'cloneJumpAccepting', 'cloakingWarpSafe', 'cloakingPrototype', 'cloaking',
    'massEntanglerEffect5', 'electronicAttributeModifyOnline', 'targetPassively',
    'cargoScan', 'shipScan', 'surveyScan', 'targetSpectrumBreakerBonus',
    'interdictionNullifierBonus', 'warpCoreStabilizerActive', 'industrialItemCompression',
))


class FittingRejected(ValueError):
    """A valid module-use attempt which desktop records even when it cannot fit."""
    def __init__(self, message, item_id):
        super().__init__(message)
        self.item_id = item_id


def item(engine, identity):
    engine._check_thread()
    import eos.db
    if type(identity) is not int or identity < 1:
        raise ValueError('Choose a bundled module')
    result = eos.db.getItem(identity)
    if result is None:
        raise ValueError('Unknown item')
    return result


def new_module(engine, identity):
    from eos.const import FittingModuleState
    from eos.saveddata.module import Module
    value = item(engine, identity)
    module = Module(value)
    if module.slot not in SLOTS.values() or value.isAbyssal:
        raise ValueError('This item needs a different fitting editor')
    limit = FittingModuleState.ONLINE if ONLINE_EFFECTS.intersection(value.effects) else FittingModuleState.ACTIVE
    if module.isValidState(limit):
        module.state = limit
    engine.resolved_item_ids[value.name] = value.ID
    return module


def check_states(fit, base):
    from eos.const import FittingModuleState
    changed = False
    for module in fit.modules:
        if module is base:
            continue
        state = module.canHaveState(module.state)
        if state is not True:
            module.state = state
            changed = True
        elif not module.isValidState(module.state):
            module.state = FittingModuleState.ONLINE
            changed = True
    for module in fit.projectedModules:
        state = module.canHaveState(module.state, fit)
        if state is not True:
            module.state = state
            changed = True
        elif not module.isValidState(module.state):
            module.state = FittingModuleState.OFFLINE
            changed = True
    for drone in fit.projectedDrones:
        if drone.amountActive > 0 and not drone.canBeApplied(fit):
            drone.amountActive = 0
            changed = True
    return changed


def _position(fit, position, occupied=False):
    if type(position) is not int or not 0 <= position < len(fit.modules):
        raise ValueError('Choose a module position in this fit')
    module = fit.modules[position]
    if module.slot not in SLOTS.values() or occupied and module.isEmpty:
        raise ValueError('Choose a fitted module')
    return module


def _reconcile(engine, fit, base):
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    if check_states(fit, base):
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)


def _fill(fit):
    import eos.db
    fit.fill()
    # GUI commands commit after fill. Our bridge reads the candidate before its
    # durable commit, so assign new vacancies' ORM owners before snapshotting.
    eos.db.saveddata_session.flush()


def add(engine, fit, identity):
    engine._check_fit(fit)
    module = new_module(engine, identity)
    # Opening an empty fit is read-only; materialize desktop vacancies on edit.
    fit.fill()
    fit.modules.append(module)
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    if module not in fit.modules or not module.fits(fit):
        raise FittingRejected('The module exceeds a slot, hardpoint, hull, rig-size or group restriction.', identity)
    if check_states(fit, module):
        engine._recalculate(fit)
    _fill(fit)
    return [identity]


def replace(engine, fit, position, identity):
    engine._check_fit(fit)
    old = _position(fit, position)
    module = new_module(engine, identity)
    if module.slot != old.slot:
        raise FittingRejected('Replacement requires the same slot type.', identity)
    fit.modules.replace(position, module)
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    changed = check_states(fit, module)
    if module not in fit.modules or not module.fits(fit):
        raise FittingRejected('The replacement exceeds a fitting restriction.', identity)
    # The original calculation command checks fits before the GUI's second
    # recalculation for state changes. Preserve that acceptance order.
    if changed:
        eos.db.saveddata_session.flush()
        engine._recalculate(fit)
    _fill(fit)
    return [identity]


def remove(engine, fit, position):
    engine._check_fit(fit)
    module = _position(fit, position, occupied=True)
    identity = module.itemID
    fit.modules.free(position)
    _reconcile(engine, fit, None)
    _fill(fit)
    return [identity]


def restrictions(engine, fit, ignore):
    engine._check_fit(fit)
    if type(ignore) is not bool:
        raise ValueError('Restriction override must be boolean')
    fit.ignoreRestrictions = ignore
    if not ignore:
        for position, module in reversed(list(enumerate(fit.modules))):
            if not module.isEmpty and not module.fits(fit, hardpointLimit=False):
                fit.modules.free(position)
                _reconcile(engine, fit, None)
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    _fill(fit)
    return []  # Original restriction toggle does not change recent use.


def promote(engine, previous, identities):
    result = list(previous)
    for identity in identities:
        value = item(engine, identity)
        result = [old for old in result if old != identity]
        if not value.isAbyssal:
            result = [identity, *result[:19]]
    return result


def details(engine, fit):
    engine._check_fit(fit)
    from eos.const import FittingModuleState, FittingSlot, FittingHardpoint
    from eos.saveddata.module import Module
    from eos.saveddata.fighter import Fighter
    if not fit.calculated:
        fit.calculateModifiedAttributes()

    def missing(value, requirements):
        # Original recursive skill requirements are warnings, not a fits() gate.
        for required, level in value.requiredSkills.items():
            previous = requirements.get(required.name)
            current, children = (previous[0] if previous else 0), {}
            if level > current and fit.character.getSkill(required).level < level:
                requirements[required.name] = (level, required.ID, children)
                missing(required, children)

    def skill_rows(values):
        return [{'id': identity, 'name': name, 'required': level,
                 'actual': fit.character.getSkill(identity).level, 'requirements': skill_rows(children)}
                for name, (level, identity, children) in sorted(values.items())]

    warnings = {}
    for thing in chain(fit.modules, fit.drones, fit.fighters, (fit.ship,), fit.appliedImplants, fit.boosters):
        if isinstance(thing, Module) and thing.slot == FittingSlot.RIG:
            continue
        for attribute in ('item', 'charge'):
            if attribute == 'charge' and isinstance(thing, Fighter):
                continue
            value = getattr(thing, attribute, None)
            if value is not None:
                requirements = {}
                missing(value, requirements)
                if requirements:
                    warnings[value.ID] = {'id': value.ID, 'name': value.name, 'requirements': skill_rows(requirements)}
    resources = {}
    for name, used, total, unit in (
            ('cpu', fit.cpuUsed, fit.ship.getModifiedItemAttr('cpuOutput'), 'tf'),
            ('powergrid', fit.pgUsed, fit.ship.getModifiedItemAttr('powerOutput'), 'MW'),
            ('calibration', fit.calibrationUsed, fit.ship.getModifiedItemAttr('upgradeCapacity'), 'points')):
        resources[name] = {'used': used, 'total': total, 'unit': unit, 'overloaded': used > total}
    modules = []
    for index, module in enumerate(fit.modules):
        legal = None if module.isEmpty else module.fits(fit)
        modules.append({'index': index, 'id': module.itemID,
            'name': module.item.name if module.item else None, 'slot': FittingSlot(module.slot).name,
            'state': FittingModuleState(module.state).name, 'charge': module.charge.name if module.charge else None,
            'legal': legal, 'overridden': bool(fit.ignoreRestrictions and getattr(module, 'restrictionOverridden', False))})
    return {'modules': modules, 'ignore_restrictions': fit.ignoreRestrictions, 'resources': resources,
            'slots': [{'slot': name, 'used': fit.getSlotsUsed(slot), 'total': fit.getNumSlots(slot)} for name, slot in SLOTS.items()],
            'hardpoints': [{'kind': kind.name, 'used': fit.getHardpointsUsed(kind),
                           'total': fit.ship.getModifiedItemAttr(attribute)} for kind, attribute in (
                               (FittingHardpoint.TURRET, 'turretSlotsLeft'), (FittingHardpoint.MISSILE, 'launcherSlotsLeft'))],
            'skill_warnings': [warnings[key] for key in sorted(warnings)]}
