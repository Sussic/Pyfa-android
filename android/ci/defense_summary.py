"""Strict C01.3.1 fixture, defense, durable input and restart validation."""
from copy import deepcopy
from math import isfinite
from pathlib import Path
from evidence_paths import evidence_dir
from resource_summary import fixture_bytes
from capacitor_summary import scalar
from mutation_history_summary import settings
from market_summary import exact

ROOT=Path(__file__).resolve().parents[2]
LAYERS=('shield','armor','hull')
DAMAGE=('em','thermal','kinetic','explosive')
REJECTIONS=['version','extra','missing','unit','boolean','kind','display','revision','missing_layer','missing_resist',
    'multiplier_unit','negative_hp','resistance_over100','pattern_missing','pattern_negative','pattern_zero','pattern_percent','fractional_integer']


def number(expected,actual):
    assert type(expected) in (int,float) and type(actual) in (int,float) and isfinite(expected) and isfinite(actual)
    assert abs(expected-actual)<=max(1e-9,1e-10*max(abs(expected),abs(actual)))


def value(left,right):
    assert set(right)=={'value','value_type','unit','display','detail'}
    scalar(left['value'],right['value'],right['value_type'])
    for key in ('value_type','unit','display','detail'):exact(left[key],right[key])


def defenses(expected,actual):
    exact({'fit_id','revision','defenses'},set(actual))
    assert type(actual['fit_id']) is str and actual['fit_id'] and type(actual['revision']) is int and actual['revision']>=1
    right=actual['defenses'];exact({'layers','total','pattern'},set(right));exact(set(LAYERS),set(right['layers']))
    for layer in LAYERS:
        left,row=expected['layers'][layer],right['layers'][layer]
        exact({'hp','ehp','multiplier','resistances'},set(row))
        for name in ('hp','ehp','multiplier'):value(left[name],row[name])
        exact(set(DAMAGE),set(row['resistances']))
        for name in DAMAGE:value(left['resistances'][name],row['resistances'][name])
    exact({'hp','ehp'},set(right['total']))
    for name in ('hp','ehp'):value(expected['total'][name],right['total'][name])
    exact(set(DAMAGE),set(right['pattern']))
    for name in DAMAGE:
        left,row=expected['pattern'][name],right['pattern'][name];exact({'amount','percentage','display'},set(row))
        number(left['amount'],row['amount']);number(left['percentage'],row['percentage']);exact(left['display'],row['display'])


def typed(value):
    exact({'data','numeric_types'},set(value));paths={}
    def walk(row,path):
        if type(row) is dict:
            for key,item in row.items():walk(item,path+'.'+key)
        elif type(row) is list:
            for index,item in enumerate(row):walk(item,f'{path}[{index}]')
        elif type(row) in (int,float):paths[path]=row
    walk(value['data'],'root');exact(set(paths),set(value['numeric_types']))
    for path,amount in paths.items():
        kind=value['numeric_types'][path];assert kind in ('integer','decimal') and isfinite(amount)
        if kind=='integer':assert type(amount) is int and -(2**63)<=amount<2**63
    return value['data']


def inputs(expected,actual):
    """Kotlin's numeric contribution/security inputs are doubles; reject booleans."""
    if type(expected) is dict:
        assert type(actual) is dict;exact(set(expected),set(actual))
        for key,item in expected.items():inputs(item,actual[key])
    elif type(expected) is list:
        assert type(actual) is list and len(expected)==len(actual)
        for left,right in zip(expected,actual):inputs(left,right)
    elif type(expected) in (int,float):number(expected,actual)
    else:exact(expected,actual)


def fit_inputs(expected,actual):
    # FitSpec omits these two optional defaults. HeadlessEngine.create_fit
    # explicitly defaults omitted restrictions to False and cargo to empty.
    # This concerns declarative input representation only: fixture APK bytes
    # still have to match the reference after CRLF-to-LF normalization only.
    expected=deepcopy(expected)
    for name,default in (('ignore_restrictions',False),('cargo',[])):
        if name in expected and name not in actual:
            exact(default,expected.pop(name))
    inputs(expected,actual)


