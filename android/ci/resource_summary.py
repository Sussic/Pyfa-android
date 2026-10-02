"""C01.1 retained APK fixtures, exact scalar kinds and independent values."""
import hashlib
import json
from math import isfinite
from pathlib import Path
from zipfile import ZipFile
from evidence_paths import evidence_dir

ROOT = Path(__file__).resolve().parents[2]


def fixture_bytes(apk, reference, reported, asset="resources-expected.json"):
    with ZipFile(apk) as archive:
        packaged = archive.read('assets/'+asset)
    assert hashlib.sha256(packaged).hexdigest() == reported, 'Reported fixture hash differs from retained APK bytes'
    assert packaged.replace(b'\r\n', b'\n') == reference.replace(b'\r\n', b'\n'), 'Packaged fixture content changed'
    return json.loads(packaged)


def resources(expected, actual):
    assert set(expected) == set(actual) and len(actual) == 11
    for name, left in expected.items():
        right = actual[name]
        assert set(right) == {'used','total','used_type','total_type','unit','overloaded',
                              'used_display','total_display','used_detail','total_detail'}
        for key in ('used','total'):
            value, observed = left[key], right[key]
            kind = 'integer' if type(value) is int else 'decimal'
            assert right[key+'_type'] == kind
            assert type(observed) in (int,float) and isfinite(observed)
            if kind == 'integer': assert type(observed) is int and observed == value
            else:
                assert type(value) is float and isfinite(value)
                # JSONObject canonicalizes whole doubles only. Preserve their
                # original kind explicitly; fractional integers never qualify.
                if type(observed) is int: assert value.is_integer() and observed == value
                assert abs(value-observed) <= max(1e-9,1e-10*max(abs(value),abs(observed)))
        assert type(right['overloaded']) is bool and right['overloaded'] == left['overloaded']
        assert right['unit'] == left['unit']
        for original, reported in [('desktop_used','used_display'),('desktop_total','total_display'),
                                   ('desktop_used_detail','used_detail'),('desktop_total_detail','total_detail')]:
            assert type(right[reported]) is str and right[reported] == left[original]


def summarize(probe, reports, engine, prior_pids=()):
    evidence = evidence_dir()
    apk = evidence.parent/'apks/app-debug-androidTest.apk'
    assert apk.is_file(), 'Retained verified test APK is required'
    reference = (ROOT/'tools/android_reference/fixtures/resources.json').read_bytes()
    fixture = fixture_bytes(apk,reference,probe['fixture_sha256'])
    assert probe['task'] == 'C01.1' and probe['phase'] == 'probe'
    assert probe['desktop_source_commit'] == fixture['source_commit'] == engine['desktop_source_commit']
    assert probe['database_logical_sha256'] == engine['database_logical_sha256']
    assert probe['desktop_import_attempts'] == []
    from mutation_history_summary import settings
    settings(fixture['eos_settings'],probe['eos_settings'])
    settings(fixture['eos_settings'],engine['eos_settings'])
    cases = fixture['cases']; assert len(cases) == len(probe['resources']) == len(probe['inputs']) == 14
    for case, inputs, actual in zip(cases,probe['inputs'],probe['resources']):
        assert inputs == {'spec':case['spec'],'fighters':case['fighters']}
        resources(case['resources'],actual)
    assert len(reports) == 2
    pids = set(prior_pids)
    assert type(probe['pid']) is int and probe['pid'] > 0 and probe['pid'] not in pids
    pids.add(probe['pid'])
    prepared = None
    for phase, report in zip(('prepare','restored'),reports):
        assert report['task'] == 'C01.1' and report['phase'] == phase
        fixture_bytes(apk,reference,report['fixture_sha256'])
        edited = fixture_bytes(apk,(ROOT/'tools/android_reference/fixtures/resources-edited.json').read_bytes(),
            report['edited_fixture_sha256'],'resources-edited-expected.json')
        assert edited['task'] == 'C01.1' and edited['source_commit'] == fixture['source_commit']
        assert edited['case'] == 2 and edited['input'] == cases[2]['spec']
        settings(fixture['eos_settings'],edited['eos_settings'])
        assert type(report['pid']) is int and report['pid'] > 0 and report['pid'] not in pids
        pids.add(report['pid'])
        start = report['runtime_start']['persistence']
        assert start['enabled'] is True and start['opened_existing'] is True
        manifest = report['runtime_start']['manifest']
        for key in ('desktop_source_commit','database_logical_sha256','engine_source_sha256','source_data_sha256'):
            assert manifest[key] == engine[key]
        settings(fixture['eos_settings'],report['runtime_start']['eos_settings'])
        assert len(report['ids']) == len(set(report['ids'])) == len(report['observations']) == 10
        saved = report['saved']; assert saved['ids'] == report['ids'] and len(saved['resources']) == 10
        if phase == 'prepare':
            assert saved['pid'] == report['pid']
            durable = [i for i,case in enumerate(cases) if case['execution']=='durable']
            assert [row['case'] for row in report['observations']] == durable
            for index, row, identifier, retained in zip(durable,report['observations'],report['ids'],saved['resources']):
                assert row['actual']['fit_id'] == identifier == retained['fit_id']
                assert row['actual'] == retained
                assert type(retained['revision']) is int and retained['revision'] >= 1
                resources(edited['resources'] if index == edited['case'] else cases[index]['resources'],row['actual']['resources'])
            assert report['protocol_rejections'] == ['version','extra','missing_pair','unit','scalar_kind','boolean_value','overload','missing_display','revision']
            prepared = saved
        else:
            assert saved == prepared and saved['pid'] != report['pid']
            assert report['protocol_rejections'] == []
            durable = [index for index,case in enumerate(cases) if case['execution']=='durable']
            for index, row, retained in zip(durable,report['observations'],saved['resources']):
                actual = row['actual']
                assert actual['fit_id'] == retained['fit_id'] and actual['resources'] == retained['resources']
                assert type(actual['revision']) is int and actual['revision'] >= 1
                resources(edited['resources'] if index == edited['case'] else cases[index]['resources'],actual['resources'])
    return {'task':'C01.1','complete':True,'cases':14,'resource_pairs':11,
            'durable_fits':10,'copy_checked':True,'process_restart':True,'protocol_rejections':9}
