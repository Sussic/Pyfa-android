#!/usr/bin/env python3
"""Complete original effect metadata plus actual item witnesses for every assigned ID."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, bootstrap, compare, logical_database_digest, validate_source


def inputs(database):
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        identities = [row[0] for row in db.execute('SELECT effectID FROM dgmeffects ORDER BY effectID')]
        assigned = [row[0] for row in db.execute('SELECT DISTINCT effectID FROM dgmtypeeffects ORDER BY effectID')]
        witnesses = [dict(effect_id=row[0], item_id=row[1]) for row in db.execute(
            'SELECT e.effectID,min(t.typeID) FROM dgmtypeeffects e JOIN invtypes t ON t.typeID=e.typeID GROUP BY e.effectID ORDER BY e.effectID')]
    compare(assigned, [row['effect_id'] for row in witnesses])
    return dict(effect_ids=identities, assigned_effect_ids=assigned, assignments=witnesses,
                item_ids=sorted({row['item_id'] for row in witnesses}))


def catalog_items():
    import eos.db
    from eos.gamedata import Effect
    definitions = eos.db.get_gamedata_session().query(Effect).order_by(Effect.ID).all()
    layers = [{}]
    for effect in definitions:
        layer = next((layer for layer in layers if effect.name not in layer), None)
        if layer is None:
            layer = {}; layers.append(layer)
        layer[effect.name] = effect
    # This is an explicitly unowned metadata container, never a synthetic game item.
    return [SimpleNamespace(ID=None, effects=named) for named in layers]


def export(source, database):
    validate_source(source)
    config = bootstrap(source, database); config.gamedataCache = False
    import config as desktop_config
    desktop_config.pyfaPath = str(source)
    import wx
    app = wx.App(False)
    import eos.db
    from tools.android_reference.inspector_metadata_oracle import load
    observe = load(source, effects_only=True)
    request = inputs(database)
    catalog = [observe(item) for item in catalog_items()]
    compare(request['effect_ids'], sorted(row['id'] for layer in catalog for row in layer['effects']))
    items = [observe(eos.db.getItem(identity)) for identity in request['item_ids']]
    if any(name.startswith('android_bridge') for name in sys.modules): raise ValueError('Android imported into original effect catalog')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source): raise ValueError('Effect oracle imported outside pinned source: ' + name)
    return dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(config.settings), inputs=request, catalog=catalog, items=items)


def verify(database, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit']); compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    request = inputs(database); compare(request, fixture['inputs'])
    compare(request['item_ids'], [row['item_id'] for row in fixture['items']])
    from tools.android_headless.check import NoDesktop
    sys.meta_path.insert(0, NoDesktop())
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database); compare(engine.settings, fixture['eos_settings'])
    from android_bridge.inspection import effects
    import eos.db
    def check(expected, item):
        actual = effects(item)
        compare(expected['effects'], actual)
        rows = [[row['name'], '' if row['active'] is None else 'Yes' if row['active'] else 'No',
                 ''.join(kind + ' ' for kind in row['types']), str(row['runtime']) if row['runtime'] else '', str(row['id'])]
                for row in actual]
        compare(expected['effect_presentation'], dict(columns=['Name', 'Active', 'Type', 'Run Time', 'ID'], rows=rows))
        return actual
    catalog = catalog_items()
    compare(len(fixture['catalog']), len(catalog))
    for expected, item in zip(fixture['catalog'], catalog): check(expected, item)
    compare(request['effect_ids'], sorted(row['id'] for layer in fixture['catalog'] for row in layer['effects']))
    covered, lists = set(), {}
    for expected in fixture['items']:
        actual = check(expected, eos.db.getItem(expected['item_id']))
        lists[expected['item_id']] = {row['id'] for row in actual}
        covered.update(lists[expected['item_id']])
    compare(request['assigned_effect_ids'], sorted(covered))
    for assignment in request['assignments']:
        if assignment['effect_id'] not in lists[assignment['item_id']]: raise ValueError('Recorded item lost its assigned effect')
    print(f'PASS {len(request["effect_ids"])} complete effect definitions, including unassigned metadata; '
          f'{len(request["assigned_effect_ids"])} assigned IDs across {len(fixture["items"])} complete actual item lists')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify')); parser.add_argument('--source', type=Path)
    parser.add_argument('--database', required=True, type=Path); parser.add_argument('--fixture', required=True, type=Path)
    args = parser.parse_args(); database = args.database.resolve()
    compare(json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256'], logical_database_digest(database))
    if args.action == 'export':
        if args.source is None: parser.error('export requires pinned --source')
        result = export(args.source.resolve(), database)
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported all{len(result["inputs"]["effect_ids"])} effect definitions and{len(result["items"])} item witnesses')
    else: verify(database, json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
