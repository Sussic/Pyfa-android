"""C02 strict independent output scalar/presentation comparisons."""
from capacitor_summary import scalar
from market_summary import exact
from copy import deepcopy
from pathlib import Path
from evidence_paths import evidence_dir
from resource_summary import fixture_bytes
from defense_summary import typed, fit_inputs
from mutation_history_summary import settings

ROOT=Path(__file__).resolve().parents[2]
REJECTIONS=['version','extra','missing','unit','boolean','kind','display','revision',
    'missing_mode','missing_damage','missing_spool','spool_flag','bomb_level','bomb_type',
    'mining_unit','outgoing_unit','fractional_integer','profile_flag']


def output(expected, actual, expected_profile):
    exact({'fit_id','revision','output','target_profile'},set(actual))
    assert type(actual['fit_id']) is str and actual['fit_id']
    assert type(actual['revision']) is int and actual['revision'] >= 1
    profile = actual['target_profile']
    if expected_profile is None:
        assert profile is None
    else:
        assert type(profile) is dict;exact(set(expected_profile),set(profile))
        for key,value in expected_profile.items():
            if value is None:assert profile[key] is None
            else:assert type(profile[key]) in (int,float) and value == profile[key]
    exact(expected_profile is not None,actual['output']['effective'])

    def compare(left,right):
        if type(left) is dict:
            assert type(right) is dict;exact(set(left),set(right))
            if set(left)=={'value','value_type','unit','display','detail'}:
                scalar(left['value'],right['value'],right['value_type'])
                for key in ('value_type','unit','display','detail'):exact(left[key],right[key])
            else:
                for key in left:compare(left[key],right[key])
        elif type(left) is list:
            assert type(right) is list and len(left)==len(right)
            for a,b in zip(left,right):compare(a,b)
        else:
            exact(left,right)
    compare(expected['output'],actual['output'])


