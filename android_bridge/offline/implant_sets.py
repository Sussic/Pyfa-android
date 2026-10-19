"""Detached C07.3 implant recipes, not live fit or character bindings.

Only ordered type IDs are saved. Item names and genuine slots always come from
the pinned character-implant catalogue; no EOS fit is created for a recipe.
"""
from copy import deepcopy
import re
import uuid

from android_bridge import character_implants
from .profiles import ProfileError, require
from .damage_patterns import integer, text, exact, parse, MAX_INT, MAX_REQUEST_BYTES, MAX_STATE_BYTES, PAGE_SIZE

CUSTOM = re.compile(r'implant-set:[0-9a-f]{32}\Z')
PREDEFINED = re.compile(r'builtin:implant-set:[1-9][0-9]*\Z')
HEX = re.compile(r'[0-9a-f]{32}\Z')
PROFILE = re.compile(r'profile:[0-9a-f]{32}\Z')
OPERATIONS = {
    'read': set(), 'create': {'name'},
    'rename': {'set_id', 'revision', 'name'}, 'duplicate': {'set_id', 'revision', 'name'},
    'delete': {'set_id', 'revision'}, 'add_item': {'set_id', 'revision', 'item_id', 'replace_item_id'},
    'remove_item': {'set_id', 'revision', 'item_id'}, 'save_current': {'name', 'fit_revision'},
    'apply_fit': {'set_id', 'revision', 'fit_revision'},
    'apply_profile': {'set_id', 'revision', 'profile_id', 'profile_revision'},
    'undo': set(), 'redo': set(),
}
LABELS = {
    'create': 'Create implant set', 'rename': 'Rename implant set', 'duplicate': 'Duplicate implant set',
    'delete': 'Delete implant set', 'add_item': 'Add implant to set', 'remove_item': 'Remove implant from set',
    'save_current': 'Save current implants as set', 'apply_fit': 'Apply implant set to fit',
    'apply_profile': 'Apply implant set to character',
}


def empty():
    return dict(version=1, sets={})


def advance(value):
    integer(value, code='revision')
    require(value < MAX_INT, 'revision', 'Implant set revision limit reached')
    return value + 1


def advance_floor(revision, floor):
    integer(revision, code='revision'); integer(floor, code='revision')
    return advance(max(revision, floor))


def name(value):
    require(type(value) is str, 'invalid_name', 'Enter an implant set name')
    return text(value.strip(), 200, code='invalid_name')


def legacy_label(value):
    """Read-only historic labels allow controls, but never lone surrogates."""
    require(type(value) is str and bool(value) and
            all(not 0xD800 <= ord(character) <= 0xDFFF for character in value),
            'invalid_label', 'Saved label is not valid Unicode text')
    return value


def metadata(item_id):
    integer(item_id, 1, 2**31 - 1)
    try:
        item, slot = character_implants.catalogue(item_id)
    except ValueError as error:
        raise ProfileError('invalid_item', 'Choose a genuine implant from the pinned catalogue') from error
    return dict(item_id=item.ID, name=item.name, slot=slot)


def item_id_for_name(value):
    """Use EOS's canonical name lookup without changing live provenance."""
    import eos.db
    item = eos.db.getItem(value)
    require(item is not None and item.name == value, 'invalid_item', 'Saved implant name is unavailable')
    return metadata(item.ID)['item_id']


def items(item_ids):
    require(type(item_ids) is list, 'format', 'Invalid ordered implant recipe')
    rows = [metadata(value) for value in item_ids]
    require(len({row['slot'] for row in rows}) == len(rows), 'slot_conflict', 'An implant set cannot repeat a slot')
    return rows


def validate(ledger):
    require(type(ledger) is dict and set(ledger) == {'version', 'sets'} and
            type(ledger['version']) is int and ledger['version'] == 1 and type(ledger['sets']) is dict,
            'format', 'Invalid implant set ledger')
    names = set()
    for key, row in ledger['sets'].items():
        require(type(key) is str and CUSTOM.fullmatch(key), 'identity', 'Invalid stored implant set identity')
        require(type(row) is dict and set(row) == {'name', 'revision', 'item_ids'}, 'format', 'Invalid implant set fields')
        require(name(row['name']) == row['name'], 'invalid_name', 'Saved implant set names must be trimmed')
        require(row['name'] not in names, 'duplicate_name', 'An implant set with this exact name already exists')
        names.add(row['name'])
        integer(row['revision'], 1, code='revision')
        items(row['item_ids'])


