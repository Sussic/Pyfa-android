"""Check complete B04.1 observations against the independently exported Market."""
import json
from pathlib import Path


def exact(expected, actual):
    # Catalogue IDs/types/memberships have no floating-point tolerance.
    assert type(expected) is type(actual)
    if isinstance(expected, dict):
        assert expected.keys() == actual.keys()
        for key in expected:
            exact(expected[key], actual[key])
    elif isinstance(expected, list):
        assert len(expected) == len(actual)
        for left, right in zip(expected, actual):
            exact(left, right)
    else:
        assert expected == actual


def summarize(report, engine):
    expected = json.loads((Path(__file__).resolve().parents[2] / 'tools/android_reference/fixtures/equipment.json').read_text(encoding='utf-8'))
    assert report['task'] == 'B04.1'
    exact(expected['catalog'], report['catalog'])
    exact(expected['searches'], report['searches'])
    runtime = report['runtime']
    assert runtime['persistence']['enabled'] and runtime['persistence']['opened_existing']
    assert runtime['android_worker_thread'] == 'pyfa-engine' and not runtime['android_main_thread']
    assert not runtime['desktop_import_attempts']
    for key in ('database_sha256', 'database_logical_sha256', 'engine_source_sha256', 'desktop_source_commit'):
        assert runtime['manifest'][key] == engine[key]
    exact(engine['eos_settings'], runtime['eos_settings'])
    assert set(report['checks']) == {'complete_desktop_catalogue', 'all_desktop_searches', 'tree_and_item_jump',
        'meta_filters_and_empty', 'pagination', 'activity_recreation', 'saved_fits_unchanged'}
    items = {row['id']: row for row in expected['catalog']['items']}
    pages = sorted(expected['searches']['Standup'], key=lambda id: (items[id]['name'].lower(), id))
    exact(pages[:20], report['first_page'])
    exact(pages[20:40], report['second_page'])
    return {'groups': len(expected['catalog']['groups']), 'items': len(items),
            'searches': len(expected['searches']), 'checks': report['checks']}
