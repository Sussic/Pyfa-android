"""Reuse unchanged host proof after the exact C03.1.3 charge-test correction."""
import ast
import hashlib
import json
import shutil
import subprocess

BEFORE='9272c2a52019e6334d62a531f2cea88eba33996f'
TEST_REVISION='79eb0017aee1dd38579f2ef983ad86e4aa265638'
PATH='android/app/src/androidTest/java/io/github/sussic/pyfa/ChargeEditingTest.kt'
PAIR=('5b012207c654cf83e7b95e36121ebd73d5616679937a6cf54523f6ce19cbd167','4e06708af65c048bed32a969e513b82251d1c7155591e8c07fe5a32a81b86fd1')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

ALIAS_BEFORE='c85a20a3013e7dc3328d3a905ef49752d8ed7762'
ALIAS_LOCAL_PAIR=('4ed2356c76735f9b65de41aaa913b452ed10876f3860cf3932c70fa7c43b6c08','e00bfe0f0b081f0f0c0367cb10e4534649523e4c12f4f4de5a6c26590fee25b2')

def alias_source(root,before,after):
    assert before==ALIAS_BEFORE
    local='android/ci/local_verification.py'
    def source(revision):return subprocess.check_output(['git','show',revision+':'+local],cwd=root)
    for revision,digest in zip((before,after),ALIAS_LOCAL_PAIR):
        assert hashlib.sha256(source(revision).replace(b'\r\n',b'\n')).hexdigest()==digest
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed={local,'android/ci/charge_keyboard_retry.py','android/ci/test_charge_keyboard_retry.py','android/ci/report_local.py'}
    assert local in changed and all(p in allowed or p.startswith('docs/android/') for p in changed)
    def executed(revision):
        tree=ast.parse(source(revision).decode())
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(tree)
                if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert executed(before)==executed(after)

def validate_alias(root,run,proof):
    alias=proof['bookkeeping_fix'];alias_source(root,alias['from_commit'],alias['to_commit'])
    assert alias['to_commit']==proof['to_commit']
    path=run/alias['original_run_file'];assert path.resolve().is_relative_to(run.resolve())
    assert sha(path)==alias['original_run_sha256']
    original=json.loads(path.read_text());from local_verification import plan
    assert original['commit']==ALIAS_BEFORE and original['status']=='paused'
    assert original['completed']==alias['retained_input_gates']==plan('full',None)[:68]
    assert plan('full',None)[67]=='native:initial'
    old=original['charge_keyboard_host_reuse']
    assert old['retained_gates']==proof['retained_gates']+plan('build',None)
    assert old['completed_before_adoption']==proof['completed_before_adoption']
    assert old['build_reuse']==proof['build_reuse']
    assert old['retained_log_hashes']==proof['retained_log_hashes']
    current=json.loads((run/'run.json').read_text())
    older={r['gate']:r for r in original['attempts']};latest={r['gate']:r for r in current['attempts']}
    for gate in alias['retained_input_gates']:
        assert latest[gate]==older[gate] and latest[gate]['exit_code']==0
        assert sha(run/latest[gate]['log'])==latest[gate]['log_sha256']

def adopt_alias_fix(root,run,state,current,original_bytes):
    from local_verification import plan
    alias_source(root,state['commit'],current)
    assert state['status']=='paused' and state['completed']==plan('full',None)[:68]
    proof=state['charge_keyboard_host_reuse']
    prior=json.loads((run/proof['archive']/'run.json').read_text())
    retained=[g for g in prior['completed'] if g.startswith(('desktop:','reference:','headless:'))]
    assert proof['retained_gates']==retained+plan('build',None)
    corrected=json.loads(json.dumps(proof));corrected['retained_gates']=retained
    validate_retained(root,run,corrected)
    path=run/'charge-keyboard-alias-before.json'
    if path.exists():assert path.read_bytes()==original_bytes
    else:path.write_bytes(original_bytes)
    proof['retained_gates']=list(retained)
    proof['bookkeeping_fix']=dict(from_commit=state['commit'],to_commit=current,retained_input_gates=list(state['completed']),
        original_run_file=path.name,original_run_sha256=sha(path))
    proof['to_commit']=current

def validated_build(run,proof,commit):
    source=(run.parent/proof['source_run']).resolve()
    assert source.parent==run.parent.resolve() and source!=run.resolve()
    assert sha(source/'run.json')==proof['state_sha256']
    assert sha(source/'files.json')==proof['manifest_sha256']
    state=json.loads((source/'run.json').read_text())
    from local_verification import plan
    assert state['mode']=='build' and state['status']=='passed' and state['gate'] is None
    assert state['commit']==commit and state['plan']==state['completed']==plan('build',None)
    latest={row['gate']:row for row in state['attempts']}
    for gate in state['completed']:
        row=latest[gate]
        assert row['exit_code']==0 and row['tested_commit']==commit
        assert sha(source/row['log'])==row['log_sha256'],gate
    manifest=json.loads((source/'files.json').read_text())
    for name,digest in proof['apk_hashes'].items():
        key='apks/'+name
        rows=[v for k,v in manifest.items() if k.replace('\\','/')==key]
        assert len(rows)==1 and rows[0]['sha256']==sha(source/key)==digest
        assert rows[0]['bytes']==(source/key).stat().st_size
    assert set(proof['apk_hashes'])=={'app-debug.apk','app-debug-androidTest.apk'}
    return source,state,latest

