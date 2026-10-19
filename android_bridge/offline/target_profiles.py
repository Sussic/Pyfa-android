"""Pure D05.1 target-only authority, strict wire validation and bounded views.

Records retain original numeric kinds and nullable raw inputs. Effective values
are a checked compatibility projection, never a second editable authority.
"""
from copy import deepcopy
import json
import math
import re
import unicodedata
import uuid

from android_bridge.output_inputs import PROFILE_FIELDS
from .profiles import ProfileError, require
from .target_catalogue import BUILTINS

MAX_REQUEST_BYTES = 16384
MAX_STATE_BYTES = 524288
PAGE_SIZE = 50
MAX_INT = 2**63 - 1
FIELDS = set(PROFILE_FIELDS)
CUSTOM = re.compile(r'target:[0-9a-f]{32}\Z')
FIT = re.compile(r'[0-9a-f]{32}\Z')
OPERATIONS = {
    'read': set(), 'create': {'name', 'values'},
    'update_values': {'target_id', 'revision', 'values'},
    'rename': {'target_id', 'revision', 'name'},
    'duplicate': {'target_id', 'revision', 'name'},
    'assign': {'target_id', 'revision', 'fit_revision'},
    'clear': {'fit_revision'},
    'delete': {'target_id', 'revision', 'bound_fit_count'},
    'undo': set(), 'redo': set(),
}


