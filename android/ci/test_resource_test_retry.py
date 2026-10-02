"""Reject unrelated source changes and any recovery outside this failed pair."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'android/ci')]
from resource_test_retry import PATH,EXTRA_IDS,recovery_graph,validate_sources,updated_launcher,updated_reporter,assets_equal

class ResourceRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths=(PATH,'android/ci/local_verification.py','android/ci/report_local.py')
        cls.old={path:subprocess.check_output(['git','show','e0e01d9b0c0246ffaa26ba822d5d7e1897e9bd1c:'+path],cwd=ROOT) for path in paths}
        old='                    val copy = send(BridgeOperation.DuplicateFit(id,"C01.1 copy"),id).fits.first { it.id != id }.id\n'
        new='                    val beforeCopy = EngineRuntime.library.value.map { it.id }.toSet()\n                    val copy = send(BridgeOperation.DuplicateFit(id,"C01.1 copy"),id).fits.single { it.id !in beforeCopy }.id\n                    assertEquals("C01.1 copy",fit(copy).name)\n'
        cls.new={PATH:cls.old[PATH].decode().replace(old,new,1).encode(),
                 'android/ci/local_verification.py':updated_launcher(cls.old['android/ci/local_verification.py'].decode()).encode(),
                 'android/ci/report_local.py':updated_reporter(cls.old['android/ci/report_local.py'].decode()).encode()}

    def setUp(self):
        ids=[f'baseline-{i}' for i in range(147)]
        self.prior={'after':{'data':[{'id':identifier,'revision':1} for identifier in ids]},'recent_after':[123]}
        records={identifier:{'projections':[],'commands':[],'spec':{'name':identifier}} for identifier in ids}
        for identifier,name in zip(EXTRA_IDS,['C01.1 Empty cruiser','C01.1 copy']):
            records[identifier]={'commands':[],'implants':[],'projections':[],'skills':{},'spec':{
                'boosters':[],'commands':[],'damage_pattern':{'emAmount':25,'explosiveAmount':25,'kineticAmount':25,'thermalAmount':25},
                'drones':[],'environments':[],'factor_reload':False,'implants':[],'modules':[],
                'name':name,'projections':[],'security':{'pilot':0,'system':'HISEC'},
                'ship':'Vexor','skill_level':5,'target_profile':None}}
        self.graph={'fit_order':ids+EXTRA_IDS,'records':records,'revisions':dict.fromkeys(ids+EXTRA_IDS,1),
                    'modified':dict.fromkeys(ids+EXTRA_IDS,2.0),'sample_id':ids[0],'recent':[123],
                    'dataset_identity':{'source':'synthetic'},'eos_settings':{'preserve':True}}

    def test_exact_source_correction_passes(self): validate_sources(self.old,self.new,list(self.new))

    def test_unrelated_test_assertion_fails(self):
        bad=deepcopy(self.new);bad[PATH]+=b'// unrelated change\n'
        with self.assertRaises(AssertionError):validate_sources(self.old,bad,list(bad))

    def test_unrelated_launcher_or_reporter_change_fails(self):
        for path in ('android/ci/local_verification.py','android/ci/report_local.py'):
            bad=deepcopy(self.new);bad[path]+=b'print("unrelated")\n'
            with self.subTest(path=path),self.assertRaises(AssertionError):validate_sources(self.old,bad,list(bad))

    def test_unrelated_product_file_fails(self):
        with self.assertRaises(AssertionError):validate_sources(self.old,self.new,list(self.new)+['android_bridge/resources.py'])

    def test_remove_only_known_pair_and_preserve_all_old_inputs(self):
        before=deepcopy(self.graph);new=recovery_graph(self.graph,self.prior)
        self.assertEqual(self.graph,before);self.assertEqual(len(new['fit_order']),147)
        for field in ('records','revisions','modified'):
            self.assertEqual(new[field],{key:before[field][key] for key in new['fit_order']})
        for field in ('sample_id','recent','dataset_identity','eos_settings'):self.assertEqual(new[field],before[field])

    def test_changed_extra_inputs_or_ids_fail(self):
        bad=deepcopy(self.graph);bad['records'][EXTRA_IDS[0]]['spec']['ship']='Caracal'
        with self.assertRaises(AssertionError):recovery_graph(bad,self.prior)
        bad=deepcopy(self.graph);bad['fit_order'][-1]='unexpected'
        with self.assertRaises(AssertionError):recovery_graph(bad,self.prior)

    def test_original_revision_links_order_or_recent_change_fails(self):
        for change in (lambda g:g['revisions'].__setitem__('baseline-0',2),
                       lambda g:g['records']['baseline-0']['commands'].append({'source_id':EXTRA_IDS[0]}),
                       lambda g:g['fit_order'].__setitem__(slice(0,2),list(reversed(g['fit_order'][:2]))),
                       lambda g:g.__setitem__('recent',[999])):
            bad=deepcopy(self.graph);change(bad)
            with self.assertRaises(AssertionError):recovery_graph(bad,self.prior)

    def test_packaged_fixtures_must_stay_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            left=Path(directory)/'old.apk';right=Path(directory)/'new.apk'
            for path in (left,right):
                with ZipFile(path,'w') as archive:archive.writestr('assets/fixture.json',b'{"same":true}\r\n')
            assets_equal(left,right)
            with ZipFile(right,'w') as archive:archive.writestr('assets/fixture.json',b'{"same":true}\n')
            with self.assertRaises(AssertionError):assets_equal(left,right)

if __name__=='__main__':unittest.main()