def summarize(reports,engine,prior_pids=()):
    apk=evidence_dir().parent/'apks/app-debug-androidTest.apk';assert apk.is_file()
    reference=(ROOT/'tools/android_reference/fixtures/output.json').read_bytes()
    assert len(reports)==2;pids=set(prior_pids);prepared=None
    for phase,report in zip(('prepare','restored'),reports):
        fixture=fixture_bytes(apk,reference,report['fixture_sha256'],'output-expected.json')
        assert fixture['task']=='C02' and fixture['source_commit']==engine['desktop_source_commit']
        settings(fixture['eos_settings'],engine['eos_settings'])
        assert report['task']=='C02' and report['phase']==phase
        assert type(report['pid']) is int and report['pid']>0 and report['pid'] not in pids;pids.add(report['pid'])
        start=report['runtime_start'];assert start['persistence']['enabled'] is True and start['persistence']['opened_existing'] is True
        for key in ('desktop_source_commit','database_logical_sha256','engine_source_sha256','source_data_sha256'):exact(engine[key],start['manifest'][key])
        settings(fixture['eos_settings'],start['eos_settings'])
        ids,rows,saved=report['ids'],report['observations'],report['saved']
        assert len(ids)==len(set(ids))==len(rows)==len(fixture['cases'])==37
        exact(ids,saved['ids']);assert len(saved['outputs'])==37;exact(list(range(37)),[r['case'] for r in rows])
        inherited,all_fits=typed(saved['inherited']),typed(saved['all_fits'])
        before,after=typed(saved['inherited_graph']),typed(saved['graph'])
        old=[row['id'] for row in inherited]
        assert len(old)==len(set(old))==230 and len(all_fits)==268
        exact(old,before['fit_order']);exact(old,after['fit_order'][:230])
        assert len(after['fit_order'])==len(set(after['fit_order']))==268
        assert set(after['fit_order'])==set(after['records'])==set(after['revisions'])==set(after['modified'])
        exact(before['sample_id'],after['sample_id']);exact(before.get('recent',[]),after.get('recent',[]))
        exact(engine['database_logical_sha256'],before['dataset_identity']);exact(before['dataset_identity'],after['dataset_identity'])
        settings(fixture['eos_settings'],before['eos_settings']);settings(fixture['eos_settings'],after['eos_settings'])
        snapshots={row['id']:row for row in all_fits};assert len(snapshots)==268
        assert set(ids)<=set(snapshots) and not set(ids)&set(old)
        for row in inherited:
            key=row['id'];exact(row,snapshots[key])
            for field in ('records','revisions','modified'):
                exact(before[field][key],after[field][key]);prefix=f'root.{field}.{key}'
                def metadata(wrapper):return {k:v for k,v in wrapper['numeric_types'].items() if k==prefix or k.startswith(prefix+'.') or k.startswith(prefix+'[')}
                exact(metadata(saved['inherited_graph']),metadata(saved['graph']))
        for index,(case,key,row,retained) in enumerate(zip(fixture['cases'],ids,rows,saved['outputs'])):
            spec=deepcopy(case['spec']);spec['name']='C02 '+spec['name']
            record=after['records'][key];exact({'spec','skills','implants','projections','commands'},set(record));fit_inputs(spec,record['spec'])
            snapshot=snapshots[key];exact(spec['name'],snapshot['name']);exact(spec['ship'],snapshot['ship'])
            exact([dict(index=i,**m) for i,m in enumerate(spec['modules'])],snapshot['modules'])
            for field in ('skills','implants','projections','commands'):
                expected={} if field=='skills' else [];exact(expected,record[field]);exact(expected,snapshot[field])
            exact(after['revisions'][key],snapshot['revision']);exact(key,retained['fit_id']);exact(after['revisions'][key],retained['revision'])
            output(case['expected'],retained,case['spec']['target_profile']);output(case['expected'],row['actual'],case['spec']['target_profile'])
            exact(retained['fit_id'],row['actual']['fit_id']);exact(retained['output'],row['actual']['output']);exact(retained['target_profile'],row['actual']['target_profile'])
            delta=6 if phase=='prepare' and index==35 else 0
            exact(row['actual']['revision']+delta,retained['revision'])
        copies=set(after['fit_order'])-set(old)-set(ids);assert len(copies)==1;copied=copies.pop();exact(copied,saved['copy_id'])
        original=deepcopy(after['records'][ids[35]]);original['spec']['name']='C02 copy';exact(original,after['records'][copied])
        exact({k:v for k,v in snapshots[ids[35]].items() if k not in ('id','name','revision')},{k:v for k,v in snapshots[copied].items() if k not in ('id','name','revision')})
        exact(copied,saved['copy_output']['fit_id']);exact(after['revisions'][copied],saved['copy_output']['revision'])
        exact(saved['copy_output'],report['copy_observation']);output(fixture['cases'][35]['expected'],report['copy_observation'],fixture['cases'][35]['spec']['target_profile'])
        edits=saved['edits'];assert len(edits)==2
        hp,clear=edits;exact({'action','after','redo'},set(hp));exact('profile_hp',hp['action'])
        for field,revision in (('after',2),('redo',4)):
            exact(ids[35],hp[field]['fit_id']);exact(revision,hp[field]['revision']);output(fixture['cases'][36]['expected'],hp[field],fixture['cases'][36]['spec']['target_profile'])
        exact({'action','after','restored'},set(clear));exact('profile_clear',clear['action'])
        wanted=deepcopy(fixture['cases'][35]['expected']);wanted['output']['effective']=False
        wanted['output']['firepower']['effective']=deepcopy(wanted['output']['firepower']['raw'])
        exact(ids[35],clear['after']['fit_id']);exact(6,clear['after']['revision']);output(wanted,clear['after'],None)
        exact(ids[35],clear['restored']['fit_id']);exact(7,clear['restored']['revision']);output(fixture['cases'][35]['expected'],clear['restored'],fixture['cases'][35]['spec']['target_profile'])
        if phase=='prepare':
            exact(report['pid'],saved['pid']);exact(REJECTIONS,report['protocol_rejections']);prepared=saved
        else:
            assert saved['pid']!=report['pid'];exact(prepared,saved);exact([],report['protocol_rejections'])
    return dict(task='C02',complete=True,cases=37,firepower_modes=2,bomb_cells=24,outgoing_types=4,
                saved_fits=268,inherited_fits=230,copy_checked=True,process_restart=True,protocol_rejections=len(REJECTIONS))
