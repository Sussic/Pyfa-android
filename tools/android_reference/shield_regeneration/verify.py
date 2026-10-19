#!/usr/bin/env python3
"""JSON-only G04 original receipt verification; no EOS/candidate imports."""
import argparse
import hashlib
import json
import math
from pathlib import Path

SUITES=('defenses','boundaries','history')
EXPECTED_STAGES={'defenses':1,'boundaries':1,'history':27}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(paths,repo):
    receipts=[json.loads(path.read_text()) for path in paths]
    assert [r['suite'] for r in receipts]==list(SUITES)
    assert len({r['process_nonce'] for r in receipts})==3
    common=receipts[0]; stages=curves=points=fits=0
    for path,row in zip(paths,receipts):
        assert row['status']=='passed'
        assert row['forbidden_attempts']==row['network_attempts']==[]
        assert row['limits']==dict(address_space_bytes=1024**3,external_timeout_seconds=180)
        assert row['elapsed_seconds']<180 and row['peak_rss_kib']<1024**2
        assert row['dataset_sha256']==row['dataset_after_sha256']=='68fb9ea965cb046e426f7c068c7508b55a4e82d2a3dceeed3cb948585d6e7203'
        assert row['logical_dataset_sha256']=='5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607'
        assert row['database_bytes']==99897344
        assert len(row['states'])==EXPECTED_STAGES[row['suite']]
        for field in ('dataset_sha256','logical_dataset_sha256','database_bytes','dataset_metadata','source','source_commit','settings','harness_files','fixture_files'):
            assert row[field]==common[field],(row['suite'],field)
        for relative,digest in {**row['source_files'],**row['original_imports']}.items():
            assert sha(Path(row['source'])/relative)==sha(repo/relative)==digest,relative
        for relative,digest in {**row['harness_files'],**row['fixture_files']}.items(): assert sha(repo/relative)==digest,relative
        stage_requests={r['stage']:r['requests'] for r in row['request_trace']}
        for name,stage in row['states'].items():
            stages+=1
            assert set(stage['fits'])==set(row['input_order'])
            for fit in stage['fits'].values():
                fits+=1; inputs=fit['inputs']; assert inputs['legal'] is True
                assert inputs['declared_factor_reload'] is inputs['effective_factor_reload']
                assert fit['source_service_options']['useGlobalForceReload'] is inputs['effective_factor_reload']
                assert fit['source_columns']['capacity']['unit']=='HP'
                assert fit['source_columns']['recharge']['unit']=='s'
                assert [r['request'] for r in fit['curves']]==stage_requests[name]
                for curve in fit['curves']:
                    curves+=1; n=len(curve['x']); points+=n
                    assert n==len(curve['y'])==len(curve['getter_x'])==len(curve['getter_y'])==curve['point_calls']
                    assert n in (1,201)
                    assert all(type(v) in (int,float) and math.isfinite(v) for field in ('x','y','getter_x','getter_y') for v in curve[field])
                    assert all(a<=b for a,b in zip(curve['x'],curve['x'][1:]))
                    assert curve['request']['y_unit']!='%'
        assert row['original_point_calls']==2*sum(len(c['getter_x']) for s in row['states'].values() for f in s['fits'].values() for c in f['curves'])
    return dict(status='passed',suites=list(SUITES),stages=stages,fit_observations=fits,curves=curves,points=points,
                repeated_reverse_order=True,max_process_seconds=max(r['elapsed_seconds'] for r in receipts),
                peak_rss_kib=max(r['peak_rss_kib'] for r in receipts),receipts={str(p):sha(p) for p in paths})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('receipts',type=Path,nargs=3); args=parser.parse_args()
    print(json.dumps(verify(args.receipts,args.repo),indent=2,sort_keys=True))
