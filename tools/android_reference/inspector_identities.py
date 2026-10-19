#!/usr/bin/env python3
"""Independent saved SQL identities for property graph-role comparisons."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, compare, logical_database_digest


def original_roles(session, fit_id):
    def rows(sql):
        return [dict(row) for row in session.execute(sql, dict(fit_id=fit_id)).fetchall()]
    result = dict(
        fit=rows('SELECT ID, name, shipID FROM fits WHERE ID=:fit_id'),
        modules=rows('SELECT ID, fitID, itemID, chargeID, position FROM modules WHERE fitID=:fit_id AND projected=0 ORDER BY position'),
        drones=rows('SELECT groupID, fitID, itemID, amount, amountActive FROM drones WHERE fitID=:fit_id AND projected=0 ORDER BY groupID'),
        fighters=rows('SELECT groupID, fitID, itemID, amount, active FROM fighters WHERE fitID=:fit_id AND projected=0 ORDER BY groupID'))
    if len(result['fit']) != 1: raise ValueError('Missing or ambiguous SQL fit identity')
    return result


def export(source, database, attributes):
    from tools.android_reference.inspector_affectors import export as construct
    def factory(source):
        import eos.db
        return lambda stuff, item, fit: original_roles(eos.db.saveddata_session, fit.ID)
    result = construct(source, database, attributes, observer_factory=factory,
                       character_name='Headless synthetic skills')
    for case in result['cases']:
        roles = case['targets'][0]['expected']
        for target in case.pop('targets'): compare(roles, target['expected'])
        case['expected'] = roles
    return result


def verify(database, attributes, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit'])
    compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    compare([case['spec'] for case in attributes['cases']], [case['spec'] for case in fixture['cases']])
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database)
    import eos.db
    from android_bridge.inspection_diagnostics import sql_roles
    compare(fixture['eos_settings'], engine.settings)
    for case in fixture['cases']:
        fit = engine.create_fit(case['spec'])
        compare(case['expected'], sql_roles(eos.db.saveddata_session, fit.ID), case['spec']['name'])
    print(f'PASS {len(fixture["cases"])} independent SQL identity graphs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    args = parser.parse_args()
    attributes = json.loads((ROOT / 'tools/android_reference/fixtures/inspector-attributes.json').read_text(encoding='utf-8'))
    compare(SOURCE_COMMIT, attributes['sourceCommit'])
    compare(logical_database_digest(args.database.resolve()), attributes['databaseLogicalSha256'])
    if args.action == 'export':
        if args.source is None: parser.error('export requires --source')
        result = export(args.source.resolve(), args.database.resolve(), attributes)
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["cases"])} independent SQL identity graphs')
    else:
        verify(args.database.resolve(), attributes, json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
