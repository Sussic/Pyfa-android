"""G09 checked, cumulative nominal allocation admission, not a heap guarantee.

The mandatory native admission uses already-owned authoritative records. It never
captures a fit, reads derived fighter quantity or runs LOCAL effects. Existing
preparation limits and graph allowance are independent and remain unchanged.
"""
import math
from android_bridge.projected_drone_admission import AdmissionRejected

MAX_COUNTER = 2**63 - 1
DEFAULT_ALLOWANCE = 100663296
MAX_WIRE_CHARS = 1036160
WIRE_HEADER_CHARS = 32768
WIRE_POINT_CHARS = 624
PRICES = {
    'container': 128, 'mapping_slot': 320, 'list_slot': 64,
    'tuple_value': 448, 'sort_slot': 32, 'output_point': 128,
    'output_slot': 320, 'serialization_unit': 6,
    'repair_parameter_call': 256, 'schedule_constructor': 512,
    'schedule_children': 64, 'scan': 0, 'sort_work': 0,
}
# Independent predicates, not mutually exclusive branches. Nosferatu is counted
# before its derived nosOverride can be read. Fighter amounts do NOT multiply N.
CONTRIBUTORS = {
    'neutStr': (('energyNeutralizerFalloff', 'structureEnergyNeutralizerFalloff', 'energyNosferatuFalloff', 'doomsdayAOENeut'), 'entityEnergyNeutralizerFalloff', 'fighterAbilityEnergyNeutralizer', 0),
    'webStr': (('remoteWebifierFalloff', 'structureModuleEffectStasisWebifier', 'doomsdayAOEWeb'), 'remoteWebifierEntity', 'fighterAbilityStasisWebifier', 1),
    'ecmStrMax': (('remoteECMFalloff', 'structureModuleEffectECM', 'doomsdayAOEECM'), 'entityECMFalloff', 'fighterAbilityECM', 0),
    'dampStrLockRange': (('remoteSensorDampFalloff', 'structureModuleEffectRemoteSensorDampener', 'doomsdayAOEDamp'), 'remoteSensorDampEntity', None, 1),
    'tdStrOptimal': (('shipModuleTrackingDisruptor', 'structureModuleEffectWeaponDisruption', 'doomsdayAOETrack'), 'npcEntityWeaponDisruptor', None, 1),
    'gdStrRange': (('shipModuleGuidanceDisruptor', 'structureModuleEffectWeaponDisruption', 'doomsdayAOETrack'), None, None, 2),
    'tpStr': (('remoteTargetPaintFalloff', 'structureModuleEffectTargetPainter', 'doomsdayAOEPaint'), 'remoteTargetPaintEntity', None, 1),
}


def refuse(message='EWAR resource admission failed'):
    raise AdmissionRejected(message)


def count(value):
    if type(value) is not int or not 0 <= value <= MAX_COUNTER:
        refuse('Invalid EWAR resource counter')
    return value


def add(a, b):
    count(a); count(b)
    if b > MAX_COUNTER - a: refuse('EWAR resource counter overflow')
    return a + b


def mul(a, b):
    count(a); count(b)
    if a and b > MAX_COUNTER // a: refuse('EWAR resource counter overflow')
    return a * b


class EwarReservation:
    """One ledger for all fits and all temporaries; there are no refunds."""
    def __init__(self, allowance=DEFAULT_ALLOWANCE):
        self.allowance = count(allowance)
        self.used = 0
        self.count = 0
        self.counts = {kind: 0 for kind in PRICES}

    def __call__(self, kind, amount):
        if kind not in PRICES: refuse('Unknown EWAR resource price')
        next_count = add(self.count, amount)
        cost = mul(amount, PRICES[kind])
        if cost > self.allowance - self.used:
            refuse('EWAR request exceeds the allocation allowance; no partial graph was returned')
        self.counts[kind] = add(self.counts[kind], amount)
        self.count = next_count
        self.used += cost


