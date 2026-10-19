"""Synthetic host wiring/refusal checks; no Android execution or native proof."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_verification
import native_suite
import remote_repair_native as phase
import projected_module_charges_native as projected_phase
import shield_regeneration_native as shield_phase

AVD = 'pyfa-local-host-fixture-c04'
OWNED = {'ANDROID_SERIAL': 'emulator-5554', 'PYFA_LOCAL_RUN_ID': 'host-fixture',
         'PYFA_BUDGET_JOB_NAME': 'Local\\PyfaBudget-host-fixture'}


def event(cls, method, current, code):
    return '\n'.join(('INSTRUMENTATION_STATUS: class=' + phase.PREFIX + cls,
                      'INSTRUMENTATION_STATUS: test=' + method,
                      'INSTRUMENTATION_STATUS: numtests=' + str(len(phase.METHODS[cls])),
                      'INSTRUMENTATION_STATUS: current=' + str(current),
                      'INSTRUMENTATION_STATUS_CODE: ' + str(code))) + '\n'


def output(cls):
    return ''.join(event(cls, method, current, code)
                   for current, method in enumerate(phase.METHODS[cls], 1)
                   for code in (1, 0)) + (
        'OK (' + str(len(phase.METHODS[cls])) + ' tests)\nINSTRUMENTATION_CODE: -1\n')


class Transport:
    """Only deterministic synthetic bytes and callbacks; never launches tools."""
    def __init__(self, test, root, fault=None):
        self.test, self.root, self.fault = test, root, fault
        self.evidence = root / 'evidence'
        self.apks = [root / 'app.apk', root / 'test.apk']
        for index, apk in enumerate(self.apks):
            apk.write_bytes(('synthetic-host-apk-' + str(index)).encode())
        self.hashes = {package: hashlib.sha256(apk.read_bytes()).hexdigest()
                       for package, apk in zip((phase.PACKAGE, phase.PACKAGE + '.test'), self.apks)}
        self.events, self.raw_logs = [], {}
        self.installed = self.offline = self.refused = False
        self.after_class = None

    def value(self, key, good, bad):
        if self.fault == key:
            self.refused = True
            return bad
        return good

    def command(self, label, *args, **kwargs):
        self.test.assertFalse(self.refused, 'A command ran after failed prerequisite')
        self.events.append(label)
        if label == 'identity-avd': return self.value('avd', AVD + '\nOK\n', 'another-avd\n')
        if label == 'identity-qemu': return self.value('qemu', '1\n', '0\n')
        if label == 'identity-api': return self.value('api', '36\n', '35\n')
        if label == 'identity-abi': return self.value('abi', 'x86_64\n', 'arm64-v8a\n')
        if label.startswith('prior-'):
            self.test.assertEqual(args[:4], ('shell', 'pm', 'list', 'packages'))
            return self.value('existing', '', 'package:' + args[-1] + '\n')
        self.test.assertTrue(self.installed)
        if label.startswith('installed-'):
            return self.value('path', 'package:/data/app/host-fixture/base.apk\n', 'package:/unexpected.apk\n')
        if label.startswith('apk-hash-'):
            digest = self.hashes[label.removeprefix('apk-hash-')]
            return self.value('hash', digest, '0' * 64) + '  /data/app/host-fixture/base.apk\n'
        if label.startswith('internet-'): return self.value('internet', 'denied\n', 'granted\n')
        if label in phase.METHODS:
            self.test.assertEqual(args, phase.instrumentation_args(label))
            self.test.assertEqual(kwargs, {'timeout': 900})
            # Invalid UTF-8 and CRLF ensure the receipt hashes raw bytes, not a
            # replacement-character encoding or newline-normalized string.
            raw = b'host-only diagnostic \xff\r\n' + output(label).encode()
            self.raw_logs[label] = raw
            if self.fault != 'missing-log':
                (self.evidence / (label + '.log')).write_bytes(
                    raw + b'mismatch' if self.fault == 'mismatched-log' else raw)
            if self.after_class: self.after_class(label)
            return raw.decode('utf-8', errors='replace')
        self.test.fail('Unexpected synthetic command: ' + label)

    def prove_offline(self, command):
        self.test.assertEqual(command, self.command)
        self.events.append('offline')
        if self.fault == 'offline': raise ValueError('Synthetic offline refusal')
        self.offline = True
        return {'synthetic_host_fixture_only': True}

    def install(self):
        self.test.assertTrue(self.offline)
        self.test.assertFalse(self.refused)
        self.events.append('install')
        self.installed = True

    def run(self):
        real_helpers = phase.helpers()
        with patch.object(real_helpers, 'require_offline', side_effect=self.prove_offline), \
                patch.object(phase, 'helpers', return_value=real_helpers):
            return phase.run(self.command, self.evidence, AVD, self.apks, self.install)


class RemoteRepairPhaseTests(unittest.TestCase):
    def test_exact_immutable_inventory_matches_real_kotlin_sources(self):
        self.assertEqual(list(phase.METHODS), ['OfflineRemoteRepairContractTest',
                                             'OfflineRemoteRepairModelTest', 'OfflineRemoteRepairUiTest'])
        self.assertEqual([len(methods) for methods in phase.METHODS.values()], [22, 15, 5])
        selected = [name for cls in phase.METHODS for name in phase.selectors(cls)]
        self.assertEqual(len(selected), 42)
        self.assertEqual(len(set(selected)), 42)
        with self.assertRaises(TypeError): phase.METHODS['unreviewed'] = ('test',)
        self.assertTrue(all(isinstance(methods, tuple) for methods in phase.METHODS.values()))
        self.assertEqual(len(phase.source_bindings()), 3)
        for cls, methods in phase.METHODS.items():
            source = (phase.SOURCE_DIR / (cls + '.kt')).read_text(encoding='utf-8')
            actual = re.findall(r'@Test\s+fun\s+(\w+)\s*\(', source)
            self.assertCountEqual(actual, methods)
            args = phase.instrumentation_args(cls)
            self.assertEqual(args[args.index('class') + 1], ','.join(phase.selectors(cls)))
            self.assertEqual(args[args.index('offline_features_phase') + 1], 'remote_repair_graph')
            self.assertEqual(args[-1], 'io.github.sussic.pyfa.dev.test/io.github.sussic.pyfa.DiagnosticTestRunner')

    def test_missing_or_changed_source_inventory_refuses_before_transport(self):
        cls = next(iter(phase.METHODS)); method = phase.METHODS[cls][0]
        for fault in ('missing', 'package', 'class', 'annotation', 'method', 'extra', 'duplicate'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix='pyfa-g052-host-') as directory:
                root = Path(directory); source = root / 'sources'; source.mkdir()
                for class_name in phase.METHODS:
                    path = phase.SOURCE_DIR / (class_name + '.kt')
                    shutil.copyfile(path, source / path.name)
                target = source / (cls + '.kt'); text = target.read_text(encoding='utf-8')
                if fault == 'missing': target.unlink()
                else:
                    replacements = {
                        'package': text.replace('package io.github.sussic.pyfa', 'package unreviewed', 1),
                        'class': text.replace('class ' + cls, 'class DifferentTest', 1),
                        'annotation': text.replace('@Test fun ' + method, 'fun ' + method, 1),
                        'method': text.replace(method, 'renamedMethod', 1),
                        'extra': text + '\n@Test fun extraMethod() {}\n',
                        'duplicate': text + '\n@Test fun ' + method + '() {}\n',
                    }
                    target.write_text(replacements[fault], encoding='utf-8')
                transport = Transport(self, root)
                with patch.object(phase, 'SOURCE_DIR', source), self.assertRaises(ValueError):
                    transport.run()
                self.assertEqual(transport.events, [])
                self.assertFalse(transport.evidence.exists())

    def test_source_hashes_bind_current_bytes_without_permanent_frozen_hash_gate(self):
        original = phase.source_bindings()
        with tempfile.TemporaryDirectory(prefix='pyfa-g052-host-') as directory:
            source = Path(directory)
            for class_name in phase.METHODS:
                path = phase.SOURCE_DIR / (class_name + '.kt')
                (source / path.name).write_bytes(path.read_bytes() + b'\n// synthetic source hash check\n')
            with patch.object(phase, 'SOURCE_DIR', source): actual = phase.source_bindings()
            self.assertEqual(set(actual), set(original))
            for key, digest in actual.items():
                self.assertNotEqual(digest, original[key])
                self.assertEqual(digest, hashlib.sha256((source / Path(key).name).read_bytes()).hexdigest())

    def test_missing_apk_existing_evidence_and_wrong_profile_refuse_before_transport(self):
        for fault in ('apk', 'evidence', 'profile'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix='pyfa-g052-host-') as directory:
                transport = Transport(self, Path(directory))
                if fault == 'apk': transport.apks[-1].unlink()
                if fault == 'evidence': transport.evidence.mkdir()
                with self.assertRaises(ValueError):
                    phase.run(transport.command, transport.evidence,
                              'Pixel_9a' if fault == 'profile' else AVD,
                              transport.apks, transport.install)
                self.assertEqual(transport.events, [])
                self.assertFalse((transport.evidence / 'result.json').exists())

    def test_real_parser_accepts_exact_complete_events(self):
        for cls in phase.METHODS: phase.validate_output(cls, output(cls))

    def test_real_parser_refuses_corrupt_execution_evidence(self):
        # Each class has a different count. In particular, the contract suite
        # must reject a corrupted 22-method count rather than testing a no-op
        # replacement inherited from the nine-method shield class.
        for cls, methods in phase.METHODS.items():
            count = len(methods); method = methods[0]; raw = output(cls)
            start = event(cls, method, 1, 1); complete = event(cls, method, 1, 0)
            summary = 'OK (' + str(count) + ' tests)\n'
            cases = {
                'failed': raw.replace('INSTRUMENTATION_STATUS_CODE: 0', 'INSTRUMENTATION_STATUS_CODE: -2', 1),
                'errored': raw.replace('INSTRUMENTATION_STATUS_CODE: 0', 'INSTRUMENTATION_STATUS_CODE: -1', 1),
                'skipped': raw.replace('INSTRUMENTATION_STATUS_CODE: 0', 'INSTRUMENTATION_STATUS_CODE: -3', 1),
                'missing-method': raw.replace(start + complete, '', 1),
                'extra-method': event(cls, 'unselectedMethod', count + 1, 1) +
                                event(cls, 'unselectedMethod', count + 1, 0) + raw,
                'wrong-class': raw.replace(phase.PREFIX + cls, phase.PREFIX + 'UnselectedTest', 1),
                'wrong-count': raw.replace('numtests=' + str(count) + '\n',
                                           'numtests=' + str(count + 1) + '\n'),
                'wrong-summary-count': raw.replace(summary, 'OK (' + str(count + 1) + ' tests)\n'),
                'missing-start': raw.replace(start, '', 1),
                'missing-completion': raw.replace(complete, '', 1),
                'duplicate-start': start + raw,
                'duplicate-completion': raw + complete,
                'missing-terminal': raw.replace('INSTRUMENTATION_CODE: -1\n', ''),
                'wrong-terminal': raw.replace('INSTRUMENTATION_CODE: -1\n', 'INSTRUMENTATION_CODE: 0\n'),
                'duplicate-terminal': raw + 'INSTRUMENTATION_CODE: -1\n',
                'missing-summary': raw.replace(summary, ''),
                'duplicate-summary': raw + summary,
                'failure-summary': raw + 'FAILURES!!!\n',
                'runner-failure': raw + 'INSTRUMENTATION_FAILED\n',
                'runner-exception': raw + 'shortMsg=synthetic error\n',
                'aborted': raw + 'INSTRUMENTATION_ABORTED\n',
            }
            for name, malformed in cases.items():
                with self.subTest(cls=cls, case=name):
                    self.assertNotEqual(malformed, raw, 'Negative fixture did not change the valid output')
                    with self.assertRaises((AssertionError, ValueError)):
                        phase.validate_output(cls, malformed)

    def test_optimization_refuses_before_parser_or_transport(self):
        for entry in ("p.validate_output(next(iter(p.METHODS)), '')", "p.run(forbidden, None, None, None, forbidden)"):
            code = ("import sys;sys.path.insert(0,sys.argv[1]);import remote_repair_native as p;"
                    "forbidden=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('LATER OPERATION'));"
                    "p.helpers=forbidden;" + entry)
            result = subprocess.run([sys.executable, '-I', '-B', '-O', '-c', code, str(Path(__file__).parent)],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Python optimization disables', result.stderr)
            self.assertNotIn('RuntimeError: LATER OPERATION', result.stderr)

    def test_focused_plan_preserves_legacy_projected_and_shield_selection(self):
        self.assertEqual(len(local_verification.plan('full', None)), 190)
        self.assertEqual(native_suite.INITIAL_TESTS, {
            'io.github.sussic.pyfa.AppShellTest.offlineLaunchShowsHonestStatusAndNavigatesBack',
            'io.github.sussic.pyfa.AppShellTest.aboutSurvivesActivityRecreationAndLandscapeWithSystemBack',
            'io.github.sussic.pyfa.EngineParityTest.bundledEngineMatchesIndependentDesktopAmmunitionStatesOffline',
            'io.github.sussic.pyfa.EngineParityTest.projectedEffectsMatchDesktopAndRefreshAllRecipientsOffline',
            'io.github.sussic.pyfa.EngineParityTest.commandBurstsMatchDesktopAndClearRecipientBonusesOffline',
        })
        self.assertEqual([len(methods) for methods in projected_phase.METHODS.values()], [3, 4, 2])
        self.assertEqual([len(methods) for methods in shield_phase.METHODS.values()], [9, 9, 2, 2])
        for legacy in (projected_phase, shield_phase):
            for cls, methods in legacy.METHODS.items():
                source = (phase.SOURCE_DIR / (cls + '.kt')).read_text(encoding='utf-8')
                self.assertCountEqual(re.findall(r'@Test\s+fun\s+(\w+)\s*\(', source), methods)
        gates = (phase.PHASE, projected_phase.PHASE, shield_phase.PHASE)
        self.assertEqual(set(native_suite.SUPPLEMENTAL_STEPS), set(gates))
        for gate in gates:
            self.assertNotIn(gate, native_suite.STEPS)
            for mode in ('full', 'desktop', 'build', 'native'):
                self.assertNotIn('native:' + gate, local_verification.plan(mode, None))
                if mode != 'native':
                    with self.assertRaises(ValueError): local_verification.plan(mode, gate)
            self.assertEqual(local_verification.plan('native', gate),
                             ['build:' + name for name in local_verification.BUILD] + ['native:' + gate])

    def test_cli_plan_accepts_only_focused_native_mode_without_tools(self):
        for mode, expected in (('native', 0), ('build', 1)):
            result = subprocess.run([sys.executable, '-I', '-B', str(Path(local_verification.__file__)),
                                     'plan', '--mode', mode, '--gate', phase.PHASE],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, expected, result.stderr)
            if mode == 'native': self.assertIn('native:' + phase.PHASE, result.stdout)

    def test_dispatch_requires_expected_avd_and_uses_supplemental_owner(self):
        with patch.object(sys, 'argv', ['native_suite.py', '--step', phase.PHASE, '--expected-avd', AVD]), \
                patch.object(native_suite, 'evidence_dir', return_value=Path('synthetic-evidence')), \
                patch.object(native_suite, 'remote_repair_graph') as invoke, \
                patch.object(native_suite, 'adb') as sdk:
            native_suite.main()
            invoke.assert_called_once_with(Path('synthetic-evidence'), AVD)
            sdk.assert_not_called()
        with patch.object(sys, 'argv', ['native_suite.py', '--step', phase.PHASE]), \
                patch.object(native_suite, 'evidence_dir') as destination, self.assertRaises(SystemExit):
            native_suite.main()
        destination.assert_not_called()

    def test_owner_refusal_never_falls_through_to_unbound_adb(self):
        for changes in ({'ANDROID_SERIAL': 'physical-phone'}, {'PYFA_LOCAL_RUN_ID': ''},
                        {'PYFA_BUDGET_JOB_NAME': 'unowned'}):
            with self.subTest(changes=changes), patch.dict(os.environ, dict(OWNED, **changes)), \
                    patch.object(sys, 'argv', ['native_suite.py', '--step', phase.PHASE, '--expected-avd', AVD]), \
                    patch.object(native_suite, 'evidence_dir', return_value=Path('synthetic-evidence')), \
                    patch.object(native_suite.subprocess, 'run') as process, \
                    patch.object(native_suite, 'adb') as sdk, self.assertRaises(ValueError):
                native_suite.main()
            process.assert_not_called(); sdk.assert_not_called()

    def test_wrapper_binds_every_command_to_owned_serial_and_preserves_raw_bytes(self):
        calls = []
        def process(args, **kwargs):
            self.assertEqual(args[:3], ['adb', '-s', 'emulator-5554'])
            kwargs['stdout'].write(b'synthetic \xff\r\n')
            calls.append((args, kwargs['timeout']))
            return subprocess.CompletedProcess(args, 0)
        def adapter(command, evidence, expected_avd, apks, install):
            self.assertEqual(expected_avd, AVD); self.assertEqual(len(apks), 2)
            evidence.mkdir()
            self.assertEqual(command('probe', 'shell', 'getprop', 'ro.kernel.qemu', timeout=9), 'synthetic \ufffd\r\n')
            install()
            return 'synthetic-result'
        with tempfile.TemporaryDirectory(prefix='pyfa-g052-host-') as directory, \
                patch.dict(os.environ, OWNED), patch.object(phase, 'run', side_effect=adapter), \
                patch.object(native_suite.subprocess, 'run', side_effect=process), \
                patch.object(native_suite, 'install_apks', side_effect=lambda command: command('install', '-t', 'fixture.apk')):
            self.assertEqual(native_suite.remote_repair_graph(Path(directory), AVD), 'synthetic-result')
        self.assertEqual([timeout for _, timeout in calls], [9, 120])

    def test_prerequisite_failures_stop_before_later_operations(self):
        for fault in ('avd', 'qemu', 'api', 'abi', 'existing', 'offline', 'path', 'hash', 'internet'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix='pyfa-g052-host-') as directory:
                transport = Transport(self, Path(directory), fault)
                with self.assertRaises(ValueError): transport.run()
                self.assertFalse(set(phase.METHODS).intersection(transport.events))
                self.assertEqual(transport.installed, fault in ('path', 'hash', 'internet'))
                self.assertFalse((transport.evidence / 'result.json').exists())

    def test_synthetic_success_binds_all_42_sources_apks_and_actual_raw_log_bytes(self):
        with tempfile.TemporaryDirectory(prefix='pyfa-g052-host-') as directory:
            transport = Transport(self, Path(directory)); result = transport.run()
            self.assertEqual(result['native_executions'], 42)
            self.assertEqual([len(row['methods']) for row in result['phases']], [22, 15, 5])
            self.assertEqual(transport.events[-3:], list(phase.METHODS))
            self.assertLess(transport.events.index('offline'), transport.events.index('install'))
            self.assertEqual(result['test_source_sha256'], phase.source_bindings())
            self.assertEqual(result['apk_sha256'], transport.hashes)
            for row in result['phases']:
                raw = transport.raw_logs[row['class']]
                self.assertEqual(row['output_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertNotEqual(row['output_sha256'], hashlib.sha256(raw.decode('utf-8', errors='replace').encode()).hexdigest())
            self.assertTrue(result['development_only'])
            for field in ('full_delivery', 'restart_qualified', 'screenshots_reviewed', 'other_cloud_native_gates_complete'):
                self.assertFalse(result[field])
            self.assertEqual(json.loads((transport.evidence / 'result.json').read_text()), result)

    def test_missing_or_mismatched_retained_log_cannot_produce_success_receipt(self):
        for fault in ('missing-log', 'mismatched-log'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix='pyfa-g052-host-') as directory:
                transport = Transport(self, Path(directory), fault)
                with self.assertRaises(ValueError): transport.run()
                self.assertEqual(len(set(phase.METHODS).intersection(transport.events)), 1)
                self.assertFalse((transport.evidence / 'result.json').exists())

    def test_source_changes_during_execution_prevent_success_receipt(self):
        with tempfile.TemporaryDirectory(prefix='pyfa-g052-host-') as directory:
            root = Path(directory); source = root / 'sources'; source.mkdir()
            for class_name in phase.METHODS:
                path = phase.SOURCE_DIR / (class_name + '.kt')
                shutil.copyfile(path, source / path.name)
            transport = Transport(self, root); target = source / (next(iter(phase.METHODS)) + '.kt')
            def change(_):
                target.write_bytes(target.read_bytes() + b'\n// changed during synthetic transport\n')
                transport.after_class = None
            transport.after_class = change
            with patch.object(phase, 'SOURCE_DIR', source), self.assertRaisesRegex(ValueError, 'changed during phase'):
                transport.run()
            self.assertFalse((transport.evidence / 'result.json').exists())

    def test_actual_owner_routes_all_three_supplements_to_c04_and_existing_outer_deadline(self):
        # Evaluate only the actual owner's side-effect-free routing expressions;
        # never instantiate Run or execute its build/emulator path.
        tree = ast.parse(Path(local_verification.__file__).read_text(encoding='utf-8'))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        start = next(node for node in calls if isinstance(node.func, ast.Attribute) and
                     node.func.attr == 'start_emulator' and node.keywords)
        suffix = next(item.value for item in start.keywords if item.arg == 'suffix')
        args = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Assign) and
                    any(isinstance(target, ast.Name) and target.id == 'arguments' for target in node.targets) and
                    isinstance(node.value, ast.IfExp) and '--expected-avd' in ast.unparse(node.value))
        execute = next(node for node in calls if isinstance(node.func, ast.Attribute) and
                       node.func.attr == 'execute' and 'android/ci/native_suite.py' in ast.unparse(node))
        timeout = next(item.value for item in execute.keywords if item.arg == 'timeout')
        def evaluate(expression, **values):
            return eval(compile(ast.Expression(expression), '<owner-routing>', 'eval'), {'__builtins__': {}}, values)
        for step in ('native:remote_repair_graph', 'native:projected_module_charges',
                     'native:shield_regeneration_graph', 'native:initial'):
            supplemental = step != 'native:initial'
            self.assertEqual(evaluate(suffix, step=step), '-c04' if supplemental else '')
            arguments = evaluate(args, step=step, self=SimpleNamespace(state={'avd_name': AVD}))
            self.assertEqual(arguments, ['--expected-avd', AVD] if supplemental else [])
            self.assertEqual(evaluate(timeout, arguments=arguments), 1200 if supplemental else None)


if __name__ == '__main__': unittest.main(verbosity=2)
