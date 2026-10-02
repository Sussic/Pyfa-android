"""Validate retained successful group 3 preparation; never rerun instrumentation."""
import json
import os
import re
from evidence_paths import evidence_dir
from mutation_history_summary import _typed_shape,exact,fixture_bytes,state,validate_fixture

evidence=evidence_dir()
os.environ['PYFA_INSTRUMENTATION_APK']=str(evidence.parent/'apks/app-debug-androidTest.apk')
output=(evidence/'mutation-history-3-prepare-instrumentation.txt').read_text(encoding='utf-8')
assert re.search(r'OK \(1 test\)',output) and 'INSTRUMENTATION_CODE: -1' in output
assert not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=',output)
assert 'class=io.github.sussic.pyfa.MutationHistoryTest' in output
assert 'test=remainingHistoryReversesAndPersistsOffline' in output
assert re.findall(r'^INSTRUMENTATION_STATUS_CODE: (-?\d+)\s*$',output,re.M)==['1','0']
report=json.loads((evidence/'mutation-history-3-prepare-native.json').read_text())
exact('B09.2',report['task']);exact(3,report['group']);exact('prepare',report['phase'])
assert type(report['pid']) is int and report['pid']>0
_typed_shape(report['before']);_typed_shape(report['after'])
prior=json.loads((evidence/'mutation-history-2-restored-native.json').read_text())
exact(prior['after'],report['before']);exact(prior['recent_after'],report['recent_before'])
fixture,digest=fixture_bytes();validate_fixture(report,digest)
exact(7,len(report['cases']));states=0
for expected,observed in zip(fixture['cases'][21:28],report['cases']):
    exact(expected['name'],observed['name']);exact(6,len(observed['steps']))
    for step,actual in zip(expected['steps'],observed['steps']):
        exact(step['action'],actual['action'])
        state(expected,step,actual['result'],observed['recent_before']);states+=1
exact(42,states)
print(json.dumps({'retained_instrumentation':'OK (1 test)','reference_cases':7,'reference_states':states,'instrumentation_rerun':False},indent=2))
