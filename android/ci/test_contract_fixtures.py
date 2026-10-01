"""Exercise the actual contract fixture guard with synthetic APK assets."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import contract_summary
import summary_repair


class GuardsPassed(Exception):
    pass


class Report(dict):
    def __getitem__(self, key):
        if key == 'states':
            raise GuardsPassed('All three fixture guards passed; later functional checks are unchanged')
        return super().__getitem__(key)


class FixtureIdentityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixtures = self.root / 'tools/android_reference/fixtures'
        fixtures.mkdir(parents=True)
        self.apk = self.root / 'retained-test.apk'
        self.oracle = dict(source_commit='pin', inputs={}, eos_settings={},
            database_logical_sha256='logical', source_data_sha256='source', dataset_metadata={})
        self.data = (json.dumps(self.oracle, indent=2) + '\n').encode()
        self.names = {'ammunition': 'vexor', 'projection': 'projection', 'command': 'command'}
        for name in self.names.values():
            (fixtures / (name + '.json')).write_bytes(self.data)
        self.engine = dict(database_sha256='db', database_logical_sha256='logical',
            engine_source_sha256='engine', source_data_sha256='source', desktop_source_commit='pin', dataset_metadata={})
        flags = {name: True for name in ('all_snapshots_matched_desktop', 'raw_scalar_types_checked',
            'units_checked', 'bulk_rejection_unchanged', 'stale_revision_unchanged', 'queries_unchanged',
            'unrelated_revisions_unchanged', 'queued_same_revision_one_success_one_conflict',
            'missing_revision_rejected_before_dispatch', 'invalid_create_unchanged',
            'queued_arguments_copied', 'ui_preserved_after_errors')}
        flags.update(desktop_snapshots_checked=63, statistics_per_snapshot=39, retained_fit_count=5)
        self.report = Report(task='B01', airplane_mode=True, no_internet_permission=True,
            manifest=self.engine, session_id='session', assertions=flags, codec_rejections=list(range(15)),
            runtime=dict(android_worker_thread='pyfa-engine', android_main_thread=False,
                session_id='session', saveddata_connectionstring='sqlite:///:memory:',
                retained_fit_count=5, desktop_import_attempts=[], manifest=self.engine, eos_settings={}), fixtures={})
        self.write_apk(self.data)

    def write_apk(self, data, missing=None):
        with ZipFile(self.apk, 'w') as apk:
            for kind, name in self.names.items():
                if name != missing:
                    apk.writestr('assets/' + name + '-expected.json', data)
                self.report['fixtures'][kind] = dict(self.oracle, sha256=hashlib.sha256(data).hexdigest())

    def check(self):
        with (patch.object(contract_summary, '__file__', str(self.root / 'android/ci/contract_summary.py')),
                patch.dict(os.environ, PYFA_INSTRUMENTATION_APK=str(self.apk))):
            contract_summary.summarize(self.report, self.engine)

    def test_lf_and_crlf_equivalents_pass_all_three_actual_guards(self):
        for packaged in (self.data, self.data.replace(b'\n', b'\r\n')):
            for reference in (self.data, self.data.replace(b'\n', b'\r\n')):
                with self.subTest(packaged=packaged == self.data, reference=reference == self.data):
                    self.write_apk(packaged)
                    for name in self.names.values():
                        (self.root / 'tools/android_reference/fixtures' / (name + '.json')).write_bytes(reference)
                    with self.assertRaises(GuardsPassed): self.check()

    def test_wrong_reported_hash_fails(self):
        for kind in self.names:
            self.write_apk(self.data)
            self.report['fixtures'][kind]['sha256'] = '0' * 64
            with self.subTest(kind=kind), self.assertRaises(AssertionError): self.check()

    def test_missing_packaged_or_reference_fixture_fails(self):
        for name in self.names.values():
            self.write_apk(self.data, missing=name)
            with self.subTest(missing_asset=name), self.assertRaises(KeyError): self.check()
        self.write_apk(self.data)
        path = self.root / 'tools/android_reference/fixtures/vexor.json'
        path.unlink()
        with self.assertRaises(FileNotFoundError): self.check()

    def test_missing_apk_fails(self):
        self.apk.unlink()
        with self.assertRaises(FileNotFoundError): self.check()

    def test_changed_content_or_other_whitespace_fails_even_with_matching_hash(self):
        for changed in (self.data.replace(b'pin', b'changed'), self.data + b' ',
                self.data.replace(b'  ', b'\t'), self.data.replace(b'\n', b'\r')):
            self.write_apk(changed)
            with self.subTest(changed=changed), self.assertRaises(AssertionError): self.check()

    def test_changed_reference_fails(self):
        path = self.root / 'tools/android_reference/fixtures/vexor.json'
        path.write_bytes(self.data + b' ')
        with self.assertRaises(AssertionError): self.check()


class ExactSourceTest(unittest.TestCase):
    def test_only_exact_approved_delta_passes(self):
        import subprocess
        root = Path(__file__).resolve().parents[2]
        original = subprocess.check_output(['git', 'show', '6792b03e:android/ci/contract_summary.py'],
            cwd=root, text=True, encoding='utf-8')
        approved = summary_repair.corrected_contract_source(original)
        self.assertEqual(approved, (root / 'android/ci/contract_summary.py').read_text(encoding='utf-8'))
        for source, accepted in ((approved, True), (approved + '\n', False),
                (approved.replace('rel_tol=1e-10', 'rel_tol=1e-5'), False),
                (approved.replace('assert proof["sha256"] ==', 'assert True or proof["sha256"] =='), False)):
            with patch.object(summary_repair.subprocess, 'check_output', side_effect=[
                    'android/ci/contract_summary.py\n', original, source]):
                if accepted:
                    summary_repair.equivalent(root, 'before', 'after')
                else:
                    with self.assertRaises(AssertionError): summary_repair.equivalent(root, 'before', 'after')


if __name__ == '__main__':
    unittest.main()