def reuse_build(r,proof):
    candidates=[]
    for path in r.directory.parent.glob('*/run.json'):
        state=json.loads(path.read_text(encoding='utf-8-sig'))
        if state.get('mode')=='build' and state.get('status')=='passed' and state.get('commit')==proof['to_commit']:
            candidates.append(path.parent)
    if not candidates:return
    source=sorted(candidates)[-1]
    build=dict(source_run=source.name,state_sha256=sha(source/'run.json'),manifest_sha256=sha(source/'files.json'),
               apk_hashes={p.name:sha(p) for p in (source/'apks').glob('*.apk')})
    source,state,latest=validated_build(r.directory,build,proof['to_commit'])
    assert r.state['completed']==proof['retained_gates']
    for index,gate in enumerate(state['completed']):
        row=dict(latest[gate]);target=r.directory/'logs'/f'reused-build-{index:02}.log'
        if target.exists():assert sha(target)==row['log_sha256']
        else:shutil.copyfile(source/row['log'],target)
        row['log']=str(target.relative_to(r.directory));row['reused_from_run']=source.name
        r.state['attempts'].append(row);r.state['completed'].append(gate)
    for name in build['apk_hashes']:shutil.copyfile(source/'apks'/name,r.directory/'apks'/name)
    proof['build_reuse']=build

def exact_source(root,before,after,completed):
    from local_verification import plan
    assert before==BEFORE and completed==plan('full',None)[:76]
    assert plan('full',None)[76]=='native:check-charge-edits.py'
    def source(revision,path):return subprocess.check_output(['git','show',revision+':'+path],cwd=root)
    for revision,digest in zip((before,after),PAIR):
        assert hashlib.sha256(source(revision,PATH).replace(b'\r\n',b'\n')).hexdigest()==digest,PATH
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed={PATH,'android/ci/local_verification.py','android/ci/report_local.py',
             'android/ci/charge_keyboard_retry.py','android/ci/test_charge_keyboard_retry.py'}
    assert PATH in changed
    assert all(p in allowed or p.startswith('docs/android/') for p in changed),changed
    def executed(revision):
        tree=ast.parse(source(revision,'android/ci/local_verification.py').decode('utf-8'))
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(tree)
                if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert executed(before)==executed(after),'Executed host/build behavior changed'

def validate_retained(root,run,proof):
    exact_source(root,proof['from_commit'],proof['to_commit'],proof['completed_before_adoption'])
    alias=proof.get('bookkeeping_fix')
    if alias:validate_alias(root,run,proof)
    build_commit=alias['from_commit'] if alias else proof['to_commit']
    archive=(run/proof['archive']).resolve()
    assert archive.is_relative_to(run.resolve()) and archive!=run.resolve()
    prior=json.loads((archive/'run.json').read_text(encoding='utf-8'))
    assert prior['commit']==proof['from_commit'] and prior['status']=='failed'
    assert prior['completed']==proof['completed_before_adoption']
    failure=prior['attempts'][-1]
    assert failure['gate']=='native:check-charge-edits.py' and failure['exit_code']!=0
    assert sha(run/failure['log'])==failure['log_sha256']
    assert proof['retained_gates']==[g for g in prior['completed'] if g.startswith(('desktop:','reference:','headless:'))]
    assert len(proof['retained_gates'])==62
    for name,digest in proof['archived_native_hashes'].items():assert sha(archive/'native'/name)==digest,name
    assert {p.name:sha(p) for p in (archive/'apks').glob('*.apk')}==proof['archived_apk_hashes']
    diagnostic=run/'charge-keyboard-failure'
    receipt=json.loads((diagnostic/'receipt.json').read_text())
    assert receipt['source_commit']==BEFORE and receipt['original_ids_revisions_retained'] is True
    assert receipt['fit_count']==9 and receipt['original_fit_count']==8
    assert receipt['partial_store_sha256']==sha(diagnostic/'partial-graph.sqlite3')=='3da2ad960d331403d7a51f94b1e690ee15435b273c7331da47f2007a586a2f6b'
    for field,name in (('module_report_sha256','module-edits-restored-native.json'),
                       ('failure_screenshot_sha256','charge-edits-failure.png'),
                       ('raw_instrumentation_sha256','charge-edits-prepare-instrumentation.txt')):
        assert receipt[field]==sha(archive/'native'/name),field
    latest={row['gate']:row for row in prior['attempts'] if row['exit_code']==0}
    assert set(proof['retained_log_hashes'])==set(proof['retained_gates'])
    for gate,digest in proof['retained_log_hashes'].items():
        assert latest[gate]['log_sha256']==sha(run/latest[gate]['log'])==digest,gate
    if proof.get('build_reuse'):
        source,state,latest_build=validated_build(run,proof['build_reuse'],build_commit)
        current=json.loads((run/'run.json').read_text())
        current_latest={row['gate']:row for row in current['attempts']}
        for gate in state['completed']:
            row=current_latest[gate]
            assert row['reused_from_run']==source.name and row['tested_commit']==build_commit
            assert row['log_sha256']==sha(run/row['log'])==latest_build[gate]['log_sha256']
        for name,digest in proof['build_reuse']['apk_hashes'].items():assert sha(run/'apks'/name)==digest