def reserve_graph(reserve, mode, bounds, point_bound):
    """Reserve the complete graph before the first LOCAL/common-data call."""
    if mode not in CONTRIBUTORS or type(point_bound) is not int or point_bound not in (1, 201): refuse()
    if type(bounds) not in (list, tuple) or not 1 <= len(bounds) <= 8: refuse()
    fits = len(bounds)
    lists = CONTRIBUTORS[mode][3]
    points = mul(fits, point_bound)
    reserve('output_point', points)
    reserve('output_slot', add(add(mul(2, points), mul(16, fits)), 24))
    reserve('container', add(8, mul(8, fits)))
    for n, neut_modules in bounds:
        count(n); count(neut_modules)
        reserve('container', 4)
        reserve('tuple_value', n)
        reserve('list_slot', mul(2, n))
        if mode == 'neutStr':
            reserve('repair_parameter_call', neut_modules)
            reserve('schedule_constructor', mul(3, neut_modules))
            reserve('schedule_children', mul(2, neut_modules))
        reserve('container', mul(point_bound, add(2, mul(4, lists))))
        reserve('mapping_slot', mul(point_bound, lists))
        entries = mul(mul(point_bound, lists), n)
        reserve('tuple_value', entries)
        reserve('list_slot', mul(3, entries))
        reserve('sort_slot', mul(4, entries))
        reserve('scan', mul(point_bound, mul(n, add(1, mul(5, lists)))))
        # ceil(log2(max(2,n))) without floating conversion or unchecked products.
        logarithm = (max(2, n) - 1).bit_length()
        reserve('sort_work', mul(mul(2, entries), logarithm))


def live_contributions(fit, mode, check):
    """Checked no-expansion pass immediately before original common data."""
    modules, drone_effect, fighter_effect, _ = CONTRIBUTORS[mode]
    total = neut_modules = 0
    for module in fit.activeModulesIter():
        check()
        for effect in modules:
            if effect in module.item.effects:
                total = add(total, 1)
                neut_modules = add(neut_modules, int(mode == 'neutStr'))
    if drone_effect:
        for drone in fit.activeDronesIter():
            check()
            if drone_effect in drone.item.effects:
                total = add(total, count(drone.amountActive))
    if fighter_effect:
        for fighter, ability in fit.activeFighterAbilityIter():
            check()
            if ability.effect.name == fighter_effect: total = add(total, 1)
    return total, neut_modules


def _raw_fighter_quantity(fighter, item):
    raw = fighter._amount
    if type(raw) is not int: refuse('Fighter authority quantity is invalid')
    if raw != -1: return count(raw)
    maximum = item.getAttribute('fighterSquadronMaxSize')
    # Source-pinned EOS has no writer for this attribute. Do not substitute the
    # derived fighter.amount getter during metadata-only admission.
    if (type(maximum) not in (int, float) or not math.isfinite(maximum) or
            not 0 <= maximum <= 2**31 - 1 or maximum != int(maximum)):
        refuse('Fighter maximum metadata is not admitted')
    return int(maximum)


def _same_quantity(row, obj, family, item):
    if family in ('drones', 'projected_drones'):
        amount, active = row.get('amount'), row.get('active')
        count(amount); count(active)
        if amount > 2**31 - 1 or active > amount or obj.amount != amount or obj.amountActive != active:
            refuse('Drone authority changed before EWAR preparation')
    elif family in ('fighters', 'projected_fighters'):
        amount = row.get('amount'); count(amount)
        if amount > 2**31 - 1 or _raw_fighter_quantity(obj, item) != amount or obj.active is not row.get('active'):
            refuse('Fighter authority changed before EWAR preparation')
        if len(obj.abilities) != len(item.effects): refuse('Fighter ability metadata changed')
        for effect in item.effects.values():
            if sum(ability.effectID == effect.ID for ability in obj.abilities) != 1:
                refuse('Fighter ability metadata changed')
        abilities = row.get('abilities')
        if abilities is not None:
            if type(abilities) is not list or len(abilities) != len(obj.abilities): refuse('Fighter ability authority changed')
            # No sorting or proportional scratch during authority verification.
            for ability in obj.abilities:
                matches = 0
                for saved in abilities:
                    if saved.get('effect_id') == ability.effectID:
                        matches += 1
                        if saved.get('active') is not ability.active: refuse('Fighter ability authority changed')
                if matches != 1: refuse('Fighter ability authority changed')


