"""Build synthetic existing-roll inputs for C04 instrumentation; no expected outputs.

Run with the headless venv, -I -B. Output must be new and outside the checkout.
The seed is installed only into a fresh disposable emulator debug installation.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--family',choices=('details','conservation'),default='details')
    args = parser.parse_args()
    output = args.output.resolve()
    assert not output.exists() and not output.is_relative_to(ROOT)
    reference = ROOT / f'tools/android_reference/fixtures/drone-{args.family}.json'
    expected = json.loads(reference.read_text())
    assert hashlib.sha256(args.database.read_bytes()).hexdigest() == expected['database_sha256']
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.store import GraphStore
    engine = HeadlessEngine(args.database)
    identity = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    graph = None
    for case in expected['cases']:
        spec = deepcopy(case['spec'])
        fit = engine.create_fit(spec, restore=True)
        bridge = BridgeSession(engine, fit, spec)
        bridge._dataset_identity = identity
        part = deepcopy(bridge._graph(bridge._records, bridge._revisions))
        if graph is None:
            graph = part
        else:
            assert not set(graph['records']) & set(part['records'])
            for field in ('records', 'revisions', 'modified'):
                graph[field].update(part[field])
            graph['fit_order'].extend(part['fit_order'])
        bridge._reset_storage()
    assert len(graph['records']) == len(expected['cases']) == (4 if args.family=='details' else 14)
    output.mkdir(parents=True)
    store = GraphStore(output / 'graph.sqlite3')
    attempt = store.prepare(graph)
    store.write(attempt)
    assert store.confirm(attempt) == 'new'
    store.accept(attempt)
    # Reopen through the real persistence reader; expected numerical values
    # continue to come exclusively from the independent desktop JSON.
    restored = BridgeSession.open(engine, store.path, identity, None)
    assert restored._records == graph['records']
    manifest = dict(synthetic_inputs_only=True, reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                    database_sha256=expected['database_sha256'], source_commit=expected['source_commit'],
                    graph_sha256=hashlib.sha256(store.path.read_bytes()).hexdigest(),
                    names=[case['spec']['name'] for case in expected['cases']])
    (output / 'seed.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
