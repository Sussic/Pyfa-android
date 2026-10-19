"""Ordered time comparison; no numerical candidate code imported."""
from tools.android_reference.remote_repair_amount_distance.compare import exact,numeric,load_original

def curve(expected,actual,label):
    assert set(actual)=={'fit_id','revision','source_rates','x','y'},label
    exact(expected['x'],actual['x'],label+'.ordered coordinates')
    assert 1<=len(expected['x'])==len(expected['y'])==len(actual['y'])<=87210,label
    for i,(a,b) in enumerate(zip(expected['y'],actual['y'])):numeric(a,b,f'{label}.y[{i}]')

def envelope(request,response):
    keys={'version','request_id','ok','error'}
    assert type(response['version']) is int and response['version']==request['version']
    exact(request['request_id'],response['request_id'],'request id')
    if not response['ok']:
        assert response['ok'] is False and set(response)==keys
        assert set(response['error'])=={'code','message'}
        return
    assert response['ok'] is True and response['error'] is None
    echoes={'context','x','y','time','distance','ancillary_reload','ignore_lock_range','ignore_drone_control_range'}
    assert set(response)==keys|echoes|{'total_points','series','effective'}
    for name in echoes:exact(request[name],response[name],'echo '+name)
    assert len(response['series'])==len(request['fits'])
    for requested,series in zip(request['fits'],response['series']):
        exact(requested,{k:series[k] for k in ('fit_id','revision')},'fit order/revision')
        assert set(series['source_rates'])=={'shield','armor','hull'}
    assert type(response['total_points']) is int and response['total_points']==sum(len(s['x']) for s in response['series'])<=87210
    exact(dict(x_range=[min(max(v,0),2500) for v in request['x']['range']],time=None,distance=None if request['distance'] is None else request['distance']*1000),response['effective'],'effective')

def selected_samples(fit):
    for index,sample in enumerate(fit['samples']):
        for c in sample['curves']:
            if c['axis']=='time' and c['range'][1]==sample['request']['horizon']:yield index,sample,c
