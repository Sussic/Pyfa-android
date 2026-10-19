#!/usr/bin/env python3
"""New fresh-cache original-only selected-time oracle; explicit --execute required.

Load only frozen preflight harness plus independently pinned original source.
Never import a candidate package. Every requested horizon starts with fresh cache.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time
from types import SimpleNamespace as NS
import uuid
sys.dont_write_bytecode=True

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def horizons(sample):
    boundaries={0.0}
    for row in sample['request']['metadata']:
        def first(node):return node if node['kind']=='CycleInfo' else first(node['sequence'][0])
        leaf=first(row['metadata']);cycle=(leaf['active_ms']+leaf['inactive_ms'])/1000
        boundaries.add(leaf['active_ms']/1000)
        if row['num_shots']:boundaries.add(row['num_shots']*cycle)
        if row['spool_step']:boundaries.add(math.ceil(row['spool_max']/row['spool_step'])*cycle)
    values={0.0}
    for t in boundaries-{0.0}:
        values.update((math.nextafter(t,0),max(0,t-1e-5),t,math.nextafter(t,math.inf),t+1e-5))
    assert len(values)<=31 and all(0<=t<=2500 for t in values)
    return sorted(values)

def main(args):
    start=time.monotonic();assert 0<resource.getrlimit(resource.RLIMIT_AS)[0]<=1024**3
    assert not args.output.exists()
    sys.path.insert(0,str(args.preflight/'repo'))
    from tools.android_reference.remote_repair_time import preflight as frozen
    assert Path(frozen.__file__).resolve().is_relative_to(args.preflight.resolve())
    audit=json.loads((args.preflight/'PREFLIGHT-VERIFY.json').read_text())
    receipts={}
    for suite,filename in [('ordinary','ordinary-attempt-2.json'),('drones','drones-attempt-1.json'),('spool','spool-attempt-1.json'),('ancillary','ancillary-attempt-2.json')]:
        p=args.preflight/filename
        assert any(r['receipt']==filename and r['sha256']==sha(p) for r in audit['receipts'])
        receipts[suite]=json.loads(p.read_text())
    first=receipts['ordinary']
    assert sha(args.database)==first['dataset_physical_sha256']
    for rel,digest in (first['source_files']|first['original_imports']).items():assert sha(args.source/rel)==digest
    frozen.initialize(NS(source=args.source,database=args.database,saved_data=None,phase='seed'))
    boundary=frozen.Boundary();boundary.install();original=frozen.Original(args.source);graph=frozen.Graph(original,boundary)
    results={};specs={}
    for suite,receipt in receipts.items():
        for label,spec in receipt['inputs'].items():
            key=suite+'/'+label; original.make(key,spec);specs[key]=spec;original.configure(key)
            fit=original.fits[key];original.service.recalc(fit);raw_before=frozen.raw_all(original)
            rows=[]
            for sample in receipt['states']['initial']['fits'][label]['samples']:
                if sample['distance_m'] is not None:continue
                for horizon in horizons(sample):
                    graph.fresh();graph.options=sample['options']
                    getter=graph.getters['Distance2RpsGetter']
                    xs,ys=getter.getRange([0,100000],dict(ancReload=sample['anc_reload'],time=horizon),NS(item=fit),None)
                    rows.append(dict(time=horizon,anc_reload=sample['anc_reload'],options=sample['options'],x=xs,y=ys,maps=graph.export_maps(fit,sample['anc_reload'])))
                    graph.internal.clear();graph.phases.clear()
            frozen.exact(raw_before,frozen.raw_all(original),'read only original')
            results[key]=dict(columns=graph.columns(fit),raw=frozen.raw_all(original)[key],inputs=frozen.capture_inputs(fit),curves=rows)
            print('ORIGINAL FRESH',key,len(rows),flush=True)
    imports={}
    for name,module in list(sys.modules.items()):
        assert name.split('.')[0] not in {'android_bridge','mobile_runtime'}
        path=getattr(module,'__file__',None)
        if path and name.split('.')[0] in {'eos','utils'}:
            p=Path(path).resolve(); rel=p.relative_to(args.source).as_posix();imports[rel]=sha(p)
    assert not boundary.attempts and not frozen.plumbing.NETWORK_ATTEMPTS
    assert sha(args.database)==first['dataset_physical_sha256']
    graph.close();boundary.close()
    result=dict(status='passed',kind='independent fresh selected-time original',process_nonce=uuid.uuid4().hex,
        dataset_physical_sha256=first['dataset_physical_sha256'],dataset_logical_sha256=first['dataset_logical_sha256'],
        source_files=original.hashes,original_imports=imports,source_kind=first['source_kind'],inputs=specs,fits=results,
        frozen_receipts={r['receipt']:r['sha256'] for r in audit['receipts']},exporter_sha256=sha(__file__),
        forbidden_attempts=boundary.attempts,network_attempts=frozen.plumbing.NETWORK_ATTEMPTS,
        elapsed_seconds=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    with args.output.open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true')
    for name in ('preflight','source','database','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();assert args.execute
    for name in ('preflight','source','database'):setattr(args,name,getattr(args,name).resolve())
    main(args)
