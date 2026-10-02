"""C01.3.1 offline EOS defenses, read-only history and process restart checks."""
import argparse
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import gc
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import compare,digest_file,logical_database_digest,validate_source
from tools.android_headless.check import DEPENDENCIES,NoDesktop


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('database','source','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--phase',choices=('prepare','restored'))
    args=parser.parse_args()
    args.database,args.source,args.output=args.database.resolve(strict=True),args.source.resolve(strict=True),args.output.resolve()
    validate_source(args.source)
    compare(DEPENDENCIES,{n:importlib.metadata.version(n) for n in DEPENDENCIES})
    fixture=ROOT/'tools/android_reference/fixtures/defenses.json'
    expected=json.loads(fixture.read_text(encoding='utf-8'))
    identity=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    if args.phase is None:
        if args.output.is_relative_to(ROOT):raise ValueError('Use fresh external evidence')
        args.output.mkdir(parents=True,exist_ok=False)
        before=digest_file(args.database);compare(identity,logical_database_digest(args.database))
        for phase in ('prepare','restored'):
            with (args.output/(phase+'.log')).open('w',encoding='utf-8') as log:
                subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),
                    '--source',str(args.source),'--output',str(args.output),'--phase',phase],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        compare(before,digest_file(args.database));validate_source(args.source)
        with (args.output/'validator-tests.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(ROOT/'android/ci/test_defense_summary.py')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        receipt=dict(task='C01.3.1',host_only=True,cases=len(expected['cases']),process_restart=True,
            functional_checks=['independent_matrix','read_only_gc','independent_contribution_edits','undo_redo','no_op','invalid_stale_failed_write_rejection','copy','identity_thread_availability','restart'],
            fixture_sha256=digest_file(fixture),database_sha256=before,game_database_unchanged=True,validator_tests_passed=22)
        (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt));return
    guard=NoDesktop();sys.meta_path.insert(0,guard)
    def audit(event,_):
        if event in ('socket.connect','socket.getaddrinfo','socket.bind'):raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge import HeadlessEngine
    from android_bridge.contract import BridgeSession
    engine=HeadlessEngine(args.database);compare(expected['eos_settings'],engine.settings)
    bridge=BridgeSession.open(engine,args.output/'fits.db',identity,{**expected['cases'][0]['spec'],'name':'C01.3.1 initial sample'})
    def send(operation,arguments):
        named={arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}
        response=json.loads(bridge.dispatch(json.dumps(dict(version=1,request_id='defenses',session_id=bridge.session_id,
            operation=operation,arguments=arguments,expected_revisions={k:bridge._revisions[k] for k in named}))))
        assert response['status']=='ok',response['error']
        return response
    def create(spec):
        old=set(bridge._fits);send('create_fit',dict(spec=spec));return (set(bridge._fits)-old).pop()
    def query(key):return bridge.defense_details(key)
    if args.phase=='restored':
        before=json.loads((args.output/'before-restart.json').read_text(encoding='utf-8'))
        compare(before,{key:query(key) for key in bridge._fits})
        assert all(bridge.history_details(k)['undo_count']==bridge.history_details(k)['redo_count']==0 for k in bridge._fits)
        print('PASS restart',len(bridge._fits));return
    ids={}
    for row in expected['cases']:
        print('DEFENSE CASE',row['spec']['name'],flush=True)
        key=create(row['spec']);ids[row['spec']['name']]=key
        if 'source' in row:
            sender=create(row['source']);send('add_projection',dict(source_id=sender,target_id=key,**row['projection']))
        observed=query(key)
        compare(row['expected']['defenses'],observed['defenses'])
        before=deepcopy(dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),organization=bridge.organization(),history=bridge.history_details(key)))
        for _ in range(3):
            gc.collect();compare(observed,query(key))
            compare(before,dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),organization=bridge.organization(),history=bridge.history_details(key)))
    key=ids['Uniform incoming'];initial=query(key)['defenses']
    compare(expected['pattern_edits']['initial'],initial)
    for step in expected['pattern_edits']['steps']:
        recent=deepcopy(bridge.recent_items());cursor=bridge.history_details(key)['undo_count']
        send('set_damage_pattern',dict(fit_id=key,pattern=step['pattern']))
        compare(step['expected'],query(key)['defenses']);compare(step['pattern'],bridge._records[key]['spec']['damage_pattern'])
        assert bridge.history_details(key)['undo_count']==cursor+1
        assert bridge.history_details(key)['undo_label']=='Change incoming damage'
        send('undo',dict(fit_id=key));compare(initial,query(key)['defenses'])
        send('redo',dict(fit_id=key));compare(step['expected'],query(key)['defenses'])
        send('undo',dict(fit_id=key));compare(initial,query(key)['defenses']);compare(recent,bridge.recent_items())
    before=deepcopy(bridge._records);history=bridge.history_details(key)['undo_count']
    send('set_damage_pattern',dict(fit_id=key,pattern={k:float(v) for k,v in before[key]['spec']['damage_pattern'].items()}))
    compare(before,bridge._records);assert bridge.history_details(key)['undo_count']==history
    def rejected(pattern,code='INVALID_REQUEST',revision=None):
        before=deepcopy(dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),history=bridge.history_details(key)))
        response=json.loads(bridge.dispatch(json.dumps(dict(version=1,request_id='defense-invalid',session_id=bridge.session_id,
            operation='set_damage_pattern',arguments=dict(fit_id=key,pattern=pattern),
            expected_revisions={key:bridge._revisions[key] if revision is None else revision}))))
        assert response['status']=='error' and response['error']['code']==code,response
        compare(before,dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),history=bridge.history_details(key)))
    uniform=before[key]['spec']['damage_pattern']
    for invalid in ({k:0 for k in uniform},{**uniform,'emAmount':-1},{**uniform,'emAmount':True},
        {**uniform,'emAmount':'1'},{k:v for k,v in uniform.items() if k!='emAmount'},
        {**uniform,'extra':1},{k:1e308 for k in uniform}):rejected(invalid)
    rejected(uniform,'REVISION_CONFLICT',revision=bridge._revisions[key]-1)
    from unittest.mock import patch
    with patch.object(bridge._store,'write',side_effect=OSError('synthetic defense save failure')):
        rejected(expected['pattern_edits']['steps'][0]['pattern'],'ENGINE_ERROR')
    send('set_damage_pattern',dict(fit_id=key,pattern=expected['pattern_edits']['steps'][3]['pattern']))
    changed=query(key)['defenses']
    old=set(bridge._fits);send('duplicate_fit',dict(fit_id=key,name='Defense copy'));copy=(set(bridge._fits)-old).pop()
    compare(changed,query(copy)['defenses']);compare(bridge._records[key]['spec']['damage_pattern'],bridge._records[copy]['spec']['damage_pattern'])
    try:query('missing')
    except KeyError:pass
    else:raise AssertionError('Missing identity accepted')
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:pool.submit(query,key).result()
        except RuntimeError:pass
        else:raise AssertionError('Wrong thread accepted')
    bridge._available=False
    try:query(key)
    except RuntimeError:pass
    else:raise AssertionError('Unavailable engine accepted')
    bridge._available=True
    (args.output/'before-restart.json').write_text(json.dumps({k:query(k) for k in bridge._fits},indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('PASS matrix/read-only/edit/copy/identity/thread/availability')


if __name__=='__main__':main()