def exact(left, right):
    """Representation equality, including raw signed zero and int/float kinds."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(exact(left[k], right[k]) for k in left)
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(exact(a, b) for a, b in zip(left, right))
    if type(left) is float and left == 0 and right == 0:
        return math.copysign(1, left) == math.copysign(1, right)
    return left == right


def integer(value, minimum=0, maximum=MAX_INT, code='invalid_request'):
    require(type(value) is int and minimum <= value <= maximum, code, 'Invalid integer or revision')
    return value


def advance(value):
    integer(value, code='revision')
    require(value < MAX_INT, 'revision', 'Target revision limit reached')
    return value + 1


def text(value, maximum, *, empty=False, code='invalid_request'):
    require(type(value) is str and (empty or bool(value)) and len(value) <= maximum and
            all(unicodedata.category(c) != 'Cc' and not 0xD800 <= ord(c) <= 0xDFFF for c in value),
            code, 'Invalid text, Unicode controls or length')
    return value


def name(value):
    require(type(value) is str, 'invalid_name', 'Enter a target profile name')
    return text(value.strip(), 200, code='invalid_name')


def values(value, *, editor=False):
    require(type(value) is dict and set(value) == FIELDS, 'invalid_values', 'Supply all eight target values')
    for key, amount in value.items():
        if amount is None and not key.endswith('Amount'):
            continue
        require(type(amount) is float if editor else type(amount) in (int, float),
                'invalid_values', 'Editor values require floating-point numbers' if editor else 'Invalid target number')
        require(type(amount) is not int or amount <= MAX_INT, 'invalid_values',
                'Named target integer values must fit the signed 63-bit range')
        try:
            finite = math.isfinite(amount)
        except (OverflowError, TypeError):
            finite = False
        require(finite and amount >= 0 and (not key.endswith('Amount') or amount <= 1),
                'invalid_values', 'Target values must be finite and nonnegative; resistances must be 0–100%')
    return deepcopy(value)


def effective(raw):
    result = values(raw)
    for key in ('maxVelocity', 'radius'):
        result[key] = result[key] or 0  # Original getter returns literal int zero.
    return result


def empty():
    return dict(version=1, profiles={}, bindings={})


def builtin_id(number):
    return 'target:builtin:' + str(number)


CATALOGUE = {}
for _number, _data in BUILTINS.items():
    _raw = dict(zip(PROFILE_FIELDS, (*_data[1:], *([None] * (9 - len(_data))))))
    CATALOGUE[builtin_id(_number)] = dict(name=_data[0], revision=0, values=_raw)


def identity(value):
    require(type(value) is str and (value in CATALOGUE or CUSTOM.fullmatch(value)),
            'invalid_request', 'Invalid target identity')
    return value


def resolve(ledger, key, *, revision=None, editable=False):
    identity(key)
    row = CATALOGUE.get(key) if key in CATALOGUE else ledger['profiles'].get(key)
    require(row is not None, 'missing_target', 'Target profile no longer exists')
    if revision is not None:
        integer(revision)
        require(revision == row['revision'], 'stale_target', 'Target profile changed; reload before editing')
    require(not editable or key not in CATALOGUE, 'protected', 'Built-in target profiles are read-only')
    return row


def validate(ledger, records):
    require(type(ledger) is dict and set(ledger) == {'version', 'profiles', 'bindings'} and
            type(ledger['version']) is int and ledger['version'] == 1,
            'format', 'Invalid target ledger')
    require(type(ledger['profiles']) is dict and type(ledger['bindings']) is dict,
            'format', 'Invalid target records or bindings')
    names = set()
    for key, row in ledger['profiles'].items():
        require(type(key) is str and CUSTOM.fullmatch(key), 'protected', 'Invalid or stored built-in target identity')
        require(type(row) is dict and set(row) == {'name', 'values', 'revision'}, 'format', 'Invalid target record')
        require(name(row['name']) == row['name'], 'invalid_name', 'Saved target names must be trimmed')
        require(row['name'] not in names, 'duplicate_name', 'Custom target name already exists')
        names.add(row['name'])
        integer(row['revision'], 1, code='revision')
        values(row['values'])
    for fit_id, binding in ledger['bindings'].items():
        require(type(fit_id) is str and FIT.fullmatch(fit_id) and fit_id in records, 'reference', 'Unknown target-bound fit')
        require(type(binding) is dict and set(binding) == {'target_id', 'revision'}, 'format', 'Invalid target binding')
        integer(binding['revision'], 1, code='revision')
        row = resolve(ledger, binding['target_id'])
        require(exact(records[fit_id]['spec']['target_profile'], effective(row['values'])),
                'target_mismatch', 'Fit target inputs disagree with the named target')


def apply(state):
    ledger = state.get('targets', empty())
    for fit_id, binding in ledger['bindings'].items():
        state['fit_graph']['records'][fit_id]['spec']['target_profile'] = effective(resolve(ledger, binding['target_id'])['values'])


def unique_name(ledger, value, excluding=None):
    value = name(value)
    require(all(key == excluding or row['name'] != value for key, row in ledger['profiles'].items()),
            'duplicate_name', 'A custom target with this exact name already exists')
    return value


def mutate(state, operation, args, fit_id, *, profile_floor=None, binding_floor=None):
    """Mutate a detached candidate only; the graph owner validates and commits."""
    state.setdefault('targets', empty())
    ledger = state['targets']
    profile_floor = profile_floor or {}
    binding_floor = binding_floor or {}
    records = state['fit_graph']['records']
    selected = None
    affected = set()
    key = args.get('target_id')
    row = None
    if key is not None:
        row = resolve(ledger, key, revision=args['revision'], editable=operation in ('update_values', 'rename', 'delete'))
    if operation in ('assign', 'clear'):
        require(fit_id in records, 'missing_fit', 'Select an existing saved fit')
        require(args['fit_revision'] == state['fit_graph']['revisions'][fit_id], 'stale_fit', 'Saved fit changed; reload')
    if operation in ('create', 'duplicate'):
        selected = 'target:' + uuid.uuid4().hex
        ledger['profiles'][selected] = dict(name=unique_name(ledger, args['name']), revision=1,
            values=values(args['values'], editor=True) if operation == 'create' else deepcopy(row['values']))
    elif operation in ('update_values', 'rename'):
        changed = dict(row)
        if operation == 'rename':
            changed['name'] = unique_name(ledger, args['name'], key)
        else:
            changed['values'] = values(args['values'], editor=True)
        if not exact(changed, row):
            changed['revision'] = advance(max(row['revision'], profile_floor.get(key, 0)))
            ledger['profiles'][key] = changed
            affected = {f for f, b in ledger['bindings'].items() if b['target_id'] == key}
            for f in affected:
                ledger['bindings'][f]['revision'] = advance(max(ledger['bindings'][f]['revision'], binding_floor.get(f, 0)))
    elif operation == 'assign':
        old = ledger['bindings'].get(fit_id)
        if old is None or old['target_id'] != key:
            ledger['bindings'][fit_id] = dict(target_id=key, revision=advance(max(old['revision'] if old else 0, binding_floor.get(fit_id, 0))))
            affected.add(fit_id)
    elif operation == 'clear':
        if fit_id in ledger['bindings'] or records[fit_id]['spec']['target_profile'] is not None:
            ledger['bindings'].pop(fit_id, None)
            records[fit_id]['spec']['target_profile'] = None
            affected.add(fit_id)
    elif operation == 'delete':
        affected = {f for f, b in ledger['bindings'].items() if b['target_id'] == key}
        require(args['bound_fit_count'] == len(affected), 'stale_bindings', 'Target assignments changed; review deletion again')
        for f in affected:
            del ledger['bindings'][f]
            records[f]['spec']['target_profile'] = None
        del ledger['profiles'][key]
    else:
        raise ProfileError('invalid_request', 'Unsupported target mutation')
    apply(state)
    return selected, affected


def parse(text_value):
    require(type(text_value) is str, 'invalid_request', 'Expected a target JSON request')
    try:
        require(len(text_value) <= MAX_REQUEST_BYTES and len(text_value.encode('utf-8')) <= MAX_REQUEST_BYTES,
                'invalid_request', 'Target request exceeds 16384 UTF-8 bytes')
    except UnicodeError as error:
        raise ProfileError('invalid_request', 'Invalid request Unicode') from error
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'invalid_request', 'Duplicate JSON keys are not allowed')
            result[key] = value
        return result
    def nonfinite(_):
        raise ProfileError('invalid_request', 'Nonfinite JSON numbers are not allowed')
    try:
        request = json.loads(text_value, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, TypeError, RecursionError) as error:
        raise ProfileError('invalid_request', 'Invalid target JSON request') from error
    return request


def request(request, context, records, ledger):
    require(type(request) is dict and set(request) == {'version', 'request_id', 'context', 'fit_id', 'view', 'operation', 'arguments'},
            'invalid_request', 'Invalid target request fields')
    require(type(request['version']) is int and request['version'] == 1, 'invalid_request', 'Unsupported target version')
    rid = request['request_id']
    require(type(rid) is str and 0 < len(rid) <= 128 and all(32 <= ord(c) < 127 for c in rid), 'invalid_request', 'Invalid request identity')
    ctx = request['context']
    require(type(ctx) is dict and set(ctx) == {'session_id', 'dataset_sha256', 'generation'} and
            type(ctx['session_id']) is str and FIT.fullmatch(ctx['session_id']) and
            type(ctx['dataset_sha256']) is str and re.fullmatch('[0-9a-f]{64}', ctx['dataset_sha256']),
            'invalid_request', 'Invalid target context')
    integer(ctx['generation'], 1)
    require(exact(ctx, context), 'stale_context', 'The graph changed; reload before editing')
    fit_id = request['fit_id']
    require(fit_id is None or type(fit_id) is str and FIT.fullmatch(fit_id) and fit_id in records,
            'missing_fit', 'Selected fit no longer exists')
    view = request['view']
    require(type(view) is dict and set(view) == {'query', 'offset', 'limit', 'selected_target_id', 'bound_offset'},
            'invalid_request', 'Invalid target view')
    text(view['query'], 200, empty=True)
    integer(view['offset']); integer(view['bound_offset']); integer(view['limit'], 1, PAGE_SIZE)
    if view['selected_target_id'] is not None:
        resolve(ledger, view['selected_target_id'])
    op, args = request['operation'], request['arguments']
    require(type(op) is str and op in OPERATIONS and type(args) is dict and set(args) == OPERATIONS[op],
            'invalid_request', 'Invalid target operation or arguments')
    if 'target_id' in args:
        identity(args['target_id']); integer(args['revision'])
    if 'fit_revision' in args:
        integer(args['fit_revision'], 1)
        require(fit_id is not None, 'missing_fit', 'Select a saved fit')
    if 'bound_fit_count' in args:
        integer(args['bound_fit_count'])
    if 'name' in args:
        name(args['name'])
    if 'values' in args:
        values(args['values'], editor=True)
    return request


def state_view(state, context, fit_id, view, history):
    """Read a detached state or proposed next state; never mutates authority."""
    ledger = state.get('targets', empty())
    graph = state['fit_graph']
    records = graph['records']
    if fit_id not in records:
        fit_id = None
    binding = ledger['bindings'].get(fit_id)
    selection = dict(kind='no_fit' if fit_id is None else 'named' if binding else
        'none' if records[fit_id]['spec']['target_profile'] is None else 'anonymous',
        target_id=binding['target_id'] if binding else None,
        binding_revision=binding['revision'] if binding else None)
    counts = {}
    for value in ledger['bindings'].values():
        counts[value['target_id']] = counts.get(value['target_id'], 0) + 1
    def metadata(key, row):
        return dict(target_id=key, kind='builtin' if key in CATALOGUE else 'custom',
                    name=row['name'], revision=row['revision'], bound_fit_count=counts.get(key, 0))
    all_rows = {**CATALOGUE, **ledger['profiles']}
    query = view['query'].casefold()
    keys = [key for key, row in all_rows.items() if query in row['name'].casefold()]
    keys.sort(key=lambda key: (all_rows[key]['name'].casefold(), all_rows[key]['name'], key))
    offset, limit = view['offset'], view['limit']
    page = dict(query=view['query'], offset=offset, limit=limit, total=len(keys),
                entries=[metadata(key, all_rows[key]) for key in keys[offset:offset + limit]])
    selected = view['selected_target_id']
    detail = None
    if selected in all_rows:
        row = all_rows[selected]
        bound = [key for key in graph['fit_order'] if ledger['bindings'].get(key, {}).get('target_id') == selected]
        start = view['bound_offset']
        detail = dict(**metadata(selected, row), values=deepcopy(row['values']), effective=effective(row['values']),
            bound_fits=dict(offset=start, limit=PAGE_SIZE, total=len(bound), entries=[
                dict(fit_id=key, name=records[key]['spec']['name'], revision=graph['revisions'][key])
                for key in bound[start:start + PAGE_SIZE]]))
    return dict(version=1, context=context, fit_id=fit_id,
                fit_revision=graph['revisions'][fit_id] if fit_id else None,
                selection=selection, page=page, detail=detail, history=history.details(fit_id or 'library'))
