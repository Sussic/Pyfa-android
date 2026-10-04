"""C03.1 exact independent targeting/navigation scalar and presentation checks."""
from capacitor_summary import scalar
from market_summary import exact
from copy import deepcopy
import hashlib,json
from pathlib import Path
from evidence_paths import evidence_dir
from resource_summary import fixture_bytes
from mutation_history_summary import settings
from defense_summary import typed,fit_inputs

ROOT=Path(__file__).resolve().parents[2]
REJECTIONS=['version','extra','missing','unit','boolean','kind','display','revision','missing_hold','changed_hold','hold_order','missing_lock','lock_radius','sensor_type','negative','fractional_integer','hold_presence','target_count_kind']


def targeting(expected,actual):
    """Compare every field/member; no JSON-equivalence or absent-to-zero coercion."""
    if type(expected) is dict:
        assert type(actual) is dict
        exact(set(expected),set(actual))
        if set(expected)=={'value','value_type','unit','display','detail'}:
            scalar(expected['value'],actual['value'],actual['value_type'])
            for key in ('value_type','unit','display','detail'):exact(expected[key],actual[key])
        else:
            for key in expected:targeting(expected[key],actual[key])
    elif type(expected) is list:
        assert type(actual) is list and len(expected)==len(actual)
        for left,right in zip(expected,actual):targeting(left,right)
    else:exact(expected,actual)


def observation(expected,actual,key,revision):
    exact({'fit_id','revision','targeting'},set(actual))
    exact(key,actual['fit_id']);assert type(revision) is int and revision>=1
    exact(revision,actual['revision']);targeting(expected['targeting'],actual['targeting'])


def skill_inputs(fixture,engine):
    """Require the independently exported full EOS cascade, including exact None."""
    witness=json.loads((ROOT/'tools/android_reference/fixtures/targeting-skill-inputs.json').read_text(encoding='utf-8'))
    exact('C03.1',witness['task']);exact(fixture['source_commit'],witness['source_commit'])
    exact(engine['database_logical_sha256'],witness['database_logical_sha256']);settings(fixture['eos_settings'],witness['eos_settings'])
    assert witness['eos_settings']['strictSkillLevels'] is True
    normalized=(ROOT/'tools/android_reference/fixtures/targeting.json').read_bytes().replace(b'\r\n',b'\n')
    exact(hashlib.sha256(normalized).hexdigest(),witness['targeting_fixture_normalized_sha256'])
    character=(ROOT/'eos/saveddata/character.py').read_bytes().replace(b'\r\n',b'\n')
    exact(hashlib.sha256(character).hexdigest(),witness['character_source_sha256'])
    assert len(witness['cases'])==53
    for index,(case,row) in enumerate(zip(fixture['cases'],witness['cases'])):
        exact({'case','spec','edits','skills'},set(row));exact(index,row['case'])
        exact(case['spec'],row['spec']);exact(case['edits'],row['edits'])
        assert type(row['skills']) is dict
        for name,level in row['skills'].items():assert type(name) is str and name and (level is None or type(level) is int and 0<=level<=5)
    return witness['cases']


def metadata_groups(wrapper,prefixes):
    """Index exactly the old prefix filters, including overlapping opaque IDs."""
    groups={prefix:{} for prefix in prefixes};trie={}
    for prefix in groups:
        node=trie
        for char in prefix:node=node.setdefault(char,{})
        node[None]=prefix
    for name,kind in wrapper['numeric_types'].items():
        node=trie
        for index,char in enumerate(name):
            node=node.get(char)
            if node is None:break
            prefix=node.get(None)
            if prefix is not None and (index+1==len(name) or name[index+1] in '.['):
                groups[prefix][name]=kind
    return groups


