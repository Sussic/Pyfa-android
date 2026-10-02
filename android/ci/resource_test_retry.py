"""Exact C01.1 copy-ID harness repair; retain unchanged execution evidence."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from cargo_history_retry import assets_equal

PATH='android/app/src/androidTest/java/io/github/sussic/pyfa/ResourcesTest.kt'
OLD_SOURCE='4927c4a8ca2c59815a577967f678ae6a4feade27a142e582833456ba0abb9491'
NEW_SOURCE='f571b5c5fa37ac816f9febc6e8f6dbe7caaf53771e6967281470ef88022be951'
EXTRA_IDS=['ac64476bd8ef4e018ca913d7a5f00e9a','a34b8ff5d85146c2a375300c94e1c33e']
ARCHIVE='resource-test-fix-original'

INIT_HOOK='''            if self.state['commit']!=current and args.adopt_resource_test_fix:
                assert self.state['status']=='failed' and self.state['completed']==plan('full',None)[:-3]
                failure=next(row for row in reversed(self.state['attempts']) if row['gate'].startswith('native:'))
                assert failure['gate']=='native:resources-prepare' and failure['exit_code']!=0
                from resource_test_retry import exact_source
                exact_source(ROOT,self.state['commit'],current)
                before=self.state['commit']
                for row in self.state['attempts']:row.setdefault('tested_commit',before)
                self.state.setdefault('resource_test_reuse',[]).append({'from_commit':before,'to_commit':current,
                    'completed_before_adoption':list(self.state['completed']),
                    'retained_gates':[gate for gate in self.state['completed'] if gate not in ('build:apks-lint','build:package')],
                    'prepared':False,'installed':False})
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
'''
PREPARE_HOOK='''            resource_fixes=self.state.get('resource_test_reuse',[])
            if resource_fixes and not resource_fixes[-1]['prepared']:
                from resource_test_retry import prepare
                prepare(self,resource_fixes[-1]);save(self.file,self.state)
'''
INSTALL_HOOK='''                    if resource_fixes and not resource_fixes[-1]['installed']:
                        from resource_test_retry import install
                        install(self,resource_fixes[-1]);save(self.file,self.state)
'''
ARGUMENT_HOOK="    parser.add_argument('--adopt-resource-test-fix',action='store_true',help='Adopt the exact C01.1 copy-ID test repair and validated two-fit recovery; retain all unchanged proof')\n"
REPORT_HOOK='''    resource_reuse=state.get('resource_test_reuse',[])
    resource_proof=resource_reuse[-1] if resource_reuse else None
    if resource_proof:
        from resource_test_retry import exact_source,validate_recovery,assets_equal
        exact_source(root,resource_proof['from_commit'],resource_proof['to_commit'])
        assert resource_proof['to_commit']==state['commit'] and resource_proof['prepared'] and resource_proof['installed']
        assert sha(run/resource_proof['regression_log'])==resource_proof['regression_log_sha256']
        assert latest['headless:resource-harness-repair']['exit_code']==0 and latest['headless:resource-harness-repair']['tested_commit']==state['commit']
        archive=run/resource_proof['archive'];assert archive.resolve().is_relative_to(run.resolve())
        validate_recovery(root,run,archive/'recovery')
        assert sha(archive/'recovery/recovery.json')==resource_proof['recovery_receipt_sha256']
        assert sha(run/'apks/app-debug.apk')==resource_proof['app_sha256']
        assert sha(archive/'apks/app-debug-androidTest.apk')==resource_proof['old_test_apk_sha256']
        assert sha(run/'apks/app-debug-androidTest.apk')==resource_proof['new_test_apk_sha256']
        assets_equal(archive/'apks/app-debug-androidTest.apk',run/'apks/app-debug-androidTest.apk')
        for name,digest in resource_proof['retained_hashes'].items():assert sha(run/name)==digest
        assert resource_proof['retained_gates']==[gate for gate in resource_proof['completed_before_adoption'] if gate not in ('build:apks-lint','build:package')]
'''
RETAIN_HOOK='''            if resource_proof and gate in resource_proof['retained_gates']:
                assert row['tested_commit']==resource_proof['from_commit']
                continue
'''

# Both historical transitions remain exact; neither permits product/fixture edits.
SLOT_SOURCE='182dcfb02f7dc78e7a0be4176a0666d915811c3bc9b4929e93a5a9ee5347e641'
SLOT_ARCHIVE='resource-placement-fix-original'
SLOT_IDS=['13fa26c6a0d94aa6816df494202accf5','63eab694c7ba4bdeb4a8510f8f25a944','b97671414d7044bf9a6e8a79718958bb']
SLOT_RECORDS=['27a4731a70ad86af9bf776bce6b0ca8389d625491b7602329a5ec291a9d283d3',
              '504b79fa7f559e4a5ab1c848339b2a1eb19c50432c77b07d6943b1431eb48811',
              'ba4370a83673148e73ec0bd7bc2763d100d27dc04f5c7995f1cae3bcfdfbf4b1']
FIRST_REPORT_HOOK=REPORT_HOOK
FIRST_RETAIN_HOOK=RETAIN_HOOK
CHAIN_REPORT_HOOK="    resource_reuse=state.get('resource_test_reuse',[])\n    resource_proof=resource_reuse[-1] if resource_reuse else None\n    if resource_proof:\n        from resource_test_retry import exact_source,validate_recovery,assets_equal\n        for index,proof in enumerate(resource_reuse):\n            exact_source(root,proof['from_commit'],proof['to_commit'])\n            following=resource_reuse[index+1] if index+1<len(resource_reuse) else None\n            assert proof['to_commit']==(following['from_commit'] if following else state['commit'])\n            assert proof['prepared'] and proof['installed']\n            assert sha(run/proof['regression_log'])==proof['regression_log_sha256']\n            assert any(row['gate']=='headless:resource-harness-repair' and row['exit_code']==0\n                and row['tested_commit']==proof['to_commit'] and row['log']==proof['regression_log'] for row in state['attempts'])\n            archive=run/proof['archive'];assert archive.resolve().is_relative_to(run.resolve())\n            validate_recovery(root,run,archive/'recovery')\n            assert sha(archive/'recovery/recovery.json')==proof['recovery_receipt_sha256']\n            assert sha(run/'apks/app-debug.apk')==proof['app_sha256']\n            assert sha(archive/'apks/app-debug-androidTest.apk')==proof['old_test_apk_sha256']\n            new_apk=run/following['archive']/'apks/app-debug-androidTest.apk' if following else run/'apks/app-debug-androidTest.apk'\n            assert sha(new_apk)==proof['new_test_apk_sha256']\n            assets_equal(archive/'apks/app-debug-androidTest.apk',new_apk)\n            for name,digest in proof['retained_hashes'].items():assert sha(run/name)==digest\n            assert proof['retained_gates']==[gate for gate in proof['completed_before_adoption'] if gate not in ('build:apks-lint','build:package')]\n"
CHAIN_RETAIN_HOOK="            if resource_proof and gate in resource_proof['retained_gates']:\n                assert any(gate in proof['retained_gates'] and row['tested_commit']==proof['from_commit'] for proof in resource_reuse)\n                continue\n"

def slot_reporter(source):
    return replace_once(replace_once(source,FIRST_REPORT_HOOK,CHAIN_REPORT_HOOK),FIRST_RETAIN_HOOK,CHAIN_RETAIN_HOOK)

def placement_graph(original,prior):
    from android_bridge.store import encode_graph
    ids=[row['id'] for row in prior['after']['data']]
    assert len(ids)==len(set(ids))==147
    assert [key for key in original['fit_order'] if key in ids]==ids
    extras=[key for key in original['fit_order'] if key not in ids]
    assert extras==SLOT_IDS and original['sample_id'] in ids
    # The sole completed recent-use operation was AddModule(Dual 150mm Railgun II).
    expected_recent=[3106]+[identity for identity in prior['recent_after'] if identity!=3106]
    assert original['recent']==expected_recent
    for identifier,digest in zip(SLOT_IDS,SLOT_RECORDS):
        assert hashlib.sha256(encode_graph(original['records'][identifier]).encode()).hexdigest()==digest
    for row in prior['after']['data']:
        assert original['revisions'][row['id']]==row['revision']
        for field in ('projections','commands'):
            assert not any(edge['source_id'] in extras for edge in original['records'][row['id']][field])
    restored=copy.deepcopy(original);restored['fit_order']=ids;restored['recent']=copy.deepcopy(prior['recent_after'])
    for field in ('records','revisions','modified'):
        assert set(original[field])==set(original['fit_order'])
        restored[field]={key:original[field][key] for key in ids}
    return restored

# Third transition adds one independent edited-fit witness; original fixtures stay exact.
KIND_ARCHIVE='resource-kind-fix-original'
KIND_IDS=['fc04c55fd58b4aa681f6a2bb08391ecf', 'd84f9ea1c59f4707b5f232641c808e37', '2d3b28321fa446d3977288aa50db3119', 'f540659dd69843ec8cff31549e2f547a']
KIND_RECORDS=['27a4731a70ad86af9bf776bce6b0ca8389d625491b7602329a5ec291a9d283d3', '504b79fa7f559e4a5ab1c848339b2a1eb19c50432c77b07d6943b1431eb48811', 'a50e53022530161b04ee0a7e3b378eb8e14cadc7dd5ee65112dcb2cebf45bc8f', '898ed34ab83abec6b40c374ffe7fa33d825c05f1247fff21e0505bd720951a5f']
EDITED_SOURCES={'android/app/src/androidTest/java/io/github/sussic/pyfa/ResourcesTest.kt': ['182dcfb02f7dc78e7a0be4176a0666d915811c3bc9b4929e93a5a9ee5347e641', '415de7e9e82c5af20b364004b954aaaaee4755396f1b9736fadea5c5d850d1fb'], 'android/prepare-engine.py': ['5420881a4a6bc13ea5680abe1055b3e7ed4f4342b73617d94c20c34c81f99953', '26735c8cb1853b2cd14b979b7249966e9ddd744159e428d8a4ff7286b3845676'], 'android/ci/resource_summary.py': ['7fc3e0aa33e2f2b86f2f197cb69fc65c42b7df5631c04c15ea7981877171f76e', '2f23e98e1832e577b5ed74cf63522c95f77e380aceb60433d8874528dfc6c2b9'], 'android/ci/test_resource_summary.py': ['edc6743a6cb98f8ca677063ca18ec9ea5327177311a05a52f9e7885b2ebff2d1', 'b35166ba3c55efc3c1143550358f9f58b2e8ccd45fc1b3f840eee167b88de01a'], 'tools/android_reference/resources_edited.py': ['e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'd562ccdd2c04b128c1d335d962ccce849be345af37b4b4ea9a932481fddd6eb4'], 'tools/android_reference/fixtures/resources-edited.json': ['e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'b33e17bbe9928f361c1f798436a32f3e72ce81d5257edd2a751879c134514e1b'], 'tools/android_headless/check_resources.py': ['386fe5907311e1c8271380e8d6bb926d2ce93e924f3c2573c8111ec61570cb7c', 'd7eb87af482e02d80668bf218502726944f26c90e2b9d7a7594d884927c9c0ba']}

THIRD_REPORT_HOOK="    resource_reuse=state.get('resource_test_reuse',[])\n    resource_proof=resource_reuse[-1] if resource_reuse else None\n    if resource_proof:\n        from resource_test_retry import exact_source,validate_recovery,validate_assets,validate_retained,validate_witness,KIND_ARCHIVE\n        for index,proof in enumerate(resource_reuse):\n            exact_source(root,proof['from_commit'],proof['to_commit'])\n            following=resource_reuse[index+1] if index+1<len(resource_reuse) else None\n            assert proof['to_commit']==(following['from_commit'] if following else state['commit'])\n            assert proof['prepared'] and proof['installed']\n            assert sha(run/proof['regression_log'])==proof['regression_log_sha256']\n            assert any(row['gate']=='headless:resource-harness-repair' and row['exit_code']==0\n                and row['tested_commit']==proof['to_commit'] and row['log']==proof['regression_log'] for row in state['attempts'])\n            archive=run/proof['archive'];assert archive.resolve().is_relative_to(run.resolve())\n            validate_recovery(root,run,archive/'recovery')\n            assert sha(archive/'recovery/recovery.json')==proof['recovery_receipt_sha256']\n            assert sha(run/'apks/app-debug.apk')==proof['app_sha256']\n            assert sha(archive/'apks/app-debug-androidTest.apk')==proof['old_test_apk_sha256']\n            new_apk=run/following['archive']/'apks/app-debug-androidTest.apk' if following else run/'apks/app-debug-androidTest.apk'\n            assert sha(new_apk)==proof['new_test_apk_sha256']\n            validate_assets(archive/'apks/app-debug-androidTest.apk',new_apk,root,proof['archive']==KIND_ARCHIVE)\n            validate_retained(run,proof)\n            validate_witness(run,proof,root)\n            assert proof['retained_gates']==[gate for gate in proof['completed_before_adoption'] if gate not in ('build:apks-lint','build:package')]\n"

def kind_reporter(source):
    return replace_once(source,CHAIN_REPORT_HOOK,THIRD_REPORT_HOOK)

def kind_graph(original,prior):
    from android_bridge.store import encode_graph
    ids=[row['id'] for row in prior['after']['data']]
    assert len(ids)==len(set(ids))==147
    assert [key for key in original['fit_order'] if key in ids]==ids
    extras=[key for key in original['fit_order'] if key not in ids]
    assert extras==KIND_IDS and original['sample_id'] in ids
    recent=list(prior['recent_after'])
    for identity in (3106,230,3106):recent=[identity]+[value for value in recent if value!=identity]
    assert original['recent']==recent
    for identifier,digest in zip(KIND_IDS,KIND_RECORDS):
        assert hashlib.sha256(encode_graph(original['records'][identifier]).encode()).hexdigest()==digest
    for row in prior['after']['data']:
        assert original['revisions'][row['id']]==row['revision']
        for field in ('projections','commands'):
            assert not any(edge['source_id'] in extras for edge in original['records'][row['id']][field])
    restored=copy.deepcopy(original);restored['fit_order']=ids;restored['recent']=copy.deepcopy(prior['recent_after'])
    for field in ('records','revisions','modified'):
        assert set(original[field])==set(original['fit_order'])
        restored[field]={key:original[field][key] for key in ids}
    return restored

def validate_assets(old,new,root,addition=False):
    if not addition:return assets_equal(old,new)
    from zipfile import ZipFile
    with ZipFile(old) as left,ZipFile(new) as right:
        original={name for name in left.namelist() if name.startswith('assets/')}
        current={name for name in right.namelist() if name.startswith('assets/')}
        extra='assets/resources-edited-expected.json'
        assert current==original|{extra} and extra not in original
        assert all(left.read(name)==right.read(name) for name in original),'Existing test asset changed'
        reference=(root/'tools/android_reference/fixtures/resources-edited.json').read_bytes()
        assert right.read(extra).replace(b'\r\n',b'\n')==reference.replace(b'\r\n',b'\n'),'Edited fixture changed'

def validate_retained(run,proof):
    diagnostics={'native\\failure.png','native\\failure-logcat.txt'}
    for name,digest in proof['retained_hashes'].items():
        if name not in diagnostics:
            assert sha(run/name)==digest,name
            continue
        # These best-effort failed-run diagnostics are not passing gate artifacts.
        # First originals were overwritten; preserve the loss instead of claiming them.
        receipt=json.loads((run/'resource-diagnostics.json').read_text(encoding='utf-8'))
        assert receipt['required_passing_evidence_affected'] is False
        row=receipt[proof['archive']][name]
        assert row['recorded_sha256']==digest
        archive=run/proof['archive']
        original=json.loads((archive/'run.json').read_text(encoding='utf-8'))
        failure=next(attempt for attempt in reversed(original['attempts']) if attempt['gate'].startswith('native:'))
        assert failure['gate']=='native:resources-prepare' and failure['exit_code']!=0
        assert failure['tested_commit']==proof['from_commit']
        assert sha(run/failure['log'])==failure['log_sha256']
        instrument=archive/'native/resources-prepare-instrumentation.txt'
        assert sha(instrument)==row['instrumentation_sha256']
        text=instrument.read_text(encoding='utf-8')
        line={ARCHIVE:173,SLOT_ARCHIVE:151,KIND_ARCHIVE:161}[proof['archive']]
        assert 'FAILURES!!!' in text and f'ResourcesTest.kt:{line}' in text
        if proof['archive']==ARCHIVE:
            known={'native\\failure.png':'c731827e8b7054bb01abda5ffa2aa8cd727305c92869478eb166461820c84f97',
                   'native\\failure-logcat.txt':'31ff34801e37d5398f6dc5a5c6411c91709dbff603c4ab989c90821312caeb4a'}
            assert digest==known[name] and row['status']=='unavailable_overwritten_by_second_failure'
            assert not (archive/'native'/Path(name.replace('\\','/')).name).exists()
        else:
            assert row['status']=='archived'
            target=archive/'native'/Path(name.replace('\\','/')).name
            assert sha(target)==digest

def validate_witness(run,proof,root):
    if proof['archive']!=KIND_ARCHIVE:return
    state=json.loads((run/'run.json').read_text(encoding='utf-8'))
    for row in proof['witness_logs']:
        assert sha(run/row['log'])==row['sha256']
        assert any(attempt['gate']==row['gate'] and attempt['log']==row['log'] and attempt['exit_code']==0
            and attempt['tested_commit']==proof['to_commit'] for attempt in state['attempts'])
    directory=run/'host/resource-edited-witness'
    reference=root/'tools/android_reference/fixtures/resources-edited.json'
    assert (directory/'resources-edited.json').read_bytes().replace(b'\r\n',b'\n')==reference.read_bytes().replace(b'\r\n',b'\n')
    assert (directory/'resources-edited.json').read_bytes()==(directory/'repeat.json').read_bytes()
    receipt=json.loads((directory/'evidence.json').read_text(encoding='utf-8'))
    assert receipt['fresh_process_repeat'] is True and receipt['game_database_unchanged'] is True
    assert receipt['reference_sha256']==sha(directory/'resources-edited.json')

def replace_once(source,anchor,replacement):
    assert source.count(anchor)==1,anchor
    return source.replace(anchor,replacement,1)

def updated_launcher(source):
    anchor="            current=git('rev-parse','HEAD')\n"
    source=replace_once(source,anchor,anchor+INIT_HOOK)
    anchor="            self.state['status']='running';save(self.file,self.state)\n"
    source=replace_once(source,anchor,anchor+PREPARE_HOOK)
    anchor="                    if self.emulator is None:self.start_emulator()\n"
    source=replace_once(source,anchor,anchor+INSTALL_HOOK)
    anchor="    args=parser.parse_args()\n"
    return replace_once(source,anchor,ARGUMENT_HOOK+anchor)

def updated_reporter(source):
    anchor="    latest={row['gate']:row for row in state['attempts']}\n"
    source=replace_once(source,anchor,anchor+REPORT_HOOK)
    anchor="            comparison_commit=state['commit']\n"
    return replace_once(source,anchor,anchor+RETAIN_HOOK)

def validate_sources(old,new,changes):
    if hashlib.sha256(old[PATH]).hexdigest()==SLOT_SOURCE:
        allowed=set(EDITED_SOURCES)|{'android/ci/resource_test_retry.py','android/ci/test_resource_test_retry.py','android/ci/report_local.py'}
        assert PATH in changes and all(path in allowed or path.startswith('docs/android/') for path in changes),changes
        for path,(before,after) in EDITED_SOURCES.items():
            assert hashlib.sha256(old[path]).hexdigest()==before,path
            assert hashlib.sha256(new[path]).hexdigest()==after,'Unrelated edited-witness source change: '+path
        assert new['android/ci/local_verification.py']==old['android/ci/local_verification.py'],'Unrelated launcher change'
        assert new['android/ci/report_local.py'].decode()==kind_reporter(old['android/ci/report_local.py'].decode()),'Unrelated reporter change'
        return
    if hashlib.sha256(old[PATH]).hexdigest()==NEW_SOURCE:
        assert hashlib.sha256(new[PATH]).hexdigest()==SLOT_SOURCE,'Unrelated resource slot test change'
        allowed={PATH,'android/ci/resource_test_retry.py','android/ci/test_resource_test_retry.py','android/ci/report_local.py'}
        assert PATH in changes and all(path in allowed or path.startswith('docs/android/') for path in changes),changes
        assert new['android/ci/local_verification.py']==old['android/ci/local_verification.py'],'Unrelated launcher change'
        assert new['android/ci/report_local.py'].decode()==slot_reporter(old['android/ci/report_local.py'].decode()),'Unrelated reporter change'
        return
    assert hashlib.sha256(old[PATH]).hexdigest()==OLD_SOURCE
    assert hashlib.sha256(new[PATH]).hexdigest()==NEW_SOURCE,'Unrelated resource test change'
    allowed={PATH,'android/ci/resource_test_retry.py','android/ci/test_resource_test_retry.py',
             'android/ci/local_verification.py','android/ci/report_local.py'}
    assert PATH in changes and all(path in allowed or path.startswith('docs/android/') for path in changes),changes
    assert new['android/ci/local_verification.py'].decode()==updated_launcher(old['android/ci/local_verification.py'].decode()),'Unrelated launcher change'
    assert new['android/ci/report_local.py'].decode()==updated_reporter(old['android/ci/report_local.py'].decode()),'Unrelated reporter change'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def exact_source(root,before,after):
    def source(commit,path):
        try:return subprocess.check_output(['git','show',commit+':'+path],cwd=root,stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:return b''
    changes=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    paths=(PATH,'android/ci/local_verification.py','android/ci/report_local.py')
    if hashlib.sha256(source(before,PATH)).hexdigest()==SLOT_SOURCE:paths=tuple(set(paths)|set(EDITED_SOURCES))
    validate_sources({path:source(before,path) for path in paths},{path:source(after,path) for path in paths},changes)

def recovery_graph(original,prior):
    ids=[row['id'] for row in prior['after']['data']]
    assert len(ids)==len(set(ids))==147
    assert [key for key in original['fit_order'] if key in ids]==ids
    extras=[key for key in original['fit_order'] if key not in ids]
    assert extras==EXTRA_IDS and original['sample_id'] in ids
    assert original['recent']==prior['recent_after']
    names=['C01.1 Empty cruiser','C01.1 copy']
    for identifier,name in zip(extras,names):
        expected={'commands':[],'implants':[],'projections':[],'skills':{},'spec':{
            'boosters':[],'commands':[],'damage_pattern':{'emAmount':25,'explosiveAmount':25,'kineticAmount':25,'thermalAmount':25},
            'drones':[],'environments':[],'factor_reload':False,'implants':[],'modules':[],
            'name':name,'projections':[],'security':{'pilot':0,'system':'HISEC'},
            'ship':'Vexor','skill_level':5,'target_profile':None}}
        from android_bridge.store import encode_graph
        assert encode_graph(original['records'][identifier])==encode_graph(expected),'Unexpected partial test input'
    for row in prior['after']['data']:
        assert original['revisions'][row['id']]==row['revision']
        for field in ('projections','commands'):
            assert not any(edge['source_id'] in extras for edge in original['records'][row['id']][field])
    restored=copy.deepcopy(original);restored['fit_order']=ids
    for field in ('records','revisions','modified'):
        assert set(original[field])==set(original['fit_order'])
        restored[field]={key:original[field][key] for key in ids}
    return restored

def validate_recovery(root,run,directory):
    sys.path.insert(0,str(root))
    from android_bridge.store import GraphStore,decode_graph,encode_graph
    receipt=json.loads((directory/'recovery.json').read_text(encoding='utf-8'))
    original=directory/'partial-graph.sqlite3';restored=directory/'restored-graph.sqlite3'
    assert sha(original)==receipt['original_store_sha256'] and sha(restored)==receipt['restored_store_sha256']
    prior_path=run/'native/mutation-history-3-restored-native.json'
    assert sha(prior_path)==receipt['prior_report_sha256']
    prior=json.loads(prior_path.read_text(encoding='utf-8'));checkpoint=json.loads((directory/'b092-test-expected.json').read_text(encoding='utf-8'))
    assert checkpoint==prior['saved'] and sha(directory/'b092-test-expected.json')==receipt['checkpoint_sha256']
    old,new=GraphStore(original).current,GraphStore(restored).current
    placement=directory.parent.name==SLOT_ARCHIVE;kind=directory.parent.name==KIND_ARCHIVE
    assert directory.parent.name in (ARCHIVE,SLOT_ARCHIVE,KIND_ARCHIVE)
    expected=(kind_graph if kind else placement_graph if placement else recovery_graph)(decode_graph(old.payload),prior)
    if placement or kind:
        baseline=GraphStore(run/ARCHIVE/'recovery/restored-graph.sqlite3').current
        assert encode_graph(expected)==encode_graph(decode_graph(baseline.payload)),'Original baseline input or metadata changed'
    assert decode_graph(new.payload)==expected
    assert new.generation==old.generation+1==receipt['generation_after'] and old.generation==receipt['generation_before']
    preserved=encode_graph({field:expected[field] for field in ('records','revisions','modified')})
    assert hashlib.sha256(preserved.encode()).hexdigest()==receipt['preserved_original_inputs_sha256']
    assert receipt['original_fits']==147 and receipt['removed_ids']==(KIND_IDS if kind else SLOT_IDS if placement else EXTRA_IDS)
    assert receipt['original_library_eos_comparison_passed'] is True
    return receipt

def prepare(runner,proof):
    source_hash=hashlib.sha256(subprocess.check_output(['git','show',proof['from_commit']+':'+PATH],cwd=Path(__file__).resolve().parents[2])).hexdigest()
    archive_name={OLD_SOURCE:ARCHIVE,NEW_SOURCE:SLOT_ARCHIVE,SLOT_SOURCE:KIND_ARCHIVE}[source_hash]
    archive=runner.directory/archive_name
    original=json.loads((archive/'run.json').read_text(encoding='utf-8'))
    assert original['commit']==proof['from_commit'] and original['completed']==proof['completed_before_adoption']
    assert original['status']=='failed' and original['attempts'][-1]['gate']=='native:resources-prepare'
    root=Path(__file__).resolve().parents[2]
    validate_recovery(root,runner.directory,archive/'recovery')
    proof['archive']=archive_name;proof['app_sha256']=sha(runner.directory/'apks/app-debug.apk')
    proof['old_test_apk_sha256']=sha(archive/'apks/app-debug-androidTest.apk')
    assert sha(runner.directory/'apks/app-debug-androidTest.apk')==proof['old_test_apk_sha256']
    proof['retained_hashes']={str(path.relative_to(runner.directory)):sha(path)
        for path in runner.native.iterdir() if path.is_file() and not path.name.startswith('resources-prepare')
        and path.name not in ('lint-results-debug.html','apk-contents.json')}
    for path in runner.native.glob('resources-prepare*'):
        assert sha(path)==sha(archive/'native'/path.name);path.unlink()
    runner.execute('headless:resource-harness-repair',[sys.executable,'-I',root/'android/ci/test_resource_test_retry.py'])
    regression=runner.state['attempts'][-1]
    output=(runner.directory/regression['log']).read_text(encoding='utf-8')
    assert 'Ran 18 tests' in output and '\nOK\n' in output
    proof['regression_log']=regression['log'];proof['regression_log_sha256']=sha(runner.directory/regression['log'])
    if archive_name==KIND_ARCHIVE:
        runner.execute('reference:resource-edited-witness',[runner.reference,'-I',root/'tools/android_reference/resources_edited.py',
            '--source',runner.source,'--database',runner.db,'--output',runner.directory/'host/resource-edited-witness',
            '--check',root/'tools/android_reference/fixtures/resources-edited.json'])
        reference_attempt=runner.state['attempts'][-1]
        runner.execute('headless:resource-edited-validation',[sys.executable,'-I',root/'android/ci/test_resource_summary.py'])
        validator_attempt=runner.state['attempts'][-1]
        assert 'Ran 11 tests' in (runner.directory/validator_attempt['log']).read_text(encoding='utf-8')
        proof['witness_logs']=[{'gate':row['gate'],'log':row['log'],'sha256':sha(runner.directory/row['log'])}
            for row in (reference_attempt,validator_attempt)]
    runner.build('apks-lint')
    assert sha(root/'android/app/build/outputs/apk/debug/app-debug.apk')==proof['app_sha256'],'Application APK changed'
    runner.build('package')
    new=runner.directory/'apks/app-debug-androidTest.apk'
    validate_assets(archive/'apks/app-debug-androidTest.apk',new,root,archive_name==KIND_ARCHIVE)
    proof['new_test_apk_sha256']=sha(new)
    assert proof['new_test_apk_sha256']!=proof['old_test_apk_sha256'],'Corrected test APK did not change'
    sdk=Path(__import__('os').environ['ANDROID_HOME'])
    runner.execute('build:resource-test-signature',[sdk/'build-tools/35.0.0/apksigner.bat','verify','--verbose','--print-certs',new])
    assert all(sha(runner.directory/name)==digest for name,digest in proof['retained_hashes'].items())
    proof['prepared']=True

def install(runner,proof):
    archive=runner.directory/proof['archive'];root=Path(__file__).resolve().parents[2]
    receipt=validate_recovery(root,runner.directory,archive/'recovery')
    def adb(*parts): return subprocess.check_output(['adb','-s',runner.serial,*map(str,parts)],timeout=60)
    assert adb('shell','getprop','ro.kernel.qemu').strip()==b'1'
    assert adb('emu','avd','name').decode().splitlines()[0]==runner.state['avd_name']
    assert adb('shell','settings','get','global','airplane_mode_on').strip()==b'1'
    package='io.github.sussic.pyfa.dev';adb('shell','am','force-stop',package)
    def graph():return adb('exec-out','run-as',package,'cat','no_backup/fits/graph.sqlite3')
    assert hashlib.sha256(graph()).hexdigest()==receipt['original_store_sha256']
    runner.execute('environment:resource-test-update',['adb','-s',runner.serial,'install','-r','-t',runner.directory/'apks/app-debug-androidTest.apk'])
    assert hashlib.sha256(graph()).hexdigest()==receipt['original_store_sha256']
    adb('push',archive/'recovery/restored-graph.sqlite3','/data/local/tmp/pyfa-c011-restored.sqlite3')
    adb('shell','run-as',package,'cp','/data/local/tmp/pyfa-c011-restored.sqlite3','no_backup/fits/graph.sqlite3')
    assert hashlib.sha256(graph()).hexdigest()==receipt['restored_store_sha256']
    adb('shell','rm','/data/local/tmp/pyfa-c011-restored.sqlite3')
    proof['installed']=True;proof['recovery_receipt_sha256']=sha(archive/'recovery/recovery.json')
