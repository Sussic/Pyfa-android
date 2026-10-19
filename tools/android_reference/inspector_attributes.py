#!/usr/bin/env python3
"""Independent pinned inspector expectations and separate adapter comparison."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, bootstrap, compare, logical_database_digest, validate_source


def contexts(fit):
    result = [('ship', fit.ship, fit.ship.item, False)]
    for module in fit.modules:
        if module.item is None:
            continue
        result.append(('module', module, module.item, False))
        if module.charge is not None:
            result.append(('charge', module, module.charge, True))
    result.extend(('drone', drone, drone.item, False) for drone in fit.drones)
    result.extend(('fighter', fighter, fighter.item, False) for fighter in fit.fighters)
    result.extend(('cargo', cargo, cargo.item, False) for cargo in fit.cargo)
    items = {item.ID: item for _, _, item, _ in result}
    result.extend(('base', None, item, False) for item in items.values())
    return result


def export(source, database):
    validate_source(source)
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.drone import Drone
    from eos.saveddata.fighter import Fighter
    from eos.saveddata.cargo import Cargo
    from eos.saveddata.targetProfile import TargetProfile
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship
    from eos.saveddata.citadel import Citadel
    from tools.android_reference.inspector_attribute_oracle import load
    from tools.android_reference.inspector_equipment_oracle import load as equipment_oracle
    oracle = load(source)
    observe_equipment = equipment_oracle(source)
    spec = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text(encoding='utf-8'))
    spec.pop('edit')
    specifications = [spec]
    output = json.loads((ROOT / 'tools/android_reference/fixtures/output.json').read_text(encoding='utf-8'))
    compare(SOURCE_COMMIT, output['source_commit'])
    compare(output['eos_settings'], dict(configuration.settings))
    specifications.extend(row['spec'] for row in output['cases'])
    def make(spec):
        item = eos.db.getItem(spec['ship'])
        fit = Fit(Ship(item) if item.category.name == 'Ship' else Citadel(item), name=spec['name'])
        fit.character = Character('Independent inspector skills', defaultLevel=spec['skill_level'])
        fit.damagePattern = DamagePattern(**spec['damage_pattern'])
        fit.factorReload = spec['factor_reload']
        fit.targetProfile = None if spec['target_profile'] is None else TargetProfile(**spec['target_profile'])
        fit.implantLocation = ImplantLocation.FIT
        fit.systemSecurity = FitSystemSecurity[spec['security']['system']]
        fit.pilotSecurity = spec['security']['pilot']
        fit.ignoreRestrictions = spec.get('ignore_restrictions', False)
        for row in spec['modules']:
            module = Module(eos.db.getItem(row['name']))
            module.state = FittingModuleState[row['state']]
            if row.get('charge'):
                module.charge = eos.db.getItem(row['charge'])
            fit.modules.append(module)
        for row in spec['drones']:
            drone = Drone(eos.db.getItem(row['name']))
            drone.amount, drone.amountActive = row['amount'], row['active']
            fit.drones.append(drone)
        for row in spec.get('fighters', []):
            fighter = Fighter(eos.db.getItem(row['name']))
            fighter.amount, fighter.active = row['amount'], row['active']
            fit.fighters.append(fighter)
        for row in spec.get('cargo', []):
            cargo = Cargo(eos.db.getItem(row['name']))
            cargo.amount = row['amount']
            fit.cargo.append(cargo)
        for row in spec['environments']:
            environment = Module(eos.db.getItem(row['name']))
            environment.state = FittingModuleState[row['state']]
            fit.projectedModules.append(environment)
        eos.db.saveddata_session.add(fit)
        eos.db.saveddata_session.flush()
        fit.calculateModifiedAttributes()
        if not fit.fits:
            raise ValueError('Invalid independent inspector fit: ' + spec['name'])
        return fit

    from tools.android_reference.inspector_cases import specifications as family_specs
    additions, coverage = family_specs(source, database, specifications[0], make)
    specifications.extend(additions)
    cases = []
    for spec in specifications:
        fit = make(spec)
        targets = [dict(context=context, item_id=item.ID,
                        expected=oracle['observe'](stuff, item, charge),
                        equipment=observe_equipment(stuff, fit))
                   for context, stuff, item, charge in contexts(fit)]
        cases.append(dict(spec=spec, targets=targets))
    if any(name.startswith('android_bridge') for name in sys.modules):
        raise ValueError('Android implementation imported into independent inspector exporter')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source):
                raise ValueError('Inspector reference imported outside the pinned source: ' + name)
    return dict(schema=2, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(configuration.settings), family_selection=coverage, cases=cases)


def verify(database, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit'])
    compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    from android_bridge import HeadlessEngine
    from android_bridge.inspection import attributes, equipment
    engine = HeadlessEngine(database)
    compare(fixture['eos_settings'], engine.settings)
    count, targets = 0, 0
    for case in fixture['cases']:
        fit = engine.create_fit(case['spec'])
        current = contexts(fit)
        compare([(context, item.ID) for context, _, item, _ in current],
                [(row['context'], row['item_id']) for row in case['targets']])
        targets += len(current)
        for (_, stuff, item, charge), expected in zip(current, case['targets']):
            compare(expected['equipment'], equipment(stuff, fit), item.name + '.equipment')
            actual = attributes(stuff, item, charge)
            rows = {row['name']: row for row in actual['rows']}
            compare(expected['expected']['precise'], [
                {key: row[key] for key in ('name', 'id', 'current', 'base', 'unit')}
                for row in actual['rows']], item.name + '.precise')
            for mode in ('normal', 'raw'):
                observed = [dict(name=entry['name'], groups=entry['groups'], label=entry['label'],
                                 current=rows[entry['name']]['raw_current' if mode == 'raw' else 'display_current'],
                                 base=rows[entry['name']]['raw_base' if mode == 'raw' else 'display_base'])
                            for entry in actual[mode]]
                compare(expected['expected'][mode], observed, item.name + '.' + mode)
                count += len(observed)
    print(f'PASS: {len(fixture["cases"])} cases, {targets} independent targets, {count} ordered normal/raw attribute rows and original equipment columns')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    args = parser.parse_args()
    if args.action == 'export':
        if args.source is None:
            parser.error('export requires --source')
        result = export(args.source.resolve(), args.database.resolve())
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["cases"])} pinned desktop cases')
    else:
        verify(args.database.resolve(), json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__':
    main()
