"""Read-only EFT text projection, following pinned service/port/eft.py.

EFT is lossy interchange, never a fit backup. Unsupported mutation serialization
fails explicitly when requested; intentional exclusions are diagnosed.
Copyright (C) Pyfa contributors. GPL-3.0-or-later.
"""
from .profiles import require

OPTIONS = {'loaded_charges', 'cargo', 'implants', 'boosters', 'mutations'}
DRONE_ORDER = ('Light Scout Drones', 'Medium Scout Drones', 'Heavy Attack Drones',
               'Sentry Drones', 'Combat Utility Drones', 'Electronic Warfare Drones',
               'Logistic Drones', 'Mining Drones', 'Salvage Drones')


def render_eft(fit, options):
    from eos.const import FittingModuleState, FittingSlot
    from android_bridge.market_policy import MarketPolicy
    market = MarketPolicy()
    require(type(options) is dict and set(options) == OPTIONS and
            all(type(v) is bool for v in options.values()), 'options', 'Invalid EFT inclusion choices')
    diagnostics = []
    def warn(code, message):
        if not any(d['code'] == code for d in diagnostics):
            diagnostics.append(dict(code=code, message=message))
    def name(value):
        require(type(value) is str and 0 < len(value) <= 512 and
                not any(c in value for c in '\r\n,[]/\u2028\u2029') and
                value == value.strip() and
                not any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in value),
                'unrepresentable_name', 'A fitting or item name cannot be represented safely in EFT')
        return value
    def quantity(value):
        require(type(value) is int and 1 <= value <= 2**31-1, 'quantity', 'Invalid EFT stack quantity')
        return value
    def item_name(obj):
        if getattr(obj, 'isMutated', False):
            require(not options['mutations'], 'unsupported_mutations',
                    'Mutation-detail export is not implemented. Disable mutated attributes only to explicitly export base items.')
            warn('mutations_excluded', 'Mutated attributes are excluded; exported items use their base types.')
            return name(obj.baseItem.typeName)
        require(not getattr(obj.item, 'isAbyssal', False), 'unsupported_mutations',
                'An abyssal item without its mutation record cannot be exported safely')
        return name(obj.item.typeName)
    require(fit.ship is not None and fit.ship.item is not None, 'missing_hull', 'Select a fit with a hull')
    header = '[{}, {}]'.format(name(fit.ship.item.typeName), name(fit.name))
    warn('eft_format_losses', 'EFT is not a backup: profiles/skills, notes, linked fits, environments, damage/target/security settings, tactical mode, restriction overrides and history are not preserved.')
    if any(module.item.isModule for module in fit.projectedModules):
        warn('projected_modules_lost', 'EFT does not preserve individual projected modules, their charges, ranges, states or spool overrides.')
    if fit.projectedDrones:
        warn('projected_drones_lost', 'EFT does not preserve incoming projected drone stacks, quantities, active states or ranges.')
    if fit.projectedFighters:
        warn('projected_fighters_lost', 'EFT does not preserve incoming fighter squadrons, quantities, active or ability states, or ranges.')
    slots = (FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH, FittingSlot.RIG,
             FittingSlot.SUBSYSTEM, FittingSlot.SERVICE)
    racks = {slot: [] for slot in slots}
    for module in fit.modules:
        require(module.slot in slots, 'unsupported_slot', 'Module slot cannot be represented safely')
        if module.item is None:
            line = '[Empty {} slot]'.format(FittingSlot(module.slot).name.capitalize())
        else:
            line = item_name(module)
            if module.rahPatternOverride is not None:
                warn('module_rah_loss', 'EFT does not preserve per-module reactive armor patterns; imported modules inherit the fit pattern.')
            if module.spoolType is not None or module.spoolAmount is not None:
                warn('module_spool_loss', 'EFT does not preserve per-module spool overrides; imported modules use the default spool setting.')
            if module.charge is not None:
                if options['loaded_charges']: line += ', ' + name(module.charge.typeName)
                else: warn('charges_excluded', 'Loaded charges are excluded by your export choice.')
            if module.state == FittingModuleState.OFFLINE: line += ' /offline'
            else: warn('module_state_loss', 'EFT distinguishes offline modules only; online/active/overheated states may change on import.')
        if module.slot == FittingSlot.SUBSYSTEM:
            warn('import_unsupported_additions', 'The current Android importer cannot restore subsystem positions, fighters, implants or boosters from this export.')
        racks[module.slot].append(line)
    sections = ['\n\n'.join('\n'.join(racks[s]) for s in slots if racks[s])]
    sections = [s for s in sections if s]
    def drone_key(drone):
        item = drone.baseItem if getattr(drone, 'isMutated', False) else drone.item
        group = market.getMarketGroupByItem(item)
        group_name = getattr(group, 'marketGroupName', None)
        require(group_name in DRONE_ORDER, 'unsupported_drone_group', 'Drone market group is not supported by desktop EFT ordering')
        return (DRONE_ORDER.index(group_name), bool(getattr(drone, 'isMutated', False)), drone.fullName)
    drones = ['{} x{}'.format(item_name(d), quantity(d.amount)) for d in sorted(fit.drones, key=drone_key)]
    fighter_order = ('Light Fighter', 'Structure Light Fighter', 'Heavy Fighter', 'Structure Heavy Fighter', 'Support Fighter', 'Structure Support Fighter')
    def fighter_key(fighter):
        group = fighter.item.group.name
        require(group in fighter_order, 'unsupported_fighter_group', 'Unsupported fighter EFT group')
        return fighter_order.index(group), fighter.item.typeName
    fighters = ['{} x{}'.format(item_name(f), quantity(f.amount)) for f in sorted(fit.fighters, key=fighter_key)]
    if drones or fighters: warn('active_counts_lost', 'Drone active counts and fighter abilities/states are not retained by EFT.')
    if fighters: warn('import_unsupported_additions', 'The current Android importer cannot restore subsystems, fighters, implants or boosters from this export.')
    minions = ['\n'.join(x) for x in (drones, fighters) if x]
    if minions: sections.append('\n\n'.join(minions))
    additions = []
    for key in ('implants', 'boosters'):
        values = list(getattr(fit, key))
        if values and not options[key]: warn(key + '_excluded', key.capitalize() + ' are excluded by your export choice.')
        if values and options[key]:
            additions.append('\n'.join(item_name(x) for x in sorted(values, key=lambda x: x.slot or 0)))
            warn('import_unsupported_additions', 'The current Android importer cannot restore subsystems, fighters, implants or boosters from this export.')
            warn('addition_active_states_lost', 'Implant and booster active states are not retained by EFT.')
            if key == 'boosters': warn('booster_effects_lost', 'Booster side-effect selections are not retained by EFT.')
    if additions: sections.append('\n\n'.join(additions))
    cargo = list(fit.cargo)
    if cargo and options['cargo']:
        if all(c.item.group.category.name == 'Drone' for c in cargo):
            warn('cargo_drone_reclassification', 'An all-drone cargo section is interpreted as drone-bay contents when EFT is imported.')
        if any(c.item.group.category.name in ('Fighter', 'Subsystem', 'Implant') for c in cargo):
            warn('cargo_import_unsupported', 'Some cargo types cannot currently be restored by the Android EFT importer.')
        sections.append('\n'.join('{} x{}'.format(item_name(c), quantity(c.amount)) for c in sorted(cargo, key=lambda c: (c.item.group.category.name, c.item.group.name, c.item.typeName))))
    elif cargo: warn('cargo_excluded', 'Cargo is excluded by your export choice.')
    text = header + '\n\n' + '\n\n\n'.join(sections)
    require(len(text.encode('utf-8')) <= 1024*1024 and len(text.splitlines()) <= 10000 and
            all(len(line) <= 1024 for line in text.splitlines()), 'limit', 'Export exceeds supported EFT text limits')
    filename = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in fit.name).strip(' .')[:80] or 'fit'
    return dict(text=text, filename=filename + '.txt', diagnostics=diagnostics)