def _same_implants(saved, live, lookup, scratch, check, *, metadata=None, character=False):
    """Validate both materialized collections without effects or captures.

    Their rows have the same existing T price, selected or dormant. Profile row
    IDs live in checked per-fit metadata, not in the local inspector-ID family.
    Charge all row scratch before comparing that projection or looking up items.
    """
    if type(saved) is not list or len(saved) != len(live):
        refuse('EWAR implant container authority changed')
    scratch(t=len(saved))
    if character and (type(metadata) is not list or metadata != saved):
        refuse('EWAR character implant projection changed')
    for row, obj in zip(saved, live):
        check()
        if (type(row) is not dict or type(row.get('name')) is not str or
                type(row.get('slot')) is not int or not 1 <= row['slot'] <= 2**31 - 1 or
                type(row.get('active')) is not bool):
            refuse('Invalid EWAR implant authority')
        item = lookup(row['name'])
        if (item is None or not item.isImplant or item.ID != obj.item.ID or
                item.ID != obj.itemID or item.name != row['name'] or
                obj.item.name != row['name'] or obj.slot != row['slot'] or
                obj.active is not row['active']):
            refuse('EWAR implant authority changed')
        slot = item.getAttribute('implantness')
        if type(slot) not in (int, float) or not math.isfinite(slot) or slot != row['slot']:
            refuse('EWAR implant slot metadata changed')
        if character:
            identity = row.get('implant_id')
            if (type(row.get('item_id')) is not int or row['item_id'] != item.ID or
                    not 1 <= row['item_id'] <= 2**31 - 1 or type(identity) is not str or
                    len(identity) != 32 or any(c not in '0123456789abcdef' for c in identity)):
                refuse('EWAR character implant identity changed')


