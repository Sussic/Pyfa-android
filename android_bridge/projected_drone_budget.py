"""Conservative incoming-drone configuration admission on immutable inputs.

This bounds incremental projected-drone dispatch/list/scan work, not all legacy
EOS work or a wall-clock deadline. Native limits are explicit, never game rules.
Unknown operation/effect semantics fail closed. Incoming drones reserve their
actual proposed active count; every activation is admitted before effects. Local
and outgoing legacy quantities remain conservatively all-active. No clamping.
"""
from copy import deepcopy
from .projected_drone_admission import AdmissionRejected
from .projected_drone_records import validate, eligible

MAX_COLD_UNITS = 16384
MAX_REQUEST_UNITS = 134217728
REQUEST_PHASES = 8
MAX_IMPORT_PHASES = 35
EFFECT_IDS = frozenset(range(6687, 6696))


def reject(reason):
    raise AdmissionRejected('Projected-drone evaluation budget: ' + reason)


def effect_id(item):
    if item is None or not eligible(item):
        reject('unsupported projected drone type')
    effects = [effect for effect in item.effects.values() if effect.isType('projected')]
    if len(effects) != 1:
        reject('unaudited projected drone effects')
    effect = effects[0]
    if (effect.ID not in EFFECT_IDS or not effect.activeByDefault or effect.getattr('grouped') or
            effect.runTime != ('late' if effect.ID == 6689 else 'normal')):
        reject('unaudited projected drone effect policy')
    return effect.ID


def present(records):
    return any(record['spec'].get('projected_drones') or record['spec'].get('projected_fighters') for record in records.values())


def implant_inputs(record):
    """Owned input containers only; a legacy record means FIT and no character rows.

    Full row validation belongs to the graph codec and live preparation. These
    same containers also carry count-only placeholders in live_records, so this
    metadata pass checks their shape and selector, never captures live implants.
    """
    modern = 'implant_source' in record
    if modern != ('character_implants' in record):
        reject('incomplete implant source inputs')
    source = record.get('implant_source', 'FIT')
    local = record.get('implants', [])
    character = record.get('character_implants', [])
    if (type(source) is not str or source not in ('FIT', 'CHARACTER') or
            type(local) is not list or type(character) is not list):
        reject('invalid implant source inputs')
    return local, character, source


def live_implant_inputs(fit, *, legacy=False):
    """Read only materialized ORM inputs, including the dormant collection.

    ImplantLocation is the pinned IntEnum FIT=0 / CHARACTER=1. Do not import EOS
    or evaluate effects just to read its persisted selector. Live fits must have
    their actual source and character even for legacy records; those records may
    not hide character rows or select CHARACTER without explicit input fields.
    """
    location = getattr(fit, 'implantLocation', None)
    if isinstance(location, bool) or not isinstance(location, int) or location not in (0, 1):
        reject('invalid live implant source')
    source = 'FIT' if location == 0 else 'CHARACTER'
    character = getattr(getattr(fit, 'character', None), 'implants', None)
    if character is None or (legacy and (source != 'FIT' or len(character))):
        reject('unrecorded character implant inputs')
    local = fit.implants
    applied = local if source == 'FIT' else character
    if getattr(fit, 'appliedImplants', None) is not applied:
        reject('live applied implant source changed')
    return local, character, source


