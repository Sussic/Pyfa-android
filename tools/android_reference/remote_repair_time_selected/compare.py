"""Pure ordered comparison. This module imports no candidate or EOS calculation."""
import hashlib
import json
import math
from pathlib import Path

PHYSICAL = '68fb9ea965cb046e426f7c068c7508b55a4e82d2a3dceeed3cb948585d6e7203'
LOGICAL = '5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607'
RECEIPTS = ('ordinary-attempt-2.json', 'drones-attempt-1.json', 'spool-attempt-1.json',
            'ancillary-attempt-2.json', 'linked-seed-attempt-2.json',
            'linked-reopen-attempt-2.json', 'resource-attempt-1.json')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def exact(left, right, label):
    assert json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False), label

def numeric(left, right, label):
    assert type(left) in (int, float) and type(right) in (int, float), label
    assert math.isfinite(left) and math.isfinite(right), label
    assert (right == 0 if left == 0 else math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9)), (label,left,right)

def curve(expected, actual, label):
    assert set(actual) == {'fit_id','revision','source_rates','x','y'}, label
    xs = [x / 1000 for x in expected['x']]
    exact(xs, actual['x'], label+'.ordered coordinates')
    assert 1 <= len(xs) == len(expected['y']) == len(actual['y']) <= 201, label
    for index,(left,right) in enumerate(zip(expected['y'],actual['y'])):
        numeric(left,right,f'{label}.y[{index}]')

def envelope(request, response):
    keys = {'version','request_id','ok','error'}
    assert response['version'] == request['version'] and type(response['version']) is int
    exact(request['request_id'],response['request_id'],'request id')
    if not response['ok']:
        assert response['ok'] is False and set(response) == keys
        assert set(response['error']) == {'code','message'}
        return
    assert response['ok'] is True and response['error'] is None
    echoes = {'context','x','y','time','ancillary_reload','ignore_lock_range','ignore_drone_control_range'}
    assert set(response) == keys | echoes | {'total_points','series'} | ({'distance','effective'} if request['version']==2 else set())
    for name in echoes: exact(request[name],response[name],'echo '+name)
    assert len(response['series']) == len(request['fits'])
    for requested,series in zip(request['fits'],response['series']):
        exact(requested, {k:series[k] for k in ('fit_id','revision')},'fit order/revision')
        assert set(series['source_rates'])=={'shield','armor','hull'}
    assert type(response['total_points']) is int and response['total_points']==sum(len(s['x']) for s in response['series'])
    if request['version']==2:
        t=request['time']; t=None if t is None else min(max(t,0),2500)
        exact(None,response['distance'],'distance')
        exact(dict(x_range=request['x']['range'],time=t,distance=None),response['effective'],'effective')

def load_original(path, audit):
    digest = sha(path)
    assert any(row['receipt']==Path(path).name and row['sha256']==digest for row in audit['receipts']), 'Unbound original receipt'
    result=json.loads(Path(path).read_text())
    assert result['status']=='passed' and result['process_nonce']
    assert result['dataset_physical_sha256']==PHYSICAL and result['dataset_logical_sha256']==LOGICAL
    assert result['forbidden_attempts']==result['network_attempts']==[]
    return result

def selected_samples(fit):
    """Only distance curves at their exact generation horizon are reusable."""
    for index,sample in enumerate(fit['samples']):
        if sample['distance_m'] is not None: continue
        for c in sample['curves']:
            if c['axis']=='distance' and c['ordinate']=='rate':
                assert c['time']==sample['request']['horizon']
                yield index,sample,c
