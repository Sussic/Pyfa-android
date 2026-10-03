"""Focused C01.3.2 tank precision, shape, spool and APK fixture regressions."""
from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import sys
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tank_summary import tank, summarize, REJECTIONS
from resource_summary import fixture_bytes

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT/'tools/android_reference/fixtures/tank.json'


class TankTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.expected = self.fixture['cases'][23]['expected']
        assert self.expected['tank']['raw']['reinforced']['armor_spool']['indicated']
        self.actual = dict(fit_id='synthetic', revision=1, **deepcopy(self.expected))
    def check(self, change):
        change(self.actual)
        with self.assertRaises((AssertionError, KeyError)):
            tank(self.expected, self.actual)
    def row(self, result): return result['tank']['raw']['reinforced']['repairs']['armorRepair']
    def spool(self, result): return result['tank']['raw']['reinforced']['armor_spool']
    def test_all_original_matrix(self):
        self.assertEqual(29, len(self.fixture['cases']))
        for case in self.fixture['cases']:
            tank(case['expected'], dict(fit_id='synthetic', revision=1, **deepcopy(case['expected'])))
    def test_wrong_value(self): self.check(lambda r: self.row(r).update(value=999999.0))
    def test_boolean_value(self): self.check(lambda r: self.row(r).update(value=True))
    def test_wrong_unit(self): self.check(lambda r: self.row(r).update(unit='GJ/s'))
    def test_missing_repair(self): self.check(lambda r: r['tank']['effective']['sustained']['repairs'].pop('hullRepair'))
    def test_extra_field(self): self.check(lambda r: r['tank']['raw'].update(extra=0))
    def test_wrong_scalar_kind(self): self.check(lambda r: self.row(r).update(value_type='integer'))
    def test_wrong_display(self): self.check(lambda r: self.row(r).update(display='0.0'))
    def test_invalid_identity_revision(self):
        for key, value in (('fit_id', ''), ('revision', 0), ('revision', True)):
            self.setUp(); self.check(lambda r: r.update({key: value}))
    def test_spool_flag_and_tooltip(self):
        self.check(lambda r: self.spool(r).update(indicated=False))
        self.setUp(); self.check(lambda r: self.spool(r).update(indicated=1))
        self.setUp(); self.check(lambda r: self.spool(r).update(tooltip=''))
    def test_spool_endpoint(self): self.check(lambda r: self.spool(r)['pre'].update(value=0))
    def test_unavailable_replacement(self): self.check(lambda r: self.row(r).update(value=None,value_type='unavailable',display=None,detail=None))


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.apk = Path(self.temp.name)/'test.apk'
        self.reference = FIXTURE.read_bytes().replace(b'\r\n',b'\n')
    def package(self, data):
        with ZipFile(self.apk, 'w') as archive: archive.writestr('assets/tank-expected.json',data)
    def test_lf_crlf_equivalence(self):
        for data in (self.reference, self.reference.replace(b'\n',b'\r\n')):
            self.package(data); fixture_bytes(self.apk,self.reference,hashlib.sha256(data).hexdigest(),'tank-expected.json')
    def test_wrong_reported_hash(self):
        self.package(self.reference)
        with self.assertRaises(AssertionError): fixture_bytes(self.apk,self.reference,'0'*64,'tank-expected.json')
    def test_missing_fixture(self):
        with ZipFile(self.apk,'w') as archive: archive.writestr('assets/other.json',self.reference)
        with self.assertRaises(KeyError): fixture_bytes(self.apk,self.reference,hashlib.sha256(self.reference).hexdigest(),'tank-expected.json')
    def test_changed_content_even_with_updated_hash(self):
        data=self.reference.replace(b'Empty tank',b'Changed tank',1); assert data!=self.reference
        self.package(data)
        with self.assertRaises(AssertionError): fixture_bytes(self.apk,self.reference,hashlib.sha256(data).hexdigest(),'tank-expected.json')
    def test_other_whitespace_rejected(self):
        data=self.reference.replace(b'  ',b'   ',1); self.package(data)
        with self.assertRaises(AssertionError): fixture_bytes(self.apk,self.reference,hashlib.sha256(data).hexdigest(),'tank-expected.json')


