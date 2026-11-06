"""Offline checks of existing V3 duration artifacts; no native acceptance.

Role-to-file projection and hashes must come from the independently reviewed
complete artifact manifest. This checks content joins, not trace completeness,
device provenance, no-reseed history, outer closure or owner acceptance.
"""
import hashlib
import json
import re
import xml.etree.ElementTree as ET

from c10_collection import CollectionError, _require

ROLES = {'edit_receipt', 'startup_edit', 'startup_reopen', 'graph_edit',
         'graph_stopped', 'graph_reopen', 'pid_absence'}


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'Duplicate JSON field')
            result[key] = value
        return result
    result = json.loads(raw, object_pairs_hook=unique)
    _require(type(result) is dict, 'Expected JSON object')
    return result


def check_duration(artifacts, required):
    """Check raw, hash-bound edit/startup/store/absence evidence as data only."""
    _require(set(artifacts) == ROLES == set(required['sha256']), 'Incomplete duration artifact roles')
    for role, raw in artifacts.items():
        _require(type(raw) is bytes, 'Duration evidence must be original bytes')
        _require(hashlib.sha256(raw).hexdigest() == required['sha256'][role], f'{role} hash differs')
    try:
        root = ET.fromstring(artifacts['edit_receipt'])
        entries = [node.text for node in root if node.tag == 'string' and node.attrib.get('name') == 'edit']
        _require(root.tag == 'map' and len(entries) == 1 and entries[0], 'Missing or duplicate edit receipt')
        edit = _json(entries[0])
        first, second = (_json(artifacts[role]) for role in ('startup_edit', 'startup_reopen'))
        absence = _json(artifacts['pid_absence'])
    except (ValueError, UnicodeError, ET.ParseError) as error:
        raise CollectionError('Invalid duration evidence: ' + str(error)) from error
    for key in ('case_id', 'oracle_sha256', 'seed_sha256', 'fit_id', 'object_key', 'position'):
        _require(type(edit.get(key)) is type(required[key]) and edit.get(key) == required[key], f'Duration {key} differs')
    for key in ('revision', 'generation'):
        _require(type(edit.get(key)) is int and edit[key] > 1, f'Invalid {key}')
    _require(type(edit.get('session')) is str and re.fullmatch('[0-9a-f]{32}', edit['session']), 'Invalid session')
    _require(edit.get('external_force_stop_required') is True, 'External stop requirement missing')
    _require(edit.get('writer_process_death_proved_by_this_test') is False, 'Unsupported writer-death claim')
    for startup in (first, second):
        for key in ('pid', 'process_start_elapsed_ms'):
            _require(type(startup.get(key)) is int and startup[key] > 0, f'Invalid startup {key}')
    for key in ('pid', 'process_start_elapsed_ms'):
        _require(type(edit.get(key)) is int and edit[key] == first[key], 'Edit/startup identity mismatch')
    _require(second['process_start_elapsed_ms'] > first['process_start_elapsed_ms'], 'Reopen process is not newer')
    graph_hash = hashlib.sha256(artifacts['graph_edit']).hexdigest()
    _require(bool(artifacts['graph_edit']), 'Empty duration store')
    _require(edit.get('graph_sha256') == graph_hash, 'Edit receipt/store mismatch')
    _require(artifacts['graph_edit'] == artifacts['graph_stopped'] == artifacts['graph_reopen'], 'Duration store changed')
    _require(type(absence.get('exit_code')) is int and absence['exit_code'] == 1, 'Process absence not confirmed')
    _require(type(absence.get('stdout')) is str and not absence['stdout'].strip(), 'Target process still present')
    _require(type(absence.get('stderr')) is str and not absence['stderr'].strip(), 'Process absence command reported an error')
    argv = absence.get('argv')
    _require(type(argv) is list and all(type(value) is str for value in argv), 'Invalid absence command')
    _require(argv == required['pid_absence_argv'], 'Absence command/device binding differs')
    _require(argv[-3:] == ['shell', 'pidof', required['package']], 'Absence check targets another app')
    return dict(status='DURATION_CONTENT_JOINS_CHECKED_ACCEPTANCE_PENDING', native_accepted=False,
                remaining=['trace_completeness_and_no_reseed', 'device_provenance', 'offline',
                           'outer_custody_and_closure', 'owner_acceptance', 'final_resulting_source_report'])
