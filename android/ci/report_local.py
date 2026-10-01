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
    checked_reuse=set()
    for gate in state['plan']:
        row=latest[gate]
        assert row['exit_code']==0 and row['tested_commit'],gate
        assert sha(run/row['log'])==row['log_sha256'],gate
        if row['tested_commit']!=state['commit']:
            if gate == 'native:summary':
                from summary_repair import equivalent
                equivalent(root, state['commit'], row['tested_commit'])
                continue
            assert gate.startswith(('desktop:','reference:','headless:','build:')),gate
            if row['tested_commit'] in checked_reuse: continue
            checked_reuse.add(row['tested_commit'])
            changes=subprocess.check_output(['git','diff','--name-only',row['tested_commit'],state['commit']],cwd=root,text=True).splitlines()
            allowed={'android/ci/local_verification.py','android/ci/native_suite.py','android/verify-local.ps1',
                'android/ci/check-history.py','android/ci/history_progress.py',
                'android/ci/report_local.py','android/ci/test_report_local.py','AGENTS.md'}
            assert all(name in allowed or name.startswith('docs/android/') for name in changes),changes
            if 'android/ci/check-history.py' in changes:
                before=subprocess.check_output(['git','show',row['tested_commit']+':android/ci/check-history.py'],cwd=root,text=True,encoding='utf-8')
                after=subprocess.check_output(['git','show',state['commit']+':android/ci/check-history.py'],cwd=root,text=True,encoding='utf-8')
                expected=before.replace('import json\n','import json\nimport os\n',1).replace('timeout=900)',"timeout=2400 if os.name == 'nt' else 900)",1)
                assert after==expected,'History changed beyond the approved timeout'
            import ast
            def executed(source):
                return {node.name:ast.dump(node,include_attributes=False) for node in ast.walk(ast.parse(source))
                    if isinstance(node,ast.FunctionDef) and node.name in ('plan','host','build','execute')}
            earlier=subprocess.check_output(['git','show',row['tested_commit']+':android/ci/local_verification.py'],cwd=root,text=True,encoding='utf-8')
            tested=subprocess.check_output(['git','show',state['commit']+':android/ci/local_verification.py'],cwd=root,text=True,encoding='utf-8')
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
