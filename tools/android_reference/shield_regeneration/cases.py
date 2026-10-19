"""Finite G04 original inputs and schedule; contains no expected calculations."""
from copy import deepcopy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ('defenses', 'boundaries', 'history')
FIELDS = ('emAmount', 'thermalAmount', 'kineticAmount', 'explosiveAmount')
HARDENER = 'Multispectrum Shield Hardener II'
EXTENDER = 'Large Shield Extender II'


def fixtures(suite):
    assert suite in SUITES
    rows = json.loads((ROOT / 'fixtures/defenses.json').read_text())['cases']
    by_name = {row['spec']['name']: deepcopy(row['spec']) for row in rows}
    if suite == 'defenses':
        result = {name.lower().replace(' ', '_'): spec for name, spec in by_name.items()}
    elif suite == 'boundaries':
        result = {'empty': by_name['Uniform incoming'], 'extended': by_name['Shield extender']}
    else:
        result = {'source_a': by_name['Hardener active'], 'source_b': by_name['Shield extender'],
                  'unrelated': by_name['Uniform incoming']}
    for key, spec in result.items():
        spec['name'] = 'G04 original ' + key
    return result


def request(name, x='time', y='shieldRegen', effective=False, span=(0.0, 300.0), start=0.0):
    unit = 's' if x == 'time' else '%' if x == 'percent' else 'EHP' if effective else 'HP'
    return dict(name=name, x_handle='shieldAmount' if x == 'percent' else x, x_unit=unit,
                y_handle=y, y_unit=('EHP' if effective else 'HP') + ('/s' if y == 'shieldRegen' else ''),
                effective=effective, input_range=list(span), starting_shield_percent=start if x == 'time' else None,
                input_scope='original_api_signed' if any(v < 0 for v in span) or (start is not None and start < 0) else 'desktop_value_domain')


def requests(suite, initial=False):
    if suite == 'defenses':
        result = []
        for effective in (False, True):
            for x in ('time', 'shieldAmount', 'percent'):
                for y in ('shieldAmount', 'shieldRegen'):
                    starts = (0.0, 25.0, 100.0) if x == 'time' else (None,)
                    for start in starts:
                        result.append(request(f'{effective}_{x}_{y}_{start}', x, y, effective,
                                              (0.0, 300.0) if x == 'time' else (0.0, 100.0), start))
        return result
    if suite == 'history':
        return [request('raw_time', start=25.0), request('effective_time', effective=True, start=25.0),
                request('raw_amount', 'shieldAmount', 'shieldAmount', span=(0.0, 100.0)),
                request('effective_percent', 'percent', effective=True, span=(0.0, 100.0))]
    return [
        request('time_equal', span=(25.0, 25.0), start=25.0),
        request('time_reversed', span=(300.0, 0.0)),
        request('time_subnormal', span=(0.0, math.ulp(0.0))),
        request('time_adjacent', span=(1e12, math.nextafter(1e12, math.inf))),
        request('time_large_finite', span=(1e305, 1.01e305)),
        request('start_null', start=None), request('start_above_100', start=150.0),
        request('shield_equal', 'shieldAmount', span=(25.0, 25.0)),
        request('shield_reversed', 'percent', span=(100.0, 0.0)),
        request('shield_above_100', 'shieldAmount', 'shieldAmount', True, (25.0, 150.0)),
        request('shield_clamped_singleton', 'percent', span=(150.0, 200.0)),
        request('shield_subnormal', 'percent', span=(0.0, math.ulp(0.0))),
        request('shield_adjacent', 'shieldAmount', span=(25.0, math.nextafter(25.0, math.inf))),
        request('api_negative_time_amount', y='shieldAmount', span=(-1000.0, -1000.0)),
        request('api_negative_time_rate', span=(-1000.0, 0.0)),
        request('api_crossing_shield', 'shieldAmount', 'shieldAmount', True, (-50.0, 150.0)),
        request('api_below_shield', 'percent', span=(-50.0, -10.0)),
        request('api_negative_start', start=-25.0),
        request('huge_shield_percent', 'shieldAmount', 'shieldAmount', span=(1e308, 1.7e308)),
        request('huge_start_percent', y='shieldAmount', start=1.7e308),
    ]


def steps(suite):
    if suite != 'history': return []
    def step(name, op, **args): return dict(name=name, op=op, args=args)
    return [step('hardener_online', 'state', fit='source_a', item=HARDENER, state='ONLINE', history=True),
            step('hardener_active', 'state', fit='source_a', item=HARDENER, state='ACTIVE'),
            step('extender_offline', 'state', fit='source_b', item=EXTENDER, state='OFFLINE', click='ctrl', history=True),
            step('extender_online', 'state', fit='source_b', item=EXTENDER, state='ONLINE', click='left'),
            step('shared_profile', 'share_profile'),
            step('management_four', 'skill', skill='Shield Management', level=4, history=True),
            step('management_five', 'skill', skill='Shield Management', level=5),
            step('operation_four', 'skill', skill='Shield Operation', level=4, history=True),
            step('operation_five', 'skill', skill='Shield Operation', level=5),
            step('pattern_asymmetric', 'pattern', fit='source_a', values=[3, 7, 11, 19], history=True),
            step('pattern_em', 'pattern', fit='source_a', values=[1, 0, 0, 0], history=True),
            step('pattern_zero', 'pattern', fit='source_a', values=[0, 0, 0, 0], history=True)]


def stage_names(suite):
    names = ['initial']
    for row in steps(suite):
        names.append(row['name'])
        if row['args'].get('history'): names += [row['name']+'_undo', row['name']+'_redo']
    return names
