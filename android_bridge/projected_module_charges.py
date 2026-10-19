"""Selected incoming charges: original scope policy, one GUI/calc transaction.

Compatibility reads modified attributes. Call only after admitted LOCAL preparation.
The complete selected scope is distinct from the calc command's per-row skips.
"""
from . import projected_module_editor as single
from . import projected_module_bulk as bulk_rows
from . import projected_module_records as records
from . import charges, bulk, fitting
from .inspection_identity import identity

OPERATIONS = {'set_projected_module_charges': (
    'fit_id', 'main', 'selection', 'scope', 'charge_id',
    'expected_targets', 'expected_changes')}
CHOICE_LIMIT = 8192
MAX_COMPATIBILITY_VISITS = 65536


class Compatibility:
    """Request-local source result cache, never item-ID or cross-query state.

    EOS validity reads raw capacity and modified size/groups. Keep raw ordered
    group values: group lookup casts int, but validity compares raw equality.
    Count duplicate group traversals exactly as getValidCharges does before it
    runs. The pinned catalogue needs <=40 visits per ordinary module, hence
    <=40960 for 1024 uncached rows. Resource refusal never truncates a choice set.
    """
    def __init__(self):
        self.cache = {}
        self.visits = 0

    def get(self, module):
        if module.isEmpty:
            return set()
        signature = (module.item.attributes['capacity'].value,
            module.getModifiedItemAttr('chargeSize'),
            *(module.getModifiedItemAttr('chargeGroup' + str(i), None) for i in range(5)))
        if signature not in self.cache:
            import eos.db
            from .projected_drone_admission import AdmissionRejected
            visits = 0
            for group_id in signature[2:]:
                if group_id:
                    group = eos.db.getGroup(int(group_id), eager='items.attributes')
                    if group is not None:
                        visits += len(group.items)
            if self.visits + visits > MAX_COMPATIBILITY_VISITS:
                raise AdmissionRejected('Projected-charge compatibility budget: candidate visits exceeded')
            self.visits += visits
            result = charges.compatible(module)
            if len(result) > CHOICE_LIMIT:
                raise ValueError('Too many projected charge choices')
            self.cache[signature] = frozenset(result)
        return self.cache[signature]


def anchor(fit, position):
    module = fit.projectedModules[position]
    return dict(index=position, object_key=identity(fit, module), item_id=module.itemID)


def resolve(engine, fit, request):
    single.require_fit(engine, fit)
    if len(fit.projectedModules) > records.LIMIT:
        raise ValueError('Select at most 1024 projected modules per edit')
    if type(request) is not dict or set(request) != {'main', 'selection', 'scope', 'charge_id'}:
        raise ValueError('Invalid projected charge preview')
    selected = bulk_rows.selected(fit, request['selection'])
    main_rows = bulk_rows.selected(fit, [request['main']])
    main_position, main = main_rows[0]
    if main_position not in {position for position, _ in selected}:
        raise ValueError('Include the reference module in the selection')
    if type(request['scope']) is not str or request['scope'] not in ('SELECTED', 'SIMILAR'):
        raise ValueError('Choose selection only or all similar modules')
    charge_id = request['charge_id']
    if charge_id is not None and (type(charge_id) is not int or not 1 <= charge_id <= 2**31 - 1):
        raise ValueError('Choose a compatible charge for the reference module')
    compatibility = Compatibility()
    main_choices = compatibility.get(main)
    if len(main_choices) > CHOICE_LIMIT:
        raise ValueError('Too many projected charge choices')
    if not main_choices:
        raise ValueError('Choose a reference module with compatible charges')
    charge = None if charge_id is None else fitting.item(engine, charge_id)
    if charge is not None and (not charge.isCharge or charge not in main_choices):
        raise ValueError('Choose a compatible charge for the reference module')
    selected_positions = {position for position, _ in selected}
    excluded = []
    if request['scope'] == 'SIMILAR':
        from .market_policy import MarketPolicy
        positions = bulk.similar(fit.projectedModules, main, MarketPolicy())
    else:
        positions = []
        for position, module in enumerate(fit.projectedModules):
            if position not in selected_positions:
                continue
            choices = compatibility.get(module)
            if len(choices) > CHOICE_LIMIT:
                raise ValueError('Too many projected charge choices')
            if choices.issubset(main_choices):
                positions.append(position)
            else:
                excluded.append(dict(**anchor(fit, position), reason='Complete compatible-charge set is not a subset of the reference module'))
    if request['scope'] == 'SIMILAR':
        for position, _ in sorted(selected):
            if position not in positions:
                excluded.append(dict(**anchor(fit, position), reason='Not similar to the reference module'))
    prefix = records.prefix(fit)
    available = all(position >= prefix and records.eligible(fit.projectedModules[position].item) for position in positions)
    targets = []
    for position in positions:
        module = fit.projectedModules[position]
        status = ('unchanged' if module.chargeID == charge_id else
                  'change' if module.isValidCharge(charge) else 'incompatible')
        targets.append(dict(**anchor(fit, position), name=module.item.name,
            charge_id=module.chargeID, charge_name=None if module.charge is None else module.charge.name,
            status=status))
    return dict(main=anchor(fit, main_position), selection=[anchor(fit, p) for p, _ in selected],
        scope=request['scope'], charge_id=charge_id,
        choices=[dict(id=item.ID, name=item.name) for item in sorted(main_choices, key=lambda item: (item.name, item.ID))],
        available=available, unavailable_reason=None if available else 'This scope includes a read-only legacy environment; use Selection only',
        targets=targets, excluded=excluded), charge


def preview(engine, fit, request):
    return resolve(engine, fit, request)[0]


def captured(rows):
    return [dict(position=row['index'], object_key=row['object_key']) for row in rows]


def change(engine, fit, args):
    request = {key: args[key] for key in ('main', 'selection', 'scope', 'charge_id')}
    result, charge = resolve(engine, fit, request)
    if not result['available']:
        raise ValueError(result['unavailable_reason'])
    changed = [row for row in result['targets'] if row['status'] == 'change']
    # Exact shape/type validation avoids bool==int or extra-key identity aliases.
    for key, expected in (('expected_targets', result['targets']), ('expected_changes', changed)):
        value = args[key]
        if type(value) is not list or len(value) > records.LIMIT:
            raise ValueError('Projected charge preview changed; review it again')
        for row in value:
            if (type(row) is not dict or set(row) != {'position', 'object_key'} or
                    type(row['position']) is not int or type(row['object_key']) is not str):
                raise ValueError('Projected charge preview changed; review it again')
        if value != captured(expected):
            raise ValueError('Projected charge preview changed; review it again')
    # No recalculation runs between assignments: all source-compatible changes
    # form one proposal. Engine guards admit the complete live graph before its
    # first effect evaluation and exact newly calculated drains before simulation.
    for row in changed:
        fit.projectedModules[row['index']].charge = charge
    need = single.inner(engine, fit, None) if changed else True
    single.finish(engine, fit, need)
