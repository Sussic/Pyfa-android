"""Focused raw-type, fixture-byte and corruption regressions; no native-pass claim."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import mutation_history_summary as summary

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'tools/android_reference/fixtures/history-mutations.json').read_text(encoding='utf-8'))


def typed(value):
    kinds = {}
    def visit(row, path):
        if type(row) is dict:
            for key, entry in row.items(): visit(entry, path + '.' + key)
        elif type(row) is list:
            for index, entry in enumerate(row): visit(entry, f'{path}[{index}]')
        elif type(row) in (int, float): kinds[path] = 'integer' if type(row) is int else 'decimal'
    visit(value, 'root')
    return dict(data=value, numeric_types=kinds)


class MutationStateTest(unittest.TestCase):
    def setUp(self):
        self.case = deepcopy(next(c for c in FIXTURE['cases'] if c['name'] == 'cargo-add'))
        self.step = self.case['steps'][1]
        self.actual = typed(deepcopy(self.step['result']))
    def test_all_168_original_states_and_explicit_recent_policy(self):
        checked = 0
        for case in FIXTURE['cases']:
            for step in case['steps']:
                actual = deepcopy(step['result'])
                if case['operation'] in ('add_implant', 'remove_implant'): actual['recent'] = []
                if case['operation'] == 'remove_cargo':
                    actual['recent'] = [] if step['action'] == 'initial' else [case['arguments']['item_id']]
                summary.state(case, step, typed(actual), [])
                checked += 1
        self.assertEqual(168, checked)
    def test_statistic_tolerances_and_original_units_are_preserved(self):
        key = next(k for k, row in self.actual['data']['stats'].items() if type(row['value']) in (int, float) and row['value'] > 1)
        self.actual['data']['stats'][key]['value'] += 1e-11
        summary.state(self.case, self.step, typed(self.actual['data']), [])
        self.actual['data']['stats'][key]['value'] += 1
        with self.assertRaises(AssertionError): summary.state(self.case, self.step, typed(self.actual['data']), [])
    def test_content_units_and_missing_fields_fail(self):
        for change in (
            lambda r: r['data']['cargo'][0].update(amount=1),
            lambda r: r['data'].update(name='Changed fit'),
            lambda r: r['data']['stats'][next(iter(r['data']['stats']))].update(unit='km/h'),
            lambda r: r['data'].pop('cargo'),
            lambda r: r['data'].update(extra=True),
        ):
            with self.subTest(change=change):
                actual = deepcopy(self.actual); change(actual)
                with self.assertRaises(AssertionError): summary.state(self.case, self.step, actual, [])
    def test_wrong_or_missing_numeric_kind_fails(self):
        for kind in ('decimal', 'boolean', None):
            actual = deepcopy(self.actual); path = 'root.cargo[0].amount'
            if kind is None: actual['numeric_types'].pop(path)
            else: actual['numeric_types'][path] = kind
            with self.assertRaises(AssertionError): summary.state(self.case, self.step, actual, [])
    def test_integer_input_cannot_be_decimal_or_boolean(self):
        for quantity in (350.0, True):
            actual = deepcopy(self.actual['data']); actual['cargo'][0]['amount'] = quantity
            with self.assertRaises(AssertionError): summary.state(self.case, self.step, typed(actual), [])
    def test_repeated_native_state_kind_cannot_change(self):
        other = deepcopy(self.actual)
        path = next(path for path, kind in other['numeric_types'].items() if path.startswith('root.stats.') and kind == 'decimal')
        other['numeric_types'][path] = 'integer'
        with self.assertRaises(AssertionError): summary.same_state(self.actual, other)
    def test_missing_or_duplicate_native_phases_fail(self):
        with patch.object(summary, 'fixture_bytes', return_value=(FIXTURE, 'a' * 64)):
            for rows in ([], [{'pid': 1}], [{'pid': 1}, {'pid': 1}]):
                with self.assertRaises(AssertionError): summary.summarize(rows, {}, [])
    def test_interleaved_recent_order_and_both_cursors(self):
        expected = FIXTURE['interleaved_recent']
        observed = dict(owner_id='owner', other_id='other', recent_before=[], steps=[
            dict(action=s['action'], owner=typed(deepcopy(s['owner'])), other=typed(deepcopy(s['other'])),
                owner_history=deepcopy(s['owner_history']), other_history=deepcopy(s['other_history']))
            for s in expected['steps']])
        summary.recent_case(expected, observed)
        for change in (
            lambda r: r['steps'][-1]['owner']['data'].update(recent=list(reversed(r['steps'][-1]['owner']['data']['recent']))),
            lambda r: r['steps'][-1]['other_history'].update(undo_count=2),
            lambda r: r['steps'][-1]['owner']['data']['cargo'][0].update(amount=149),
            lambda r: r['steps'].pop(),
        ):
            corrupted = deepcopy(observed); change(corrupted)
            with self.assertRaises(AssertionError): summary.recent_case(expected, corrupted)


class SettingsRepresentationTest(unittest.TestCase):
    def test_only_spoolup_whole_double_representation_is_accepted(self):
        expected = FIXTURE['eos_settings']
        for number in (1, 1.0):
            actual = deepcopy(expected); actual['globalDefaultSpoolupPercentage'] = number
            summary.settings(expected, actual)
    def test_wrong_value_boolean_string_nonfinite_and_missing_setting_fail(self):
        expected = FIXTURE['eos_settings']
        for number in (0, 1.0000000001, True, '1', float('nan'), float('inf')):
            actual = deepcopy(expected); actual['globalDefaultSpoolupPercentage'] = number
            with self.assertRaises(AssertionError): summary.settings(expected, actual)
        actual = deepcopy(expected); actual.pop('globalDefaultSpoolupPercentage')
        with self.assertRaises(AssertionError): summary.settings(expected, actual)
    def test_other_settings_still_require_exact_boolean_types(self):
        expected = FIXTURE['eos_settings']
        for name in ('strictSkillLevels', 'useStaticAdaptiveArmorHardener'):
            actual = deepcopy(expected); actual[name] = int(actual[name])
            with self.assertRaises(AssertionError): summary.settings(expected, actual)


class FixtureBytesTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.reference = self.root / 'tools/android_reference/fixtures/history-mutations.json'
        self.reference.parent.mkdir(parents=True)
        self.reference.write_bytes(b'{\n  "value": 1\n}\n')
        self.apk = self.root / 'synthetic-test.apk'
        self.file = patch.object(summary, '__file__', str(self.root / 'android/ci/mutation_history_summary.py'))
        self.environment = patch.dict(summary.os.environ, PYFA_INSTRUMENTATION_APK=str(self.apk))
        self.file.start(); self.environment.start()
        self.addCleanup(self.file.stop); self.addCleanup(self.environment.stop)
    def packaged(self, raw, missing=False):
        with ZipFile(self.apk, 'w') as archive:
            if not missing: archive.writestr('assets/history-mutations-expected.json', raw)
    def test_lf_and_crlf_equivalence_preserves_exact_packaged_hash(self):
        for raw in (self.reference.read_bytes(), self.reference.read_bytes().replace(b'\n', b'\r\n')):
            self.packaged(raw); value, digest = summary.fixture_bytes()
            self.assertEqual({'value': 1}, value)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            summary.validate_fixture({'fixture_sha256': digest}, digest)
    def test_incorrect_reported_hash_fails(self):
        self.packaged(self.reference.read_bytes()); _, digest = summary.fixture_bytes()
        for value in ('0' * 64, '', True):
            with self.assertRaises(AssertionError): summary.validate_fixture({'fixture_sha256': value}, digest)
    def test_missing_packaged_or_reference_fixture_fails(self):
        self.packaged(b'', missing=True)
        with self.assertRaises(KeyError): summary.fixture_bytes()
        self.packaged(self.reference.read_bytes()); self.reference.unlink()
        with self.assertRaises(FileNotFoundError): summary.fixture_bytes()
    def test_content_change_even_with_matching_updated_hash_fails(self):
        for raw in (b'{\n  "value": 2\n}\n', b'{ "value": 1 }\n', b'{\n  "value": 1\n}\r'):
            self.packaged(raw)
            summary.validate_fixture({'fixture_sha256': hashlib.sha256(raw).hexdigest()}, hashlib.sha256(raw).hexdigest())
            with self.assertRaises(AssertionError): summary.fixture_bytes()


if __name__ == '__main__': unittest.main()