def summarize(reports,engine,prior_pids=()):
    apk=evidence_dir().parent/'apks/app-debug-androidTest.apk';assert apk.is_file()
    reference=(ROOT/'tools/android_reference/fixtures/targeting.json').read_bytes()
    expected_skills=skill_inputs(json.loads(reference),engine)
    assert len(reports)==4;pids=set(prior_pids);prepared=None;previous=None
    for phase,report in zip(('prepare0','prepare1','prepare2','restored'),reports):
        count={'prepare0':33,'prepare1':45,'prepare2':53,'restored':53}[phase]
        full=phase in ('prepare2','restored');total=325 if full else 268+count
        fixture=fixture_bytes(apk,reference,report['fixture_sha256'],'targeting-expected.json')
        assert fixture['task']=='C03.1' and fixture['source_commit']==engine['desktop_source_commit']
        settings(fixture['eos_settings'],engine['eos_settings']);assert len(fixture['hull_inventory'])==437
        assert len(fixture['hold_attributes'])==21 and len(fixture['reference_targets'])==8
        assert set(fixture['available_holds'])|set(fixture['absent_holds'])==set(fixture['hold_attributes'])
        assert not set(fixture['available_holds'])&set(fixture['absent_holds'])
        assert report['task']=='C03.1' and report['phase']==phase
        assert type(report['pid']) is int and report['pid']>0 and report['pid'] not in pids;pids.add(report['pid'])
        start=report['runtime_start'];assert start['persistence']['enabled'] is True and start['persistence']['opened_existing'] is True
        for key in ('desktop_source_commit','database_logical_sha256','engine_source_sha256','source_data_sha256'):exact(engine[key],start['manifest'][key])
        settings(fixture['eos_settings'],start['eos_settings'])
        stage=report['stage_start'];exact({'graph','all_fits'},set(stage))
        if previous is None:
            exact(report['saved']['inherited_graph'],stage['graph']);exact(report['saved']['inherited'],stage['all_fits'])
        else:
            exact(previous['graph'],stage['graph']);exact(previous['all_fits'],stage['all_fits'])
        ids,rows,saved=report['ids'],report['observations'],report['saved']
        assert len(fixture['cases'])==53 and len(ids)==len(set(ids))==len(rows)==count
        exact(ids,saved['ids']);assert len(saved['outputs'])==count;exact(list(range(count)),[row['case'] for row in rows])
        inherited,all_fits=typed(saved['inherited']),typed(saved['all_fits'])
        before,after=typed(saved['inherited_graph']),typed(saved['graph'])
        old=[row['id'] for row in inherited];assert len(old)==len(set(old))==268 and len(all_fits)==total
        exact(old,before['fit_order']);exact(old,after['fit_order'][:268])
        assert len(after['fit_order'])==len(set(after['fit_order']))==total
        assert set(after['fit_order'])==set(after['records'])==set(after['revisions'])==set(after['modified'])
        exact(before['sample_id'],after['sample_id']);exact(engine['database_logical_sha256'],before['dataset_identity']);exact(before['dataset_identity'],after['dataset_identity'])
        settings(fixture['eos_settings'],before['eos_settings']);settings(fixture['eos_settings'],after['eos_settings'])
        cargo_case=next(case for case in fixture['cases'] if case['spec']['name']=='Cargo tooltip refresh')
        cargo_item=cargo_case['edits'][0]['args']['item_id']
        wanted_recent=([cargo_item]+[i for i in before.get('recent',[]) if i!=cargo_item])[:20] if full else before.get('recent',[])
        exact(wanted_recent,after.get('recent',[]))
        snapshots={row['id']:row for row in all_fits};assert len(snapshots)==total and set(snapshots)==set(after['fit_order'])
        assert set(ids)<=set(snapshots) and not set(ids)&set(old)
        prefixes=[f'root.{field}.{key}' for key in old for field in ('records','revisions','modified')]
        before_metadata=metadata_groups(saved['inherited_graph'],prefixes);after_metadata=metadata_groups(saved['graph'],prefixes)
        for row in inherited:
            key=row['id'];exact(row,snapshots[key])
            for field in ('records','revisions','modified'):
                exact(before[field][key],after[field][key]);prefix=f'root.{field}.{key}'
                exact(before_metadata[prefix],after_metadata[prefix])
        ui=saved['ui_history'];ui_index=next(i for i,case in enumerate(fixture['cases']) if case['spec']['name']=='Drone range' and case['edits'])
        exact(ui_index,ui['case']);exact({'case','before','undone','redone'},set(ui))
        ui_case=fixture['cases'][ui_index]
        for field,expected,revision in (('before',ui_case['expected'],4),('undone',ui_case['initial'],5),('redone',ui_case['expected'],6)):
            observation(expected,ui[field],ids[ui_index],revision)
        sources=[];expected_order=list(old);edit_indices=[]
        for index,(case,key,row,retained) in enumerate(zip(fixture['cases'],ids,rows,saved['outputs'])):
            expected_order.append(key);spec=deepcopy(case['spec']);spec['name']='C03 '+spec['name'];skills=expected_skills[index]['skills']
            for edit in case['edits']:
                operation,args=edit['operation'],edit['args']
                if operation=='set_module_states':
                    for position in args['module_indices']:spec['modules'][position]['state']=args['state']
                elif operation=='set_skill_level':pass # Full original EOS cascade is independently exported above.
                elif operation=='add_cargo':spec['cargo']=[dict(name='Antimatter Charge M',amount=args['quantity'])]
                else:raise AssertionError('Unexpected reference operation')
            record=after['records'][key];exact({'spec','skills','implants','projections','commands'},set(record));fit_inputs(spec,record['spec'])
            snapshot=snapshots[key];exact(spec['name'],snapshot['name']);exact(spec['ship'],snapshot['ship'])
            exact([dict(index=i,**m) for i,m in enumerate(spec['modules'])],snapshot['modules'])
            projections=[]
            if 'source_spec' in case:
                assert len(record['projections'])==1;source=record['projections'][0]['source_id']
                assert source not in sources and source not in ids and source not in old;sources.append(source);expected_order.append(source)
                source_spec=deepcopy(case['source_spec']);source_spec['name']='C03 '+source_spec['name']
                source_record=after['records'][source];exact({'spec','skills','implants','projections','commands'},set(source_record));fit_inputs(source_spec,source_record['spec'])
                source_snapshot=snapshots[source];exact(source_spec['name'],source_snapshot['name']);exact(source_spec['ship'],source_snapshot['ship'])
                exact([dict(index=i,**m) for i,m in enumerate(source_spec['modules'])],source_snapshot['modules'])
                for field in ('skills','implants','projections','commands'):
                    wanted={} if field=='skills' else [];exact(wanted,source_record[field]);exact(wanted,source_snapshot[field])
                exact(after['revisions'][source],source_snapshot['revision'])
                projections=[dict(source_id=source,range_m=None,active=True,amount=1)]
            for field,wanted in (('skills',skills),('implants',[]),('projections',projections),('commands',[])):
                exact(wanted,record[field]);exact(wanted,snapshot[field])
            mutated=bool(case['edits'] or 'source_spec' in case)
            revision=6 if index==ui_index else 4 if mutated else 1
            exact(revision,after['revisions'][key]);exact(revision,snapshot['revision'])
            observation(case['expected'],retained,key,revision)
            observation(case['expected'],row['actual'],key,revision)
            if mutated:edit_indices.append(index)
        exact(edit_indices,[edit['case'] for edit in saved['edits']])
        for edit in saved['edits']:
            index=edit['case'];case=fixture['cases'][index];exact({'case','applied','undone','redone'},set(edit))
            for field,expected,revision in (('applied',case['expected'],2),('undone',case['initial'],3),('redone',case['expected'],4)):
                observation(expected,edit[field],ids[index],revision)
        assert len(sources)==(3 if full else 0)
        owner_index=next(i for i,case in enumerate(fixture['cases']) if case['spec']['name']=='Targeting Vexor')
        if full:
            copied=saved['copy_id'];assert copied not in old and copied not in ids and copied not in sources
            expected_order.append(copied)
            original=deepcopy(after['records'][ids[owner_index]]);original['spec']['name']='C03 copy';exact(original,after['records'][copied])
            exact(3,after['revisions'][copied]);exact(3,snapshots[copied]['revision'])
            exact({k:v for k,v in snapshots[ids[owner_index]].items() if k not in ('id','name','revision')},{k:v for k,v in snapshots[copied].items() if k not in ('id','name','revision')})
            observation(fixture['cases'][owner_index]['expected'],saved['copy_targeting'],copied,3);exact(saved['copy_targeting'],report['copy_observation'])
        else:
            for value in (saved['copy_id'],saved['copy_targeting'],report['copy_observation']):assert value is None
        exact(expected_order,after['fit_order'])
        if phase=='restored':assert saved['pid']!=report['pid'];exact(prepared,saved)
        else:exact(report['pid'],saved['pid'])
        exact(REJECTIONS if phase=='prepare2' else [],report['protocol_rejections'])
        if previous is not None:
            for field in ('ids','edits','outputs'):
                exact(previous[field],saved[field][:len(previous[field])])
            for field in ('inherited','inherited_graph','ui_history'):exact(previous[field],saved[field])
            previous_graph=typed(previous['graph'])
            for key in previous_graph['fit_order']:
                for field in ('records','revisions','modified'):exact(previous_graph[field][key],after[field][key])
        previous=saved
        if phase=='prepare2':prepared=saved
    return dict(task='C03.1',complete=True,cases=53,hold_attributes=21,available_holds=14,absent_holds=7,reference_targets=8,
        saved_fits=325,inherited_fits=268,copy_checked=True,process_restart=True,protocol_rejections=len(REJECTIONS))
