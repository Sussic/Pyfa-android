"""Reuse only unchanged host proof after the exact C02 Android repairs."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

BEFORE='31cb285979f93e5e170d8dfe83229983c8a0d164'
PAIRS={
 'android/app/src/main/java/io/github/sussic/pyfa/BridgeContract.kt':('2dff01c4cd98d9f2516dcead781a06fd8c2ebb1c6139b3ba609fdb0cd9451f30','5330de8af62be5bb4f74f2cc0dcc625aedcbbf942fab26b37128f3ce2ca2b357'),
 'android/app/src/main/java/io/github/sussic/pyfa/OutputView.kt':('10c2b9b4ac3a7082f6049602ba2640e55dcbdf333501816e18bcd5cabcdf79e6','e8a4d2ef74c675198751efd7f2e3a719ee050bb06bc1356fcee3b5bfff442da4'),
 'android/app/src/androidTest/java/io/github/sussic/pyfa/OutputTest.kt':('f03b5f645e1a417103970b4221929c34942c2279f9281c0aa0397b62640cdd28','66518ed1e17a10d9f5178ba0c9b225e6d4dcf5c749fc7f6efcbbe5f4903d2d6e'),
}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def exact_source(root,before,after,completed):
    from local_verification import plan
    assert before==BEFORE and completed==plan('full',None)[:106]
    assert plan('full',None)[106]=='native:output-prepare'
    def source(revision,path):return subprocess.check_output(['git','show',revision+':'+path],cwd=root)
    for path,pair in PAIRS.items():
        for revision,digest in zip((before,after),pair):
            assert hashlib.sha256(source(revision,path).replace(b'\r\n',b'\n')).hexdigest()==digest,path
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed=set(PAIRS)|{'android/ci/local_verification.py','android/ci/report_local.py',
                       'android/ci/output_profile_retry.py','android/ci/test_output_profile_retry.py'}
    assert set(PAIRS)<=set(changed)
    assert all(p in allowed or p.startswith('docs/android/') for p in changed),changed
    def executed(revision):
        tree=ast.parse(source(revision,'android/ci/local_verification.py').decode('utf-8'))
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(tree)
                if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert executed(before)==executed(after),'Executed host/build behavior changed'

def validate_retained(root,run,proof):
    exact_source(root,proof['from_commit'],proof['to_commit'],proof['completed_before_adoption'])
    archive=(run/proof['archive']).resolve()
    assert archive.is_relative_to(run.resolve()) and archive!=run.resolve()
    prior=json.loads((archive/'run.json').read_text(encoding='utf-8'))
    assert prior['commit']==proof['from_commit'] and prior['status']=='failed'
    assert prior['completed']==proof['completed_before_adoption']
    failure=prior['attempts'][-1]
    assert failure['gate']=='native:output-prepare' and failure['exit_code']!=0
    assert sha(run/failure['log'])==failure['log_sha256']
    assert proof['retained_gates']==[g for g in prior['completed'] if g.startswith(('desktop:','reference:','headless:'))]
    assert len(proof['retained_gates'])==60
    for name,digest in proof['archived_native_hashes'].items():assert sha(archive/'native'/name)==digest,name
    assert {p.name:sha(p) for p in (archive/'apks').glob('*.apk')}==proof['archived_apk_hashes']
