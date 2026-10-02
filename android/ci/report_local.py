"""Publish explicitly local verification results, never an Actions conclusion."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):digest.update(data)
    return digest.hexdigest()

def validate(run,root):
    sys.path.insert(0,str(root/'android/ci'))
    from local_verification import plan
    state=json.loads((run/'run.json').read_text(encoding='utf-8'))
    assert state['mode']=='full' and state['gate'] is None and state['status']=='passed'
    assert state['plan']==state['completed']==plan('full',None)
    files=json.loads((run/'files.json').read_text(encoding='utf-8'))
    for name,row in files.items():
        file=(run/name).resolve()
        assert file.is_relative_to(run.resolve()) and file.stat().st_size==row['bytes']
        assert sha(file)==row['sha256'],name
    for name in ('run.json','native/native-summary.json','native/junit/TEST-windows-initial.xml'):
        assert name in files or name.replace('/',chr(92)) in files, 'Required evidence is absent from the manifest: '+name
    assert not state.get('hosted_actions_pass',False), 'Local results cannot claim Actions success'
    latest={row['gate']:row for row in state['attempts']}
    stale_reuse=state.get('stale_history_reuse',[])
    stale_proof=stale_reuse[-1] if stale_reuse else None
    middle_apks=run/'apks'
    if stale_proof:
        from stale_history_retry import exact_source,validate_recovery
        from cargo_history_retry import assets_equal
        exact_source(root,stale_proof['from_commit'],stale_proof['to_commit'])
        assert stale_proof['to_commit']==state['commit'] and stale_proof['prepared'] and stale_proof['installed']
        archive=run/stale_proof['archive'];assert archive.resolve().is_relative_to(run.resolve())
        validate_recovery(root,run,archive/'recovery')
        assert sha(archive/'recovery/recovery.json')==stale_proof['recovery_receipt_sha256']
        assert sha(archive/'apks/app-debug.apk')==sha(run/'apks/app-debug.apk')==stale_proof['app_sha256']
        assert sha(archive/'apks/app-debug-androidTest.apk')==stale_proof['old_test_apk_sha256']
        assert sha(run/'apks/app-debug-androidTest.apk')==stale_proof['new_test_apk_sha256']
        assets_equal(archive/'apks/app-debug-androidTest.apk',run/'apks/app-debug-androidTest.apk')
        retained=[g for g in state['plan'] if g not in ('native:mutation-history-3-prepare','native:mutation-history-3-restored','native:summary')]
        assert stale_proof['retained_gates']==retained
        for name,digest in stale_proof['retained_report_hashes'].items():assert sha(run/'native'/name)==digest
        assert set(stale_proof['retained_report_hashes'])=={f'mutation-history-{group}-{phase}-native.json' for group in range(3) for phase in ('prepare','restored')}
        assert all(latest[g]['tested_commit']==state['commit'] for g in ('native:mutation-history-3-prepare','native:mutation-history-3-restored'))
        middle_apks=archive/'apks'
    cargo_reuse=state.get('cargo_observer_reuse',[])
    cargo_proof=cargo_reuse[-1] if cargo_reuse else None
    prior_apks=run/'apks';prior_native=run/'native'
    if cargo_proof:
        from cargo_history_retry import exact_source,validate_recovery,assets_equal
        exact_source(root,cargo_proof['from_commit'],cargo_proof['to_commit'])
        assert cargo_proof['to_commit']==(stale_proof['from_commit'] if stale_proof else state['commit']) and cargo_proof['prepared'] and cargo_proof['installed']
        archive=run/cargo_proof['archive'];assert archive.resolve().is_relative_to(run.resolve())
        validate_recovery(root,run,archive/'recovery')
        assert sha(archive/'recovery/recovery.json')==cargo_proof['recovery_receipt_sha256']
        assert sha(archive/'apks/app-debug.apk')==sha(run/'apks/app-debug.apk')==cargo_proof['app_sha256']
        assert sha(archive/'apks/app-debug-androidTest.apk')==cargo_proof['old_test_apk_sha256']
        assert sha(middle_apks/'app-debug-androidTest.apk')==cargo_proof['new_test_apk_sha256']
        assets_equal(archive/'apks/app-debug-androidTest.apk',middle_apks/'app-debug-androidTest.apk')
        assert cargo_proof['retained_gates']==[g for g in cargo_proof['completed_before_adoption'] if not g.startswith('native:mutation-history-')]
        assert all(latest[g]['tested_commit']==cargo_proof['to_commit'] for g in state['plan'] if g.startswith('native:mutation-history-') and (not stale_proof or g in stale_proof['retained_gates']))
        prior_apks=archive/'apks';prior_native=archive/'native'
    settings_reuse=state.get('settings_fix_reuse',[])
    settings_proof=settings_reuse[-1] if settings_reuse else None
    if settings_proof:
        from local_verification import pending_settings_fix
        pending_settings_fix(root,settings_proof['from_commit'],settings_proof['to_commit'])
        assert settings_proof['to_commit']==(cargo_proof['from_commit'] if cargo_proof else state['commit']) and settings_proof['validated']
        archive=run/settings_proof['archive']
        assert archive.resolve().is_relative_to(run.resolve())
        for name,digest in settings_proof['retained_hashes'].items():
            assert sha(archive/name)==sha(prior_native/name)==digest
        for name,digest in settings_proof['apk_hashes'].items():assert sha(prior_apks/name)==digest
        old_attempts=json.loads((run/cargo_proof['archive']/'run.json').read_text())['attempts'] if cargo_proof else state['attempts']
        assert next(r for r in reversed(old_attempts) if r['gate']=='native:mutation-history-0-restored')['retained_native_execution_commit']==settings_proof['from_commit']
    runner_reuse=state.get('runner_fix_reuse',[])
    proof=runner_reuse[-1] if runner_reuse else None
    if proof:
        from local_verification import pending_runner_fix
        pending_runner_fix(root,proof['from_commit'],proof['to_commit'],proof['completed_before_adoption'])
        assert proof['to_commit']==(settings_proof['from_commit'] if settings_proof else cargo_proof['from_commit'] if cargo_proof else state['commit']) and proof['prepared'] and proof['installed']
        archive=run/proof['archive']
        assert archive.resolve().is_relative_to(run.resolve())
        assert sha(archive/'apks/app-debug.apk')==sha(run/'apks/app-debug.apk')==proof['app_sha256']
        assert sha(archive/'apks/app-debug-androidTest.apk')==proof['old_test_apk_sha256']
        assert sha(prior_apks/'app-debug-androidTest.apk')==proof['new_test_apk_sha256']
        from zipfile import ZipFile
        with ZipFile(archive/'apks/app-debug-androidTest.apk') as old, ZipFile(prior_apks/'app-debug-androidTest.apk') as new:
            assets={name for name in old.namelist() if name.startswith('assets/')}
            assert assets=={name for name in new.namelist() if name.startswith('assets/')}
            assert all(old.read(name)==new.read(name) for name in assets)
    checked_reuse=set()
    for gate in state['plan']:
        row=latest[gate]
        assert row['exit_code']==0 and row['tested_commit'],gate
        assert sha(run/row['log'])==row['log_sha256'],gate
        if row['tested_commit']!=state['commit']:
            comparison_commit=state['commit']
            if stale_proof and gate in stale_proof['retained_gates']:
                if row['tested_commit']==stale_proof['from_commit']:continue
                comparison_commit=stale_proof['from_commit']
            if cargo_proof and gate in cargo_proof['retained_gates']:
                if row['tested_commit']==cargo_proof['from_commit']:continue
                comparison_commit=cargo_proof['from_commit']
            if settings_proof and gate in settings_proof['completed_before_adoption']:
                if row['tested_commit']==settings_proof['from_commit']:continue
                comparison_commit=settings_proof['from_commit']
            if proof and gate in proof['completed_before_adoption']:
                assert not gate.startswith('native:mutation-history-')
                if row['tested_commit']==proof['from_commit']:continue
                comparison_commit=proof['from_commit']
            if gate == 'native:summary':
                from summary_repair import equivalent
                equivalent(root, state['commit'], row['tested_commit'])
                continue
            assert gate.startswith(('desktop:','reference:','headless:','build:')),gate
            if row['tested_commit'] in checked_reuse: continue
            checked_reuse.add(row['tested_commit'])
            changes=subprocess.check_output(['git','diff','--name-only',row['tested_commit'],comparison_commit],cwd=root,text=True).splitlines()
            allowed={'android/ci/local_verification.py','android/ci/native_suite.py','android/verify-local.ps1',
                'android/ci/check-history.py','android/ci/history_progress.py',
                'android/ci/report_local.py','android/ci/test_report_local.py','AGENTS.md'}
            if 'tools/android_headless/check_history_mutations.py' in changes:
                from local_verification import pending_mutation_count_fix
                reuse = next(r for r in state['launcher_fix_reuse'] if r['from_commit'] == row['tested_commit']
                    and r['to_commit'] == comparison_commit)
                pending_mutation_count_fix(root, row['tested_commit'], comparison_commit, reuse['completed_before_adoption'])
                assert gate in reuse['completed_before_adoption']
                allowed.add('tools/android_headless/check_history_mutations.py')
            assert all(name in allowed or name.startswith('docs/android/') for name in changes),changes
            if 'android/ci/check-history.py' in changes:
                before=subprocess.check_output(['git','show',row['tested_commit']+':android/ci/check-history.py'],cwd=root,text=True,encoding='utf-8')
                after=subprocess.check_output(['git','show',comparison_commit+':android/ci/check-history.py'],cwd=root,text=True,encoding='utf-8')
                expected=before.replace('import json\n','import json\nimport os\n',1).replace('timeout=900)',"timeout=2400 if os.name == 'nt' else 900)",1)
                assert after==expected,'History changed beyond the approved timeout'
            import ast
            def executed(source):
                return {node.name:ast.dump(node,include_attributes=False) for node in ast.walk(ast.parse(source))
                    if isinstance(node,ast.FunctionDef) and node.name in ('plan','host','build','execute')}
            earlier=subprocess.check_output(['git','show',row['tested_commit']+':android/ci/local_verification.py'],cwd=root,text=True,encoding='utf-8')
            tested=subprocess.check_output(['git','show',comparison_commit+':android/ci/local_verification.py'],cwd=root,text=True,encoding='utf-8')
            assert executed(earlier)==executed(tested),'Reused host/build commands changed'
    summary=json.loads((run/'native/native-summary.json').read_text(encoding='utf-8'))
    assert summary['checkout_sha']==latest['native:summary']['tested_commit'] and summary['workflow_run'] is None
    assert summary['execution']=={'kind':'local_windows','local_run_id':run.name}
    review=json.loads((run/'screenshots-reviewed.json').read_text(encoding='utf-8'))
    assert review['tested_commit']==state['commit']
    screenshots=sorted(p.name for p in (run/'native').glob('*.png'))
    assert screenshots==sorted(row['name'] for row in review['screenshots'])
    for row in review['screenshots']:
        assert row['reviewed'] is True and row['observation']
        assert sha(run/'native'/row['name'])==row['sha256']
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    changes=subprocess.check_output(['git','diff','--name-only',state['commit'],head],cwd=root,text=True).splitlines()
    from summary_repair import equivalent
    equivalent(root, state['commit'], head)
    if state.get('summary_repairs'):
        provenance=state['summary_repairs'][-1]
        assert sha(run/'native/apk-contents.json')==provenance['report_sha256']
        assert sha(run/provenance['archive']/'native/apk-contents.json')==provenance['report_sha256']
        for name,digest in provenance['apk_sha256'].items():
            assert sha(run/'apks'/name)==digest
    return state,head

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True);parser.add_argument('--receipt-url',required=True)
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args();run=Path(args.run).resolve()
    state,head=validate(run,ROOT)
    payload={'state':'success','context':'local/full-verification','target_url':args.receipt_url,
        'description':'Windows local suite + screenshot review; evidence '+state['commit'][:8]}
    print(json.dumps({'reported_head':head,'tested_commit':state['commit'],'local_status':payload},indent=2))
    if args.publish:
        subprocess.run(['gh','api','--method','POST','repos/Sussic/Pyfa-android/statuses/'+head,
            '--input','-'],input=json.dumps(payload),text=True,check=True)
if __name__=='__main__':main()
