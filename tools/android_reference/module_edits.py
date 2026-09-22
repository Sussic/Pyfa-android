"""Independent B04.2.2 original desktop command/state/legality reference."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (
    SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare, digest_file,
    logical_database_digest, snapshot, validate_source)


def export(source, database):
    configuration = bootstrap(source, database)
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FitSystemSecurity, ImplantLocation, FittingModuleState, FittingSlot, FittingHardpoint
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.module_oracle import load
    oracle = load(source)
    service, market = oracle['service'], Market.getInstance()
    recent_key = 'pyfaMarketRecentlyUsedModules'

    def recent():
        return list(market.serviceMarketRecentlyUsedModules[recent_key])

    def observation(fit):
        stats = snapshot(fit)
        stats['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        def requirements(values):
            return [{'id': id, 'name': name, 'required': level,
                     'actual': fit.character.getSkill(id).level, 'requirements': requirements(children)}
                    for name, (level, id, children) in sorted(values.items())]
        warnings = [{'id': item.ID, 'name': item.name, 'requirements': requirements(values)}
                    for item, values in sorted(oracle['requirements'].checkRequirements(fit).items(), key=lambda pair: pair[0].ID)]
        resources = {}
        for key, used, total, unit in (
                ('cpu', fit.cpuUsed, fit.ship.getModifiedItemAttr('cpuOutput'), 'tf'),
                ('powergrid', fit.pgUsed, fit.ship.getModifiedItemAttr('powerOutput'), 'MW'),
                ('calibration', fit.calibrationUsed, fit.ship.getModifiedItemAttr('upgradeCapacity'), 'points')):
            resources[key] = {'used': used, 'total': total, 'unit': unit, 'overloaded': used > total}
        slots = [{'slot': slot.name, 'used': fit.getSlotsUsed(slot.value), 'total': fit.getNumSlots(slot.value)}
                 for slot in (FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH, FittingSlot.RIG, FittingSlot.SERVICE)]
        hardpoints = [{'kind': kind.name, 'used': fit.getHardpointsUsed(kind),
                       'total': fit.ship.getModifiedItemAttr(attribute)} for kind, attribute in (
                           (FittingHardpoint.TURRET, 'turretSlotsLeft'), (FittingHardpoint.MISSILE, 'launcherSlotsLeft'))]
        modules = [{'index': index, 'id': module.itemID, 'name': module.item.name if module.item else None,
                    'slot': FittingSlot(module.slot).name, 'state': FittingModuleState(module.state).name,
                    'charge': module.charge.name if module.charge else None,
                    'legal': None if module.isEmpty else module.fits(fit),
                    'overridden': bool(fit.ignoreRestrictions and getattr(module, 'restrictionOverridden', False))}
                   for index, module in enumerate(fit.modules)]
        return {'modules': modules, 'ignore_restrictions': fit.ignoreRestrictions,
                'resources': resources, 'slots': slots, 'hardpoints': hardpoints,
                'skill_warnings': warnings, 'stats': stats, 'recent': recent()}

    def make_fit(case):
        item = eos.db.getItem(case['ship'])
        fit = Fit(Citadel(item) if item.category.name == 'Structure' else Ship(item), name=case['name'])
        fit.character = Character('Independent synthetic skills', defaultLevel=case['skills'])
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity, fit.ignoreRestrictions = FitSystemSecurity.HISEC, 0.0, False
        for row in case.get('modules', []):
            info = oracle['ModuleInfo'](eos.db.getItem(row['name']).ID,
                chargeID=eos.db.getItem(row['charge']).ID if row.get('charge') else None,
                state=FittingModuleState[row['state']])
            fit.modules.append(info.toModule())
        eos.db.saveddata_session.add(fit)
        eos.db.saveddata_session.flush()
        service.getFit(fit.ID)  # The original desktop initializes and fills it.
        return fit

    cases = []
    inputs = json.loads((ROOT / 'tools/android_reference/module-edits.json').read_text())
    market.serviceMarketRecentlyUsedModules[recent_key] = []
    for case in inputs:
        fit = make_fit(case)
        recipients = []
        for recipient in case.get('recipients', []):
            target = make_fit({**recipient, 'skills': 5})
            target.projectedFitDict[fit.ID] = fit
            eos.db.saveddata_session.flush()
            eos.db.saveddata_session.refresh(fit)
            info = fit.getProjectionInfo(target.ID)
            info.projectionRange, info.active, info.amount = 0.0, True, 1
            service.recalc(fit)
            service.recalc(target)
            recipients.append(target)

        def report():
            result = observation(fit)
            result['recipients'] = []
            for target in recipients:
                if not target.calculated:
                    target.calculateModifiedAttributes()
                stats = snapshot(target)
                stats['scan_resolution'] = {'value': target.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
                result['recipients'].append({'name': target.name, 'stats': stats})
            return result

        rows = [{'input': None, 'accepted': True, 'result': report()}]
        for operation in case['operations']:
            name, *args, accepted = operation
            if name in ('add', 'replace'):
                item = eos.db.getItem(args[-1])
                if item is None:
                    raise ValueError('Unknown reference item: ' + args[-1])
                info = oracle['ModuleInfo'](item.ID)
                command = (oracle['commands']['localAdd'](fit.ID, info) if name == 'add'
                           else oracle['commands']['localReplace'](fit.ID, args[0], info))
                success = command.Do()
                # Original GUI add/replace stores even an unsuccessful attempt.
                market.storeRecentlyUsed(item.ID)
                if command.needsGuiRecalc:
                    eos.db.saveddata_session.flush()
                    service.recalc(fit)
            elif name == 'remove':
                command = oracle['commands']['localRemove'](fit.ID, [args[0]])
                success = command.Do()
                for container in (command.savedSubInfos, command.savedModInfos):
                    for position in sorted(container, reverse=True):
                        market.storeRecentlyUsed(container[position].itemID)
                if command.needsGuiRecalc:
                    eos.db.saveddata_session.flush()
                    service.recalc(fit)
            elif name == 'restrictions':
                # Audited GUI toggle orchestration; individual removals, state
                # checks and all legality are the unchanged original commands.
                fit.ignoreRestrictions = args[0]
                if not fit.ignoreRestrictions:
                    for position, module in reversed(list(enumerate(fit.modules))):
                        if not module.isEmpty and not module.fits(fit, hardpointLimit=False):
                            assert oracle['commands']['localRemove'](fit.ID, [position]).Do()
                eos.db.saveddata_session.flush()
                service.recalc(fit)
                success = True
            else:
                raise ValueError(name)
            if success is not accepted:
                raise AssertionError((case['name'], operation, success))
            service.fill(fit)
            eos.db.saveddata_session.commit()
            rows.append({'input': operation[:-1], 'accepted': success, 'result': report()})
        cases.append({'name': case['name'], 'ship': case['ship'], 'skill_level': case['skills'],
                      'initial_modules': case.get('modules', []), 'recipients': case.get('recipients', []), 'steps': rows})

    catalogue = json.loads((ROOT / 'tools/android_reference/fixtures/equipment.json').read_text())['catalog']['items']
    states = []
    for row in catalogue:
        if row['category'] not in ('Module', 'Structure Module'):
            continue
        info = oracle['ModuleInfo'](row['id'])
        limit = oracle['activeStateLimit'](row['id'])
        module = info.toModule(fallbackState=limit)
        if module is not None and module.slot in (1, 2, 3, 4, 8):
            states.append({'id': row['id'], 'name': row['name'], 'slot': FittingSlot(module.slot).name,
                           'limit': FittingModuleState(limit).name, 'state': FittingModuleState(module.state).name})
    market.serviceMarketRecentlyUsedModules[recent_key] = []
    history_inputs = [row['id'] for row in states[:22]] + [states[2]['id'], states[2]['id']]
    abyssal = next(item for item in eos.db.getItemsByCategory('Module') if item.isAbyssal)
    history_inputs.append(abyssal.ID)
    history = []
    for id in history_inputs:
        market.storeRecentlyUsed(id)
        history.append({'id': id, 'result': recent()})
    assert len(recent()) == 20 and abyssal.ID not in recent()
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
            'eos_settings': dict(configuration.settings), 'cases': cases, 'default_states': states,
            'recent_history': history, 'abyssal_id': abyssal.ID,
            'inputs': {'factor_reload': False, 'system_security': 'HISEC', 'pilot_security': 0.0,
                       'uniform_damage': [25, 25, 25, 25], 'drones': [], 'implants': [], 'boosters': [],
                       'projections': [], 'commands': [], 'environments': []}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('source', 'database', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
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
    for name in ('modules', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', str(args.source),
                '--database', str(args.database), '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
    actual = json.loads((args.output / 'modules.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database))
    validate_source(args.source)
    receipt = {'task': 'B04.2.2', 'source_commit': SOURCE_COMMIT, 'dependencies': DEPENDENCIES,
        'database_logical_sha256': baseline['database_logical_sha256'], 'database_sha256': before,
        'fresh_process_repeat': True, 'game_database_unchanged': True,
        'reference_sha256': digest_file(args.output / 'modules.json'), 'cases': len(actual['cases']),
        'steps': sum(len(case['steps']) for case in actual['cases']), 'default_states': len(actual['default_states'])}
    (args.output / 'evidence.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