def unique_name(ledger, value, excluding=None):
    value = name(value)
    require(all(key == excluding or row['name'] != value for key, row in ledger['sets'].items()),
            'duplicate_name', 'An implant set with this exact name already exists')
    return value


def predefined():
    """Resolve every pinned row, in its stored member order, without GUI startup.

    Missing/ineligible items are the original reader's expected filtering. Other
    parse/metadata errors fail the entire read. The pinned C07.3 catalogue has
    56 rows, no filtered entries and no repeated slots; do not sort by slot.
    """
    import eos.db
    catalogue = {}
    for source in eos.db.getAllImplantSets():
        integer(source.ID, 1, 2**31 - 1)
        family = text(source.setName, 200)
        grade = None if source.gradeName is None else text(source.gradeName, 200)
        require(type(source.implants) is str and bool(source.implants), 'catalogue', 'Invalid predefined implant recipe')
        recipe = []
        for token in source.implants.split(','):
            require(re.fullmatch('[1-9][0-9]*', token), 'catalogue', 'Invalid predefined implant identity')
            item_id = integer(int(token), 1, 2**31 - 1)
            try:
                item, slot = character_implants.catalogue(item_id)
            except character_implants.IneligibleImplant:
                continue
            recipe.append(item.ID)
        items(recipe)
        identity = 'builtin:implant-set:' + str(source.ID)
        require(identity not in catalogue, 'catalogue', 'Duplicate predefined implant identity')
        catalogue[identity] = dict(name=text(family if grade is None else grade + ' ' + family, 200),
                                   family=family, grade=grade, revision=0, item_ids=recipe)
    grades = {'low-grade': 0, 'mid-grade': 1, 'high-grade': 2}
    return dict(sorted(catalogue.items(), key=lambda pair: (pair[1]['family'],
        grades.get((pair[1]['grade'] or '').lower(), 3), pair[1]['grade'] or '', pair[0])))


def resolve(ledger, key, catalogue, *, revision=None, editable=False):
    identity(key)
    row = catalogue.get(key) if key in catalogue else ledger['sets'].get(key)
    require(row is not None, 'missing_set', 'Implant set no longer exists')
    if revision is not None:
        integer(revision)
        require(row['revision'] == revision, 'stale_set', 'Implant set changed; reload before editing')
    require(not editable or key not in catalogue, 'protected', 'Predefined implant sets are read-only')
    return row


def mutate(ledger, operation, args, catalogue, *, revision_floor=None, current_ids=None):
    """Edit a detached ledger; all validation/reservation precedes assignment."""
    revision_floor = revision_floor or {}
    key = args.get('set_id')
    row = None if key is None else resolve(ledger, key, catalogue, revision=args['revision'],
        editable=operation in ('duplicate', 'rename', 'delete', 'add_item', 'remove_item'))
    if operation in ('create', 'duplicate', 'save_current'):
        value = unique_name(ledger, args['name'])
        recipe = [] if operation == 'create' else list(row['item_ids']) if operation == 'duplicate' else current_ids
        require(operation != 'save_current' or bool(recipe), 'empty_source', 'There are no currently applied implants to save')
        items(recipe)
        selected = 'implant-set:' + uuid.uuid4().hex
        require(selected not in ledger['sets'] and selected not in revision_floor,
                'identity', 'Implant set identity was already used')
        ledger['sets'][selected] = dict(name=value, revision=1, item_ids=list(recipe))
        return selected
    if operation == 'delete':
        advance_floor(row['revision'], revision_floor.get(key, 0))
        del ledger['sets'][key]
        return None
    changed = deepcopy(row)
    if operation == 'rename':
        changed['name'] = unique_name(ledger, args['name'], key)
    elif operation == 'add_item':
        incoming = metadata(args['item_id'])
        rows = items(row['item_ids'])
        occupant = next((value['item_id'] for value in rows if value['slot'] == incoming['slot']), None)
        expected = args['replace_item_id']
        if expected is not None: integer(expected, 1, 2**31 - 1)
        require(occupant == expected, 'conflict', 'Implant set slot occupant changed; reload before replacing')
        changed['item_ids'] = [value for value in row['item_ids'] if value != occupant] + [incoming['item_id']]
    elif operation == 'remove_item':
        integer(args['item_id'], 1, 2**31 - 1)
        require(args['item_id'] in row['item_ids'], 'conflict', 'Implant is no longer in this set')
        changed['item_ids'].remove(args['item_id'])
    else:
        raise ProfileError('invalid_request', 'Unsupported implant set mutation')
    if not exact(changed, row):
        changed['revision'] = advance_floor(row['revision'], revision_floor.get(key, 0))
        ledger['sets'][key] = changed
    return key


