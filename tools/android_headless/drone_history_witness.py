"""Register every C04 command with independently exported Do/Undo observations."""
from copy import deepcopy
import json
from tools.android_reference.reference import compare,digest_file
from tools.android_reference.drone_edits import observe,PIN


def witness(bridge,send,fixture):
    expected=json.loads(fixture.read_text(encoding='utf-8')); compare(PIN,expected['source_commit'])
    covered=set(); rows=[]
    for case in expected['cases']:
        op=case['operation']
        if op in covered: continue
        key=send('create_fit',dict(spec=deepcopy(case['spec'])))['fits'][0]['id']
        before=deepcopy(bridge._records[key])
        compare(case['before'],observe(bridge.get_fit(key)))
        send(op,dict(fit_id=key,**case['arguments']))
        compare(case['after'],observe(bridge.get_fit(key)))
        after=deepcopy(bridge._records[key])
        for action,record,state in (('undo',before,'restored'),('redo',after,'after')):
            send(action,dict(fit_id=key))
            compare(case[state],observe(bridge.get_fit(key)))
            compare(record,bridge._records[key])
        covered.add(op); rows.append(dict(operation=op,case=case['spec']['name']))
    return dict(operations=sorted(covered),cases=rows,reference_sha256=digest_file(fixture))


def conservation_witness(bridge,send,fixture):
    """Approved count-table/EOS witnesses, explicitly distinct from desktop commands."""
    expected=json.loads(fixture.read_text(encoding='utf-8'))
    from tools.android_reference.drone_conservation import POLICY
    compare(POLICY,expected['policy']);covered=set();rows=[]
    for case in expected['cases']:
        op=case['operation']
        if op in covered or not case['accepted'] or any('mutation' in r for r in case['spec']['drones']):continue
        key=send('create_fit',dict(spec=deepcopy(case['spec'])))['fits'][0]['id']
        before=deepcopy(bridge._records[key]);compare(case['before']['core'],observe(bridge.get_fit(key)))
        send(op,dict(fit_id=key,**case['arguments']));compare(case['after']['core'],observe(bridge.get_fit(key)))
        after=deepcopy(bridge._records[key])
        for action,record,state in (('undo',before,'before'),('redo',after,'after')):
            send(action,dict(fit_id=key));compare(case[state]['core'],observe(bridge.get_fit(key)));compare(record,bridge._records[key])
        covered.add(op);rows.append(dict(operation=op,case=case['spec']['name']))
    return dict(operations=sorted(covered),cases=rows,reference_sha256=digest_file(fixture),policy=POLICY)
