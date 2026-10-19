"""Independent fitted mode/cargo/implant/booster inspection and reversal states.

The original EOS owns every mutation and calculation. Original desktop methods
own attributes, property getters, equipment columns and both affector trees.
No Android adapter is imported when producing these expectations.
"""
import argparse
import ast
from copy import deepcopy
import importlib.metadata
import gzip
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT, DEPENDENCIES,
    bootstrap, compare, digest_file, logical_database_digest, validate_source)


def contexts(fit):
    from tools.android_reference.inspector_attributes import contexts as existing
    rows = [row for row in existing(fit) if row[0] != 'base']
    if fit.mode is not None:
        rows.append(('mode', fit.mode, fit.mode.item, False))
    rows.extend(('implant', obj, obj.item, False) for obj in fit.implants)
    rows.extend(('booster', obj, obj.item, False) for obj in fit.boosters)
    items = {item.ID: item for _, _, item, _ in rows}
    return rows + [('base', None, item, False) for item in items.values()]


def roles(session, fit):
    from tools.android_reference.inspector_identities import original_roles
    result = original_roles(session, fit.ID)
    def rows(query):
        return [dict(row) for row in session.execute(query, {'fit_id': fit.ID})]
    result.update(
        cargo=rows('SELECT ID, fitID, itemID, amount FROM cargo WHERE fitID=:fit_id ORDER BY ID'),
        implants=rows('SELECT i.ID, i.itemID, i.active FROM implants i JOIN fitImplants f ON f.implantID=i.ID WHERE f.fitID=:fit_id ORDER BY i.ID'),
        boosters=rows('SELECT ID, fitID, itemID, active FROM boosters WHERE fitID=:fit_id ORDER BY ID'),
        booster_side_effects=rows('SELECT s.boosterID, s.effectID, s.active FROM boosterSideEffects s JOIN boosters b ON b.ID=s.boosterID WHERE b.fitID=:fit_id ORDER BY s.boosterID,s.effectID'),
        mode=rows('SELECT modeID FROM fits WHERE ID=:fit_id'))
    return result


def flat_affectors(stuff, item, fit, charge=False, source_positions=False):
    """Record even unused/unchanged original EOS afflictions without UI filtering."""
    from tools.android_reference.inspector_property_oracle import representation
    if stuff is None:
        return []
    values = stuff.chargeModifiedAttributes if charge else stuff.itemModifiedAttributes
    output = []
    members = [(kind, obj, member) for kind, obj, member, _ in contexts(fit) if obj is not None]
    for name in sorted(values.iterAfflictions()):
        for source_fit, entries in values.getAfflictions(name).items():
            for source, operator, stacking, before, after, used in entries:
                source_item = source.charge if source is stuff and getattr(source, 'charge', None) else getattr(source, 'item', None)
                matches = [(kind, member.ID) for kind, obj, member in members if obj is source and member is source_item]
                if len(matches) > 1:
                    raise ValueError('Ambiguous independent fitted affector role')
                role = None if not matches else dict(context=matches[0][0], item_id=matches[0][1])
                if role is not None and source_positions:
                    kind = role['context']
                    things = ([fit.ship] if kind == 'ship' else [fit.mode] if kind == 'mode' else
                              fit.modules if kind in ('module', 'charge') else
                              getattr(fit, dict(drone='drones', fighter='fighters', cargo='cargo',
                                               implant='implants', booster='boosters')[kind]))
                    positions = [index for index, obj in enumerate(things) if obj is source]
                    if len(positions) != 1:
                        raise ValueError('Ambiguous independent source position')
                    role['index'] = positions[0]
                output.append(dict(attribute=name,
                    changed=values[name] != values.getOriginal(name, 0), used=bool(used),
                    source_type=type(source).__name__, source_id=getattr(source, 'ID', None),
                    source_fit_id=source_fit.ID, source_fit_name=source_fit.name,
                    source_ship_id=source_fit.ship.item.ID,
                    item_id=None if source_item is None else source_item.ID,
                    item_name=None if source_item is None else source_item.name,
                    source_role=role,
                    projected=bool(getattr(source, 'projected', False)), operator=operator.name,
                    stacking=representation(stacking), before=before, after=after))
    return output


