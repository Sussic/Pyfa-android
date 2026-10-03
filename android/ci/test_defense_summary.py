"""C01.3.1 numerical, shape, packaged fixture and transport regressions."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from defense_summary import defenses,typed,fit_inputs
from resource_summary import fixture_bytes

ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT/'tools/android_reference/fixtures/defenses.json'


class DefenseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.expected=self.fixture['cases'][0]['expected']['defenses']
        self.actual=dict(fit_id='synthetic',revision=1,defenses=deepcopy(self.expected))
    def check(self,mutate):
        mutate(self.actual)
        with self.assertRaises((AssertionError,KeyError)):defenses(self.expected,self.actual)
    def test_all_original_matrix_and_contribution_witnesses(self):
        values=[r['expected']['defenses'] for r in self.fixture['cases']]+[r['expected'] for r in self.fixture['pattern_edits']['steps']]
        self.assertEqual(18,len(values))
        for value in values:defenses(value,dict(fit_id='synthetic',revision=1,defenses=deepcopy(value)))
    def test_integral_decimal_report_retains_kind(self):
        row=self.actual['defenses']['layers']['shield']['resistances']['em'];row['value']=int(row['value'])
        defenses(self.expected,self.actual)
        row['value_type']='integer'
        with self.assertRaises(AssertionError):defenses(self.expected,self.actual)
    def test_wrong_value_rejected(self):self.check(lambda r:r['defenses']['layers']['shield']['hp'].update(value=999999.0))
    def test_wrong_unit_rejected(self):self.check(lambda r:r['defenses']['layers']['armor']['ehp'].update(unit='GJ'))
    def test_boolean_rejected(self):self.check(lambda r:r['defenses']['layers']['hull']['hp'].update(value=True))
    def test_unavailable_replacement_rejected(self):self.check(lambda r:r['defenses']['total']['hp'].update(value=None,value_type='unavailable',display=None,detail=None))
    def test_missing_resistance_rejected(self):self.check(lambda r:r['defenses']['layers']['shield']['resistances'].pop('em'))
    def test_missing_layer_rejected(self):self.check(lambda r:r['defenses']['layers'].pop('hull'))
    def test_extra_field_rejected(self):self.check(lambda r:r['defenses']['pattern']['em'].update(extra=0))
    def test_changed_contribution_rejected(self):self.check(lambda r:r['defenses']['pattern']['thermal'].update(amount=50))
    def test_wrong_display_rejected(self):self.check(lambda r:r['defenses']['layers']['shield']['multiplier'].update(display='0.00'))
    def test_invalid_identity_revision_rejected(self):
        for key,value in (('fit_id',''),('revision',0),('revision',True)):
            self.setUp();self.check(lambda r:r.update({key:value}))
    def test_typed_input_metadata_must_cover_every_number(self):
        valid=dict(data=dict(weight=1,range_m=0),numeric_types={'root.weight':'integer','root.range_m':'decimal'})
        typed(valid)
        for change in (lambda v:v['numeric_types'].pop('root.weight'),lambda v:v['numeric_types'].update({'root.weight':'text'}),lambda v:v['data'].update(weight=1.25)):
            bad=deepcopy(valid);change(bad)
            with self.assertRaises(AssertionError):typed(bad)
    def test_native_optional_defaults_retain_the_same_fit_state(self):
        spec=deepcopy(self.fixture['cases'][0]['spec']);native=deepcopy(spec)
        native.pop('ignore_restrictions');native.pop('cargo');fit_inputs(spec,native)
        for field,nondefault in (('ignore_restrictions',True),('cargo',[dict(name='Antimatter Charge M',amount=1)])):
            changed=deepcopy(spec);changed[field]=nondefault
            with self.assertRaises(AssertionError):fit_inputs(changed,native)
    def test_missing_or_changed_calculation_input_still_fails(self):
        spec=deepcopy(self.fixture['cases'][0]['spec'])
        for change in (lambda v:v.pop('damage_pattern'),lambda v:v['damage_pattern'].update(emAmount=26),lambda v:v.update(skill_level=0)):
            bad=deepcopy(spec);change(bad)
            with self.assertRaises((AssertionError,KeyError)):fit_inputs(spec,bad)


class FixtureTests(unittest.TestCase):
    def package(self,data):
        self.apk=Path(self.temp.name)/'test.apk'
        with ZipFile(self.apk,'w') as archive:archive.writestr('assets/defenses-expected.json',data)
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.reference=FIXTURE.read_bytes().replace(b'\r\n',b'\n')
    def test_lf_and_crlf_only_equivalence_passes(self):
        for data in (self.reference,self.reference.replace(b'\n',b'\r\n')):
            self.package(data);fixture_bytes(self.apk,self.reference,hashlib.sha256(data).hexdigest(),'defenses-expected.json')
    def test_incorrect_reported_hash_fails(self):
        self.package(self.reference)
        with self.assertRaises(AssertionError):fixture_bytes(self.apk,self.reference,'0'*64,'defenses-expected.json')
    def test_missing_fixture_fails(self):
        self.apk=Path(self.temp.name)/'test.apk'
        with ZipFile(self.apk,'w') as archive:archive.writestr('assets/other.json',self.reference)
        with self.assertRaises(KeyError):fixture_bytes(self.apk,self.reference,hashlib.sha256(self.reference).hexdigest(),'defenses-expected.json')
    def test_changed_content_with_matching_updated_hash_fails(self):
        data=self.reference.replace(b'Uniform incoming',b'Changed incoming',1);assert data!=self.reference
        self.package(data)
        with self.assertRaises(AssertionError):fixture_bytes(self.apk,self.reference,hashlib.sha256(data).hexdigest(),'defenses-expected.json')
    def test_other_whitespace_is_not_normalized(self):
        data=self.reference.replace(b'  ',b'   ',1);self.package(data)
        with self.assertRaises(AssertionError):fixture_bytes(self.apk,self.reference,hashlib.sha256(data).hexdigest(),'defenses-expected.json')


class NativeBoundaryTests(unittest.TestCase):
    def test_all_existing_phase_flags_and_new_defense_phase_keep_storage(self):
        path=ROOT/'android/app/src/androidTest/java/io/github/sussic/pyfa/DiagnosticTestRunner.kt'
        flags=set(re.findall(r'containsKey\("([^"]+)"\)',path.read_text(encoding='utf-8')))
        historical=subprocess.check_output(['git','show','7775b40a5832d263fdb0b16fdfa5961c7c4f1959:android/app/src/androidTest/java/io/github/sussic/pyfa/DiagnosticTestRunner.kt'],cwd=ROOT,text=True)
        self.assertEqual(set(re.findall(r'containsKey\("([^"]+)"\)',historical))|{'c013_phase','c0132_phase'},flags)
        condition=' and '.join(f'{flag!r} not in args' for flag in sorted(flags))
        self.assertTrue(eval(condition,{'args':set()}))
        for flag in flags:self.assertFalse(eval(condition,{'args':{flag}}))
    def test_hash_verified_pull_rejects_truncation_wrong_hash_and_empty(self):
        text=(ROOT/'android/ci/check-defenses.py').read_text(encoding='utf-8');tree=ast.parse(text)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pull')
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'raw.json';data=b'{"passed":true}'
            def run(*args,**kwargs):target.write_bytes(data);return subprocess.CompletedProcess([],0,b'pulled',b'')
            namespace=dict(subprocess=subprocess,hashlib=hashlib,evidence=Path(directory));exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual pull>','exec'),namespace)
            digest=hashlib.sha256(data).hexdigest().encode()
            for size,before,after,passes in ((len(data),digest,digest,True),(len(data)+1,digest,digest,False),(len(data),b'0'*64,b'0'*64,False),(len(data),digest,b'1'*64,False),(0,digest,digest,False)):
                namespace['adb']=unittest.mock.Mock(side_effect=[b'',before,str(size).encode(),after])
                with patch.object(subprocess,'run',side_effect=run):
                    if passes:self.assertEqual(data,namespace['pull']('remote',target))
                    else:
                        with self.assertRaises(AssertionError):namespace['pull']('remote',target)


if __name__=='__main__':unittest.main(verbosity=2)
