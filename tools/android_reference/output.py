"""C02 independent pinned desktop output calculations and wx presentation."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT,DEPENDENCIES,bootstrap,
    compare,digest_file,logical_database_digest,validate_source)


def export(source,database):
    configuration=bootstrap(source,database);configuration.gamedataCache=False
    import config
    config.pyfaPath=str(source)
    import eos.db
    from eos.const import FittingModuleState,FitSystemSecurity,ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.ship import Ship
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.drone import Drone
    from eos.saveddata.fighter import Fighter
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.targetProfile import TargetProfile
    from tools.android_reference.output_view_oracle import load
    oracle=load(source)
    base=json.loads((ROOT/'tools/android_reference/vexor.json').read_text());base.pop('edit')
    base.update(modules=[],drones=[],ignore_restrictions=False,cargo=[])
    def module(name,state='ACTIVE',charge=None):return dict(name=name,state=state,charge=charge)
    def spec(name,modules=(),ship='Vexor',drones=(),profile=None,**extra):
        return {**deepcopy(base),'name':name,'ship':ship,'modules':list(modules),'drones':list(drones),'target_profile':deepcopy(profile),**extra}
    def drone(name,active=1):return dict(name=name,amount=1,active=active)
    mixed=dict(emAmount=.1,thermalAmount=.3,kineticAmount=.5,explosiveAmount=.7,maxVelocity=0,signatureRadius=None,radius=0,hp=None)
    turret=module('250mm Railgun II',charge='Antimatter Charge M')
    cases=[dict(spec=spec('Empty output'))]
    for state in ('ACTIVE','ONLINE','OFFLINE','OVERHEATED'):
        cases.append(dict(spec=spec('Turret '+state,[{**turret,'state':state}])))
    for charge in ('Mjolnir Heavy Missile','Inferno Heavy Missile','Scourge Heavy Missile','Nova Heavy Missile'):
        cases.append(dict(spec=spec(charge,[module('Heavy Missile Launcher II',charge=charge)],ship='Caracal')))
    drones=[drone(n) for n in ('Acolyte II','Hobgoblin II','Hornet II','Warrior II')]
    cases.append(dict(spec=spec('Mixed drones',[turret],drones=drones)))
    cases.append(dict(spec=spec('Inactive drones',drones=[drone('Hobgoblin II',0)])))
    for active in (True,False):cases.append(dict(spec=spec('Fighter '+str(active),ship='Archon',fighters=[dict(name='Templar I',amount=1,active=active)])))
    spool=module('Heavy Entropic Disintegrator II',charge='Occult M')
    cases.append(dict(spec=spec('Weapon spool',[spool],ship='Vedmak')))
    cases.append(dict(spec=spec('Mixed profile',[turret],drones=drones,profile=mixed)))
    for resistance in (0.0,1.0):
        profile={**mixed,**{k:resistance for k in ('emAmount','thermalAmount','kineticAmount','explosiveAmount')}}
        cases.append(dict(spec=spec('Uniform profile '+str(resistance),[turret],profile=profile)))
    cases.append(dict(spec=spec('Spool profile',[spool],ship='Vedmak',profile=mixed)))
    for label,modules,drones in (
        ('Mixed mining',[module('Miner II')],[drone('Mining Drone II')]),
        ('Inactive mining',[module('Miner II','OFFLINE')],[drone('Mining Drone II',0)]),
        ('Strip mining',[module('Strip Miner I')],[]),
        ('Crystal mining',[module('Modulated Strip Miner II',charge='Simple Asteroid Mining Crystal Type A II')],[]),
        ('No crystal',[module('Modulated Strip Miner II')],[])):
        cases.append(dict(spec=spec(label,modules,ship='Procurer' if 'Strip' in label or 'crystal' in label.lower() else 'Vexor',drones=drones)))
    cases.append(dict(spec=spec('Smartbomb',[module('Medium EMP Smartbomb II')])) )
    cases.append(dict(spec=spec('Bomb launcher',[module('Bomb Launcher I',charge='Electron Bomb')],ship='Purifier')))
    cases.append(dict(spec=spec('Small bomb target',ship='Rifter')))
    cases.append(dict(spec=spec('Resistant bomb target',[module('Damage Control II','ONLINE'),module('1600mm Steel Plates II','ONLINE')],ship='Dominix')))
    for level,state in ((1,'ONLINE'),(6,'ONLINE'),(6,'OFFLINE')):
        cases.append(dict(spec=spec('Red Giant '+str(level)+' '+state,environments=[dict(name=f'Class {level} Red Giant Effects',state=state)])))
    cases.append(dict(spec=spec('Stacked Red Giants',environments=[dict(name=f'Class {level} Red Giant Effects',state='ONLINE') for level in (1,6)])))
    remote=[module(n) for n in ('Medium Remote Capacitor Transmitter II','Medium Remote Shield Booster II','Medium Remote Armor Repairer II','Medium Remote Hull Repairer II')]
    cases.append(dict(spec=spec('All outgoing',remote)))
    cases.append(dict(spec=spec('Outgoing spool',[module('Heavy Mutadaptive Remote Armor Repairer II')],ship='Rodiva')))
    cases.append(dict(spec=spec('Outgoing inactive',[{**m,'state':'ONLINE'} for m in remote])))
    reload=spec('Missile reload',[module('Heavy Missile Launcher II',charge='Scourge Heavy Missile')],ship='Caracal');reload['factor_reload']=True
    cases.append(dict(spec=reload))
    for hp in (10000.0,1000000.0):
        cases.append(dict(spec=spec('Breacher hp '+str(hp),[module('Small Breacher Pod Launcher',charge='SCARAB Breacher Pod S')],ship='Tholos',profile={**mixed,'hp':hp})))
    def make(value):
        fit=Fit(Ship(eos.db.getItem(value['ship'])),name=value['name'])
        fit.character=Character('Independent output skills',defaultLevel=value['skill_level'])
        fit.damagePattern=DamagePattern(**value['damage_pattern']);fit.factorReload=value['factor_reload']
        fit.targetProfile=None if value['target_profile'] is None else TargetProfile(**value['target_profile'])
        fit.implantLocation=ImplantLocation.FIT;fit.systemSecurity=FitSystemSecurity[value['security']['system']];fit.pilotSecurity=value['security']['pilot']
        for row in value['modules']:
            item=eos.db.getItem(row['name']);assert item is not None,row['name']
            m=Module(item);m.state=FittingModuleState[row['state']]
            if row['charge']:
                charge=eos.db.getItem(row['charge']);assert charge is not None and m.isValidCharge(charge),row
                m.charge=charge
            fit.modules.append(m)
        for row in value['drones']:
            d=Drone(eos.db.getItem(row['name']));d.amount=row['amount'];d.amountActive=row['active'];fit.drones.append(d)
        for row in value.get('fighters',[]):
            f=Fighter(eos.db.getItem(row['name']));f.amount=row['amount'];f.active=row['active'];fit.fighters.append(f)
        for row in value['environments']:
            m=Module(eos.db.getItem(row['name']));m.state=FittingModuleState[row['state']];fit.projectedModules.append(m)
        eos.db.saveddata_session.add(fit);eos.db.saveddata_session.flush();fit.calculateModifiedAttributes()
        assert fit.fits,'Invalid original fixture '+value['name']
        return fit
    try:
        for row in cases:row['expected']=oracle['observe'](make(row['spec']))
        assert not any(n.startswith('android_bridge') for n in sys.modules)
        for name,mod in list(sys.modules.items()):
            if name.split('.')[0] in ('eos','service','gui','config') and getattr(mod,'__file__',None):
                assert Path(mod.__file__).resolve().is_relative_to(source),name
        return dict(task='C02',source_commit=SOURCE_COMMIT,eos_settings=dict(configuration.settings),desktop_output_views_sha256=oracle['source_sha256'],cases=cases)
    finally:oracle['close']()


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
    for name in ('output','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),
                '--database',str(args.database),'--output',str(args.output/(name+'.json')),'--worker'],
                cwd=args.source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    actual=json.loads((args.output/'output.json').read_text())
    compare(actual,json.loads((args.output/'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()),actual)
    compare(before,digest_file(args.database)); validate_source(args.source)
    receipt=dict(task='C02',source_commit=SOURCE_COMMIT,database_sha256=before,
        database_logical_sha256=baseline['database_logical_sha256'],fresh_process_repeat=True,
        game_database_unchanged=True,cases=len(actual['cases']),firepower_modes=2,bomb_cells=24,outgoing_types=4,
        reference_sha256=digest_file(args.output/'output.json'))
    (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__': main()
