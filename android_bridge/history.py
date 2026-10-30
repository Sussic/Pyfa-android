"""Session-local user-action history; EOS replay and durable commits stay in the bridge."""
from copy import deepcopy
from dataclasses import dataclass


LIMIT = 100  # Pinned Fit.getCommandProcessor(maxCommands=100).
MODULE_LABELS = {
    'fit_implant': 'Fit implant',
    'toggle_implants': 'Toggle implants',
    'remove_implants': 'Remove implants',
    'set_system_security': 'Change fit system security',
    'set_module_rah': 'Change reactive armor pattern',
    'set_module_spool': 'Change module spool',
    'add_module': 'Add module', 'replace_module': 'Replace module',
    'remove_module': 'Remove module', 'set_fit_restrictions': 'Change fitting restrictions',
    'set_charges': 'Change ammunition', 'set_module_charge': 'Change ammunition',
    'set_bulk_charges': 'Change selected ammunition', 'set_module_states': 'Change module states',
    'set_bulk_states': 'Change selected states', 'fill_modules_item': 'Fill slots',
    'fill_modules_clone': 'Fill with clones', 'clone_selected_modules': 'Clone selected modules',
    'clone_module_at': 'Clone module', 'change_variation': 'Change module variation',
    'change_bulk_variations': 'Change selected variations', 'remove_bulk_modules': 'Remove selected modules',
    'swap_modules': 'Reorder modules',
}
LABELS = {**MODULE_LABELS,
    'set_mutation_attributes': 'Edit exact mutation rolls',
    'set_mutation_display_attributes': 'Edit displayed mutation rolls',
    'set_projected_module_charges':'Change selected projected charges',
    'set_projected_fighters_active':'Change selected projected fighter states',
    'set_projected_fighter_ranges':'Change selected projected fighter ranges',
    'remove_projected_fighters':'Remove selected projected fighter squadrons',
    'toggle_projected_fighter_abilities':'Toggle selected projected fighter abilities',

    'set_projected_drones_active':'Change selected projected drone states',
    'set_projected_drone_ranges':'Change selected projected drone ranges',
    'remove_projected_drones':'Remove selected projected drone stacks',
    'add_projected_fighter':'Add projected fighter',
    'set_projected_fighter_amount':'Change projected fighter quantity',
    'set_projected_fighter_active':'Change projected fighter state',
    'toggle_projected_fighter_ability':'Toggle projected fighter ability',
    'set_projected_fighter_range':'Change projected fighter range',
    'change_projected_fighter_variation':'Change projected fighter variation',
    'remove_projected_fighter':'Remove projected fighter',
    'add_projected_drone':'Add projected drone',
    'set_projected_drone_amount':'Change projected drone quantity',
    'set_projected_drone_active':'Change projected drone state',
    'set_projected_drone_range':'Change projected drone range',
    'change_projected_drone_variation':'Change projected drone variation',
    'remove_projected_drone':'Remove projected drone',
    'set_projected_module_states':'Change selected projected states',
    'set_projected_module_ranges':'Change selected projected ranges',
    'remove_projected_modules':'Remove selected projected modules',
    'add_projected_module':'Add projected module',
    'remove_projected_module':'Remove projected module',
    'set_projected_module_state':'Change projected module state',
    'set_projected_module_charge':'Change projected module charge',
    'set_projected_module_range':'Change projected module range',
    'set_projected_module_spool':'Change projected module spool',
    'change_projected_module_variation':'Change projected module variation',
    'add_fighter':'Add fighter squadron','set_fighter_amount':'Change fighter quantity',
    'remove_fighters':'Remove fighter squadrons','toggle_fighters':'Change fighter states',
    'toggle_fighter_ability':'Change fighter abilities','change_fighter_variations':'Change fighter variations',
    'add_drone': 'Add drone', 'add_drone_stack': 'Add drone stack',
    'set_drone_amount': 'Change drone quantity', 'remove_drones': 'Remove selected drones',
    'toggle_drones': 'Change selected drone states', 'clone_drone': 'Clone drone stack',
    'split_drone': 'Split drone stack', 'merge_drones': 'Merge drone stacks',
    'rename_fit': 'Rename fit', 'change_mode': 'Change hull mode',
    'set_subsystem': 'Change subsystem', 'add_cargo': 'Add cargo',
    'set_cargo_quantity': 'Change cargo quantity', 'remove_cargo': 'Remove cargo',
    'set_cargo_quantities': 'Change selected cargo quantities',
    'remove_cargos': 'Remove selected cargo', 'add_cargo_preset': 'Add ammunition preset',
    'fill_cargo': 'Fill cargo', 'change_cargo_variations': 'Change cargo variations',
    'transfer_cargo': 'Transfer fitted equipment and cargo',
    'set_damage_pattern': 'Change incoming damage',
    'set_target_profile': 'Change target profile',
    'set_skill_level': 'Change skill level', 'add_implant': 'Add implant',
    'set_implant_active': 'Change implant state', 'remove_implant': 'Remove implant',
    'fit_booster': 'Fit booster', 'toggle_boosters': 'Change booster states',
    'remove_boosters': 'Remove boosters', 'change_booster_variation': 'Change booster variation',
    'add_booster': 'Add booster', 'set_booster_active': 'Change booster state',
    'set_booster_side_effect': 'Change booster side effect', 'remove_booster': 'Remove booster',
    'add_command_fit': 'Add command fit',
    'set_command_fit_active': 'Change command fit state',
    'remove_command_fit': 'Remove command fit',
    'add_projected_fit': 'Add projected fit',
    'set_projected_fit_amount': 'Change projected fit quantity',
    'set_projected_fit_range': 'Change projected fit range',
    'set_projected_fit_active': 'Change projected fit state',
    'remove_projected_fit': 'Remove projected fit',
    'add_projection': 'Add projected fit', 'configure_projection': 'Change projected fit',
    'remove_projection': 'Remove projected fit', 'add_command': 'Add command fit',
    'set_command_active': 'Change command fit state', 'remove_command': 'Remove command fit',
}
# Lifecycle changes are library operations, not fitting commands. Notes follow
# the original direct notes service and must survive unrelated fitting reversals.
NON_HISTORY = {'snapshot': 'query', 'create_fit': 'new fit has empty history',
    'duplicate_fit': 'copy has empty history', 'delete_fit': 'prune fit and invalid references',
    'set_notes': 'direct note write', 'undo': 'move cursor', 'redo': 'move cursor'}