def admit(records, *, extra_module=True, extra_edge=True, request_phases=REQUEST_PHASES, include_local_only=False):
    """Metadata-only reservation before evaluation or destructive graph replay.

    One prospective local module/subsystem and one edge are reserved for normal
    editors. Create/copy/import add complete records separately before this call.
    No engine._item lookup: rejected admission must not mutate provenance.
    """
    if type(request_phases) is not int or not REQUEST_PHASES <= request_phases <= MAX_IMPORT_PHASES:
        reject("unsupported request phase reservation")
    # G09 opts in before LOCAL even when no individual incoming item exists.
    # This bypasses only the legacy exemption, not prices, caps or effect policy.
    if type(include_local_only) is not bool: reject("invalid local-only admission flag")
    if not include_local_only and not present(records): return dict(enabled=False, cold_units=0, request_units=0)
    import eos.db
    costs, modules, outgoing = {}, {}, {}
    implants = boosters = edges = 0
    max_rows = 0
    for key, record in records.items():
        spec = record['spec']
        rows = spec.get('projected_drones', [])
        validate(rows)
        subsystem_count = 0
        module_effects = 0
        for row in spec['modules']:
            if 'name' in row:
                item = eos.db.getItem(row['name'])
                if item is None: reject('unknown module input')
                subsystem_count += int(item.category.name == 'Subsystem')
                module_effects += sum(e.isType('projected') for e in item.effects.values())
        # Source-only slot writer proof: base six-slot sum <=39, each existing
        # subsystem contributes <=13. Reserve one future row/modifier (+14).
        size = len(spec['modules']) + 39 + 13 * subsystem_count + (14 if extra_module else 0)
        modules[key] = size
        cost = 0
        seen = set()
        for row in rows:
            item = eos.db.getItem(row['name'])
            effect = effect_id(item)
            if item.ID in seen: reject('duplicate projected drone type')
            seen.add(item.ID)
            cost += 3 + row['active'] * (4 + (3 * size if effect == 6694 else 0))
            if cost > MAX_COLD_UNITS: reject('active projected-drone quantities exceed the cold-read reservation')
        local_quantity_work = 0
        outgoing_quantity_work = 0
        for row in spec.get('drones', []):
            item = eos.db.getItem(row['name'])
            if item is None: reject('unknown local drone input')
            quantity = row['amount']
            local_quantity_work += 3 * len(item.effects)
            local_quantity_work += 4 * sum(1 if e.getattr('grouped') else quantity for e in item.effects.values() if e.activeByDefault and e.isType('passive'))
            outgoing_quantity_work += sum(1 if e.getattr('grouped') else quantity for e in item.effects.values() if e.activeByDefault and e.isType('projected'))
        for row in spec.get('fighters', []):
            item = eos.db.getItem(row['name'])
            if item is None: reject('unknown fighter input')
            local_quantity_work += 3 * len(item.effects)
            local_quantity_work += 4 * sum(1 if e.getattr('grouped') else row['amount'] for e in item.effects.values() if e.activeByDefault)
            outgoing_quantity_work += sum(1 if e.getattr('grouped') else row['amount'] for e in item.effects.values() if e.activeByDefault and e.isType('projected'))
        from .projected_fighter_budget import cost as fighter_cost
        cost += fighter_cost(spec.get('projected_fighters', []))
        cost += local_quantity_work
        if cost > MAX_COLD_UNITS: reject('local drone quantities exceed the configuration reservation')
        costs[key] = cost
        outgoing[key] = (3 * (size + len(spec.get('drones', [])) + len(spec.get('fighters', []))),
                         4 * (module_effects + outgoing_quantity_work))
        local_implants, character_implants, _ = implant_inputs(record)
        # Logical profile sharing does not share mutable EOS instances: every
        # bound fit materializes both collections, even when either is dormant.
        implant_rows = len(local_implants) + len(character_implants)
        implants += implant_rows
        boosters += len(record.get('boosters', []))
        edges += len(record.get('projections', [])) + len(record.get('commands', []))
        other = sum(len(spec.get(name, [])) for name in ('drones','fighters','cargo','environments','projected_modules','projected_drones','projected_fighters'))
        max_rows = max(max_rows, size + other + implant_rows + len(record.get('boosters', [])))
    commands = {}
    for key, record in records.items():
        commands[key] = sum(costs[edge['source_id']] for edge in record.get('commands', []) if edge['source_id'] != key)
    cold = {}
    for key, record in records.items():
        value = costs[key] + commands[key]
        for edge in record.get('projections', []):
            source = edge['source_id']
            if source != key: value += costs[source] + commands[source]
        # __runProjectionEffects loops every saved multiplicity, including self
        # edges, and may run a local drone handler once per active drone. Reserve
        # all quantities and each recipient's module-scan bound, even if inactive.
        for edge in record.get('projections', []):
            source = edge['source_id']
            amount = edge['amount']
            calls, handlers = outgoing[source]
            value += amount * (calls + handlers * (4 + 3 * modules[key]))
        cold[key] = value
    maximum = max(cold.values(), default=0)
    if extra_edge:
        # A new projection can add a source and its commands; a new command can
        # also be reached through every existing incoming projection path.
        maximum += (1 + max((len(r.get('projections', [])) for r in records.values()), default=0)) * max(costs.values(), default=0) + max(commands.values(), default=0)
    if maximum > MAX_COLD_UNITS: reject('linked-fit cold-read reservation exceeded')
    fits = len(records)
    rebuild = 5 * fits + implants + boosters + 2 * (edges + int(extra_edge))
    # See admission contract's finite operation-family schedule. Each phase is
    # bounded by a rebuild plus worst per-row fitting reconciliation on ONE
    # selected fit (all current bulk operations are single-fit), including
    # rollback. Ordinary nesting is <=5H (reserve8H); imports separately
    # reserve max(8,2N+3)H before their first stage, at most35H for16docs.
    roots = rebuild + 4 * max_rows + 8 * fits + 32
    work = request_phases * roots * maximum
    if work > MAX_REQUEST_UNITS: reject('complete-request reservation exceeded')
    return dict(enabled=True, fits=fits, cold_units=maximum, request_units=work,
                root_calls_per_phase=roots, request_phases=request_phases,
                module_bounds=modules)


