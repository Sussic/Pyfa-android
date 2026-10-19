"""Strict added inspector metadata without relaxing inherited record assertions."""
from functools import lru_cache
import json
from pathlib import Path
import re
from market_summary import exact

CORE = {'spec', 'skills', 'implants', 'projections', 'commands'}


@lru_cache(maxsize=1)
def modes():
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/inspector-mode-identities.json').read_text(encoding='utf-8'))
    exact('8b04f3b271e614b3e103853b44a7851a63d79d0e', fixture['sourceCommit'])
    exact('5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607', fixture['databaseLogicalSha256'])
    result = {}
    for case in fixture['modeFamilies']:
        choices = case['choices']
        assert len(choices) == len(set(choices))
        assert case['name'] not in result
        result[case['name']] = choices
    return result


def core_keys(record):
    assert type(record) is dict and CORE <= set(record) <= CORE | {'inspection_ids', 'boosters'}
    if 'boosters' in record:
        rows = record['boosters']; assert type(rows) is list and rows
        slots = set()
        for row in rows:
            assert type(row) is dict
            exact({'name', 'slot', 'active', 'side_effects'}, set(row))
            assert type(row['name']) is str and row['name']
            assert type(row['slot']) is int and 1 <= row['slot'] <= 2**31 - 1 and row['slot'] not in slots
            slots.add(row['slot']); assert type(row['active']) is bool
            effects = row['side_effects']; assert type(effects) is list
            ids = []
            for effect in effects:
                assert type(effect) is dict
                exact({'effect_id', 'active'}, set(effect))
                assert type(effect['effect_id']) is int and 1 <= effect['effect_id'] <= 2**31 - 1
                assert type(effect['active']) is bool
                ids.append(effect['effect_id'])
            exact(sorted(set(ids)), ids)
    if 'inspection_ids' in record:
        spec = record['spec']; assert type(spec) is dict
        choices = modes().get(spec['ship'], [])
        if 'mode' in spec:
            assert type(spec['mode']) is int and spec['mode'] in choices
        counts = dict(ship=1, modules=len(spec['modules']), drones=len(spec['drones']),
                      fighters=len(spec.get('fighters', [])), implants=len(record['implants']),
                      boosters=len(record.get('boosters', spec['boosters'])), cargo=len(spec.get('cargo', [])), mode=int(bool(choices)))
        saved = record['inspection_ids']; assert type(saved) is dict
        exact(set(counts), set(saved)); keys = []
        for family, count in counts.items():
            values = saved[family]; assert type(values) is list and len(values) == count
            assert all(type(value) is str and re.fullmatch('[0-9a-f]{32}', value) for value in values)
            keys.extend(values)
        assert len(keys) == len(set(keys))
    return set(record) - {'inspection_ids'}


def graph_identities(records):
    assert type(records) is dict
    keys = []
    for record in records.values():
        exact(CORE | ({'boosters'} if 'boosters' in record else set()), core_keys(record))
        keys.extend(value for values in record.get('inspection_ids', {}).values() for value in values)
    assert len(keys) == len(set(keys)), 'Inspector identities must be unique across saved fits'


def copy_record(expected, actual):
    fields = core_keys(expected)
    exact(fields, core_keys(actual))
    exact({key: expected[key] for key in fields}, {key: actual[key] for key in fields})
    exact('inspection_ids' in expected, 'inspection_ids' in actual)
    if 'inspection_ids' in expected:
        first = {key for values in expected['inspection_ids'].values() for key in values}
        second = {key for values in actual['inspection_ids'].values() for key in values}
        assert first.isdisjoint(second), 'Copied fits must have fresh inspector identities'