def validate_fixture(fixture):
    """Fail closed on omitted domains, lost reversals or fabricated restoration."""
    compare(SOURCE_COMMIT, fixture['sourceCommit'])
    compare('5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607', fixture['databaseLogicalSha256'])
    mode_inventory = json.loads((ROOT / 'tools/android_reference/fixtures/inspector-mode-identities.json').read_text(encoding='utf-8'))
    modes = [case for case in fixture['cases'] if case['family'] == 'mode']
    compare([row['name'] for row in mode_inventory['modeFamilies']], [case['spec']['ship'] for case in modes])
    for family, case in zip(mode_inventory['modeFamilies'], modes):
        choices = {target['item_id'] for state in case['states'] for target in state['targets'] if target['context'] == 'mode'}
        compare(set(family['choices']), choices)
        compare(6, len(case['states']))
    catalogue = fixture['boosterCatalogue']
    compare(311, len(catalogue))
    identities = [row['id'] for row in catalogue]
    if identities != sorted(set(identities)):
        raise ValueError('Incomplete or duplicate booster catalogue')
    shapes = {}
    for row in catalogue:
        signature = (row['slot'], tuple(row['side_effects']))
        shapes.setdefault(signature, row)
    compare(list(shapes.values()), fixture['boosterRepresentatives'])
    boosters = [case for case in fixture['cases'] if case['family'] == 'booster']
    compare([row['name'] for row in shapes.values()], [case['spec']['boosters'][0]['name'] for case in boosters])
    for row, case in zip(shapes.values(), boosters):
        effects = [state['action']['effect_id'] for state in case['states'] if state['action']['kind'] == 'set_booster_side_effect']
        compare(row['side_effects'], effects)
        compare(7 + 2 * len(effects), len(case['states']))
    compare(1, len([case for case in fixture['cases'] if case['family'] == 'cargo']))
    compare(1, len([case for case in fixture['cases'] if case['family'] == 'implant']))
    if any(case['family'] not in ('mode', 'cargo', 'implant', 'booster') for case in fixture['cases']):
        raise ValueError('Unexpected fitted context family')
    for case in fixture['cases']:
        states = case['states']
        compare(dict(kind='construction'), states[0]['action'])
        compare(dict(kind='initial'), states[1]['action'])
        initial = states[1]['targets']
        for state in states:
            replayed = state['replayed']
            compare(set(state) - {'replayed'}, set(replayed))
            compare(state['action'], replayed['action'])
            compare(state['module_inputs'], replayed['module_inputs'])
            compare(state['ignore_restrictions'], replayed['ignore_restrictions'])
            compare([(row['context'], row['item_id']) for row in state['targets']],
                    [(row['context'], row['item_id']) for row in replayed['targets']])
            for before, after in zip(state['targets'], replayed['targets']):
                compare(set(before), set(after))
                compare([row['contract']['name'] for row in before['properties']],
                        [row['contract']['name'] for row in after['properties']])
            if type(state['ignore_restrictions']) is not bool:
                raise ValueError('Invalid original restriction input')
            compare(False, state['ignore_restrictions'])
            compare(len(state['roles']['modules']), len(state['module_inputs']))
            for row in state['module_inputs']:
                compare({'empty_slot'}, set(row))
                if row['empty_slot'] not in ('LOW', 'MED', 'HIGH', 'RIG', 'SERVICE', 'SUBSYSTEM'):
                    raise ValueError('Invalid original vacant-slot input')
            if case['family'] != 'mode' or state['action']['kind'] != 'set_mode':
                compare([], state['module_inputs'])
            keys = [(target['context'], target['item_id']) for target in state['targets']]
            if len(keys) != len(set(keys)):
                raise ValueError('Duplicate context target')
            if state['action']['kind'].startswith('reverse'):
                compare([(target['context'], target['item_id']) for target in initial], keys)
                for before, after in zip(initial, state['targets']):
                    for field in ('attributes', 'equipment', 'affector_views'):
                        compare(before[field], after[field], case['spec']['name'] + '.' + state['action']['kind'] + '.' + field)
            if state['action']['kind'].startswith('remove'):
                if any(target['context'] == case['family'] and target['item_id'] == initial[1]['item_id'] for target in state['targets']):
                    raise ValueError('Removed fitted target survived')
        if case['family'] != 'mode':
            compare('reverse_remove', states[-1]['action']['kind'])
            removal_index = -3 if case['family'] == 'booster' else -2
            compare('remove_' + case['family'], states[removal_index]['action']['kind'])


