#!/usr/bin/env python3
"""Independent original affector trees for every existing inspector fit/target."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, bootstrap, compare, logical_database_digest, validate_source
from tools.android_reference.inspector_attributes import contexts


def export(source, database, attributes, observer_factory=None, character_name='Independent inspector skills'):
    validate_source(source)
    configuration = bootstrap(source, database); configuration.gamedataCache = False
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
    from tools.android_reference.inspector_affector_oracle import load
    observe = (observer_factory or load)(source)
    cases = []
    for case in attributes['cases']:
        spec = case['spec']; item = eos.db.getItem(spec['ship'])
        fit = Fit(Ship(item) if item.category.name == 'Ship' else Citadel(item), name=spec['name'])
        fit.character = Character(character_name, defaultLevel=spec['skill_level'])
        fit.damagePattern = DamagePattern(**spec['damage_pattern']); fit.factorReload = spec['factor_reload']
        fit.targetProfile = None if spec['target_profile'] is None else TargetProfile(**spec['target_profile'])
        fit.implantLocation = ImplantLocation.FIT; fit.systemSecurity = FitSystemSecurity[spec['security']['system']]
        fit.pilotSecurity = spec['security']['pilot']; fit.ignoreRestrictions = spec.get('ignore_restrictions', False)
        for row in spec['modules']:
            module = Module(eos.db.getItem(row['name'])); module.state = FittingModuleState[row['state']]
            if row.get('charge'): module.charge = eos.db.getItem(row['charge'])
            fit.modules.append(module)
        for row in spec['drones']:
            drone = Drone(eos.db.getItem(row['name'])); drone.amount, drone.amountActive = row['amount'], row['active']
            fit.drones.append(drone)
        for row in spec.get('fighters', []):
            fighter = Fighter(eos.db.getItem(row['name'])); fighter.amount, fighter.active = row['amount'], row['active']
            fit.fighters.append(fighter)
        for row in spec.get('cargo', []):
            cargo = Cargo(eos.db.getItem(row['name'])); cargo.amount = row['amount']; fit.cargo.append(cargo)
        for row in spec['environments']:
            environment = Module(eos.db.getItem(row['name'])); environment.state = FittingModuleState[row['state']]
            fit.projectedModules.append(environment)
        eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush(); fit.calculateModifiedAttributes()
        if not fit.fits: raise ValueError('Invalid original inspector fit: ' + spec['name'])
        current = contexts(fit)
        compare([(row['context'], row['item_id']) for row in case['targets']], [(kind, item.ID) for kind, _, item, _ in current])
        cases.append(dict(spec=spec, targets=[dict(context=kind, item_id=item.ID, expected=observe(stuff, item, fit))
                                             for kind, stuff, item, charge in current]))
    if any(name.startswith('android_bridge') for name in sys.modules): raise ValueError('Android imported by original affector oracle')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source): raise ValueError('Reference imported outside pinned source: ' + name)
    return dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(configuration.settings), cases=cases)


def flatten(nodes, path=()):
    result = []
    for node in nodes:
        current = [*path, node['label']]
        result.append(dict(path=current, alternate=node['alternate']))
        result.extend(flatten(node['children'], current))
    return result


def verify(database, attributes, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit']); compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    compare([row['spec'] for row in attributes['cases']], [row['spec'] for row in fixture['cases']])
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database); compare(fixture['eos_settings'], engine.settings)
    from android_bridge.inspection_affectors import views
    count = 0
    for case in fixture['cases']:
        fit = engine.create_fit(case['spec']); current = contexts(fit)
        compare([(row['context'], row['item_id']) for row in case['targets']], [(kind, item.ID) for kind, _, item, _ in current])
        for (kind, stuff, item, charge), expected in zip(current, case['targets']):
            actual = {key: flatten(nodes) for key, nodes in views(stuff, item, fit).items()}
            compare(expected['expected'], actual, case['spec']['name'] + '.' + kind + '.' + item.name)
            count += sum(len(nodes) for nodes in actual.values())
    print(f'PASS: {len(fixture["cases"])} original affector cases and {count} complete source/attribute tree rows')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify')); parser.add_argument('--source', type=Path)
    parser.add_argument('--database', required=True, type=Path); parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--attributes', type=Path, default=ROOT / 'tools/android_reference/fixtures/inspector-attributes.json')
    args = parser.parse_args(); attributes = json.loads(args.attributes.read_text(encoding='utf-8'))
    compare(SOURCE_COMMIT, attributes['sourceCommit']); compare(logical_database_digest(args.database.resolve()), attributes['databaseLogicalSha256'])
    if args.action == 'export':
        if args.source is None: parser.error('export requires --source')
        result = export(args.source.resolve(), args.database.resolve(), attributes)
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["cases"])} complete original affector cases')
    else: verify(args.database.resolve(), attributes, json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
