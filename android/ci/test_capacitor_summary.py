"""Focused C01.2 regressions: byte identity, raw types, units and presentation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sys
from zipfile import ZipFile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from capacitor_summary import capacitor, summarize, REJECTIONS
from resource_summary import fixture_bytes

FIXTURE = Path(__file__).resolve().parents[2]/'tools/android_reference/fixtures/capacitor.json'


class CapacitorValidationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.expected = self.fixture['cases'][5]['expected']
        self.actual = {k:deepcopy(self.expected[k]) for k in ('capacitor','stability')}
        self.actual.update(fit_id='synthetic',revision=1)

    def test_all_independent_rows_pass_and_whole_decimal_transport_retains_kind(self):
        for row in self.fixture['cases']:
            actual={k:deepcopy(row['expected'][k]) for k in ('capacitor','stability')}
            actual.update(fit_id='synthetic',revision=1)
            capacitor(row['expected'],actual)
        row=self.actual['capacitor']['capacity']
        if row['value_type']=='decimal' and row['value'].is_integer():row['value']=int(row['value'])
        capacitor(self.expected,self.actual)

    def test_corrupted_values_types_units_display_and_structure_fail(self):
        changes={
            'value':lambda a:a['capacitor']['capacity'].update(value=1.0),
            'bool':lambda a:a['capacitor']['capacity'].update(value=True),
            'kind':lambda a:a['capacitor']['capacity'].update(value_type='integer'),
            'unit':lambda a:a['capacitor']['capacity'].update(unit='MW'),
            'display':lambda a:a['capacitor']['delta'].update(display='0'),
            'missing':lambda a:a['capacitor'].pop('use'),
            'extra':lambda a:a.update(extra=True),
            'state_kind':lambda a:a['stability'].update(kind='depletion'),
            'state_unit':lambda a:a['stability'].update(unit='s'),
            'state_value':lambda a:a['stability'].update(values=[0]),
            'state_type':lambda a:a['stability'].update(value_types=['boolean']),
            'revision':lambda a:a.update(revision=True),
            'null':lambda a:a['capacitor']['capacity'].update(value=None)}
        for name,change in changes.items():
            with self.subTest(name=name):
                actual=deepcopy(self.actual);change(actual)
                with self.assertRaises((AssertionError,KeyError)):capacitor(self.expected,actual)

    def test_null_effective_values_remain_null(self):
        expected=self.fixture['cases'][0]['expected']
        actual={k:deepcopy(expected[k]) for k in ('capacitor','stability')};actual.update(fit_id='empty',revision=1)
        capacitor(expected,actual)
        actual['capacitor']['effective_capacity']['value']=0
        with self.assertRaises(AssertionError):capacitor(expected,actual)

    def packaged(self, packaged, reference, reported=None, missing=False):
        with tempfile.TemporaryDirectory() as directory:
            apk=Path(directory)/'test.apk'
            with ZipFile(apk,'w') as archive:
                if not missing:archive.writestr('assets/capacitor-expected.json',packaged)
            return fixture_bytes(apk,reference,reported or hashlib.sha256(packaged).hexdigest(),'capacitor-expected.json')

    def test_lf_crlf_only_equivalence_passes(self):
        reference=FIXTURE.read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(self.fixture,self.packaged(reference.replace(b'\n',b'\r\n'),reference))

    def test_wrong_reported_hash_fails(self):
        reference=FIXTURE.read_bytes()
        with self.assertRaises(AssertionError):self.packaged(reference,reference,'0'*64)

    def test_missing_fixture_fails(self):
        with self.assertRaises(KeyError):self.packaged(b'',FIXTURE.read_bytes(),missing=True)

    def test_changed_content_with_matching_reported_hash_fails(self):
        reference=FIXTURE.read_bytes();changed=reference.replace(b'Empty capacitor',b'Other capacitor')
        self.assertNotEqual(reference,changed)
        with self.assertRaises(AssertionError):self.packaged(changed,reference)

    def test_other_whitespace_is_not_ignored(self):
        reference=FIXTURE.read_bytes()
        with self.assertRaises(AssertionError):self.packaged(reference+b' ',reference)

    def test_json_equivalence_does_not_bypass_exact_bytes(self):
        reference=FIXTURE.read_bytes();changed=json.dumps(self.fixture,sort_keys=True).encode()
        with self.assertRaises(AssertionError):self.packaged(changed,reference)

    def summary_inputs(self):
        inherited=[dict(id='prior-'+str(i),name='prior-'+str(i)) for i in range(158)]
        snapshots=deepcopy(inherited);ids=[];values=[]
        def snapshot(spec,identifier):
            return dict(id=identifier,name='C01.2 '+spec['name'],ship=spec['ship'],skills={},implants=[],commands=[],
                modules=[dict(index=i,**row) for i,row in enumerate(spec['modules'])],projections=[])
        for index,row in enumerate(self.fixture['cases']):
            identifier='target-'+str(index);ids.append(identifier)
            target=snapshot(row['spec'],identifier);snapshots.append(target)
            if 'source' in row:
                sender='source-'+str(index);snapshots.append(snapshot(row['source'],sender))
                target['projections']=[dict(source_id=sender,**row['projection'])]
            actual={k:deepcopy(row['expected'][k]) for k in ('capacitor','stability')}
            actual.update(fit_id=identifier,revision=1);values.append(actual)
        copied=deepcopy(snapshots[163]);copied.update(id='copy',name='C01.2 copy');snapshots.append(copied)
        saved=dict(pid=100,ids=ids,inherited=dict(data=inherited),all_fits=dict(data=snapshots),capacitors=values)
        engine=dict(desktop_source_commit=self.fixture['source_commit'],database_logical_sha256='logical',
            engine_source_sha256='engine',source_data_sha256='data',eos_settings=self.fixture['eos_settings'])
        start=dict(manifest={k:v for k,v in engine.items() if k!='eos_settings'},eos_settings=engine['eos_settings'],
            persistence=dict(enabled=True,opened_existing=True))
        common=dict(task='C01.2',runtime_start=start,ids=ids,saved=saved,fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        reports=[dict(**deepcopy(common),phase='prepare',pid=100,protocol_rejections=REJECTIONS,
            observations=[dict(case=i,actual=deepcopy(row)) for i,row in enumerate(values)]),
            dict(**deepcopy(common),phase='restored',pid=101,protocol_rejections=[],observations=[dict(actual=deepcopy(row)) for row in values])]
        return reports,engine

    def test_complete_summary_consistency_passes_and_corruption_fails(self):
        reports,engine=self.summary_inputs()
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'native').mkdir();(run/'apks').mkdir()
            with ZipFile(run/'apks/app-debug-androidTest.apk','w') as archive:
                archive.writestr('assets/capacitor-expected.json',FIXTURE.read_bytes())
            with patch('capacitor_summary.evidence_dir',return_value=run/'native'):
                self.assertTrue(summarize(reports,engine,{99})['complete'])
                corruptions={
                    'manifest':lambda r:r[0]['runtime_start']['manifest'].update(engine_source_sha256='wrong'),
                    'hash':lambda r:r[0].update(fixture_sha256='0'*64),
                    'pid':lambda r:r[1].update(pid=100),
                    'saved':lambda r:r[1]['saved']['capacitors'][0].update(revision=2),
                    'protocol':lambda r:r[0].update(protocol_rejections=[]),
                    'inherit':lambda r:r[0]['saved']['all_fits']['data'][0].update(name='changed'),
                    'module':lambda r:r[0]['saved']['all_fits']['data'][159]['modules'][0].update(name='wrong'),
                    'projection':lambda r:r[0]['saved']['all_fits']['data'][167]['projections'][0].update(amount=2),
                    'copy':lambda r:r[0]['saved']['all_fits']['data'][-1].update(ship='wrong')}
                for name,change in corruptions.items():
                    with self.subTest(name=name):
                        bad=deepcopy(reports);change(bad)
                        with self.assertRaises((AssertionError,KeyError)):summarize(bad,engine,{99})


if __name__=='__main__':unittest.main()
