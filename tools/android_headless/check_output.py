"""C02 offline EOS output, read-only history and process restart checks."""
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
    fixture=ROOT/'tools/android_reference/fixtures/output.json'
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
            subprocess.run([sys.executable,'-I',str(ROOT/'android/ci/test_output_summary.py')],
                stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        receipt=dict(task='C02',host_only=True,cases=len(expected['cases']),process_restart=True,
            functional_checks=['independent_matrix','read_only_gc','profile_undo_redo_clear_noop_rejection','stale_revision','atomic_failed_save','copy','identity_thread_availability','restart'],
            fixture_sha256=digest_file(fixture),database_sha256=before,game_database_unchanged=True,validator_tests_passed=25)
        (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt));return
    guard=NoDesktop();sys.meta_path.insert(0,guard)
    def audit(event,_):
        if event in ('socket.connect','socket.getaddrinfo','socket.bind'):raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge import HeadlessEngine
    from android_bridge.contract import BridgeSession
    engine=HeadlessEngine(args.database);compare(expected['eos_settings'],engine.settings)
    bridge=BridgeSession.open(engine,args.output/'fits.db',identity,{**expected['cases'][0]['spec'],'name':'C02 initial sample'})
    def send(operation,arguments):
        named={arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}
        response=json.loads(bridge.dispatch(json.dumps(dict(version=1,request_id='output',session_id=bridge.session_id,
            operation=operation,arguments=arguments,expected_revisions={k:bridge._revisions[k] for k in named}))))
        assert response['status']=='ok',response['error']
        return response
    def create(spec):
        old=set(bridge._fits);send('create_fit',dict(spec=spec));return (set(bridge._fits)-old).pop()
    def query(key):return bridge.output_details(key)
    if args.phase=='restored':
        before=json.loads((args.output/'before-restart.json').read_text())
        compare(before,{key:query(key) for key in bridge._fits})
        assert all(bridge.history_details(k)['undo_count']==bridge.history_details(k)['redo_count']==0 for k in bridge._fits)
        print('PASS restart',len(bridge._fits));return
    ids=[]
    for row in expected['cases']:
        print('OUTPUT CASE',row['spec']['name'],flush=True)
        key=create(row['spec']);ids.append(key);observed=query(key)
        compare(row['expected']['output'],observed['output']);compare(row['spec']['target_profile'],observed['target_profile'])
        before=deepcopy(dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),organization=bridge.organization(),history=bridge.history_details(key)))
        for _ in range(3):
            gc.collect();compare(observed,query(key))
            compare(before,dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),organization=bridge.organization(),history=bridge.history_details(key)))
    key=ids[35];before=query(key)
    profile=expected['cases'][36]['spec']['target_profile']
    send('set_target_profile',dict(fit_id=key,profile=profile));changed=query(key)
    compare(expected['cases'][36]['expected']['output'],changed['output'])
    send('undo',dict(fit_id=key));compare(before['output'],query(key)['output']);compare(before['target_profile'],query(key)['target_profile'])
    send('redo',dict(fit_id=key));compare(changed['output'],query(key)['output'])
    send('undo',dict(fit_id=key))
    send('set_target_profile',dict(fit_id=key,profile=None));cleared=query(key)
    compare(before['output']['firepower']['raw'],cleared['output']['firepower']['effective']);assert cleared['output']['effective'] is False
    send('undo',dict(fit_id=key));compare(before['output'],query(key)['output'])
    stable=deepcopy(dict(graph=bridge._graph(bridge._records,bridge._revisions),history=bridge.history_details(key),query=query(key)))
    send('set_target_profile',dict(fit_id=key,profile=before['target_profile']))
    # Existing bridge mutations advance the refresh revision even for unchanged
    # inputs; no-op must preserve inputs, modification order and history actions.
    stable['graph']['revisions'][key] += 1
    stable['query']['revision'] += 1
    stable['history']['revision'] += 1
    compare(stable,dict(graph=bridge._graph(bridge._records,bridge._revisions),history=bridge.history_details(key),query=query(key)))
    for bad in ({},{**profile,'hp':0},{**profile,'emAmount':True},{**profile,'kineticAmount':1.1},{**profile,'signatureRadius':0}):
        result=json.loads(bridge.dispatch(json.dumps(dict(version=1,request_id='bad',session_id=bridge.session_id,operation='set_target_profile',arguments=dict(fit_id=key,profile=bad),expected_revisions={key:bridge._revisions[key]}))))
        assert result['status']=='error' and result['error']['code']=='INVALID_REQUEST'
        compare(stable,dict(graph=bridge._graph(bridge._records,bridge._revisions),history=bridge.history_details(key),query=query(key)))
    def rejected(value,code,revision=None):
        state=deepcopy(dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),history=bridge.history_details(key)))
        result=json.loads(bridge.dispatch(json.dumps(dict(version=1,request_id='rejected',session_id=bridge.session_id,operation='set_target_profile',arguments=dict(fit_id=key,profile=value),expected_revisions={key:bridge._revisions[key] if revision is None else revision}))))
        assert result['status']=='error' and result['error']['code']==code,result
        compare(state,dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),history=bridge.history_details(key)))
    rejected(profile,'REVISION_CONFLICT',bridge._revisions[key]-1)
    from unittest.mock import patch
    with patch.object(bridge._store,'write',side_effect=OSError('synthetic output save failure')):rejected(profile,'ENGINE_ERROR')
    old=set(bridge._fits);send('duplicate_fit',dict(fit_id=key,name='Output copy'));copied=(set(bridge._fits)-old).pop()
    compare(before['output'],query(copied)['output']);compare(before['target_profile'],query(copied)['target_profile'])
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
    (args.output/'before-restart.json').write_text(json.dumps({k:query(k) for k in bridge._fits},indent=2,allow_nan=False)+'\n')
    print('PASS matrix/read-only/profile/history/noop/rejection/copy/identity/thread/availability')


if __name__=='__main__':main()