def admit_transition(before, after, *, extra_module=True, extra_edge=True,
                     request_phases=REQUEST_PHASES, include_local_only=False):
    """Reserve a complete candidate plus rollback before either EOS stage.

    The existing eight-phase schedule already includes recovery. Use the larger
    root and cold bounds across both graphs, not merely two independent success
    checks: their maxima can belong to different inputs. No inputs are combined,
    mutated or materialized, and the legacy no-incoming exemption is preserved
    only when neither side needs the reservation.
    """
    if type(include_local_only) is not bool:
        reject('invalid local-only admission flag')
    enabled = include_local_only or present(before) or present(after)
    options = dict(extra_module=extra_module, extra_edge=extra_edge,
                   request_phases=request_phases, include_local_only=enabled)
    previous = admit(before, **options)
    proposed = admit(after, **options)
    if not enabled:
        return proposed
    roots = max(previous['root_calls_per_phase'], proposed['root_calls_per_phase'])
    cold = max(previous['cold_units'], proposed['cold_units'])
    work = request_phases * roots * cold
    if work > MAX_REQUEST_UNITS:
        reject('complete-request candidate and rollback reservation exceeded')
    return dict(enabled=True, fits=max(previous['fits'], proposed['fits']),
                cold_units=cold, request_units=work,
                root_calls_per_phase=roots, request_phases=request_phases)


def proposed_records(records, key, rows, family='projected_drones'):
    if family not in ('projected_drones', 'projected_fighters'):
        raise ValueError('Unknown incoming projection record family')
    result = deepcopy(records)
    result[key]['spec'][family] = deepcopy(rows)
    return result


def live_records(fits):
    """No effects/derived attributes: snapshot only already-owned ORM inputs."""
    from .projected_fighter_records import row as fighter_row
    result = {}
    for fit in fits:
        local_implants, character_implants, source = live_implant_inputs(fit)
        result[id(fit)] = dict(spec=dict(
            modules=[{} if m.isEmpty else {'name': m.item.name} for m in fit.modules],
            drones=[dict(name=d.item.name, amount=d.amount) for d in fit.drones],
            fighters=[dict(name=f.item.name, amount=f.amount) for f in fit.fighters],
            cargo=[None for _ in fit.cargo], environments=[],
            projected_modules=[None for _ in fit.projectedModules],
            projected_drones=[dict(name=d.item.name, amount=d.amount, active=d.amountActive,
                                   range_m=d.projectionRange) for d in fit.projectedDrones],
            projected_fighters=[fighter_row(f) for f in fit.projectedFighters]),
            implants=[None for _ in local_implants],
            character_implants=[None for _ in character_implants], implant_source=source,
            boosters=[None for _ in fit.boosters],
            projections=[dict(source_id=id(source), amount=source.getProjectionInfo(fit.ID).amount)
                         for source in fit.projectedFitDict.values()],
            commands=[dict(source_id=id(source)) for source in fit.commandFitDict.values()])
    return result


