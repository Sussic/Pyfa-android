"""Explicit, resumable local verification. No runner service or hosted execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import nullcontext

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_suite import STEPS as NATIVE_STEPS

ROOT=Path(__file__).resolve().parents[2]
PIN='8b04f3b271e614b3e103853b44a7851a63d79d0e'
FAMILIES=['projection','command','catalog','equipment','empty_hulls','module_edits',
    'charge_edits','variation_edits','rack_ordering','bulk_charges','bulk_states',
    'clone_fill','bulk_variation_removal','hull_modes','subsystems','structures',
    'cargo_stacks','cargo_actions','cargo_transfers','notes','history','history_mutations']
HEADLESS=['bridge','persistence','library','market','empty_hulls','module_edits',
    'charge_edits','variation_edits','rack_ordering','bulk_charges','bulk_states',
    'clone_fill','bulk_variation_removal','hull_modes','subsystems','structures',
    'cargo_stacks','cargo_actions','cargo_transfers','notes','history','history_mutations']
BUILD=['dependencies','engine-assets','apks-lint','signature','package']


def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def save(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def plan(mode,gate):
    desktop=['desktop:utilities','desktop:reference','desktop:migration',
        *('reference:'+name for name in FAMILIES),
        'headless:base','headless:projection','headless:command',
        *('headless:'+name for name in HEADLESS)]
    if gate:
        assert mode=='desktop' and gate in FAMILIES, 'Focused gates use desktop --gate <family>'
        return ['reference:'+gate,'headless:'+({'equipment':'market'}.get(gate,gate))] if gate not in ('catalog',) else ['reference:'+gate]
    return (desktop if mode in ('full','desktop') else []) + \
        ['build:'+name for name in BUILD if mode in ('full','build','native')] + \
        ['native:'+name for name in NATIVE_STEPS if mode in ('full','native')]


class Run:
    def __init__(self,args):
        self.args=args
        self.directory=Path(args.run).resolve() if args.run else \
            Path(os.environ['LOCALAPPDATA'])/'PyfaAndroid/PyfaDevelopment/evidence'/(
                datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+git('rev-parse','--short','HEAD')+'-'+uuid.uuid4().hex[:6])
        assert not self.directory.is_relative_to(ROOT), 'Keep large evidence outside the synced checkout'
        self.file=self.directory/'run.json'
        self.emulator=None
        self.serial=None
        if args.action=='start':
            assert not git('status','--porcelain','--untracked-files=normal'), 'Commit reviewed changes before recording exact-commit evidence'
            self.directory.mkdir(parents=True,exist_ok=False)
            self.state={'version':1,'commit':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),
                'mode':args.mode,'gate':args.gate,'status':'pending','plan':plan(args.mode,args.gate),
                'completed':[],'attempts':[],'platform':platform.platform(),'python':sys.version,
                'started_utc':datetime.now(timezone.utc).isoformat(),'hosted_actions_pass':False}
            save(self.file,self.state)
        else:
            self.original_run_bytes=self.file.read_bytes()
            self.state=json.loads(self.file.read_text(encoding='utf-8'))
            assert self.state['status'] != 'passed', 'Completed runs are immutable; start a new run'
            assert not git('status','--porcelain','--untracked-files=normal'), 'Resume the same clean tested commit'
            current=git('rev-parse','HEAD')
            if self.state['commit']!=current:
                assert args.adopt_launcher_fix or args.restart_native, 'Resume the same commit, explicitly adopt a launcher fix, or restart native verification'
                assert args.restart_native or not any(step.startswith('native:') for step in self.state['completed']), 'Native execution has begun; require a fresh native run'
                changed=git('diff','--name-only',self.state['commit'],current).splitlines()
                allowed={'android/ci/local_verification.py','android/ci/native_suite.py','android/verify-local.ps1'}
                if args.restart_native:
                    allowed.update({'android/ci/check-history.py','android/ci/history_progress.py',
                        'android/ci/report_local.py','android/ci/test_report_local.py'})
                    changed=[p for p in changed if p!='AGENTS.md' and not p.startswith('docs/android/')]
                    if 'android/ci/check-history.py' in changed:
                        old_history=git('show',self.state['commit']+':android/ci/check-history.py')
                        new_history=(ROOT/'android/ci/check-history.py').read_text(encoding='utf-8').strip()
                        expected_history=old_history.replace('import json\n','import json\nimport os\n',1).replace('timeout=900)',"timeout=2400 if os.name == 'nt' else 900)",1)
                        assert new_history==expected_history, 'Only the approved import and exact Windows history timeout expression may change'
                assert changed and set(changed)<=allowed, 'Completed host/build inputs changed; results cannot be reused'
                import ast
                previous=ast.parse(git('show',self.state['commit']+':android/ci/local_verification.py'))
                present=ast.parse(Path(__file__).read_text(encoding='utf-8'))
                def executed(tree):
                    result={}
                    for node in ast.walk(tree):
                        if isinstance(node,ast.FunctionDef) and node.name in ('plan','host','build','execute'):
                            result[node.name]=ast.dump(node,include_attributes=False)
                    return result
                assert executed(previous)==executed(present), 'Executed host/build behavior changed'
                assert self.state['plan']==plan(self.state['mode'],self.state['gate'])
                for row in self.state['attempts']: row.setdefault('tested_commit',self.state['commit'])
                self.state.setdefault('launcher_fix_reuse',[]).append({'from_commit':self.state['commit'],
                    'to_commit':current,'changed_files':changed,'unchanged_completed_host_build_inputs':True})
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            assert self.state['tree']==git('rev-parse','HEAD^{tree}')
        self.native=self.directory/'native';self.native.mkdir(exist_ok=True)
        os.environ['PYFA_EVIDENCE_DIR']=str(self.native)
        os.environ['PYFA_EXECUTION_KIND']='local_windows'
        os.environ['PYFA_LOCAL_RUN_ID']=self.directory.name
        os.environ['PYTHONUTF8']='1'
        os.environ.pop('GITHUB_RUN_ID',None);os.environ.pop('GITHUB_STEP_SUMMARY',None)
        self.reference=Path(args.reference_python or ROOT/'.venv/reference/Scripts/python.exe')
        self.source=Path(args.source or ROOT/'build/reference-upstream').resolve()
        assert git('-C',str(self.source),'rev-parse','HEAD')==PIN
        self.db=Path(self.state.get('database',ROOT/'android/build/engine/assets/engine/eve.db'))
        assert sys.version_info[:2]==(3,11), 'Reuse the pinned Python 3.11 environment'
        assert sha(ROOT/'android/gradle/wrapper/gradle-wrapper.jar')=='81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f'

    def execute(self,name,command,cwd=ROOT,timeout=None):
        attempt=self.directory/'logs'/f'{len(self.state["attempts"]):03}-{name.replace(":","-")}.log'
        attempt.parent.mkdir(exist_ok=True)
        row={'gate':name,'command':list(map(str,command)),'log':str(attempt.relative_to(self.directory)),
            'started_utc':datetime.now(timezone.utc).isoformat()}
        self.state['attempts'].append(row);save(self.file,self.state)
        print('Running '+name,flush=True)
        started=time.monotonic()
        with attempt.open('wb') as log:
            try:
                result=subprocess.run(list(map(str,command)),cwd=cwd,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
                row['exit_code']=result.returncode
            except BaseException:
                row['exit_code']=None;row['interrupted']=True;save(self.file,self.state);raise
        row['seconds']=round(time.monotonic()-started,3);row['log_sha256']=sha(attempt)
        save(self.file,self.state)
        if row['exit_code']!=0:
            print(attempt.read_text(encoding='utf-8',errors='replace')[-6000:],flush=True)
            raise RuntimeError(f'{name} failed; full log: {attempt}')
        print('PASS '+name,flush=True)

    def host(self,step):
        kind,name=step.split(':',1)
        output=self.directory/'host'/f'{len(self.state["attempts"]):03}-{kind}-{name}'
        output.parent.mkdir(exist_ok=True)
        if step=='desktop:utilities': command=[self.reference,'-m','unittest','discover','-s','tools/android_reference/tests','-v']
        elif step=='desktop:reference': command=[self.reference,'-I','tools/android_reference/reference.py','--source',self.source,'--output',output,'--check','tools/android_reference/fixtures/vexor.json']
        elif step=='desktop:migration': command=[self.reference,'-I','tools/android_headless/check_desktop_migration.py','--database',self.db]
        elif kind=='reference':
            command=[self.reference,'-I',f'tools/android_reference/{name}.py','--source',self.source,'--database',self.db,
                '--output',output,'--check',f'tools/android_reference/fixtures/{name.replace("_","-")}.json']
        else:
            script='check.py' if name in ('base','projection','command') else f'check_{name}.py'
            command=[sys.executable,'-I',f'tools/android_headless/{script}','--database',self.db,'--output',output]
            if name in ('projection','command'): command+=['--scenario',name]
            if '--source' in (ROOT/'tools/android_headless'/script).read_text(encoding='utf-8'):
                command+=['--source',self.source]
        self.execute(step,command)
        if step=='desktop:reference':
            self.db=output/'eve.db';self.state['database']=str(self.db)

    def build(self,name):
        sdk=Path(os.environ['ANDROID_HOME']);android=ROOT/'android'
        commands={
            'dependencies':[sys.executable,'prepare-dependencies.py'],
            'engine-assets':[sys.executable,'-I','prepare-engine.py'],
            'apks-lint':[android/'gradlew.bat','--no-daemon','--console=plain',':app:assembleDebug',':app:assembleDebugAndroidTest',':app:lintDebug'],
            'signature':[sdk/'build-tools/35.0.0/apksigner.bat','verify','--verbose','--print-certs','app/build/outputs/apk/debug/app-debug.apk'],
            'package':[sys.executable,'ci/verify-apk.py']}
        self.execute('build:'+name,commands[name],cwd=android)
        if name=='package':
            target=self.directory/'apks';target.mkdir(exist_ok=True)
            for apk in (android/'app/build/outputs/apk').rglob('*.apk'):shutil.copyfile(apk,target/apk.name)
            lint=android/'app/build/reports/lint-results-debug.html'
            shutil.copyfile(lint,self.native/lint.name)

    def start_emulator(self):
        sdk=Path(os.environ['ANDROID_HOME']);tools=Path(os.environ['PYFA_SDKMANAGER']).parent
        self.execute('environment:whpx',[sdk/'emulator/emulator.exe','-accel-check'])
        whpx=(self.directory/self.state['attempts'][-1]['log']).read_text(encoding='utf-8')
        assert 'WHPX' in whpx and 'usable' in whpx
        image=sdk/'system-images/android-36/google_apis/x86_64'
        assert image.is_dir(), 'Install system-images;android-36;google_apis;x86_64 first'
        avds=self.directory/'avd';avds.mkdir(exist_ok=True)
        os.environ['ANDROID_AVD_HOME']=str(avds)
        name='pyfa-local-'+self.directory.name.replace('.','-')
        self.state['avd_name']=name
        if not (avds/f'{name}.ini').exists():
            with (self.directory/f'avd-create-{len(self.state["attempts"]):03}.log').open('wb') as log:
                subprocess.run([str(tools/'avdmanager.bat'),'create','avd','--name',name,'--package',
                    'system-images;android-36;google_apis;x86_64','--device','pixel_2'],input=b'no\n',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        # Bind only this disposable emulator. Other emulators and phones stay untouched.
        devices=subprocess.check_output(['adb','devices'],text=True)
        used={line.split()[0] for line in devices.splitlines()[1:] if line.strip()}
        port=next(p for p in range(5560,5680,2) if f'emulator-{p}' not in used)
        self.serial=f'emulator-{port}';os.environ['ANDROID_SERIAL']=self.serial
        self.state['emulator_serial']=self.serial
        self.state['emulator_version']=(sdk/'emulator/source.properties').read_text(encoding='utf-8')
        self.state['image_version']=(image/'source.properties').read_text(encoding='utf-8')
        save(self.file,self.state)
        self.emulator_log=(self.directory/'emulator.log').open('ab')
        self.emulator=subprocess.Popen([str(sdk/'emulator/emulator.exe'),'-avd',name,'-port',str(port),
            '-accel','on','-no-window','-gpu','swiftshader_indirect','-no-snapshot','-noaudio',
            '-no-boot-anim','-camera-back','none'],stdout=self.emulator_log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            if self.emulator.poll() is not None: raise RuntimeError('Emulator exited; inspect emulator.log')
            boot=subprocess.run(['adb','-s',self.serial,'shell','getprop','sys.boot_completed'],capture_output=True,text=True,timeout=20)
            if boot.returncode==0 and boot.stdout.strip()=='1':break
            time.sleep(1)
        else:raise RuntimeError('Emulator did not boot within 300 seconds')
        actual=subprocess.check_output(['adb','-s',self.serial,'emu','avd','name'],text=True)
        assert actual.splitlines()[0]==name

    def stop_emulator(self):
        if self.emulator is None:return
        subprocess.run(['adb','-s',self.serial,'emu','kill'],capture_output=True,timeout=30)
        try:self.emulator.wait(timeout=30)
        except subprocess.TimeoutExpired:self.emulator.terminate();self.emulator.wait(timeout=30)
        self.emulator_log.close();self.emulator=None

    def run(self):
        import msvcrt
        lock=(self.directory/'run.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        print('Evidence: '+str(self.directory),flush=True)
        try:
            if self.args.restart_native:
                assert self.state['status']=='failed' and any(s.startswith('native:') for s in self.state['plan']), 'Restart only a failed native chain'
                # Preserve failed evidence before removing only this run's disposable AVD.
                # Replaying a failed mutation phase against its partially modified store
                # would violate its original-library precondition.
                archive=self.directory/('failed-native-'+uuid.uuid4().hex[:8])
                archive.mkdir()
                (archive/'run.json').write_bytes(self.original_run_bytes)
                shutil.copytree(self.native,archive/'native')
                reports=ROOT/'android/app/build/outputs/androidTest-results/connected'
                if reports.exists():shutil.copytree(reports,archive/'junit')
                for name in ('screenshots-reviewed-partial.json','screenshots-reviewed.json'):
                    if (self.directory/name).exists():shutil.copyfile(self.directory/name,archive/name)
                retained=list((self.directory/'apks').glob('*.apk'))
                assert len(retained)==2, 'Both previously tested APKs are required'
                for apk in retained:
                    current=list((ROOT/'android/app/build/outputs/apk').rglob(apk.name))
                    assert len(current)==1 and sha(apk)==sha(current[0]), 'Reused APK differs from the tested copy'
                if (self.directory/'avd').exists():
                    assert (self.directory/'avd').resolve().parent==self.directory
                    shutil.rmtree(self.directory/'avd')
                from summary_repair import clear_native_results
                clear_native_results(self.native)
                self.state.setdefault('native_restarts',[]).append({'archive':archive.name,'reason':'Failed native chain; fresh disposable store required','commit':self.state['commit']})
                self.state['completed']=[s for s in self.state['completed'] if not s.startswith('native:')]
            self.state['status']='running';save(self.file,self.state)
            for step in self.state['plan']:
                if step in self.state['completed']:continue
                if (self.directory/'PAUSE').exists():
                    self.state['status']='paused';save(self.file,self.state);return
                assert self.state['commit']==git('rev-parse','HEAD') and not git('status','--porcelain'), 'Test inputs changed during execution'
                if step.startswith(('desktop:','reference:','headless:')):self.host(step)
                elif step.startswith('build:'):self.build(step.split(':')[1])
                else:
                    if self.emulator is None:self.start_emulator()
                    from history_progress import HistoryProgress
                    diagnostics=HistoryProgress(self.directory/'diagnostics'/f'history-{len(self.state["attempts"]):03}',self.serial) if step=='native:check-history.py' else nullcontext()
                    with diagnostics:
                        self.execute(step,[sys.executable,ROOT/'android/ci/native_suite.py','--step',step.split(':',1)[1]],cwd=ROOT/'android')
                self.state['completed'].append(step);save(self.file,self.state)
            self.state['status']='passed'
            self.state['completed_utc']=datetime.now(timezone.utc).isoformat()
            reports=ROOT/'android/app/build/outputs/androidTest-results/connected'
            if any(s.startswith('native:') for s in self.state['plan']) and reports.exists():shutil.copytree(reports,self.native/'junit',dirs_exist_ok=True)
            self.stop_emulator()
            for row in self.state['attempts']: row.setdefault('tested_commit',self.state['commit'])
            save(self.file,self.state)
            files={str(p.relative_to(self.directory)):{'sha256':sha(p),'bytes':p.stat().st_size}
                for p in self.directory.rglob('*') if p.is_file() and not p.is_relative_to(self.directory/'avd') and p.name not in ('run.lock','files.json')}
            save(self.directory/'files.json',files)
            print('PASS local '+self.state['mode']+'; screenshot review is still a separate required step',flush=True)
        except BaseException:
            self.state['status']='failed';save(self.file,self.state);raise
        finally:
            if self.state['status']!='passed':
                for row in self.state['attempts']: row.setdefault('tested_commit',self.state['commit'])
                save(self.file,self.state)
            self.stop_emulator();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
            # Successful full verification no longer needs writable emulator data.
            if self.state['status']=='passed' and (self.directory/'avd').exists():shutil.rmtree(self.directory/'avd')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','resume','pause','plan'])
    parser.add_argument('--mode',choices=['full','desktop','build','native'],default='full')
    parser.add_argument('--gate',choices=FAMILIES)
    parser.add_argument('--run');parser.add_argument('--source');parser.add_argument('--reference-python')
    parser.add_argument('--adopt-launcher-fix',action='store_true',help='Reuse unchanged host/build gates before any native gate passed, after a verified launcher-only fix')
    parser.add_argument('--restart-native',action='store_true',help='Archive failed evidence and restart the complete native chain with a fresh disposable AVD; reuse only unchanged host/build gates')
    args=parser.parse_args()
    if args.action=='plan':print('\n'.join(plan(args.mode,args.gate)));return
    assert os.name=='nt', 'This explicit launcher owns Windows WHPX AVDs'
    if args.action=='pause':
        assert args.run
        (Path(args.run)/'PAUSE').write_text('Pause at the next completed gate\n',encoding='utf-8');return
    assert args.action!='resume' or args.run
    runner=Run(args)
    if args.action=='resume':(runner.directory/'PAUSE').unlink(missing_ok=True)
    runner.run()


if __name__=='__main__':main()
