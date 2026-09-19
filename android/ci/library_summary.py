"""Validate actual B03.1 native lifecycle receipts and restart boundaries."""
from pathlib import Path
import json
import math


def equal(expected, actual):
    if isinstance(expected, dict):
        assert expected.keys() == actual.keys()
        for key in expected: equal(expected[key], actual[key])
    elif isinstance(expected, list):
        assert len(expected) == len(actual)
        for left, right in zip(expected, actual): equal(left, right)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert type(actual) in (int, float)
        assert math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-9)
    else:
        assert type(expected) is type(actual) and expected == actual


def summarize(reports):
    assert len(reports) == 3
    sessions, pids = set(), set()
    previous = None
    fixtures = Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures'
    baseline = json.loads((fixtures / 'projection.json').read_text(encoding='utf-8'))['states']['initial']['target']
    for report, phase in zip(reports, ('prepare', 'reopen_delete', 'empty_reopen')):
        assert report['task'] == 'B03.1' and report['phase'] == phase
        start, end = report['runtime_start'], report['runtime_end']
        assert start['session_id'] == end['session_id'] and start['session_id'] not in sessions
        assert report['pid'] not in pids
        sessions.add(start['session_id']); pids.add(report['pid'])
        for runtime in (start, end):
            assert runtime['persistence']['enabled'] and runtime['persistence']['opened_existing']
            assert runtime['android_worker_thread'] == 'pyfa-engine' and not runtime['android_main_thread']
            assert not runtime['desktop_import_attempts']
        observations = report['observations']
        assert observations[0]['label'] == 'start' and observations[-1]['label'] == 'end'
        initial, final = observations[0]['fits'], observations[-1]['fits']
        if previous is not None: equal(previous, initial)
        previous = final
        assert start['retained_fit_count'] == len(initial)
        assert end['retained_fit_count'] == len(final)
        if phase == 'prepare':
            assert len(initial) == 9 and len(final) == 11
            initial_ids = {fit['id'] for fit in initial}
            assert initial_ids <= {fit['id'] for fit in final}
            assert [row['label'] for row in observations] == ['start', 'Celestis-linked', 'Celestis-deleted', 'Vulture-linked', 'Vulture-deleted', 'end']
            for row in observations[1:]:
                targets = [fit for fit in row['fits'] if fit['name'] in ('B03 independent copy', 'B03 second recipient')]
                assert len(targets) == 2
                kind = 'projection' if row['label'].startswith('Celestis') else 'command'
                expected = baseline
                if row['label'].endswith('-linked'):
                    stage = 'applied_zero' if kind == 'projection' else 'applied'
                    expected = json.loads((fixtures / (kind + '.json')).read_text(encoding='utf-8'))['states'][stage]['target']
                for fit in targets:
                    equal(expected, fit['stats'])
                    assert len(fit['stats']) == 39
                    scalar_names = {int: 'integer', float: 'decimal', bool: 'boolean', str: 'string'}
                    assert fit['scalar_types'] == {key: scalar_names[type(stat['value'])] for key, stat in expected.items()}
            assert not any(fit['name'].startswith('探索') for fit in final)
        else:
            assert not final and end['sample_id'] is None
            if phase == 'empty_reopen': assert not initial and start['sample_id'] is None
        assert end['persistence']['generation'] > start['persistence']['generation']
    return {'phases': 3, 'distinct_processes': 3, 'distinct_sessions': 3,
        'restart_graphs_matched': True, 'empty_store_reopened': True,
        'two_recipient_projection_and_command_deletion': True,
        'desktop_stat_comparisons': 10 * 39, 'native_ui_assertions_passed': True}
