"""D04.2 raw security input validation and fit-local replay restoration.

ProfileGraph owns the ledger and projection. This cache is only its validated
replay pair, not editable authority or an alternate character registry. EOS
retains every getter/effect formula; values are never rounded or clamped here.
"""
import math

ABSENT = object()
HULLS = {44993: 'Pacifier', 44995: 'Enforcer', 44996: 'Marshal',
         85062: 'Sidewinder', 85229: 'Cobra', 85236: 'Python'}
PRESETS = [-10, -8, -6, -4, -2, 0, 1, 2, 3, 4, 5]


def number(value, *, nullable=False):
    from .offline.profiles import require
    require((nullable and value is None) or
            (type(value) in (int, float) and -10 <= value <= 5 and math.isfinite(value)),
            'invalid_values', 'Security must be a finite number from -10 to 5' + (' or Character (null)' if nullable else ''))
    return value


def eligible(item):
    return type(item.ID) is int and HULLS.get(item.ID) == item.name


def install(fit, pilot, character=ABSENT):
    number(pilot, nullable=character is not ABSENT)
    if character is not ABSENT: number(character)
    fit._native_security_inputs = (pilot, character)
    restore(fit)


def restore(fit):
    from .offline.profiles import require
    pair = getattr(fit, '_native_security_inputs', None)
    require(type(pair) is tuple and len(pair) == 2, 'profile_mismatch', 'Fit security replay inputs are missing')
    pilot, character = pair
    number(pilot, nullable=character is not ABSENT)
    fit.pilotSecurity = pilot
    if character is not ABSENT:
        number(character)
        # Relationship expiration can replace the Character object. Restore on
        # the current relationship, never a separately retained ORM character.
        fit.character.secStatus = character


def capture(fit):
    from .offline.profiles import require
    from .offline.target_profiles import exact
    restore(fit)
    pair = getattr(fit, '_native_security_inputs', None)
    require(pair is not None, 'profile_mismatch', 'Fit security replay inputs are missing')
    pilot, character = pair
    require(exact(fit.pilotSecurity, pilot), 'profile_mismatch', 'Pilot source differs from replay inputs')
    if character is ABSENT: return {}
    require(exact(fit.character.secStatus, character), 'profile_mismatch', 'Character security differs from replay inputs')
    return dict(character_security=character)


def check_live(record, fit):
    from .offline.profiles import require
    from .offline.target_profiles import exact
    projection = capture(fit)
    require(exact(fit.pilotSecurity, record['spec']['security']['pilot']) and
            exact(projection, {'character_security': record['character_security']}),
            'profile_mismatch', 'Live pilot security does not match the bound saved inputs')


def bound_profile(state, fit_id):
    from .offline.profiles import require
    from .offline.target_profiles import exact
    ledger = state['profiles']
    binding = ledger['bindings'].get(fit_id)
    require(type(binding) is dict and binding.get('profile_id') in ledger['profiles'],
            'profile_mismatch', 'The bound character profile is missing')
    profile = ledger['profiles'][binding['profile_id']]
    value = number(profile.get('sec_status'))
    record = state['fit_graph']['records'][fit_id]
    number(record['spec']['security']['pilot'], nullable=True)
    require('character_security' in record and exact(record['character_security'], value),
            'profile_mismatch', 'Character security projection differs from the assigned profile')
    return binding, profile
