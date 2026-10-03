"""Regression checks for the exact revision wait and retained-state recovery."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
import tank_history_retry as retry

class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old={p:subprocess.check_output(['git','show',retry.BEFORE+':'+p],cwd=ROOT,text=True,encoding='utf-8') for p in retry.TRANSFORMS}
        cls.new={p:fn(cls.old[p]) for p,fn in retry.TRANSFORMS.items()}
    def test_exact_fix(self):retry.validate_sources(self.old,self.new,list(self.new))
    # Compare the delivered repair, not later feature additions to the gate plan.
    def test_checked_in_fix(self):retry.validate_sources(self.old,{p:subprocess.check_output(['git','show','e49c7220474509f66d5c4c03005616e8ddeb4dbc:'+p],cwd=ROOT,text=True,encoding='utf-8') for p in self.new},list(self.new))
    def test_unrelated_native_change(self):
        new=dict(self.new);new[retry.PATH]+='\n// unrelated\n'
        with self.assertRaises(AssertionError):retry.validate_sources(self.old,new,list(new))
    def test_removed_functional_assertion(self):
        new=dict(self.new);new[retry.PATH]=new[retry.PATH].replace('assertEquals(230, EngineRuntime.library.value.size)','assertEquals(229, EngineRuntime.library.value.size)')
        with self.assertRaises(AssertionError):retry.validate_sources(self.old,new,list(new))
    def test_timeout_increase(self):
        new=dict(self.new);new[retry.PATH]=new[retry.PATH].replace('compose.waitUntil(60_000)','compose.waitUntil(90_000)')
        with self.assertRaises(AssertionError):retry.validate_sources(self.old,new,list(new))
    def test_old_revision_acceptance(self):
        new=dict(self.new);new[retry.PATH]=new[retry.PATH].replace('fit(id).revision > revision','fit(id).revision >= revision')
        with self.assertRaises(AssertionError):retry.validate_sources(self.old,new,list(new))
    def test_unrelated_product_source(self):
        with self.assertRaises(AssertionError):retry.validate_sources(self.old,self.new,[*self.new,'android_bridge/tank.py'])
    def test_unrelated_fixture_source(self):
        with self.assertRaises(AssertionError):retry.validate_sources(self.old,self.new,[*self.new,'tools/android_reference/fixtures/tank.json'])
    def test_unrelated_launcher_change(self):
        new=dict(self.new);new['android/ci/local_verification.py']+='\n# unrelated\n'
        with self.assertRaises(AssertionError):retry.validate_sources(self.old,new,list(new))

class PackageTests(unittest.TestCase):
    def check(self,changed):
        with tempfile.TemporaryDirectory() as directory:
            old=Path(directory)/'old.apk';new=Path(directory)/'new.apk'
            base={'classes.dex':b'old','assets/tank-expected.json':b'fixture\r\n','AndroidManifest.xml':b'manifest'}
            other=dict(base,**{'classes.dex':b'new'});changed(other)
            for path,contents in ((old,base),(new,other)):
                with ZipFile(path,'w') as archive:
                    for name,value in contents.items():archive.writestr(name,value)
            retry.packages_equal(old,new)
    def test_only_bytecode_changes(self):self.check(lambda _:None)
    def test_changed_fixture_bytes(self):
        with self.assertRaises(AssertionError):self.check(lambda d:d.update({'assets/tank-expected.json':b'fixture\n'}))
    def test_missing_fixture(self):
        with self.assertRaises(AssertionError):self.check(lambda d:d.pop('assets/tank-expected.json'))
    def test_changed_manifest(self):
        with self.assertRaises(AssertionError):self.check(lambda d:d.update({'AndroidManifest.xml':b'changed'}))

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads((ROOT/'tools/android_reference/fixtures/tank.json').read_text(encoding='utf-8'))
        ids=[f'old-{i}' for i in range(189)]
        self.baseline=dict(format=1,dataset_identity='synthetic',fit_order=ids,
            records={i:{'spec':{'name':i},'projections':[]} for i in ids},revisions={i:1 for i in ids},
            modified={i:1 for i in ids},recent=[],sample_id=ids[0],eos_settings={'strictSkillLevels':True})
        self.prior={'saved':{'graph':{'data':copy.deepcopy(self.baseline),'numeric_types':{}}}}
        def types(value,path):
            if type(value) is dict:
                for k,v in value.items():types(v,path+'.'+k)
            elif type(value) is list:
                for i,v in enumerate(value):types(v,f'{path}[{i}]')
            elif type(value) in (int,float):self.prior['saved']['graph']['numeric_types'][path]='integer'
        types(self.baseline,'root')
        self.original=copy.deepcopy(self.baseline)
        for case in self.fixture['cases']:
            for spec in [case['spec']]+([case['source']] if 'source' in case else []):
                i=f'new-{len(self.original["fit_order"])}';self.original['fit_order'].append(i)
                self.original['records'][i]={'spec':{'name':'C01.3.2 '+spec['name']},'projections':[]}
                self.original['revisions'][i]=1;self.original['modified'][i]=2
    def test_only_known_extras_removed(self):
        self.assertEqual(self.baseline,retry.recovery_graph(self.original,self.prior,self.fixture));self.assertEqual(229,len(self.original['fit_order']))
    def rejected(self):
        with self.assertRaises(AssertionError):retry.recovery_graph(self.original,self.prior,self.fixture)
    def test_changed_inherited_record(self):self.original['records']['old-0']['spec']['name']='changed';self.rejected()
    def test_changed_inherited_revision(self):self.original['revisions']['old-0']=2;self.rejected()
    def test_changed_inherited_modified(self):self.original['modified']['old-0']=2;self.rejected()
    def test_changed_inherited_order(self):self.original['fit_order'][:2]=reversed(self.original['fit_order'][:2]);self.rejected()
    def test_unknown_extra(self):self.original['records']['new-189']['spec']['name']='personal fit';self.rejected()
    def test_missing_extra(self):self.original['fit_order'].pop();self.rejected()
    def test_changed_recent(self):self.original['recent']=[{'item':1}];self.rejected()
    def test_changed_settings(self):self.original['eos_settings']['strictSkillLevels']=False;self.rejected()
    def test_changed_dataset(self):self.original['dataset_identity']='changed';self.rejected()
    def test_inherited_edge_to_extra(self):self.original['records']['old-0']['projections']=[{'source_id':'new-189'}];self.rejected()
    def test_numeric_metadata_required(self):self.prior['saved']['graph']['numeric_types'].pop('root.format');self.rejected()

if __name__=='__main__':unittest.main()
