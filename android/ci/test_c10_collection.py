"""Synthetic offline receipts; no Android, subprocess or owner acceptance."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import os
import re
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from c10_collection import CollectionError, check_collection

ROOT = Path(os.environ.get('PYFA_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT / 'android/ci'))
spec = importlib.util.spec_from_file_location('c10_existing_protocol', ROOT / 'android/ci/check-drones.py')
PROTOCOL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PROTOCOL)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class CollectionTests(unittest.TestCase):
    def setUp(self):
        groups = {}
        for group, class_name in (('CONTRACT','MutationDisplayContractTest'),
                                  ('LEGACY','MutationDisplayEditorUiTest'),
                                  ('DURATION','MutationDurationEditorUiTest')):
            source = ROOT / f'android/app/src/androidTest/java/io/github/sussic/pyfa/{class_name}.kt'
            methods = re.findall(r'@Test\s+fun\s+(\w+)\s*\(', source.read_text(encoding='utf-8'))
            self.assertEqual({'CONTRACT':10,'LEGACY':2,'DURATION':2}[group],len(methods))
            groups[group] = dict(class_name=class_name, methods=methods)
        def phase(label, group, indices=None, name=None):
            row = groups[group]
            methods = row['methods'] if indices is None else [row['methods'][i] for i in indices]
            selector = 'io.github.sussic.pyfa.' + row['class_name']
            if len(methods) == 1:
                selector += '#' + methods[0]
            return dict(label=label, selector=selector, phase=name, methods=methods)
        phases = [phase('contract', 'CONTRACT'), phase('legacy-1', 'LEGACY', [0], 'mutation_units'),
                  phase('legacy-2', 'LEGACY', [1], 'mutation_units'),
                  phase('duration-edit', 'DURATION', [0], 'mutation_duration_edit'),
                  phase('duration-reopen', 'DURATION', [1], 'mutation_duration_reopen')]
        self.logs = {}
        for row in phases:
            lines = []
            for method in row['methods']:
                for code in (1, 0):
                    lines.extend([f"INSTRUMENTATION_STATUS: numtests={len(row['methods'])}",
                                  'INSTRUMENTATION_STATUS: class=' + row['selector'].split('#')[0],
                                  'INSTRUMENTATION_STATUS: test=' + method,
                                  f'INSTRUMENTATION_STATUS_CODE: {code}'])
            lines += [f"OK ({len(row['methods'])} tests)", 'INSTRUMENTATION_CODE: -1']
            self.logs[row['label']] = ('\n'.join(lines) + '\n').encode()
        self.report = dict(source_commit='a'*40, source_tree='b'*40, policy_sha256='c'*64,
                           status='COLLECTED_FIXED14_PENDING_OUTER_CLOSURE_REVIEW', error=None,
                           cleanup_errors=[], native_acceptance=False, full_C10_acceptance=False,
                           writer_process_death_claim=False, default_adb_server_addressed=False,
                           actual_outer_guard_zero_closure_required=True, phases=phases)
        self.required = {k: self.report[k] for k in ('source_commit','source_tree','policy_sha256')}
        self.required.update(phases=copy.deepcopy(phases), instrumentation_sha256={k: sha(v) for k,v in self.logs.items()})

    def check(self, bind_report=True):
        raw = json.dumps(self.report).encode()
        if bind_report:
            self.required['report_sha256'] = sha(raw)
        return check_collection(raw, self.logs, self.required, PROTOCOL.passed)

    def test_complete_collection_remains_pending_and_inputs_are_preserved(self):
        before = copy.deepcopy((self.report, self.logs, self.required))
        result = self.check()
        self.assertEqual(14, result['checked_methods'])
        self.assertIs(False, result['native_accepted'])
        self.assertIn('owner_acceptance', result['remaining'])
        self.assertEqual(before[:2], (self.report, self.logs))

    def test_report_byte_tamper_is_rejected(self):
        self.check(); self.report['source_commit']='d'*40
        with self.assertRaisesRegex(CollectionError, 'Report hash'): self.check(False)

    def test_wrong_source_tree_and_policy_are_rejected(self):
        for key in ('source_commit','source_tree','policy_sha256'):
            with self.subTest(key=key):
                before=self.report[key]; self.report[key]='wrong'
                with self.assertRaisesRegex(CollectionError,key): self.check()
                self.report[key]=before

    def test_failure_cleanup_and_promoted_acceptance_are_rejected(self):
        for key, bad in [('status','passed'),('error','failure'),('cleanup_errors',['unknown closure']),
                         ('native_acceptance',True),('full_C10_acceptance',True),
                         ('writer_process_death_claim',True),('default_adb_server_addressed',True),
                         ('actual_outer_guard_zero_closure_required',False)]:
            with self.subTest(key=key):
                old=self.report[key]; self.report[key]=bad
                with self.assertRaises(CollectionError): self.check()
                self.report[key]=old

    def test_missing_required_flags_and_error_are_rejected(self):
        for key in ('error','cleanup_errors','native_acceptance','actual_outer_guard_zero_closure_required'):
            with self.subTest(key=key):
                old=self.report.pop(key)
                with self.assertRaises(CollectionError): self.check()
                self.report[key]=old

    def test_missing_reordered_extra_or_changed_phases_are_rejected(self):
        original=copy.deepcopy(self.report['phases'])
        changed=copy.deepcopy(original); changed[-1]['methods']=['wrong']
        for phases in (original[:-1],list(reversed(original)),original+[original[0]],changed):
            with self.subTest(phases=phases):
                self.report['phases']=phases
                with self.assertRaisesRegex(CollectionError,'phase selection'): self.check()
        self.report['phases']=original

    def test_missing_extra_or_tampered_logs_are_rejected(self):
        original=copy.deepcopy(self.logs)
        for logs in ({k:v for k,v in original.items() if k!='contract'},
                     {**original,'extra':b'OK'}, {**original,'contract':b'OK'}):
            with self.subTest(logs=logs.keys()):
                self.logs=logs
                with self.assertRaises(CollectionError): self.check()
        self.logs=original

    def test_real_parser_rejects_skipped_failed_missing_and_duplicate_results(self):
        original=self.logs['duration-reopen']
        for bad in (original+b'FAILURES!!!\n', original.replace(b'CODE: 0',b'CODE: -3'),
                    original.replace(b'CODE: 0',b'CODE: 1'), original+original,
                    b'OK (1 tests)\nINSTRUMENTATION_CODE: -1\n'):
            with self.subTest(bad=bad):
                self.logs['duration-reopen']=bad
                self.required['instrumentation_sha256']['duration-reopen']=sha(bad)
                with self.assertRaisesRegex(CollectionError,'instrumentation'): self.check()

    def test_optimized_python_cannot_silently_disable_real_parser(self):
        result = subprocess.run([sys.executable, '-B', '-O', str(Path(__file__).resolve()), '--optimized-probe'],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('optimized parser refused', result.stdout)


if __name__ == '__main__':
    if sys.argv[1:] == ['--optimized-probe']:
        fixture = CollectionTests()
        fixture.setUp()
        fixture.logs = {name: b'' for name in fixture.logs}
        fixture.required['instrumentation_sha256'] = {name: sha(raw) for name,raw in fixture.logs.items()}
        try:
            fixture.check()
        except CollectionError as error:
            if 'requires assertion-enabled Python' not in str(error):
                raise
            print('optimized parser refused')
        else:
            raise SystemExit('ERROR: empty logs accepted with assertions disabled')
    else:
        unittest.main(verbosity=2)
