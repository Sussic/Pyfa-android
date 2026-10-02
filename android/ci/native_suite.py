"""The same offline native gates on Windows and Linux; never target a phone."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
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
    'CargoTransferTest', 'NotesTest', 'EditHistoryTest', 'MutationHistoryTest', 'ResourceProbeTest', 'ResourcesTest', 'CapacitorTest']
MUTATION_STEPS = [f'mutation-history-{group}-{phase}' for group in range(4) for phase in ('prepare', 'restored')]
RESOURCE_STEPS = ['resources-'+phase for phase in ('probe','prepare','restored')]
CAPACITOR_STEPS = ['capacitor-'+phase for phase in ('prepare','restored')]
STEPS = ['initial', *CHECKS, *MUTATION_STEPS, *RESOURCE_STEPS, *CAPACITOR_STEPS, 'summary']
INITIAL_TESTS = {
    'io.github.sussic.pyfa.AppShellTest.offlineLaunchShowsHonestStatusAndNavigatesBack',
    'io.github.sussic.pyfa.AppShellTest.aboutSurvivesActivityRecreationAndLandscapeWithSystemBack',
    'io.github.sussic.pyfa.EngineParityTest.bundledEngineMatchesIndependentDesktopAmmunitionStatesOffline',
    'io.github.sussic.pyfa.EngineParityTest.projectedEffectsMatchDesktopAndRefreshAllRecipientsOffline',
    'io.github.sussic.pyfa.EngineParityTest.commandBurstsMatchDesktopAndClearRecipientBonusesOffline',
}


def initial_junit(output):
    """Translate actual AndroidJUnitRunner success events, rejecting incomplete runs."""
    assert not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=|INSTRUMENTATION_ABORTED', output), output[-6000:]
    assert re.search(r'^OK \(5 tests\)\s*$', output, re.M), output[-6000:]
    assert re.findall(r'^INSTRUMENTATION_CODE: (-?\d+)\s*$', output, re.M) == ['-1']
    fields = {}; started = {}; passed = set()
    for line in output.splitlines():
        if line.startswith('INSTRUMENTATION_STATUS: '):
            key, separator, value = line[len('INSTRUMENTATION_STATUS: '):].partition('=')
            if separator: fields[key] = value
        elif line.startswith('INSTRUMENTATION_STATUS_CODE: '):
            code = int(line.split(': ', 1)[1])
            assert code in (0, 1), fields
            assert fields.get('id') == 'AndroidJUnitRunner' and fields.get('numtests') == '5', fields
            name = fields['class'] + '.' + fields['test']
            assert name in INITIAL_TESTS, fields
            if code == 1:
                assert name not in started and name not in passed, fields
                started[name] = fields['current']
            else:
                assert name in started and name not in passed and fields['current'] == started[name], fields
                passed.add(name)
            fields = {}
    assert passed == INITIAL_TESTS and set(started.values()) == {'1', '2', '3', '4', '5'}
    suite = ET.Element('testsuite', name='Windows direct Android instrumentation', tests='5', failures='0', errors='0', skipped='0')
    for name in sorted(passed):
        classname, method = name.rsplit('.', 1)
        ET.SubElement(suite, 'testcase', classname=classname, name=method)
    return ET.tostring(suite, encoding='utf-8', xml_declaration=True)


def windows_initial(evidence, reports):
    # Bypass Windows UTP's failed host gRPC transport, not the device assertions.
    # Keep a fresh offline installation and the same post-test uninstall boundary.
    for relative in ('apk/debug/app-debug.apk', 'apk/androidTest/debug/app-debug-androidTest.apk'):
        result = adb('install', '-t', str(ROOT / 'app/build/outputs' / relative))
        assert 'Success' in result, result
    command = ['adb', 'shell', 'am', 'instrument', '-w', '-r', '-e', 'notClass',
        ','.join('io.github.sussic.pyfa.'+name for name in EXCLUDED),
        PACKAGE+'.test/io.github.sussic.pyfa.DiagnosticTestRunner']
    result = subprocess.run(command, capture_output=True, text=True, timeout=480)
    output = result.stdout + result.stderr
    (evidence / 'initial-instrumentation.txt').write_text(output, encoding='utf-8')
    result.check_returncode()
    xml = initial_junit(output)
    reports.mkdir(parents=True, exist_ok=True)
    (reports / 'TEST-windows-initial.xml').write_bytes(xml)
    for package in (PACKAGE, PACKAGE+'.test'):
        assert 'Success' in adb('uninstall', package)
    assert f'package:{PACKAGE}' not in adb('shell','pm','list','packages',PACKAGE).splitlines()


def adb(*args, binary=False):
    if os.name == 'nt' and args[:2] == ('exec-out', 'cat'):
        command = ['adb', *args]
        result = subprocess.run(command, capture_output=True, text=not binary, timeout=120)
        error = result.stderr.decode(errors='replace') if binary else result.stderr
        if result.returncode and error.strip() == 'error: device offline':
            print('Retained failed artifact read: '+error.strip(), flush=True)
            serial = os.environ['ANDROID_SERIAL']
            assert re.fullmatch(r'emulator-\d+', serial)
            subprocess.run(['adb', '-s', serial, 'reconnect'], check=True, timeout=30)
            subprocess.run(['adb', '-s', serial, 'wait-for-device'], check=True, timeout=120)
            def identity(*parts):
                return subprocess.check_output(['adb', '-s', serial, *parts], text=True, timeout=30).strip()
            assert identity('emu', 'avd', 'name').splitlines()[0] == 'pyfa-local-'+os.environ['PYFA_LOCAL_RUN_ID']
            assert identity('shell', 'getprop', 'ro.kernel.qemu') == '1'
            assert identity('shell', 'getprop', 'ro.build.version.sdk') == '36'
            assert identity('shell', 'settings', 'get', 'global', 'airplane_mode_on') == '1'
            print('Verified owned offline emulator; retrying artifact read once', flush=True)
            result = subprocess.run(command, capture_output=True, text=not binary, timeout=120)
        result.check_returncode()
        return result.stdout
    return subprocess.check_output(['adb', *args], timeout=120, text=not binary)


def initial(evidence):
    # ANDROID_SERIAL is supplied by the Windows AVD owner. Linux retains its one
    # disposable emulator. Refuse an attached physical device in either mode.
    assert adb('shell', 'getprop', 'ro.kernel.qemu').strip() == '1'
    assert adb('shell', 'getprop', 'ro.build.version.sdk').strip() == '36'
    assert adb('shell', 'getprop', 'ro.product.cpu.abi').strip() == 'x86_64'
    # A first boot can publish sys.boot_completed before the phone binder.
    # Require it instead of skipping the mobile-data offline command.
    deadline=time.monotonic()+120
    while 'Service phone: found' not in adb('shell','service','check','phone'):
        if time.monotonic()>=deadline: raise RuntimeError('Phone service did not become ready; mobile-data disable remains required')
        time.sleep(1)
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
    (evidence / 'sdk-packages.txt').write_bytes(subprocess.check_output([manager, '--sdk_root='+str(sdk), '--list_installed'], timeout=120))
    reports = ROOT / 'app/build/outputs/androidTest-results/connected'
    if reports.exists(): shutil.rmtree(reports)
    wrapper = str(ROOT / ('gradlew.bat' if os.name == 'nt' else 'gradlew'))
    command = [wrapper, '--no-daemon', '--console=plain', ':app:connectedDebugAndroidTest',
        '-Pandroid.testInstrumentationRunnerArguments.notClass=' + ','.join('io.github.sussic.pyfa.'+name for name in EXCLUDED)]
    if os.name == 'nt': windows_initial(evidence, reports)
    else: subprocess.run(command, cwd=ROOT, check=True, timeout=480)
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
                if step in MUTATION_STEPS:
                    _, _, group, phase = step.split('-')
                    command = [sys.executable, str(ROOT/'ci/check-mutation-history.py'), '--group', group, '--phase', phase]
                elif step in RESOURCE_STEPS:
                    command = [sys.executable, str(ROOT/'ci/check-resources.py'), '--phase', step.split('-')[1]]
                elif step in CAPACITOR_STEPS:
                    command = [sys.executable, str(ROOT/'ci/check-capacitor.py'), '--phase', step.split('-')[1]]
                else:
                    script='summarize-tests.py' if step=='summary' else step
                    command = [sys.executable, str(ROOT/'ci'/script)]
                subprocess.run(command,cwd=ROOT,check=True)
    except BaseException:
        for name, command in [('failure.png',('exec-out','screencap','-p')),
                              ('failure-logcat.txt',('logcat','-d','-t','300','AndroidRuntime:E','PyfaEngine:E','TestRunner:I','python.stderr:W','*:S'))]:
            try: (evidence/name).write_bytes(adb(*command,binary=True))
            except Exception: pass
        raise


if __name__=='__main__': main()