def merge_fit(record, item_ids, resolve_name):
    """One detached ordered merge, preserving exact duplicate rows and IDs."""
    incoming = items(item_ids)
    rows = deepcopy(record['implants'])
    identities = list(record['inspection_ids']['implants'])
    require(len(rows) == len(identities), 'identity', 'Implant inspection identities differ')
    existing = []
    for row in rows:
        item_id = resolve_name(row['name'])
        info = metadata(item_id)
        require(info['name'] == row['name'] and info['slot'] == row['slot'], 'invalid_item', 'Saved implant metadata differs')
        existing.append(item_id)
    for info in incoming:
        # Desktop duplicate check precedes makeRoom. An inactive duplicate is
        # untouched and does not move, even when another recipe row is added.
        if info['item_id'] in existing:
            continue
        occupant = next((index for index, row in enumerate(rows) if row['slot'] == info['slot']), None)
        if occupant is not None:
            del rows[occupant]; del identities[occupant]; del existing[occupant]
        rows.append(dict(name=info['name'], slot=info['slot'], active=True))
        identities.append(uuid.uuid4().hex)
        existing.append(info['item_id'])
    record['implants'] = rows
    record['inspection_ids']['implants'] = identities


def applied_ids(state, fit_id, resolve_name):
    record = state['fit_graph']['records'][fit_id]
    if record['implant_source'] == 'CHARACTER':
        profile_id = state['profiles']['bindings'][fit_id]['profile_id']
        return [row['item_id'] for row in state['profiles']['profiles'][profile_id]['implants']]
    return [resolve_name(row['name']) for row in record['implants']]


def identity(value):
    require(type(value) is str and (CUSTOM.fullmatch(value) or PREDEFINED.fullmatch(value)),
            'identity', 'Invalid implant set identity')
    if PREDEFINED.fullmatch(value):
        number = value.rsplit(':', 1)[1]
        require(len(number) <= 10 and int(number) <= 2**31 - 1, 'identity', 'Invalid predefined set identity')
    return value


def profile_identity(value):
    require(type(value) is str and (value in ('builtin:all0', 'builtin:all5') or PROFILE.fullmatch(value)),
            'identity', 'Invalid character identity')
    return value


def request(value, context, state):
    require(type(value) is dict and set(value) == {'version', 'request_id', 'context', 'anchor_fit_id', 'view', 'operation', 'arguments'},
            'invalid_request', 'Invalid implant set request fields')
    require(type(value['version']) is int and value['version'] == 1, 'invalid_request', 'Unsupported implant set version')
    rid = value['request_id']
    require(type(rid) is str and 0 < len(rid) <= 128 and all(32 <= ord(c) < 127 for c in rid),
            'invalid_request', 'Invalid request identity')
    ctx = value['context']
    require(type(ctx) is dict and set(ctx) == {'session_id', 'dataset_sha256', 'generation'} and
            type(ctx['session_id']) is str and HEX.fullmatch(ctx['session_id']) and
            type(ctx['dataset_sha256']) is str and re.fullmatch('[0-9a-f]{64}', ctx['dataset_sha256']),
            'invalid_request', 'Invalid implant set context')
    integer(ctx['generation'], 1)
    require(exact(ctx, context), 'stale_context', 'The graph changed; reload before editing')
    anchor = value['anchor_fit_id']
    require(anchor is None or type(anchor) is str and HEX.fullmatch(anchor) and anchor in state['fit_graph']['records'],
            'missing_fit', 'Selected fit no longer exists')
    view = value['view']
    require(type(view) is dict and set(view) == {'query', 'offset', 'limit', 'selected_set_id', 'target_profile_id', 'history_target'},
            'invalid_request', 'Invalid implant set view')
    text(view['query'], 200, empty=True)
    integer(view['offset']); integer(view['limit'], 1, PAGE_SIZE)
    if view['selected_set_id'] is not None: identity(view['selected_set_id'])
    if view['target_profile_id'] is not None: profile_identity(view['target_profile_id'])
    require(view['history_target'] == 'library' or anchor is not None and view['history_target'] == anchor,
            'invalid_request', 'History must target the displayed library or anchored fit')
    operation, args = value['operation'], value['arguments']
    require(type(operation) is str and operation in OPERATIONS and type(args) is dict and set(args) == OPERATIONS[operation],
            'invalid_request', 'Invalid implant set operation or arguments')
    if 'set_id' in args:
        identity(args['set_id']); integer(args['revision'])
        require(view['selected_set_id'] == args['set_id'], 'invalid_request', 'Selected set does not match the operation')
    if 'name' in args:
        require(name(args['name']) == args['name'], 'invalid_name', 'Implant set name must be trimmed')
    if 'item_id' in args: integer(args['item_id'], 1, 2**31 - 1)
    if args.get('replace_item_id') is not None: integer(args['replace_item_id'], 1, 2**31 - 1)
    if 'fit_revision' in args:
        integer(args['fit_revision'], 1)
        require(anchor is not None, 'missing_fit', 'Select a saved fit')
    if operation == 'apply_fit':
        require(view['target_profile_id'] is None and view['history_target'] == anchor,
                'invalid_request', 'Fit application requires the displayed fit destination and history')
    elif operation == 'apply_profile':
        profile_identity(args['profile_id']); integer(args['profile_revision'], 1)
        require(view['target_profile_id'] == args['profile_id'] and view['history_target'] == 'library',
                'invalid_request', 'Character application requires the displayed character and library history')
    elif operation not in ('read', 'undo', 'redo'):
        require(view['history_target'] == 'library', 'invalid_request', 'Template changes require library history')
    return value


