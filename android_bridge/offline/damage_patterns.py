"""Pure D05.4 damage and named-module authority, strict wire validation and bounded views.

Records retain original contribution kinds and signed zero. Bound fit values
are a checked compatibility projection, never a second editable authority.
"""
from copy import deepcopy
import json
import math
import re
import unicodedata
import uuid

from .profiles import ProfileError, require
from .damage_catalogue import BUILTINS

MAX_REQUEST_BYTES = 16384
MAX_STATE_BYTES = 524288
PAGE_SIZE = 50
MAX_INT = 2**63 - 1
DAMAGE_FIELDS = ('emAmount', 'thermalAmount', 'kineticAmount', 'explosiveAmount')
FIELDS = set(DAMAGE_FIELDS)
ITEM_ATTRIBUTES = ('emDamage', 'thermalDamage', 'kineticDamage', 'explosiveDamage')
SELECTED_AMMO = 'damage:selected_ammo'
SELECTED_AMMO_NAME = 'Selected Ammo'
READ_OPERATIONS = frozenset(('read', 'item_options', 'module_options'))
CUSTOM = re.compile(r'damage:[0-9a-f]{32}\Z')
FIT = re.compile(r'[0-9a-f]{32}\Z')
OPERATIONS = {
    'read': set(), 'item_options': {'item_id', 'fit_revision'},
    'module_options': {'fit_revision', 'object_key', 'position'},
    'set_module': {'fit_revision', 'object_key', 'position', 'selection'},
    'apply_item': {'item_id', 'fit_revision'}, 'create': {'name', 'values'},
    'update_values': {'pattern_id', 'revision', 'values'},
    'rename': {'pattern_id', 'revision', 'name'},
    'duplicate': {'pattern_id', 'revision', 'name'},
    'assign': {'pattern_id', 'revision', 'fit_revision'},
    'detach_to_anonymous': {'pattern_id', 'revision', 'binding_revision', 'fit_revision'},
    'reset_uniform': {'fit_revision'},
    'delete': {'pattern_id', 'revision', 'bound_fit_count', 'bound_module_count', 'affected_fit_count'},
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
    require(value < MAX_INT, 'revision', 'Damage revision limit reached')
    return value + 1


def text(value, maximum, *, empty=False, code='invalid_request'):
    require(type(value) is str and (empty or bool(value)) and len(value) <= maximum and
            all(unicodedata.category(c) != 'Cc' and not 0xD800 <= ord(c) <= 0xDFFF for c in value),
            code, 'Invalid text, Unicode controls or length')
    return value


def name(value):
    require(type(value) is str, 'invalid_name', 'Enter a damage pattern name')
    value = text(value.strip(), 200, code='invalid_name')
    require(value not in ('Uniform', 'Selected Ammo'), 'reserved_name', 'This name is reserved for an original damage pattern')
    return value


def values(value, *, editor=False):
    require(type(value) is dict and set(value) == FIELDS, 'invalid_values', 'Supply all four damage contributions')
    for key in DAMAGE_FIELDS:
        amount = value[key]
        require(type(amount) is float if editor else type(amount) in (int, float),
                'invalid_values', 'Editor values require floating-point numbers' if editor else 'Invalid damage number')
        require(type(amount) is not int or amount <= MAX_INT, 'invalid_values',
                'Named damage integer values must fit the signed 63-bit range')
        try:
            finite = math.isfinite(amount)
        except (OverflowError, TypeError):
            finite = False
        require(finite and amount >= 0, 'invalid_values', 'Damage contributions must be finite and nonnegative')
    require(math.isfinite(total(value)), 'invalid_values', 'Damage contribution total must be finite')
    return deepcopy(value)


def total(raw):
    return sum(raw[key] for key in DAMAGE_FIELDS)


def assignable(raw):
    return total(raw) > 0


def percentages(raw):
    amount = total(raw)
    return {key: raw[key] / amount * 100 if amount > 0 else 0.0 for key in DAMAGE_FIELDS}


def empty():
    return dict(version=2, patterns={}, bindings={})


def normalized(ledger):
    """Normalize an already-validated historical ledger without storing it."""
    result = deepcopy(ledger)
    result['version'] = 2
    return result


def builtin_id(number):
    return 'damage:builtin:' + str(number)


CATALOGUE = {}
for _number, _data in BUILTINS.items():
    _raw = dict(zip(DAMAGE_FIELDS, _data[1:]))
    CATALOGUE[builtin_id(_number)] = dict(name=_data[0], revision=0, values=_raw)


UNIFORM = builtin_id(-1)


def identity(value):
    require(type(value) is str and (value in CATALOGUE or value == SELECTED_AMMO or CUSTOM.fullmatch(value)),
            'invalid_request', 'Invalid damage identity')
    return value


def resolve(ledger, key, *, revision=None, editable=False):
    identity(key)
    row = CATALOGUE.get(key) if key in CATALOGUE else ledger['patterns'].get(key)
    require(row is not None, 'missing_pattern', 'Damage pattern no longer exists')
    if revision is not None:
        integer(revision)
        require(revision == row['revision'], 'stale_pattern', 'Damage pattern changed; reload before editing')
    require(not editable or key not in CATALOGUE and key != SELECTED_AMMO,
            'protected', 'Built-in and Selected Ammo damage patterns are read-only')
    return row


def validate(ledger, records, *, version=2):
    require(type(ledger) is dict and set(ledger) == {'version', 'patterns', 'bindings'} and
            type(ledger['version']) is int and ledger['version'] == version and version in (1, 2),
            'format', 'Invalid damage ledger')
    require(type(ledger['patterns']) is dict and type(ledger['bindings']) is dict,
            'format', 'Invalid damage records or bindings')
    names = set()
    for key, row in ledger['patterns'].items():
        special = version == 2 and key == SELECTED_AMMO
        require(type(key) is str and (special or CUSTOM.fullmatch(key)), 'protected', 'Invalid or stored built-in damage identity')
        require(type(row) is dict and set(row) == {'name', 'values', 'revision'}, 'format', 'Invalid damage record')
        if special:
            require(row['name'] == SELECTED_AMMO_NAME, 'protected', 'Invalid Selected Ammo name')
        else:
            require(name(row['name']) == row['name'], 'invalid_name', 'Saved damage names must be trimmed')
        require(row['name'] not in names, 'duplicate_name', 'Custom damage name already exists')
        names.add(row['name'])
        integer(row['revision'], 1, code='revision')
        values(row['values'])
        require(not special or assignable(row['values']), 'unassignable', 'Selected Ammo requires a positive total')
    for fit_id, binding in ledger['bindings'].items():
        require(type(fit_id) is str and FIT.fullmatch(fit_id) and fit_id in records, 'reference', 'Unknown damage-bound fit')
        require(type(binding) is dict and set(binding) == {'pattern_id', 'revision'}, 'format', 'Invalid damage binding')
        integer(binding['revision'], 1, code='revision')
        row = resolve(ledger, binding['pattern_id'])
        require(assignable(row['values']), 'unassignable', 'Bound damage patterns require a positive total')
        require(exact(records[fit_id]['spec']['damage_pattern'], row['values']),
                'damage_mismatch', 'Fit damage inputs disagree with the named damage')


def apply(state):
    ledger = state.get('damage_patterns', empty())
    for fit_id, binding in ledger['bindings'].items():
        state['fit_graph']['records'][fit_id]['spec']['damage_pattern'] = deepcopy(resolve(ledger, binding['pattern_id'])['values'])


def unique_name(ledger, value, excluding=None):
    value = name(value)
    require(all(key == excluding or row['name'] != value for key, row in ledger['patterns'].items()),
            'duplicate_name', 'A custom damage with this exact name already exists')
    return value


def item_options(engine, item_id):
    """Read bundled base attributes, never fitted overrides or recent-use resolution."""
    integer(item_id, 1, 2**31 - 1)
    from android_bridge.fitting import item
    try:
        source = item(engine, item_id)
    except ValueError as error:
        raise ProfileError('unknown_item', 'Unknown bundled item') from error
    raw = [source.getAttribute(key) for key in ITEM_ATTRIBUTES]
    eligible = any(value is not None for value in raw)
    contributions = None
    reason = 'no_damage_attributes'
    if eligible:
        try:
            contributions = values(dict(zip(DAMAGE_FIELDS, (value or 0 for value in raw))))
            reason = None if assignable(contributions) else 'zero_total'
        except (ProfileError, OverflowError, TypeError, ValueError):
            reason = 'invalid_values'
    return dict(item_id=item_id, name=text(source.name, 1024), eligible=eligible,
                available=reason is None, unavailable_reason=reason, values=contributions)


def mutate(state, operation, args, fit_id, *, pattern_floor=None, binding_floor=None, item=None):
    """Mutate a detached candidate only; the graph owner validates and commits."""
    state.setdefault('damage_patterns', empty())
    ledger = state['damage_patterns']
    pattern_floor = pattern_floor or {}
    binding_floor = binding_floor or {}
    records = state['fit_graph']['records']
    from .named_rah import inventory, holder_fits, module_rows
    selected = None
    affected = set()
    key = args.get('pattern_id')
    row = None
    if key is not None:
        row = resolve(ledger, key, revision=args['revision'], editable=operation in ('update_values', 'rename', 'delete') or operation == 'duplicate' and key == SELECTED_AMMO)
    if operation in ('assign', 'reset_uniform', 'detach_to_anonymous', 'apply_item'):
        require(fit_id in records, 'missing_fit', 'Select an existing saved fit')
        require(args['fit_revision'] == state['fit_graph']['revisions'][fit_id], 'stale_fit', 'Saved fit changed; reload')
    def next_binding(f, pattern_id):
        old = ledger['bindings'].get(f)
        return dict(pattern_id=pattern_id, revision=advance(max(old['revision'] if old else 0, binding_floor.get(f, 0))))
    if operation == 'apply_item':
        # This preview is resolved by the graph owner in this action, never wire input.
        require(item is not None and item['item_id'] == args['item_id'], 'invalid_request', 'Missing server item snapshot')
        require(item['available'], item['unavailable_reason'], 'This item cannot provide a supported positive damage pattern')
        raw = values(item['values'])
        require(assignable(raw), 'zero_total', 'Selected Ammo requires a positive total')
        selected = key = SELECTED_AMMO
        previous = ledger['patterns'].get(key)
        changed = previous is None or not exact(previous['values'], raw)
        old = ledger['bindings'].get(fit_id)
        incoming = {f for f, binding in ledger['bindings'].items() if binding['pattern_id'] == key}
        affected = holder_fits(records, ledger, key) if changed else set()
        rebound = set(incoming) if changed else set()
        if changed or old is None or old['pattern_id'] != key:
            affected.add(fit_id)
            rebound.add(fit_id)
        # Module-only holders recalculate without acquiring incoming bindings.
        bindings = {f: next_binding(f, key) for f in rebound}
        if changed:
            revision = advance(max(previous['revision'] if previous else 0, pattern_floor.get(key, 0)))
            ledger['patterns'][key] = dict(name=SELECTED_AMMO_NAME, values=raw, revision=revision)
        ledger['bindings'].update(bindings)
    elif operation in ('create', 'duplicate'):
        selected = 'damage:' + uuid.uuid4().hex
        ledger['patterns'][selected] = dict(name=unique_name(ledger, args['name']), revision=1,
            values=values(args['values'], editor=True) if operation == 'create' else deepcopy(row['values']))
    elif operation in ('update_values', 'rename'):
        changed = dict(row)
        if operation == 'rename':
            changed['name'] = unique_name(ledger, args['name'], key)
        else:
            changed['values'] = values(args['values'], editor=True)
        bound = {f for f, b in ledger['bindings'].items() if b['pattern_id'] == key}
        holders = holder_fits(records, ledger, key)
        require(not holders or assignable(changed['values']), 'unassignable', 'Assigned damage patterns require a positive total; no changes were saved')
        if not exact(changed, row):
            changed['revision'] = advance(max(row['revision'], pattern_floor.get(key, 0)))
            bindings = {f: next_binding(f, key) for f in bound}
            ledger['patterns'][key] = changed
            ledger['bindings'].update(bindings)
            affected = holders
    elif operation in ('assign', 'reset_uniform'):
        if operation == 'reset_uniform':
            key, row = UNIFORM, CATALOGUE[UNIFORM]
        require(assignable(row['values']), 'unassignable', 'Enter a positive contribution before assigning this pattern')
        old = ledger['bindings'].get(fit_id)
        if old is None or old['pattern_id'] != key:
            ledger['bindings'][fit_id] = next_binding(fit_id, key)
            affected.add(fit_id)
    elif operation == 'detach_to_anonymous':
        old = ledger['bindings'].get(fit_id)
        require(old is not None and old['pattern_id'] == key and old['revision'] == args['binding_revision'],
                'stale_binding', 'Damage assignment changed; reload before detaching')
        require(exact(records[fit_id]['spec']['damage_pattern'], row['values']),
                'damage_mismatch', 'Saved damage inputs disagree with the named pattern')
        records[fit_id]['spec']['damage_pattern'] = deepcopy(row['values'])
        del ledger['bindings'][fit_id]
        affected.add(fit_id)
    elif operation == 'delete':
        holders = inventory(records, ledger, key)
        affected = holder_fits(records, ledger, key)
        require(args['bound_fit_count'] == len(holders['incoming']) and
                args['bound_module_count'] == len(holders['modules']) and
                args['affected_fit_count'] == len(affected),
                'stale_bindings', 'Damage assignments changed; review deletion again')
        # Reserve the deleted identity too; later recreation cannot reuse a floor.
        advance(max(row['revision'], pattern_floor.get(key, 0)))
        bindings = {f: next_binding(f, UNIFORM) for f in holders['incoming']}
        for pid, _, _, _, module in list(module_rows(records)):
            if pid == key: module.pop('rah_pattern')
        ledger['bindings'].update(bindings)
        del ledger['patterns'][key]
    else:
        raise ProfileError('invalid_request', 'Unsupported damage mutation')
    apply(state)
    return selected, affected


def parse(text_value):
    require(type(text_value) is str, 'invalid_request', 'Expected a damage JSON request')
    try:
        require(len(text_value) <= MAX_REQUEST_BYTES and len(text_value.encode('utf-8')) <= MAX_REQUEST_BYTES,
                'invalid_request', 'Damage request exceeds 16384 UTF-8 bytes')
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
        raise ProfileError('invalid_request', 'Invalid damage JSON request') from error
    return request


def request(request, context, records, ledger):
    require(type(request) is dict and set(request) == {'version', 'request_id', 'context', 'fit_id', 'view', 'operation', 'arguments'},
            'invalid_request', 'Invalid damage request fields')
    require(type(request['version']) is int and request['version'] == 3, 'invalid_request', 'Unsupported damage version')
    rid = request['request_id']
    require(type(rid) is str and 0 < len(rid) <= 128 and all(32 <= ord(c) < 127 for c in rid), 'invalid_request', 'Invalid request identity')
    ctx = request['context']
    require(type(ctx) is dict and set(ctx) == {'session_id', 'dataset_sha256', 'generation'} and
            type(ctx['session_id']) is str and FIT.fullmatch(ctx['session_id']) and
            type(ctx['dataset_sha256']) is str and re.fullmatch('[0-9a-f]{64}', ctx['dataset_sha256']),
            'invalid_request', 'Invalid damage context')
    integer(ctx['generation'], 1)
    require(exact(ctx, context), 'stale_context', 'The graph changed; reload before editing')
    fit_id = request['fit_id']
    require(fit_id is None or type(fit_id) is str and FIT.fullmatch(fit_id) and fit_id in records,
            'missing_fit', 'Selected fit no longer exists')
    view = request['view']
    require(type(view) is dict and set(view) == {'query', 'offset', 'limit', 'selected_pattern_id', 'bound_offset', 'module_offset'},
            'invalid_request', 'Invalid damage view')
    text(view['query'], 200, empty=True)
    integer(view['offset']); integer(view['bound_offset']); integer(view['module_offset']); integer(view['limit'], 1, PAGE_SIZE)
    if view['selected_pattern_id'] is not None:
        resolve(ledger, view['selected_pattern_id'])
    op, args = request['operation'], request['arguments']
    require(type(op) is str and op in OPERATIONS and type(args) is dict and set(args) == OPERATIONS[op],
            'invalid_request', 'Invalid damage operation or arguments')
    if 'pattern_id' in args:
        identity(args['pattern_id']); integer(args['revision'])
    if 'fit_revision' in args:
        integer(args['fit_revision'], 1)
        require(fit_id is not None, 'missing_fit', 'Select a saved fit')
    if 'item_id' in args:
        integer(args['item_id'], 1, 2**31 - 1)
    if 'binding_revision' in args:
        integer(args['binding_revision'], 1)
    for field in ('bound_fit_count', 'bound_module_count', 'affected_fit_count', 'position'):
        if field in args: integer(args[field])
    if 'object_key' in args:
        require(type(args['object_key']) is str and FIT.fullmatch(args['object_key']),
                'invalid_request', 'Invalid logical module identity')
    if 'selection' in args:
        from .named_rah import selection as validate_selection
        validate_selection(args['selection'])
    if 'name' in args:
        name(args['name'])
    if 'values' in args:
        values(args['values'], editor=True)
    return request


def state_view(state, context, fit_id, view, history, *, item=None, module=None, engine=None):
    """Read a detached state or proposed next state; never mutates authority."""
    ledger = state.get('damage_patterns', empty())
    graph = state['fit_graph']
    records = graph['records']
    if fit_id not in records:
        fit_id = None
    binding = ledger['bindings'].get(fit_id)
    selection = dict(kind='no_fit' if fit_id is None else 'named' if binding else 'anonymous',
        pattern_id=binding['pattern_id'] if binding else None,
        pattern_revision=resolve(ledger, binding['pattern_id'])['revision'] if binding else None,
        binding_revision=binding['revision'] if binding else None)
    from .named_rah import module_rows
    module_holders = {}
    holder_fits = {}
    ordered = {key: records[key] for key in graph['fit_order']}
    for pid, holder_fit, key, position, source in module_rows(ordered):
        module_holders.setdefault(pid, []).append((holder_fit, key, position, source))
        holder_fits.setdefault(pid, set()).add(holder_fit)
    counts = {}
    for holder_fit, value in ledger['bindings'].items():
        holder_fits.setdefault(value['pattern_id'], set()).add(holder_fit)
        counts[value['pattern_id']] = counts.get(value['pattern_id'], 0) + 1
    def metadata(key, row):
        return dict(pattern_id=key, kind='builtin' if key in CATALOGUE else 'selected_ammo' if key == SELECTED_AMMO else 'custom',
                    name=row['name'], revision=row['revision'], bound_fit_count=counts.get(key, 0),
                    bound_module_count=len(module_holders.get(key, ())),
                    affected_fit_count=len(holder_fits.get(key, ())),
                    assignable=assignable(row['values']), unassignable_reason=None if assignable(row['values']) else 'zero_total')
    all_rows = {**CATALOGUE, **ledger['patterns']}
    query = view['query'].casefold()
    keys = [key for key, row in CATALOGUE.items() if query in row['name'].casefold()]
    if SELECTED_AMMO in ledger['patterns'] and query in SELECTED_AMMO_NAME.casefold():
        keys.append(SELECTED_AMMO)
    custom = [key for key, row in ledger['patterns'].items() if key != SELECTED_AMMO and query in row['name'].casefold()]
    keys.extend(sorted(custom, key=lambda key: (all_rows[key]['name'].casefold(), all_rows[key]['name'], key)))
    offset, limit = view['offset'], view['limit']
    page = dict(query=view['query'], offset=offset, limit=limit, total=len(keys),
                entries=[metadata(key, all_rows[key]) for key in keys[offset:offset + limit]])
    selected = view['selected_pattern_id']
    detail = None
    if selected in all_rows:
        row = all_rows[selected]
        bound = [key for key in graph['fit_order'] if ledger['bindings'].get(key, {}).get('pattern_id') == selected]
        start = view['bound_offset']
        detail = dict(**metadata(selected, row), values=deepcopy(row['values']), percentages=percentages(row['values']),
            bound_fits=dict(offset=start, limit=PAGE_SIZE, total=len(bound), entries=[
                dict(fit_id=key, name=records[key]['spec']['name'], revision=graph['revisions'][key])
                for key in bound[start:start + PAGE_SIZE]]))
        module_start = view['module_offset']
        holders = module_holders.get(selected, ())
        entries = []
        for holder_fit, key, position, source in holders[module_start:module_start + PAGE_SIZE]:
            require(engine is not None, 'engine', 'Module holder metadata requires the bundled catalogue')
            source_item = engine._item(source['name'])
            entries.append(dict(fit_id=holder_fit, fit_name=records[holder_fit]['spec']['name'],
                fit_revision=graph['revisions'][holder_fit], object_key=key, position=position,
                item_id=source_item.ID, name=source_item.name))
        detail['bound_modules'] = dict(offset=module_start, limit=PAGE_SIZE, total=len(holders), entries=entries)
    return dict(version=3, context=context, fit_id=fit_id,
                fit_revision=graph['revisions'][fit_id] if fit_id else None,
                selection=selection, page=page, detail=detail, history=history.details(fit_id or 'library'), item=deepcopy(item), module=deepcopy(module))