def summarize(reports,engine,prior_pids=()):
    apk=evidence_dir().parent/'apks/app-debug-androidTest.apk';assert apk.is_file()
    reference=(ROOT/'tools/android_reference/fixtures/defenses.json').read_bytes()
    assert len(reports)==2;pids=set(prior_pids);prepared=None
    for phase,report in zip(('prepare','restored'),reports):
        fixture=fixture_bytes(apk,reference,report['fixture_sha256'],'defenses-expected.json')
        assert fixture['task']=='C01.3.1' and fixture['source_commit']==engine['desktop_source_commit']
        settings(fixture['eos_settings'],engine['eos_settings'])
        assert report['task']=='C01.3.1' and report['phase']==phase
        assert type(report['pid']) is int and report['pid']>0 and report['pid'] not in pids;pids.add(report['pid'])
        start=report['runtime_start'];assert start['persistence']['enabled'] is True and start['persistence']['opened_existing'] is True
        for key in ('desktop_source_commit','database_logical_sha256','engine_source_sha256','source_data_sha256'):exact(engine[key],start['manifest'][key])
        settings(fixture['eos_settings'],start['eos_settings'])
        ids,rows,saved=report['ids'],report['observations'],report['saved']
        assert len(ids)==len(set(ids))==len(rows)==len(fixture['cases'])==14
        assert saved['ids']==ids and len(saved['defenses'])==14
        assert [row['case'] for row in rows]==list(range(14))
        inherited,all_fits=typed(saved['inherited']),typed(saved['all_fits'])
        assert len(inherited)==174 and len(all_fits)==189
        before,after=typed(saved['inherited_graph']),typed(saved['graph'])
        inherited_ids=[row['id'] for row in inherited]
        assert len(set(inherited_ids))==174 and before['fit_order']==inherited_ids and after['fit_order'][:174]==inherited_ids
        assert len(after['fit_order'])==len(set(after['fit_order']))==189 and set(after['fit_order'])==set(after['records'])==set(after['revisions'])==set(after['modified'])
        exact(before['sample_id'],after['sample_id']);exact(before.get('recent',[]),after.get('recent',[]))
        exact(engine['database_logical_sha256'],before['dataset_identity']);exact(before['dataset_identity'],after['dataset_identity'])
        settings(fixture['eos_settings'],before['eos_settings']);settings(fixture['eos_settings'],after['eos_settings'])
        snapshots={row['id']:row for row in all_fits};assert len(snapshots)==189
        assert set(ids)<=set(snapshots) and not set(ids)&set(inherited_ids)
        for row in inherited:
            key=row['id'];exact(row,snapshots[key])
            for field in ('records','revisions','modified'):
                exact(before[field][key],after[field][key])
                prefix=f'root.{field}.{key}'
                exact({k:v for k,v in saved['inherited_graph']['numeric_types'].items() if k==prefix or k.startswith(prefix+'.') or k.startswith(prefix+'[')},
                    {k:v for k,v in saved['graph']['numeric_types'].items() if k==prefix or k.startswith(prefix+'.') or k.startswith(prefix+'[')})
        for index,(case,key,retained,row) in enumerate(zip(fixture['cases'],ids,saved['defenses'],rows)):
            original=deepcopy(case['spec']);original['name']='C01.3.1 '+original['name']
            wanted=case['expected']['defenses']
            if index==0:original['damage_pattern']=fixture['pattern_edits']['steps'][3]['pattern'];wanted=fixture['pattern_edits']['steps'][3]['expected']
            record=after['records'][key];exact({'spec','skills','implants','projections','commands'},set(record));fit_inputs(original,record['spec'])
            for field in ('skills','implants','projections','commands'):exact({} if field=='skills' else [],record[field])
            assert snapshots[key]['name']==original['name'] and snapshots[key]['ship']==original['ship']
            assert snapshots[key]['modules']==[dict(index=i,**module) for i,module in enumerate(original['modules'])]
            for field in ('skills','implants','projections','commands'):exact({} if field=='skills' else [],snapshots[key][field])
            assert row['actual']['fit_id']==retained['fit_id']==key and retained['revision']==after['revisions'][key]
            defenses(wanted,retained)
            defenses(case['expected']['defenses'] if phase=='prepare' else wanted,row['actual'])
            if phase=='restored' or index!=0:exact(row['actual'],retained)
        copies=set(after['fit_order'])-set(inherited_ids)-set(ids);assert len(copies)==1;copy=copies.pop()
        original=deepcopy(after['records'][ids[0]]);original['spec']['name']='C01.3.1 copy';exact(original,after['records'][copy])
        assert snapshots[copy]['name']=='C01.3.1 copy'
        exact(copy,saved['copy_id']);exact(saved['copy_defense'],report['copy_observation'])
        assert saved['copy_defense']['fit_id']==copy and saved['copy_defense']['revision']==after['revisions'][copy]
        defenses(fixture['pattern_edits']['steps'][3]['expected'],report['copy_observation'])
        exact({k:v for k,v in snapshots[ids[0]].items() if k not in ('id','name','revision')},
            {k:v for k,v in snapshots[copy].items() if k not in ('id','name','revision')})
        edits=saved['edits'];assert len(edits)==len(fixture['pattern_edits']['steps'])==4
        for step,edit in zip(fixture['pattern_edits']['steps'],edits):
            exact({'field','after','redo'},set(edit));exact(step['field'],edit['field'])
            for key in ('after','redo'):
                assert edit[key]['fit_id']==ids[0];defenses(step['expected'],edit[key])
            assert edit['redo']['revision']>edit['after']['revision']
        if phase=='prepare':
            assert saved['pid']==report['pid'];exact(REJECTIONS,report['protocol_rejections']);prepared=saved
        else:
            exact([],report['protocol_rejections']);exact(prepared,saved);assert saved['pid']!=report['pid']
    return dict(task='C01.3.1',complete=True,cases=14,layers=3,resistances=12,independent_contribution_edits=4,
        durable_fits=14,saved_fits=189,inherited_fits=174,copy_checked=True,process_restart=True,protocol_rejections=len(REJECTIONS))
