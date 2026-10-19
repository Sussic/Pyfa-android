"""Logical inspector identities survive positional edits and EOS graph replay."""
from uuid import uuid4, uuid5, NAMESPACE_URL
from weakref import WeakKeyDictionary, WeakSet

_identities = WeakKeyDictionary()
_projected = WeakSet()
_projected_drones = WeakSet()
_projected_fighters = WeakSet()

def enable_projected_fighters(fit):
    _projected_fighters.add(fit)

def projected_fighters_enabled(fit):
    return fit in _projected_fighters


def enable_projected_drones(fit):
    _projected_drones.add(fit)

def projected_drones_enabled(fit):
    return fit in _projected_drones


def enable_projected(fit):
    _projected.add(fit)

def projected_enabled(fit):
    return fit in _projected



def identity(fit, thing):
    if fit not in _identities:
        _identities[fit] = WeakKeyDictionary()
    members = _identities[fit]
    if thing not in members:
        members[thing] = uuid4().hex
    return members[thing]


def families(fit):
    result = dict(ship=[fit.ship], modules=list(fit.modules), drones=list(fit.drones),
                fighters=list(fit.fighters), implants=list(fit.implants), boosters=list(fit.boosters),
                cargo=list(fit.cargo), mode=[] if fit.mode is None else [fit.mode])
    if projected_enabled(fit): result["projected_modules"] = list(fit.projectedModules)
    if projected_drones_enabled(fit): result["projected_drones"] = list(fit.projectedDrones)
    if projected_fighters_enabled(fit): result["projected_fighters"] = list(fit.projectedFighters)
    return result


def capture(fit):
    return {name: [identity(fit, thing) for thing in things] for name, things in families(fit).items()}


def validate(saved, lengths):
    if type(saved) is not dict or set(saved) != set(lengths):
        raise ValueError('Invalid inspector identity families')
    all_ids = []
    for name, count in lengths.items():
        values = saved[name]
        if type(values) is not list or len(values) != count:
            raise ValueError('Inspector identity count differs')
        if any(type(value) is not str or len(value) != 32 or
               any(letter not in '0123456789abcdef' for letter in value) for value in values):
            raise ValueError('Invalid logical inspector identity')
        all_ids.extend(values)
    if len(all_ids) != len(set(all_ids)):
        raise ValueError('Duplicate logical inspector identity')


def restore(fit, saved, legacy_namespace=None):
    if saved is not None and "projected_modules" in saved: enable_projected(fit)
    if saved is not None and "projected_drones" in saved: enable_projected_drones(fit)
    if saved is not None and "projected_fighters" in saved: enable_projected_fighters(fit)
    members = families(fit)
    if fit not in _identities:
        _identities[fit] = WeakKeyDictionary()
    keys = _identities[fit]
    if saved is None:
        if legacy_namespace is not None:
            for name, things in members.items():
                for index, thing in enumerate(things):
                    keys[thing] = uuid5(NAMESPACE_URL,
                        f'pyfa-inspection:{legacy_namespace}:{name}:{index}').hex
        return capture(fit)
    validate(saved, {name: len(things) for name, things in members.items()})
    for name, things in members.items():
        for thing, key in zip(things, saved[name]):
            keys[thing] = key
    return saved
