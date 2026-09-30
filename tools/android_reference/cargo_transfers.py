"""Export B07.3 fitted cargo transfer actions from the pinned desktop."""
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
    from eos.saveddata.cargo import Cargo
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.cargo_transfers_oracle import load
    oracle = load(source)
    service, market = oracle['service'], Market.getInstance()
    market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'] = []

    def item(name):
        value = eos.db.getItem(name)
        assert value is not None, name
        return value

    def make_fit(case):
        hull = item(case['ship'])
        fit = Fit(Citadel(hull) if hull.category.name == 'Structure' else Ship(hull), name=case['name'])
        fit.character = Character('Independent all V', defaultLevel=5)
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity = FitSystemSecurity.HISEC, 0.0
        for row in case['modules']:
            module = oracle['ModuleInfo'](item(row['name']).ID,
                chargeID=item(row['charge']).ID if row.get('charge') else None,
                state=FittingModuleState[row['state']]).toModule()
            fit.modules.appendIgnoreEmpty(module)
        for row in case['cargo']:
            stack = Cargo(item(row['name'])); stack.amount = row['amount']; fit.cargo.append(stack)
        eos.db.saveddata_session.add(fit)
        eos.db.saveddata_session.flush()
        service.getFit(fit.ID)
        service.fill(fit.ID); service.recalc(fit.ID)
        return fit

    def observe(fit):
        service.recalc(fit.ID)
        stats = snapshot(fit)
        stats['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        return {'modules': [{'index': i, 'id': m.itemID, 'name': m.item.name if m.item else None,
                    'slot': FittingSlot(m.slot).name, 'state': FittingModuleState(m.state).name,
                    'charge_id': m.chargeID, 'charge': m.charge.name if m.charge else None,
                    'charge_amount': m.numCharges, 'legal': None if m.isEmpty else m.fits(fit)}
                   for i,m in enumerate(fit.modules)],
                'cargo': [{'id': c.itemID, 'name': c.item.name, 'amount': c.amount,
                           'unit_volume_m3': c.getModifiedItemAttr('volume')} for c in fit.cargo],
                'used_m3': fit.cargoBayUsed, 'capacity_m3': fit.ship.getModifiedItemAttr('capacity'),
                'stats': stats, 'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'])}

    cases = []
    for case in json.loads((ROOT / 'tools/android_reference/cargo-transfers.json').read_text()):
        fit = make_fit(case)
        steps = [{'operation': None, 'changed': None, 'result': observe(fit)}]
        for operation in case['operations']:
            resolved = {**operation, 'cargo_item_id': item(operation['cargo']).ID if operation['cargo'] else None}
            changed = oracle['run'](fit, resolved)
            steps.append({'operation': resolved, 'changed': changed, 'result': observe(fit)})
        cases.append({**case, 'steps': steps})
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
            'database_logical_sha256': logical_database_digest(database),
            'eos_settings': dict(configuration.settings), 'cases': cases,
            'command': 'Unchanged original GuiCargoToLocalModuleCommand and GuiLocalModuleToCargoCommand with real wx internal history.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'database', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    args.source, args.database, args.output = (
        args.source.resolve(), args.database.resolve(strict=True), args.output.resolve())
    validate_source(args.source)
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    if args.worker:
        args.output.write_text(json.dumps(export(args.source, args.database), indent=2,
                                          allow_nan=False) + '\n', encoding='utf-8')
        return
    if args.output.is_relative_to(ROOT):
        raise ValueError('Use a new output outside checkout')
    baseline = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())
    compare(baseline['database_logical_sha256'], logical_database_digest(args.database))
    before = digest_file(args.database)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ('cargo-transfers', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--source', str(args.source), '--database', str(args.database),
                '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'cargo-transfers.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    print(json.dumps({'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases']),
        'source_commit': actual['source_commit'], 'repeated': True}))


if __name__ == '__main__':
    main()
