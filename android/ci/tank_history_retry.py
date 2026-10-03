"""Exact tank history wait repair; retain unchanged proof and recover its baseline."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from capacitor_runner_retry import packages_equal, once

BEFORE = 'c387a3bfa12cde6824b317e1ed8f1124663c05f2'
PATH = 'android/app/src/androidTest/java/io/github/sussic/pyfa/TankTest.kt'
ARCHIVE = 'tank-history-fix-original'
ADDITION = '''    private fun reverse(id: String, redo: Boolean) {
        ready(id); val revision = fit(id).revision
        val history = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
        compose.waitUntil(60_000) { !history.loading && !history.editing && history.options?.revision == revision }
        val tag = if (redo) "history-redo" else "history-undo"
        compose.onNodeWithTag(tag).performScrollTo().assertIsEnabled()
        click(tag)
        compose.waitUntil(60_000) { fit(id).revision > revision && !history.loading && !history.editing && history.options?.revision == fit(id).revision }
        assertNull(history.error); ready(id)
    }
'''
INIT = '''            if self.state['commit']!=current and getattr(args,'adopt_tank_history_fix',False):
                assert self.state['status']=='failed' and self.state['completed']==plan('full',None)[:-3]
                failure=next(row for row in reversed(self.state['attempts']) if row['gate'].startswith('native:'))
                assert failure['gate']=='native:tank-prepare' and failure['exit_code']!=0
                from tank_history_retry import exact_source
                exact_source(ROOT,self.state['commit'],current)
                before=self.state['commit']
                for row in self.state['attempts']:row.setdefault('tested_commit',before)
                self.state['tank_history_reuse']={'from_commit':before,'to_commit':current,
                    'completed_before_adoption':list(self.state['completed']),
                    'retained_gates':[g for g in self.state['completed'] if g not in ('build:apks-lint','build:package')],
                    'prepared':False,'installed':False}
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
'''
PREPARE = '''            tank_fix=self.state.get('tank_history_reuse')
            if tank_fix and not tank_fix['prepared']:
                from tank_history_retry import prepare
                prepare(self,tank_fix);save(self.file,self.state)
'''
INSTALL = '''                    if tank_fix and not tank_fix['installed']:
                        from tank_history_retry import install
                        install(self,tank_fix);save(self.file,self.state)
'''
ARG = "    parser.add_argument('--adopt-tank-history-fix',action='store_true',help='Adopt only the exact C01.3.2 revision wait repair; recover its validated synthetic baseline and rerun affected gates')\n"
REPORT = '''    tank_proof=state.get('tank_history_reuse')
    if tank_proof:
        from tank_history_retry import exact_source,validate_retained
        exact_source(root,tank_proof['from_commit'],tank_proof['to_commit'])
        assert tank_proof['to_commit']==state['commit'] and tank_proof['prepared'] and tank_proof['installed']
        validate_retained(root,run,tank_proof)
        for gate in ('headless:tank-history-guard','build:apks-lint','build:package','build:tank-test-signature'):
            assert latest[gate]['exit_code']==0 and latest[gate]['tested_commit']==state['commit']
'''
RETAIN = '''            if tank_proof and gate in tank_proof['retained_gates']:
                if row['tested_commit']==tank_proof['from_commit']:continue
                comparison_commit=tank_proof['from_commit']
'''

def test_source(text):
    text=once(text,'    private fun open(id: String)',ADDITION+'    private fun open(id: String)')
    count=0
    for identifier in ('armor','owner'):
        for action in ('undo','redo'):
            old=f'click("history-{action}"); ready({identifier})'
            count+=text.count(old)
            text=text.replace(old,f'reverse({identifier}, {str(action=="redo").lower()})')
    assert count==9
    return text

def launcher_source(text):
    text=once(text,"            if self.state['commit']!=current and args.adopt_capacitor_runner_fix:",INIT+"            if self.state['commit']!=current and args.adopt_capacitor_runner_fix:")
    text=once(text,"            capacitor_fix=self.state.get('capacitor_runner_reuse')",PREPARE+"            capacitor_fix=self.state.get('capacitor_runner_reuse')")
    text=once(text,"                    if capacitor_fix and not capacitor_fix['installed']:",INSTALL+"                    if capacitor_fix and not capacitor_fix['installed']:")
    return once(text,'    args=parser.parse_args()\n',ARG+'    args=parser.parse_args()\n')

def reporter_source(text):
    text=once(text,"    capacitor_proof=state.get('capacitor_runner_reuse')",REPORT+"    capacitor_proof=state.get('capacitor_runner_reuse')")
    return once(text,"            comparison_commit=state['commit']", "            comparison_commit=state['commit']\n"+RETAIN.rstrip())

def powershell_source(text):
    text=once(text,'[switch]$RestartNative','[switch]$RestartNative, [switch]$AdoptTankHistoryFix')
    return once(text,'& $localPython @localArguments',"if ($AdoptTankHistoryFix) { $localArguments += '--adopt-tank-history-fix' }\n& $localPython @localArguments")

TRANSFORMS={PATH:test_source,'android/ci/local_verification.py':launcher_source,
    'android/ci/report_local.py':reporter_source,'android/verify-local.ps1':powershell_source}

def validate_sources(old,new,changes):
    allowed=set(TRANSFORMS)|{'android/ci/tank_history_retry.py','android/ci/test_tank_history_retry.py'}
    assert set(TRANSFORMS)<=set(changes) and all(p in allowed or p.startswith('docs/android/') for p in changes)
    for path,transform in TRANSFORMS.items():assert new[path]==transform(old[path]),'Unrelated source change: '+path
    def commands(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text))
        if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert commands(old['android/ci/local_verification.py'])==commands(new['android/ci/local_verification.py'])

def exact_source(root,before,after):
    assert before==BEFORE
    def source(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=root,text=True,encoding='utf-8')
    changes=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    validate_sources({p:source(before,p) for p in TRANSFORMS},{p:source(after,p) for p in TRANSFORMS},changes)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def untyped(envelope):
    from defense_summary import typed
    data=copy.deepcopy(typed(envelope));types=envelope['numeric_types']
    def walk(value,path):
        if type(value) is dict:return {k:walk(v,path+'.'+k) for k,v in value.items()}
        if type(value) is list:return [walk(v,f'{path}[{i}]') for i,v in enumerate(value)]
        if type(value) in (int,float):return float(value) if types[path]=='decimal' else value
        return value
    return walk(data,'root')

def recovery_graph(original,prior,fixture):
    from android_bridge.store import encode_graph
    baseline=untyped(prior['saved']['graph']);ids=baseline['fit_order']
    assert len(ids)==len(set(ids))==189 and [i for i in original['fit_order'] if i in ids]==ids
    assert set(original)==set(baseline)
    extras=[i for i in original['fit_order'] if i not in ids]
    names=[]
    for case in fixture['cases']:
        names.append('C01.3.2 '+case['spec']['name'])
        if 'source' in case:names.append('C01.3.2 '+case['source']['name'])
    assert len(extras)==len(names)==40 and [original['records'][i]['spec']['name'] for i in extras]==names
    restored=copy.deepcopy(original);restored['fit_order']=ids
    for field in ('records','revisions','modified'):
        assert set(original[field])==set(original['fit_order'])
        restored[field]={i:original[field][i] for i in ids}
    for field in ('recent','sample_id','dataset_identity','eos_settings'):assert encode_graph(original[field])==encode_graph(baseline[field]),field
    assert encode_graph(restored)==encode_graph(baseline),'Inherited input/type/order/metadata changed'
    return restored

def validate_recovery(root,run,directory):
    sys.path.insert(0,str(root))
    from android_bridge.store import GraphStore,decode_graph,encode_graph
    receipt=read(directory/'recovery.json')
    oldpath=directory/'partial-graph.sqlite3';newpath=directory/'restored-graph.sqlite3'
    assert sha(oldpath)==receipt['original_store_sha256'] and sha(newpath)==receipt['restored_store_sha256']
    prior=run/'native/defenses-restored-native.json';fixture=root/'tools/android_reference/fixtures/tank.json'
    assert sha(prior)==receipt['prior_report_sha256'] and sha(fixture)==receipt['fixture_sha256']
    old,new=GraphStore(oldpath).current,GraphStore(newpath).current
    expected=recovery_graph(decode_graph(old.payload),read(prior),read(fixture))
    assert new.payload==encode_graph(expected) and new.generation==old.generation+1==receipt['generation_after']
    assert old.generation==receipt['generation_before'] and receipt['retained_fits']==189 and receipt['removed_synthetic_fits']==40
    assert hashlib.sha256(new.payload.encode()).hexdigest()==receipt['baseline_payload_sha256']
    return receipt

def prepare(runner,proof):
    root=Path(__file__).resolve().parents[2];archive=runner.directory/ARCHIVE
    original=read(archive/'run.json')
    assert original['commit']==proof['from_commit']==BEFORE and original['completed']==proof['completed_before_adoption']
    assert original['status']=='failed' and original['attempts'][-1]['gate']=='native:tank-prepare'
    validate_recovery(root,runner.directory,archive/'recovery')
    proof.update(archive=ARCHIVE,app_sha256=sha(runner.directory/'apks/app-debug.apk'),
        old_test_apk_sha256=sha(archive/'apks/app-debug-androidTest.apk'),
        retained_hashes={str(p.relative_to(runner.directory)):sha(p) for p in runner.native.rglob('*') if p.is_file()
            and not p.name.startswith('tank-') and p.name not in ('failure.png','failure-logcat.txt','apk-contents.json','lint-results-debug.html')},
        failed_artifact_hashes={str(p.relative_to(archive)):sha(p) for p in (archive/'native').iterdir() if p.is_file()})
    assert sha(runner.directory/'apks/app-debug-androidTest.apk')==proof['old_test_apk_sha256']
    for path in runner.native.iterdir():
        if path.is_file() and (path.name.startswith('tank-') or path.name in ('failure.png','failure-logcat.txt')):
            assert sha(path)==sha(archive/'native'/path.name);path.unlink()
    runner.execute('headless:tank-history-guard',[sys.executable,'-I',root/'android/ci/test_tank_history_retry.py'])
    runner.build('apks-lint')
    assert sha(root/'android/app/build/outputs/apk/debug/app-debug.apk')==proof['app_sha256'],'Application APK changed'
    runner.build('package')
    new=runner.directory/'apks/app-debug-androidTest.apk';packages_equal(archive/'apks/app-debug-androidTest.apk',new)
    proof['new_test_apk_sha256']=sha(new);assert proof['new_test_apk_sha256']!=proof['old_test_apk_sha256']
    sdk=Path(os.environ['ANDROID_HOME'])
    runner.execute('build:tank-test-signature',[sdk/'build-tools/35.0.0/apksigner.bat','verify','--verbose','--print-certs',new])
    assert all(sha(runner.directory/name)==digest for name,digest in proof['retained_hashes'].items())
    proof['prepared']=True

def install(runner,proof):
    root=Path(__file__).resolve().parents[2];archive=runner.directory/proof['archive']
    receipt=validate_recovery(root,runner.directory,archive/'recovery')
    def adb(*parts):return subprocess.check_output(['adb','-s',runner.serial,*map(str,parts)],timeout=60)
    assert adb('emu','avd','name').decode().splitlines()[0]==runner.state['avd_name']
    assert adb('shell','getprop','ro.kernel.qemu').strip()==b'1' and adb('shell','settings','get','global','airplane_mode_on').strip()==b'1'
    package='io.github.sussic.pyfa.dev';adb('shell','am','force-stop',package);adb('shell','sync')
    remote='no_backup/fits/graph.sqlite3'
    def graph():return adb('exec-out','run-as',package,'cat',remote)
    assert hashlib.sha256(graph()).hexdigest()==receipt['original_store_sha256']
    runner.execute('environment:tank-test-update',['adb','-s',runner.serial,'install','-r','-t',runner.directory/'apks/app-debug-androidTest.apk'])
    assert hashlib.sha256(graph()).hexdigest()==receipt['original_store_sha256'],'Test installation changed fits'
    target='/data/local/tmp/pyfa-c0132-restored.sqlite3'
    adb('push',archive/'recovery/restored-graph.sqlite3',target);adb('shell','run-as',package,'cp',target,remote)
    assert hashlib.sha256(graph()).hexdigest()==receipt['restored_store_sha256'];adb('shell','rm',target)
    proof.update(installed=True,recovery_receipt_sha256=sha(archive/'recovery/recovery.json'))

def validate_retained(root,run,proof):
    archive=run/proof['archive'];assert archive.resolve().is_relative_to(run.resolve())
    original=read(archive/'run.json')
    assert proof['completed_before_adoption']==original['completed'] and len(original['completed'])==102
    assert proof['retained_gates']==[g for g in original['completed'] if g not in ('build:apks-lint','build:package')]
    failure=original['attempts'][-1];assert failure['exit_code']!=0 and sha(run/failure['log'])==failure['log_sha256']
    assert sha(run/'apks/app-debug.apk')==proof['app_sha256']
    assert sha(archive/'apks/app-debug-androidTest.apk')==proof['old_test_apk_sha256']
    assert sha(run/'apks/app-debug-androidTest.apk')==proof['new_test_apk_sha256']
    packages_equal(archive/'apks/app-debug-androidTest.apk',run/'apks/app-debug-androidTest.apk')
    for name,digest in proof['retained_hashes'].items():assert sha(run/name)==digest
    for name,digest in proof['failed_artifact_hashes'].items():assert sha(archive/name)==digest
    validate_recovery(root,run,archive/'recovery')
    assert sha(archive/'recovery/recovery.json')==proof['recovery_receipt_sha256']
