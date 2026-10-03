"""C01.3.2 strict tank scalar and original presentation comparisons."""
from capacitor_summary import scalar
from copy import deepcopy
import json
from pathlib import Path
from evidence_paths import evidence_dir
from resource_summary import fixture_bytes
from defense_summary import typed, fit_inputs
from market_summary import exact
from mutation_history_summary import settings

ROOT = Path(__file__).resolve().parents[2]
REJECTIONS = ['version','extra','missing','unit','boolean','kind','display','revision',
    'missing_mode','missing_repair','spool_flag','spool_tooltip','spool_missing','fractional_integer']


def tank(expected, actual):
    assert set(actual) == {'fit_id', 'revision', 'tank'}
    assert type(actual['fit_id']) is str and actual['fit_id']
    assert type(actual['revision']) is int and actual['revision'] >= 1
    left, right = expected['tank'], actual['tank']
    assert set(left) == set(right) == {'raw', 'effective'}

    def value(reference, observed):
        assert set(observed) == set(reference) == {'value', 'value_type', 'unit', 'display', 'detail'}
        scalar(reference['value'], observed['value'], observed['value_type'])
        for key in ('value_type', 'unit', 'display', 'detail'):
            assert reference[key] == observed[key]

    for mode in left:
        assert set(left[mode]) == set(right[mode]) == {'passive_shield', 'reinforced', 'sustained'}
        value(left[mode]['passive_shield'], right[mode]['passive_shield'])
        for stability in ('reinforced', 'sustained'):
            reference, observed = left[mode][stability], right[mode][stability]
            assert set(observed) == set(reference) == {'repairs', 'armor_spool'}
            assert set(observed['repairs']) == set(reference['repairs']) == {'shieldRepair', 'armorRepair', 'hullRepair'}
            for name in reference['repairs']:
                value(reference['repairs'][name], observed['repairs'][name])
            reference, observed = reference['armor_spool'], observed['armor_spool']
            assert set(observed) == set(reference) == {'pre', 'full', 'indicated', 'tooltip'}
            for name in ('pre', 'full'):
                value(reference[name], observed[name])
            assert type(observed['indicated']) is bool and reference['indicated'] == observed['indicated']
            assert type(observed['tooltip']) is str and reference['tooltip'] == observed['tooltip']


def recent_after_removal(previous, module_id):
    assert type(previous) is list and len(previous) <= 20
    assert all(type(i) is int and 0 < i < 2**63 for i in previous)
    assert len(previous) == len(set(previous)) and type(module_id) is int and 0 < module_id < 2**63
    # Original module removal promotes the removed item; Undo does not rewind
    # equipment recent use and Redo promotes that same item again.
    return [module_id, *[i for i in previous if i != module_id][:19]]


