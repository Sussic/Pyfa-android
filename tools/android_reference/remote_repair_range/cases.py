"""Finite G05.1 source inputs and ordered schedule; no expected calculations."""
from copy import deepcopy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ('ordinary', 'drones', 'spool', 'ancillary', 'linked')
TRANSFER = 'Medium Remote Capacitor Transmitter II'
SHIELD = 'Medium Remote Shield Booster II'
ARMOR = 'Medium Remote Armor Repairer II'
HULL = 'Medium Remote Hull Repairer II'
ANC_ARMOR = 'Small Ancillary Remote Armor Repairer'
ANC_SHIELD = 'Small Ancillary Remote Shield Booster'
DRONES = ('Light Shield Maintenance Bot I', 'Light Armor Maintenance Bot I', 'Light Hull Maintenance Bot I')


def anchor(name):
    data = json.loads((ROOT / 'fixtures/output.json').read_text())
    return deepcopy(next(c['spec'] for c in data['cases'] if c['spec']['name'] == name))


def fixtures(suite):
    assert suite in SUITES
    mixed = anchor('All outgoing')
    empty = deepcopy(mixed); empty['modules'] = []
    cap = deepcopy(mixed); cap['modules'] = cap['modules'][:1]
    if suite == 'ordinary':
        rows = [('mixed', mixed), ('empty', empty), ('capacitor_only', cap)]
    elif suite == 'drones':
        empty['drones'] = [dict(name=name, amount=2, active=1) for name in DRONES]
        rows = [('maintenance', empty)]
    elif suite == 'spool':
        rows = [('mutadaptive', anchor('Outgoing spool'))]
    elif suite == 'ancillary':
        empty['modules'] = [dict(name=ANC_ARMOR, state='ACTIVE', charge='Nanite Repair Paste'),
                            dict(name=ANC_SHIELD, state='ACTIVE', charge='Cap Booster 25')]
        reloaded = deepcopy(empty); reloaded['factor_reload'] = True
        rows = [('reload_off', empty), ('reload_on', reloaded)]
    else:
        rows = [('source_a', mixed), ('source_b', deepcopy(mixed)), ('unrelated', empty)]
    for name, value in rows:
        value['name'] = 'G05.1 original ' + name
    return dict(rows)


def steps(suite):
    step = lambda name, op, **args: dict(name=name, op=op, args=args)
    if suite == 'ordinary':
        return [step(layer+'_'+state.lower(), 'state', fit='mixed', item=item, state=state)
                for layer, item in [('shield', SHIELD), ('armor', ARMOR), ('hull', HULL)]
                for state in ('ONLINE', 'ACTIVE')]
    if suite == 'drones':
        return [step('shield_partial_two', 'drone_amount', fit='maintenance', index=0, amount=3, history=True)]
    if suite == 'spool':
        return [step('spool_zero', 'spool', fit='mutadaptive', spool_type='SPOOL_SCALE', amount=0.0),
                step('spool_three_cycles', 'spool', fit='mutadaptive', spool_type='CYCLES', amount=3.0, history=True),
                step('spool_reset', 'spool', fit='mutadaptive', spool_type=None, amount=None)]
    if suite == 'ancillary':
        result = []
        for key in ('reload_off', 'reload_on'):
            for layer, item, charge in [('armor', ANC_ARMOR, 'Nanite Repair Paste'), ('shield', ANC_SHIELD, 'Cap Booster 25')]:
                result += [step(key+'_'+layer+'_unloaded', 'charge', fit=key, item=item, charge=None),
                           step(key+'_'+layer+'_reloaded', 'charge', fit=key, item=item, charge=charge)]
        return result
    return [step('link_a_to_b', 'add_link', source='source_a', target='source_b'),
            step('link_b_to_a', 'add_link', source='source_b', target='source_a'),
            step('a_shield_online', 'state', fit='source_a', item=SHIELD, state='ONLINE', history=True),
            step('a_shield_active', 'state', fit='source_a', item=SHIELD, state='ACTIVE'),
            step('shared_profile', 'share_profile'),
            step('shared_repair_skill_four', 'repair_skill', level=4, history=True),
            step('shared_repair_skill_five', 'repair_skill', level=5),
            step('delete_source_a', 'delete_source', fit='source_a')]


def requests(suite, initial):
    options = [dict(ancReload=True, ignoreLockRange=True, ignoreDCR=False)]
    if suite == 'ancillary':
        options.append(dict(ancReload=False, ignoreLockRange=True, ignoreDCR=False))
    if suite == 'drones':
        options = [dict(ancReload=True, ignoreLockRange=lock, ignoreDCR=control)
                   for lock, control in ((True, False), (False, False), (False, True), (True, True))]
    ranges = [('default', [0.0, 100.0])]
    if suite == 'ordinary' and initial:
        ranges += [('equal', [13.5, 13.5]),
                   ('near_equal_duplicates', [1000000000000.0, math.nextafter(1000000000000.0, math.inf)]),
                   ('tiny_positive', [0.0, math.ulp(0.0)]),
                   ('very_large_finite', [1e305, 1.01e305])]
    return [dict(name=name+'_'+str(index), distance_km=distance, time=None, **option)
            for name, distance in ranges for index, option in enumerate(options)]
