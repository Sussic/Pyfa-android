#!/usr/bin/env python3
"""Original comparison sort sequences, including stable equal-key reversals."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, bootstrap, compare, logical_database_digest, validate_source


def export(source, database, metadata):
    validate_source(source)
    configuration = bootstrap(source, database); configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import wx
    import eos.db
    app = wx.App(False)
    from tools.android_reference.inspector_metadata_oracle import load
    observe = load(source, sorts_only=True)
    items = [observe(eos.db.getItem(row['item_id'])) for row in metadata['items']]
    if any(name.startswith('android_bridge') for name in sys.modules): raise ValueError('Android imported into sort reference')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source): raise ValueError('Reference imported outside pinned source')
    return dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(configuration.settings), items=items, probes=observe.sort_probes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export',)); parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--database', required=True, type=Path); parser.add_argument('--fixture', required=True, type=Path)
    args = parser.parse_args()
    metadata = json.loads((ROOT / 'tools/android_reference/fixtures/inspector-metadata.json').read_text(encoding='utf-8'))
    compare(SOURCE_COMMIT, metadata['sourceCommit'])
    compare(logical_database_digest(args.database.resolve()), metadata['databaseLogicalSha256'])
    result = export(args.source.resolve(), args.database.resolve(), metadata)
    args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Exported {len(result["items"])} original variation sort sequences')


if __name__ == '__main__': main()
