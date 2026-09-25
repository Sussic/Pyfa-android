"""Export B05.4 states from original pinned selection and bulk commands."""
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
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.bulk_edit_oracle import load

    oracle = load(source)
    service, market = oracle['service'], Market.getInstance()
    market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'] = []

    def make_fit(case):
        fit = Fit(Ship(eos.db.getItem(case['ship'])), name=case['name'])
        fit.character = Character('Independent all V', defaultLevel=5)
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25,
                                          kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity = FitSystemSecurity.HISEC, 0.0
        fit.ignoreRestrictions = case.get('ignore_restrictions', False)
        for row in case.get('modules', []):
            value = eos.db.getItem(row['name'])
            charge = eos.db.getItem(row['charge']) if row.get('charge') else None
            assert value is not None and (not row.get('charge') or charge is not None)
            fit.modules.append(oracle['ModuleInfo'](value.ID, state=FittingModuleState[row['state']],
                               chargeID=charge.ID if charge else None).toModule())
        eos.db.saveddata_session.add(fit)
        eos.db.saveddata_session.flush()
        service.getFit(fit.ID)
        service.fill(fit.ID)
        assert all(module.isEmpty or module.fits(fit) for module in fit.modules), case['name']
        return fit

    def report(fit, recipients):
        if not fit.calculated:
            fit.calculateModifiedAttributes()
        def stats(value):
            if not value.calculated:
                value.calculateModifiedAttributes()
            result = snapshot(value)
            result['scan_resolution'] = {
                'value': value.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
            return result
        return {'stats': stats(fit),
                'modules': [{'index': i, 'id': module.itemID, 'slot': FittingSlot(module.slot).name,
                             'state': FittingModuleState(module.state).name,
                             'charge_id': module.chargeID}
                            for i, module in enumerate(fit.modules) if not module.isEmpty],
                'free_slots': {slot.name: fit.getSlotsFree(slot.value) for slot in (
                    FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH,
                    FittingSlot.RIG, FittingSlot.SERVICE)},
                'recipients': [{'name': target.name, 'stats': stats(target)} for target in recipients],
                'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'])}

    cases = []
    for case in json.loads((ROOT / 'tools/android_reference/bulk-variation-removal.json').read_text()):
        fit = make_fit(case)
        recipients = []
        for row in case.get('recipients', []):
            target = make_fit(row)
            target.projectedFitDict[fit.ID] = fit
            eos.db.saveddata_session.flush()
            eos.db.saveddata_session.refresh(fit)
            info = fit.getProjectionInfo(target.ID)
            info.projectionRange, info.active, info.amount = 0.0, True, 1
            service.recalc(fit); service.recalc(target)
            recipients.append(target)
        steps = [{'input': None, 'positions': [], 'changed': False,
                  'result': report(fit, recipients)}]
        for operation in case['operations']:
            kind, main, selected, scope = operation[:4]
            value = eos.db.getItem(operation[4]) if kind.startswith('variation') else None
            if kind == 'variation':
                assert value is not None
                assert any(row['id'] == value.ID for row in oracle['choices'](
                    fit, fit.modules[main].item, 'module'))
            result = oracle['bulk_run'](fit, kind, main, selected, scope,
                                        value.ID if value else None)
            steps.append({'input': {'kind': kind, 'main_position': main,
                                    'selected_positions': selected, 'scope': scope,
                                    'item_id': value.ID if value else None},
                          'positions': result['positions'], 'changed': result['changed'],
                          'result': report(fit, recipients)})
        cases.append({**case, 'steps': steps})
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
            'eos_settings': dict(configuration.settings), 'cases': cases,
            'selection': 'Original itemVariationChange/RemoveItem handlers and GUI bulk commands.'}


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
    for name in ('bulk-variation-removal', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--source', str(args.source), '--database', str(args.database),
                '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'bulk-variation-removal.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    print(json.dumps({'cases': len(actual['cases']),
        'states': sum(len(c['steps']) for c in actual['cases']),
        'source_commit': actual['source_commit'], 'repeated': True}))


if __name__ == '__main__':
    main()
