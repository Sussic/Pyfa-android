"""Strict source-text to bridge-spec preparation, without persisting a fit.

Section interpretation follows pinned service/port/eft.py. The bounded importer
refuses unsupported/ambiguous input instead of adopting desktop's silent drops.
EOS owns module slots and charge/state validity; the frozen bridge owns public
catalogue and default module-state policies. CPU/PG are not import restrictions.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see upstream COPYING.
"""
from collections import OrderedDict
import importlib.util
from pathlib import Path
import re


from . import eft_preview as _preview
EosResolver = _preview.EosResolver
MAX_QUANTITY = _preview.MAX_QUANTITY
# A resource bound, not a replacement for EOS hull/rack fitting restrictions.
MAX_MODULE_ROWS = 256
RACK_ORDER = ('LOW', 'MED', 'HIGH', 'RIG', 'SERVICE')
_CFG_FIELD = re.compile(r'^(?:(?:Drones|Implant|Booster)_(?:Active|Inactive)|Cargohold|Description)=')
_CFG_HEADER = re.compile(r'^\[[^\[\],]+\]$')
_UNSUPPORTED = {'Fighter': 'unsupported_fighter', 'Subsystem': 'unsupported_subsystem',
                'Implant': 'unsupported_implant', 'Booster': 'unsupported_booster'}


def _diagnostic(document, line, code, message):
    return dict(document=document['document'], label=document['label'], line=line,
                code=code, message=message)


def _base_spec(header):
    # Explicit bridge scenario defaults. The graph replaces the compatibility
    # skill level with its validated chosen profile before a candidate is used.
    return dict(name=header['name'], ship=header['item']['name'], skill_level=5,
                factor_reload=False,
                damage_pattern=dict(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25),
                security=dict(system='HISEC', pilot=0.0), target_profile=None,
                modules=[], drones=[], cargo=[], implants=[], boosters=[],
                projections=[], commands=[], environments=[], ignore_restrictions=False)


class _Catalogue:
    def __init__(self):
        import eos.db
        from android_bridge.market_policy import MarketPolicy
        self.lookup = eos.db.getItem
        self.policy = MarketPolicy()
        self.cache = {}

    def item(self, metadata):
        identity = metadata['id']
        if identity not in self.cache:
            value = self.lookup(identity)
            if (value is None or value.ID != identity or value.typeName != metadata['name']
                    or value.category.name != metadata['category']):
                raise ValueError('Catalogue identity changed during preparation')
            self.cache[identity] = value
        return self.cache[identity]


def _public_item(metadata, document, line, catalog, diagnostics):
    if metadata is None:
        return None  # The regenerated preview already located this lookup error.
    try:
        item = catalog.item(metadata)
        if item.isAbyssal:
            diagnostics.append(_diagnostic(document, line, 'unsupported_mutation',
                                           'Mutated items require the mutation import path'))
            return None
        if not catalog.policy.getPublicityByItem(item):
            diagnostics.append(_diagnostic(document, line, 'unpublished_item',
                                           'Item is unavailable under the offline catalogue policy'))
            return None
        return item
    except Exception:
        diagnostics.append(_diagnostic(document, line, 'catalog_unavailable',
                                       'Offline item validation failed'))
        return None


