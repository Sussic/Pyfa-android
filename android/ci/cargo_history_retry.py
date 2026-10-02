"""Bounded B09.2 observer repair: retain legacy proof, rerun every affected phase."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

PATH='android/app/src/androidTest/java/io/github/sussic/pyfa/MutationHistoryTest.kt'
OLD_SOURCE='ca361c40e45d26933d8961496060edd8eaca4c9f1c1dafbd6a6fd9b585a4658b'
NEW_SOURCE='04dd23d52d924d7f1fcfc66e09156735fc2c38711f59c5f1faeb31719cc9fe47'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def exact_source(root,before,after):
    def source(commit,path):
        return subprocess.check_output(['git','show',commit+':'+path],cwd=root)
    assert hashlib.sha256(source(before,PATH)).hexdigest()==OLD_SOURCE
    assert hashlib.sha256(source(after,PATH)).hexdigest()==NEW_SOURCE,'Unrelated native source change'
    changes=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed={PATH,'android/ci/cargo_history_retry.py','android/ci/test_cargo_history_retry.py',
        'android/ci/local_verification.py','android/ci/report_local.py'}
    assert PATH in changes and set(changes)<=allowed,changes
    import ast
    def executed(text):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text))
            if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert executed(source(before,'android/ci/local_verification.py'))==executed(source(after,'android/ci/local_verification.py'))

def recovery_graph(original,prior,fixture):
    """Remove exactly the partial first 13 synthetic cases; retain every old input."""
    import copy
    ids=[row['id'] for row in prior['after']['data']]
    assert len(ids)==111 and len(set(ids))==111
    assert [key for key in original['fit_order'] if key in ids]==ids
    assert original['sample_id'] in ids
    assert all(original['revisions'][row['id']]==row['revision'] for row in prior['after']['data'])
    extras=[key for key in original['fit_order'] if key not in ids]
    assert len(extras)==13 and set(original['records'])==set(original['fit_order'])
    names=['Renamed independent — Δ']+['Mutation history '+case['name'] for case in fixture['cases'][1:13]]
    assert [original['records'][key]['spec']['name'] for key in extras]==names
    for key in ids:
        assert not any(edge['source_id'] in extras for field in ('projections','commands') for edge in original['records'][key][field])
    restored=copy.deepcopy(original)
    restored['fit_order']=ids
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
    assert sha(run/'native/history-native.json')==receipt['prior_report_sha256']
    fixture=root/'tools/android_reference/fixtures/history-mutations.json'
    assert sha(fixture)==receipt['fixture_sha256']
    old,new=GraphStore(original).current,GraphStore(restored).current
    expected=recovery_graph(decode_graph(old.payload),json.loads((run/'native/history-native.json').read_text())[-1],json.loads(fixture.read_text()))
    assert decode_graph(new.payload)==expected
    assert new.generation==old.generation+1==receipt['generation_after'] and old.generation==receipt['generation_before']
    preserved=encode_graph({field:expected[field] for field in ('records','revisions','modified')})
    assert hashlib.sha256(preserved.encode()).hexdigest()==receipt['preserved_original_inputs_sha256']
    assert receipt['original_library_eos_comparison_passed'] is True
    return receipt

def prepare(runner,proof):
    archive=runner.directory/'cargo-sort-fix-original';archive.mkdir(exist_ok=False)
    (archive/'run.json').write_bytes(runner.original_run_bytes)
    shutil.copytree(runner.directory/'apks',archive/'apks')
    native=archive/'native';native.mkdir()
    # Archive whole affected B09.2 evidence before replacing it. Legacy files stay.
    for path in runner.native.glob('mutation-history*'):
        if path.is_file():shutil.move(str(path),str(native/path.name))
    for name in ('failure.png','apk-contents.json'):
        if (runner.native/name).exists():shutil.copyfile(runner.native/name,native/name)
    source=Path(runner.args.cargo_recovery).resolve()
    validate_recovery(Path(__file__).resolve().parents[2],runner.directory,source)
    shutil.copytree(source,archive/'recovery')
    proof['archive']=archive.name
    proof['app_sha256']=sha(archive/'apks/app-debug.apk')
    proof['old_test_apk_sha256']=sha(archive/'apks/app-debug-androidTest.apk')
    runner.build('apks-lint')
    root=Path(__file__).resolve().parents[2]
    assert sha(root/'android/app/build/outputs/apk/debug/app-debug.apk')==proof['app_sha256']
    runner.build('package')
    new=runner.directory/'apks/app-debug-androidTest.apk'
    assets_equal(archive/'apks/app-debug-androidTest.apk',new)
    proof['new_test_apk_sha256']=sha(new);proof['prepared']=True

def assets_equal(old,new):
    with ZipFile(old) as a,ZipFile(new) as b:
        names={n for n in a.namelist() if n.startswith('assets/')}
        assert names=={n for n in b.namelist() if n.startswith('assets/')}
        assert all(a.read(n)==b.read(n) for n in names),'Packaged fixture changed'

def install(runner,proof,validation=validate_recovery):
    archive=runner.directory/proof['archive']
    root=Path(__file__).resolve().parents[2]
    receipt=validation(root,runner.directory,archive/'recovery')
    def adb(*args):return subprocess.check_output(['adb','-s',runner.serial,*map(str,args)],timeout=30)
    assert adb('shell','getprop','ro.kernel.qemu').strip()==b'1'
    assert adb('emu','avd','name').decode().splitlines()[0]==runner.state['avd_name']
    assert adb('shell','settings','get','global','airplane_mode_on').strip()==b'1'
    package='io.github.sussic.pyfa.dev'
    adb('shell','am','force-stop',package)
    def graph():return adb('exec-out','run-as',package,'cat','no_backup/fits/graph.sqlite3')
    assert hashlib.sha256(graph()).hexdigest()==receipt['original_store_sha256'],'Disposable store changed since recovery proof'
    runner.execute('environment:cargo-observer-update',['adb','-s',runner.serial,'install','-r','-t',runner.directory/'apks/app-debug-androidTest.apk'])
    assert hashlib.sha256(graph()).hexdigest()==receipt['original_store_sha256']
    target=archive/'recovery/restored-graph.sqlite3'
    adb('push',target,'/data/local/tmp/pyfa-b092-restored.sqlite3')
    adb('shell','run-as',package,'cp','/data/local/tmp/pyfa-b092-restored.sqlite3','no_backup/fits/graph.sqlite3')
    assert hashlib.sha256(graph()).hexdigest()==receipt['restored_store_sha256']
    adb('shell','rm','/data/local/tmp/pyfa-b092-restored.sqlite3')
    proof['installed']=True;proof['recovery_receipt_sha256']=sha(archive/'recovery/recovery.json')
