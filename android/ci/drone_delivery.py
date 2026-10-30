"""C04 required gates, independent native evidence checks and explicit admission."""
import ctypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'tools/android_reference/fixtures'
OPERATIONS={'add_drone','add_drone_stack','set_drone_amount','remove_drones','toggle_drones','clone_drone'}
HOST_GATES=('reference:drone_core','reference:drone_details','reference:drone_acceptance',
            'headless:drone_core','headless:drone_details',
            *('headless:drone_'+group for group in ('projection','command','variations','history','boundaries')),
            'headless:drone_harness','reference:drone_conservation','headless:drone_conservation')
NATIVE_GATE='native:c04-delivery'
DECISION_GATE='acceptance:c04-split-merge'
PHASES={
    'contract':('DroneContractTest',('exactDetailsContractRejectsLostFieldsUnitsIdentityAndCounts',
        'queuedSelectionsAreIndependentOfCallerMutation','eightOperationsEncodePreciselyAndPermitMainOnlyToggle')),
    'fresh-ui':('DroneUiTest',('cargoBrowseReturnsToDronesAndEditsSurviveRecreation',)),
    'core':('DroneMatrixTest',('originalCoreCommandsAndHullBoundariesOffline',)),
    'linked':('DroneMatrixTest',('originalLinkedRecipientsAndOrdinaryVariationsOffline',)),
    'conservation':('DroneMatrixTest',('approvedConservationAndRestartOffline',)),
    'conservation-restored':('DroneMatrixTest',('approvedConservationAndRestartOffline',)),
    'prepare':('DroneAcceptanceTest',('originalDetailsMutationHistoryAtomicityAndRestartOffline',)),
    'restored':('DroneAcceptanceTest',('originalDetailsMutationHistoryAtomicityAndRestartOffline',)),
    'mutation-ui':('DroneUiTest',('restoredMutationsShowDetailsAndRetainSeparateIdentities',)),
}
SCREENSHOTS=('selected-over-limit.png','empty-after-redo.png','existing-roll-details.png','ordinary-variation.png','conserved-split-merge.png')
REFERENCE_FILES={'drone_core':'drone-core-edits.json','drone_details':'drone-details.json','drone_acceptance':'drone-acceptance.json','drone_conservation':'drone-conservation.json'}


def require_decision():
    record=json.loads((ROOT/'docs/android/evidence/c04-conservation-decision.json').read_text(encoding='utf-8'))
    expected=json.loads((FIXTURES/'drone-conservation.json').read_text(encoding='utf-8'))
    assert record['status']=='approved' and record['selected']==expected['policy'], 'Unapproved conservation policy'
    policy=record['selected']
    assert policy['id']=='F08.03-conserve-v1' and policy['active_counts']=='conserve'
    assert policy['split_allocation']=='moved_active=min(requested,original_active)'
    return policy



def admit_native(*, starting=False):
    """Apply the current host policy, rather than an archived native RAM floor."""
    sys.path.insert(0,str(ROOT/'scripts'))
    from execution_policy import AdmissionDeferred,admit,detect_host,load_policy,select
    from policy_host_metrics import host_memory
    policy,policy_hash=load_policy()
    host=os.environ.get('CODEX_EXECUTION_HOST') or detect_host()
    if host!=detect_host():
        raise RuntimeError('Selected policy host differs from the actual executor')
    profile='full_suite' if starting else 'focused_test'
    settings=select(policy,host,profile)
    physical,commit=host_memory()
    disk=shutil.disk_usage(ROOT).free
    forecast=policy['android_runtime']['new_avd_disk_forecast_bytes'] if starting else 0
    reasons=admit(settings,physical,commit,disk,forecast,0)
    if reasons:
        raise AdmissionDeferred('; '.join(reasons)+'; native validation remains pending')
    return {'available_physical_bytes':physical,'available_commit_bytes':commit,
            'free_disk_bytes':disk,'policy_sha256':policy_hash,'host':host,'workload':profile}



