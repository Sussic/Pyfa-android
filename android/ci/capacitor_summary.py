"""C01.2 exact packaged fixture identity and capacitor raw/presentation results."""
from math import isfinite
from pathlib import Path
from evidence_paths import evidence_dir
from resource_summary import fixture_bytes
from mutation_history_summary import settings

ROOT = Path(__file__).resolve().parents[2]
REJECTIONS = ['version','extra','missing','unit','boolean','kind','display','revision',
              'stability_unit','stability_kind','bounds','reversed_range','fractional_integer']


def scalar(expected, actual, kind):
    assert kind == ('unavailable' if expected is None else 'integer' if type(expected) is int else 'decimal')
    if expected is None:
        assert actual is None
    else:
        assert type(actual) in (int,float) and isfinite(actual) and isfinite(expected)
        if kind == 'integer': assert type(actual) is int and expected == actual
        else:
            if type(actual) is int: assert expected.is_integer() and expected == actual
            assert abs(expected-actual) <= max(1e-9,1e-10*max(abs(expected),abs(actual)))


def capacitor(expected, actual):
    assert set(actual) == {'fit_id','revision','capacitor','stability'}
    assert type(actual['fit_id']) is str and actual['fit_id']
    assert type(actual['revision']) is int and actual['revision'] >= 1
    left, right = expected['capacitor'], actual['capacitor']
    assert set(left) == set(right) and len(right) == 7
    for name, row in left.items():
        observed = right[name]
        assert set(observed) == {'value','value_type','unit','display','detail'}
        scalar(row['value'],observed['value'],observed['value_type'])
        for key in ('value_type','unit','display','detail'): assert row[key] == observed[key]
    left, right = expected['stability'], actual['stability']
    assert set(right) == {'kind','unit','values','value_types','display'}
    for key in ('kind','unit','value_types','display'): assert left[key] == right[key]
    assert len(left['values']) == len(right['values']) == len(right['value_types'])
    for value, observed, kind in zip(left['values'],right['values'],right['value_types']): scalar(value,observed,kind)


def summarize(reports, engine, prior_pids=()):
    apk = evidence_dir().parent/'apks/app-debug-androidTest.apk'
    assert apk.is_file(), 'Retained verified test APK required'
    reference = (ROOT/'tools/android_reference/fixtures/capacitor.json').read_bytes()
    assert len(reports) == 2
    pids = set(prior_pids); prepared = None
    for phase, report in zip(('prepare','restored'),reports):
        fixture = fixture_bytes(apk,reference,report['fixture_sha256'],'capacitor-expected.json')
        assert fixture['source_commit'] == engine['desktop_source_commit']
        settings(fixture['eos_settings'],engine['eos_settings'])
        assert report['task'] == 'C01.2' and report['phase'] == phase
        assert type(report['pid']) is int and report['pid'] > 0 and report['pid'] not in pids
        pids.add(report['pid'])
        start = report['runtime_start']; assert start['persistence']['enabled'] is True and start['persistence']['opened_existing'] is True
        for key in ('desktop_source_commit','database_logical_sha256','engine_source_sha256','source_data_sha256'):
            assert start['manifest'][key] == engine[key]
        settings(fixture['eos_settings'],start['eos_settings'])
        ids, rows, saved = report['ids'], report['observations'], report['saved']
        assert len(ids) == len(set(ids)) == len(rows) == len(fixture['cases']) == 12
        assert saved['ids'] == ids and len(saved['capacitors']) == 12
        assert len(saved['inherited']['data']) == 158 and len(saved['all_fits']['data']) == 174
        inherited_ids = {row['id'] for row in saved['inherited']['data']}
        all_ids = {row['id'] for row in saved['all_fits']['data']}
        assert len(inherited_ids) == 158 and len(all_ids) == 174 and inherited_ids <= all_ids
        assert set(ids) <= all_ids and not set(ids) & inherited_ids
        snapshots = {row['id']:row for row in saved['all_fits']['data']}
        for inherited in saved['inherited']['data']:
            assert snapshots[inherited['id']] == inherited, 'Inherited fit changed'
        def inputs(spec, snapshot):
            assert snapshot['name'] == 'C01.2 ' + spec['name'] and snapshot['ship'] == spec['ship']
            assert snapshot['skills'] == {} and snapshot['implants'] == [] and snapshot['commands'] == []
            assert snapshot['modules'] == [dict(index=index,**row) for index,row in enumerate(spec['modules'])]
        for case, identifier in zip(fixture['cases'],ids):
            target = snapshots[identifier]; inputs(case['spec'],target)
            if 'source' in case:
                source = [row for row in snapshots.values() if row['name'] == 'C01.2 ' + case['source']['name']]
                assert len(source) == 1; inputs(case['source'],source[0])
                assert source[0]['projections'] == []
                assert target['projections'] == [dict(source_id=source[0]['id'],**case['projection'])]
            else: assert target['projections'] == []
        copies = [row for row in snapshots.values() if row['name'] == 'C01.2 copy']
        assert len(copies) == 1 and copies[0]['id'] not in inherited_ids | set(ids)
        copy = copies[0]; original = snapshots[ids[5]]
        assert {k:v for k,v in copy.items() if k not in ('id','name','revision')} == {
            k:v for k,v in original.items() if k not in ('id','name','revision')}
        if phase == 'prepare':
            assert saved['pid'] == report['pid'] and report['protocol_rejections'] == REJECTIONS
            assert [row['case'] for row in rows] == list(range(12))
            prepared = saved
        else:
            assert saved == prepared and saved['pid'] != report['pid'] and report['protocol_rejections'] == []
        for case, row, identifier, retained in zip(fixture['cases'],rows,ids,saved['capacitors']):
            assert row['actual'] == retained and row['actual']['fit_id'] == identifier
            capacitor(case['expected'],row['actual'])
    return dict(task='C01.2',complete=True,cases=12,capacitor_values=7,durable_fits=12,
                copy_checked=True,process_restart=True,protocol_rejections=len(REJECTIONS))