def collection(rows, *, local_ids=None):
    if local_ids is not None:
        require(len(rows) == len(local_ids), 'identity', 'Implant inspection identities differ')
    result = []
    for index, row in enumerate(rows):
        info = metadata(item_id_for_name(row['name']) if local_ids is not None else row['item_id'])
        require(info['slot'] == row['slot'], 'invalid_item', 'Saved implant slot differs')
        result.append(dict(info, row_id=local_ids[index] if local_ids is not None else row['implant_id'], active=row['active']))
    return result


def state_view(state, context, anchor, view, history, catalogue, is_structure):
    ledger = state.get('implant_sets', empty())
    graph = state['fit_graph']
    profiles = state['profiles']
    all_rows = {**catalogue, **ledger['sets']}
    def summary(key, row):
        builtin = key in catalogue
        return dict(set_id=key, kind='builtin' if builtin else 'custom', name=row['name'],
                    family=row['family'] if builtin else None, grade=row['grade'] if builtin else None,
                    revision=row['revision'], item_count=len(row['item_ids']))
    keys = list(catalogue) + sorted(ledger['sets'], key=lambda key: (ledger['sets'][key]['name'], key))
    query = view['query'].casefold()
    keys = [key for key in keys if query in all_rows[key]['name'].casefold()]
    offset, limit = view['offset'], view['limit']
    page = dict(query=view['query'], offset=offset, limit=limit, total=len(keys),
                entries=[summary(key, all_rows[key]) for key in keys[offset:offset + limit]])
    selected = view['selected_set_id']
    detail = None if selected not in all_rows else dict(summary(selected, all_rows[selected]), items=items(all_rows[selected]['item_ids']))
    if anchor not in graph['records']: anchor = None
    target = view['target_profile_id']
    destination = None
    if target is not None:
        if target in profiles['profiles']:
            row = profiles['profiles'][target]
            destination = dict(kind='profile', profile_id=target, profile_revision=row['revision'], name=legacy_label(row['name']),
                readonly=target.startswith('builtin:'), assigned_fit_count=sum(binding['profile_id'] == target for binding in profiles['bindings'].values()),
                implants=collection(row['implants']))
    elif anchor is not None:
        record = graph['records'][anchor]
        destination = dict(kind='fit', fit_id=anchor, fit_revision=graph['revisions'][anchor], name=legacy_label(record['spec']['name']),
                           is_structure=is_structure(anchor), implants=collection(record['implants'], local_ids=record['inspection_ids']['implants']))
    source = None
    if anchor is not None:
        record = graph['records'][anchor]
        character = record['implant_source'] == 'CHARACTER'
        profile_id = profiles['bindings'][anchor]['profile_id'] if character else None
        profile = profiles['profiles'][profile_id] if character else None
        source = dict(fit_id=anchor, fit_revision=graph['revisions'][anchor], source=record['implant_source'],
                      profile_id=profile_id, profile_revision=profile['revision'] if character else None,
                      profile_name=legacy_label(profile['name']) if character else None,
                      implant_count=len(profile['implants'] if character else record['implants']))
    history_target = view['history_target'] if view['history_target'] == 'library' or anchor is not None else 'library'
    return dict(version=1, context=context, anchor_fit_id=anchor, page=page, detail=detail, destination=destination,
                save_source=source, history=dict(target=history_target, **history.details(history_target)))
