#!/usr/bin/env python3
"""Serial bounded D02.1 proof runner. Owner grants the slot before invocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[3]
ROOT=REPO.parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('original','candidate','reopen'))
    p.add_argument('suite',choices=('composition','incoming','outgoing','publication'))
    p.add_argument('label');p.add_argument('--reverse',action='store_true')
    p.add_argument('--oracle',type=Path);p.add_argument('--store',type=Path)
    a=p.parse_args();folder=ROOT/'multisource-evidence'/a.label
    folder.mkdir(parents=True,exist_ok=False)
    ref=Path('/workspace/scratch/0ee45d4eac42/cloud-source-receipts/pyfa/reconstructed-source')
    files=sorted((REPO/'tools/android_reference/multisource').glob('*.py'))+sorted((REPO/'tools/android_reference/multisource').glob('*.json'))+[REPO/'tools/android_reference/reference.py',REPO/'tools/android_reference/projection.json']
    candidate=REPO/'tools/android_headless/check_multisource_parity.py'
    if candidate.exists():files.append(candidate)
    for path in files:shutil.copy2(path,folder/path.name)
    production=sorted((REPO/'android_bridge').rglob('*.py'))+[REPO/'android/app/src/main/python/mobile_runtime.py']
    originals=sorted((ref/'eos').rglob('*.py'))+sorted((ref/'utils').rglob('*.py'))+sorted((ref/'gui/fitCommands').rglob('*.py'))+[ref/'service/fit.py',ref/'service/ammo.py',ref/'service/market.py',ref/'gui/builtinContextMenus/itemProjectionRange.py']
    binding=dict(harness={str(x.relative_to(REPO)):sha(x) for x in files},production={str(x.relative_to(REPO)):sha(x) for x in production},original={str(x.relative_to(ref)):sha(x) for x in originals},
        database_path=os.environ['PYFA_DATABASE'],database_sha256=sha(Path(os.environ['PYFA_DATABASE'])),dataset_logical_sha256=os.environ['PYFA_DATASET_SHA'],
        source_lineage='8b04f3b271e614b3e103853b44a7851a63d79d0e semantic lineage; reconstructed public745fc1e2 + historicaldirty2e518a2, not clean pinned checkout',
        preserved_projection_sha256=sha(REPO/'tools/android_reference/fixtures/projection.json'))
    output=folder/'output.json'
    if a.mode=='original':
        cmd=[sys.executable,'-B',str(REPO/'tools/android_reference/multisource/oracle.py'),'--source',str(ref),'--database',os.environ['PYFA_DATABASE'],'--suite',a.suite,'--output',str(output)]
    else:
        assert a.oracle and a.oracle.is_file()
        store=a.store or folder/'fits.sqlite'
        cmd=[sys.executable,'-B',str(candidate),'--suite',a.suite,'--output',str(output),'--oracle',str(a.oracle.resolve()),'--store',str(store.resolve()),'--phase',a.mode]
    if a.reverse:cmd.append('--reverse')
    freeze=ROOT/'SOURCE-FREEZE.json'
    if freeze.exists():binding['source_freeze_sha256']=sha(freeze)
    binding['command']=cmd;write(folder/'binding.json',binding)
    def bounded():resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
    start=time.monotonic();code=124
    with (folder/'process.log').open('wb') as log:
        try:code=subprocess.run(cmd,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,timeout=180,preexec_fn=bounded).returncode
        except subprocess.TimeoutExpired:log.write(b'\nHARNESS TIMEOUT 180 seconds\n')
    unchanged=all(sha(REPO/k)==v for group in ('harness','production') for k,v in binding[group].items()) and all(sha(ref/k)==v for k,v in binding['original'].items()) and sha(Path(binding['database_path']))==binding['database_sha256']
    if 'source_freeze_sha256' in binding:unchanged=unchanged and sha(freeze)==binding['source_freeze_sha256']
    result=dict(exit_code=code,seconds=time.monotonic()-start,bound_seconds=180,bound_address_space_bytes=1024**3,inputs_unchanged=unchanged,log_sha256=sha(folder/'process.log'),binding_sha256=sha(folder/'binding.json'))
    write(folder/'result.json',result);print((folder/'process.log').read_text());print(json.dumps(result));raise SystemExit(code or (0 if unchanged else 3))
if __name__=='__main__':main()
