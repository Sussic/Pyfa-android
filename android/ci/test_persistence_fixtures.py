"""Exercise B02's actual fixture guards and preserved manifest consistency."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import persistence_summary as validator
import summary_repair


class GuardsPassed(Exception):
    pass


class Report(dict):
    def __getitem__(self, key):
        if key == 'runtime_start':
            raise GuardsPassed('Fixture guards and manifest/report consistency passed')
        return super().__getitem__(key)


class PersistenceFixtureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'tools/android_reference/fixtures'
        self.directory.mkdir(parents=True)
        self.apk = self.root / 'retained-test.apk'
        self.engine = dict(database_sha256='db', database_logical_sha256='logical',
            engine_source_sha256='engine', source_data_sha256='source', desktop_source_commit='pin', dataset_metadata={})
        self.names = {'ammunition': 'vexor', 'projection': 'projection', 'command': 'command'}
        self.data = {}
        self.reports = []
        for index, phase in enumerate(validator.PHASES):
            self.reports.append(Report(task='B02', phase=phase, pid=index + 1,
                session_id=f'{index+1:032x}', role_ids={role: f'{j+1:032x}' for j, role in enumerate(validator.ROLES)},
                airplane_mode=True, no_internet_permission=True, manifest=dict(self.engine), fixtures={}))
        for kind, name in self.names.items():
            oracle = dict(source_commit='pin', inputs={'target': {}} if kind == 'projection' else {},
                eos_settings={}, resolved_item_ids={}, database_logical_sha256='logical',
                source_data_sha256='source', dataset_metadata={})
            self.data[name] = (json.dumps(oracle, indent=2) + '\n').encode()
            (self.directory / (name + '.json')).write_bytes(self.data[name])
            for report in self.reports:
                report['fixtures'][kind] = dict(oracle)
        self.write_apk(self.data)

    def write_apk(self, contents, missing=None):
        with ZipFile(self.apk, 'w') as apk:
            for kind, name in self.names.items():
                raw = contents[name]
                if name != missing: apk.writestr('assets/' + name + '-expected.json', raw)
                for report in self.reports:
                    report['fixtures'][kind]['sha256'] = hashlib.sha256(raw).hexdigest()
                    key = 'desktop_fixture_sha256' if kind == 'ammunition' else kind + '_fixture_sha256'
                    report['manifest'][key] = hashlib.sha256(raw).hexdigest()

    def check(self):
        with (patch.object(validator, '__file__', str(self.root / 'android/ci/persistence_summary.py')),
                patch.dict(os.environ, PYFA_INSTRUMENTATION_APK=str(self.apk))):
            validator.summarize(self.reports, self.engine)

    def test_lf_crlf_equivalents_pass(self):
        for apk_crlf in (False, True):
            for source_crlf in (False, True):
                self.write_apk({k: v.replace(b'\n', b'\r\n') if apk_crlf else v for k, v in self.data.items()})
                for name, raw in self.data.items():
                    (self.directory / (name + '.json')).write_bytes(raw.replace(b'\n', b'\r\n') if source_crlf else raw)
                with self.subTest(apk_crlf=apk_crlf, source_crlf=source_crlf), self.assertRaises(GuardsPassed): self.check()

    def test_wrong_reported_hash_fails_even_with_matching_manifest(self):
        for kind in self.names:
            self.write_apk(self.data)
            self.reports[0]['fixtures'][kind]['sha256'] = '0' * 64
            key = 'desktop_fixture_sha256' if kind == 'ammunition' else kind + '_fixture_sha256'
            self.reports[0]['manifest'][key] = '0' * 64
            with self.subTest(kind=kind), self.assertRaises(AssertionError): self.check()

    def test_manifest_report_inconsistency_still_fails(self):
        self.reports[0]['manifest']['desktop_fixture_sha256'] = '0' * 64
        with self.assertRaises(AssertionError): self.check()

    def test_changed_content_or_whitespace_fails_with_updated_hashes(self):
        for name in self.names.values():
            for altered in (self.data[name].replace(b'pin', b'changed'), self.data[name] + b' ',
                    self.data[name].replace(b'  ', b'\t'), self.data[name].replace(b'\n', b'\r')):
                self.write_apk(dict(self.data, **{name: altered}))
                with self.subTest(name=name, altered=altered), self.assertRaises(AssertionError): self.check()

    def test_missing_fixture_fails(self):
        for name in self.names.values():
            self.write_apk(self.data, missing=name)
            with self.subTest(name=name), self.assertRaises(KeyError): self.check()
        self.write_apk(self.data)
        (self.directory / 'vexor.json').unlink()
        with self.assertRaises(FileNotFoundError): self.check()

    def test_changed_reference_fails(self):
        (self.directory / 'vexor.json').write_bytes(self.data['vexor'] + b' ')
        with self.assertRaises(AssertionError): self.check()

    def test_only_exact_source_exception_is_accepted(self):
        root = Path(__file__).resolve().parents[2]
        original = subprocess.check_output(['git', 'show', '6792b03e:android/ci/persistence_summary.py'],
            cwd=root, text=True, encoding='utf-8')
        approved = summary_repair.corrected_persistence_source(original)
        self.assertEqual(approved, (root / 'android/ci/persistence_summary.py').read_text(encoding='utf-8'))
        for source, accepted in ((approved, True), (approved + '\n', False),
                (approved.replace('assert manifest[hash_key] == proof["sha256"]', 'assert True'), False),
                (approved.replace('hashlib.sha256(packaged)', 'hashlib.sha256(data)'), False)):
            with patch.object(summary_repair.subprocess, 'check_output', side_effect=[
                    'android/ci/persistence_summary.py\n', original, source]):
                if accepted: summary_repair.equivalent(root, 'before', 'after')
                else:
                    with self.assertRaises(AssertionError): summary_repair.equivalent(root, 'before', 'after')


if __name__ == '__main__':
    unittest.main()
