"""The same offline native gates on Windows and Linux; never target a phone."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from evidence_paths import evidence_dir

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'io.github.sussic.pyfa.dev'
CHECKS = ['measure-performance.py', 'check-contract.py', 'check-persistence.py',
    'check-library.py', 'check-navigation.py', 'check-market.py', 'check-empty-hulls.py',
    'check-module-edits.py', 'check-charge-edits.py', 'check-variation-edits.py',
    'check-rack-ordering.py', 'check-bulk-charges.py', 'check-bulk-states.py',
    'check-clone-fill.py', 'check-bulk-variation-removal.py', 'check-hull-modes.py',
    'check-subsystems.py', 'check-structures.py', 'check-cargo-stacks.py',
    'check-cargo-actions.py', 'check-cargo-transfers.py', 'check-notes.py', 'check-history.py']
EXCLUDED = ['PerformanceTest', 'BridgeContractTest', 'PersistenceTest', 'FitLibraryTest',
    'LibraryNavigationTest', 'EquipmentBrowserTest', 'EmptyHullTest', 'ModuleEditingTest',
    'ChargeEditingTest', 'VariationEditingTest', 'RackOrderingTest', 'BulkChargesTest',
    'BulkStatesTest', 'CloneFillTest', 'BulkVariationRemovalTest', 'HullModeTest',
    'SubsystemTest', 'StructureServiceTest', 'CargoStackTest', 'CargoActionTest',
    'CargoTransferTest', 'NotesTest', 'EditHistoryTest']
STEPS = ['initial', *CHECKS, 'summary']


def adb(*args, binary=False):
    return subprocess.check_output(['adb', *args], timeout=120, text=not binary)


def initial(evidence):
    # ANDROID_SERIAL is supplied by the Windows AVD owner. Linux retains its one
    # disposable emulator. Refuse an attached physical device in either mode.
    assert adb('shell', 'getprop', 'ro.kernel.qemu').strip() == '1'
    assert adb('shell', 'getprop', 'ro.build.version.sdk').strip() == '36'
    assert adb('shell', 'getprop', 'ro.product.cpu.abi').strip() == 'x86_64'
    adb('shell', 'cmd', 'connectivity', 'airplane-mode', 'enable')
    adb('shell', 'svc', 'wifi', 'disable'); adb('shell', 'svc', 'data', 'disable')
    assert adb('shell', 'settings', 'get', 'global', 'airplane_mode_on').strip() == '1'
    prior = adb('shell', 'pm', 'list', 'packages', PACKAGE)
    (evidence / 'prior-install.txt').write_text(prior, encoding='utf-8')
    assert f'package:{PACKAGE}' not in prior.splitlines(), 'Require a fresh disposable AVD'
    for name, prop in [('fingerprint','ro.build.fingerprint'), ('abi','ro.product.cpu.abi'), ('api','ro.build.version.sdk')]:
        (evidence / f'device-{name}.txt').write_text(adb('shell','getprop',prop), encoding='utf-8')
    sdk = Path(os.environ['ANDROID_HOME'])
    shutil.copyfile(sdk / 'emulator/source.properties', evidence / 'emulator-version.txt')
    manager = os.environ.get('PYFA_SDKMANAGER', 'sdkmanager')
    (evidence / 'sdk-packages.txt').write_bytes(subprocess.check_output([manager, '--list_installed'], timeout=120))
    reports = ROOT / 'app/build/outputs/androidTest-results/connected'
    if reports.exists(): shutil.rmtree(reports)
    wrapper = str(ROOT / ('gradlew.bat' if os.name == 'nt' else 'gradlew'))
    command = [wrapper, '--no-daemon', '--console=plain', ':app:connectedDebugAndroidTest',
        '-Pandroid.testInstrumentationRunnerArguments.notClass=' + ','.join('io.github.sussic.pyfa.'+name for name in EXCLUDED)]
    subprocess.run(command, cwd=ROOT, check=True, timeout=480)
    for name in ('home','about','about-landscape','fit'):
        (evidence / f'{name}.png').write_bytes(adb('exec-out','cat',f'/sdcard/Download/pyfa-a07-{name}.png',binary=True))
    for name, source in [('engine','a07-engine'), ('projection','a08-projection'), ('command','a09-command')]:
        (evidence / f'{name}-native.json').write_bytes(adb('exec-out','cat',f'/sdcard/Download/pyfa-{source}.json',binary=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--step', choices=STEPS)
    args=parser.parse_args()
    evidence=evidence_dir()
    try:
        for step in ([args.step] if args.step else STEPS):
            print('Native gate: '+step, flush=True)
            if step=='initial': initial(evidence)
            else:
                assert adb('shell','getprop','ro.kernel.qemu').strip()=='1'
                assert adb('shell','settings','get','global','airplane_mode_on').strip()=='1'
                script='summarize-tests.py' if step=='summary' else step
                subprocess.run([sys.executable,str(ROOT/'ci'/script)],cwd=ROOT,check=True)
    except BaseException:
        for name, command in [('failure.png',('exec-out','screencap','-p')),
                              ('failure-logcat.txt',('logcat','-d','-t','300','AndroidRuntime:E','PyfaEngine:E','TestRunner:I','python.stderr:W','*:S'))]:
            try: (evidence/name).write_bytes(adb(*command,binary=True))
            except Exception: pass
        raise


if __name__=='__main__': main()
