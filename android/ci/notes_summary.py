"""Validate exact B08 notes, unchanged fits and a real durable process restart."""
import json
from pathlib import Path
from market_summary import exact

PREPARE = ['exact_text_and_character_counts', 'autosave_and_immediate_navigation_flush',
    'correct_fit_switch_and_recreation', 'stale_draft_retry_and_conflict_resolution',
    'structure_readonly_and_durable_copies', 'unchanged_calculations_and_recent_use', 'typed_notes_protocol']
RESTORED = ['fresh_process_restore', 'reopen_each_fit']
PROTOCOL = ['version','extra','null_text','boolean_count','negative_count','wrong_count',
            'decimal_count','editable','revision','surrogate']


def note(text, actual, editable=True):
    exact({'text':text,'characters':len(text),'editable':editable},actual)


def summarize(reports, engine):
    assert len(reports)==2
    prepare,restored=reports
    exact(['prepare','restored'],[row['phase'] for row in reports])
    assert prepare['pid'] != restored['pid']
    for report in reports:
        assert report['task']=='B08'
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
    assert prepare['runtime_end']['session_id'] != restored['runtime_start']['session_id']
    assert prepare['runtime_end']['persistence']['generation']==restored['runtime_start']['persistence']['generation']
    assert restored['runtime_start']['persistence']['generation']==restored['runtime_end']['persistence']['generation']
    exact(PREPARE,prepare['checks']); exact(RESTORED,restored['checks'])
    exact(PROTOCOL,prepare['protocol_rejections']); exact([],restored['protocol_rejections'])
    exact({},restored['observations'])
    exact(prepare['saved'],restored['saved'])
    exact(prepare['before'],prepare['saved']['prior'])
    exact(prepare['after'],prepare['saved']['fits'])
    exact(prepare['after'],restored['before']); exact(restored['before'],restored['after'])
    old={row['id']:row for row in prepare['before']['data']}
    new={row['id']:row for row in prepare['after']['data']}
    assert len(old)==85 and len(new)==90
    exact(old,{key:new[key] for key in old})
    ids=prepare['new_ids']
    assert len(ids)==len(set(ids))==5 and set(new)-set(old)==set(ids)
    exact(ids,restored['new_ids']); exact(ids,prepare['saved']['new_ids'])
    assert prepare['saved']['active_id']==ids[3]
    exact(['B08 alpha – 探索','B08 beta – 探索','B08 structure – 探索',
           'B08 copy alpha – Δ','B08 copy structure – Δ'],[new[key]['name'] for key in ids])
    for value in (prepare['recent_after'],restored['recent_before'],restored['recent_after'],prepare['saved']['recent']):
        exact(prepare['recent_before'],value)
    fixture=json.loads((Path(__file__).resolve().parents[2]/'tools/android_reference/fixtures/notes.json').read_text(encoding='utf-8'))
    assert len(fixture['steps'])==13
    inputs=fixture['inputs']; observations=prepare['observations']
    exact({'empty','unicode','quick_back','switch','clear','recreated','stale','retry','conflict','conflict_saved_draft','structure'},set(observations))
    # Expected saved values come from original timer/navigation service execution.
    for label,index,key in [('empty',0,'alpha'),('unicode',2,'alpha'),('quick_back',4,'alpha'),
                            ('switch',6,'beta'),('clear',8,'alpha'),('recreated',10,'alpha')]:
        note(fixture['steps'][index]['saved'][key] or '',observations[label])
    note(inputs['unicode'],observations['retry'])
    note(inputs['long'],observations['conflict_saved_draft'])
    note(inputs['structure'],observations['structure'],False)
    for label,stored,draft in [('stale','long','unicode'),('conflict','whitespace','long')]:
        exact({'draft','stored'},set(observations[label]))
        exact(inputs[draft],observations[label]['draft']); note(inputs[stored],observations[label]['stored'])
    states=prepare['saved']['notes']
    exact(set(ids),set(states)); exact(states,restored['restored_notes'])
    for index,key in enumerate(('alpha','beta','structure','alpha','structure')):
        note(fixture['copies'][key] or '',states[ids[index]],key!='structure')
    baseline=prepare['saved']['baseline_stats']
    exact(set(ids[:3]),set(baseline))
    for key in ids[:3]:
        exact(baseline[key]['data'],new[key]['stats'])
        for stat,kind in baseline[key]['numeric_types'].items():
            suffix=stat.removeprefix('root.')
            index=next(i for i,row in enumerate(prepare['after']['data']) if row['id']==key)
            exact(kind,prepare['after']['numeric_types'][f'root[{index}].stats.{suffix}'])
    return {'reference_states':13,'new_fits':5,'restored_fits':90,'screenshots':7,
            'protocol_rejections':len(PROTOCOL),'checks':{'prepare':PREPARE,'restored':RESTORED}}
