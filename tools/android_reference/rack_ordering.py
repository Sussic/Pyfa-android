"""B04.2.3.3 original rack swaps and positional heat in an isolated desktop."""
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
    from tools.android_reference.ordering_oracle import load
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

    def report(fit, recipients):
        values = stats(fit)
        rows = []
        for index, mod in enumerate(fit.modules):
            heat = None
            if mod.state == FittingModuleState.OVERHEATED:
                thermo = oracle['thermodynamics'](fit)
                cycles = thermo.calcBurnCycles(mod)
                # Original Heat.getText uses duration before speed for time,
                # while calcBurnCycles uses speed before duration internally.
                cycle_time = (mod.getModifiedItemAttr('duration') or mod.getModifiedItemAttr('speed')) / 1000
                heat = {'cycles': {'value': cycles, 'unit': 'cycles'},
                        'seconds': {'value': cycles * cycle_time, 'unit': 's'},
                        'probabilities': [{'seconds': seconds, 'value': thermo.calcDamageProbability(mod, seconds), 'unit': 'probability'}
                                          for seconds in (1.0, 10.0, 60.0, 600.0)]}
            rows.append({'index': index, 'id': mod.itemID, 'name': mod.item.name if mod.item else None,
                         'slot': FittingSlot(mod.slot).name, 'state': FittingModuleState(mod.state).name,
                         'charge_id': mod.chargeID, 'charge': mod.charge.name if mod.charge else None, 'heat': heat})
        return {'rack': {'modules': rows}, 'stats': values,
                'recipients': [{'name': target.name, 'stats': stats(target)} for target in recipients],
                'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'])}

    cases = []
    inputs = json.loads((ROOT / 'tools/android_reference/rack-ordering.json').read_text())
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
        for slot, source_position, target_position in case['operations']:
            positions = [i for i, mod in enumerate(fit.modules) if mod.slot == FittingSlot[slot]]
            first, second = positions[source_position], positions[target_position]
            originals = fit.modules[first], fit.modules[second]
            assert not originals[0].isEmpty, 'Desktop startDrag rejects a vacant source'
            print(case['name'], slot, source_position, target_position, first, second, flush=True)
            command = oracle['swap'](fit.ID, first, second)
            changed = command.Do()
            assert (fit.modules[second], fit.modules[first]) == originals
            service.recalc(fit)
            steps.append({'input': {'from_position': first, 'to_position': second}, 'changed': changed,
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
            'heat': {'source': 'gui/builtinViewColumns/heat.py', 'simulation_seconds': 600,
                     'probability_sample_seconds': [1.0, 10.0, 60.0, 600.0],
                     'meaning': 'Pinned desktop estimate of cycles and time until burnout, not measured game duration.'}}


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
    for name in ('ordering', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', str(args.source),
                '--database', str(args.database), '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'ordering.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    receipt = {'task': 'B04.2.3.3', 'source_commit': SOURCE_COMMIT, 'dependencies': DEPENDENCIES,
        'database_logical_sha256': baseline['database_logical_sha256'], 'database_sha256': before,
        'fresh_process_repeat': True, 'game_database_unchanged': True,
        'reference_sha256': digest_file(args.output / 'ordering.json'), 'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases'])}
    (args.output / 'evidence.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
