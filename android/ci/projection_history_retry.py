"""Revalidate real successful instrumentation after only projection JSON typing repair."""
from pathlib import Path
import shutil
import subprocess

ADDITION='''def projection_inputs(expected, actual, kinds):
    # JSONObject renders integral Double metres as JSON integers. Require the
    # retained decimal kind and lossless exact value; all other fields stay typed.
    exact(len(expected), len(actual))
    for index, (left, right) in enumerate(zip(expected, actual)):
        exact(set(left), set(right))
        for key, value in left.items():
            other = right[key]
            if key == 'range_m':
                exact('decimal', kinds[f'root.projections[{index}].range_m'])
                assert type(value) is float and type(other) in (int, float)
                assert isfinite(value) and isfinite(other) and float(other) == other
                exact(value, float(other))
            else: exact(value, other)


'''

def exact_source(root,before,after):
    def source(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=root,text=True,encoding='utf-8')
    path='android/ci/mutation_history_summary.py';old=source(before,path)
    anchor='def state(case, step, observed, recent):'
    branch="        if field in ('stats', 'linked_stats') and wanted[field] is not None: stats(wanted[field], actual[field])"
    assert old.count(anchor)==old.count(branch)==1
    assert source(after,path)==old.replace(anchor,ADDITION+anchor,1).replace(branch,branch+"\n        elif field == 'projections': projection_inputs(wanted[field], actual[field], observed['numeric_types'])",1)
    test='android/ci/test_pending_settings_fix.py';old_test=source(before,test)
    assert source(after,test)==old_test.replace("self.new=(ROOT/PATH).read_text(encoding='utf-8')","self.new=subprocess.check_output(['git','show','287c0c336c0191c78129a017b363dbc3d030adad:'+PATH],cwd=ROOT,text=True,encoding='utf-8')",1)
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    assert path in changed and set(changed)<={path,test,'android/ci/projection_history_retry.py',
        'android/ci/test_projection_history_report.py','android/ci/revalidate-projection-history.py',
        'android/ci/local_verification.py','android/ci/report_local.py'}
    import ast
    def executed(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert executed(source(before,'android/ci/local_verification.py'))==executed(source(after,'android/ci/local_verification.py'))

def revalidate(runner,proof):
    from cargo_history_retry import sha
    archive=runner.directory/'projection-range-fix-original';archive.mkdir(exist_ok=False)
    (archive/'run.json').write_bytes(runner.original_run_bytes)
    names=['mutation-history-3-prepare-'+suffix for suffix in ('native.json','instrumentation.txt')]
    proof['retained_hashes']={name:sha(runner.native/name) for name in names}
    proof['apk_hashes']={p.name:sha(p) for p in (runner.directory/'apks').glob('*.apk')};assert len(proof['apk_hashes'])==2
    for name in names:shutil.copyfile(runner.native/name,archive/name)
    import sys
    runner.execute('native:mutation-history-3-prepare',[sys.executable,Path(__file__).resolve().parent/'revalidate-projection-history.py'])
    runner.state['attempts'][-1]['retained_native_execution_commit']=proof['from_commit']
    assert all(sha(runner.native/name)==digest for name,digest in proof['retained_hashes'].items())
    runner.state['completed'].append('native:mutation-history-3-prepare')
    proof['archive']=archive.name;proof['validated']=True
