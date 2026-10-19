"""Metadata-only cost proof for the audited grouped incoming fighter effects.

The verified catalogue has 20 eligible types and four constant-work projected
handlers. A grouped handler runs even at quantity zero. No drone quantity loop
or local recipient tube/bay admission applies to incoming squadrons.
"""
from . import projected_fighter_records as records
from .projected_drone_admission import AdmissionRejected

EFFECT_IDS = frozenset((6434, 6435, 6436, 6437))


def reject(reason):
    # Stable shared admission error prefix; UI labels the incoming family.
    raise AdmissionRejected('Projected-drone evaluation budget: ' + reason)


def cost(rows):
    import eos.db
    records.validate(rows)
    total = 0
    for row in rows:
        item = eos.db.getItem(row['name'])
        if not records.eligible(item):
            reject('unsupported projected fighter type')
        maximum = item.getAttribute('fighterSquadronMaxSize')
        if type(maximum) not in (int, float) or maximum != 3 or not 0 <= row['amount'] <= maximum:
            reject('unaudited projected fighter squadron size')
        effects = {effect.ID: effect for effect in item.effects.values()}
        states = {ability['effect_id']: ability['active'] for ability in row['abilities']}
        if set(states) != set(effects):
            reject('projected fighter ability set differs from the pinned item')
        projected = [effect for effect in effects.values() if effect.isType('projected')]
        if len(projected) != 1:
            reject('unaudited projected fighter effects')
        for effect in projected:
            if (effect.ID not in EFFECT_IDS or not effect.isImplemented or
                    not effect.activeByDefault or not effect.getattr('grouped') or effect.runTime != 'normal'):
                reject('unaudited projected fighter effect policy')
        if any(states[key] and not effect.isImplemented for key, effect in effects.items()):
            reject('unimplemented projected fighter ability cannot be active')
        # Three runtime calls, three ability scans for active squadrons, and one
        # constant-work handler. Grouped dispatch occurs even when amount is zero.
        total += 3
        if row['active']:
            total += 3 * len(effects) + 4 * sum(states[effect.ID] for effect in projected)
    return total
