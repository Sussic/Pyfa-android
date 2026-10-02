"""Validate native B09.1 independent comparisons, action history and durable reversal."""
from copy import deepcopy
import json
from math import isclose
from pathlib import Path
from market_summary import exact

PREPARE=['complete_original_matrix','touch_repeated_undo_redo','linked_recipients',
    'selection_safety','notes_preserved','fit_isolation','redo_branch_invalidated',
    'history_recreation','stale_rejected','copy_has_no_history','typed_history_protocol']
RESTORED=['fresh_process_restore','reopen_each_fit','session_history_empty','notes_retained']
PROTOCOL=['version','extra','boolean_count','decimal_count','negative_count','overflow',
          'limit','revision','missing_label','unexpected_label']


def _stats(expected,actual):
    exact(set(expected),set(actual))
    for key,row in expected.items():
        exact(row['unit'],actual[key]['unit']);left,right=row['value'],actual[key]['value']
        if right is None and key in ('gun_optimal','gun_falloff'):
            assert left in (0,1)
        elif type(left) in (int,float) and type(right) in (int,float):
            assert isclose(left,right,rel_tol=1e-10,abs_tol=1e-9),(key,left,right)
        else:exact(left,right)


def _typed_shape(value):
    """JSON loses integral-decimal spelling; retained kinds must describe every number."""
    assert value.keys()=={'data','numeric_types'}
    paths={}
    def walk(node,path):
        if type(node) is dict:
            for key,row in node.items():walk(row,path+'.'+key)
        elif type(node) is list:
            for index,row in enumerate(node):walk(row,f'{path}[{index}]')
        elif type(node) in (int,float):paths[path]=node
    walk(value['data'],'root')
    exact(set(paths),set(value['numeric_types']))
    for path,number in paths.items():
        kind=value['numeric_types'][path]
        assert kind in ('integer','decimal')
        if kind=='integer':assert type(number) is int
        if '.stats.' not in path and '.recipients[' not in path:exact('integer',kind)


def _same_values_and_kinds(left,right):
    # Counts/recent intentionally differ across an undo. All actual input/value
    # fields and statistic numeric kinds must return to their earlier native state.
    for key in ('stats','modules','ignore_restrictions','recipients'):
        exact(left['data'][key],right['data'][key])
    for prefix in ('root.stats.','root.modules[','root.recipients['):
        exact({k:v for k,v in left['numeric_types'].items() if k.startswith(prefix)},
              {k:v for k,v in right['numeric_types'].items() if k.startswith(prefix)})