def validate_operations(operations):
    """New bridge operations need an explicit history disposition before use."""
    if set(operations) != set(LABELS) | set(NON_HISTORY):
        raise ValueError('Every bridge operation must declare its history disposition')


def _same(left, right):
    if type(left) is not type(right): return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same(a,b) for a,b in zip(left,right))
    return left == right


def _meaning(record):
    """Do not make an undo action just because a no-op filled spare slot rows."""
    result = deepcopy(record)
    spec = result['spec']
    if 'inspection_ids' in result:
        result['inspection_ids']['modules'] = [key for key, row in zip(
            result['inspection_ids']['modules'], spec['modules']) if 'empty_slot' not in row]
    spec['modules'] = [(i,row) for i,row in enumerate(spec['modules']) if 'empty_slot' not in row]
    spec['ignore_restrictions'] = spec.get('ignore_restrictions', False)
    return result


@dataclass(frozen=True)
class Change:
    path: tuple
    before_present: bool
    before: object
    after_present: bool
    after: object


def _changes(before, after, path=()):
    for key in sorted(before.keys() | after.keys()):
        a, b = before.get(key), after.get(key)
        if key in before and key in after and type(a) is dict and type(b) is dict:
            yield from _changes(a,b,(*path,key))
        elif key not in before or key not in after or not _same(a,b):
            yield Change((*path,key),key in before,deepcopy(a),key in after,deepcopy(b))


@dataclass(frozen=True)
class Action:
    label: str
    changes: tuple
    recent: tuple