def host_command(step,output,database,reference_python,source):
    kind,name=step.split(':',1); assert step in HOST_GATES
    if kind=='reference':
        return [reference_python,'-I','-B',str(ROOT/'android/ci/drone_reference.py'),'--family',name,
                '--source',str(source),'--database',str(database),'--output',str(output)]
    if name=='drone_harness':
        return [sys.executable,'-I','-B','-m','unittest','discover','-s',str(ROOT/'android/ci'),'-p','test_drone*.py','-v']
    if name=='drone_conservation':
        return [sys.executable,'-I','-B',str(ROOT/'tools/android_headless/check_drone_conservation.py'),'--database',str(database),
                '--reference',str(FIXTURES/REFERENCE_FILES[name]),'--output',str(output)]
    if name in ('drone_core','drone_details'):
        script='check_drone_edits.py' if name=='drone_core' else 'check_drone_details.py'
        return [sys.executable,'-I','-B',str(ROOT/'tools/android_headless'/script),'--database',str(database),
                '--reference',str(FIXTURES/REFERENCE_FILES[name]),'--output',str(output)]
    return [sys.executable,'-I','-B',str(ROOT/'tools/android_headless/check_drone_acceptance.py'),
            '--database',str(database),'--reference',str(FIXTURES/'drone-acceptance.json'),
            '--group',name.removeprefix('drone_'),'--output',str(output)]


def compare_wire(expected,actual,path='root'):
    """Complete JSON values/units; integer-valued decimal serialization is allowed.

    Android JSONObject writes 0.0 as 0. Booleans never count as numbers, missing
    and extra fields fail, and all decimals keep REL1e-10/ABS1e-9. Raw DTO kind
    validation remains in BridgeCodec and the inherited typed transport gates.
    """
    if isinstance(expected,dict):
        assert type(actual) is dict and expected.keys()==actual.keys(),path
        for key in expected: compare_wire(expected[key],actual[key],path+'.'+key)
    elif isinstance(expected,list):
        assert type(actual) is list and len(expected)==len(actual),path
        for i,(a,b) in enumerate(zip(expected,actual)): compare_wire(a,b,f'{path}[{i}]')
    elif type(expected) in (int,float):
        assert type(actual) in (int,float) and math.isfinite(actual) and math.isfinite(expected),path
        assert math.isclose(expected,actual,rel_tol=1e-10,abs_tol=1e-9),(path,expected,actual)
    else: assert type(expected) is type(actual) and expected==actual,(path,expected,actual)


def validate_observations(core,linked,original,acceptance):
    cases=original['cases']+acceptance['core_extra']; assert len(cases)==len(core)==18
    for row,case in zip(core,cases):
        accepted=case.get('accepted',True)
        wanted=dict(name=case['spec']['name'],operation=case['operation'],accepted=accepted,
                    before=case['before'],after=case['after'],restored=case['restored'])
        if accepted: wanted['redone']=case['after']
        compare_wire(wanted,row)
    assert {row['operation'] for row in core}==OPERATIONS
    assert set(linked)=={'linked','variations'}
    assert len(linked['linked'])==len(acceptance['linked'])==14
    for row,case in zip(linked['linked'],acceptance['linked']):
        compare_wire(dict(name=case['spec']['name'],operation=case['operation'],link=case['link'],
                          after=case['after'],restored=case['restored'],redone=case['after']),row)
    wanted=[dict(name=case['spec']['name'],step=i,after=step['after'])
            for case in acceptance['variations'] for i,step in enumerate(case['steps'])]
    assert len(wanted)==6
    compare_wire(wanted,linked['variations'])


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()



VERIFIED_HELPER_FILES=frozenset((
    'android/ci/check-drones.py','android/ci/drone_delivery.py',
    'android/ci/test_drone_runner.py','android/ci/test_drone_delivery.py',
    'docs/android/LOCAL-VERIFICATION.md','docs/android/tasks/C04-native-development-plan.md'))
