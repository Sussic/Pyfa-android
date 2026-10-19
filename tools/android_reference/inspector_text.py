#!/usr/bin/env python3
"""Original real wx HTML-window description/traits text, including copy-all."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

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
    from gui.builtinItemStatsViews.itemDescription import ItemDescription
    from gui.builtinItemStatsViews.itemTraits import ItemTraits
    app = wx.App(False)
    frame = wx.Frame(None, size=(1000, 800))
    def observe(item):
        result = dict(description=item.description,
                      traits=None if item.traits is None else item.traits.display)
        for field, cls in [('description', ItemDescription), ('traits', ItemTraits)]:
            if result[field] is None or result[field] == '':
                result[field + '_plain'] = None
                continue
            panel = cls(frame, None, item)
            window = getattr(panel, field)
            result[field + '_plain'] = window.ToText()
            panel.Destroy()
        return result
    items = [dict(item_id=row['item_id'], expected=observe(eos.db.getItem(row['item_id']))) for row in metadata['items']]
    probes = []
    for text in [None, '', 'First paragraph\n\nSecond paragraph — café 🧪',
                 '<font color="#ff0000">Color</font> <a href="showinfo:626">Vexor</a> &amp; Unicode Ω',
                 '<p>One</p><p>Two<br>Three</p>', '<b>Heading</b><ul><li>First</li><li>Second</li></ul>',
                 'Literal \ufffc and <img src="missing-local-image.png"> image cell']:
        probes.append(dict(input=text, expected=observe(SimpleNamespace(description=text,
            traits=None if text is None else SimpleNamespace(display=text)))))
    frame.Destroy()
    if any(name.startswith('android_bridge') for name in sys.modules): raise ValueError('Android imported into text reference')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source): raise ValueError('Text reference imported outside pinned source')
    return dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(configuration.settings), items=items, probes=probes)


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
    print(f'Exported {len(result["items"])} original HTML-window text pairs and {len(result["probes"])} explicit markup/absence probes')


if __name__ == '__main__': main()
