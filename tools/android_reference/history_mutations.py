"""B09.2 original-command reversal matrix, independently repeated in fresh processes."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare,
    digest_file, logical_database_digest, snapshot, validate_source)


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    import wx
    from eos.const import FitSystemSecurity, FittingModuleState, FittingSlot, ImplantLocation
    from eos.saveddata.cargo import Cargo
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.drone import Drone
    from eos.saveddata.fit import Fit
    from eos.saveddata.implant import Implant
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.mutation_history_oracle import load
    oracle = load(source)
    service, commands, namespace = oracle['service'], oracle['mutation_commands'], oracle['mutation_namespace']
    market = Market.getInstance()
    base = deepcopy(json.loads((ROOT / 'tools/android_reference/fixtures/history.json').read_text())['cases'][0]['spec'])
    base.update(modules=[], drones=[], implants=[], cargo=[])
    item = lambda name: eos.db.getItem(name)
    iid = lambda name: item(name).ID

    def make_fit(spec):
        fit = Fit(Ship(item(spec['ship'])), name=spec['name'])
        fit.character = Character('Independent mutation all V', defaultLevel=spec['skill_level'])
        fit.damagePattern = DamagePattern(**spec['damage_pattern'])
        fit.factorReload, fit.targetProfile, fit.implantLocation = spec['factor_reload'], None, ImplantLocation.FIT
        fit.systemSecurity = FitSystemSecurity[spec['security']['system']]
        fit.pilotSecurity = spec['security']['pilot']
        fit.ignoreRestrictions = spec.get('ignore_restrictions', False)
        fit.notes = spec.get('notes', '')
        for row in spec['modules']:
            if 'empty_slot' in row: continue
            fit.modules.append(oracle['ModuleInfo'](iid(row['name']), state=FittingModuleState[row['state']],
                chargeID=iid(row['charge']) if row.get('charge') else None).toModule())
        for row in spec['drones']:
            drone = Drone(item(row['name'])); drone.amount, drone.amountActive = row['amount'], row['active']
            fit.drones.append(drone)
        for row in spec['implants']:
            implant = Implant(item(row['name'])); implant.active = row['active']; fit.implants.append(implant)
        for row in spec.get('cargo', []):
            cargo = Cargo(item(row['name'])); cargo.amount = row['amount']; fit.cargo.append(cargo)
        eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush()
        service.getFit(fit.ID); service.fill(fit.ID); service.recalc(fit.ID)
        return fit

    def stats(fit):
        service.recalc(fit.ID)
        result = snapshot(fit)
        result['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        return result

    def observe(fit, linked=None):
        result = {'name': fit.name, 'notes': fit.notes or '', 'stats': stats(fit),
            'mode': fit.mode.item.ID if fit.mode else None,
            'modules': [dict(index=i, name=m.item.name, state=FittingModuleState(m.state).name,
                charge=m.charge.name if m.charge else None) for i, m in enumerate(fit.modules) if not m.isEmpty],
            'drones': [dict(name=d.item.name, amount=d.amount, active=d.amountActive) for d in fit.drones],
            'implants': [dict(name=i.item.name, slot=i.slot, active=i.active) for i in fit.implants],
            # Original cargoView displays this categorical/name order; Undo may
            # append restored EOS cargo objects in a different internal order.
            'cargo': [dict(name=c.item.name, amount=c.amount) for c in sorted(fit.cargo,
                key=lambda c: (c.item.group.category.name, c.item.group.name, c.item.name))],
            'skill_override': fit.character.getSkill(item('Gunnery')).activeLevel,
            'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules']),
            'projections': [], 'commands': [], 'linked_stats': stats(linked) if linked is not None else None}
        for source_fit in fit.projectedFitDict.values():
            edge = source_fit.getProjectionInfo(fit.ID)
            result['projections'].append(dict(source_name=source_fit.name, range_m=edge.projectionRange,
                active=edge.active, amount=edge.amount))
        for source_fit in fit.commandFitDict.values():
            result['commands'].append(dict(source_name=source_fit.name, active=source_fit.getCommandInfo(fit.ID).active))
        return result

    def restored_values(before, after):
        # Original EOS can render an integral statistic as 0.0 before a command
        # and 0 after Undo. Retain both raw kinds in the fixture; compare values
        # with the established statistic tolerances, all inputs/units exactly.
        compare(before.keys(), after.keys())
        for field in before:
            if field == 'recent': continue
            if field in ('stats', 'linked_stats') and before[field] is not None:
                compare(before[field].keys(), after[field].keys())
                for key, row in before[field].items():
                    other = after[field][key]
                    compare(row['unit'], other['unit'])
                    left, right = row['value'], other['value']
                    if key in ('gun_optimal', 'gun_falloff') and (left is None or right is None):
                        assert (right if left is None else left) in (None, 0, 1), (field, key, left, right)
                    elif type(left) in (int, float) and type(right) in (int, float):
                        assert math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9), (field, key, left, right)
                    else: compare(left, right, path=field + '.' + key)
            else: compare(before[field], after[field])

    class Group(wx.Command):
        """One mobile action delegates to the original commands in exact order."""
        def __init__(self, parts):
            wx.Command.__init__(self, True, 'Grouped original input action')
            self.parts = parts
        def Do(self): return all(command.Do() for command in self.parts)
        def Undo(self): return all(command.Undo() for command in reversed(self.parts))

    # Each definition names the existing Android operation, its inputs and an
    # original constructor. No Android adapter or Android result is imported.
    definitions = []
    def add(name, op, args, constructor, overrides=None, setup=None, link=None, boundary='original wx command'):
        spec = {**deepcopy(base), 'name': 'Mutation history ' + name, 'notes': 'Independent notes — 保持', **(overrides or {})}
        definitions.append((name, op, args, constructor, spec, setup, link, boundary))
    gun = {'name': 'Dual 150mm Railgun II', 'state': 'ACTIVE', 'charge': 'Spike M'}
    ammo = 'Antimatter Charge M'
    cargo = [{'name': ammo, 'amount': 200}, {'name': 'Iron Charge M', 'amount': 300}]
    add('rename', 'rename_fit', {'name': 'Renamed independent — Δ'}, lambda f, _: commands['gui/fitRename'](f.ID, 'Renamed independent — Δ'))
    add('mode', 'change_mode', {'item_id': iid('Confessor Sharpshooter Mode')},
        lambda f, _: commands['gui/shipModeChange'](f.ID, iid('Confessor Sharpshooter Mode')), {'ship': 'Confessor'})
    subsystem = 'Tengu Offensive - Accelerated Ejection Bay'
    add('subsystem-add', 'set_subsystem', {'kind': 127, 'item_id': iid(subsystem)},
        lambda f, _: commands['gui/localModule/add'](f.ID, iid(subsystem)), {'ship': 'Tengu'})
    add('cargo-add', 'add_cargo', {'item_id': iid(ammo), 'quantity': 150},
        lambda f, _: commands['add'](f.ID, iid(ammo), 150), {'cargo': cargo})
    add('cargo-set', 'set_cargo_quantity', {'item_id': iid(ammo), 'quantity': 75},
        lambda f, _: commands['changeAmount'](f.ID, [iid(ammo)], 75), {'cargo': cargo})
    add('cargo-remove-part', 'remove_cargo', {'item_id': iid(ammo), 'quantity': 75},
        lambda f, _: namespace['CalcRemoveCargoCommand'](f.ID, namespace['CargoInfo'](itemID=iid(ammo), amount=75)), {'cargo': cargo})
    add('cargo-selected-zero', 'set_cargo_quantities', {'item_ids': [iid(ammo), iid('Iron Charge M')], 'quantity': 0},
        lambda f, _: commands['changeAmount'](f.ID, [iid(ammo), iid('Iron Charge M')], 0), {'cargo': cargo})
    add('cargo-selected-remove', 'remove_cargos', {'item_ids': [iid(ammo), iid('Iron Charge M')]},
        lambda f, _: commands['remove'](f.ID, [iid(ammo), iid('Iron Charge M')]), {'cargo': cargo})

    def menu_command(fit, operation):
        captured = []
        oracle['run'](fit, operation, command_sink=lambda command: captured.append(command) or True)
        assert len(captured) == 1
        return captured[0]
    add('cargo-preset', 'add_cargo_preset', {'item_id': iid(ammo)},
        lambda f, _: menu_command(f, {'kind': 'preset', 'item': ammo}), {'modules': [gun]})
    for from_cargo in (False, True):
        add('cargo-fill-' + str(from_cargo), 'fill_cargo', {'item_id': iid(ammo), 'from_cargo': from_cargo},
            lambda f, _, flag=from_cargo: menu_command(f, {'kind': 'fill_cargo' if flag else 'fill_market', 'item': ammo}), {'cargo': cargo})
    add('cargo-variation', 'change_cargo_variations', {'main_item_id': iid('Damage Control II'),
        'item_ids': [iid('Damage Control II')], 'item_id': iid('Damage Control I')},
        lambda f, _: commands['changeMetas'](f.ID, [iid('Damage Control II')], iid('Damage Control I')),
        {'cargo': [{'name': 'Damage Control II', 'amount': 2}]})
    for copy in (False, True):
        add('transfer-to-' + str(copy), 'transfer_cargo', {'direction': 'TO_CARGO', 'positions': [0], 'item_id': None, 'copy': copy},
            lambda f, _, flag=copy: commands['gui/localModuleCargo/localModuleToCargo'](f.ID, 0, None, flag), {'modules': [gun], 'cargo': cargo})
        add('transfer-from-' + str(copy), 'transfer_cargo', {'direction': 'FROM_CARGO', 'positions': [0], 'item_id': iid('200mm Railgun II'), 'copy': copy},
            lambda f, _, flag=copy: commands['gui/localModuleCargo/cargoToLocalModule'](f.ID, iid('200mm Railgun II'), 0, flag),
            {'modules': [gun], 'cargo': [{'name': '200mm Railgun II', 'amount': 2}]})
    implant = "Eifyr and Co. 'Rogue' Navigation NN-601"
    implant_inputs = [{'name': implant, 'active': True}]
    add('implant-add', 'add_implant', {'implant': implant, 'active': True}, lambda f, _: commands['gui/implant/add'](f.ID, iid(implant)))
    add('implant-state', 'set_implant_active', {'slot': 6, 'active': False},
        lambda f, _: commands['gui/implant/toggleStates'](f.ID, 0, [0]), {'implants': implant_inputs})
    add('implant-remove', 'remove_implant', {'slot': 6}, lambda f, _: commands['gui/implant/remove'](f.ID, [0]), {'implants': implant_inputs})
    for context, old, new, extra in (
        ('implant', implant, "Eifyr and Co. 'Rogue' Navigation NN-605", {'implants': implant_inputs}),
        ('drone', 'Hobgoblin I', 'Hobgoblin II', {'drones': [{'name': 'Hobgoblin I', 'amount': 2, 'active': 1}]})):
        add('variation-' + context, 'change_variation', {'context': context, 'position': 0, 'item_id': iid(new)},
            lambda f, _, kind=context, name=new: oracle['variation_commands'][kind](f.ID, 0 if kind == 'implant' else [0], iid(name)), extra)
    projection_spec = json.loads((ROOT / 'tools/android_reference/projection.json').read_text())['source']
    command_spec = json.loads((ROOT / 'tools/android_reference/command.json').read_text())['source']
    def projection_setup(f, other):
        command = commands['projectedFit/add'](f.ID, other.ID, 1, state=True); assert command.Do()
        assert commands['projectedFit/changeProjectionRange'](f.ID, other.ID, 0.0).Do()
        eos.db.saveddata_session.flush(); service.recalc(f.ID)
    def command_setup(f, other):
        command = commands['commandFit/add'](f.ID, other.ID, state=True); assert command.Do()
        eos.db.saveddata_session.flush(); service.recalc(f.ID)
    add('projection-add', 'add_projection', {'range_m': 0.0, 'active': True, 'amount': 1},
        lambda f, other: Group([commands['projectedFit/add'](f.ID, other.ID, 1, state=True),
            commands['projectedFit/changeProjectionRange'](f.ID, other.ID, 0.0)]), link=projection_spec)
    add('projection-configure', 'configure_projection', {'range_m': 15000.0, 'active': False, 'amount': 2},
        lambda f, other: Group([commands['projectedFit/changeState'](f.ID, other.ID, False),
            commands['projectedFit/changeAmount'](f.ID, other.ID, 2),
            commands['projectedFit/changeProjectionRange'](f.ID, other.ID, 15000.0)]), setup=projection_setup, link=projection_spec)
    add('projection-remove', 'remove_projection', {},
        lambda f, other: commands['projectedFit/remove'](f.ID, other.ID, math.inf), setup=projection_setup, link=projection_spec)
    add('command-add', 'add_command', {'active': True},
        lambda f, other: commands['gui/commandFit/add'](f.ID, [other.ID]), link=command_spec)
    add('command-state', 'set_command_active', {'active': False},
        lambda f, other: commands['gui/commandFit/toggleStates'](f.ID, other.ID, [other.ID]), setup=command_setup, link=command_spec)
    add('command-remove', 'remove_command', {}, lambda f, other: commands['gui/commandFit/remove'](f.ID, [other.ID]), setup=command_setup, link=command_spec)

    class SkillInput(wx.Command):
        """Explicit desktop non-command gap: original Skill.setLevel and EOS only."""
        def __init__(self, fit):
            wx.Command.__init__(self, True, 'Fit-scoped skill override')
            self.skill = fit.character.getSkill(item('Gunnery')); self.old = self.skill.activeLevel
        def Do(self): self.skill.setLevel(4); return True
        def Undo(self): self.skill.setLevel(self.old); return True
    add('skill-override', 'set_skill_level', {'skill': 'Gunnery', 'level': 4}, lambda f, _: SkillInput(f),
        {'modules': [gun]}, boundary='direct desktop Skill.setLevel input; Android action grouping is explicit')
    cases = []
    for name, operation, arguments, constructor, spec, setup, linked_spec, boundary in definitions:
        print('Original history case:', name, operation, flush=True)
        fit = make_fit(spec)
        linked = make_fit({**deepcopy(linked_spec), 'name': 'Independent source ' + name}) if linked_spec else None
        if setup: setup(fit, linked)
        market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'] = []
        processor = service.getCommandProcessor(fit.ID)
        initial = observe(fit, linked)
        steps = [{'action': 'initial', 'result': initial}]
        command = constructor(fit, linked)
        for action in ('do', 'undo', 'redo', 'undo', 'redo'):
            accepted = processor.Submit(command) if action == 'do' else getattr(processor, action.title())()
            assert accepted, (name, action)
            steps.append({'action': action, 'result': observe(fit, linked)})
        for index in (2, 4):
            # Recent-use promotion is a desktop Do side effect, not reversed.
            restored_values(initial, steps[index]['result'])
        cases.append({'name': name, 'operation': operation, 'arguments': arguments, 'spec': spec,
            'source_spec': {**linked_spec, 'name': linked.name} if linked_spec else None,
            'setup_link': operation in ('configure_projection', 'remove_projection', 'set_command_active', 'remove_command'),
            'boundary': boundary, 'steps': steps})
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    oracle['source_files']['gui/builtinAdditionPanes/cargoView.py'] = digest_file(source / 'gui/builtinAdditionPanes/cargoView.py')
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
        'eos_settings': dict(configuration.settings), 'database_logical_sha256': logical_database_digest(database),
        'cases': cases, 'boundary': 'Original Do/Undo bodies and real wx processors; explicit grouped calls and direct skill-profile gap identified per case.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'database', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--worker', action='store_true'); parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    args.source, args.database, args.output = args.source.resolve(), args.database.resolve(strict=True), args.output.resolve()
    validate_source(args.source)
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    if args.worker:
        args.output.write_text(json.dumps(export(args.source, args.database), indent=2, allow_nan=False) + '\n', encoding='utf-8'); return
    if args.output.is_relative_to(ROOT): raise ValueError('Use fresh output outside checkout')
    baseline = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())
    compare(baseline['database_logical_sha256'], logical_database_digest(args.database))
    before = digest_file(args.database); args.output.mkdir(parents=True, exist_ok=False)
    for name in ('history-mutations', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', str(args.source),
                '--database', str(args.database), '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
    actual = json.loads((args.output / 'history-mutations.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    (args.output / 'evidence.json').write_text(json.dumps({'task': 'B09.2', 'source_commit': SOURCE_COMMIT,
        'game_database_unchanged': True, 'fresh_process_repeat': True, 'cases': len(actual['cases']),
        'states': sum(len(c['steps']) for c in actual['cases']), 'database_sha256': before,
        'reference_sha256': digest_file(args.output / 'history-mutations.json')}, indent=2) + '\n')
    print('PASS independent B09.2 original history matrix, repeated in fresh process')


if __name__ == '__main__': main()
