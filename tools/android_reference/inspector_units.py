#!/usr/bin/env python3
"""All pinned unit definitions through unchanged original attribute formatting."""
import argparse
import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, bootstrap, compare, logical_database_digest, validate_source


def export(source, database):
    validate_source(source)
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.gamedata import Unit
    from gui.utils.numberFormatter import formatAmount, roundDec
    path = source / 'gui/builtinItemStatsViews/itemAttributes.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'FormatValue')
    method.decorator_list = []
    namespace = dict(formatAmount=formatAmount, roundDec=roundDec)
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
    units = eos.db.get_gamedata_session().query(Unit).order_by(Unit.ID).all()
    rows = []
    for unit in units:
        # IDs use known catalogue identities and an absent/zero witness. Rig
        # sizes use all four valid values; Boolean preserves numeric and bool
        # inputs. Other units retain zero, fractional, signed and large values.
        samples = {'Sizeclass': [1, 2, 3, 4], 'Boolean': [0, 1, False, True],
                   'typeID': [587, 0], 'groupID': [25, 0], 'attributeID': [4, 0]}.get(
                       unit.name, [0, 1, 1.25, -1.25, 123456.789])
        for value in samples:
            rows.append(dict(unit=dict(id=unit.ID, name=unit.name, display=unit.displayName), value=value,
                             expected=namespace['FormatValue'](*unit.PreformatValue(value))))
    if any(name.startswith('android_bridge') for name in sys.modules):
        raise ValueError('Android implementation imported into independent unit exporter')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source):
                raise ValueError('Unit reference imported outside pinned source: ' + name)
    return dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(configuration.settings), units=rows)


def verify(database, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit'])
    compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    from android_bridge import HeadlessEngine
    from android_bridge.inspection import _formatted
    engine = HeadlessEngine(database)
    compare(fixture['eos_settings'], engine.settings)
    import eos.db
    from eos.gamedata import Unit
    units = {unit.ID: unit for unit in eos.db.get_gamedata_session().query(Unit).all()}
    compare(sorted(units), sorted({row['unit']['id'] for row in fixture['units']}))
    for row in fixture['units']:
        unit = units[row['unit']['id']]
        compare(row['unit'], dict(id=unit.ID, name=unit.name, display=unit.displayName))
        compare(row['expected'], _formatted(row['value'], SimpleNamespace(unit=unit)), unit.name + ':' + str(row['value']))
    print(f'PASS: all {len(units)} unit definitions and {len(fixture["units"])} independent formatting witnesses')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'export':
        if args.source is None: parser.error('export requires --source')
        result = export(args.source.resolve(), args.database.resolve())
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["units"])} original unit formatting witnesses')
    else: verify(args.database.resolve(), json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
