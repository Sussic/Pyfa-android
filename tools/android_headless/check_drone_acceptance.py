"""Bounded C04 linked-recipient/variation/history acceptance against original commands."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_headless.check import DEPENDENCIES,NoDesktop
from tools.android_reference.reference import compare,digest_file
from tools.android_reference.drone_edits import PIN,observe


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('database','reference','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--group',choices=('projection','command','variations','history','boundaries'),required=True)
    p.add_argument('--restore',action='store_true')
    args=p.parse_args(); args.output=args.output.resolve(); assert not args.output.is_relative_to(ROOT)
    expected=json.loads(args.reference.read_text(encoding='utf-8'))
    compare(PIN,expected['source_commit']); compare(expected['database_sha256'],digest_file(args.database))
    for relative,digest in expected['source_files'].items(): compare(digest,digest_file(ROOT/'build/reference-upstream'/relative))
    compare(DEPENDENCIES,{name:importlib.metadata.version(name) for name in DEPENDENCIES})
    guard=NoDesktop(); network=[]; sys.meta_path.insert(0,guard)
    def audit(event,_):
        if event in ('socket.connect','socket.bind','socket.getaddrinfo'):
            network.append(event); raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge import drones,variations
    from android_bridge.store import StoreWriteRejected
    engine=HeadlessEngine(args.database); compare(expected['eos_settings'],engine.settings)
    identity=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    bridge=None; checks=[]
    def state(history=True):
        result=dict(records=deepcopy(bridge._records),revisions=dict(bridge._revisions),
                    snapshots=deepcopy(bridge._snapshots),recent=bridge.recent_items(),
                    details={key:bridge.drone_details(key) for key in bridge._fits})
        if history: result['history']={key:bridge.history_details(key) for key in bridge._fits}
        return result
    def send(op,a,ok=True,stale=False):
        keys={a[k] for k in ('fit_id','source_id','target_id') if k in a}
        result=json.loads(bridge.dispatch(json.dumps(dict(version=1,request_id='c04-acceptance',session_id=bridge.session_id,
            operation=op,arguments=a,expected_revisions={key:0 if stale else bridge._revisions[key] for key in keys}))))
        compare('ok' if ok else 'error',result['status'])
        return result
    def report(key):
        detail=bridge.drone_details(key)
        return dict(core=observe(bridge.get_fit(key)),stats=engine.projection_snapshot(bridge.get_fit(key)),
                    attributes=[{name:next(m['value'] for m in row['metrics'] if m['key']==name)
                                 for name in expected['units']['attributes']} for row in detail['stacks']])
    def fresh(spec,index):
        nonlocal bridge
        if bridge is not None: bridge._reset_storage()
        bridge=BridgeSession.open(engine,args.output/f'case-{index}.db',identity,deepcopy(spec))
        # Match the original GUI's filled vacancy state, as the existing
        # independent variation harness does, without coercing numeric kinds.
        send('set_fit_restrictions',dict(fit_id=bridge.sample_id,ignore=False))
        return bridge.sample_id
    def atomic(op,a,stale=False):
        before=state(); raw=bridge._store.path.read_bytes()
        send(op,a,False,stale)
        compare(before,state()); assert raw==bridge._store.path.read_bytes()
    if args.restore:
        saved=json.loads((args.output/'before-restart.json').read_text(encoding='utf-8'))
        bridge=BridgeSession.open(engine,Path(saved['store']),identity,None)
        compare(saved['state'],state(False)); assert bridge.persistence_info['opened_existing']
        assert not guard.attempts and not network
        (args.output/'restored.json').write_text(json.dumps(dict(matched=True,fits=len(bridge._fits))))
        return
    args.output.mkdir(parents=True,exist_ok=False)
    if args.group in ('projection','command'):
        cases=[c for c in expected['linked'] if c['link']==args.group]
        assert len(cases)==7
        for index,case in enumerate(cases):
            owner=fresh(case['spec'],index); ids=[owner]
            for spec in case['recipients']:
                target=send('create_fit',dict(spec=deepcopy(spec)))['fits'][0]['id']; ids.append(target)
                send('set_fit_restrictions',dict(fit_id=target,ignore=False))
                compare(case['unlinked'][len(ids)-2],report(target))
                send('add_'+case['link'],dict(source_id=owner,target_id=target,active=True,
                    **(dict(range_m=0.0,amount=1) if case['link']=='projection' else {})))
            unrelated=send('create_fit',dict(spec=dict(deepcopy(case['recipients'][0]),name='C04 unrelated')))['fits'][0]['id']
            compare(case['before'],[report(key) for key in ids])
            a=dict(fit_id=owner,**case['arguments']); op=case['operation']
            before=state(); bytes_before=bridge._store.path.read_bytes()
            module=variations if op=='change_variation' else drones; real=module.change
            def fail(*a,**kw): real(*a,**kw); raise RuntimeError('Injected after linked drone mutation')
            with patch.object(module,'change',side_effect=fail): atomic(op,a)
            with patch.object(bridge._store,'write',side_effect=StoreWriteRejected('Injected durable rejection')): atomic(op,a)
            atomic(op,a,True)
            response=send(op,a)
            compare(set(ids),{row['id'] for row in response['fits']})
            for key in ids: compare(before['revisions'][key]+1,bridge._revisions[key])
            compare(before['revisions'][unrelated],bridge._revisions[unrelated])
            compare(case['after'],[report(key) for key in ids]); after=deepcopy(bridge._records)
            for action,wanted,records in (('undo','restored',before['records']),('redo','after',after)):
                revisions=dict(bridge._revisions)
                response=send(action,dict(fit_id=owner)); compare(set(bridge._fits),{row['id'] for row in response['fits']})
                for key in ids: compare(revisions[key]+1,bridge._revisions[key])
                compare(revisions[unrelated],bridge._revisions[unrelated])
                compare(case[wanted],[report(key) for key in ids]); compare(records,bridge._records)
            checks.append(dict(operation=op,link=case['link'],recipients=2,unrelated_unchanged=True,
                               post_mutation_rollback=True,durable_rollback=True,undo_redo=True))
    elif args.group=='variations':
        for index,case in enumerate(expected['variations']):
            owner=fresh(case['spec'],index)
            for step in case['steps']:
                compare(step['before'],report(owner)); before=deepcopy(bridge._records[owner])
                a=dict(fit_id=owner,**step['arguments'])
                send('change_variation',a); compare(step['after'],report(owner)); after=deepcopy(bridge._records[owner])
                if step['changed']:
                    for op,key,record in (('undo','restored',before),('redo','after',after)):
                        send(op,dict(fit_id=owner)); compare(step[key],report(owner)); compare(record,bridge._records[owner])
                checks.append(dict(name=case['spec']['name'],arguments=step['arguments'],changed=step['changed']))
            for args_bad in (dict(context='drone',position=999,item_id=2454),dict(context='drone',position=0,item_id=587),
                             dict(context='drone',position=0,item_id=2183)):
                atomic('change_variation',dict(fit_id=owner,**args_bad))
            current=bridge.drone_details(owner)['stacks'][0]['item_id']
            stable=deepcopy(bridge._records); history=bridge.history_details(owner)['undo_count']
            send('change_variation',dict(fit_id=owner,context='drone',position=0,item_id=current))
            compare(stable,bridge._records); compare(history,bridge.history_details(owner)['undo_count'])
            # A new edit after undo discards redo without changing another stack.
            send('set_drone_amount',dict(fit_id=owner,position=0,amount=8))
            send('undo',dict(fit_id=owner)); send('toggle_drones',dict(fit_id=owner,main_position=0,positions=[]))
            compare(0,bridge.history_details(owner)['redo_count']); atomic('redo',dict(fit_id=owner))
    elif args.group=='history':
        from tools.android_headless.drone_history_witness import witness
        empty=deepcopy(expected['variations'][0]['spec']); empty['drones']=[]
        fresh(empty,0)
        proof=witness(bridge,send,ROOT/'tools/android_reference/fixtures/drone-core-edits.json')
        compare(sorted(drones.ORIGINAL_OPERATIONS),proof['operations']); checks=proof['cases']
    else:
        for index,case in enumerate(expected['core_extra']):
            owner=fresh(case['spec'],index); compare(case['before'],observe(bridge.get_fit(owner)))
            if case['accepted']:
                send(case['operation'],dict(fit_id=owner,**case['arguments']))
                compare(case['after'],observe(bridge.get_fit(owner)))
                send('undo',dict(fit_id=owner)); compare(case['restored'],observe(bridge.get_fit(owner)))
            else: atomic(case['operation'],dict(fit_id=owner,**case['arguments']))
            checks.append(dict(ship=case['spec']['ship'],accepted=case['accepted']))
    (args.output/'before-restart.json').write_text(json.dumps(dict(store=str(bridge._store.path),state=state(False)),allow_nan=False),encoding='utf-8')
    bridge._reset_storage()
    with (args.output/'restart.log').open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--database',str(args.database),
            '--reference',str(args.reference),'--output',str(args.output),'--group',args.group,'--restore'],
            stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    assert not guard.attempts and not network
    proof=dict(group=args.group,host_only=True,cases=len(checks),checks=checks,
               reference_sha256=digest_file(args.reference),database_sha256=digest_file(args.database),
               fresh_process=json.loads((args.output/'restored.json').read_text()),
               no_desktop_imports=True,no_network=True)
    (args.output/'evidence.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(group=args.group,cases=len(checks),fresh_process=proof['fresh_process'])))


if __name__=='__main__': main()
