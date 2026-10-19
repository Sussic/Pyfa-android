#!/usr/bin/env python3
"""Full worker-owned inspector payload isolation/finite JSON and effect preservation."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_headless.check import NoDesktop
sys.meta_path.insert(0, NoDesktop())
from tools.android_reference.reference import SOURCE_COMMIT, compare, logical_database_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    args = parser.parse_args(); database = args.database.resolve()
    fixtures = ROOT / 'tools/android_reference/fixtures'
    attributes = json.loads((fixtures / 'inspector-attributes.json').read_text(encoding='utf-8'))
    catalog = json.loads((fixtures / 'inspector-effect-catalog.json').read_text(encoding='utf-8'))
    properties = json.loads((fixtures / 'inspector-properties.json').read_text(encoding='utf-8'))
    units = json.loads((fixtures / 'inspector-units.json').read_text(encoding='utf-8'))
    probes = json.loads((fixtures / 'inspector-equipment-probes.json').read_text(encoding='utf-8'))
    domains = json.loads((fixtures / 'inspector-guard-domains.json').read_text(encoding='utf-8'))
    compare([case['spec'] for case in attributes['cases']], [case['spec'] for case in properties['cases']])
    compare(dict(character_name='Headless synthetic skills'), properties['inputs'])
    for fixture in (attributes, catalog, properties, units, probes, domains):
        compare(SOURCE_COMMIT, fixture['sourceCommit'])
        compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    from android_bridge import HeadlessEngine
    from android_bridge.inspection import details, base_details, options
    engine = HeadlessEngine(database)
    from android_bridge.inspection_diagnostics import unit_witnesses
    compare(units['eos_settings'], engine.settings)
    samples = [dict(unit_id=row['unit']['id'], value=row['value']) for row in units['units']]
    expected_units = {row['unit']['id']: row['unit'] for row in units['units']}
    actual_units = unit_witnesses(samples)
    compare([expected_units[key] for key in sorted(expected_units)], actual_units['units'])
    compare([dict(unit=row['unit'], value=row['value'], formatted=row['expected']) for row in units['units']], actual_units['witnesses'])
    assert len(expected_units) == 60 and len(samples) == 289
    for invalid in ({}, [dict(unit_id=True, value=1)], [dict(unit_id=-1, value=1)],
                    [dict(unit_id=1, value=None)], [dict(unit_id=1, value=float('nan'))],
                    [dict(unit_id=1, value=float('inf'))], [dict(unit_id=1, value=1, expected='fake')]):
        try: unit_witnesses(invalid)
        except ValueError: pass
        else: raise AssertionError('Malformed unit diagnostic input accepted')
    print('PASS: headless unit diagnostic contract, all60 definitions/289 original witnesses/seven malformed inputs')
    fitted = 0; property_members = 0
    for case, property_case in zip(attributes['cases'], properties['cases']):
        fit = engine.create_fit(case['spec'])
        compare(properties['inputs']['character_name'], fit.character.name)
        fitted_expected = [row for row in property_case['targets'] if row['context'] != 'base']
        base_expected = {row['item_id']: row for row in property_case['targets'] if row['context'] == 'base'}
        targets = options(engine, fit)
        compare(len(fitted_expected), len(targets))
        for target, expected in zip(targets, fitted_expected):
            compare((expected['context'], expected['item_id']), (target['context'], target['item_id']))
            selection = {key: target[key] for key in ('context', 'index', 'item_id')}
            payload = details(engine, fit, selection)
            base = base_details(engine, target['item_id'])
            json.dumps(payload, allow_nan=False); json.dumps(base, allow_nan=False)
            compare([row['contract'] for row in expected['expected']], payload['properties'])
            compare([row['contract'] for row in base_expected[target['item_id']]['expected']], base['properties'])
            property_members += len(expected['expected'])
            fitted += 1
    for row in catalog['items']:
        payload = base_details(engine, row['item_id'])
        json.dumps(payload, allow_nan=False)
        compare(row['effects'], payload['effects'])
    print(f'PASS {len(attributes["cases"])} cases/{fitted} fitted plus matching base payloads; '
          f'{len(catalog["items"])} complete catalog base payloads/effect lists; '
          f'{property_members} fitted property members plus complete matching base properties; desktop imports blocked')

    from android_bridge.inspection_equipment_diagnostics import equipment_probes, guard_domains
    for fixture in (probes, domains): compare(fixture['eos_settings'], engine.settings)
    probe_spec = {**attributes['cases'][0]['spec'], 'name': 'Inspector booster duration probes',
                  'modules': [], 'drones': [], 'fighters': [], 'cargo': [], 'environments': []}
    probe_fit = engine.create_fit(probe_spec)
    request = deepcopy(probes['inputs']); request.pop('booster_duration_unit')
    expected = deepcopy(probes['results'])
    for row in request['conditional']: row.pop('expected_error')
    for row in expected['conditional']: row['input'].pop('expected_error')
    previous_trace = sys.gettrace()
    actual = equipment_probes(engine, probe_fit, request)
    compare(expected, actual['results'])
    assert sys.gettrace() is previous_trace and not probe_fit.boosters
    compare(domains['results'], guard_domains(domains['inputs']))
    assert sys.gettrace() is previous_trace
    assert len(domains['inputs']) == 2793
    for invalid in ({}, [dict(group='ECM', values={}, expected=None)]):
        try: guard_domains(invalid)
        except ValueError: pass
        else: raise AssertionError('Malformed guard diagnostic accepted')
    injected = deepcopy(request); injected['conditional'][0]['expected_error'] = None
    try: equipment_probes(engine, probe_fit, injected)
    except ValueError: pass
    else: raise AssertionError('Equipment diagnostic accepted expectation field')
    print('PASS: source-free equipment diagnostic complete original probes and2793 domains; trace/booster restoration and malformed rejection')


if __name__ == '__main__': main()
