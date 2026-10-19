"""Independent complete effects/variations for every remaining fitted context item."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, compare, logical_database_digest


def inputs():
    content = gzip.decompress((ROOT / 'tools/android_reference/fixtures/inspector-contexts.json.gz').read_bytes())
    fixture = json.loads(content)
    compare(SOURCE_COMMIT, fixture['sourceCommit'])
    from tools.android_reference.inspector_contexts import validate_fixture
    validate_fixture(fixture)
    targets = [target for case in fixture['cases'] for state in case['states'] for target in state['targets']]
    return dict(sourceCommit=fixture['sourceCommit'], databaseLogicalSha256=fixture['databaseLogicalSha256'],
                cases=[dict(targets=targets)]), hashlib.sha256(content).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    args = parser.parse_args(); attributes, digest = inputs()
    compare(logical_database_digest(args.database.resolve()), attributes['databaseLogicalSha256'])
    from tools.android_reference.inspector_metadata import export, verify
    if args.action == 'export':
        if args.source is None: parser.error('export requires --source')
        result = export(args.source.resolve(), args.database.resolve(), attributes)
        result['context_fixture_sha256'] = digest
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["items"])} independent remaining-context metadata items')
    else:
        fixture = json.loads(args.fixture.read_text(encoding='utf-8'))
        compare(digest, fixture['context_fixture_sha256'])
        verify(args.database.resolve(), attributes, fixture)


if __name__ == '__main__': main()
