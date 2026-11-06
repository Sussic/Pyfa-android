"""Offline first-stage C10 collection check; never grants native acceptance.

The caller supplies trusted source bindings, exact phase selections, and hashes
from its independently reviewed artifact manifest. The report cannot supply its
own expectations. The existing check-drones.passed parser validates raw logs.
Owner acceptance, offline/store/closure proof and final-report adoption are later
joins; a successful return here keeps all of them pending.
"""
import hashlib
import json


class CollectionError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise CollectionError(message)


def check_collection(report_bytes, instrumentation, required, passed):
    """Validate bound bytes and exact phases, returning only a pending result.

    No filesystem, runtime or mutable ownership operations. `passed` is the
    repository's existing instrumentation validator, not a new parser.
    """
    _require(__debug__, 'Existing parser requires assertion-enabled Python')
    _require(isinstance(report_bytes, bytes), 'Report must be original bytes')
    _require(hashlib.sha256(report_bytes).hexdigest() == required['report_sha256'], 'Report hash differs')
    try:
        report = json.loads(report_bytes)
    except (ValueError, UnicodeError) as error:
        raise CollectionError('Invalid report JSON') from error
    _require(type(report) is dict, 'Report must be an object')
    for key in ('source_commit', 'source_tree', 'policy_sha256'):
        _require(report.get(key) == required[key], f'{key} differs')
    _require(report.get('status') == 'COLLECTED_FIXED14_PENDING_OUTER_CLOSURE_REVIEW', 'Not a complete collection')
    _require('error' in report and report['error'] is None, 'Controller error or missing error field')
    _require(report.get('cleanup_errors') == [], 'Cleanup errors or missing cleanup result')
    for field in ('native_acceptance', 'full_C10_acceptance', 'writer_process_death_claim', 'default_adb_server_addressed'):
        _require(report.get(field) is False, f'Unexpected or missing {field}')
    _require(report.get('actual_outer_guard_zero_closure_required') is True, 'Outer review requirement missing')
    phases = required['phases']
    labels = [phase['label'] for phase in phases]
    _require(len(labels) == 5 and len(set(labels)) == 5, 'Trusted fixed phase selection invalid')
    _require(sum(len(phase['methods']) for phase in phases) == 14, 'Trusted fixed method selection invalid')
    _require(report.get('phases') == phases, 'Missing, reordered or altered phase selection')
    _require(set(instrumentation) == set(labels), 'Missing or unexpected instrumentation log')
    _require(set(required['instrumentation_sha256']) == set(labels), 'Incomplete trusted log binding')
    all_methods = set()
    for phase in phases:
        label = phase['label']
        raw = instrumentation[label]
        _require(type(raw) is bytes, 'Instrumentation must be original bytes')
        _require(hashlib.sha256(raw).hexdigest() == required['instrumentation_sha256'][label], f'{label} hash differs')
        expected = {phase['selector'].split('#', 1)[0] + '#' + name for name in phase['methods']}
        _require(len(expected) == len(phase['methods']), 'Duplicate trusted method')
        _require(not all_methods.intersection(expected), 'Repeated method across phases')
        all_methods.update(expected)
        try:
            passed(raw.decode('utf-8', errors='strict'), expected)
        except (AssertionError, ValueError, KeyError, UnicodeError) as error:
            raise CollectionError(f'{label} instrumentation is incomplete or failed') from error
    _require(len(all_methods) == 14, 'Fixed14 method coverage differs')
    return dict(status='COLLECTION_CHECKED_ACCEPTANCE_PENDING', native_accepted=False,
                checked_methods=len(all_methods),
                remaining=['offline', 'duration_store_and_fresh_process', 'outer_custody_and_closure',
                           'owner_acceptance', 'final_resulting_source_report'])
