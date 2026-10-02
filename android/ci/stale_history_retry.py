"""Retain groups 0–2; repair only the final group's enum comparison/reporting."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from cargo_history_retry import PATH,sha,assets_equal

def exact_source(root,before,after):
    def source(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=root,text=True,encoding='utf-8')
    old=source(before,PATH)
    assertion='assertEquals("REVISION_CONFLICT", rejected.error?.code)'
    report='observations.put("stale_error_code", rejected.error!!.code)'
    assert old.count(assertion)==old.count(report)==1
    assert source(after,PATH)==old.replace(assertion,'assertEquals(BridgeErrorCode.REVISION_CONFLICT, rejected.error?.code)',1).replace(report,'observations.put("stale_error_code", rejected.error!!.code.name)',1)
    path='android/ci/cargo_history_retry.py';old=source(before,path)
    assert source(after,path)==old.replace('def install(runner,proof):','def install(runner,proof,validation=validate_recovery):',1).replace("receipt=validate_recovery(root,runner.directory,archive/'recovery')","receipt=validation(root,runner.directory,archive/'recovery')",1)
    test='android/ci/test_cargo_history_retry.py';old_test=source(before,test)
    assert source(after,test)==old_test.replace('self.new=(ROOT/retry.PATH).read_text().encode()',"self.new=subprocess.check_output(['git','show','66e89f31864ff12396f02dd420f5b3b5a1a5fd00:'+retry.PATH],cwd=ROOT)",1)
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    assert PATH in changed and set(changed)<={PATH,path,test,'android/ci/stale_history_retry.py',
        'android/ci/test_stale_history_retry.py','android/ci/local_verification.py','android/ci/report_local.py'}
    import ast
    def executed(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert executed(source(before,'android/ci/local_verification.py'))==executed(source(after,'android/ci/local_verification.py'))

def recovery_graph(original,prior,fixture):
    ids=[row['id'] for row in prior['after']['data']]
    assert len(ids)==134 and len(set(ids))==134 and original['sample_id'] in ids
    assert [key for key in original['fit_order'] if key in ids]==ids
    assert set(original['records'])==set(original['fit_order'])
    assert all(original['revisions'][row['id']]==row['revision'] for row in prior['after']['data'])
    extras=[key for key in original['fit_order'] if key not in ids]
    names=[]
    for case in fixture['cases'][21:28]:
        names.append(case['spec']['name'])
        if case['source_spec'] is not None:names.append(case['source_spec']['name'])
    names.append('B09.2 independent link copy — Δ')
    assert len(extras)==len(names)==14
    assert [original['records'][key]['spec']['name'] for key in extras]==names
    for key in ids:
        assert not any(edge['source_id'] in extras for field in ('projections','commands') for edge in original['records'][key][field])
    restored=copy.deepcopy(original);restored['fit_order']=ids
    for field in ('records','revisions','modified'):
        assert set(original[field])==set(original['records'])
        restored[field]={key:original[field][key] for key in ids}
    restored['recent']=copy.deepcopy(prior['recent_after'])
    return restored

def validate_recovery(root,run,directory):
    sys.path.insert(0,str(root))
    from android_bridge.store import GraphStore,decode_graph,encode_graph
    receipt=json.loads((directory/'recovery.json').read_text())
    original=directory/'partial-graph.sqlite3';restored=directory/'restored-graph.sqlite3'
    assert sha(original)==receipt['original_store_sha256'] and sha(restored)==receipt['restored_store_sha256']
    prior=run/'native/mutation-history-2-restored-native.json'
    fixture=root/'tools/android_reference/fixtures/history-mutations.json'
    assert sha(prior)==receipt['prior_report_sha256'] and sha(fixture)==receipt['fixture_sha256']
    old,new=GraphStore(original).current,GraphStore(restored).current
    expected=recovery_graph(decode_graph(old.payload),json.loads(prior.read_text()),json.loads(fixture.read_text()))
    assert decode_graph(new.payload)==expected
    assert new.generation==old.generation+1==receipt['generation_after'] and old.generation==receipt['generation_before']
    preserved=encode_graph({field:expected[field] for field in ('records','revisions','modified')})
    assert hashlib.sha256(preserved.encode()).hexdigest()==receipt['preserved_original_inputs_sha256']
    assert receipt['original_library_eos_comparison_passed'] is True
    return receipt

def prepare(runner,proof):
    root=Path(__file__).resolve().parents[2]
    source=Path(runner.args.stale_recovery).resolve();validate_recovery(root,runner.directory,source)
    archive=runner.directory/'stale-error-fix-original';archive.mkdir(exist_ok=False)
    (archive/'run.json').write_bytes(runner.original_run_bytes)
    shutil.copytree(runner.directory/'apks',archive/'apks');shutil.copytree(source,archive/'recovery')
    native=archive/'native';native.mkdir()
    for path in runner.native.glob('mutation-history-3-*'):
        if path.is_file():shutil.move(str(path),str(native/path.name))
    for name in ('failure.png','apk-contents.json'):
        shutil.copyfile(runner.native/name,native/name)
    proof['archive']=archive.name
    proof['retained_report_hashes']={p.name:sha(p) for p in runner.native.glob('mutation-history-*-native.json')}
    assert len(proof['retained_report_hashes'])==6
    proof['app_sha256']=sha(archive/'apks/app-debug.apk')
    proof['old_test_apk_sha256']=sha(archive/'apks/app-debug-androidTest.apk')
    runner.build('apks-lint');assert sha(root/'android/app/build/outputs/apk/debug/app-debug.apk')==proof['app_sha256']
    runner.build('package');new=runner.directory/'apks/app-debug-androidTest.apk'
    assets_equal(archive/'apks/app-debug-androidTest.apk',new)
    proof['new_test_apk_sha256']=sha(new);proof['prepared']=True

def install(runner,proof):
    from cargo_history_retry import install as install_recovery
    install_recovery(runner,proof,validation=validate_recovery)