def _module(item, charge, token, document, diagnostics):
    from android_bridge.fitting import ONLINE_EFFECTS, SLOTS
    from eos.const import FittingModuleState, FittingSlot
    from eos.saveddata.module import Module
    try:
        module = Module(item)
        if module.slot not in SLOTS.values():
            diagnostics.append(_diagnostic(document, token['line'], 'unsupported_module',
                                           'This module needs a different fitting editor'))
            return None
        if token['offline']:
            if not module.isValidState(FittingModuleState.OFFLINE):
                diagnostics.append(_diagnostic(document, token['line'], 'invalid_state',
                                               'This module cannot be imported offline'))
                return None
            module.state = FittingModuleState.OFFLINE
        else:
            limit = (FittingModuleState.ONLINE if ONLINE_EFFECTS.intersection(item.effects)
                     else FittingModuleState.ACTIVE)
            if module.isValidState(limit):
                module.state = limit
        row = dict(name=item.typeName, state=FittingModuleState(module.state).name)
        if charge is not None:
            if charge.category.name != 'Charge':
                return None  # Preview already reports charge_category.
            if not module.isValidCharge(charge):
                diagnostics.append(_diagnostic(document, token['line'], 'invalid_charge',
                                               'Loaded charge is incompatible with this module'))
                return None
            row['charge'] = charge.typeName
        # Never call fits(), calculate, create_fit, or mutate engine bookkeeping.
        return FittingSlot(module.slot).name, row
    except ValueError:
        diagnostics.append(_diagnostic(document, token['line'], 'unsupported_module',
                                       'Item cannot be used as an ordinary fitted module'))
    except Exception:
        diagnostics.append(_diagnostic(document, token['line'], 'catalog_unavailable',
                                       'Offline module validation failed'))
    return None


def _add_stack(stacks, item, token, document, diagnostics, *, drone=False):
    previous = stacks.get(item.ID)
    amount = token['amount'] + (previous['amount'] if previous else 0)
    if amount > MAX_QUANTITY:
        diagnostics.append(_diagnostic(document, token['line'], 'quantity',
                                       'Combined stack quantity exceeds the positive 32-bit limit'))
        return
    if previous is not None:
        previous['amount'] = amount
    else:
        row = dict(name=item.typeName, amount=amount)
        if drone:
            # Pinned AbstractFit.addDrone changes amount only. Drone's constructor
            # initializes amountActive to zero, including merged ordinary stacks.
            row['active'] = 0
        stacks[item.ID] = row


def _cfg_diagnostics(source, document, diagnostics):
    lines = source['text'].removeprefix('\ufeff').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    first = True
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if (_CFG_FIELD.match(line) or first and _CFG_HEADER.fullmatch(line)
                and not _preview.EMPTY.fullmatch(line) and not re.fullmatch(r'\[\d+\]', line)):
            diagnostics.append(_diagnostic(document, number, 'unsupported_cfg',
                                           'EFT configuration-store input is not supported by text import'))
        first = False


def _validate_fitting(spec, module_lines, hull_item, catalog, document, diagnostics):
    """Locate structural EOS refusals using a wholly detached candidate.

    This mirrors the pre-add portion of HeadlessEngine.create_fit. A private
    zero-skill character supplies EOS's required calculation context; skills are
    never checked as fitting requirements. The actual selected profile remains
    authoritative in atomic graph staging. No resource-budget gates are added.
    """
    if not spec['modules']:
        return
    import eos.db
    from android_bridge.fitting import VACANT_SLOTS
    from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship

    # Do not let an incidental EOS read flush unrelated pending user objects.
    # Every relationship below links newly constructed, transient objects only.
    with eos.db.saveddata_session.no_autoflush:
        hull = Citadel(hull_item) if hull_item.category.name == 'Structure' else Ship(hull_item)
        fit = Fit(hull, name=spec['name'])
        fit.character = Character('Detached EFT structural validation', defaultLevel=0)
        fit.damagePattern = DamagePattern(**spec['damage_pattern'])
        fit.targetProfile = None
        fit.factorReload = spec['factor_reload']
        fit.implantLocation = ImplantLocation.FIT
        fit.systemSecurity = FitSystemSecurity[spec['security']['system']]
        fit.pilotSecurity = spec['security']['pilot']
        fit.ignoreRestrictions = False
        by_name = {item.typeName: item for item in catalog.cache.values()}
        modules = []
        for row in spec['modules']:
            if 'empty_slot' in row:
                module = Module.buildEmpty(VACANT_SLOTS[row['empty_slot']])
            else:
                module = Module(by_name[row['name']])
                module.state = FittingModuleState[row['state']]
                if row.get('charge') is not None:
                    module.charge = by_name[row['charge']]
            module.owner = fit
            fit.modules.appendIgnoreEmpty(module)
            modules.append(module)
        fit.calculateModifiedAttributes()
        rack_positions = {}
        for module, line in zip(modules, module_lines):
            position = rack_positions.get(module.slot, 0)
            rack_positions[module.slot] = position + 1
            # EOS ignores vacancies in getSlotsFree. Preserve the source's
            # explicit interior positions while refusing impossible rack size.
            outside_rack = position >= fit.getNumSlots(module.slot)
            legal = module.isEmpty or module.fits(fit)
            if outside_rack or not legal:
                diagnostics.append(_diagnostic(document, line, 'fitting_restriction',
                                               'Module or position exceeds a hull, slot, hardpoint, rig-size or group restriction'))


