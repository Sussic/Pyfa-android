"""Exact missing C01.2 persistent-storage runner flag; retain unchanged proof."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

PATH='android/app/src/androidTest/java/io/github/sussic/pyfa/DiagnosticTestRunner.kt'
OLD='!arguments.containsKey("b092_phase") && !arguments.containsKey("c011_phase"))'
NEW='!arguments.containsKey("b092_phase") && !arguments.containsKey("c011_phase") && !arguments.containsKey("c012_phase"))'
ARCHIVE='capacitor-runner-fix-original'
INIT='''            if self.state['commit']!=current and args.adopt_capacitor_runner_fix:
                from capacitor_runner_retry import exact_source
                assert self.state['status']=='failed' and self.state['completed']==plan('full',None)[:-3]
                assert self.state['attempts'][-1]['gate']=='native:capacitor-prepare' and self.state['attempts'][-1]['exit_code']!=0
                exact_source(ROOT,self.state['commit'],current)
                before=self.state['commit']
                for row in self.state['attempts']:row.setdefault('tested_commit',before)
                self.state['capacitor_runner_reuse']={'from_commit':before,'to_commit':current,
                    'retained_gates':list(self.state['completed']),'prepared':False,'installed':False}
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
'''
PREPARE='''            capacitor_fix=self.state.get('capacitor_runner_reuse')
            if capacitor_fix and not capacitor_fix['prepared']:
                from capacitor_runner_retry import prepare
                prepare(self,capacitor_fix);save(self.file,self.state)
'''
INSTALL='''                    if capacitor_fix and not capacitor_fix['installed']:
                        from capacitor_runner_retry import install
                        install(self,capacitor_fix);save(self.file,self.state)
'''
ARG="    parser.add_argument('--adopt-capacitor-runner-fix',action='store_true',help='Adopt only the exact missing C01.2 persistent runner flag; retain all prior gates and app APK')\n"
REPORT='''    capacitor_proof=state.get('capacitor_runner_reuse')
    if capacitor_proof:
        from capacitor_runner_retry import exact_source,validate_retained
        exact_source(root,capacitor_proof['from_commit'],capacitor_proof['to_commit'])
        assert capacitor_proof['to_commit']==state['commit'] and capacitor_proof['prepared'] and capacitor_proof['installed']
        validate_retained(run,capacitor_proof)
        assert latest['build:capacitor-test-runner']['exit_code']==0 and latest['headless:capacitor-runner-guard']['exit_code']==0
'''
RETAIN='''            if capacitor_proof and gate in capacitor_proof['retained_gates']:
                assert row['tested_commit']==capacitor_proof['from_commit']
                continue
'''

def once(text,anchor,value):
    assert text.count(anchor)==1,anchor
    return text.replace(anchor,value,1)

def runner_source(text):
    text=once(text,'            if self.state[\'commit\']!=current and args.adopt_resource_test_fix:',INIT+'            if self.state[\'commit\']!=current and args.adopt_resource_test_fix:')
    text=once(text,"            resource_fixes=self.state.get('resource_test_reuse',[])",PREPARE+"            resource_fixes=self.state.get('resource_test_reuse',[])")
    text=once(text,"                    if resource_fixes and not resource_fixes[-1]['installed']:",INSTALL+"                    if resource_fixes and not resource_fixes[-1]['installed']:")
    return once(text,'    args=parser.parse_args()\n',ARG+'    args=parser.parse_args()\n')

def report_source(text):
    text=once(text,"    resource_reuse=state.get('resource_test_reuse',[])",REPORT+"    resource_reuse=state.get('resource_test_reuse',[])")
    return once(text,"            comparison_commit=state['commit']",RETAIN+"            comparison_commit=state['commit']")

def validate_sources(old,new,changed):
    allowed={PATH,'android/ci/local_verification.py','android/ci/report_local.py',
             'android/ci/capacitor_runner_retry.py','android/ci/test_capacitor_runner_retry.py'}
    assert PATH in changed and set(changed)<=allowed,changed
    assert new[PATH]==once(old[PATH],OLD,NEW),'Unrelated native runner source change'
    for path,transform in [('android/ci/local_verification.py',runner_source),('android/ci/report_local.py',report_source)]:
        assert new[path]==transform(old[path]),'Unrelated verification change: '+path
    def commands(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text))
        if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert commands(old['android/ci/local_verification.py'])==commands(new['android/ci/local_verification.py'])

def exact_source(root,before,after):
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    paths=(PATH,'android/ci/local_verification.py','android/ci/report_local.py')
    def source(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=root,text=True,encoding='utf-8')
    validate_sources({p:source(before,p) for p in paths},{p:source(after,p) for p in paths},changed)

def packages_equal(old,new):
    import re
    with ZipFile(old) as a,ZipFile(new) as b:
        assert set(a.namelist())==set(b.namelist())
        for name in a.namelist():
            if name.startswith('META-INF/') or re.fullmatch(r'classes\d*\.dex',name):continue
            assert a.read(name)==b.read(name),'Non-bytecode test package content changed: '+name

def prepare(runner,proof):
    from local_verification import sha
    root=Path(__file__).resolve().parents[2]
    archive=runner.directory/ARCHIVE;archive.mkdir(exist_ok=False)
    (archive/'run.json').write_bytes(runner.original_run_bytes)
    shutil.copytree(runner.directory/'apks',archive/'apks')
    (archive/'native').mkdir()
    for name in ('capacitor-prepare-instrumentation.txt','failure.png','failure-logcat.txt','apk-contents.json'):
        path=runner.native/name
        if path.exists():shutil.copyfile(path,archive/'native'/name)
    proof.update(archive=ARCHIVE,app_sha256=sha(archive/'apks/app-debug.apk'),
        old_test_apk_sha256=sha(archive/'apks/app-debug-androidTest.apk'),
        retained_hashes={str(p.relative_to(runner.directory)):sha(p) for p in runner.native.rglob('*')
            if p.is_file() and not p.name.startswith('capacitor-') and p.name not in ('failure.png','failure-logcat.txt','apk-contents.json')})
    runner.execute('headless:capacitor-runner-guard',[sys.executable,'-I',root/'android/ci/test_capacitor_runner_retry.py'])
    runner.execute('build:capacitor-test-runner',[root/'android/gradlew.bat','--no-daemon','--console=plain',':app:assembleDebugAndroidTest'],cwd=root/'android')
    assert sha(root/'android/app/build/outputs/apk/debug/app-debug.apk')==proof['app_sha256']
    test=root/'android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'
    packages_equal(archive/'apks/app-debug-androidTest.apk',test)
    runner.build('package')
    assert sha(runner.directory/'apks/app-debug.apk')==proof['app_sha256']
    proof['new_test_apk_sha256']=sha(runner.directory/'apks/app-debug-androidTest.apk');proof['prepared']=True

def install(runner,proof):
    from local_verification import sha,save
    def adb(*args):return subprocess.check_output(['adb','-s',runner.serial,*map(str,args)],timeout=120)
    package='io.github.sussic.pyfa.dev';archive=runner.directory/proof['archive']
    assert adb('emu','avd','name').decode().splitlines()[0]==runner.state['avd_name']
    assert adb('shell','getprop','ro.kernel.qemu').strip()==b'1'
    assert adb('shell','settings','get','global','airplane_mode_on').strip()==b'1'
    adb('shell','am','force-stop',package);adb('shell','sync')
    remote='no_backup/fits/graph.sqlite3'
    digest=adb('shell','run-as',package,'sha256sum',remote).split()[0].decode()
    target=archive/'retained-graph.sqlite3';target.write_bytes(adb('exec-out','run-as',package,'cat',remote));assert sha(target)==digest
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from android_bridge.store import GraphStore,decode_graph
    store=GraphStore(target);graph=decode_graph(store.current.payload)
    prior=json.loads((runner.native/'resources-restored-native.json').read_text(encoding='utf-8'))
    assert store.current.generation==prior['runtime_start']['persistence']['generation']
    ids=[r['id'] for r in prior['saved']['inherited']['data']]+prior['saved']['ids']
    assert len(ids)==157 and len(set(ids))==157 and len(graph['fit_order'])==158
    assert set(ids)<=set(graph['fit_order'])
    copy=set(graph['fit_order'])-set(ids);assert len(copy)==1
    assert graph['records'][next(iter(copy))]['spec']['name']=='C01.1 copy'
    assert not any(r['spec']['name'].startswith('C01.2 ') for r in graph['records'].values())
    before={field:graph[field] for field in ('records','revisions','modified','fit_order','recent','sample_id')}
    runner.execute('environment:capacitor-runner-install',['adb','-s',runner.serial,'install','-r','-t',runner.directory/'apks/app-debug-androidTest.apk'])
    assert adb('shell','run-as',package,'sha256sum',remote).split()[0].decode()==digest
    proof.update(retained_graph_sha256=digest,retained_generation=store.current.generation,retained_fits=158,
        baseline_sha256=sha(runner.native/'resources-restored-native.json'),installed=True,
        no_capacitor_fit_created_before_failure=True,graph_unchanged_by_install=True)
    save(archive/'retained-store.json',dict(graph_sha256=digest,generation=store.current.generation,fit_count=158,
        original_inputs_metadata_order_recent=before,no_changes=True))

def validate_retained(run,proof):
    from local_verification import sha
    archive=run/proof['archive'];assert archive.resolve().is_relative_to(run.resolve())
    assert proof['retained_gates']==json.loads((archive/'run.json').read_text(encoding='utf-8'))['completed']
    assert len(proof['retained_gates'])==94 and proof['retained_fits']==158 and proof['graph_unchanged_by_install']
    assert proof['no_capacitor_fit_created_before_failure']
    assert sha(archive/'retained-graph.sqlite3')==proof['retained_graph_sha256']
    assert sha(run/'native/resources-restored-native.json')==proof['baseline_sha256']
    assert sha(archive/'apks/app-debug.apk')==sha(run/'apks/app-debug.apk')==proof['app_sha256']
    assert sha(archive/'apks/app-debug-androidTest.apk')==proof['old_test_apk_sha256']
    assert sha(run/'apks/app-debug-androidTest.apk')==proof['new_test_apk_sha256']
    packages_equal(archive/'apks/app-debug-androidTest.apk',run/'apks/app-debug-androidTest.apk')
    for name,digest in proof['retained_hashes'].items():assert sha(run/name)==digest