# Explicit reviewed dispatch surface; new families need a new cost proof.
# D01.4 selected projector helper: <= N+1 roots within existing 4T; no cap runs.
# D01.9 joint incoming charge helper: <=2 roots, no direct cap simulation.
ADMITTED_OPERATIONS = frozenset(('set_projected_module_charges', 'set_projected_fighters_active', 'set_projected_fighter_ranges', 'remove_projected_fighters', 'toggle_projected_fighter_abilities', 'add_projected_fighter', 'set_projected_fighter_amount', 'set_projected_fighter_active', 'toggle_projected_fighter_ability', 'set_projected_fighter_range', 'change_projected_fighter_variation', 'remove_projected_fighter', 'set_projected_drones_active', 'set_projected_drone_ranges', 'remove_projected_drones', 'set_projected_module_states', 'set_projected_module_ranges', 'remove_projected_modules', 'add_booster', 'add_cargo', 'add_cargo_preset', 'add_command', 'add_command_fit', 'add_drone', 'add_drone_stack', 'add_fighter', 'add_implant', 'add_module', 'add_projected_drone', 'add_projected_fit', 'add_projected_module', 'add_projection', 'change_booster_variation', 'change_bulk_variations', 'change_cargo_variations', 'change_fighter_variations', 'change_mode', 'change_projected_drone_variation', 'change_projected_module_variation', 'change_variation', 'clone_drone', 'clone_module_at', 'clone_selected_modules', 'configure_projection', 'create_fit', 'delete_fit', 'duplicate_fit', 'fill_cargo', 'fill_modules_clone', 'fill_modules_item', 'fit_booster', 'fit_implant', 'merge_drones', 'redo', 'remove_booster', 'remove_boosters', 'remove_bulk_modules', 'remove_cargo', 'remove_cargos', 'remove_command', 'remove_command_fit', 'remove_drones', 'remove_fighters', 'remove_implant', 'remove_implants', 'remove_module', 'remove_projected_drone', 'remove_projected_fit', 'remove_projected_module', 'remove_projection', 'rename_fit', 'replace_module', 'set_booster_active', 'set_booster_side_effect', 'set_bulk_charges', 'set_bulk_states', 'set_cargo_quantities', 'set_cargo_quantity', 'set_charges', 'set_command_active', 'set_command_fit_active', 'set_damage_pattern', 'set_drone_amount', 'set_fighter_amount', 'set_fit_restrictions', 'set_implant_active', 'set_module_charge', 'set_module_rah', 'set_module_spool', 'set_module_states', 'set_notes', 'set_projected_drone_active', 'set_projected_drone_amount', 'set_projected_drone_range', 'set_projected_fit_active', 'set_projected_fit_amount', 'set_projected_fit_range', 'set_projected_module_charge', 'set_projected_module_range', 'set_projected_module_spool', 'set_projected_module_state', 'set_skill_level', 'set_subsystem', 'set_system_security', 'set_target_profile', 'snapshot', 'split_drone', 'swap_modules', 'toggle_boosters', 'toggle_drones', 'toggle_fighter_ability', 'toggle_fighters', 'toggle_implants', 'transfer_cargo', 'undo'))

def require_operation(operation, records):
    if present(records) and operation not in ADMITTED_OPERATIONS:
        reject("operation has no reviewed evaluation reservation")
