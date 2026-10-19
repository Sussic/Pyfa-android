"""Independent complete EOS afflictions, including unused and unchanged rows."""
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, compare, logical_database_digest


def export(source, database, attributes):
    from tools.android_reference.inspector_affectors import export as construct
    from tools.android_reference.inspector_contexts import flat_affectors, roles
    expected = iter(target for case in attributes['cases'] for target in case['targets'])

    def factory(source):
        import eos.db
        from tools.android_reference.inspector_attribute_oracle import load
        oracle = load(source)

        def observe(stuff, item, fit):
            target = next(expected)
            charge = target['context'] == 'charge'
            compare(target['item_id'], item.ID)
            # Materialize the same original attribute getters before observing
            # cache-sensitive EOS afflictions. No Android producer is imported.
            compare(target['expected'], oracle['observe'](stuff, item, charge),
                    fit.name + '.' + target['context'] + '.attributes')
            return dict(sql_roles=roles(eos.db.saveddata_session, fit),
                        affectors=flat_affectors(stuff, item, fit, charge, source_positions=True))
        return observe

    result = construct(source, database, attributes, observer_factory=factory,
                       character_name='Headless synthetic skills')
    if next(expected, None) is not None:
        raise ValueError('Missing independent target observations')
    return result


def verify(database, attributes, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit'])
    compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    compare([case['spec'] for case in attributes['cases']], [case['spec'] for case in fixture['cases']])
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database)
    from android_bridge.inspection import attributes as inspect_attributes, affectors
    from tools.android_reference.inspector_attributes import contexts
    from tools.android_reference.inspector_contexts import roles
    import eos.db
    compare(fixture['eos_settings'], engine.settings)
    count = 0
    for case in fixture['cases']:
        fit = engine.create_fit(case['spec'])
        current = contexts(fit)
        compare([(row['context'], row['item_id']) for row in case['targets']],
                [(kind, item.ID) for kind, _, item, _ in current])
        for (kind, stuff, item, charge), target in zip(current, case['targets']):
            # This host path has no saved UUID resolver. Its SQL identity is
            # independently checked in full, rather than normalized away.
            compare(target['expected']['sql_roles'], roles(eos.db.saveddata_session, fit), fit.name + '.sql_roles')
            inspect_attributes(stuff, item, charge)
            expected = []
            for row in target['expected']['affectors']:
                row = dict(row)
                row['source_target'] = row.pop('source_role')
                row['source_fit_key'] = None
                expected.append(row)
            actual = affectors(stuff, item, charge)
            compare(expected, actual, fit.name + '.' + kind + '.' + item.name + '.affectors')
            count += len(actual)
    print(f'PASS {len(fixture["cases"])} complete original affector cases / {count} raw rows')


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
        if args.source is None:
            parser.error('export requires --source')
        result = export(args.source.resolve(), args.database.resolve(), attributes)
        content = (json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
        args.fixture.write_bytes(gzip.compress(content, mtime=0))
        print(f'Exported {len(result["cases"])} complete original affector cases / {len(content)} decoded bytes')
    else:
        verify(args.database.resolve(), attributes, json.loads(gzip.decompress(args.fixture.read_bytes())))


if __name__ == '__main__':
    main()
