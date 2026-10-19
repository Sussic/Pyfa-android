#!/usr/bin/env python3
"""Independent equipment return witnesses for the complete current inspector matrix."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, compare, logical_database_digest
from tools.android_reference.inspector_attributes import contexts


def coverage(fixture):
    inventory = json.loads((ROOT / 'tools/android_reference/fixtures/inspector-inventory.json').read_text())
    compare(inventory['sourceCommit'], fixture['sourceCommit'])
    compare(inventory['databaseLogicalSha256'], fixture['databaseLogicalSha256'])
    required = {name + ':' + str(index) for name, column in inventory['equipmentColumns'].items()
                for index in range(len(column['returnPaths']))}
    witnessed = {identity for case in fixture['cases'] for target in case['targets']
                 for mode in target['expected'] for identity in mode['returns']}
    if not witnessed <= required: raise ValueError('Unexpected equipment return witness')
    return dict(required_return_ids=sorted(required), witnessed_return_ids=sorted(witnessed),
                remaining_return_ids=sorted(required - witnessed))


def export(source, database, attributes):
    from tools.android_reference.inspector_affectors import export as construct
    from tools.android_reference.inspector_equipment_coverage import original_factory
    result = construct(source, database, attributes, observer_factory=original_factory)
    result['coverage'] = coverage(result)
    return result


def verify(database, attributes, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit'])
    compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    compare([case['spec'] for case in attributes['cases']], [case['spec'] for case in fixture['cases']])
    compare(coverage(fixture), fixture['coverage'])
    from tools.android_headless.check import NoDesktop
    sys.meta_path.insert(0, NoDesktop())
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database)
    compare(fixture['eos_settings'], engine.settings)
    from tools.android_reference.inspector_equipment_coverage import android_observe
    witnessed = set()
    for case in fixture['cases']:
        fit = engine.create_fit(case['spec'])
        current = contexts(fit)
        compare([(row['context'], row['item_id']) for row in case['targets']],
                [(kind, item.ID) for kind, stuff, item, charge in current])
        for (kind, stuff, item, charge), expected in zip(current, case['targets']):
            actual = android_observe(stuff, item, fit)
            compare(expected['expected'], actual, case['spec']['name'] + '.' + kind)
            for mode in actual: witnessed.update(mode['returns'])
    print(f'PASS {len(fixture["cases"])} equipment cases; {len(witnessed)} original return paths witnessed across raw/EHP display probes')
    compare(fixture['coverage']['witnessed_return_ids'], sorted(witnessed))
    print(f'{len(fixture["coverage"]["remaining_return_ids"])} required return paths remain explicitly unwitnessed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--attributes', type=Path, default=ROOT / 'tools/android_reference/fixtures/inspector-attributes.json')
    args = parser.parse_args()
    attributes = json.loads(args.attributes.read_text(encoding='utf-8'))
    compare(SOURCE_COMMIT, attributes['sourceCommit'])
    compare(logical_database_digest(args.database.resolve()), attributes['databaseLogicalSha256'])
    if args.action == 'export':
        if args.source is None: parser.error('export requires pinned --source')
        result = export(args.source.resolve(), args.database.resolve(), attributes)
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["cases"])} independently traced equipment cases')
    else: verify(args.database.resolve(), attributes, json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
