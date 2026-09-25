"""Export B05.2 values by executing the original pinned desktop state command."""
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
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.bulk_state_oracle import load

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
        rows = []
        editable_slots = {FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH, FittingSlot.RIG, FittingSlot.SERVICE}
        for index, mod in enumerate(fit.modules):
            editable = not mod.isEmpty and mod.slot in editable_slots
            rows.append({'index': index, 'item_id': mod.itemID,
                         'state': None if mod.isEmpty else FittingModuleState(mod.state).name,
                         'editable': editable,
                         'similar_candidates': [i for i in oracle['similar'](fit.modules, mod)
                                                if fit.modules[i].slot in editable_slots] if editable else [],
                         'click_states': {} if mod.isEmpty else {
                             click: FittingModuleState(Module.getProposedState(mod, click)).name
                             for click in ('left', 'right', 'ctrl')},
                         'supported_states': {} if mod.isEmpty else {
                             state.name: FittingModuleState(mod.getMaxState(proposedState=state)).name
                             for state in FittingModuleState}})
        return {'modules': rows}

    def report(fit, recipients):
        return {'options': options(fit), 'stats': stats(fit),
                'modules': [{'index': i, 'id': m.itemID, 'slot': FittingSlot(m.slot).name,
                             'state': FittingModuleState(m.state).name if not m.isEmpty else None,
                             'charge_id': m.chargeID} for i, m in enumerate(fit.modules)],
                'recipients': [{'name': target.name, 'stats': stats(target)} for target in recipients],
                'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'])}

    charge_cases = {case['name']: case for case in json.loads((ROOT / 'tools/android_reference/bulk-charges.json').read_text())}
    inputs = json.loads((ROOT / 'tools/android_reference/bulk-states.json').read_text())
    market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'] = []
    cases = []
    for case in inputs:
        basis = charge_cases[case['basis']]
        fit = make_fit(basis)
        recipients = []
        for row in basis.get('recipients', []):
            target = make_fit(row)
            container = target.commandFitDict if basis.get('link') == 'command' else target.projectedFitDict
            container[fit.ID] = fit
            eos.db.saveddata_session.flush(); eos.db.saveddata_session.refresh(fit)
            if basis.get('link') == 'command': fit.getCommandInfo(target.ID).active = True
            else:
                info = fit.getProjectionInfo(target.ID)
                info.projectionRange, info.active, info.amount = 0.0, True, 1
            service.recalc(fit); service.recalc(target)
            recipients.append(target)
        steps = [{'input': None, 'changed': False, 'result': report(fit, recipients)}]
        originals = [m for m in fit.modules if not m.isEmpty]
        for main, selected, scope, click in case['operations']:
            main = fit.modules.index(originals[main])
            selected = [fit.modules.index(originals[p]) for p in selected]
            positions = oracle['similar'](fit.modules, fit.modules[main]) if scope == 'SIMILAR' else selected
            command = oracle['command'](fit.ID, main, positions, click)
            before = [m.state for m in fit.modules]
            changed = command.Do()
            if command.needsGuiRecalc:
                eos.db.flush(); service.recalc(fit.ID)
            service.fill(fit.ID); eos.db.commit()
            actual = [i for i, m in enumerate(fit.modules) if i < len(before) and m.state != before[i]]
            assert changed == bool(actual) or not changed and not actual
            print(case['basis'], scope, click, main, selected, positions, actual, flush=True)
            steps.append({'input': {'main_position': main, 'module_indices': selected, 'scope': scope,
                                   'click': click}, 'targets': positions, 'changed_positions': actual,
                          'changed': changed, 'result': report(fit, recipients)})
        cases.append({**basis, 'operations': case['operations'], 'steps': steps})
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
            'eos_settings': dict(configuration.settings), 'cases': cases,
            'inputs': {'skill_level': 5, 'factor_reload': False, 'system_security': 'HISEC',
                       'pilot_security': 0.0, 'uniform_damage': [25, 25, 25, 25]},
            'selection': 'Original desktop getSimilarModPositions and CalcChangeLocalModuleStatesCommand.Do/needsGuiRecalc/fill.'}


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
    for name in ('states', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', str(args.source),
                '--database', str(args.database), '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'states.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    print(json.dumps({'cases': len(actual['cases']), 'states': sum(len(c['steps']) for c in actual['cases']),
                      'recipients': sum(len(c.get('recipients', [])) for c in actual['cases'])}))


if __name__ == '__main__': main()