class SummaryTests(unittest.TestCase):
    def typed(self, data):
        result = dict(data=deepcopy(data), numeric_types={})
        def walk(value, path):
            if type(value) is dict:
                for key, row in value.items(): walk(row, path+'.'+key)
            elif type(value) is list:
                for index, row in enumerate(value): walk(row, f'{path}[{index}]')
            elif type(value) in (int,float): result['numeric_types'][path] = 'integer' if type(value) is int else 'decimal'
        walk(data, 'root'); return result
    def inputs(self):
        fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
        engine = dict(desktop_source_commit=fixture['source_commit'], database_logical_sha256='logical',
            engine_source_sha256='engine', source_data_sha256='data', eos_settings=fixture['eos_settings'])
        graph = dict(sample_id='prior-0', fit_order=[], records={}, revisions={}, modified={}, recent=[],
                     dataset_identity='logical', eos_settings=fixture['eos_settings'])
        snapshots=[]
        def add(key, spec, edges=()):
            spec=deepcopy(spec); spec['name']='C01.3.2 '+spec['name']
            graph['fit_order'].append(key); graph['records'][key]=dict(spec=spec, skills={}, implants=[], projections=list(edges), commands=[])
            graph['revisions'][key]=1; graph['modified'][key]=0
            snapshots.append(dict(id=key, name=spec['name'], ship=spec['ship'], revision=1, skills={}, implants=[], commands=[], projections=list(edges),
                modules=[dict(index=i,**m) for i,m in enumerate(spec['modules'])]))
        for index in range(189): add('prior-'+str(index), fixture['cases'][0]['spec'])
        before=deepcopy(graph); inherited=deepcopy(snapshots)
        ids=[]; sources={}; values=[]
        for index, case in enumerate(fixture['cases']):
            key='target-'+str(index); ids.append(key); edges=[]
            if 'source' in case:
                source='source-'+str(index); sources[key]=source; add(source,case['source'])
                edges=[dict(source_id=source,**case['projection'])]
            add(key,case['spec'],edges)
            values.append(dict(fit_id=key, revision=1, **deepcopy(case['expected'])))
        copied=deepcopy(graph['records'][ids[23]]);copied['spec']['name']='C01.3.2 copy'
        graph['fit_order'].append('copy');graph['records']['copy']=copied;graph['revisions']['copy']=1;graph['modified']['copy']=0
        snap=deepcopy(next(s for s in snapshots if s['id']==ids[23]));snap.update(id='copy',name='C01.3.2 copy');snapshots.append(snap)
        edits=[]
        for action,index,owner in zip(('offline','remove_module','remove_projection'),(6,0,24),(4,4,23)):
            after=dict(fit_id=ids[owner],revision=2,**deepcopy(fixture['cases'][index]['expected']))
            redo=deepcopy(after);redo['revision']=4;edits.append(dict(action=action,after=after,redo=redo))
        copy=dict(fit_id='copy',revision=1,**deepcopy(fixture['cases'][23]['expected']))
        saved=dict(pid=100, ids=ids, sources=sources, inherited=self.typed(inherited), inherited_graph=self.typed(before), graph=self.typed(graph),
            all_fits=self.typed(snapshots), edits=edits, copy_id='copy', copy_tank=copy, tanks=values)
        start=dict(manifest={k:v for k,v in engine.items() if k!='eos_settings'}, eos_settings=engine['eos_settings'], persistence=dict(enabled=True,opened_existing=True))
        common=dict(task='C01.3.2',runtime_start=start,ids=ids,saved=saved,copy_observation=copy,fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            observations=[dict(case=i,actual=deepcopy(v)) for i,v in enumerate(values)])
        return [dict(**deepcopy(common),phase='prepare',pid=100,protocol_rejections=REJECTIONS),
                dict(**deepcopy(common),phase='restored',pid=101,protocol_rejections=[])], engine
    def test_complete_summary_and_corruptions(self):
        reports,engine=self.inputs()
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'native').mkdir();(run/'apks').mkdir()
            with ZipFile(run/'apks/app-debug-androidTest.apk','w') as archive: archive.writestr('assets/tank-expected.json',FIXTURE.read_bytes())
            with patch('tank_summary.evidence_dir',return_value=run/'native'):
                self.assertTrue(summarize(reports,engine,{99})['complete'])
                changes={
                    'hash':lambda r:r[0].update(fixture_sha256='0'*64),
                    'pid':lambda r:r[1].update(pid=100),
                    'old_pid':lambda r:r[0].update(pid=99),
                    'manifest':lambda r:r[0]['runtime_start']['manifest'].update(engine_source_sha256='wrong'),
                    'settings':lambda r:r[0]['runtime_start']['eos_settings'].update(globalDefaultSpoolupPercentage=0.0),
                    'ephemeral':lambda r:r[0]['runtime_start']['persistence'].update(enabled=False),
                    'guards':lambda r:r[0].update(protocol_rejections=[]),
                    'missing':lambda r:r[0]['observations'].pop(),
                    'case':lambda r:r[0]['observations'][0].update(case=1),
                    'value':lambda r:r[0]['observations'][23]['actual']['tank']['raw']['reinforced']['repairs']['armorRepair'].update(value=9999),
                    'spool':lambda r:r[0]['observations'][23]['actual']['tank']['raw']['reinforced']['armor_spool'].update(indicated=False),
                    'inherited':lambda r:r[0]['saved']['all_fits']['data'][0].update(name='changed'),
                    'graph':lambda r:r[0]['saved']['graph']['data']['records']['prior-0']['spec'].update(name='changed'),
                    'type':lambda r:r[0]['saved']['graph']['numeric_types'].update({'root.revisions.prior-0':'decimal'}),
                    'source':lambda r:r[0]['saved']['sources'].update({'target-23':'source-24'}),
                    'projection':lambda r:r[0]['saved']['graph']['data']['records']['target-23']['projections'][0].update(amount=2),
                    'copy':lambda r:r[0]['saved']['copy_tank'].update(fit_id='target-23'),
                    'saved':lambda r:r[1]['saved']['tanks'][0].update(revision=2),
                    'edit':lambda r:r[0]['saved']['edits'][0]['after']['tank']['raw']['reinforced']['repairs']['armorRepair'].update(value=9999),
                }
                for name,change in changes.items():
                    with self.subTest(name=name):
                        bad=deepcopy(reports);change(bad)
                        with self.assertRaises((AssertionError,KeyError)):summarize(bad,engine,{99})


