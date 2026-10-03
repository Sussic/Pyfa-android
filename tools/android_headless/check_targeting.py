"""C03.1 independent matrix, read-only/GC, history/copy and durable restart."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import gc,importlib.metadata,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'android/ci'))
from tools.android_reference.reference import compare,digest_file,logical_database_digest,validate_source
from tools.android_headless.check import DEPENDENCIES,NoDesktop
from targeting_summary import targeting


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('database','source','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--phase',choices=('prepare','restored'));args=parser.parse_args()
    args.database=args.database.resolve(strict=True);args.source=args.source.resolve(strict=True);args.output=args.output.resolve()
    validate_source(args.source);compare(DEPENDENCIES,{n:importlib.metadata.version(n) for n in DEPENDENCIES})
    fixture=ROOT/'tools/android_reference/fixtures/targeting.json';expected=json.loads(fixture.read_text(encoding='utf-8'))
    identity=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text(encoding='utf-8'))['database_logical_sha256']
    if args.phase is None:
        if args.output.is_relative_to(ROOT):raise ValueError('Use fresh external evidence')
        args.output.mkdir(parents=True,exist_ok=False);before=digest_file(args.database);compare(identity,logical_database_digest(args.database))
        for phase in ('prepare','restored'):
            with (args.output/(phase+'.log')).open('w',encoding='utf-8') as log:
                subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),'--source',str(args.source),
                    '--output',str(args.output),'--phase',phase],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        compare(before,digest_file(args.database));validate_source(args.source)
        with (args.output/'validator-tests.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(ROOT/'android/ci/test_targeting_summary.py')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        receipt=dict(task='C03.1',host_only=True,cases=len(expected['cases']),process_restart=True,
            functional_checks=['independent_matrix','all_holds','all_lock_times','read_only_gc','undo_redo_modifiers_skills_cargo_projections','copy','identity_thread_availability','restart'],
            fixture_sha256=digest_file(fixture),database_sha256=before,game_database_unchanged=True)
        (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt));return
    sys.meta_path.insert(0,NoDesktop())
    def audit(event,_):
        if event in ('socket.connect','socket.getaddrinfo','socket.bind'):raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge import HeadlessEngine
    from android_bridge.contract import BridgeSession
    engine=HeadlessEngine(args.database);compare(expected['eos_settings'],engine.settings)
    bridge=BridgeSession.open(engine,args.output/'fits.db',identity,{**expected['cases'][0]['spec'],'name':'C03 initial sample'})
    def send(operation,arguments):
        named={arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}
        result=json.loads(bridge.dispatch(json.dumps(dict(version=1,request_id='targeting',session_id=bridge.session_id,
            operation=operation,arguments=arguments,expected_revisions={k:bridge._revisions[k] for k in named}))))
        assert result['status']=='ok',result['error'];return result
    def create(spec):
        before=set(bridge._fits);send('create_fit',dict(spec=spec));return (set(bridge._fits)-before).pop()
    query=bridge.targeting_details
    if args.phase=='restored':
        before=json.loads((args.output/'before-restart.json').read_text(encoding='utf-8'))
        targeting(before,{key:query(key) for key in bridge._fits})
        assert all(bridge.history_details(key)['undo_count']==bridge.history_details(key)['redo_count']==0 for key in bridge._fits)
        print('PASS exact restart',len(bridge._fits));return
    ids=[]
    for index,row in enumerate(expected['cases']):
        print('TARGETING CASE',index,row['spec']['name'],flush=True)
        key=create(row['spec']);ids.append(key)
        if 'initial' in row:targeting(row['initial']['targeting'],query(key)['targeting'])
        for edit in row['edits']:send(edit['operation'],dict(fit_id=key,**edit['args']))
        if 'source_spec' in row:
            source=create(row['source_spec']);send('add_projection',dict(source_id=source,target_id=key,range_m=None,active=True,amount=1))
        observed=query(key);targeting(row['expected']['targeting'],observed['targeting'])
        if row['edits'] or 'source_spec' in row:
            before_revision=bridge._revisions[key];send('undo',dict(fit_id=key));assert bridge._revisions[key]==before_revision+1
            targeting(row['initial']['targeting'],query(key)['targeting'])
            send('redo',dict(fit_id=key));assert bridge._revisions[key]==before_revision+2
            targeting(row['expected']['targeting'],query(key)['targeting']);observed=query(key)
        stable=deepcopy(dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),organization=bridge.organization(),history=bridge.history_details(key)))
        for _ in range(3):
            gc.collect();targeting(observed,query(key))
            compare(stable,dict(records=bridge._records,revisions=bridge._revisions,recent=bridge.recent_items(),organization=bridge.organization(),history=bridge.history_details(key)))
    key=ids[next(i for i,row in enumerate(expected['cases']) if row['spec']['name']=='Targeting Vexor')]
    before=query(key);old=set(bridge._fits);send('duplicate_fit',dict(fit_id=key,name='Targeting copy'));copied=(set(bridge._fits)-old).pop()
    targeting(before['targeting'],query(copied)['targeting'])
    skill_case=next(row for row in expected['cases'] if row['spec']['name']=='Skill Drone Avionics')
    send('set_skill_level',dict(fit_id=copied,skill='Drone Avionics',level=0))
    targeting(skill_case['expected']['targeting'],query(copied)['targeting']);targeting(before,query(key))
    send('undo',dict(fit_id=copied));targeting(before['targeting'],query(copied)['targeting'])
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
    print('PASS matrix/all holds/lock times/read-only/history/copy/identity/thread/availability')


if __name__=='__main__':main()