def summarize(reports, engine, prior_pids=()):
    apk = evidence_dir().parent/'apks/app-debug-androidTest.apk'
    assert apk.is_file(), 'Retained verified test APK required'
    reference = (ROOT/'tools/android_reference/fixtures/tank.json').read_bytes()
    assert len(reports) == 2
    pids = set(prior_pids); prepared = None
    for phase, report in zip(('prepare','restored'), reports):
        fixture = fixture_bytes(apk, reference, report['fixture_sha256'], 'tank-expected.json')
        assert fixture['task'] == 'C01.3.2' and fixture['source_commit'] == engine['desktop_source_commit']
        settings(fixture['eos_settings'], engine['eos_settings'])
        assert report['task'] == 'C01.3.2' and report['phase'] == phase
        assert type(report['pid']) is int and report['pid'] > 0 and report['pid'] not in pids
        pids.add(report['pid'])
        start = report['runtime_start']
        assert start['persistence']['enabled'] is True and start['persistence']['opened_existing'] is True
        for key in ('desktop_source_commit','database_logical_sha256','engine_source_sha256','source_data_sha256'):
            exact(engine[key], start['manifest'][key])
        settings(fixture['eos_settings'], start['eos_settings'])
        ids, rows, saved = report['ids'], report['observations'], report['saved']
        assert len(ids) == len(set(ids)) == len(rows) == len(fixture['cases']) == 29
        exact(ids, saved['ids']); assert len(saved['tanks']) == 29
        exact(list(range(29)), [row['case'] for row in rows])
        inherited, all_fits = typed(saved['inherited']), typed(saved['all_fits'])
        before, after = typed(saved['inherited_graph']), typed(saved['graph'])
        inherited_ids = [row['id'] for row in inherited]
        assert len(inherited_ids) == len(set(inherited_ids)) == 189 and len(all_fits) == 230
        exact(inherited_ids, before['fit_order']); exact(inherited_ids, after['fit_order'][:189])
        assert len(after['fit_order']) == len(set(after['fit_order'])) == 230
        assert set(after['fit_order']) == set(after['records']) == set(after['revisions']) == set(after['modified'])
        exact(before['sample_id'], after['sample_id'])
        catalog = json.loads((ROOT/'tools/android_reference/fixtures/equipment.json').read_text(encoding='utf-8'))['catalog']['items']
        module_name = fixture['cases'][4]['spec']['modules'][0]['name']
        exact('Medium Armor Repairer II', module_name)
        module_ids = [row['id'] for row in catalog if row['name'] == module_name]
        exact([3530], module_ids)
        exact(recent_after_removal(before.get('recent',[]), module_ids[0]), after.get('recent',[]))
        exact(engine['database_logical_sha256'], before['dataset_identity']); exact(before['dataset_identity'], after['dataset_identity'])
        settings(fixture['eos_settings'], before['eos_settings']); settings(fixture['eos_settings'], after['eos_settings'])
        snapshots = {row['id']:row for row in all_fits}; assert len(snapshots) == 230
        assert set(ids) <= set(snapshots) and not set(ids) & set(inherited_ids)
        for row in inherited:
            key = row['id']; exact(row, snapshots[key])
            for field in ('records','revisions','modified'):
                exact(before[field][key], after[field][key])
                prefix = f'root.{field}.{key}'
                def metadata(wrapper): return {k:v for k,v in wrapper['numeric_types'].items()
                    if k == prefix or k.startswith(prefix+'.') or k.startswith(prefix+'[')}
                exact(metadata(saved['inherited_graph']), metadata(saved['graph']))
        sources = saved['sources']
        assert set(sources) == {ids[i] for i,case in enumerate(fixture['cases']) if 'source' in case}
        assert len(sources) == len(set(sources.values())) == 11
        assert not set(sources.values()) & (set(ids) | set(inherited_ids))

        def record(key, spec, projections=()):
            original = deepcopy(spec); original['name'] = 'C01.3.2 ' + original['name']
            actual = after['records'][key]
            exact({'spec','skills','implants','projections','commands'}, set(actual)); fit_inputs(original, actual['spec'])
            for field in ('skills','implants','commands'): exact({} if field == 'skills' else [], actual[field])
            exact(list(projections), actual['projections'])
            snapshot = snapshots[key]
            exact(original['name'], snapshot['name']); exact(original['ship'], snapshot['ship'])
            exact([dict(index=i,**m) for i,m in enumerate(original['modules'])], snapshot['modules'])
            for field in ('skills','implants','commands'): exact({} if field == 'skills' else [], snapshot[field])
            exact(list(projections), snapshot['projections']); exact(after['revisions'][key], snapshot['revision'])

        for case, key, row, retained in zip(fixture['cases'], ids, rows, saved['tanks']):
            edge = []
            if 'source' in case:
                sender = sources[key]; record(sender, case['source'])
                edge = [dict(source_id=sender, **case['projection'])]
            record(key, case['spec'], edge)
            exact(key, retained['fit_id']); exact(after['revisions'][key], retained['revision'])
            tank(case['expected'], retained); tank(case['expected'], row['actual']); exact(retained, row['actual'])
        copies = set(after['fit_order']) - set(inherited_ids) - set(ids) - set(sources.values())
        assert len(copies) == 1; copy = copies.pop(); exact(copy, saved['copy_id'])
        original = deepcopy(after['records'][ids[23]]); original['spec']['name'] = 'C01.3.2 copy'
        exact(original, after['records'][copy])
        exact({k:v for k,v in snapshots[ids[23]].items() if k not in ('id','name','revision')},
              {k:v for k,v in snapshots[copy].items() if k not in ('id','name','revision')})
        exact(copy, saved['copy_tank']['fit_id']); exact(after['revisions'][copy], saved['copy_tank']['revision'])
        exact(saved['copy_tank'], report['copy_observation']); tank(fixture['cases'][23]['expected'], report['copy_observation'])
        edits = saved['edits']; assert len(edits) == 3
        for edit, action, expected_index, owner_index in zip(edits, ('offline','remove_module','remove_projection'), (6,0,24), (4,4,23)):
            exact({'action','after','redo'}, set(edit)); exact(action, edit['action'])
            for field in ('after','redo'):
                exact(ids[owner_index], edit[field]['fit_id']); tank(fixture['cases'][expected_index]['expected'], edit[field])
            assert edit['redo']['revision'] > edit['after']['revision']
        if phase == 'prepare':
            exact(report['pid'], saved['pid']); exact(REJECTIONS, report['protocol_rejections']); prepared = saved
        else:
            assert saved['pid'] != report['pid']; exact(prepared, saved); exact([], report['protocol_rejections'])
    return dict(task='C01.3.2', complete=True, cases=29, modes=2, repair_layers=3,
        durable_fits=29, projected_sources=11, saved_fits=230, inherited_fits=189,
        copy_checked=True, process_restart=True, protocol_rejections=len(REJECTIONS))