def _prepare_document(document, source, catalog, diagnostics):
    _cfg_diagnostics(source, document, diagnostics)
    header = document['header']
    hull = None if header is None else _public_item(header.get('item'), document, header['line'], catalog, diagnostics)
    spec = _base_spec(header) if hull is not None and hull.category.name in ('Ship', 'Structure') else None
    sections = OrderedDict()
    prepared = {}
    items = {}
    module_count = sum(t['kind'] == 'empty' or t['kind'] == 'item'
                       and (t.get('item') or {}).get('category') in ('Module', 'Structure Module')
                       for t in document['tokens'])
    too_many = module_count > MAX_MODULE_ROWS
    if too_many:
        diagnostics.append(_diagnostic(document, header['line'] if header else 0, 'limit',
                                       'Fitting exceeds the module-row preparation limit'))
    for token in document['tokens']:
        sections.setdefault(token['section'], []).append(token)
        kind, line = token['kind'], token['line']
        if kind == 'empty':
            if token['slot'] not in RACK_ORDER:
                diagnostics.append(_diagnostic(document, line, 'unsupported_subsystem',
                                               'Subsystem positions require the subsystem import path'))
            elif not too_many:
                prepared[line] = token['slot'], dict(empty_slot=token['slot'])
            continue
        if kind not in ('item', 'quantity'):
            continue
        item = _public_item(token.get('item'), document, line, catalog, diagnostics)
        charge = (_public_item(token.get('charge_item'), document, line, catalog, diagnostics)
                  if kind == 'item' and token['charge'] else None)
        if item is None:
            continue
        category = item.category.name
        if category in _UNSUPPORTED:
            code = ('unsupported_booster' if category == 'Implant' and 'boosterness' in item.attributes
                    else _UNSUPPORTED[category])
            diagnostics.append(_diagnostic(document, line, code,
                                           'This item category requires a separate import path'))
            continue
        if kind == 'quantity':
            # Upstream MultiItemSpec is cargo except in a homogeneous drone/fighter
            # bay. A module xN is a cargo stack and is never expanded into modules.
            items[line] = item
        elif category not in ('Module', 'Structure Module'):
            diagnostics.append(_diagnostic(document, line, 'unsupported_item',
                                           'Only fitted modules support this line form; additions need quantities'))
        elif not too_many:
            # A missing charge must not turn into an unloaded imported module.
            if token['charge'] and charge is None:
                continue
            value = _module(item, charge, token, document, diagnostics)
            if value is not None:
                prepared[line] = value
    racks = {slot: [] for slot in RACK_ORDER}
    drones, cargo = OrderedDict(), OrderedDict()
    for tokens in sections.values():
        kinds = {token['kind'] for token in tokens}
        if kinds == {'empty'}:
            # Desktop _clearTail drops an entirely empty rack. Explicit matching
            # vacancy labels are safe; mixed racks remain ambiguous and rejected.
            slots = {t['slot'] for t in tokens}
            if len(slots) != 1:
                diagnostics.append(_diagnostic(document, tokens[0]['line'], 'ambiguous_section',
                                               'An empty-only section must identify one module rack'))
            continue
        if kinds <= {'item', 'empty'}:
            # Pinned importEft applies _clearTail to each section before rack
            # assembly. A trailing vacancy must not push a later section's
            # module to a different rack position.
            while tokens and tokens[-1]['kind'] == 'empty':
                tokens = tokens[:-1]
            occupied_slots = {prepared[t['line']][0] for t in tokens
                              if t['kind'] == 'item' and t['line'] in prepared}
            for token in tokens:
                value = prepared.get(token['line'])
                if value is None:
                    continue
                slot, row = value
                if token['kind'] == 'empty' and occupied_slots and occupied_slots != {slot}:
                    diagnostics.append(_diagnostic(document, token['line'], 'ambiguous_section',
                                                   'Empty positions must belong to the single module rack in this section'))
                    continue
                racks[slot].append((row, token['line']))
        elif kinds == {'quantity'}:
            # Missing/unsupported entries are already errors. Do not guess which
            # bay a partially resolvable section was intended to populate.
            if not all(t['line'] in items for t in tokens):
                continue
            is_drone_bay = all(items[t['line']].category.name == 'Drone' for t in tokens)
            target = drones if is_drone_bay else cargo
            for token in tokens:
                _add_stack(target, items[token['line']], token, document, diagnostics, drone=is_drone_bay)
        elif kinds - {'invalid'}:
            diagnostics.append(_diagnostic(document, tokens[0]['line'], 'ambiguous_section',
                                           'Separate fitted-module and quantity-addition sections with a blank line'))
    if spec is not None:
        located_modules = [value for slot in RACK_ORDER for value in racks[slot]]
        spec['modules'] = [row for row, line in located_modules]
        spec['drones'], spec['cargo'] = list(drones.values()), list(cargo.values())
        _validate_fitting(spec, [line for row, line in located_modules], hull, catalog, document, diagnostics)
    return spec


