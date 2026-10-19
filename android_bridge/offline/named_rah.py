"""Local named RAH references, owned by one candidate graph and its ledger.

No process-global registry and no second stored module-binding authority. The
resolver retains exact EOS objects only for the lifetime of its reconstruction.
"""
from copy import deepcopy

from . import damage_patterns as damage
from .profiles import require


def named_id(value):
    require(type(value) is str and (value == damage.SELECTED_AMMO or damage.CUSTOM.fullmatch(value)),
            'invalid_request', 'Invalid named reactive armor identity')
    return value


def module_rows(records):
    """Yield canonical holders, including inactive local modules, in fit order."""
    for fit_id, record in records.items():
        modules = record['spec']['modules']
        keys = record.get('inspection_ids', {}).get('modules')
        for position, module in enumerate(modules):
            tag = module.get('rah_pattern')
            if type(tag) is dict and tag.get('mode') == 'named':
                require(set(tag) == {'mode', 'pattern_id'}, 'format', 'Invalid named reactive armor tag')
                named_id(tag['pattern_id'])
                require(type(fit_id) is str and damage.FIT.fullmatch(fit_id) and
                        type(keys) is list and len(keys) == len(modules) and
                        all(type(key) is str and damage.FIT.fullmatch(key) for key in keys) and
                        len(keys) == len(set(keys)) and 'empty_slot' not in module,
                        'reference', 'Named reactive armor requires aligned logical module identities')
                yield tag['pattern_id'], fit_id, keys[position], position, module


def inventory(records, ledger, pattern_id):
    return dict(incoming=tuple(sorted(fit_id for fit_id, binding in ledger['bindings'].items()
                                      if binding['pattern_id'] == pattern_id)),
                modules=tuple(sorted((fit_id, key) for pid, fit_id, key, _, _ in module_rows(records)
                                     if pid == pattern_id)))


def holder_fits(records, ledger, pattern_id):
    holders = inventory(records, ledger, pattern_id)
    return set(holders['incoming']) | {fit_id for fit_id, _ in holders['modules']}


def validate(records, ledger, engine):
    from android_bridge.module_rah import GROUP
    for pattern_id, _, _, _, module in module_rows(records):
        row = damage.resolve(ledger, pattern_id)
        require(damage.assignable(row['values']), 'unassignable', 'Named reactive armor requires a positive pattern')
        item = engine._item(module['name'])
        require(item.group.name == GROUP, 'reference', 'Only local reactive armor hardeners may hold named patterns')


class Resolver:
    def __init__(self, ledger):
        self.ledger = deepcopy(ledger)
        self._objects = {}

    def resolve(self, pattern_id):
        named_id(pattern_id)
        row = damage.resolve(self.ledger, pattern_id)
        require(damage.assignable(row['values']), 'unassignable', 'Named reactive armor requires a positive pattern')
        if pattern_id not in self._objects:
            from eos.saveddata.damagePattern import DamagePattern
            value = DamagePattern(**deepcopy(row['values']))
            value.rawName = row['name']
            self._objects[pattern_id] = value
        return self._objects[pattern_id]

    def identify(self, value):
        # Never infer identity from names, values or ORM IDs.
        return next((key for key, known in self._objects.items() if known is value), None)


def selection(value):
    require(type(value) is dict, 'invalid_request', 'Invalid reactive armor selection')
    mode = value.get('mode')
    if mode in ('fit', 'disabled'):
        require(set(value) == {'mode'}, 'invalid_request', 'This mode has no pattern identity')
    elif mode == 'builtin':
        require(set(value) == {'mode', 'pattern_id'} and type(value['pattern_id']) is int and
                damage.builtin_id(value['pattern_id']) in damage.CATALOGUE,
                'invalid_request', 'Choose a known built-in pattern')
    elif mode == 'named':
        require(set(value) == {'mode', 'pattern_id', 'revision'}, 'invalid_request', 'Invalid named selection')
        named_id(value['pattern_id'])
        damage.integer(value['revision'], 1)
    else:
        require(False, 'invalid_request', 'Invalid reactive armor mode')
    return value


