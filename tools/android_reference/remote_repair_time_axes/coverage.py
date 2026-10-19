"""Read-only frozen original receipt coverage; no EOS/candidate imports."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
PREFLIGHT=ROOT.parent/'pyfa-g052-preflight-20261018'
SOURCE=ROOT.parent/'cloud-source-receipts/pyfa/reconstructed-source'
FILES=('ordinary-attempt-2.json','drones-attempt-1.json','spool-attempt-1.json','ancillary-attempt-2.json','linked-seed-attempt-2.json','linked-reopen-attempt-2.json','resource-attempt-1.json')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 audit=json.loads((PREFLIGHT/'PREFLIGHT-VERIFY.json').read_text());rows=[];bindings={};lifetimes=[]
 for name in FILES:
  path=PREFLIGHT/name;data=json.loads(path.read_text());digest=sha(path)
  assert any(r['receipt']==name and r['sha256']==digest for r in audit['receipts'])
  assert data['status']=='passed' and data['network_attempts']==data['forbidden_attempts']==[]
  for rel,d in (data['source_files']|data['original_imports']).items():assert sha(SOURCE/rel)==d,rel
  bindings[name]={k:data[k] for k in ('source_files','original_imports','harness_files','dataset_physical_sha256','dataset_logical_sha256','process_nonce','source_kind')};bindings[name]['sha256']=digest;bindings[name]['current_harness_differences']={rel:dict(recorded=d,current=sha(PREFLIGHT/'repo'/rel)) for rel,d in data['harness_files'].items() if sha(PREFLIGHT/'repo'/rel)!=d}
  for stage,state in data['states'].items():
   for label,life in state.get('cache_lifetime',{}).items():
    lifetimes.append(dict(receipt=name,stage=stage,fit=label,amount_first_rows=sum(r['order'][0]=='RepAmount' for r in life['horizon_reads']),cross_order_scalar_maps_exported=False))
   for label,fit in state['fits'].items():
    for si,s in enumerate(fit['samples']):
     for ci,c in enumerate(s['curves']):
      if c['axis']!='time':continue
      exact_horizon=c['range'][1]==s['request']['horizon']
      rows.append(dict(receipt=name,stage=stage,fit=label,sample_index=si,curve_index=ci,requested_range=c['range'],cache_horizon=s['request']['horizon'],exact_fresh_horizon=exact_horizon,ordinate=c['ordinate'],distance_km=None if c['distance_m'] is None else c['distance_m']/1000,options=s['options'],ancillary_reload=s['anc_reload'],x_unit_original='s',x_unit_candidate='s',y_unit='HP' if c['ordinate']=='amount' else 'HP/s',points=len(c['x']),coordinate_transform='identity; preserve order and duplicates',nonsorted=any(b<a for a,b in zip(c['x'],c['x'][1:])),json_pointer=f'/states/{stage}/fits/{label}/samples/{si}/curves/{ci}',original_curve_sha256=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),original_inputs_sha256=hashlib.sha256(json.dumps(data['inputs'][label],sort_keys=True).encode()).hexdigest(),original_source_columns_unit='HP/s'))
 assert len(rows)==2422,len(rows)
 out=dict(status='bound_original_coverage_only',count=len(rows),exact_horizon_count=sum(r['exact_fresh_horizon'] for r in rows),retained_horizon_count=sum(not r['exact_fresh_horizon'] for r in rows),nonsorted_count=sum(r['nonsorted'] for r in rows),receipts=bindings,curves=rows,lifetime_evidence=lifetimes,qualifications=['Graph.sample prepares rate before amount. No amount-only resource admission claim.','Lifetime validates retained/fresh within preparation order, not exported cross-order scalar equality.','Linked prerequisite-skill undo and equivalent zero spool raw differences remain narrowly qualified exactly as predecessor.','No candidate source binding until parent freezes production successor.'])
 with (ROOT/'TIME-ORIGINAL-COVERAGE.json').open('x') as f:json.dump(out,f,indent=2)
 print('Bound',len(rows),'curves;',len(lifetimes),'lifetime state/fit records')
if __name__=='__main__':main()
