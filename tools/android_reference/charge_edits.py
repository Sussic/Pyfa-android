"""B04.2.3.1 independent original charge commands and complete compatible sets."""
import argparse
import ast
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (
    SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare, digest_file,
    logical_database_digest, snapshot, validate_source)

ATTRIBUTES = {'maxRange': 'm', 'falloff': 'm', 'trackingSpeed': 'rad/s',
    'speed': 'ms', 'damageMultiplier': 'multiplier', 'capacitorNeed': 'GJ',
    'capacitorBonus': 'GJ', 'armorDamageAmount': 'HP', 'shieldBonus': 'HP',
    'miningAmount': 'm3', 'scanResolutionBonus': '%', 'maxTargetRangeBonus': '%'}


def export(source, database):
    configuration = bootstrap(source, database)
    # Match desktop config.init before importing the gamedata session. Cached
    # typed lookups share integer keys; desktop disables that cache as policy.
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    import wx
    from logbook import Logger
    from eos.const import FitSystemSecurity, ImplantLocation, FittingModuleState
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship
    from service.ammo import Ammo
    from service.market import Market
    from tools.android_reference.module_oracle import load
    oracle = load(source)
    service, market, ammo = oracle['service'], Market.getInstance(), Ammo.getInstance()
    source_files = dict(oracle['source_files'])
    def parse(relative):
        path = source / relative
        source_files[relative] = digest_file(path)
        return ast.parse(path.read_bytes(), filename=str(path))
    path = 'gui/fitCommands/calc/module/changeCharges.py'
    node = next(n for n in parse(path).body if isinstance(n, ast.ClassDef) and n.name == 'CalcChangeModuleChargesCommand')
    namespace = dict(wx=wx, Fit=type(service), Market=Market, pyfalog=Logger('independent-charge-oracle'))
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source / path), 'exec'), namespace)
    command_type = namespace['CalcChangeModuleChargesCommand']
    # Execute the original browser union method with real Fit/Ammo services;
    # only the window's active-fit identifier is supplied by a minimal holder.
    path = 'gui/builtinMarketBrowser/itemView.py'
    cls = next(n for n in parse(path).body if isinstance(n, ast.ClassDef) and any(
        isinstance(m, ast.FunctionDef) and m.name == 'getChargesForActiveFit' for m in n.body))
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'getChargesForActiveFit')
    scope = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source / path), 'exec'), scope)
    active_union = scope['getChargesForActiveFit']
    for relative in ('service/ammo.py', 'gui/fitCommands/gui/localModule/changeCharges.py',
                     'gui/builtinContextMenus/moduleAmmoChange.py'):
        source_files[relative] = digest_file(source / relative)

    def make_fit(ship, name, modules=()):
        item = eos.db.getItem(ship)
        fit = Fit(Citadel(item) if item.category.name == 'Structure' else Ship(item), name=name)
        fit.character = Character('Independent all V', defaultLevel=5)
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity, fit.ignoreRestrictions = FitSystemSecurity.HISEC, 0.0, False
        for row in modules:
            item = eos.db.getItem(row['name'])
            assert item is not None, row['name']
            charge = eos.db.getItem(row['charge']) if row.get('charge') else None
            assert not row.get('charge') or charge is not None, row
            info = oracle['ModuleInfo'](item.ID, state=FittingModuleState[row['state']],
                                        chargeID=charge.ID if charge else None)
            fit.modules.append(info.toModule())
        eos.db.saveddata_session.add(fit)
        eos.db.saveddata_session.flush()
        service.getFit(fit.ID)
        return fit

    def options(fit):
        holder = SimpleNamespace(mainFrame=SimpleNamespace(getActiveFit=lambda: fit.ID), sFit=service, sAmmo=ammo)
        items = active_union(holder)
        return {'modules': [{'index': i, 'item_id': mod.itemID, 'charge_id': mod.chargeID,
                            'charge_ids': sorted(item.ID for item in ammo.getModuleFlatAmmo(mod))}
                           for i, mod in enumerate(fit.modules)],
                'items': [{'id': item.ID, 'name': item.name} for item in sorted(items, key=lambda item: item.ID)]}

    def stats(fit):
        if not fit.calculated:
            fit.calculateModifiedAttributes()
        value = snapshot(fit)
        value['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        return value

    def report(fit, recipients):
        return {'options': options(fit), 'stats': stats(fit),
            'modules': [{'index': i, 'id': mod.itemID, 'state': FittingModuleState(mod.state).name,
                         'charge_id': mod.chargeID, 'attributes': {
                             key: {'value': mod.getModifiedItemAttr(key, None), 'unit': unit}
                             for key, unit in ATTRIBUTES.items()}}
                        for i, mod in enumerate(fit.modules) if not mod.isEmpty],
            'recipients': [{'name': target.name, 'stats': stats(target)} for target in recipients],
            'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'])}

    cases = []
    inputs = json.loads((ROOT / 'tools/android_reference/charge-edits.json').read_text())
    market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'] = []
    for case in inputs:
        fit = make_fit(case['ship'], case['name'], case['modules'])
        recipients = []
        for row in case.get('recipients', []):
            target = make_fit(row['ship'], row['name'])
            container = target.commandFitDict if case.get('link') == 'command' else target.projectedFitDict
            container[fit.ID] = fit
            eos.db.saveddata_session.flush()
            eos.db.saveddata_session.refresh(fit)
            if case.get('link') == 'command':
                fit.getCommandInfo(target.ID).active = True
            else:
                info = fit.getProjectionInfo(target.ID)
                info.projectionRange, info.active, info.amount = 0.0, True, 1
            service.recalc(fit)
            service.recalc(target)
            recipients.append(target)
        rows = [{'input': None, 'changed': False, 'result': report(fit, recipients)}]
        for position, name, expected_change in case['operations']:
            item = eos.db.getItem(name) if name is not None else None
            assert name is None or item is not None, name
            command = command_type(fit.ID, False, {position: item.ID if item else None})
            changed = command.Do()
            if command.needsGuiRecalc:
                eos.db.saveddata_session.flush()
                service.recalc(fit)
            service.fill(fit)
            eos.db.saveddata_session.commit()
            assert changed is expected_change, (case['name'], name, changed)
            rows.append({'input': {'position': position, 'charge_id': item.ID if item else None,
                                  'charge': name}, 'changed': changed, 'result': report(fit, recipients)})
        cases.append({**case, 'steps': rows})

    catalog = json.loads((ROOT / 'tools/android_reference/fixtures/equipment.json').read_text())['catalog']['items']
    compatibility = []
    for row in catalog:
        if row['category'] not in ('Module', 'Structure Module'):
            continue
        mod = oracle['ModuleInfo'](row['id']).toModule()
        if mod is None or mod.slot not in (1, 2, 3, 4, 8):
            continue
        compatibility.append({'id': row['id'], 'charge_ids': sorted(item.ID for item in ammo.getModuleFlatAmmo(mod))})
    assert len(compatibility) == 4242
    assert not active_union(SimpleNamespace(mainFrame=SimpleNamespace(getActiveFit=lambda: None)))
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': source_files,
        'eos_settings': dict(configuration.settings), 'cases': cases, 'compatibility': compatibility,
        'inputs': {'skill_level': 5, 'factor_reload': False, 'system_security': 'HISEC',
                   'pilot_security': 0.0, 'uniform_damage': [25, 25, 25, 25],
                   'drones': [], 'implants': [], 'boosters': [], 'commands': [], 'environments': []}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'database', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    args.source, args.database, args.output = args.source.resolve(), args.database.resolve(strict=True), args.output.resolve()
    validate_source(args.source)
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    if args.worker:
        args.output.write_text(json.dumps(export(args.source, args.database), indent=2, allow_nan=False) + '\n', encoding='utf-8')
        return
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError('Use a new output outside the checkout and input database')
    baseline = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())
    compare(baseline['database_logical_sha256'], logical_database_digest(args.database))
    before = digest_file(args.database)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ('charges', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', str(args.source),
                '--database', str(args.database), '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'charges.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database))
    validate_source(args.source)
    receipt = {'task': 'B04.2.3.1', 'source_commit': SOURCE_COMMIT, 'dependencies': DEPENDENCIES,
        'database_logical_sha256': baseline['database_logical_sha256'], 'database_sha256': before,
        'fresh_process_repeat': True, 'game_database_unchanged': True,
        'reference_sha256': digest_file(args.output / 'charges.json'), 'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases']), 'modules': len(actual['compatibility'])}
    (args.output / 'evidence.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