def target(state, fit_id, args, engine):
    from android_bridge.module_rah import GROUP
    graph = state['fit_graph']
    require(fit_id in graph['records'], 'missing_fit', 'Select an existing saved fit')
    damage.integer(args['fit_revision'], 1)
    require(args['fit_revision'] == graph['revisions'][fit_id], 'stale_fit', 'Saved fit changed; reload')
    key, position = args['object_key'], args['position']
    damage.integer(position)
    require(type(key) is str and damage.FIT.fullmatch(key), 'invalid_request', 'Invalid logical module identity')
    record = graph['records'][fit_id]
    modules = record['spec']['modules']
    keys = record.get('inspection_ids', {}).get('modules')
    require(type(keys) is list and len(keys) == len(modules) and position < len(modules) and
            keys[position] == key and 'empty_slot' not in modules[position],
            'stale_module', 'The selected module changed; reload')
    module = modules[position]
    item = engine._item(module['name'])
    require(item.group.name == GROUP, 'stale_module', 'The selected module is not a reactive armor hardener')
    return module, item


def descriptor(state, fit_id, position, engine):
    graph = state['fit_graph']
    record = graph['records'][fit_id]
    key = record['inspection_ids']['modules'][position]
    module, item = target(state, fit_id, dict(fit_revision=graph['revisions'][fit_id], object_key=key, position=position), engine)
    tag = module.get('rah_pattern', {'mode': 'fit'})
    mode = tag['mode']
    builtin = tag['pattern_id'] if mode == 'builtin' else None
    named = tag['pattern_id'] if mode == 'named' else None
    row = damage.resolve(state['damage_patterns'], named or damage.builtin_id(builtin)) if mode in ('builtin', 'named') else None
    raw = row['values'] if row else None
    require(raw is None or damage.assignable(raw), 'unassignable', 'Reactive armor pattern is unavailable')
    return dict(index=position, object_key=key, item_id=item.ID, name=item.name, mode=mode,
                builtin_id=builtin, named_id=named, pattern_revision=row['revision'] if row else None,
                pattern_name=row['name'] if row else None,
                components={name: raw[name+'Amount'] for name in ('em', 'thermal', 'kinetic', 'explosive')} if raw else None)


def set_module(state, fit_id, args, engine):
    module, _ = target(state, fit_id, args, engine)
    value = selection(args['selection'])
    if value['mode'] == 'named':
        row = damage.resolve(state['damage_patterns'], value['pattern_id'], revision=value['revision'])
        require(damage.assignable(row['values']), 'unassignable', 'Choose a positive damage pattern')
    tag = {key: value[key] for key in ('mode', 'pattern_id') if key in value}
    previous = module.get('rah_pattern', {'mode': 'fit'})
    if damage.exact(previous, tag):
        return None, set()
    if value['mode'] == 'fit':
        module.pop('rah_pattern', None)
    else:
        module['rah_pattern'] = tag
    return None, {fit_id}


def check_live(record, fit, resolver):
    """Read-only consistency check, never recover an unknown live override."""
    from android_bridge.inspection_identity import identity
    from android_bridge.module_rah import capture
    modules = record['spec']['modules']
    keys = record['inspection_ids']['modules']
    require(len(fit.modules) == len(modules) == len(keys), 'stale_module', 'The local module layout changed')
    for live, saved, key in zip(fit.modules, modules, keys):
        require(identity(fit, live) == key and live.isEmpty == ('empty_slot' in saved),
                'stale_module', 'The local module identity changed')
        if live.isEmpty:
            require('rah_pattern' not in saved, 'stale_module', 'An empty slot cannot hold a pattern')
        else:
            require(live.item.name == saved['name'], 'stale_module', 'The local module item changed')
            require(damage.exact(capture(live, resolver),
                    {'rah_pattern': saved['rah_pattern']} if 'rah_pattern' in saved else {}),
                    'stale_module', 'The local reactive armor selection changed')
