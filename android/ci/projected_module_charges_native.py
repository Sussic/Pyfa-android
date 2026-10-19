"""Supplemental D01.9 phase, called by the existing native_suite owner.
No standalone execution, provisioning or resource manager. Run.execute and the
outer r12 guard retain admission, ownership, budgets and teardown responsibility.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
PHASE = 'projected_module_charges'
PREFIX = 'io.github.sussic.pyfa.'
PACKAGE = PREFIX + 'dev'
METHODS = {'ProjectedModuleChargeContractTest': ('orderedPreviewIsImmutableAndOperationSnapshotsAllThreeCollections', 'malformedEnvelopesAndUnreviewedOperationListsAreRejected', 'exactCaptureRejectsStaleRowsAndReadOnlyScopeCannotBecomeApplicable'), 'ProjectedModuleChargeModelTest': ('explicitRefreshCapturesSelectionOrderAndDispatchesOnlyConfirmedOrderedChangesOnce', 'oneHeldReadGateDropsEveryObsoleteScopeMainSelectionDraftNavigationAndEditReply', 'harmlessFailureMalformedReplyAndUnavailableStatesRetainInputsUntilExplicitReview', 'zeroChangeAndReadOnlyScopeCannotApplyAndRawRangeDraftIsNeverDiscarded'), 'ProjectedModuleChargeUiTest': ('selectedAndSimilarScriptsPreviewExactSkipsHaveRealEffectsAndOneUndo', 'recreationNavigationRetainsInputsAndRangeDraftStaleDeletionRequireReview')}


def require(condition, message):
    if not condition: raise ValueError(message)


def selectors(cls):
    return tuple(PREFIX+cls+'#'+method for method in METHODS[cls])


def instrumentation_args(cls):
    return ('shell','am','instrument','-w','-r','-e','class',','.join(selectors(cls)),
            '-e','offline_features_phase',PHASE,PACKAGE+'.test/'+PREFIX+'DiagnosticTestRunner')


def helpers():
    spec=importlib.util.spec_from_file_location('projected_charge_helpers',Path(__file__).with_name('check-drones.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def validate_output(cls, output):
    require(__debug__, 'Python optimization disables required instrumentation assertions')
    helpers().passed(output,set(selectors(cls)))
    require(len(re.findall(r'^OK \(\d+ tests?\)\s*$',output,re.M))==1,'Duplicate instrumentation completion')


def run(command, evidence, expected_avd, apks, install):
    """Reuse the caller's owned serial transport, bounded execution and APK setup."""
    require(__debug__, 'Python optimization disables required instrumentation assertions')
    require(re.fullmatch(r'pyfa-local-[A-Za-z0-9-]+-c04',expected_avd) is not None,'Owned C04 profile required')
    evidence=Path(evidence)
    require(not evidence.exists(),'Retain existing phase evidence; use a fresh run')
    require(len(apks)==2 and all(Path(p).is_file() for p in apks),'Source-bound APK setup missing')
    hashes={package:hashlib.sha256(Path(apk).read_bytes()).hexdigest()
            for package,apk in zip((PACKAGE,PACKAGE+'.test'),apks)}
    evidence.mkdir(parents=True)
    require(command('identity-avd','emu','avd','name').splitlines()[0]==expected_avd,'Wrong owned AVD')
    for label,prop,expected in (('qemu','ro.kernel.qemu','1'),('api','ro.build.version.sdk','36'),('abi','ro.product.cpu.abi','x86_64')):
        require(command('identity-'+label,'shell','getprop',prop).strip()==expected,'Wrong emulator '+label)
    for package in hashes:
        require('package:'+package not in command('prior-'+package,'shell','pm','list','packages',package).splitlines(),
                'Refusing existing installation; preserve its app data')
    offline=helpers().require_offline(command)
    install()
    for package,expected in hashes.items():
        paths=command('installed-'+package,'shell','pm','path',package).splitlines()
        require(len(paths)==1 and re.fullmatch(r'package:/data/app/[A-Za-z0-9_./=+~-]+\.apk',paths[0]),'Unexpected APK path')
        actual=command('apk-hash-'+package,'shell','sha256sum',paths[0][8:]).split()
        require(len(actual)==2 and actual[0]==expected,'Installed APK differs from built input')
        require(command('internet-'+package,'shell','cmd','package','check-permission',
                        'android.permission.INTERNET',package,'0').strip()=='denied','INTERNET not confirmed denied')
    phases=[]
    for cls in METHODS:
        output=command(cls,*instrumentation_args(cls),timeout=900)
        validate_output(cls,output)
        phases.append({'class':cls,'methods':list(selectors(cls)),
                       'output_sha256':hashlib.sha256(output.encode()).hexdigest()})
    result={'phase':PHASE,'native_executions':9,'phases':phases,'offline':offline,'apk_sha256':hashes,
            'development_only':True,'full_delivery':False,'restart_qualified':False,
            'screenshots_reviewed':False,'other_cloud_native_gates_complete':False}
    (evidence/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
