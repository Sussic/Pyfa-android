"""C01.3.2 independent pinned desktop tank simulation and presentation."""
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
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.damagePattern import DamagePattern
    from tools.android_reference.tank_view_oracle import load
    oracle = load(source)
    base = deepcopy(json.loads((ROOT/'tools/android_reference/vexor.json').read_text(encoding='utf-8')))
    del base['edit']
    base.update(modules=[], drones=[], ignore_restrictions=False, cargo=[])
    def module(name, state='ACTIVE', charge=None): return dict(name=name,state=state,charge=charge)
    def spec(name, modules=()): return {**deepcopy(base),'name':name,'modules':list(modules)}
    cases = [dict(spec=spec('Empty tank'))]
    for label, name in [('Shield', 'Large Shield Booster II'), ('Armor', 'Medium Armor Repairer II'), ('Hull', 'Medium Hull Repairer II')]:
        for state in ('ACTIVE', 'ONLINE', 'OFFLINE'):
            cases.append(dict(spec=spec(label+' '+state,[module(name,state)])))
    cases.extend([
        dict(spec=spec('Passive shield modules',[module('Large Shield Extender II','ONLINE'),module('Shield Power Relay II','ONLINE')])),
        dict(spec=spec('Cap limited repairs',[module('10MN Afterburner II'),module('Medium Armor Repairer II'),module('Medium Armor Repairer II')])),
        dict(spec=spec('Battery repairs',[module('Large Cap Battery II','ONLINE'),module('Medium Armor Repairer II')])),
        dict(spec=spec('Ancillary armor',[module('Medium Ancillary Armor Repairer',charge='Nanite Repair Paste')])),
        dict(spec=spec('Ancillary shield',[module('Large Ancillary Shield Booster',charge='Cap Booster 150')]))])
    reload_case=deepcopy(cases[-1]);reload_case['spec']['name']='Ancillary shield reload';reload_case['spec']['factor_reload']=True
    cases.append(reload_case)
    reload_case=deepcopy(cases[-3]);reload_case['spec']['name']='Ancillary armor reload';reload_case['spec']['factor_reload']=True
    cases.append(reload_case)
    for label, name in [('Shield', 'Medium Remote Shield Booster II'), ('Armor', 'Medium Remote Armor Repairer II'),
                        ('Hull', 'Medium Remote Hull Repairer II'), ('Spool', 'Heavy Mutadaptive Remote Armor Repairer II')]:
        for active in (True,False):
            cases.append(dict(spec=spec('Projected '+label+(' active' if active else ' inactive')),
                source=spec(label+' repair source',[module(name)]),projection=dict(range_m=0.0,active=active,amount=1)))
    for label, distance, quantity in [('falloff', 20000.0, 1),('out of range', 10000000.0, 1),('two sources', 0.0, 2)]:
        cases.append(dict(spec=spec('Spool '+label),source=spec('Spool '+label+' source',[module('Heavy Mutadaptive Remote Armor Repairer II')]),
            projection=dict(range_m=distance,active=True,amount=quantity)))
    # The mutadaptive repairer has zero falloff. Use the ordinary armor repairer
    # at its actual all-V Vexor optimal (10500 m) plus falloff (3000 m).
    cases[25] = dict(spec=spec('Projected Armor falloff'),
        source=spec('Armor falloff source',[module('Medium Remote Armor Repairer II')]),
        projection=dict(range_m=13500.0,active=True,amount=1))
    mixed=deepcopy(cases[1]);mixed['spec']['name']='Shield mixed incoming';mixed['spec']['damage_pattern']=dict(emAmount=3,thermalAmount=7,kineticAmount=11,explosiveAmount=19)
    cases.append(mixed)
    for row in cases:
        if 'source' in row:
            row['source']['name'] = row['spec']['name'] + ' source'
            if any('Mutadaptive' in m['name'] for m in row['source']['modules']):
                row['source']['ship'] = 'Rodiva'
    def make(value):
        fit=Fit(Ship(eos.db.getItem(value['ship'])),name=value['name'])
        fit.character=Character('Independent tank skills',defaultLevel=value['skill_level'])
        fit.damagePattern=DamagePattern(**value['damage_pattern'])
        fit.factorReload,fit.targetProfile,fit.implantLocation=value['factor_reload'],None,ImplantLocation.FIT
        fit.systemSecurity=FitSystemSecurity[value['security']['system']];fit.pilotSecurity=value['security']['pilot']
        for row in value['modules']:
            item=eos.db.getItem(row['name'])
            if item is None: raise ValueError('Unknown reference module '+row['name'])
            m=Module(item);m.state=FittingModuleState[row['state']]
            if row['charge']:
                charge=eos.db.getItem(row['charge'])
                if charge is None or not m.isValidCharge(charge): raise ValueError('Invalid reference charge '+row['charge'])
                m.charge=charge
            fit.modules.append(m)
        eos.db.saveddata_session.add(fit);eos.db.saveddata_session.flush();fit.calculateModifiedAttributes()
        if not fit.fits:
            restrictions={m.item.name: {key: eos.db.getItem(int(attr.value)).name if key.startswith('canFitShipType') else attr.value
                for key,attr in m.item.attributes.items() if key.startswith(('canFitShip','fitsToShip'))}
                for m in fit.modules}
            raise ValueError('Invalid independent tank equipment '+value['name']+' '+repr(restrictions))
        return fit
    try:
        for row in cases:
            fit=make(row['spec'])
            if 'source' in row:
                sender=make(row['source']);fit.projectedFitDict[sender.ID]=sender
                eos.db.saveddata_session.flush();eos.db.saveddata_session.refresh(sender)
                sender.clear();sender.calculateModifiedAttributes()
                info=sender.getProjectionInfo(fit.ID)
                info.projectionRange,info.active,info.amount=row['projection']['range_m'],row['projection']['active'],row['projection']['amount']
                fit.clear();fit.calculateModifiedAttributes()
            row['expected']=oracle['observe'](fit)
        assert any(r['expected']['tank']['raw']['reinforced']['armor_spool']['indicated'] for r in cases)
        assert any(r['expected']['tank']['raw']['reinforced']['repairs']['armorRepair']['value'] > r['expected']['tank']['raw']['sustained']['repairs']['armorRepair']['value'] for r in cases)
        assert 0 < cases[25]['expected']['tank']['raw']['reinforced']['repairs']['armorRepair']['value'] < cases[19]['expected']['tank']['raw']['reinforced']['repairs']['armorRepair']['value']
        assert not any(n.startswith('android_bridge') for n in sys.modules)
        for name,mod in list(sys.modules.items()):
            if name.split('.')[0] in ('eos','service','gui','config') and getattr(mod,'__file__',None):
                assert Path(mod.__file__).resolve().is_relative_to(source),name
        return dict(task='C01.3.2',source_commit=SOURCE_COMMIT,eos_settings=dict(configuration.settings),
            desktop_tank_view_sha256=oracle['source_sha256'],cases=cases)
    finally: oracle['close']()

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
    for name in ('tank','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),
                '--database',str(args.database),'--output',str(args.output/(name+'.json')),'--worker'],
                cwd=args.source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    actual=json.loads((args.output/'tank.json').read_text())
    compare(actual,json.loads((args.output/'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()),actual)
    compare(before,digest_file(args.database)); validate_source(args.source)
    receipt=dict(task='C01.3.2',source_commit=SOURCE_COMMIT,database_sha256=before,
        database_logical_sha256=baseline['database_logical_sha256'],fresh_process_repeat=True,
        game_database_unchanged=True,cases=len(actual['cases']),tank_modes=2,repair_layers=3,
        reference_sha256=digest_file(args.output/'tank.json'))
    (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__': main()
