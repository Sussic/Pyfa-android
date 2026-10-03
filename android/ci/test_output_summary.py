"""Focused C02 output schema, units, pure damage, spool and fixture checks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from output_summary import output,summarize,REJECTIONS
from resource_summary import fixture_bytes
from android_bridge.output_inputs import profile,environments,fighters

ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT/'tools/android_reference/fixtures/output.json'


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads(FIXTURE.read_text())
        self.expected=self.fixture['cases'][35]['expected']
        self.actual=dict(fit_id='synthetic',revision=1,**deepcopy(self.expected),target_profile=deepcopy(self.fixture['cases'][35]['spec']['target_profile']))
    def row(self,value):return value['output']['firepower']['effective']['weapon']
    def reject(self,change):
        change(self.actual)
        with self.assertRaises((AssertionError,KeyError)):output(self.expected,self.actual,self.fixture['cases'][35]['spec']['target_profile'])
    def test_complete_original_matrix(self):
        self.assertEqual(37,len(self.fixture['cases']))
        for case in self.fixture['cases']:
            output(case['expected'],dict(fit_id='synthetic',revision=1,**deepcopy(case['expected']),target_profile=case['spec']['target_profile']),case['spec']['target_profile'])
    def test_wrong_value(self):self.reject(lambda r:self.row(r)['current'].update(value=99999))
    def test_boolean_scalar(self):self.reject(lambda r:self.row(r)['current'].update(value=True))
    def test_wrong_kind(self):self.reject(lambda r:self.row(r)['current'].update(value_type='integer'))
    def test_wrong_unit(self):self.reject(lambda r:self.row(r)['current'].update(unit='HP/s'))
    def test_wrong_display(self):self.reject(lambda r:self.row(r)['current'].update(display='incorrect'))
    def test_unavailable_replacement(self):self.reject(lambda r:self.row(r)['current'].update(value=None,value_type='unavailable',display=None,detail=None))
    def test_wrong_target_profile(self):self.reject(lambda r:r['target_profile'].update(hp=20000.0))
    def test_pure_hp_limit(self):self.reject(lambda r:self.row(r)['damage']['pure']['amount'].update(value=250.0))
    def test_missing_damage(self):self.reject(lambda r:self.row(r)['damage'].pop('thermal'))
    def test_spool_endpoint(self):self.reject(lambda r:self.row(r)['pre'].update(value=123456.0))
    def test_spool_indication(self):self.reject(lambda r:self.row(r).update(indicated=True))
    def test_extra_field(self):self.reject(lambda r:r['output'].update(extra=0))
    def test_wrong_bomb_level(self):self.reject(lambda r:r['output']['bombing']['levels'][0].update(covert_ops_level=5))
    def test_wrong_bomb_count(self):self.reject(lambda r:r['output']['bombing']['levels'][0]['counts']['em'].update(value=99.0))
    def test_missing_bomb_type(self):self.reject(lambda r:r['output']['bombing']['levels'][0]['counts'].pop('kinetic'))
    def test_mining_hour_unit(self):self.reject(lambda r:r['output']['mining']['module']['yield_hour'].update(unit='m³/s'))
    def test_outgoing_unit(self):self.reject(lambda r:r['output']['outgoing']['capacitor']['current'].update(unit='HP/s'))
    def test_wrong_revision(self):
        for value in (0,True,1.0):
            self.setUp();self.reject(lambda r:r.update(revision=value))


class InputTests(unittest.TestCase):
    def setUp(self):self.value=json.loads(FIXTURE.read_text())['cases'][35]['spec']['target_profile']
    def test_valid_profiles(self):
        profile(None);profile(self.value)
        for x in (0.0,1.0):profile({**self.value,'emAmount':x})
    def test_invalid_profiles(self):
        for key,bad in (('emAmount',True),('emAmount',1.1),('emAmount',-.1),('hp',0),('signatureRadius',0),('radius',-1),('maxVelocity',float('inf'))):
            with self.subTest(key=key,value=bad),self.assertRaises(ValueError):profile({**self.value,key:bad})
        with self.assertRaises(ValueError):profile({})
        with self.assertRaises(ValueError):profile({**self.value,'extra':0})
    def test_environment_inputs(self):
        environments([]);environments([dict(name='Class 6 Red Giant Effects',state='ONLINE')])
        for rows in ([dict(name='unrelated',state='ONLINE')],[dict(name='Class 6 Red Giant Effects',state='ACTIVE')],
                     [dict(name='Class 6 Red Giant Effects',state='ONLINE')]*2):
            with self.assertRaises(ValueError):environments(rows)
    def test_fighter_inputs(self):
        fighters([]);fighters([dict(name='Templar I',amount=1,active=True)])
        for amount,active in ((True,True),(0,True),(1,1),(1.0,True)):
            with self.assertRaises(ValueError):fighters([dict(name='Templar I',amount=amount,active=active)])


class FixtureTests(unittest.TestCase):
    def test_exact_packaged_hash_and_lf_crlf_only(self):
        reference=FIXTURE.read_bytes().replace(b'\r\n',b'\n')
        with tempfile.TemporaryDirectory() as directory:
            apk=Path(directory)/'test.apk'
            for data,accepted in ((reference,True),(reference.replace(b'\n',b'\r\n'),True),
                                  (reference.replace(b'Empty output',b'Changed output',1),False),
                                  (reference.replace(b'  ',b'   ',1),False)):
                with ZipFile(apk,'w') as archive:archive.writestr('assets/output-expected.json',data)
                if accepted:fixture_bytes(apk,reference,hashlib.sha256(data).hexdigest(),'output-expected.json')
                else:
                    with self.assertRaises(AssertionError):fixture_bytes(apk,reference,hashlib.sha256(data).hexdigest(),'output-expected.json')
                with self.assertRaises(AssertionError):fixture_bytes(apk,reference,'0'*64,'output-expected.json')
            with ZipFile(apk,'w') as archive:archive.writestr('assets/other.json',reference)
            with self.assertRaises(KeyError):fixture_bytes(apk,reference,hashlib.sha256(reference).hexdigest(),'output-expected.json')


class SummaryTests(unittest.TestCase):
    def inputs(self):
        from test_tank_summary import SummaryTests as Typed
        typed=Typed().typed
        fixture=json.loads(FIXTURE.read_text())
        engine=dict(desktop_source_commit=fixture['source_commit'],database_logical_sha256='logical',engine_source_sha256='engine',source_data_sha256='data',eos_settings=fixture['eos_settings'])
        graph=dict(sample_id='prior-0',fit_order=[],records={},revisions={},modified={},recent=[],dataset_identity='logical',eos_settings=fixture['eos_settings'])
        snapshots=[]
        def add(key,spec,revision=1):
            spec=deepcopy(spec);spec['name']='C02 '+spec['name']
            graph['fit_order'].append(key);graph['records'][key]=dict(spec=spec,skills={},implants=[],projections=[],commands=[]);graph['revisions'][key]=revision;graph['modified'][key]=0
            snapshots.append(dict(id=key,name=spec['name'],ship=spec['ship'],revision=revision,skills={},implants=[],projections=[],commands=[],modules=[dict(index=i,**m) for i,m in enumerate(spec['modules'])]))
        for i in range(230):add('prior-'+str(i),fixture['cases'][0]['spec'])
        before=deepcopy(graph);inherited=deepcopy(snapshots);ids=[];values=[]
        for i,case in enumerate(fixture['cases']):
            key='target-'+str(i);ids.append(key);revision=7 if i==35 else 1;add(key,case['spec'],revision)
            values.append(dict(fit_id=key,revision=revision,**deepcopy(case['expected']),target_profile=deepcopy(case['spec']['target_profile'])))
        add('copy',fixture['cases'][35]['spec']);graph['records']['copy']['spec']['name']='C02 copy';snapshots[-1]['name']='C02 copy'
        copied=dict(fit_id='copy',revision=1,**deepcopy(fixture['cases'][35]['expected']),target_profile=deepcopy(fixture['cases'][35]['spec']['target_profile']))
        changed=dict(fit_id=ids[35],revision=2,**deepcopy(fixture['cases'][36]['expected']),target_profile=deepcopy(fixture['cases'][36]['spec']['target_profile']))
        redo=deepcopy(changed);redo['revision']=4
        cleared=deepcopy(values[35]);cleared.update(revision=6,target_profile=None);cleared['output']['effective']=False;cleared['output']['firepower']['effective']=deepcopy(cleared['output']['firepower']['raw'])
        saved=dict(pid=100,ids=ids,inherited=typed(inherited),inherited_graph=typed(before),graph=typed(graph),all_fits=typed(snapshots),
            edits=[dict(action='profile_hp',after=changed,redo=redo),dict(action='profile_clear',after=cleared,restored=deepcopy(values[35]))],copy_id='copy',copy_output=copied,outputs=values)
        start=dict(manifest={k:v for k,v in engine.items() if k!='eos_settings'},eos_settings=fixture['eos_settings'],persistence=dict(enabled=True,opened_existing=True))
        common=dict(task='C02',runtime_start=start,ids=ids,saved=saved,copy_observation=copied,fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),observations=[dict(case=i,actual=deepcopy(v)) for i,v in enumerate(values)])
        prepared=dict(**deepcopy(common),phase='prepare',pid=100,protocol_rejections=REJECTIONS);prepared['observations'][35]['actual']['revision']=1
        return [prepared,dict(**deepcopy(common),phase='restored',pid=101,protocol_rejections=[])],engine
    def test_complete_summary_and_corruptions(self):
        from unittest.mock import patch
        reports,engine=self.inputs()
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'native').mkdir();(run/'apks').mkdir()
            with ZipFile(run/'apks/app-debug-androidTest.apk','w') as archive:archive.writestr('assets/output-expected.json',FIXTURE.read_bytes())
            with patch('output_summary.evidence_dir',return_value=run/'native'):
                self.assertTrue(summarize(reports,engine,{99})['complete'])
                changes={
                    'hash':lambda r:r[0].update(fixture_sha256='0'*64),
                    'pid':lambda r:r[1].update(pid=100),
                    'manifest':lambda r:r[0]['runtime_start']['manifest'].update(engine_source_sha256='wrong'),
                    'settings':lambda r:r[0]['runtime_start']['eos_settings'].update(globalDefaultSpoolupPercentage=.5),
                    'restart':lambda r:r[1]['runtime_start']['persistence'].update(opened_existing=False),
                    'missing_case':lambda r:r[0]['observations'].pop(),
                    'case_order':lambda r:r[0]['observations'][0].update(case=1),
                    'history_revision':lambda r:r[0]['observations'][35]['actual'].update(revision=2),
                    'unedited_revision':lambda r:r[0]['observations'][0]['actual'].update(revision=2),
                    'restored_revision':lambda r:r[1]['observations'][35]['actual'].update(revision=1),
                    'recent':lambda r:r[0]['saved']['graph']['data'].update(recent=[3530]),
                    'inherited':lambda r:r[0]['saved']['all_fits']['data'][0].update(name='changed'),
                    'inherited_kind':lambda r:r[0]['saved']['graph']['numeric_types'].update({'root.revisions.prior-0':'decimal'}),
                    'fighter':lambda r:r[0]['saved']['graph']['data']['records']['target-11']['spec']['fighters'][0].update(active=False),
                    'environment':lambda r:r[0]['saved']['graph']['data']['records']['target-28']['spec']['environments'][0].update(state='OFFLINE'),
                    'profile':lambda r:r[0]['saved']['outputs'][35]['target_profile'].update(hp=20000.0),
                    'edit':lambda r:r[0]['saved']['edits'][0].update(action='wrong'),
                    'edit_revision':lambda r:r[0]['saved']['edits'][0]['after'].update(revision=3),
                    'copy':lambda r:r[0]['copy_observation'].update(fit_id='wrong'),
                    'guards':lambda r:r[0].update(protocol_rejections=[]),
                    'missing_metadata':lambda r:r[0]['saved']['graph']['numeric_types'].pop('root.revisions.target-35'),
                }
                for name,change in changes.items():
                    with self.subTest(name=name):
                        bad=deepcopy(reports);change(bad)
                        with self.assertRaises((AssertionError,KeyError)):summarize(bad,engine,{99})


if __name__=='__main__':unittest.main()
