"""B04.2.3.2 independent original variation menus and commands."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare,
    digest_file, logical_database_digest, snapshot, validate_source)
from tools.android_reference.charge_edits import ATTRIBUTES


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FitSystemSecurity, ImplantLocation, FittingModuleState
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.variation_oracle import load
    oracle = load(source)
    service, market = oracle['service'], Market.getInstance()

    def make_fit(case):
        item = eos.db.getItem(case['ship'])
        fit = Fit(Citadel(item) if item.category.name == 'Structure' else Ship(item), name=case['name'])
        fit.character = Character('Independent all V', defaultLevel=5)
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity = FitSystemSecurity.HISEC, 0.0
        fit.ignoreRestrictions = case.get('ignore_restrictions', False)
        for row in case.get('modules', []):
            item, charge = eos.db.getItem(row['name']), eos.db.getItem(row['charge']) if row.get('charge') else None
            assert item is not None and (not row.get('charge') or charge is not None), row
            fit.modules.append(oracle['ModuleInfo'](item.ID, state=FittingModuleState[row['state']],
                               chargeID=charge.ID if charge else None).toModule())
        for row in case.get('drones', []):
            item = eos.db.getItem(row['name']); assert item is not None, row
            fit.drones.append(oracle['DroneInfo'](row['amount'], row['active'], item.ID).toDrone())
        for row in case.get('implants', []):
            item = eos.db.getItem(row['name']); assert item is not None, row
            fit.implants.append(oracle['ImplantInfo'](item.ID, row['active']).toImplant())
        assert len(fit.implants) == len(case.get('implants', []))
        eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush()
        service.getFit(fit.ID)
        return fit

    def stats(fit):
        if not fit.calculated: fit.calculateModifiedAttributes()
        result = snapshot(fit)
        result['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        return result

    def options(fit):
        rows = []
        for context, things in (('module', fit.modules), ('drone', fit.drones), ('implant', fit.implants)):
            for i, thing in enumerate(things):
                if getattr(thing, 'isEmpty', False): continue
                if context == 'module' and thing.slot not in (1, 2, 3, 4, 8): continue
                current = ({'state': FittingModuleState(thing.state).name, 'charge_id': thing.chargeID}
                    if context == 'module' else {'amount': thing.amount, 'active': thing.amountActive}
                    if context == 'drone' else {'slot': thing.slot, 'active': thing.active, 'location': 'FIT'})
                rows.append({'context': context, 'index': i, 'item_id': thing.itemID, 'name': thing.item.name,
                             'current': current, 'choices': oracle['choices'](fit, thing.item, context)})
        return {'targets': rows}

    def report(fit, recipients):
        value = stats(fit)
        return {'options': options(fit), 'stats': value,
            'modules': [{'index': i, 'id': mod.itemID, 'state': FittingModuleState(mod.state).name,
                         'charge_id': mod.chargeID, 'attributes': {key: {'value': mod.getModifiedItemAttr(key, None), 'unit': unit}
                            for key, unit in ATTRIBUTES.items()}} for i, mod in enumerate(fit.modules) if not mod.isEmpty],
            'drones': [{'index': i, 'id': drone.itemID, 'amount': drone.amount, 'active': drone.amountActive}
                       for i, drone in enumerate(fit.drones)],
            'implants': [{'index': i, 'id': implant.itemID, 'slot': implant.slot, 'active': implant.active}
                        for i, implant in enumerate(fit.implants)],
            'implant_location': ImplantLocation(fit.implantLocation).name,
            'recipients': [{'name': target.name, 'stats': stats(target)} for target in recipients],
            'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'])}

    cases = []
    inputs = json.loads((ROOT / 'tools/android_reference/variation-edits.json').read_text())
    market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'] = []
    for case in inputs:
        fit = make_fit(case)
        recipients = []
        for row in case.get('recipients', []):
            target = make_fit(row)
            container = target.commandFitDict if case.get('link') == 'command' else target.projectedFitDict
            container[fit.ID] = fit
            eos.db.saveddata_session.flush(); eos.db.saveddata_session.refresh(fit)
            if case.get('link') == 'command': fit.getCommandInfo(target.ID).active = True
            else:
                info = fit.getProjectionInfo(target.ID)
                info.projectionRange, info.active, info.amount = 0.0, True, 1
            service.recalc(fit); service.recalc(target)
            recipients.append(target)
        steps = [{'input': None, 'changed': False, 'result': report(fit, recipients)}]
        for context, index, name in case['operations']:
            item = eos.db.getItem(name); assert item is not None, name
            target = {'module': fit.modules, 'drone': fit.drones, 'implant': fit.implants}[context][index]
            assert any(c['id'] == item.ID and c['enabled'] for c in oracle['choices'](fit, target.item, context)), (case['name'], name)
            command = oracle['variation_commands'][context](fit.ID, index if context == 'implant' else [index], item.ID)
            changed = command.Do()
            steps.append({'input': {'context': context, 'position': index, 'item_id': item.ID, 'name': name},
                          'changed': changed, 'result': report(fit, recipients)})
        cases.append({**case, 'steps': steps})
    # Complete published equipment families; actual menu logic may include
    # additional unpublished family members and explicitly disabled hull choices.
    catalog = json.loads((ROOT / 'tools/android_reference/fixtures/equipment.json').read_text())['catalog']['items']
    probe = make_fit({'name': 'Complete variation menu probe', 'ship': 'Rifter'})
    families = []
    for row in catalog:
        category = row['category']
        if category not in ('Module', 'Structure Module', 'Drone', 'Implant'): continue
        item = eos.db.getItem(row['id'])
        if category in ('Module', 'Structure Module'):
            mod = oracle['ModuleInfo'](item.ID).toModule()
            if mod is None or mod.slot not in (1, 2, 3, 4, 8): continue
            context = 'module'
        elif category == 'Drone': context = 'drone'
        else:
            if 'implantness' not in item.attributes: continue
            context = 'implant'
        families.append({'id': item.ID, 'context': context, 'choices': oracle['choices'](probe, item, context)})
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
            'eos_settings': dict(configuration.settings), 'cases': cases, 'families': families,
            'family_probe_ship': 'Rifter', 'inputs': {'skill_level': 5, 'factor_reload': False,
            'system_security': 'HISEC', 'pilot_security': 0.0, 'uniform_damage': [25, 25, 25, 25]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'database', 'output'): parser.add_argument('--' + name, type=Path, required=True)
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
        raise ValueError('Use a new output outside checkout and input database')
    baseline = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())
    compare(baseline['database_logical_sha256'], logical_database_digest(args.database))
    before = digest_file(args.database)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ('variations', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', str(args.source),
                '--database', str(args.database), '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'variations.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    receipt = {'task': 'B04.2.3.2', 'source_commit': SOURCE_COMMIT, 'dependencies': DEPENDENCIES,
        'database_logical_sha256': baseline['database_logical_sha256'], 'database_sha256': before,
        'fresh_process_repeat': True, 'game_database_unchanged': True,
        'reference_sha256': digest_file(args.output / 'variations.json'), 'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases']), 'families': len(actual['families'])}
    (args.output / 'evidence.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
