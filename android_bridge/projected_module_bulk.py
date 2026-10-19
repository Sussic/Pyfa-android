"""One selected-module transaction with original projected GUI/calc boundaries.

State changes are proposed together; range reconciles in captured selection order;
removal reconciles in descending position order. Never loop public bridge edits.
"""
from . import projected_module_editor as single
from . import projected_module_records as records

OPERATIONS = {
    'set_projected_module_states': ('fit_id', 'selection', 'state'),
    'set_projected_module_ranges': ('fit_id', 'selection', 'range_m'),
    'remove_projected_modules': ('fit_id', 'selection'),
}


def selected(fit, selection):
    """Resolve the entire captured selection before any mutation."""
    if type(selection) is not list or not 1 <= len(selection) <= records.LIMIT:
        raise ValueError('Choose one or more projected modules')
    positions, keys, result = set(), set(), []
    for row in selection:
        if type(row) is not dict or set(row) != {'position', 'object_key'}:
            raise ValueError('Invalid projected module selection')
        position, key = row['position'], row['object_key']
        if type(position) is not int or type(key) is not str or not key:
            raise ValueError('Invalid projected module selection')
        if position in positions or key in keys:
            raise ValueError('Choose each projected module once')
        module = single.selected(fit, position, key)
        positions.add(position); keys.add(key)
        result.append((position, module))
    return result


def change(engine, fit, operation, args):
    single.require_fit(engine, fit)
    rows = selected(fit, args['selection'])
    need = True
    if operation == 'set_projected_module_states':
        state = args['state']
        if type(state) is not str or state not in ('inactive', 'active', 'overheat'):
            raise ValueError('Choose a projected state action')
        # Calculate every proposal before applying any of them, then reconcile once.
        proposals = [(module, single.proposals(module)[state]) for _, module in rows]
        changed = False
        for module, proposed in proposals:
            if module.state != proposed:
                module.state = proposed
                changed = True
        if changed:
            need = single.inner(engine, fit, None)
    elif operation == 'set_projected_module_ranges':
        range_m = records.range_value(args['range_m'])
        for _, module in rows:
            # Original GUI overwrites, rather than ORs, the last command's flag.
            # Even a trailing no-op requests the final GUI recalculation.
            need = True
            if module.projectionRange != range_m:
                module.projectionRange = range_m
                need = single.inner(engine, fit, module)
    elif operation == 'remove_projected_modules':
        for position, _ in sorted(rows, key=lambda row: row[0], reverse=True):
            del fit.projectedModules[position]
            need = single.inner(engine, fit, None, flush=True)
    else:
        raise ValueError('Unknown selected projected module operation')
    single.finish(engine, fit, need)
