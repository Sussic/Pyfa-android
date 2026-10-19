"""Corrupt actual retained inspector payloads; never generates native observations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from inspection_canonical_summary import validate as canonical_validate, decode
from inspection_identity_summary import validate as identity_validate
from inspection_links_summary import validate as links_validate
from inspection_context_summary import validate as context_validate


def ship(row): return row['targets'][0]['data']
def module(row): return next(target['data'] for target in row['targets'] if target['data']['selection']['context'] == 'module')
def unit(row): return next(value['unit'] for value in ship(row)['attributes']['rows'] if value['unit'] is not None)
def navigation(row): return next(value['source_target'] for value in ship(row)['affectors'] if value['source_target'] is not None)
def affector(row): return ship(row)['affectors'][0]


CANONICAL_ROWS = (
    ('wrong-raw-before', lambda row: affector(row).update(before=123456789.0)),
    ('wrong-raw-after', lambda row: affector(row).update(after=123456789.0)),
    ('wrong-raw-used', lambda row: affector(row).update(used=not affector(row)['used'])),
    ('wrong-raw-changed', lambda row: affector(row).update(changed=not affector(row)['changed'])),
    ('wrong-raw-operator', lambda row: affector(row).update(operator='FORCE')),
    ('wrong-raw-stacking', lambda row: affector(row).update(stacking={'fabricated': True})),
    ('wrong-raw-source-id', lambda row: affector(row).update(source_id=123456789)),
    ('missing-raw-row', lambda row: ship(row)['affectors'].pop()),
    ('wrong-case-index', lambda row: row.update(case_index=1)),
    ('unknown-fit', lambda row: row.update(fit_id='removed-fit')),
    ('wrong-selection-item', lambda row: module(row)['selection'].update(item_id=1)),
    ('wrong-durable-key', lambda row: module(row)['selection'].update(object_key='0' * 32)),
    ('wrong-current', lambda row: ship(row)['attributes']['rows'][0].update(current=123456789.0)),
    ('wrong-unit', lambda row: unit(row).update(name='fabricated unit')),
    ('missing-attribute', lambda row: ship(row)['attributes']['rows'].pop()),
    ('extra-attribute-field', lambda row: ship(row)['attributes']['rows'][0].update(extra=False)),
    ('wrong-published', lambda row: ship(row)['attributes']['rows'][0].update(published=not ship(row)['attributes']['rows'][0]['published'])),
    ('wrong-normal-flag', lambda row: ship(row)['attributes']['rows'][0].update(normal=not ship(row)['attributes']['rows'][0]['normal'])),
    ('wrong-group', lambda row: ship(row)['attributes']['normal'][0]['groups'].append('fabricated group')),
    ('altered-property', lambda row: ship(row)['properties'][0].update(reason='fabricated diagnostic')),
    ('missing-properties', lambda row: ship(row)['properties'].pop()),
    ('altered-effect', lambda row: ship(row)['effects'][0].update(name='fabricated effect')),
    ('altered-tree', lambda row: ship(row)['affector_views']['source'][0].update(label='fabricated source')),
    ('wrong-source-fit', lambda row: affector(row).update(source_fit_key='other-fit')),
    ('wrong-source-name', lambda row: affector(row).update(source_fit_name='wrong owner')),
    ('wrong-source-key', lambda row: navigation(row).update(object_key='0' * 32)),
    ('extra-protocol-field', lambda row: ship(row).update(extra=False)),
    ('wrong-sql-membership', lambda row: row['sql_roles']['modules'][0].update(position=999)),
    ('wrong-sql-row-type', lambda row: row['sql_roles']['modules'][0].update(ID=True)),
    ('false-variation-highlight', lambda row: ship(row)['variations']['rows'][0].update(selected=not ship(row)['variations']['rows'][0]['selected'])),
    ('fabricated-zero-price', lambda row: ship(row)['variations']['rows'][0]['price'].update(value=0)),
)
FRESH_ROWS = (
    ('wrong-phase', lambda row: row.update(phase='unknown-phase')),
    ('wrong-worker', lambda row: row.update(pid=row['pid'] + 1)),
    ('noninteger-worker', lambda row: row.update(pid=float(row['pid']))),
    ('missing-worker', lambda row: row.pop('pid')),
    ('missing-phase', lambda row: row.pop('phase')),
)


def rejected(name, check, digest):
    try: check()
    except (AssertionError, KeyError, IndexError):
        return dict(name=name, mutated_sha256=digest)
    raise AssertionError('Actual inspector corruption accepted: ' + name)


def canonical(state, raw, fixture, fresh=True):
    """Preserve all37 original actual-report mutations, plus fresh-worker cases."""
    canonical_validate(state, raw, fixture, fresh=fresh)
    lines = raw.splitlines(keepends=True); first = decode(lines[0]); results = []
    for name, mutate in (*CANONICAL_ROWS, *(FRESH_ROWS if fresh else ())):
        row = deepcopy(first); mutate(row)
        changed = json.dumps(row, separators=(',', ':'), allow_nan=False).encode() + b'\n' + b''.join(lines[1:])
        report = deepcopy(state); report['payload_sha256'] = hashlib.sha256(changed).hexdigest()
        results.append(rejected(name, lambda: canonical_validate(report, changed, fixture, fresh=fresh), report['payload_sha256']))
    states = (
        ('wrong-case-count', lambda report: report.update(cases=151)),
        ('wrong-target-count', lambda report: report.update(targets=725)),
        ('duplicate-process', lambda report: report.update(pids=[report['pids'][0], report['pids'][0]])),
        ('altered-input-name', lambda report: report['graph']['data']['records'][first['fit_id']]['spec'].update(name='altered input')),
        ('unexpected-skill-input', lambda report: report['graph']['data']['records'][first['fit_id']]['skills'].update(Synthetic=0)),
        ('extra-record-field', lambda report: report['graph']['data']['records'][first['fit_id']].update(extra=False)),
    )
    for name, mutate in states:
        report = deepcopy(state); mutate(report)
        digest = hashlib.sha256(json.dumps(report, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        results.append(rejected(name, lambda: canonical_validate(report, raw, fixture, fresh=fresh), digest))
    assert len(results) == (42 if fresh else 37)
    return dict(group='canonical', phase=state['last_phase'], fresh_worker_payload=fresh,
                payload_sha256=hashlib.sha256(raw).hexdigest(), count=len(results), rejected=results)


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def settings_type(runtime): runtime['eos_settings']['globalDefaultSpoolupPercentage'] = True
def settings_witness(runtime): runtime['eos_settings_numeric_types']['root.globalDefaultSpoolupPercentage'] = 'boolean'


def protocols(reports, mutate):
    for report in reports:
        for target in report['saved']['targets']: mutate(target['protocol'])
        for actual in report['observations']: mutate(actual)


def protocol_unit(protocol):
    return next(row['unit'] for row in protocol['attributes']['rows'] if row['unit'] is not None)


IDENTITY = (
    ('missing_phase', lambda reports: reports.pop()),
    ('extra_field', lambda reports: reports[0].update(extra=False)),
    ('duplicate_pid', lambda reports: reports[1].update(pid=reports[0]['pid'])),
    ('wrong_fixture_hash', lambda reports: reports[0].update(fixture_sha256='0' * 64)),
    ('wrong_source', lambda reports: reports[0]['runtime_start']['manifest'].update(desktop_source_commit='0' * 40)),
    ('wrong_dataset', lambda reports: reports[0]['runtime_start']['manifest'].update(database_logical_sha256='0' * 64)),
    ('wrong_worker', lambda reports: reports[0]['runtime_start'].update(android_worker_thread='main')),
    ('disabled_persistence', lambda reports: reports[0]['runtime_start']['persistence'].update(enabled=False)),
    ('not_reopened', lambda reports: reports[1]['runtime_start']['persistence'].update(opened_existing=False)),
    ('desktop_import', lambda reports: reports[0]['runtime_start'].update(desktop_import_attempts=['wx'])),
    ('wrong_settings_type', lambda reports: settings_type(reports[0]['runtime_start'])),
    ('wrong_settings_witness', lambda reports: settings_witness(reports[0]['runtime_start'])),
    ('nonempty_reopened_history', lambda reports: next(iter(reports[1]['history'].values())).update(undo_count=1)),
    ('missing_history', lambda reports: reports[1]['history'].pop(reports[1]['saved']['id'])),
    ('stale_revision_all_protocols', lambda reports: protocols(reports, lambda actual: actual.update(revision=0))),
    ('wrong_original_value_all_protocols', lambda reports: protocols(reports, lambda actual: actual['attributes']['rows'][0].update(current=123456789.0))),
    ('wrong_original_unit_all_protocols', lambda reports: protocols(reports, lambda actual: protocol_unit(actual).update(name='fabricated unit'))),
    ('wrong_equipment_all_protocols', lambda reports: protocols(reports, lambda actual: actual.update(equipment={}))),
    ('wrong_key', lambda reports: reports[0]['saved']['targets'][0].update(object_key='0' * 32)),
    ('wrong_graph_numeric_type', lambda reports: reports[0]['saved']['graph']['numeric_types'].update({'root.format': 'decimal'})),
)


def identity(reports, fixture, fixture_bytes):
    identity_validate(reports, fixture, fixture_bytes)
    results = []
    for name, mutate in IDENTITY:
        changed = deepcopy(reports); mutate(changed)
        results.append(rejected(name, lambda: identity_validate(changed, fixture, fixture_bytes), digest(changed)))
    assert len(results) == 20
    return dict(group='identity', input_sha256=digest(reports), count=len(results), rejected=results)


def linked_source(report):
    return next(affector for observed in report['observations'] for role in observed['roles'].values()
                for detail in role['inspection'] for affector in detail['affectors'] if affector['source_target'] is not None)


def linked_target(report):
    return next(detail for role in report['observations'][0]['roles'].values() for detail in role['inspection']
                if detail['selection']['context'] != 'base')


LINKED = (
    ('wrong_count', lambda report: report.update(followed_sources=report['followed_sources'] + 1)),
    ('wrong_cross_count', lambda report: report.update(followed_projected_sources=report['followed_projected_sources'] + 1)),
    ('missing_owner', lambda report: linked_source(report).pop('source_fit_key')),
    ('foreign_owner', lambda report: linked_source(report).update(source_fit_key='foreign-fit')),
    ('wrong_source_item', lambda report: linked_source(report)['source_target'].update(item_id=0)),
    ('malformed_source_key', lambda report: linked_source(report)['source_target'].update(object_key='not-a-key')),
    ('bool_source_index', lambda report: linked_source(report)['source_target'].update(index=True)),
    ('wrong_original_value', lambda report: linked_target(report)['attributes']['rows'][0].update(current=123456789.0)),
    ('wrong_state', lambda report: report['observations'][0].update(state='unknown-state')),
    ('stale_revision', lambda report: linked_target(report).update(revision=0)),
    ('wrong_fixture_hash', lambda report: report.update(fixture_sha256='0' * 64)),
    ('wrong_worker', lambda report: report['runtime_start'].update(android_worker_thread='main')),
    ('wrong_settings_type', lambda report: settings_type(report['runtime_start'])),
    ('extra_field', lambda report: report.update(extra=False)),
)


def linked(report, fixture, fixture_bytes, kind):
    links_validate(report, fixture, fixture_bytes, kind)
    results = []
    for name, mutate in LINKED:
        changed = deepcopy(report); mutate(changed)
        results.append(rejected(name, lambda: links_validate(changed, fixture, fixture_bytes, kind), digest(changed)))
    assert len(results) == 14
    return dict(group='linked', kind=kind, input_sha256=digest(report), count=len(results), rejected=results)


def context_target(row): return row['targets'][0]['data']
def context_record(row): return row['graph']['data']['records'][row['fit_id']]


CONTEXT_ROWS = (
    ('wrong-case', lambda row: row.update(case_index=-1)),
    ('wrong-observation', lambda row: row.update(observation='unknown-observation')),
    ('wrong-worker', lambda row: row.update(pid=row['pid'] + 1)),
    ('missing-target', lambda row: row['targets'].pop()),
    ('reordered-targets', lambda row: row['targets'].reverse()),
    ('unknown-fit', lambda row: row.update(fit_id='removed-fit')),
    ('wrong-current', lambda row: context_target(row)['attributes']['rows'][0].update(current=123456789.0)),
    ('wrong-unit', lambda row: protocol_unit(context_target(row)).update(name='fabricated unit')),
    ('missing-properties', lambda row: context_target(row)['properties'].pop()),
    ('extra-protocol-field', lambda row: context_target(row).update(extra=False)),
    ('stale-revision', lambda row: context_target(row).update(revision=0)),
    ('wrong-durable-key', lambda row: context_target(row)['selection'].update(object_key='0' * 32)),
    ('wrong-selection-item', lambda row: context_target(row)['selection'].update(item_id=0)),
    ('wrong-sql-hull', lambda row: row['sql_roles']['fit'][0].update(shipID=0)),
    ('wrong-sql-id-type', lambda row: row['sql_roles']['fit'][0].update(ID=True)),
    ('wrong-saved-name', lambda row: context_record(row)['spec'].update(name='altered input')),
    ('unexpected-skills', lambda row: context_record(row)['skills'].update(Synthetic=0)),
    ('extra-saved-field', lambda row: context_record(row).update(extra=False)),
)


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''): result.update(chunk)
    return result.hexdigest()


def context(state, payload_path, fixture):
    """Mutate actual streamed observations without retaining altered native files."""
    payload_path = Path(payload_path).resolve()
    context_validate(state, payload_path, fixture)
    with payload_path.open('rb') as source: first = decode(source.readline())
    results = []
    for name, mutate in CONTEXT_ROWS:
        row = deepcopy(first); mutate(row)
        with tempfile.NamedTemporaryFile(prefix='c032-corruption-', suffix='.jsonl', dir=payload_path.parent, delete=False) as output:
            temporary = Path(output.name).resolve()
            assert temporary.parent == payload_path.parent
            try:
                output.write(json.dumps(row, separators=(',', ':'), allow_nan=False).encode() + b'\n')
                with payload_path.open('rb') as source:
                    source.readline(); shutil.copyfileobj(source, output)
            except BaseException:
                output.close(); temporary.unlink(); raise
        try:
            report = deepcopy(state); report['payload_sha256'] = file_sha(temporary)
            results.append(rejected(name, lambda: context_validate(report, temporary, fixture), report['payload_sha256']))
        finally: temporary.unlink()
    states = (
        ('wrong-case-count', lambda report: report.update(cases=report['cases'] - 1)),
        ('wrong-observation-count', lambda report: report.update(observations=report['observations'] + 1)),
        ('wrong-original-target-count', lambda report: report.update(original_targets=report['original_targets'] + 1)),
        ('duplicate-worker', lambda report: report['pids'].append(report['pids'][0])),
        ('wrong-settings', lambda report: settings_type(report['runtime_start']['data'])),
        ('wrong-worker-thread', lambda report: report['runtime_start']['data'].update(android_worker_thread='main')),
        ('disabled-persistence', lambda report: report['runtime_start']['data']['persistence'].update(enabled=False)),
    )
    for name, mutate in states:
        report = deepcopy(state); mutate(report)
        results.append(rejected(name, lambda: context_validate(report, payload_path, fixture), digest(report)))
    assert len(results) == 25
    return dict(group='contexts', phase=state['phase'], payload_sha256=file_sha(payload_path),
                count=len(results), rejected=results)
