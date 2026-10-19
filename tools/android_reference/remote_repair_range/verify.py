#!/usr/bin/env python3
"""JSON-only final original G05.1 receipt verifier; never imports EOS/adapter."""
import argparse
import hashlib
import json
import math
from pathlib import Path

SUITES = ('ordinary', 'drones', 'spool', 'ancillary', 'linked')
EXPECTED_STAGES = {'ordinary': 7, 'drones': 4, 'spool': 6, 'ancillary': 9, 'linked': 13}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(paths, repo):
    receipts = [json.loads(path.read_text()) for path in paths]
    assert [r['suite'] for r in receipts] == list(SUITES), 'Preserve exact suite order'
    assert len({r['process_nonce'] for r in receipts}) == len(SUITES)
    common = receipts[0]
    total_states = total_curves = total_points = 0
    for path, receipt in zip(paths, receipts):
        assert receipt['status'] == 'passed'
        assert receipt['time_cache_empty'] is True
        assert receipt['forbidden_attempts'] == receipt['network_attempts'] == []
        assert receipt['limits'] == dict(address_space_bytes=1024**3, external_timeout_seconds=180)
        assert receipt['elapsed_seconds'] < 180 and receipt['peak_rss_kib'] < 1024**2
        assert len(receipt['states']) == EXPECTED_STAGES[receipt['suite']]
        for field in ('dataset_sha256', 'dataset_metadata', 'source', 'source_commit', 'settings', 'harness_files', 'fixture_files'):
            assert receipt[field] == common[field], (receipt['suite'], field)
        for relative, digest in {**receipt['source_files'], **receipt['original_imports']}.items():
            assert sha(Path(receipt['source'])/relative) == digest
            assert sha(repo/relative) == digest
        for relative, digest in {**receipt['harness_files'], **receipt['fixture_files']}.items():
            assert sha(repo/relative) == digest
        for stage in receipt['states'].values():
            for fit in stage['fits'].values():
                assert fit['inputs']['legal'] is True
                assert fit['inputs']['declared_factor_reload'] is fit['inputs']['effective_factor_reload']
                assert fit['source_service_options']['useGlobalForceReload'] is fit['inputs']['effective_factor_reload']
                assert set(fit['source_columns']) == {'shield', 'armor', 'hull'}
                assert all(v['unit'] == 'HP/s' and math.isfinite(v['value']) and v['value'] >= 0 for v in fit['source_columns'].values())
                for curve in fit['curves']:
                    n = len(curve['distance_m']); total_curves += 1; total_points += n
                    assert n == len(curve['distance_km']) == len(curve['repair_hp_s'])
                    assert n == 1 or 51 <= n <= 201
                    assert n == curve['point_calls'] == curve['application_calls']
                    assert curve['request']['time'] is None
                    assert all(type(curve['request'][key]) is bool for key in ('ancReload', 'ignoreLockRange', 'ignoreDCR'))
                    assert all(math.isfinite(v) and v >= 0 for key in ('distance_m', 'distance_km', 'repair_hp_s') for v in curve[key])
                    assert curve['distance_km'] == [v/1000 for v in curve['distance_m']]
                    assert all(a <= b for a,b in zip(curve['distance_m'], curve['distance_m'][1:]))
        total_states += len(receipt['states'])
    return dict(status='passed', suites=list(SUITES), states=total_states,
                recorded_curves=total_curves, recorded_points=total_points,
                observations='Every recorded result repeated in reverse fit-read order',
                peak_rss_kib=max(r['peak_rss_kib'] for r in receipts),
                max_process_seconds=max(r['elapsed_seconds'] for r in receipts),
                receipts={str(p):sha(p) for p in paths})


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('receipts', type=Path, nargs=5)
    args=parser.parse_args()
    print(json.dumps(verify(args.receipts, args.repo), indent=2, sort_keys=True))