def summarize(reports,engine):
    assert len(reports)==2
    prepare,restored=reports
    exact(['prepare','restored'],[r['phase'] for r in reports])
    assert prepare['pid']!=restored['pid']
    for report in reports:
        assert report['task']=='B09.1'
        for stage in ('runtime_start','runtime_end'):
            runtime=report[stage]
            assert runtime['persistence']['enabled'] and runtime['persistence']['opened_existing']
            assert runtime['android_worker_thread']=='pyfa-engine' and runtime['android_main_thread'] is False
            assert runtime['saveddata_connectionstring']=='sqlite:///:memory:' and not runtime['desktop_import_attempts']
            exact(engine['eos_settings'],runtime['eos_settings'])
            for key in ('database_sha256','database_logical_sha256','engine_source_sha256',
                        'source_data_sha256','desktop_source_commit','dataset_metadata'):
                exact(engine[key],runtime['manifest'][key])
            assert runtime['retained_fit_count']==len(report['before' if stage=='runtime_start' else 'after']['data'])
    assert prepare['runtime_end']['session_id']!=restored['runtime_start']['session_id']
    assert prepare['runtime_end']['persistence']['generation']==restored['runtime_start']['persistence']['generation']
    assert restored['runtime_start']['persistence']['generation']==restored['runtime_end']['persistence']['generation']
    exact(PREPARE,prepare['checks']);exact(RESTORED,restored['checks'])
    exact(PROTOCOL,prepare['protocol_rejections']);exact([],restored['protocol_rejections'])
    exact([],restored['cases']);exact({},restored['observations'])
    exact(prepare['saved'],restored['saved'])
    exact(prepare['before'],prepare['saved']['prior']);exact(prepare['after'],prepare['saved']['fits'])
    exact(prepare['after'],restored['before']);exact(restored['before'],restored['after'])
    for value in (restored['recent_before'],restored['recent_after'],prepare['saved']['recent']):exact(prepare['recent_after'],value)
    old={r['id']:r for r in prepare['before']['data']};new={r['id']:r for r in prepare['after']['data']}
    assert len(old)==90 and len(new)==111
    exact(old,{key:new[key] for key in old})
    ids=prepare['new_ids'];assert len(ids)==len(set(ids))==21 and set(new)-set(old)==set(ids)
    exact(ids,restored['new_ids']);exact(ids,prepare['saved']['new_ids'])
    assert prepare['saved']['active_id']==ids[0]
    assert new[ids[-1]]['name']=='B09 history copy – Δ'
    assert prepare['saved']['notes']=='History preserves notes — 保持'
    exact({'undo_count':0,'redo_count':1,'can_undo':False,'can_redo':True},prepare['saved']['history_before_restart'])
    fixture=json.loads((Path(__file__).resolve().parents[2]/'tools/android_reference/fixtures/history.json').read_text())
    assert len(fixture['cases'])==len(prepare['cases'])==18
    states=0;case_ids=[];recipient_ids=[]
    for expected,observed in zip(fixture['cases'],prepare['cases']):
        exact(expected['name'],observed['name']);case_ids.append(observed['fit_id'])
        assert new[observed['fit_id']]['name']==expected['spec']['name']
        assert len(observed['recipients'])==len(expected.get('recipients',[]))
        recipient_ids+=observed['recipients']
        assert len(expected['steps'])==len(observed['steps'])==6
        for row,actual in zip(expected['steps'],observed['steps']):
            exact(row['action'],actual['action'])
            value=actual['result'];_typed_shape(value);data=value['data'];wanted=deepcopy(row['result'])
            assert set(data)==set(wanted)
            for key in ('modules','ignore_restrictions','history'):exact(wanted[key],data[key])
            _stats(wanted['stats'],data['stats'])
            assert len(wanted['recipients'])==len(data['recipients'])
            for a,b in zip(wanted['recipients'],data['recipients']):_stats(a,b)
            recent=wanted['recent']
            exact((recent+[key for key in observed['recent_before'] if key not in recent])[:20],data['recent'])
            states+=1
        for index in (2,4):_same_values_and_kinds(observed['steps'][0]['result'],observed['steps'][index]['result'])
        for index in (3,5):_same_values_and_kinds(observed['steps'][1]['result'],observed['steps'][index]['result'])
    assert states==108 and len(recipient_ids)==2
    assert set(case_ids+recipient_ids)==set(ids[:-1])
    for report in reports:
        exact(set(ids),set(report['histories']))
        for key,value in report['histories'].items():
            undo=1 if report is prepare and key in case_ids[1:]+recipient_ids else 0
            redo=1 if report is prepare and key==ids[0] else 0
            exact({'undo_count':undo,'redo_count':redo,'can_undo':undo>0,'can_redo':redo>0},value)
    observations=prepare['observations']
    exact({'selection_after_undo','undone','other_history','branched','stale'},set(observations))
    exact([],observations['selection_after_undo'])
    for key in ('other_history','branched','stale'):
        exact({'undo_count':1,'redo_count':0,'can_undo':True,'can_redo':False},observations[key])
    _same_values_and_kinds(prepare['cases'][0]['steps'][0]['result'],observations['undone'])
    return {'reference_cases':18,'reference_states':states,'recipients':2,'new_fits':21,'restored_fits':111,
            'screenshots':6,'protocol_rejections':len(PROTOCOL),'checks':{'prepare':PREPARE,'restored':RESTORED}}