def export(source, database):
    validate_source(source)
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    logical = logical_database_digest(database)
    compare('5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607', logical)
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FittingModuleState, FittingSlot, FitSystemSecurity, ImplantLocation
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.module import Module
    from eos.saveddata.mode import Mode
    from eos.saveddata.cargo import Cargo
    from eos.saveddata.implant import Implant
    from eos.saveddata.booster import Booster
    from tools.android_reference.inspector_attribute_oracle import load as attribute_load
    from tools.android_reference.inspector_property_oracle import load as property_load
    from tools.android_reference.inspector_equipment_oracle import load as equipment_load
    from tools.android_reference.inspector_affector_oracle import load as affector_load
    attrs = attribute_load(source)
    properties = property_load(source, app=attrs['app'])
    equipment = equipment_load(source)
    affectors = affector_load(source)
    session = eos.db.saveddata_session
    item = eos.db.getItem
    base = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text(encoding='utf-8'))
    base.pop('edit')
    base.update(modules=[], drones=[], cargo=[], fighters=[])
    cases = []
    mode_command = None

    def change_mode(fit, identity):
        nonlocal mode_command
        if mode_command is None:
            # Load only after the original first base-property reads, retaining
            # the independent cold Item cache expectation.
            from tools.android_reference.module_oracle import load
            from service.market import Market
            import wx
            from logbook import Logger
            service = load(source)['service']
            path = source / 'gui/fitCommands/calc/shipModeChange.py'
            definitions = [node for node in ast.parse(path.read_bytes(), filename=str(path)).body
                           if isinstance(node, ast.ClassDef) and node.name == 'CalcChangeShipModeCommand']
            compare(1, len(definitions))
            namespace = dict(wx=wx, pyfalog=Logger(__name__), Fit=type(service), Market=Market, Mode=Mode)
            exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), 'exec'), namespace)
            mode_command = namespace['CalcChangeShipModeCommand']
        if not mode_command(fit.ID, identity).Do():
            raise ValueError('Original mode command failed')
        session.flush(); fit.clear(); fit.calculateModifiedAttributes()
        fit.fill(); session.flush()

    def make(spec):
        fit = Fit(Ship(item(spec['ship'])), name=spec['name'])
        fit.character = Character('Headless synthetic skills', defaultLevel=spec['skill_level'])
        fit.damagePattern = DamagePattern(**spec['damage_pattern'])
        fit.factorReload = spec['factor_reload']
        fit.targetProfile = None
        fit.implantLocation = ImplantLocation.FIT
        fit.systemSecurity = FitSystemSecurity[spec['security']['system']]
        fit.pilotSecurity = spec['security']['pilot']
        if spec.get('mode') is not None:
            fit.mode = Mode(item(spec['mode']))
        for row in spec['modules']:
            if 'empty_slot' in row:
                fit.modules.appendIgnoreEmpty(Module.buildEmpty(FittingSlot[row['empty_slot']]))
                continue
            obj = Module(item(row['name']))
            obj.state = FittingModuleState[row['state']]
            if row.get('charge'):
                obj.charge = item(row['charge'])
            fit.modules.append(obj)
        for kind, model in (('cargo', Cargo), ('implants', Implant), ('boosters', Booster)):
            for row in spec[kind]:
                obj = model(item(row['name']))
                if kind == 'cargo':
                    obj.amount = row['amount']
                else:
                    obj.active = row['active']
                getattr(fit, kind).append(obj)
        session.add(fit)
        session.flush()
        return fit

    def state(fit, action, with_replay=True):
        session.flush()
        # Match the original service recalc: direct model setters alone do not
        # invalidate Fit's calculated flag. Every edit needs a fresh EOS pass.
        fit.clear()
        fit.calculateModifiedAttributes()
        if not fit.fits:
            raise ValueError('Invalid independent context fit: ' + fit.name)
        targets = []
        for kind, obj, member, charge in contexts(fit):
            # Preserve the adapter's query order; later property getters must
            # not supply metadata retroactively to an earlier affector result.
            target = dict(context=kind, item_id=member.ID,
                          attributes=attrs['observe'](obj, member, charge))
            target['affectors'] = flat_affectors(obj, member, fit, charge)
            target['affector_views'] = affectors(obj, member, fit)
            target['properties'] = properties(obj, member, fit)
            target['equipment'] = equipment(obj, fit)
            targets.append(target)
        if any(not module.isEmpty for module in fit.modules):
            raise ValueError('Unexpected fitted module in empty context reference')
        result = dict(action=action, roles=roles(session, fit), targets=targets,
                    module_inputs=[dict(empty_slot=FittingSlot(module.slot).name) for module in fit.modules],
                    ignore_restrictions=bool(fit.ignoreRestrictions))
        if with_replay:
            # B01/B02/B09 restore declarative inputs into fresh EOS objects.
            # Keep direct getters above AND independently observe that distinct
            # lifecycle: ORM update timestamps and first-pass effect registration
            # cannot be assumed identical after reconstruction.
            replay_spec = deepcopy(base)
            replay_spec.update(name=fit.name, ship=fit.ship.item.name,
                               modules=deepcopy(result['module_inputs']),
                               cargo=[dict(name=obj.item.name, amount=obj.amount) for obj in fit.cargo],
                               implants=[dict(name=obj.item.name, active=bool(obj.active)) for obj in fit.implants],
                               boosters=[dict(name=obj.item.name, active=bool(obj.active)) for obj in fit.boosters])
            if fit.mode is not None:
                replay_spec['mode'] = fit.mode.item.ID
            replay_fit = make(replay_spec)
            for before, after in zip(fit.boosters, replay_fit.boosters):
                flags = {effect.effect.ID: bool(effect.active) for effect in before.sideEffects}
                for effect in after.sideEffects:
                    effect.active = flags[effect.effect.ID]
            session.flush()
            replay_fit.clear(); replay_fit.calculateModifiedAttributes()
            result['replayed'] = state(replay_fit, action, with_replay=False)
            session.delete(replay_fit); session.flush()
        return result

    def initial_states(fit):
        # First-pass skill effects can precede a booster's fit registration.
        # Retain that cold construction result, then the original service's
        # recalculated baseline. Every state remains an independent expectation.
        return [state(fit, dict(kind='construction')), state(fit, dict(kind='initial'))]

    inventory = json.loads((ROOT / 'tools/android_reference/fixtures/inspector-mode-identities.json').read_text(encoding='utf-8'))
    compare(SOURCE_COMMIT, inventory['sourceCommit'])
    compare(logical, inventory['databaseLogicalSha256'])
    for family in inventory['modeFamilies']:
        spec = deepcopy(base)
        spec.update(name='Inspector modes: ' + family['name'], ship=family['name'])
        fit = make(spec)
        compare(family['choices'], [member.ID for member in fit.ship.modeItems])
        original = fit.mode
        spec['mode'] = original.item.ID
        states = initial_states(fit)
        for identity in family['choices']:
            if identity == original.item.ID:
                continue
            change_mode(fit, identity)
            states.append(state(fit, dict(kind='set_mode', item_id=identity)))
            # Atomic history restores the complete pre-edit declarative graph,
            # including the absence of physical vacancy records. Original EOS
            # still computes every restored field from that exact input state.
            compare(True, all(module.isEmpty for module in fit.modules))
            fit.modules.clear()
            fit.mode = original
            states.append(state(fit, dict(kind='reverse', item_id=original.item.ID)))
        cases.append(dict(family='mode', spec=spec, states=states))

    spec = deepcopy(base)
    spec.update(name='Inspector mixed cargo', cargo=[dict(name='Antimatter Charge M', amount=123), dict(name='Dual 150mm Railgun II', amount=2)])
    fit = make(spec)
    obj = fit.cargo[0]
    states = initial_states(fit)
    obj.amount = 987
    states.append(state(fit, dict(kind='set_cargo_amount', index=0, amount=987)))
    obj.amount = 123
    states.append(state(fit, dict(kind='reverse', amount=123)))
    fit.cargo.remove(obj)
    states.append(state(fit, dict(kind='remove_cargo', index=0)))
    restored = Cargo(obj.item)
    restored.amount = 123
    fit.cargo.insert(0, restored)
    states.append(state(fit, dict(kind='reverse_remove')))
    cases.append(dict(family='cargo', spec=spec, states=states))

    spec = deepcopy(base)
    spec.update(name='Inspector fit-local implants', implants=[dict(name="Eifyr and Co. 'Rogue' Navigation NN-601", active=True)])
    fit = make(spec)
    obj = fit.implants[0]
    states = initial_states(fit)
    obj.active = False
    states.append(state(fit, dict(kind='set_implant_active', slot=obj.slot, active=False)))
    obj.active = True
    states.append(state(fit, dict(kind='reverse', active=True)))
    fit.implants.remove(obj)
    states.append(state(fit, dict(kind='remove_implant', slot=obj.slot)))
    restored = Implant(obj.item)
    restored.active = True
    fit.implants.append(restored)
    states.append(state(fit, dict(kind='reverse_remove')))
    cases.append(dict(family='implant', spec=spec, states=states))

    # Existing probes cover all 311 published booster duration paths. Fitted
    # states additionally cover every distinct original slot/side-effect shape,
    # selected deterministically from the entire published catalogue.
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        published = db.execute("SELECT t.typeID,t.typeName FROM invtypes t JOIN invgroups g ON g.groupID=t.groupID WHERE g.name='Booster' AND t.published=1 ORDER BY t.typeID").fetchall()
    catalogue, selected = [], {}
    for identity, name in published:
        obj = Booster(item(identity))
        signature = (obj.slot, tuple(sorted(effect.effect.ID for effect in obj.sideEffects)))
        row = dict(id=identity, name=name, slot=signature[0], side_effects=list(signature[1]))
        catalogue.append(row)
        selected.setdefault(signature, row)
    for row in selected.values():
        spec = deepcopy(base)
        spec.update(name='Inspector booster: ' + row['name'], boosters=[dict(name=row['name'], active=True)])
        fit = make(spec)
        obj = fit.boosters[0]
        states = initial_states(fit)
        obj.active = False
        states.append(state(fit, dict(kind='set_booster_active', index=0, active=False)))
        obj.active = True
        states.append(state(fit, dict(kind='reverse', active=True)))
        # The native history boundary reconstructs every object. Continue the
        # next direct edit from that original-EOS reconstructed baseline too;
        # a side-effect-only edit must not inherit an earlier active-toggle's
        # transient ORM update timestamp.
        def restored_booster():
            restored_fit = make(spec)
            for _ in range(2):
                restored_fit.clear(); restored_fit.calculateModifiedAttributes()
            session.flush()
            return restored_fit, restored_fit.boosters[0]
        fit, obj = restored_booster()
        for effect_id in row['side_effects']:
            effect = next(effect for effect in obj.sideEffects if effect.effect.ID == effect_id)
            effect.active = True
            states.append(state(fit, dict(kind='set_booster_side_effect', index=0, effect_id=effect.effect.ID, active=True)))
            effect.active = False
            states.append(state(fit, dict(kind='reverse_side_effect', effect_id=effect.effect.ID, active=False)))
            fit, obj = restored_booster()
        fit.boosters.remove(obj)
        states.append(state(fit, dict(kind='remove_booster', index=0)))
        restored = Booster(obj.item)
        restored.active = True
        fit.boosters.append(restored)
        states.append(state(fit, dict(kind='recreated')))
        states.append(state(fit, dict(kind='reverse_remove')))
        cases.append(dict(family='booster', spec=spec, states=states))

    if any(name.startswith('android_bridge') for name in sys.modules):
        raise ValueError('Android implementation imported by independent context exporter')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source):
                raise ValueError('Reference imported outside pinned source: ' + name)
    files = ('eos/saveddata/fit.py', 'eos/saveddata/ship.py', 'eos/saveddata/mode.py',
             'eos/saveddata/cargo.py', 'eos/saveddata/implant.py', 'eos/saveddata/booster.py',
             'eos/saveddata/boosterSideEffect.py', 'eos/modifiedAttributeDict.py',
             'gui/builtinItemStatsViews/itemAttributes.py', 'gui/builtinItemStatsViews/itemProperties.py',
             'gui/builtinItemStatsViews/itemAffectedBy.py',
             'gui/fitCommands/calc/shipModeChange.py', 'service/fit.py',
             'eos/saveddata/module.py', 'eos/db/saveddata/cargo.py',
             'eos/db/saveddata/booster.py', 'eos/db/saveddata/implant.py')
    result = dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical,
                eos_settings=dict(configuration.settings), sourceFiles={name: digest_file(source / name) for name in files},
                boosterCatalogue=catalogue, boosterRepresentatives=list(selected.values()), cases=cases)
    validate_fixture(result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export',))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.source.resolve(), args.database.resolve())
    content = (json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    args.fixture.write_bytes(gzip.compress(content, mtime=0) if args.fixture.suffix == '.gz' else content)
    print('Independent fitted contexts:', len(result['cases']), 'cases;', sum(len(case['states']) for case in result['cases']), 'states;', sum(len(state['targets']) for case in result['cases'] for state in case['states']), 'targets')