def admit_preparation(records, fits, revisions, engine_fits, rows, handles, mode, reserve, check, *, lookup=None):
    """Production mandatory callback, using all authoritative library records.

    R is every owned record. T counts every row in local/incoming containers,
    both implant collections (even dormant), boosters, edges and saved ability
    states. E is every referenced module/drone/fighter item's effect metadata,
    including ability metadata when
    a legacy row omits explicit ability state. Charge K=F+1 scratch incrementally
    before validation/helper dictionaries or live-record snapshots can allocate.
    """
    if type(records) is not dict or type(fits) is not dict or type(revisions) is not dict:
        refuse('Missing authoritative EWAR records')
    if not len(records) == len(fits) == len(revisions) == len(engine_fits):
        refuse('EWAR library authority changed')
    passes = add(len(rows), 1)
    reserve('container', mul(passes, 16))
    def scratch(r=0, t=0, e=0):
        reserve('container', mul(passes, add(mul(8, r), mul(8, t))))
        reserve('mapping_slot', mul(passes, add(add(mul(16, r), mul(16, t)), mul(8, e))))
        reserve('list_slot', mul(passes, add(add(mul(16, r), mul(8, t)), mul(8, e))))
        reserve('sort_slot', mul(passes, mul(4, t)))
    if lookup is None:
        import eos.db
        lookup = eos.db.getItem
    bounds = []  # <=8 selected rows, covered by fixed envelope reservation.
    module_effects, drone_effect, fighter_effect, _ = CONTRIBUTORS[mode]
    families = (('modules','modules'), ('drones','drones'), ('fighters','fighters'),
                ('projected_drones','projectedDrones'),
                ('projected_fighters','projectedFighters'), ('cargo','cargo'))
    for key, record in records.items():
        check(); scratch(r=1)
        if key not in fits or key not in revisions or type(record) is not dict:
            refuse('EWAR library authority changed')
        fit = fits[key]
        reserve('scan', len(engine_fits))
        if sum(value is fit for value in engine_fits) != 1: refuse('EWAR engine authority changed')
        spec = record['spec']; total = neut_modules = incoming_effects = 0
        for family, attribute in families:
            saved = spec.get(family, [])
            live = getattr(fit, attribute)
            if type(saved) is not list or len(saved) != len(live): refuse('EWAR container authority changed')
            for row, obj in zip(saved, live):
                check(); scratch(t=1)
                if family == 'modules' and 'name' not in row:
                    if not obj.isEmpty: refuse('EWAR module authority changed')
                    continue
                if obj.item.name != row.get('name'): refuse('EWAR item authority changed')
                if family == 'cargo': continue
                item = lookup(row['name'])
                if item is None or item.ID != obj.item.ID: refuse('Unknown EWAR item metadata')
                scratch(e=len(item.effects))
                abilities = row.get('abilities', ())
                scratch(t=len(abilities))
                _same_quantity(row, obj, family, item)
                if family == 'modules':
                    for effect in module_effects:
                        if effect in item.effects:
                            total = add(total, 1)
                            neut_modules = add(neut_modules, int(mode == 'neutStr'))
                elif family == 'drones' and drone_effect in item.effects:
                    total = add(total, count(row['active']))
                elif family == 'fighters' and fighter_effect:
                    for effect in item.effects.values():
                        if effect.name == fighter_effect: total = add(total, 1)
        from android_bridge.projected_drone_budget import implant_inputs, live_implant_inputs
        local, character, source = implant_inputs(record)
        modern = 'implant_source' in record
        live_local, live_character, live_source = live_implant_inputs(fit, legacy=not modern)
        if source != live_source: refuse('EWAR selected implant source changed')
        _same_implants(local, live_local, lookup, scratch, check)
        _same_implants(character, live_character, lookup, scratch, check,
                       metadata=getattr(fit, '_offline_character_implants', None) if modern else [],
                       character=True)
        saved = record.get('boosters', ())
        if len(saved) != len(fit.boosters): refuse('EWAR container authority changed')
        scratch(t=len(saved))
        environments = spec.get('environments', ())
        projectors = spec.get('projected_modules', ())
        if len(fit.projectedModules) != len(environments) + len(projectors):
            refuse('EWAR projector authority changed')
        for index, obj in enumerate(fit.projectedModules):
            check(); scratch(t=1)
            row = environments[index] if index < len(environments) else projectors[index-len(environments)]
            if obj.item.name != row.get('name'): refuse('EWAR projector authority changed')
            item = lookup(row['name'])
            if item is None or item.ID != obj.item.ID: refuse('Unknown EWAR projector metadata')
            scratch(e=len(item.effects))
            incoming_effects = add(incoming_effects, len(item.effects))
        for family, attribute, info_name in (('projections','projectedFitDict','getProjectionInfo'), ('commands','commandFitDict','getCommandInfo')):
            saved = record.get(family, ())
            live = getattr(fit, attribute)
            if len(saved) != len(live): refuse('EWAR edge authority changed')
            for edge in saved:
                check(); scratch(t=1)
                source = edge.get('source_id')
                if source not in records or source not in fits: refuse('Unknown EWAR source edge')
                source_fit = fits[source]
                if live.get(source_fit.ID) is not source_fit: refuse('EWAR source identity changed')
                info = getattr(source_fit, info_name)(fit.ID)
                if info.active is not edge.get('active'): refuse('EWAR source state changed')
                if family == 'projections':
                    count(edge.get('amount'))
                    if info.amount != edge['amount'] or info.projectionRange != edge.get('range_m'):
                        refuse('EWAR projection authority changed')
        for selected, handle in zip(rows, handles):
            if selected['fit_id'] == key:
                if fit is not handle or revisions[key] != selected['revision']: refuse('EWAR selected authority changed')
                bounds.append((key, total, neut_modules, add(len(spec['modules']), incoming_effects), len(spec['modules'])))
    if len(bounds) != len(rows): refuse('Missing EWAR selected authority')
    from android_bridge.projected_drone_budget import admit
    check()
    result = admit(records, extra_module=False, extra_edge=False, include_local_only=True)
    check()
    from android_bridge.projected_drone_budget import present
    if present(records):
        # Existing engine cap guard generates drains BEFORE its MAX_DRAINS check,
        # then normalizes/groups/resets, but never runs a capacitor simulation.
        # Each of the eight pinned addDrain handlers appends at most one drain.
        # Full admitted cold_units conservatively bounds linked quantity dispatch.
        cold = count(result['cold_units'])
        for _, _, _, direct, local_modules in bounds:
            drains = add(direct, cold)
            reserve('container', add(8, drains))
            reserve('tuple_value', mul(4, drains))
            reserve('list_slot', mul(12, drains))
            reserve('mapping_slot', mul(2, drains))
            reserve('repair_parameter_call', local_modules)
            reserve('schedule_constructor', mul(3, local_modules))
            reserve('schedule_children', mul(2, local_modules))
    # Return request order, not library order. This bounded <=8 list is included
    # in the fixed output bookkeeping; no all-library copy is made.
    return [(next(value[1:3] for value in bounds if value[0] == row['fit_id'])) for row in rows]
