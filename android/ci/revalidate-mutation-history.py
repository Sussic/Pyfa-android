"""Validate retained group 0 instrumentation; never execute or invent a native result."""
import hashlib
import json
import os
import re
from evidence_paths import evidence_dir
from mutation_history_summary import summarize

evidence=evidence_dir()
os.environ['PYFA_INSTRUMENTATION_APK']=str(evidence.parent/'apks/app-debug-androidTest.apk')
reports=[];hashes={}
for phase in ('prepare','restored'):
    log=evidence/f'mutation-history-0-{phase}-instrumentation.txt'
    output=log.read_text(encoding='utf-8')
    assert re.search(r'OK \(1 test\)',output) and 'INSTRUMENTATION_CODE: -1' in output
    assert not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=',output)
    assert 'class=io.github.sussic.pyfa.MutationHistoryTest' in output
    assert 'test=remainingHistoryReversesAndPersistsOffline' in output
    assert re.findall(r'^INSTRUMENTATION_STATUS_CODE: (-?\d+)\s*$',output,re.M)==['1','0']
    path=evidence/f'mutation-history-0-{phase}-native.json'
    reports.append(json.loads(path.read_text(encoding='utf-8')))
    for file in (log,path):hashes[file.name]=hashlib.sha256(file.read_bytes()).hexdigest()
result=summarize(reports,json.loads((evidence/'engine-native.json').read_text()),
    json.loads((evidence/'history-native.json').read_text()),complete=False)
(evidence/'mutation-history-0-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'validation':'retained successful native instrumentation','summary':result,'retained_hashes':hashes},indent=2))
