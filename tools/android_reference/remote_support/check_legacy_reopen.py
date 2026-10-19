#!/usr/bin/env python3
"""Reopen an actual pre-fix populated graph without rewriting legacy edge order."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import resource
import sqlite3
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from tools.android_headless.check_remote_support_parity import Candidate, exact, sha, write, PROCESS_NONCE


def main(args):
    assert 0 < resource.getrlimit(resource.RLIMIT_AS)[0] <= 1024**3
    before_sha = sha(args.store)
    with sqlite3.connect(args.store.as_uri()+'?mode=ro', uri=True) as connection:
        before = json.loads(connection.execute('SELECT payload FROM graph_state').fetchone()[0])
    oracle = json.loads(args.oracle.read_text())
    args.suite = 'repair'; args.reverse = True; args.phase = 'reopen'
    candidate = Candidate(args, oracle)
    expected_stage = 'add_source_a_to_target_c'
    candidate.stage = 'legacy_populated_reopen'
    with candidate.observe_work():
        exact(before, candidate.session.graph.snapshot()['graph'], 'legacy graph unchanged')
        actual = candidate.sample()
        candidate.verify_sample(oracle['states'][expected_stage], actual, 'legacy original reverse graph')
        order = candidate.edge_order()
        exact(oracle['states'][expected_stage]['projection_iteration'], order['actual'], 'legacy actual source order')
        exact(['source_b', 'source_a'], order['actual']['target_c'], 'pre-fix retained source sequence')
        # This is a real persisted pre-correction graph, not a fabricated object.
        for key in candidate.session._fits:
            history = candidate.session.history_details(key)
            assert history['undo_count'] == history['redo_count'] == 0
        assert not candidate.runtime._forbidden and not candidate.network_attempts
    exact(before_sha, sha(args.store), 'legacy store bytes not rewritten')
    write(args.output, dict(status='PASS actual pre-fix store reopened without migration/reordering',
        process_nonce=PROCESS_NONCE, store_sha256=before_sha, original_receipt_sha256=sha(args.oracle),
        expected_stage=expected_stage, values=actual, edge_order=order, requests=candidate.requests,
        preserved_graph=before, histories_reset=True))
    print('PASS legacy populated graph exact bytes/order/original values')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('store', 'oracle', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    main(parser.parse_args())
