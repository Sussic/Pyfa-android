"""Reject fixture/content/scalar corruption; line endings are the sole normalization."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sys
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from resource_summary import fixture_bytes, resources, ROOT


class ResourceSummaryTests(unittest.TestCase):
    def setUp(self):
        self.reference = (ROOT/'tools/android_reference/fixtures/resources.json').read_bytes()
        self.expected = json.loads(self.reference)['cases'][1]['resources']
        self.actual = {name:dict(used=row['used'],total=row['total'],
            used_type='integer' if type(row['used']) is int else 'decimal',
            total_type='integer' if type(row['total']) is int else 'decimal',unit=row['unit'],overloaded=row['overloaded'],
            used_display=row['desktop_used'],total_display=row['desktop_total'],
            used_detail=row['desktop_used_detail'],total_detail=row['desktop_total_detail']) for name,row in self.expected.items()}

    def archive(self, data, reported=None, missing=False):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory)/'test.apk'
            with ZipFile(apk,'w') as archive:
                archive.writestr('assets/other.json' if missing else 'assets/resources-expected.json',data)
            return fixture_bytes(apk,self.reference,reported or hashlib.sha256(data).hexdigest())

    def test_lf_crlf_equivalents_pass(self):
        lf = self.reference.replace(b'\r\n',b'\n')
        self.assertEqual(self.archive(lf),self.archive(lf.replace(b'\n',b'\r\n')))

    def test_wrong_reported_hash_fails(self):
        with self.assertRaises(AssertionError): self.archive(self.reference,'0'*64)

    def test_missing_fixture_fails(self):
        with self.assertRaises(KeyError): self.archive(self.reference,missing=True)

    def test_changed_content_with_matching_hash_fails(self):
        changed = self.reference.replace(b'Empty cruiser',b'Changed cruiser',1)
        with self.assertRaises(AssertionError): self.archive(changed)

    def test_other_whitespace_and_json_equivalence_fail(self):
        with self.assertRaises(AssertionError): self.archive(self.reference.replace(b'  "task"',b'   "task"',1))
        with self.assertRaises(AssertionError): self.archive(json.dumps(json.loads(self.reference)).encode())

    def test_original_and_whole_double_serialization_pass(self):
        resources(self.expected,self.actual)
        for row in self.actual.values():
            for key in ('used','total'):
                if type(row[key]) is float and row[key].is_integer(): row[key]=int(row[key])
        resources(self.expected,self.actual)

    def test_wrong_kind_fractional_integer_and_boolean_fail(self):
        for key,value in [('total_type','integer'),('total',True),('used',1.5)]:
            bad=deepcopy(self.actual); bad['turret_hardpoints'][key]=value
            with self.subTest(key=key), self.assertRaises(AssertionError): resources(self.expected,bad)

    def test_changed_values_displays_units_overload_missing_fail(self):
        for key,value in [('total',123.0),('unit','MW'),('used_display','wrong'),('overloaded',True),('total',float('nan'))]:
            bad=deepcopy(self.actual); bad['cpu'][key]=value
            with self.subTest(key=key), self.assertRaises(AssertionError): resources(self.expected,bad)
        bad=deepcopy(self.actual); del bad['fighter_bay']
        with self.assertRaises(AssertionError): resources(self.expected,bad)



    def edited_archive(self, data, reported=None, missing=False):
        reference=(ROOT/'tools/android_reference/fixtures/resources-edited.json').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            apk=Path(directory)/'test.apk'
            with ZipFile(apk,'w') as archive:
                archive.writestr('assets/other.json' if missing else 'assets/resources-edited-expected.json',data)
            return fixture_bytes(apk,reference,reported or hashlib.sha256(data).hexdigest(),'resources-edited-expected.json')

    def test_edited_fixture_line_endings_and_exact_hash(self):
        reference=(ROOT/'tools/android_reference/fixtures/resources-edited.json').read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(self.edited_archive(reference),self.edited_archive(reference.replace(b'\n',b'\r\n')))
        with self.assertRaises(AssertionError):self.edited_archive(reference,'0'*64)

    def test_edited_fixture_missing_content_and_whitespace_fail(self):
        reference=(ROOT/'tools/android_reference/fixtures/resources-edited.json').read_bytes()
        with self.assertRaises(KeyError):self.edited_archive(reference,missing=True)
        for changed in (reference.replace(b'Offline guns',b'Changed guns',1),reference.replace(b'  "task"',b'   "task"',1)):
            self.assertNotEqual(reference,changed)
            with self.assertRaises(AssertionError):self.edited_archive(changed)

    def test_edited_scalar_kind_and_value_remain_strict(self):
        expected=json.loads((ROOT/'tools/android_reference/fixtures/resources-edited.json').read_text(encoding='utf-8'))['resources']
        actual={name:dict(used=row['used'],total=row['total'],
            used_type='integer' if type(row['used']) is int else 'decimal',
            total_type='integer' if type(row['total']) is int else 'decimal',unit=row['unit'],overloaded=row['overloaded'],
            used_display=row['desktop_used'],total_display=row['desktop_total'],
            used_detail=row['desktop_used_detail'],total_detail=row['desktop_total_detail']) for name,row in expected.items()}
        resources(expected,actual)
        self.assertEqual(actual['calibration']['used_type'],'decimal')
        for key,value in (('used_type','integer'),('used',True),('used',0.5),('unit','wrong')):
            bad=deepcopy(actual);bad['calibration'][key]=value
            with self.assertRaises(AssertionError):resources(expected,bad)

if __name__=='__main__': unittest.main()