class EditHistory:
    def __init__(self, rows=None):
        # Lists and actions are treated as immutable after construction. Staging
        # another object leaves the published cursor intact if persistence fails.
        self.rows = {} if rows is None else rows

    def details(self, fit_id):
        actions, cursor = self.rows.get(fit_id, ((),0))
        return {'undo_count':cursor,'redo_count':len(actions)-cursor,'limit':LIMIT,
            'undo_label':actions[cursor-1].label if cursor else None,
            'redo_label':actions[cursor].label if cursor<len(actions) else None}

    def after_edit(self, operation, arguments, before, after, recent):
        rows = {key:value for key,value in self.rows.items() if key in after}
        owner = arguments.get('fit_id', arguments.get('target_id'))
        tracked = operation in LABELS
        if tracked:
            changes = tuple(_changes(before[owner],after[owner]))
            if _same(_meaning(before[owner]),_meaning(after[owner])):
                return EditHistory(rows)
            actions,cursor = rows.get(owner,((),0))
            label = ('Change addition variation' if operation == 'change_variation' and
                arguments['context'] != 'module' else LABELS[operation])
            actions = (*actions[:cursor],Action(label,changes,tuple(recent)))[-LIMIT:]
            rows[owner] = actions,len(actions)
        else:
            # Lifecycle writes which remove a referenced source invalidate that
            # recipient's conflicting actions rather than reviving a deleted fit.
            for key in list(rows):
                if key not in before: continue
                changed = [value.path for value in _changes(before[key],after[key])]
                actions,_ = rows[key]
                if any(a[:len(b)]==b or b[:len(a)]==a for a in changed
                       for action in actions for b in (c.path for c in action.changes)):
                    del rows[key]
        return EditHistory(rows)

    def replay(self, fit_id, redo, records):
        actions,cursor = self.rows.get(fit_id,((),0))
        if (redo and cursor==len(actions)) or (not redo and cursor==0):
            raise ValueError('No redo action is available' if redo else 'No undo action is available')
        action=actions[cursor if redo else cursor-1]
        result=deepcopy(records)
        original_modules = records[fit_id]['spec']['modules']
        for change in action.changes:
            parent=result[fit_id]
            for name in change.path[:-1]: parent=parent[name]
            key=change.path[-1]
            present,value=(change.before_present,change.before) if redo else (change.after_present,change.after)
            matches = (key in parent)==present and (not present or _same(parent[key],value))
            if change.path == ('spec','modules') and present and key in parent:
                matches = _same([(i,row) for i,row in enumerate(parent[key]) if 'empty_slot' not in row],
                                [(i,row) for i,row in enumerate(value) if 'empty_slot' not in row])
            if change.path == ('inspection_ids', 'modules') and present and key in parent:
                current_modules = result[fit_id]['spec']['modules']
                module_change = next((member for member in action.changes if member.path == ('spec', 'modules')), None)
                expected_modules = ((module_change.before if redo else module_change.after)
                                    if module_change is not None else current_modules)
                def occupied(identities, modules):
                    return [(index, identity) for index, identity in enumerate(identities)
                            if index < len(modules) and 'empty_slot' not in modules[index]]
                matches = _same(occupied(parent[key], current_modules), occupied(value, expected_modules))
            if change.path == ('spec','ignore_restrictions'):
                matches = _same(parent.get(key,False),value if present else False)
            if not matches:
                raise ValueError('Fit inputs changed outside this undo history')
            present,value=(change.after_present,change.after) if redo else (change.before_present,change.before)
            if present: parent[key]=deepcopy(value)
            else: parent.pop(key,None)
        # A no-op may append spare EOS slot rows without entering history. If
        # replay restores the shorter original module list, discard identities
        # only for those proven-empty spare rows, retaining every occupied ID.
        if 'inspection_ids' in result[fit_id]:
            identities = result[fit_id]['inspection_ids']['modules']
            count = len(result[fit_id]['spec']['modules'])
            if len(identities) > count:
                if len(identities) != len(original_modules) or any(
                        'empty_slot' not in row for row in original_modules[count:]):
                    raise ValueError('Fit object identities changed outside this undo history')
                result[fit_id]['inspection_ids']['modules'] = identities[:count]
        rows=dict(self.rows)
        rows[fit_id]=actions,cursor+(1 if redo else -1)
        return result,EditHistory(rows),list(action.recent) if redo else []