VERIFIED_DOCUMENTATION_FILES=frozenset((
    'AGENTS.md','docs/android/ROADMAP.md','docs/android/STATUS.md',
    'docs/android/tasks/C04-native-development-plan.md'))
APK_OUTPUTS=('build/app/outputs/apk/debug/app-debug.apk',
             'build/app/outputs/apk/androidTest/debug/app-debug-androidTest.apk')


def source_binding(files):
    """Reuse the qualified inventory's ordinal path/NUL/hash/LF binding."""
    return hashlib.sha256(''.join(name+'\0'+files[name]+'\n' for name in sorted(files)).encode('utf-8')).hexdigest()


def verified_inputs(path,expected_sha256,root=None):
    """Validate an explicitly pinned development snapshot; never a clean commit."""
    if not __debug__: raise RuntimeError('Python optimization disables required verification assertions')
    root=Path(root) if root is not None else ROOT
    path=Path(path).resolve(strict=True)
    assert sha(path)==expected_sha256, 'Verified-input descriptor changed'
    descriptor=json.loads(path.read_text(encoding='utf-8'))
    version=descriptor.get('version')
    assert type(version) is int and version in (1,2), 'Unsupported verified-input version'
    fields={'version','source_manifest','qualification','apks','reviewed_changes'}
    assert set(descriptor)==fields|({'documentation_review'} if version==2 else set())
    def reference(ref):
        assert set(ref)=={'path','sha256'} and Path(ref['path']).is_absolute()
        file=Path(ref['path']).resolve(strict=True)
        assert sha(file)==ref['sha256'], 'Qualified receipt changed: '+str(file)
        return json.loads(file.read_text(encoding='utf-8'))
    source=reference(descriptor['source_manifest'])
    qualification=reference(descriptor['qualification'])
    candidate=source['candidate']; original=candidate['files']
    assert Path(candidate['root']).resolve()==root.resolve(), 'Qualified source root differs'
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=root,text=True,encoding='utf-8',timeout=10).rstrip('\r\n')
    assert git('rev-parse','HEAD')==candidate['head'], 'Qualified base HEAD differs'
    assert git('branch','--show-current')==candidate['branch'], 'Qualified branch differs'
    names=(set(git('ls-files','-z').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').split('\0')))-{''}
    assert names==set(original), 'Qualified source inventory changed'
    assert VERIFIED_HELPER_FILES<=names, 'Qualified helper inventory is incomplete'
    assert len({name.casefold() for name in names})==len(names), 'Ambiguous source paths'
    current={}
    for name in sorted(names):
        relative=Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and relative.as_posix()==name
        file=root/relative
        assert file.resolve(strict=True).is_relative_to(root.resolve()), 'Source escapes checkout'
        current[name]=sha(file)
    binding=source_binding(original)
    assert binding==source['candidate_sha256_map_binding']['sha256']==qualification['source_binding_sha256']
    assert qualification['maintained_source_files_verified']==len(original)
    assert qualification['maintained_source_changes']==[]
    assert qualification['status']=='ASSEMBLY_REUSED_FULL_LINT_AND_PACKAGE_PASS'
    changes=descriptor['reviewed_changes']
    actual={name for name in names if original[name]!=current[name]}
    eligible=VERIFIED_HELPER_FILES|(VERIFIED_DOCUMENTATION_FILES if version==2 else frozenset())
    assert set(changes)==actual and actual<=eligible, 'Unreviewed or non-helper source change'
    for name,row in changes.items():
        assert row==dict(before=original[name],after=current[name]), 'Reviewed helper hashes differ: '+name
    executing_binding=source_binding(current)
    if version==2:
        review=reference(descriptor['documentation_review'])
        assert set(review)=={'version','source_manifest','qualified_source_binding_sha256',
            'executing_source_binding_sha256','reviewed_changes','review_notes'}, 'Documentation review schema differs'
        assert type(review['version']) is int and review['version']==1
        assert review['source_manifest']==descriptor['source_manifest'], 'Documentation review source differs'
        assert review['qualified_source_binding_sha256']==binding, 'Documentation review build binding differs'
        assert review['executing_source_binding_sha256']==executing_binding, 'Documentation review executing binding differs'
        documents=actual&VERIFIED_DOCUMENTATION_FILES
        assert documents and set(review['reviewed_changes'])==set(review['review_notes'])==documents, \
            'Documentation review must cover exactly the changed control documents'
        for name in documents:
            assert review['reviewed_changes'][name]==changes[name], 'Documentation review hashes differ: '+name
            assert isinstance(review['review_notes'][name],str) and review['review_notes'][name].strip(), \
                'Documentation review rationale missing: '+name
    for phase,status in (('lint','ASSEMBLY_REUSED_LINT_AND_CLOSURE_PASS'),('package','APK_QUALIFICATION_PASS')):
        row=qualification[phase]
        assert row['status']==status and row['exit_code']==0, 'Qualification phase did not pass'
        if phase=='lint': assert row['errors']==row['fatals']==0
        proof=reference(dict(path=row['receipt'],sha256=row['receipt_sha256']))
        assert proof['status']==status
    assert set(descriptor['apks'])=={'app','test'}
    apks={}
    for label,output in zip(('app','test'),APK_OUTPUTS):
        file=Path(descriptor['apks'][label]); assert file.is_absolute()
        file=file.resolve(strict=True); expected=qualification['outputs'][output]
        observed=dict(bytes=file.stat().st_size,sha256=sha(file))
        assert observed==expected, 'Qualified APK changed: '+label
        apks[label]=dict(path=str(file),**observed)
    return dict(mode='verified-snapshot',descriptor=dict(path=str(path),sha256=expected_sha256),
        base_commit=candidate['head'],branch=candidate['branch'],qualified_git_status=candidate['status'],
        git_status=git('status','--porcelain'),qualified_source_binding_sha256=binding,
        executing_source_binding_sha256=executing_binding,reviewed_changes=changes,
        helper_sha256={name:current[name] for name in sorted(VERIFIED_HELPER_FILES) if name in current},apks=apks,
        **(dict(documentation_review=descriptor['documentation_review']) if version==2 else {}))


def validate_conservation_rows(rows,expected):
    assert len(rows)==len(expected['cases'])==14
    for row,case in zip(rows,expected['cases']):
        wanted=dict(name=case['spec']['name'],operation=case['operation'],accepted=case['accepted'],
                    before=case['before'],after=case['after'],restored=case['before'])
        if case['accepted']: wanted['redone']=case['after']
        compare_wire(wanted,row)


def validate_conservation_native(directory):
    require_decision(); directory=Path(directory)
    before=json.loads((directory/'c04-conservation-observed.json').read_text(encoding='utf-8'))
    after=json.loads((directory/'c04-conservation-restored.json').read_text(encoding='utf-8'))
    expected=json.loads((FIXTURES/'drone-conservation.json').read_text(encoding='utf-8'))
    validate_conservation_rows(before['cases'],expected)
    assert before['pid']!=after['pid'] and before['pid']==after['prior_pid']
    assert before['runtime']['session_id']!=after['runtime']['session_id']
    assert after['runtime']['persistence']['opened_existing'] is True
    compare_wire(before['graph'],after['graph']);compare_wire(before['details'],after['details'])
    assert len(before['graph']['records'])==len(before['details'])==14
    assert set(before['graph']['records'])==set(before['details'])
    all_ids=set()
    for record in before['graph']['records'].values():
        ids=record['inspection_ids']['drones']
        assert len(ids)==len(set(ids))==len(record['spec']['drones']) and not all_ids.intersection(ids)
        all_ids.update(ids)
    for case in expected['cases']:
        record=next(r for r in before['graph']['records'].values() if r['spec']['name']==case['spec']['name'])
        compare_wire(case['after_rows'],record['spec']['drones'])
    return dict(cases=14,reopened_fits=14,policy=expected['policy'])


def validate_conservation_acceptance(run,state=None):
    run=Path(run);require_decision()
    if state is None:state=json.loads((run/'run.json').read_text(encoding='utf-8'))
    latest={r['gate']:r for r in state.get('attempts',[])}
    required=('reference:drone_conservation','headless:drone_conservation',NATIVE_GATE)
    assert all(g in latest and latest[g].get('exit_code')==0 for g in required), 'Missing completed conservation gate'
    for gate in required:
        row=latest[gate]
        assert row.get('tested_commit')==state['commit'], 'Conservation inputs differ from candidate'
        assert sha(run/row['log'])==row['log_sha256']
    for gate in required[:2]:
        command=latest[gate]['command'];directory=Path(command[command.index('--output')+1]).resolve()
        assert directory.is_relative_to(run.resolve())
        proof=json.loads((directory/'evidence.json').read_text(encoding='utf-8'))
        assert proof['reference_sha256' if gate.startswith('headless') else 'fixture_sha256']==sha(FIXTURES/'drone-conservation.json')
        if gate.startswith('headless'):
            assert proof['policy']==require_decision() and len(proof['cases'])==18 and proof['invalid_cases']>=14
            assert proof['fresh_process']==dict(matched=True,stores=18)
            assert proof['history']['operations']==['merge_drones','split_drone']
    return validate_conservation_native(run/'native/c04')


def validate_native(directory,commit=None,*,verified_inputs_sha256=None):
    directory=Path(directory)
    result=json.loads((directory/'result.json').read_text(encoding='utf-8'))
    inputs=json.loads((directory/'inputs.json').read_text(encoding='utf-8'))
    mode=inputs.get('input_mode','clean-git')
    assert mode in ('clean-git','verified-snapshot') and result.get('input_mode','clean-git')==mode
    provenance=inputs.get('source_provenance')
    if mode=='verified-snapshot':
        assert verified_inputs_sha256 is not None, 'Snapshot development proof cannot enter full delivery'
        assert inputs['commit'] is None and commit is None, 'Snapshot is not an exact tested commit'
        assert provenance['descriptor']['sha256']==verified_inputs_sha256
        assert provenance==verified_inputs(provenance['descriptor']['path'],verified_inputs_sha256)
    else:
        assert provenance is None and verified_inputs_sha256 is None, 'Snapshot provenance requires explicit mode'
        if commit is not None: assert inputs['commit']==commit
    assert result['development_only'] is True and result['full_delivery'] is False
    assert result['native_executions']==sum(len(methods) for _,methods in PHASES.values())==11
    assert [row['phase'] for row in result['phases']]==list(PHASES)
    actual={p.name for p in directory.iterdir() if p.is_file()}-{'result.json'}
    assert set(result['files'])==actual
    for name,digest in result['files'].items():
        assert Path(name).name==name and sha(directory/name)==digest,name
    assert set(inputs['fixtures'])==set(REFERENCE_FILES.values())
    for name,digest in inputs['fixtures'].items(): assert sha(FIXTURES/name)==digest,name
    spec=importlib.util.spec_from_file_location('c04_runner_validation',ROOT/'android/ci/check-drones.py')
    runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    for row,(phase,(cls,methods)) in zip(result['phases'],PHASES.items()):
        assert row['tests']==len(methods)
        runner.passed((directory/(phase+'.log')).read_text(encoding='utf-8'),{'io.github.sussic.pyfa.'+cls+'#'+m for m in methods})
    load=lambda name:json.loads((directory/name).read_text(encoding='utf-8'))
    validate_observations(load('c04-core-observed.json'),load('c04-linked-observed.json'),
        json.loads((FIXTURES/'drone-core-edits.json').read_text()),json.loads((FIXTURES/'drone-acceptance.json').read_text()))
    conservation=validate_conservation_native(directory)
    before=load('c04-restart-witness.json'); restored=load('c04-restored-receipt.json')
    assert before['pid']!=restored['pid'] and before['pid']==restored['prior_pid']
    assert before['runtime']['session_id']!=restored['runtime']['session_id']
    assert restored['runtime']['persistence']['opened_existing'] is True
    assert restored['fits']==len(before['details'])==8
    compare_wire(before['graph'],restored['graph']); compare_wire(before['details'],restored['details'])
    original=json.loads((FIXTURES/'drone-details.json').read_text())
    records=before['graph']['records']; all_ids=set()
    for record in records.values():
        ids=record['inspection_ids']['drones']; assert len(ids)==len(set(ids))==16
        assert not all_ids.intersection(ids); all_ids.update(ids)
    for case in original['cases']:
        key,record=next((key,record) for key,record in records.items() if record['spec']['name']==case['spec']['name'])
        rows=before['details'][key]['stacks']; assert len(rows)==16
        for expected,row in zip(case['stacks'],rows[:15]):
            for field in ('item_id','name','amount','active'): compare_wire(expected[field],row[field])
            metrics={metric['key']:metric['value'] for metric in row['metrics']}
            assert len(metrics)==len(row['metrics'])==47
            compare_wire(expected['metrics'],metrics)
    for name in SCREENSHOTS:
        raw=(directory/name).read_bytes(); assert raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw)>1000
    return dict(tested_commit=inputs['commit'],native_executions=11,core_cases=18,linked_cases=14,
                variation_steps=6,conservation=conservation,original_detail_stacks=60,reopened_fits=8,screenshots=list(SCREENSHOTS),
                split_merge='conservation-native-verified',full_delivery=False,
                **(dict(source_provenance=provenance) if mode=='verified-snapshot' else {}))


def is_emulator_data(directory,path):
    import re
    first=Path(path).relative_to(directory).parts[0]
    return first=='avd' or re.fullmatch(r'avd-(?:c04-)?r[0-9]+',first) is not None


def avd_identity(directory,restart):
    """Every explicit native retry owns a fresh C04 AVD; prior data stays intact."""
    assert type(restart) is int and restart>=0
    directory=Path(directory)
    return (directory/f'avd-c04-r{restart}',
            'pyfa-local-'+directory.name.replace('.','-')+f'-r{restart}-c04')


def run_native(run):
    # Keep inherited app data/evidence in its existing AVD. C04 owns a second,
    # freshly created disposable AVD, sequentially, with no app-data overwrite.
    run.stop_emulator(); admit_native(); run.start_emulator(suffix='-c04')
    retry=len(run.state.get('native_restarts',[]))
    seed=run.directory/f'c04-seed-r{retry}'; evidence=run.native/'c04'
    run.execute('environment:c04-seed',[sys.executable,'-I','-B',ROOT/'android/ci/prepare-drone-seed.py',
                '--database',ROOT/'android/build/engine/assets/engine/eve.db','--output',seed])
    conservation_seed=run.directory/f'c04-conservation-seed-r{retry}'
    run.execute('environment:c04-conservation-seed',[sys.executable,'-I','-B',ROOT/'android/ci/prepare-drone-seed.py',
                '--database',ROOT/'android/build/engine/assets/engine/eve.db','--family','conservation','--output',conservation_seed])
    run.execute(NATIVE_GATE,[sys.executable,'-I','-B',ROOT/'android/ci/check-drones.py',
        '--serial',run.serial,'--avd',run.state['avd_name'],'--seed',seed,'--conservation-seed',conservation_seed,'--evidence',evidence,'--heavy-slot-released'],timeout=6300)
    checked=validate_native(evidence,run.state['commit'])
    (run.native/'c04-summary.json').write_text(json.dumps(checked,indent=2)+'\n',encoding='utf-8')
    for name in SCREENSHOTS: shutil.copyfile(evidence/name,run.native/('c04-'+name))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--accept-conservation',type=Path,required=True)
    print(json.dumps(validate_conservation_acceptance(parser.parse_args().accept_conservation)))
