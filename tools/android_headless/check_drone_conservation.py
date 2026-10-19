"""Bounded F08.03 policy, pinned-EOS, transactional and durable acceptance."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.android_headless.check import NoDesktop,DEPENDENCIES
from tools.android_reference.reference import compare,digest_file
from tools.android_reference.drone_edits import observe,PIN
from tools.android_reference.drone_conservation import POLICY

def main():
 p=argparse.ArgumentParser()
 for n in ('database','reference','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--restore',action='store_true');a=p.parse_args();a.output=a.output.resolve()
 expected=json.loads(a.reference.read_text(encoding='utf-8'))
 compare(POLICY,expected['policy']);compare(PIN,expected['source_commit']);compare(expected['database_sha256'],digest_file(a.database))
 for n,d in expected['source_files'].items():compare(d,digest_file(ROOT/'build/reference-upstream'/n))
 compare(DEPENDENCIES,{n:importlib.metadata.version(n) for n in DEPENDENCIES})
 assert not a.output.is_relative_to(ROOT)
 guard=NoDesktop();network=[];sys.meta_path.insert(0,guard)
 def audit(event,args):
  if event in ('socket.connect','socket.bind','socket.getaddrinfo'):network.append(event);raise RuntimeError('Network disabled')
 sys.addaudithook(audit)
 from android_bridge.engine import HeadlessEngine
 from android_bridge.contract import BridgeSession
 from android_bridge.store import GraphStore,StoreWriteRejected
 from android_bridge import drones
 engine=HeadlessEngine(a.database)
 identity=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
 bridge=None;reopens=[];checks=[]
 def state(history=True):
  r=dict(records=deepcopy(bridge._records),revisions=dict(bridge._revisions),snapshots=deepcopy(bridge._snapshots),
         details={k:bridge.drone_details(k) for k in bridge._fits},recent=bridge.recent_items())
  if history:r['history']={k:bridge.history_details(k) for k in bridge._fits}
  return r
 def send(op,args,ok=True,stale=False):
  keys={args[k] for k in ('fit_id','source_id','target_id') if k in args}
  r=json.loads(bridge.dispatch(json.dumps(dict(version=1,request_id='conserve',session_id=bridge.session_id,operation=op,arguments=args,
    expected_revisions={k:0 if stale else bridge._revisions[k] for k in keys}))))
  assert r['status']==('ok' if ok else 'error'),r
  return r
 def report(key):
  return dict(core=observe(bridge.get_fit(key)),stats=engine.projection_snapshot(bridge.get_fit(key)),
    metrics=[{n:next(m['value'] for m in row['metrics'] if m['key']==n) for n in expected['metrics']}
             for row in bridge.drone_details(key)['stacks']])
 def atomic(op,args,stale=False):
  before=state();raw=bridge._store.path.read_bytes();send(op,args,False,stale)
  compare(before,state());assert raw==bridge._store.path.read_bytes()
 if a.restore:
  for saved in json.loads((a.output/'reopens.json').read_text()):
   bridge=BridgeSession.open(engine,Path(saved['store']),identity,None)
   compare(saved['state'],state(False));assert bridge.persistence_info['opened_existing'];bridge._reset_storage()
  (a.output/'restored.json').write_text(json.dumps(dict(matched=True,stores=len(json.loads((a.output/'reopens.json').read_text())))))
  assert not guard.attempts and not network;return
 a.output.mkdir(parents=True,exist_ok=False)
 for index,case in enumerate(expected['cases']+expected['linked']):
  if bridge:bridge._reset_storage()
  spec=deepcopy(case['spec']);fit=engine.create_fit(spec,restore=True);bridge=BridgeSession(engine,fit,spec)
  owner=bridge.sample_id;bridge._dataset_identity=identity
  bridge._store=GraphStore(a.output/f'case-{index}.sqlite3');attempt=bridge._store.prepare(bridge._graph(bridge._records,bridge._revisions))
  assert bridge._write_and_confirm(attempt)=='new';bridge._store.accept(attempt)
  send('set_fit_restrictions',dict(fit_id=owner,ignore=False));ids=[owner]
  for recipient in case.get('recipients',[]):
   key=send('create_fit',dict(spec=deepcopy(recipient)))['fits'][0]['id'];ids.append(key)
   send('set_fit_restrictions',dict(fit_id=key,ignore=False))
   send('add_'+case['link'],dict(source_id=owner,target_id=key,active=True,**(dict(range_m=0.0,amount=1) if case['link']=='projection' else {})))
  unrelated=send('create_fit',dict(spec=dict(deepcopy(expected['cases'][0]['spec']),name='Unrelated')))['fits'][0]['id']
  def reports():return [report(k) for k in ids] if 'link' in case else report(owner)
  compare(case['before'],reports());op=case['operation'];args=dict(fit_id=owner,**case['arguments'])
  before=state();old_ids=before['records'][owner]['inspection_ids']['drones'];initial_history=bridge.history_details(owner)['undo_count']
  atomic(op,args,True)
  if case.get('accepted',True):
   real=drones.change
   def fail(*args,**kwargs):real(*args,**kwargs);raise RuntimeError('Injected after conserving edit')
   with patch.object(drones,'change',side_effect=fail):atomic(op,args)
   with patch.object(bridge._store,'write',side_effect=StoreWriteRejected('Injected save rejection')):atomic(op,args)
   response=send(op,args);compare(set(ids),{r['id'] for r in response['fits']})
   compare(case['after'],reports());compare(case['after_rows'],bridge._records[owner]['spec']['drones'])
   after=state();new_ids=after['records'][owner]['inspection_ids']['drones']
   for key in ids:compare(before['revisions'][key]+1,after['revisions'][key])
   compare(before['revisions'][unrelated],after['revisions'][unrelated]);compare(initial_history+1,bridge.history_details(owner)['undo_count'])
   if op=='split_drone':
    compare(old_ids,new_ids[:-1]);assert new_ids[-1] not in old_ids
   else:
    compare([key for i,key in enumerate(old_ids) if i!=args['source_position']],new_ids)
    assert old_ids[args['destination_position']] in new_ids
   for action,wanted,record in (('undo','before',before['records']),('redo','after',after['records'])):
    revisions=dict(bridge._revisions);send(action,dict(fit_id=owner));compare(case[wanted],reports());compare(record,bridge._records)
    for key in ids:compare(revisions[key]+1,bridge._revisions[key])
    compare(revisions[unrelated],bridge._revisions[unrelated])
   # Copy and branch isolation apply equally to mutated split/merge results.
   duplicate=send('duplicate_fit',dict(fit_id=owner,name='Conservation copy'))['fits'][-1]['id']
   compare(case['after_rows'],bridge._records[duplicate]['spec']['drones'])
   assert set(new_ids).isdisjoint(bridge._records[duplicate]['inspection_ids']['drones'])
   send('undo',dict(fit_id=owner));send('clone_drone',dict(fit_id=owner,position=0));atomic('redo',dict(fit_id=owner))
   compare(case['after_rows'],bridge._records[duplicate]['spec']['drones'])
   # Restore the original conserved result for durable restart comparison.
   send('undo',dict(fit_id=owner));send(op,args);compare(case['after'],reports())
  else:atomic(op,args)
  checks.append(dict(name=spec['name'],operation=op,accepted=case.get('accepted',True),linked=case.get('link'),
                     atomic_rollback=True,stale_rejection=True,identity_history=case.get('accepted',True)))
  reopens.append(dict(store=str(bridge._store.path),state=state(False)))
 # Reject malformed/range/self/type/overflow inputs without state or byte changes.
 owner=bridge.sample_id
 invalid=[('split_drone',dict(position=0,amount=n)) for n in (0,-1,True,1.5,2**31)]
 invalid += [('split_drone',dict(position=999,amount=1)),('split_drone',dict(position=0,amount=bridge.get_fit(owner).drones[0].amount)),
             ('split_drone',dict(position=0)),('merge_drones',dict(source_position=0,destination_position=0)),
             ('merge_drones',dict(source_position=999,destination_position=0)),('merge_drones',dict(source_position=True,destination_position=0)),
             ('merge_drones',dict(source_position=0)),('merge_drones',dict(source_position=0,destination_position=0,extra=True))]
 for op,args in invalid:atomic(op,dict(fit_id=owner,**args))
 overflow_spec=dict(deepcopy(expected['cases'][0]['spec']),name='Conservation overflow',
                    drones=[dict(name='Hobgoblin I',amount=2**31-1,active=0),dict(name='Hobgoblin I',amount=1,active=0)])
 overflow=send('create_fit',dict(spec=overflow_spec))['fits'][0]['id']
 atomic('merge_drones',dict(fit_id=overflow,source_position=0,destination_position=1))
 from tools.android_headless.drone_history_witness import conservation_witness
 history=conservation_witness(bridge,send,a.reference)
 compare(['merge_drones','split_drone'],history['operations'])
 reopens[-1]['state']=state(False)
 bridge._reset_storage();(a.output/'reopens.json').write_text(json.dumps(reopens,allow_nan=False),encoding='utf-8')
 with (a.output/'restart.log').open('w') as log:
  subprocess.run([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--database',str(a.database),'--reference',str(a.reference),'--output',str(a.output),'--restore'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
 assert not guard.attempts and not network
 proof=dict(policy=POLICY,host_only=True,cases=checks,invalid_cases=len(invalid)+1,history=history,
            reference_sha256=digest_file(a.reference),database_sha256=digest_file(a.database),
            fresh_process=json.loads((a.output/'restored.json').read_text()),no_desktop_imports=True,no_network=True)
 (a.output/'evidence.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(cases=len(checks),invalid=len(invalid)+1,fresh_process=proof['fresh_process'])))

if __name__=='__main__':main()