def prepare_documents(documents, engine):
    """Regenerate syntax/lookup from original text and prepare an all-or-none batch.

    Return ``ok, specs, diagnostics, documents``. Every diagnostic is located by
    zero-based document index/label and one-based line (0 for a whole request).
    ``specs`` is empty on *any* refusal; ``documents`` retains the fresh preview.
    No caller-supplied preview JSON or stored Fit instance is used. Structural
    validation uses detached EOS objects, without storage/session transactions.
    """
    try:
        engine._check_thread()
    except Exception:
        return dict(ok=False, specs=[], documents=[], diagnostics=[dict(document=None, label=None, line=0,
                    code='catalog_unavailable', message='Use the owning initialized EOS worker')])
    try:
        result = _preview.preview(dict(version=1, operation='preview_eft', documents=documents), EosResolver())
    except _preview.PreviewError as error:
        return dict(ok=False, specs=[], documents=[], diagnostics=[dict(document=None, label=None, line=0,
                    code=error.code, message=str(error))])
    diagnostics = list(result['diagnostics'])
    try:
        catalog = _Catalogue()
    except Exception:
        diagnostics.append(dict(document=None, label=None, line=0, code='catalog_unavailable',
                                message='Offline catalogue policy is unavailable'))
        return dict(ok=False, specs=[], documents=result['documents'], diagnostics=diagnostics)
    specs = []
    for document, source in zip(result['documents'], documents):
        try:
            specs.append(_prepare_document(document, source, catalog, diagnostics))
        except Exception:
            # A catalogue/engine exception in one document must not conceal
            # independently discoverable diagnostics in the remaining documents.
            diagnostics.append(_diagnostic(document, 0, 'catalog_unavailable',
                                           'Offline fitting preparation failed'))
            specs.append(None)
    # Stable source order is useful for highlighting all refusals in one preview.
    diagnostics.sort(key=lambda d: (-1 if d['document'] is None else d['document'], d['line']))
    return dict(ok=not diagnostics, specs=specs if not diagnostics else [],
                diagnostics=diagnostics, documents=result['documents'])
