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
from resource_test_retry import PATH,EXTRA_IDS,recovery_graph,validate_sources,updated_launcher,updated_reporter,assets_equal,SLOT_IDS,placement_graph,slot_reporter,KIND_IDS,kind_graph,EDITED_SOURCES,kind_reporter,validate_assets,validate_retained,sha

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


    def slot_sources(self):
        paths=(PATH,'android/ci/local_verification.py','android/ci/report_local.py')
        old={path:subprocess.check_output(['git','show','86d3e36d:'+path],cwd=ROOT) for path in paths}
        new=deepcopy(old)
        new[PATH]=old[PATH].decode().replace('                    send(BridgeOperation.AddModule(id,item(module.getString("name"))),id)\n                    val state = ModuleState.valueOf(module.getString("state"))\n                    if (fit(id).modules[position].state != state)\n                        send(BridgeOperation.SetModuleStates(id,listOf(position),state),id)\n                    if (!module.isNull("charge")) send(BridgeOperation.SetModuleCharge(id,position,item(module.getString("charge"))),id)\n','                    val occupied = fit(id).modules.filter { it.name != null }.map { it.index }.toSet()\n                    send(BridgeOperation.AddModule(id,item(module.getString("name"))),id)\n                    val added = fit(id).modules.single { it.name != null && it.index !in occupied }\n                    assertEquals(module.getString("name"),added.name)\n                    val state = ModuleState.valueOf(module.getString("state"))\n                    if (added.state != state)\n                        send(BridgeOperation.SetModuleStates(id,listOf(added.index),state),id)\n                    if (!module.isNull("charge")) send(BridgeOperation.SetModuleCharge(id,added.index,item(module.getString("charge"))),id)\n',1).encode()
        new['android/ci/report_local.py']=slot_reporter(old['android/ci/report_local.py'].decode()).encode()
        return old,new

    def placement(self):
        graph=deepcopy(self.graph);base=graph['fit_order'][:-2]
        empty=deepcopy(graph['records'][EXTRA_IDS[0]])
        copy=deepcopy(graph['records'][EXTRA_IDS[1]])
        fitted=deepcopy(empty);fitted['spec'].update(name='C01.1 Fitted cruiser',ignore_restrictions=False,
            drones=[{'active':3,'amount':5,'name':'Hammerhead II'}],
            modules=[{'empty_slot':'LOW'} for _ in range(5)]+[{'empty_slot':'MED'} for _ in range(4)]+
            [{'charge':None,'name':'Dual 150mm Railgun II','state':'ACTIVE'}]+[{'empty_slot':'HIGH'} for _ in range(3)]+
            [{'empty_slot':'RIG'} for _ in range(3)])
        graph['fit_order']=base+SLOT_IDS
        for field in ('records','revisions','modified'):graph[field]={key:value for key,value in graph[field].items() if key in base}
        for identifier,record in zip(SLOT_IDS,[empty,copy,fitted]):
            graph['records'][identifier]=record;graph['revisions'][identifier]=1;graph['modified'][identifier]=2.0
        graph['recent']=[3106]+self.prior['recent_after']
        return graph

    def test_exact_slot_source_and_chain_pass(self):
        old,new=self.slot_sources();validate_sources(old,new,[PATH,'android/ci/report_local.py'])

    def test_slot_source_rejects_other_changes(self):
        old,new=self.slot_sources()
        for path in new:
            bad=deepcopy(new);bad[path]+=b'# unrelated change\n'
            with self.subTest(path=path),self.assertRaises(AssertionError):validate_sources(old,bad,[PATH,'android/ci/report_local.py'])
        with self.assertRaises(AssertionError):validate_sources(old,new,[PATH,'android_bridge/contract.py'])

    def test_placement_recovery_preserves_baseline_and_restores_expected_recent(self):
        graph=self.placement();before=deepcopy(graph);restored=placement_graph(graph,self.prior)
        self.assertEqual(graph,before);self.assertEqual(restored['recent'],self.prior['recent_after'])
        for field in ('records','revisions','modified'):
            self.assertEqual(restored[field],{key:graph[field][key] for key in restored['fit_order']})
        self.assertEqual(len(restored['fit_order']),147)

    def test_placement_recovery_rejects_inputs_ids_recent_revisions_order_links(self):
        for change in (lambda g:g['records'][SLOT_IDS[2]]['spec']['modules'][9].__setitem__('state','OFFLINE'),
                       lambda g:g['fit_order'].__setitem__(-1,'unexpected'),
                       lambda g:g.__setitem__('recent',[999]),
                       lambda g:g['revisions'].__setitem__('baseline-0',2),
                       lambda g:g['fit_order'].__setitem__(slice(0,2),list(reversed(g['fit_order'][:2]))),
                       lambda g:g['records']['baseline-0']['commands'].append({'source_id':SLOT_IDS[0]})):
            bad=self.placement();change(bad)
            with self.assertRaises(AssertionError):placement_graph(bad,self.prior)


    def edited_sources(self):
        paths=set(EDITED_SOURCES)|{'android/ci/local_verification.py','android/ci/report_local.py'}
        old={}
        for path in paths:
            try:old[path]=subprocess.check_output(['git','show','ebe1d810:'+path],cwd=ROOT,stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:old[path]=b''
        new={path:(ROOT/path).read_bytes().replace(b'\r\n',b'\n') for path in paths}
        return old,new

    def kind_state(self):
        graph=self.placement();base=graph['fit_order'][:-3]
        empty=deepcopy(graph['records'][SLOT_IDS[0]]);copy=deepcopy(graph['records'][SLOT_IDS[1]])
        fitted=deepcopy(graph['records'][SLOT_IDS[2]])
        fitted['spec']['modules'][9]['charge']='Antimatter Charge M'
        fitted['spec']['modules'][10]={'charge':'Antimatter Charge M','name':'Dual 150mm Railgun II','state':'ACTIVE'}
        fitted['spec']['cargo']=[{'amount':400,'name':'Antimatter Charge M'}]
        offline=deepcopy(empty);offline['spec'].update(name='C01.1 Offline guns',ignore_restrictions=False)
        offline['spec']['modules']=deepcopy(fitted['spec']['modules'])
        for index in (9,10):offline['spec']['modules'][index].update(charge=None,state='OFFLINE')
        graph['fit_order']=base+KIND_IDS
        for field in ('records','revisions','modified'):graph[field]={key:value for key,value in graph[field].items() if key in base}
        for identifier,record in zip(KIND_IDS,[empty,copy,fitted,offline]):
            graph['records'][identifier]=record;graph['revisions'][identifier]=1;graph['modified'][identifier]=2.0
        recent=list(self.prior['recent_after'])
        for identity in (3106,230,3106):recent=[identity]+[value for value in recent if value!=identity]
        graph['recent']=recent
        return graph

    def test_exact_edited_sources_and_all_other_differences_rejected(self):
        old,new=self.edited_sources();changes=list(EDITED_SOURCES)+['android/ci/report_local.py']
        validate_sources(old,new,changes)
        for path in new:
            bad=deepcopy(new);bad[path]+=b'# unrelated difference\n'
            with self.subTest(path=path),self.assertRaises(AssertionError):validate_sources(old,bad,changes)
        for path in ('android_bridge/resources.py','tools/android_reference/fixtures/resources.json'):
            with self.assertRaises(AssertionError):validate_sources(old,new,changes+[path])

    def test_exact_four_fit_recovery_preserves_original_baseline(self):
        graph=self.kind_state();before=deepcopy(graph);restored=kind_graph(graph,self.prior)
        self.assertEqual(graph,before);self.assertEqual(len(restored['fit_order']),147)
        self.assertEqual(restored['recent'],self.prior['recent_after'])
        for field in ('records','revisions','modified'):
            self.assertEqual(restored[field],{key:graph[field][key] for key in restored['fit_order']})

    def test_four_fit_recovery_rejects_other_inputs_ids_recent_revisions_links(self):
        for change in (lambda g:g['records'][KIND_IDS[2]]['spec']['cargo'][0].__setitem__('amount',401),
                       lambda g:g['records'][KIND_IDS[3]]['spec']['modules'][9].__setitem__('state','ACTIVE'),
                       lambda g:g['fit_order'].__setitem__(-1,'unexpected'),
                       lambda g:g.__setitem__('recent',[999]),
                       lambda g:g['revisions'].__setitem__('baseline-0',2),
                       lambda g:g['fit_order'].__setitem__(slice(0,2),list(reversed(g['fit_order'][:2]))),
                       lambda g:g['records']['baseline-0']['commands'].append({'source_id':KIND_IDS[0]})):
            bad=self.kind_state();change(bad)
            with self.assertRaises(AssertionError):kind_graph(bad,self.prior)

    def test_only_verified_added_asset_is_permitted(self):
        reference=(ROOT/'tools/android_reference/fixtures/resources-edited.json').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            old=Path(directory)/'old.apk';new=Path(directory)/'new.apk'
            with ZipFile(old,'w') as archive:archive.writestr('assets/fixture.json',b'original\r\n')
            def write(extra,base=b'original\r\n',other=False):
                with ZipFile(new,'w') as archive:
                    archive.writestr('assets/fixture.json',base)
                    if extra is not None:archive.writestr('assets/resources-edited-expected.json',extra)
                    if other:archive.writestr('assets/unrelated.json',b'{}')
            write(reference);validate_assets(old,new,ROOT,True)
            write(reference.replace(b'\r\n',b'\n'));validate_assets(old,new,ROOT,True)
            for extra,base,other in ((None,b'original\r\n',False),(reference,b'original\n',False),
                                     (reference,b'original\r\n',True),(reference+b' ',b'original\r\n',False)):
                write(extra,base,other)
                with self.assertRaises(AssertionError):validate_assets(old,new,ROOT,True)

    def test_missing_or_changed_required_retained_file_always_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'required').write_bytes(b'original')
            proof={'retained_hashes':{'required':sha(run/'required')}}
            validate_retained(run,proof)
            (run/'required').write_bytes(b'changed')
            with self.assertRaises(AssertionError):validate_retained(run,proof)
            (run/'required').unlink()
            with self.assertRaises(FileNotFoundError):validate_retained(run,proof)

    def test_missing_optional_diagnostic_requires_explicit_validated_record(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory)
            proof={'archive':'resource-test-fix-original','retained_hashes':{'native\\failure.png':'c731827e8b7054bb01abda5ffa2aa8cd727305c92869478eb166461820c84f97'}}
            with self.assertRaises(FileNotFoundError):validate_retained(run,proof)
            (run/'resource-diagnostics.json').write_text(json.dumps({'required_passing_evidence_affected':True}))
            with self.assertRaises(AssertionError):validate_retained(run,proof)

if __name__=='__main__':unittest.main()
