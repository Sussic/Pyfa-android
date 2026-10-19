"""Focused C04 native development proof; never a replacement for full verification.

Requires an explicitly released heavy slot, a new dedicated API36 x86_64 AVD,
fresh debug APKs and a synthetic seed. Does not build, start emulators or install
SDK components. Refuses existing app installations and existing evidence paths.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import zipfile

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from drone_delivery import admit_native, validate_native, REFERENCE_FILES

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'io.github.sussic.pyfa.dev'
PREFIX = 'io.github.sussic.pyfa.'


def passed(output, expected):
    assert not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=|INSTRUMENTATION_ABORTED', output), output[-6000:]
    assert re.search(r'^OK \(' + str(len(expected)) + r' tests?\)\s*$', output, re.M), output[-6000:]
    assert re.findall(r'^INSTRUMENTATION_CODE: (-?\d+)\s*$', output, re.M) == ['-1']
    fields = {}; started = set(); completed = set()
    for line in output.splitlines():
        if line.startswith('INSTRUMENTATION_STATUS: '):
            key, sep, value = line[len('INSTRUMENTATION_STATUS: '):].partition('=')
            if sep: fields[key] = value
        elif line.startswith('INSTRUMENTATION_STATUS_CODE: '):
            code = int(line.split(': ', 1)[1])
            assert code in (0, 1), fields
            assert fields.get('numtests') == str(len(expected))
            name = fields['class'] + '#' + fields['test']
            assert name in expected and name not in completed
            if code == 1:
                assert name not in started
                started.add(name)
            else:
                assert name in started
                completed.add(name)
            fields = {}
    assert started == completed == expected


class OfflineStateError(RuntimeError):
    """Required current Android state is missing, unknown or still online."""


def offline_state(airplane, wifi, connectivity):
    """Prove networking unavailable (DEVELOPMENT.md offline requirement).

    Android 16 DataSettingsManager enable flags are preferences/policy, not
    connectivity: they do not test airplane mode, radio power or registration.
    Telephony dumps remain diagnostics. Gate on current effective network state;
    command success or a stored preference alone never proves offline operation.
    """
    airplane, wifi, connectivity = (value.replace('\r\n', '\n')
                                    for value in (airplane, wifi, connectivity))
    def require(condition, message):
        if not condition:
            raise OfflineStateError(message)
    require(airplane.strip() == '1', 'Airplane mode is not confirmed enabled')
    require(re.findall(r'^Wifi is (\S+)\s*$', wifi, re.M) == ['disabled'],
            'Wi-Fi is not confirmed disabled')
    require(re.findall(r'^Active default network: (\S+)[ \t]*$', connectivity, re.M) == ['none'],
            'A default network exists or its state is unknown')
    require(not re.search(r'DUMP TIMEOUT|Failure while dumping|Error dumping service|'
                          r'Exception occurred while dumping|Failed to dump', connectivity, re.I),
            'Connectivity dump reported a timeout/failure')
    networks = re.findall(r'^Current Networks:[ \t]*\n(.*?)^Status for known UIDs:[ \t]*$',
                          connectivity, re.M | re.S)
    require(len(re.findall(r'^Current Networks:[ \t]*$', connectivity, re.M)) == 1 and
            len(re.findall(r'^Status for known UIDs:[ \t]*$', connectivity, re.M)) == 1 and
            len(networks) == 1 and not networks[0].strip(),
            'Current networks remain or the connectivity dump is incomplete')
    return dict(airplane_mode_on=True, wifi_disabled=True, networking_unavailable=True,
                active_default_network=None, current_networks=[])


def require_offline(command, *, clock=time.monotonic, sleep=time.sleep, seconds=120):
    """Set and prove offline state within one bounded prerequisite deadline.

    command(label, *adb_arguments, timeout=...) must retain stdout/stderr and
    reject nonzero exit codes. No mobile-data bypass for a missing phone service.
    Failure diagnostics have a separate, shared 20-second cap and never authorize
    installation or instrumentation. All labels are unique for this invocation.
    """
    began = clock(); deadline = began + seconds; attempt = 0
    def run(label, *args):
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError('Offline prerequisite deadline expired (phone/mobile data remain required)')
        result = command(label, *args, timeout=min(20, remaining))
        if clock() >= deadline:
            raise TimeoutError('Offline prerequisite response exceeded its deadline')
        return result
    try:
        features = run('offline-features', 'shell', 'pm', 'list', 'features')
        if 'feature:android.hardware.telephony.data' not in features.splitlines():
            raise OfflineStateError('Configured emulator does not advertise telephony data; no bypass is permitted')
        while True:
            phone = run('offline-phone-ready-' + str(attempt), 'shell', 'service', 'check', 'phone').strip()
            attempt += 1
            if phone == 'Service phone: found':
                break
            if phone != 'Service phone: not found':
                raise OfflineStateError('Unrecognised phone service readiness response: ' + phone)
            sleep(min(1, max(0, deadline - clock())))
        run('offline-airplane', 'shell', 'cmd', 'connectivity', 'airplane-mode', 'enable')
        run('offline-wifi', 'shell', 'svc', 'wifi', 'disable')
        run('offline-data', 'shell', 'svc', 'data', 'disable')
        # Preserve platform preference evidence once, without making it an
        # acceptance condition. Even a complete dump's enabled=true is compatible
        # with airplane mode/radio off; missing diagnostics cannot prove offline.
        diagnostic_error = None
        try:
            remaining = deadline - clock()
            if remaining > 0:
                command('offline-telephony-diagnostic', 'shell', 'dumpsys', '-t', '5',
                        'activity', 'service', 'com.android.phone/.TelephonyDebugService',
                        timeout=min(7, remaining))
        except Exception as error:
            diagnostic_error = type(error).__name__ + ': ' + str(error)
        readiness_polls = attempt
        attempt = 0; last_error = None
        while True:
            values = [run('offline-state-' + str(attempt) + '-' + label, *args) for label, args in (
                ('airplane', ('shell', 'settings', 'get', 'global', 'airplane_mode_on')),
                ('wifi', ('shell', 'cmd', 'wifi', 'status')),
                ('connectivity', ('shell', 'dumpsys', '-t', '5', 'connectivity')))]
            try:
                result = offline_state(*values)
                return dict(result, seconds=round(clock()-began, 3), readiness_polls=readiness_polls,
                            state_polls=attempt + 1, mobile_data_disable_command_exit=0,
                            telephony_diagnostic_log='offline-telephony-diagnostic.log',
                            telephony_diagnostic_error=diagnostic_error,
                            telephony_preferences_are_offline_requirement=False)
            except OfflineStateError as error:
                last_error = error
            attempt += 1
            if clock() + 1 >= deadline:
                raise OfflineStateError('Offline state did not settle: ' + str(last_error))
            sleep(1)
    except Exception:
        diagnostic_deadline = clock() + 20
        for label, args in (
            ('services', ('shell', 'service', 'list')),
            ('phone', ('shell', 'dumpsys', '-t', '5', 'phone')),
            ('logcat', ('shell', 'logcat', '-b', 'all', '-d', '-t', '300'))):
            remaining = diagnostic_deadline - clock()
            if remaining <= 0:
                break
            try:
                command('offline-failure-' + label, *args, timeout=min(7, remaining))
            except Exception:
                pass  # Preserve the prerequisite failure; diagnostics never turn it into a pass.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--avd', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--conservation-seed',type=Path,required=True)
    parser.add_argument('--heavy-slot-released', action='store_true', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'emulator-\d+', args.serial)
    assert re.fullmatch(r'(?:pyfa-c04-[a-zA-Z0-9-]+|pyfa-local-[a-zA-Z0-9-]+-c04)', args.avd)
    admission = admit_native()
    evidence = args.evidence.resolve()
    assert not evidence.exists() and not evidence.is_relative_to(ROOT.parent)
    seed = args.seed.resolve(strict=True)
    metadata = json.loads((seed / 'seed.json').read_text())
    seed_bytes = (seed / 'graph.sqlite3').read_bytes()
    assert metadata['synthetic_inputs_only'] is True
    assert hashlib.sha256(seed_bytes).hexdigest() == metadata['graph_sha256']
    conservation_seed=args.conservation_seed.resolve(strict=True)
    conservation_metadata=json.loads((conservation_seed/'seed.json').read_text())
    conservation_bytes=(conservation_seed/'graph.sqlite3').read_bytes()
    assert conservation_metadata['synthetic_inputs_only'] is True
    assert hashlib.sha256(conservation_bytes).hexdigest()==conservation_metadata['graph_sha256']
    assert hashlib.sha256((ROOT.parent/'tools/android_reference/fixtures/drone-conservation.json').read_bytes()).hexdigest()==conservation_metadata['reference_sha256']
    expected_file = ROOT.parent / 'tools/android_reference/fixtures/drone-details.json'
    assert hashlib.sha256(expected_file.read_bytes()).hexdigest() == metadata['reference_sha256']
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT.parent, text=True).strip(), 'Commit the reviewed candidate first'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT.parent, text=True).strip()
    apks = [ROOT / 'app/build/outputs/apk/debug/app-debug.apk',
            ROOT / 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk']
    assert all(path.is_file() for path in apks)
    with zipfile.ZipFile(apks[0]) as archive:
        manifest = json.loads(archive.read('assets/engine/manifest.json'))
        for relative, digest in manifest['engine_sources'].items():
            assert hashlib.sha256((ROOT.parent / relative).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == digest, relative
    fixtures = {name: hashlib.sha256((ROOT.parent/'tools/android_reference/fixtures'/name).read_bytes()).hexdigest()
                for name in REFERENCE_FILES.values()}
    with zipfile.ZipFile(apks[1]) as archive:
        for name, digest in fixtures.items():
            assert hashlib.sha256(archive.read('assets/'+name.replace('.json','-expected.json'))).hexdigest() == digest
    evidence.mkdir(parents=True)
    receipts = []
    def adb(*arguments, data=None, timeout=120):
        return subprocess.run(['adb', '-s', args.serial, *arguments], input=data,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=timeout).stdout
    def text(*arguments): return adb(*arguments).decode().strip()
    assert text('emu', 'avd', 'name').splitlines()[0] == args.avd
    assert text('shell', 'getprop', 'ro.kernel.qemu') == '1'
    assert text('shell', 'getprop', 'ro.build.version.sdk') == '36'
    assert text('shell', 'getprop', 'ro.product.cpu.abi') == 'x86_64'
    for package in (PACKAGE, PACKAGE + '.test'):
        assert not text('shell', 'pm', 'path', package), 'Refusing an existing installation'
    def offline_command(label, *arguments, timeout):
        try:
            result = subprocess.run(['adb', '-s', args.serial, *arguments],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            (evidence / (label + '.log')).write_bytes((error.stdout or b'') + b'\n' + (error.stderr or b''))
            raise
        (evidence / (label + '.log')).write_bytes(result.stdout + b'\n' + result.stderr)
        result.check_returncode()
        return result.stdout.decode(errors='replace')
    offline = require_offline(offline_command)
    (evidence / 'offline-proof.json').write_text(json.dumps(offline, indent=2) + '\n')
    def install():
        for apk in apks: assert 'Success' in text('install', '-t', str(apk))
    def run(label, cls, methods, phase=None):
        text('shell', 'am', 'force-stop', PACKAGE)
        target = PREFIX + cls + ('#' + methods[0] if len(methods) == 1 else '')
        command = ['shell', 'am', 'instrument', '-w', '-r', '-e', 'class', target]
        command += ['-e', 'c04_phase', phase or label]
        command += [PACKAGE + '.test/' + PREFIX + 'DiagnosticTestRunner']
        began = time.monotonic()
        result = subprocess.run(['adb', '-s', args.serial, *command], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=900)
        (evidence / (label + '.log')).write_bytes(result.stdout)
        result.check_returncode()
        passed(result.stdout.decode(errors='replace'), {PREFIX + cls + '#' + method for method in methods})
        receipts.append(dict(phase=label, tests=len(methods), seconds=time.monotonic()-began))
    def private(name):
        raw = adb('exec-out', 'run-as', PACKAGE, 'cat', 'no_backup/' + name)
        json.loads(raw)
        (evidence / name).write_bytes(raw)
    def screen(name):
        raw = adb('exec-out', 'cat', '/sdcard/Download/pyfa-c04-' + name + '.png')
        assert raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) > 1000
        (evidence / (name + '.png')).write_bytes(raw)
    (evidence / 'inputs.json').write_text(json.dumps(dict(commit=commit, avd=args.avd, serial=args.serial,
        fingerprint=text('shell', 'getprop', 'ro.build.fingerprint'), seed=metadata, conservation_seed=conservation_metadata, fixtures=fixtures, admission=admission,
        apk_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in apks}), indent=2))
    install()
    run('contract', 'DroneContractTest', ['exactDetailsContractRejectsLostFieldsUnitsIdentityAndCounts',
        'queuedSelectionsAreIndependentOfCallerMutation', 'eightOperationsEncodePreciselyAndPermitMainOnlyToggle'])
    run('fresh-ui', 'DroneUiTest', ['cargoBrowseReturnsToDronesAndEditsSurviveRecreation'])
    private('c04-ui-receipt.json')
    screen('selected-over-limit'); screen('empty-after-redo'); screen('ordinary-variation'); screen('conserved-split-merge')
    run('core', 'DroneMatrixTest', ['originalCoreCommandsAndHullBoundariesOffline'])
    private('c04-core-observed.json')
    run('linked', 'DroneMatrixTest', ['originalLinkedRecipientsAndOrdinaryVariationsOffline'])
    private('c04-linked-observed.json')
    for package in (PACKAGE + '.test', PACKAGE): assert 'Success' in text('uninstall', package)
    install()
    adb('shell', "run-as " + PACKAGE + " sh -c 'mkdir -p no_backup/fits && cat > no_backup/fits/graph.sqlite3'",data=conservation_bytes)
    assert adb('exec-out','run-as',PACKAGE,'cat','no_backup/fits/graph.sqlite3')==conservation_bytes
    method=['approvedConservationAndRestartOffline']
    run('conservation','DroneMatrixTest',method,'conservation'); private('c04-conservation-observed.json')
    run('conservation-restored','DroneMatrixTest',method,'conservation-restored'); private('c04-conservation-restored.json')
    # Only this runner's newly installed synthetic test app is reset. Evidence
    # is retained first. A failed run leaves all artifacts and app data intact.
    for package in (PACKAGE + '.test', PACKAGE): assert 'Success' in text('uninstall', package)
    install()
    adb('shell', "run-as " + PACKAGE + " sh -c 'mkdir -p no_backup/fits && cat > no_backup/fits/graph.sqlite3'", data=seed_bytes)
    assert adb('exec-out', 'run-as', PACKAGE, 'cat', 'no_backup/fits/graph.sqlite3') == seed_bytes
    method = ['originalDetailsMutationHistoryAtomicityAndRestartOffline']
    run('prepare', 'DroneAcceptanceTest', method, 'prepare'); private('c04-restart-witness.json')
    run('restored', 'DroneAcceptanceTest', method, 'restored'); private('c04-restored-receipt.json')
    run('mutation-ui', 'DroneUiTest', ['restoredMutationsShowDetailsAndRetainSeparateIdentities'])
    screen('existing-roll-details')
    report = dict(development_only=True, native_executions=sum(row['tests'] for row in receipts), phases=receipts,
                  screenshot_review='pending', full_delivery=False,
                  files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence.iterdir() if p.is_file()})
    (evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    checked = validate_native(evidence, commit)
    print(json.dumps(checked))


if __name__ == '__main__':
    main()
