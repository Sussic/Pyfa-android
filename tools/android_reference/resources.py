"""C01.1 independent EOS resource values and original desktop presentation."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT, DEPENDENCIES, bootstrap,
    compare, digest_file, logical_database_digest, validate_source)


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.ship import Ship
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.drone import Drone
    from eos.saveddata.fighter import Fighter
    from eos.saveddata.cargo import Cargo
    from eos.saveddata.damagePattern import DamagePattern
    from tools.android_reference.resource_view_oracle import load
    oracle = load(source)
    base = deepcopy(json.loads((ROOT/'tools/android_reference/vexor.json').read_text()))
    del base['edit']
    base.update(modules=[], drones=[], ignore_restrictions=False, cargo=[])
    cases = []
    def add(name, ship='Vexor', modules=(), drones=(), cargo=(), fighters=(), override=False, ephemeral=False):
        spec = deepcopy(base)
        spec.update(name=name, ship=ship, modules=list(modules), drones=list(drones),
                    cargo=list(cargo), ignore_restrictions=override)
        cases.append(dict(spec=spec, fighters=list(fighters), execution='ephemeral' if ephemeral or fighters else 'durable'))
    def module(name, state='ACTIVE', charge=None):
        return dict(name=name, state=state, charge=charge)
    add('Empty cruiser')
    add('Fitted cruiser', modules=[module('Dual 150mm Railgun II', charge='Antimatter Charge M')]*2,
        drones=[dict(name='Hammerhead II', amount=5, active=3)],
        cargo=[dict(name='Antimatter Charge M', amount=400)])
    add('Offline guns', modules=[module('Dual 150mm Railgun II', 'OFFLINE')]*2)
    add('Turret and fitting overload', modules=[module('Tachyon Beam Laser II')]*10, override=True, ephemeral=True)
    add('Launcher overload', ship='Caracal', modules=[module('Heavy Missile Launcher II')]*6, override=True, ephemeral=True)
    add('CPU overload', modules=[module('X-Large Shield Booster II')]*4, override=True)
    add('Calibration overload', modules=[module('Medium Cargohold Optimization II', 'ONLINE')]*3, override=True)
    add('Drone count overload', drones=[dict(name='Hobgoblin II', amount=6, active=6)])
    add('Drone bay and bandwidth overload', drones=[dict(name='Ogre II', amount=20, active=5)])
    add('Cargo overload', cargo=[dict(name='Antimatter Charge M', amount=100000)])
    add('Empty carrier', ship='Thanatos')
    add('Carrier squadrons', ship='Thanatos', fighters=[dict(name='Firbolg I', amount=9, active=True),
        dict(name='Firbolg I', amount=4, active=False)])
    add('Fighter tube and bay overload', ship='Thanatos',
        fighters=[dict(name='Firbolg I', amount=6, active=True)]*20)
    add('Empty structure', ship='Astrahus')
    try:
        for row in cases:
            spec = row['spec']; item = eos.db.getItem(spec['ship'])
            fit = Fit(Citadel(item) if item.category.name == 'Structure' else Ship(item), name=spec['name'])
            fit.character = Character('Independent resource skills', defaultLevel=spec['skill_level'])
            fit.damagePattern = DamagePattern(**spec['damage_pattern'])
            fit.factorReload, fit.targetProfile, fit.implantLocation = spec['factor_reload'], None, ImplantLocation.FIT
            fit.systemSecurity = FitSystemSecurity[spec['security']['system']]
            fit.pilotSecurity, fit.ignoreRestrictions = spec['security']['pilot'], spec['ignore_restrictions']
            for value in spec['modules']:
                m = Module(eos.db.getItem(value['name'])); m.state = FittingModuleState[value['state']]
                if value['charge']: m.charge = eos.db.getItem(value['charge'])
                fit.modules.append(m)
            for value in spec['drones']:
                d = Drone(eos.db.getItem(value['name'])); d.amount, d.amountActive = value['amount'], value['active']
                fit.drones.append(d)
            for value in spec['cargo']:
                c = Cargo(eos.db.getItem(value['name'])); c.amount = value['amount']; fit.cargo.append(c)
            for value in row['fighters']:
                f = Fighter(eos.db.getItem(value['name'])); f.amount, f.active = value['amount'], value['active']
                fit.fighters.append(f)
            eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush()
            fit.calculateModifiedAttributes()
            row['resources'] = oracle['observe'](fit)
            assert len(row['resources']) == 11
        overloaded = {name for row in cases for name, value in row['resources'].items() if value['overloaded']}
        assert overloaded == {'turret_hardpoints','launcher_hardpoints','active_drones','fighter_tubes',
                              'calibration','cpu','powergrid','drone_bay','fighter_bay','drone_bandwidth','cargo_bay'}
        assert not any(n.startswith('android_bridge') for n in sys.modules)
        for name, mod in list(sys.modules.items()):
            if name.split('.')[0] in ('eos','service','gui','config') and getattr(mod,'__file__',None):
                assert Path(mod.__file__).resolve().is_relative_to(source), name
        return dict(task='C01.1', source_commit=SOURCE_COMMIT, eos_settings=dict(configuration.settings),
                    desktop_resource_view_sha256=oracle['source_sha256'], cases=cases)
    finally:
        oracle['close']()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--check', type=Path); parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    args.source, args.database, args.output = args.source.resolve(), args.database.resolve(strict=True), args.output.resolve()
    validate_source(args.source)
    compare(DEPENDENCIES, {n:importlib.metadata.version(n) for n in DEPENDENCIES})
    if args.worker:
        args.output.write_text(json.dumps(export(args.source,args.database),indent=2,allow_nan=False)+'\n',encoding='utf-8')
        return
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError('Use a new external output and retained input database')
    baseline=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text())
    compare(baseline['database_logical_sha256'],logical_database_digest(args.database))
    before=digest_file(args.database); args.output.mkdir(parents=True,exist_ok=False)
    for name in ('resources','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),
                '--database',str(args.database),'--output',str(args.output/(name+'.json')),'--worker'],
                cwd=args.source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    actual=json.loads((args.output/'resources.json').read_text())
    compare(actual,json.loads((args.output/'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()),actual)
    compare(before,digest_file(args.database)); validate_source(args.source)
    receipt=dict(task='C01.1',source_commit=SOURCE_COMMIT,database_sha256=before,
        database_logical_sha256=baseline['database_logical_sha256'],fresh_process_repeat=True,
        game_database_unchanged=True,cases=len(actual['cases']),resource_pairs=11,
        reference_sha256=digest_file(args.output/'resources.json'))
    (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__': main()
