"""Inspector integration must preserve the delivered verification contract."""
import ast
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import local_verification
from tools.android_reference.check_inspector import FAMILIES, REFERENCE_ONLY, command

ROOT = Path(__file__).resolve().parents[2]
DELIVERED = '745fc1e2cbc0127d69a3b228243a9a49ff303786'


class InspectorPlanTest(unittest.TestCase):
    def test_metadata_provenance_reuse_rejects_value_or_prefix_changes(self):
        before='e9a2baa24c4eed986673ebf0e2da0ef4e07bfc87'
        path='tools/android_reference/fixtures/inspector-context-metadata.json'
        old=subprocess.check_output(['git','show',before+':'+path],cwd=ROOT,text=True,encoding='utf-8')
        new=(ROOT/path).read_text(encoding='utf-8')
        gates=local_verification.plan('full',None)[:79]; files=[path,'android/ci/local_verification.py']
        def check(previous=before,completed=gates,revised=new,changed=files):
            def output(command,**kwargs):
                if command[1]=='diff': return '\n'.join(changed)
                return old if command[2].startswith(before+':') else revised
            with patch.object(local_verification.subprocess,'check_output',side_effect=output):
                local_verification.pending_inspector_context_metadata_fix(ROOT,previous,'candidate',completed)
        check()
        for arguments in (dict(previous='wrong'),dict(completed=gates[:-1]),
                          dict(completed=gates+['reference:inspector_context_metadata']),
                          dict(revised=new+' '),dict(revised=new.replace('e2ea5a56','00000000')),
                          dict(changed=files+['android_bridge/inspection.py'])):
            with self.subTest(arguments=tuple(arguments)),self.assertRaises(AssertionError):check(**arguments)

    def test_pending_booster_history_reuse_preserves_complete_assertions(self):
        before='750e4a7df002a44a9da6f907176e974c0bd2627b'
        path='tools/android_headless/check_history_mutations.py'
        helper='tools/android_headless/booster_history_witness.py'
        old=subprocess.check_output(['git','show',before+':'+path],cwd=ROOT,text=True,encoding='utf-8')
        # This exception validates the exact historical booster-only revision.
        # The expanded C04 history witness correctly cannot reuse that exception.
        new=subprocess.check_output(['git','show','cbda3ade:'+path],cwd=ROOT,text=True,encoding='utf-8'); witness=(ROOT/helper).read_text(encoding='utf-8')
        changes=[path,helper,'android/ci/local_verification.py','android/ci/test_inspector_plan.py']
        completed=local_verification.plan('full',None)[:55]
        def check(previous=before,gates=completed,revised=new,extra=witness,files=changes):
            def output(command,**kwargs):
                if command[1]=='diff': return '\n'.join(files)
                if command[2].endswith(':'+helper): return extra
                return old if command[2].startswith(before+':') else revised
            with patch.object(local_verification.subprocess,'check_output',side_effect=output):
                local_verification.pending_inspector_booster_history_fix(ROOT,previous,'candidate',gates)
        check()
        for arguments in (dict(previous='unrelated'),dict(gates=completed[:-1]),
                          dict(gates=completed+['headless:history_mutations']),
                          dict(revised=new.replace("compare(set(LABELS) - set(MODULE_LABELS), covered - {'change_variation'})","pass")),
                          dict(extra=witness.replace('compare(record, bridge._records[key])','pass')),
                          dict(files=changes+['android_bridge/history.py'])):
            with self.subTest(arguments=tuple(arguments)),self.assertRaises(AssertionError): check(**arguments)

    def test_pending_library_copy_reuse_rejects_unrelated_changes(self):
        before='fb35ca91c6cd73e3e9ecd71037984d2d3da268a5'
        path='tools/android_headless/tests/test_library.py'
        old=subprocess.check_output(['git','show',before+':'+path],cwd=ROOT,text=True,encoding='utf-8')
        new=(ROOT/path).read_text(encoding='utf-8')
        changes=[path,'android/ci/local_verification.py','android/ci/test_inspector_plan.py']
        completed=local_verification.plan('full',None)[:36]
        def check(previous=before, gates=completed, revised=new, files=changes):
            def output(command,**kwargs):
                if command[1]=='diff': return '\n'.join(files)
                return old if command[2].startswith(before+':') else revised
            with patch.object(local_verification.subprocess,'check_output',side_effect=output):
                local_verification.pending_inspector_library_copy_fix(ROOT,previous,'candidate',gates)
        check()
        for arguments in (dict(previous='unrelated'),dict(gates=completed[:-1]),
                          dict(gates=completed+['headless:library']),
                          dict(revised=new.replace('self.assertEqual(copy, expected)','pass')),
                          dict(revised=new.replace('self.assertTrue(set(key','self.assertFalse(set(key')),
                          dict(files=changes+['android_bridge/contract.py'])):
            with self.subTest(arguments=tuple(arguments)),self.assertRaises(AssertionError): check(**arguments)

    def test_every_delivered_gate_keeps_order_and_membership(self):
        source = subprocess.check_output(
            ['git', 'show', DELIVERED + ':android/ci/local_verification.py'], cwd=ROOT, text=True)
        tree = ast.parse(source)
        nodes = [node for node in tree.body if
                 isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
                 target.id in ('FAMILIES', 'HEADLESS', 'BUILD') for target in node.targets) or
                 isinstance(node, ast.FunctionDef) and node.name == 'plan']
        namespace = {'NATIVE_STEPS': [step for step in local_verification.NATIVE_STEPS if step != 'targeting-prepare3']}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<delivered-plan>', 'exec'), namespace)
        old = namespace['plan']('full', None)
        current = local_verification.plan('full', None)
        from drone_delivery import HOST_GATES, NATIVE_GATE, DECISION_GATE
        self.assertEqual(list(HOST_GATES)+[NATIVE_GATE,DECISION_GATE],current[175:])
        current=current[:175]
        retained = [gate for gate in current if not gate.startswith(
            ('reference:inspector_', 'headless:inspector_', 'native:inspection-'))]
        self.assertEqual(old, [gate for gate in retained if gate != 'native:targeting-prepare3'])
        self.assertEqual(115, len(old))
        self.assertEqual(old[:62], current[:62])
        self.assertEqual(60, len(current) - len(old))
        from inspection_delivery import PHASES
        self.assertEqual(['native:inspection-' + phase for phase in (*PHASES, 'summary')], current[-24:])
        self.assertEqual(175, len(current))
        self.assertEqual(len(current), len(set(current)))
        original_native = subprocess.check_output(
            ['git', 'show', DELIVERED + ':android/ci/native_suite.py'], cwd=ROOT)
        # The new class is excluded from the inherited five-test launch and
        # runs separately. No inherited native assertion or phase may change.
        expected_native = original_native.replace(b"'CargoActionTest',", b"'CargoActionTest', 'InspectionTest',", 1)
        expected_native = expected_native.replace(b"'TargetingTest']", b"'TargetingTest', 'InspectionUiTest']", 1)
        expected_native = expected_native.replace(b"('prepare0','prepare1','prepare2','restored')", b"('prepare0','prepare1','prepare2','prepare3','restored')")
        expected_native=expected_native.replace(b"'InspectionUiTest']", b"'InspectionUiTest', 'DroneContractTest', 'DroneAcceptanceTest', 'DroneUiTest', 'DroneMatrixTest']")
        self.assertEqual(expected_native.replace(b'\r\n', b'\n'),
                         (ROOT / 'android/ci/native_suite.py').read_bytes().replace(b'\r\n', b'\n'))

    def test_all_original_inspector_families_have_reference_and_comparison(self):
        plan = local_verification.plan('desktop', None)
        for family in FAMILIES:
            self.assertIn('reference:inspector_' + family, plan)
            if family not in REFERENCE_ONLY: self.assertIn('headless:inspector_' + family, plan)
            else: self.assertNotIn('headless:inspector_' + family, plan)
        self.assertNotIn('headless:inspector_inventory', plan)
        self.assertIn('headless:inspector_presentation', plan)
        self.assertIn('headless:inspector_payloads', plan)
        self.assertIn('headless:inspector_lifecycle', plan)

    def test_reference_routing_uses_original_sources_and_link_kind(self):
        database, fixture, source = Path('database'), Path('fixture'), Path('source')
        for family in FAMILIES:
            args = command(family, 'export', database, fixture, source)
            self.assertEqual(['--source', 'source'], args[args.index('--source'):args.index('--source') + 2])
            if family in ('projection', 'command'):
                self.assertTrue(args[2].endswith('inspector_links.py'))
                self.assertEqual(['--kind', family], args[-2:])
            if family == 'inventory':
                self.assertIn('--output', args)
            if family in REFERENCE_ONLY:
                with self.assertRaises(ValueError): command(family, 'verify', database, fixture)

    def test_focused_inspector_uses_only_real_existing_gates(self):
        self.assertEqual(['headless:inspector_lifecycle'],local_verification.plan('desktop','inspector_lifecycle'))
        with self.assertRaises(AssertionError):local_verification.plan('full','inspector_lifecycle')
        for family in FAMILIES:
            gate = 'inspector_' + family
            expected = ['reference:' + gate]
            if family not in REFERENCE_ONLY: expected.append('headless:' + gate)
            self.assertEqual(expected, local_verification.plan('desktop', gate))
            with self.assertRaises(AssertionError): local_verification.plan('full', gate)
        with self.assertRaises(AssertionError): local_verification.plan('desktop', 'inspector_missing')


if __name__ == '__main__': unittest.main()
