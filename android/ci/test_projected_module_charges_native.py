"""Host checks only: synthetic runner text never constitutes Android proof."""
import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import projected_module_charges_native as phase
import native_suite
import local_verification


def output(cls):
    names = phase.selectors(cls)
    lines = []
    for current, name in enumerate(names, 1):
        classname, method = name.split('#')
        for code in (1, 0):
            lines += ['INSTRUMENTATION_STATUS: class='+classname,
                      'INSTRUMENTATION_STATUS: test='+method,
                      'INSTRUMENTATION_STATUS: numtests='+str(len(names)),
                      'INSTRUMENTATION_STATUS: current='+str(current),
                      'INSTRUMENTATION_STATUS_CODE: '+str(code)]
    return '\n'.join(lines+['OK ('+str(len(names))+' tests)', 'INSTRUMENTATION_CODE: -1'])+'\n'


class SupplementalPhaseTests(unittest.TestCase):
    def test_exact_nine_methods_exist_in_real_kotlin_sources(self):
        self.assertEqual([len(x) for x in phase.METHODS.values()], [3,4,2])
        root=Path(__file__).resolve().parents[1]/'app/src/androidTest/java/io/github/sussic/pyfa'
        for cls, methods in phase.METHODS.items():
            source=(root/(cls+'.kt')).read_text()
            for method in methods:
                self.assertIn('fun '+method+'(', source)
            args=phase.instrumentation_args(cls)
            self.assertEqual(args[args.index('class')+1], ','.join(phase.selectors(cls)))
            self.assertEqual(args[args.index('offline_features_phase')+1], phase.PHASE)

    def test_real_parser_accepts_exact_synthetic_events(self):
        for cls in phase.METHODS: phase.validate_output(cls, output(cls))

    def test_real_parser_rejects_incomplete_extra_duplicate_and_skipped_events(self):
        cls=next(iter(phase.METHODS)); raw=output(cls)
        cases=[raw.replace('INSTRUMENTATION_STATUS_CODE: 0','INSTRUMENTATION_STATUS_CODE: -3',1),
               raw.replace('INSTRUMENTATION_CODE: -1',''),
               raw.replace(phase.METHODS[cls][0],'unselectedMethod'),
               raw.replace('INSTRUMENTATION_STATUS_CODE: 1','INSTRUMENTATION_STATUS_CODE: 0',1),
               raw+'OK (3 tests)\n', raw+raw,
               raw.replace('numtests=3','numtests=4')]
        for malformed in cases:
            with self.subTest(case=cases.index(malformed)), self.assertRaises((AssertionError, ValueError)):
                phase.validate_output(cls, malformed)

    def test_optimization_refuses_before_parser_or_sdk(self):
        code="import sys;sys.path.insert(0,sys.argv[1]);import projected_module_charges_native as p;p.validate_output(next(iter(p.METHODS)),'')"
        result=subprocess.run([sys.executable,'-I','-B','-O','-c',code,str(Path(__file__).parent)],capture_output=True,text=True,timeout=20)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Python optimization disables',result.stderr)

    def test_supplement_is_opt_in_and_legacy_plan_remains_190(self):
        self.assertEqual(len(local_verification.plan('full',None)),190)
        for mode in ('full','desktop','build','native'):
            self.assertNotIn('native:'+phase.PHASE,local_verification.plan(mode,None))
        focused=local_verification.plan('native',phase.PHASE)
        self.assertEqual(focused,['build:'+name for name in local_verification.BUILD]+['native:'+phase.PHASE])
        self.assertNotIn(phase.PHASE,native_suite.STEPS)
        with self.assertRaises(ValueError): local_verification.plan('full',phase.PHASE)

    def test_existing_cli_plan_accepts_phase_without_execution(self):
        result=subprocess.run([sys.executable,'-I','-B',str(Path(local_verification.__file__)),
                               'plan','--mode','native','--gate',phase.PHASE],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('native:'+phase.PHASE,result.stdout)

    def test_native_suite_dispatch_and_legacy_positive_selection(self):
        with patch.object(sys,'argv',['native_suite.py','--step',phase.PHASE,'--expected-avd','pyfa-local-host-fixture-c04']), \
             patch.object(native_suite,'evidence_dir',return_value=Path('host-fixture')), \
             patch.object(native_suite,'projected_module_charges') as invoke, \
             patch.object(native_suite,'adb') as sdk:
            native_suite.main()
            invoke.assert_called_once_with(Path('host-fixture'),'pyfa-local-host-fixture-c04')
            sdk.assert_not_called()
        source=Path(native_suite.__file__).read_text()
        self.assertNotIn("'-e', 'notClass'",source)
        self.assertNotIn('RunnerArguments.notClass=',source)
        self.assertEqual(len(native_suite.INITIAL_TESTS),5)

    def test_phone_refusal_does_not_fall_through_to_generic_adb_diagnostics(self):
        with patch.object(sys,'argv',['native_suite.py','--step',phase.PHASE,'--expected-avd','pyfa-local-host-fixture-c04']), \
             patch.object(native_suite,'evidence_dir',return_value=Path('host-fixture')), \
             patch.dict(os.environ,{'ANDROID_SERIAL':'physical-phone'}), \
             patch.object(native_suite.subprocess,'run') as process, \
             patch.object(native_suite,'adb') as sdk:
            with self.assertRaises(ValueError): native_suite.main()
            process.assert_not_called();sdk.assert_not_called()

    def test_wrong_api_or_existing_app_refuses_before_install(self):
        for wrong_api, existing in ((True,False),(False,True)):
            with tempfile.TemporaryDirectory(prefix='pyfa-host-only-') as directory:
                root=Path(directory);apks=[root/'app.apk',root/'test.apk']
                for apk in apks: apk.write_bytes(b'host-only-apk-fixture')
                def command(label,*args,**kwargs):
                    if label=='identity-avd': return 'pyfa-local-host-fixture-c04\nOK\n'
                    if label=='identity-qemu': return '1\n'
                    if label=='identity-api': return '35\n' if wrong_api else '36\n'
                    if label=='identity-abi': return 'x86_64\n'
                    if label.startswith('prior-'): return 'package:'+phase.PACKAGE+'\n' if existing else ''
                    self.fail('Reached later phase before prerequisite refusal: '+label)
                install=Mock()
                with self.assertRaises(ValueError):
                    phase.run(command,root/'evidence','pyfa-local-host-fixture-c04',apks,install)
                install.assert_not_called()

    def test_synthetic_success_transport_covers_absence_install_and_exact_nine(self):
        # These temporary bytes/events test host wiring only, never Android proof.
        with tempfile.TemporaryDirectory(prefix='pyfa-host-only-') as directory:
            root=Path(directory);apks=[root/'app.apk',root/'test.apk']
            for index,apk in enumerate(apks): apk.write_bytes(('host-only-fixture-'+str(index)).encode())
            hashes={package:hashlib.sha256(apk.read_bytes()).hexdigest()
                    for package,apk in zip((phase.PACKAGE,phase.PACKAGE+'.test'),apks)}
            events=[];installed=False;offline=False
            def command(label,*args,**kwargs):
                events.append(label)
                if label=='identity-avd': return 'pyfa-local-host-fixture-c04\nOK\n'
                if label=='identity-qemu': return '1\n'
                if label=='identity-api': return '36\n'
                if label=='identity-abi': return 'x86_64\n'
                if label.startswith('prior-'):
                    if args[:3]==('shell','pm','path'):
                        raise subprocess.CalledProcessError(1,args)  # Real missing-package semantics.
                    self.assertEqual(args[:4],('shell','pm','list','packages'))
                    return ''
                self.assertTrue(installed)
                if label.startswith('installed-'): return 'package:/data/app/host-fixture/base.apk\n'
                if label.startswith('apk-hash-'): return hashes[label.removeprefix('apk-hash-')]+'  /data/app/host-fixture/base.apk\n'
                if label.startswith('internet-'): return 'denied\n'
                if label in phase.METHODS:
                    self.assertEqual(args,phase.instrumentation_args(label))
                    return output(label)
                self.fail('Unexpected host-fixture command '+label)
            def prove_offline(callback):
                nonlocal offline
                self.assertIs(callback,command);offline=True;events.append('offline')
                return {'synthetic_host_fixture_only':True}
            def install():
                nonlocal installed
                self.assertTrue(offline);installed=True;events.append('install')
            actual_helpers=phase.helpers()
            with patch.object(actual_helpers,'require_offline',side_effect=prove_offline), \
                 patch.object(phase,'helpers',return_value=actual_helpers):
                result=phase.run(command,root/'evidence','pyfa-local-host-fixture-c04',apks,install)
            self.assertEqual(result['native_executions'],9)
            self.assertEqual([len(row['methods']) for row in result['phases']],[3,4,2])
            self.assertFalse(result['full_delivery'])
            self.assertEqual(events[-3:],list(phase.METHODS))
            self.assertLess(events.index('offline'),events.index('install'))


if __name__=='__main__': unittest.main(verbosity=2)
