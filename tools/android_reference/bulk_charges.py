"""B05.1 original bulk charge selection and commands in an isolated desktop."""
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


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FitSystemSecurity, ImplantLocation, FittingModuleState, FittingSlot
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from service.market import Market
    from service.ammo import Ammo
    from tools.android_reference.bulk_charge_oracle import load
    oracle = load(source)
    service, market = oracle['service'], Market.getInstance()

    def make_fit(case):
        item = eos.db.getItem(case['ship'])
        fit = Fit(Citadel(item) if item.category.name == 'Structure' else Ship(item), name=case['name'])
        fit.character = Character('Independent all V', defaultLevel=5)
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity, fit.ignoreRestrictions = FitSystemSecurity.HISEC, 0.0, False
        for row in case.get('modules', []):
            item = eos.db.getItem(row['name'])
            charge = eos.db.getItem(row['charge']) if row.get('charge') else None
            assert item is not None and (not row.get('charge') or charge is not None), row
            fit.modules.append(oracle['ModuleInfo'](item.ID, state=FittingModuleState[row['state']],
                               chargeID=charge.ID if charge else None).toModule())
        eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush()
        service.getFit(fit.ID)
        assert all(m.isEmpty or m.fits(fit) for m in fit.modules)
        return fit

    def stats(fit):
        if not fit.calculated: fit.calculateModifiedAttributes()
        result = snapshot(fit)
        result['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        return result

    def options(fit):
        items, rows = {}, []
        ammo = Ammo.getInstance()
        charges = [set() if mod.isEmpty else ammo.getModuleFlatAmmo(mod) for mod in fit.modules]
        for index, mod in enumerate(fit.modules):
            choices = charges[index]
            items.update((item.ID, item) for item in choices)
            rows.append({'index': index, 'item_id': mod.itemID, 'charge_id': mod.chargeID,
                         'charge_ids': sorted(item.ID for item in choices),
                         'selection_candidates': [] if mod.isEmpty else [i for i, other in enumerate(fit.modules)
                             if not other.isEmpty and charges[i].issubset(choices)],
                         'similar_candidates': [] if mod.isEmpty else oracle['similar'](fit.modules, mod)})
        return {'modules': rows, 'items': [{'id': i, 'name': items[i].name} for i in sorted(items)]}

    def report(fit, recipients):
        return {'options': options(fit), 'stats': stats(fit),
                'modules': [{'index': i, 'id': m.itemID, 'slot': FittingSlot(m.slot).name,
                             'state': FittingModuleState(m.state).name, 'charge_id': m.chargeID}
                            for i, m in enumerate(fit.modules)],
                'recipients': [{'name': target.name, 'stats': stats(target)} for target in recipients],
                'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'])}

    cases = []
    inputs = json.loads((ROOT / 'tools/android_reference/bulk-charges.json').read_text())
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
        # Operation positions address initial occupied modules. Resolve their
        # identities again after original fill inserts vacant rack positions.
        originals = [m for m in fit.modules if not m.isEmpty]
        for main, selected, scope, charge_name in case['operations']:
            main = fit.modules.index(originals[main])
            selected = [fit.modules.index(originals[p]) for p in selected]
            charge = eos.db.getItem(charge_name) if charge_name is not None else None
            assert charge_name is None or charge is not None, charge_name
            command = oracle['select'](fit, main, selected, charge, scope)
            inverted = oracle['select'](fit, main, selected, charge, scope, invert=True)
            assert command.positions == inverted.positions
            targets = [p for p in command.positions if fit.modules[p].isValidCharge(charge)]
            changes = [p for p in targets if fit.modules[p].chargeID != (charge.ID if charge else None)]
            print(case['name'], scope, main, selected, charge_name, targets, changes, flush=True)
            changed = command.Do()
            assert changed is bool(changes)
            service.recalc(fit)
            steps.append({'input': {'main_position': main, 'module_indices': selected, 'scope': scope,
                                   'charge_id': charge.ID if charge else None},
                          'targets': targets, 'changed_positions': changes, 'changed': changed,
                          'result': report(fit, recipients)})
        cases.append({**case, 'steps': steps})
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
            'eos_settings': dict(configuration.settings), 'cases': cases,
            'inputs': {'skill_level': 5, 'factor_reload': False, 'system_security': 'HISEC',
                       'pilot_security': 0.0, 'uniform_damage': [25, 25, 25, 25]},
            'selection': 'Original desktop subset filtering and similar-group/effect policy; modifier inversion checked for every operation.'}


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
    for name in ('bulk', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', str(args.source),
                '--database', str(args.database), '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'bulk.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    receipt = {'task': 'B05.1', 'source_commit': SOURCE_COMMIT, 'dependencies': DEPENDENCIES,
        'database_logical_sha256': baseline['database_logical_sha256'], 'database_sha256': before,
        'fresh_process_repeat': True, 'game_database_unchanged': True,
        'reference_sha256': digest_file(args.output / 'bulk.json'), 'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases'])}
    (args.output / 'evidence.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
