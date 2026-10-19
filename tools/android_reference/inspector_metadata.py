#!/usr/bin/env python3
"""Independent original effects/variation presentation, separate adapter verifier."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, bootstrap, compare, logical_database_digest, validate_source


def export(source, database, attributes):
    validate_source(source)
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import wx
    import eos.db
    app = wx.App(False)
    from tools.android_reference.inspector_metadata_oracle import load
    observe = load(source)
    identities = sorted({target['item_id'] for case in attributes['cases'] for target in case['targets']})
    rows = [observe(eos.db.getItem(identity)) for identity in identities]
    if any(name.startswith('android_bridge') for name in sys.modules):
        raise ValueError('Android implementation imported into independent metadata exporter')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source):
                raise ValueError('Metadata reference imported outside pinned source: ' + name)
    return dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(configuration.settings), items=rows)


def verify(database, attributes, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit'])
    compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    compare(sorted({target['item_id'] for case in attributes['cases'] for target in case['targets']}),
            [row['item_id'] for row in fixture['items']])
    from android_bridge import HeadlessEngine
    from android_bridge.inspection import effects, variations
    engine = HeadlessEngine(database)
    compare(fixture['eos_settings'], engine.settings)
    import eos.db
    count = 0
    for expected in fixture['items']:
        item = eos.db.getItem(expected['item_id'])
        actual_effects = effects(item)
        compare(expected['effects'], actual_effects, item.name + '.effects')
        presentation = [[row['name'], '' if row['active'] is None else 'Yes' if row['active'] else 'No',
                         ''.join(kind + ' ' for kind in row['types']),
                         str(row['runtime']) if row['runtime'] else '', str(row['id'])] for row in actual_effects]
        compare(expected['effect_presentation'], dict(columns=['Name', 'Active', 'Type', 'Run Time', 'ID'], rows=presentation), item.name + '.effect_presentation')
        actual = variations(item)
        compare(expected['variation_ids'], [row['id'] for row in actual['rows']], item.name + '.family')
        compare(expected['variation_columns'], actual['columns'], item.name + '.columns')
        for mode in ('normal', 'raw'):
            rows = [[row['name']] + [cell['display' if mode == 'normal' else 'raw'] if cell['available'] else '' for cell in row['values']]
                    + [row['price']['display'] if row['price']['available'] else ''] for row in actual['rows']]
            columns = ['Item'] + [column['label'] for column in actual['columns']] + ['Price']
            compare(expected['variation_presentation'][mode], dict(columns=columns, rows=rows), item.name + '.' + mode)
            count += sum(len(row) for row in rows)
    print(f'PASS: {len(fixture["items"])} complete item effect lists and original variation families; {count} original normal/raw cells')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--attributes', type=Path, default=ROOT / 'tools/android_reference/fixtures/inspector-attributes.json')
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    attributes = json.loads(args.attributes.read_text(encoding='utf-8'))
    compare(SOURCE_COMMIT, attributes['sourceCommit'])
    compare(logical_database_digest(args.database.resolve()), attributes['databaseLogicalSha256'])
    if args.action == 'export':
        if args.source is None: parser.error('export requires --source')
        result = export(args.source.resolve(), args.database.resolve(), attributes)
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["items"])} original item effects and variation comparisons')
    else: verify(args.database.resolve(), attributes, json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