class NativeBoundaryTests(unittest.TestCase):
    def test_new_phase_preserves_all_existing_persistent_flags(self):
        path='android/app/src/androidTest/java/io/github/sussic/pyfa/DiagnosticTestRunner.kt'
        previous=subprocess.check_output(['git','show','2d941fd9:'+path],cwd=ROOT,text=True,encoding='utf-8')
        current=(ROOT/path).read_text(encoding='utf-8')
        flags=lambda text:set(re.findall(r'containsKey\("([^"]+)"\)',text))
        self.assertEqual(flags(previous)|{'c0132_phase'}, flags(current))
        condition=' and '.join(f'{flag!r} not in args' for flag in sorted(flags(current)))
        self.assertTrue(eval(condition,{'args':set()}))
        for flag in flags(current): self.assertFalse(eval(condition,{'args':{flag}}))
    def test_new_fixture_is_staged_and_required_gates_are_added(self):
        text=(ROOT/'android/prepare-engine.py').read_text(encoding='utf-8')
        self.assertIn('fixtures/tank.json", tests / "tank-expected.json"',text)
        from local_verification import plan
        self.assertIn('reference:tank',plan('full',None));self.assertIn('headless:tank',plan('full',None))
        self.assertIn('native:tank-prepare',plan('full',None));self.assertIn('native:tank-restored',plan('full',None))
        self.assertEqual(105,len(plan('full',None)))
    def test_hash_verified_pull_rejects_truncation_wrong_hash_and_empty(self):
        text=(ROOT/'android/ci/check-tank.py').read_text(encoding='utf-8');tree=ast.parse(text)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pull')
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'raw.json';data=b'{"passed":true}'
            def run(*args,**kwargs):target.write_bytes(data);return subprocess.CompletedProcess([],0,b'pulled',b'')
            namespace=dict(subprocess=subprocess,hashlib=hashlib,evidence=Path(directory))
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual pull>','exec'),namespace)
            digest=hashlib.sha256(data).hexdigest().encode()
            for size,before,after,passes in ((len(data),digest,digest,True),(len(data)+1,digest,digest,False),
                                           (len(data),b'0'*64,b'0'*64,False),(len(data),digest,b'1'*64,False),(0,digest,digest,False)):
                namespace['adb']=unittest.mock.Mock(side_effect=[b'',before,str(size).encode(),after])
                with patch.object(subprocess,'run',side_effect=run):
                    if passes:self.assertEqual(data,namespace['pull']('remote',target))
                    else:
                        with self.assertRaises(AssertionError):namespace['pull']('remote',target)


if __name__ == '__main__': unittest.main()
