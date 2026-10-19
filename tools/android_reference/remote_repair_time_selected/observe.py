"""Candidate-only observational snapshots, never an expected-value calculator."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

LAYERS=('shield','armor','hull','capacitor')

def repair(value):return {name:getattr(value,name) for name in LAYERS}

def row_key(fit,row):
    for family,values in (('module',fit.modules),('drone',fit.drones)):
        for index,value in enumerate(values):
            if value is row:return f'{family}:{index}:{value.item.ID}'
    raise AssertionError('unbound candidate repair key')

def map_rows(fit,values):return [dict(key=row_key(fit,key),repair=repair(value)) for key,value in values.items()]

@contextmanager
def snapshots():
    from android_bridge.offline.remote_repair_time_math import CheckedTimeCache
    records=[];generate=CheckedTimeCache._generateInternalForm;schedule=CheckedTimeCache._schedule;clear=CheckedTimeCache.clearAll
    def generated(cache,src,ancReload,maxTime):
        cache._observed_fit=src.item;cache._observed_cycles=[]
        result=generate(cache,src,ancReload,maxTime)
        data=cache._data[src.item.ID][ancReload]
        record=dict(fit_id=src.item.ID,horizon=data['maxTime'],anc_reload=ancReload,
            cycles=cache._observed_cycles,
            internal_rates=[dict(key=row_key(src.item,k),segments=[dict(start=a,end=b,repair_rate=repair(v)) for a,b,v in values]) for k,values in data['internalRps'].items()],
            internal_amounts=[dict(key=row_key(src.item,k),events=[dict(time=t,repair_amount=repair(v)) for t,v in values.items()]) for k,values in data['internalRepAmount'].items()])
        cache._observed_record=record;records.append(record)
        return result
    def scheduled(cache,row):
        value=schedule(cache,row)
        if value is None:return None
        record=dict(key=row_key(cache._observed_fit,row),cycles=[]);cache._observed_cycles.append(record)
        def cycles():
            for item in value.iterCycles():record['cycles'].append(list(item));yield item
        return SimpleNamespace(iterCycles=cycles)
    def cleared(cache):
        record=getattr(cache,'_observed_record',None)
        if record is not None:
            data=cache._data.get(cache._observed_fit.ID,{}).get(record['anc_reload'],{})
            record['finalRps']=[dict(time=t,rows=map_rows(cache._observed_fit,m)) for t,m in data.get('finalRps',{}).items()]
        result=clear(cache)
        assert not cache._data and not cache._schedules and not cache._active
        if record is not None:record['cleared']=True
        return result
    with patch.object(CheckedTimeCache,'_generateInternalForm',generated),patch.object(CheckedTimeCache,'_schedule',scheduled),patch.object(CheckedTimeCache,'clearAll',cleared):yield records
