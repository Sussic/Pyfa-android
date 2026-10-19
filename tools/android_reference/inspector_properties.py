#!/usr/bin/env python3
"""Complete original property getter/value expectations with separate verification."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, compare, logical_database_digest
from tools.android_reference.inspector_attributes import contexts


def export(source, database, attributes):
    from tools.android_reference.inspector_affectors import export as construct_original
    from tools.android_reference.inspector_property_oracle import load
    result = construct_original(source, database, attributes, observer_factory=load, character_name='Headless synthetic skills')
    result['inputs'] = dict(character_name='Headless synthetic skills')
    return result


def verify(database, attributes, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit']); compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    compare([case['spec'] for case in attributes['cases']], [case['spec'] for case in fixture['cases']])
    compare(dict(character_name='Headless synthetic skills'), fixture['inputs'])
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database)
    from android_bridge.inspection import properties
    compare(fixture['eos_settings'], engine.settings)
    count, supported = 0, 0
    for case in fixture['cases']:
        fit = engine.create_fit(case['spec'])
        compare(fixture['inputs']['character_name'], fit.character.name)
        current = contexts(fit)
        compare([(target['context'], target['item_id']) for target in case['targets']], [(kind, item.ID) for kind, _, item, _ in current])
        for (kind, stuff, item, charge), target in zip(current, case['targets']):
            actual = properties(stuff, item)
            compare([row['contract'] for row in target['expected']], actual, case['spec']['name'] + '.' + kind + '.' + item.name)
            for original, row in zip(target['expected'], actual):
                if original['original_primitive_display'] is not None:
                    compare(original['original_primitive_display'], str(row['value']), item.name + '.' + row['name'] + '.original_display')
                count += 1; supported += row['available']
    print(f'PASS: {len(fixture["cases"])} cases; {count} complete property members, {supported} supported original values')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify')); parser.add_argument('--source', type=Path)
    parser.add_argument('--database', required=True, type=Path); parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--attributes', type=Path, default=ROOT / 'tools/android_reference/fixtures/inspector-attributes.json')
    args = parser.parse_args(); attributes = json.loads(args.attributes.read_text(encoding='utf-8'))
    compare(SOURCE_COMMIT, attributes['sourceCommit']); compare(logical_database_digest(args.database.resolve()), attributes['databaseLogicalSha256'])
    if args.action == 'export':
        if args.source is None: parser.error('export requires --source')
        result = export(args.source.resolve(), args.database.resolve(), attributes)
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["cases"])} complete original property cases')
    else: verify(args.database.resolve(), attributes, json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
