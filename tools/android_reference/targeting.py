"""C03.1 original wx/EOS targeting/navigation reference and full hold inventory."""
import argparse
from copy import deepcopy
import importlib.metadata,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT,DEPENDENCIES,bootstrap,compare,digest_file,logical_database_digest,validate_source


def export(source,database):
    configuration=bootstrap(source,database);configuration.gamedataCache=False
    import config
    config.pyfaPath=str(source)
    import eos.db
    from eos.const import FittingModuleState,FitSystemSecurity,ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.ship import Ship
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.cargo import Cargo
    from eos.saveddata.damagePattern import DamagePattern
    from service.market import Market
    from tools.android_reference.targeting_view_oracle import load
    oracle=load(source)
    base=json.loads((ROOT/'tools/android_reference/vexor.json').read_text(encoding='utf-8'));base.pop('edit')
    base.update(modules=[],drones=[],cargo=[],ignore_restrictions=False)
    def spec(name,ship='Vexor',modules=(),level=5):
        return {**deepcopy(base),'name':name,'ship':ship,'modules':list(modules),'skill_level':level}
    def make(value):
        item=eos.db.getItem(value['ship']);assert item is not None,value['ship']
        fit=Fit(Ship(item) if item.category.name=='Ship' else Citadel(item),name=value['name'])
        fit.character=Character('Independent targeting skills',defaultLevel=value['skill_level'])
        fit.damagePattern=DamagePattern(**value['damage_pattern']);fit.factorReload=value['factor_reload']
        fit.targetProfile=None;fit.implantLocation=ImplantLocation.FIT
        fit.systemSecurity=FitSystemSecurity[value['security']['system']];fit.pilotSecurity=value['security']['pilot']
        for row in value['modules']:
            item=eos.db.getItem(row['name']);assert item is not None,row['name']
            m=Module(item);assert m.isValidState(FittingModuleState[row['state']]),row
            m.state=FittingModuleState[row['state']]
            if row.get('charge'):
                charge=eos.db.getItem(row['charge']);assert m.isValidCharge(charge),row;m.charge=charge
            fit.modules.append(m)
        for row in value['cargo']:
            cargo=Cargo(eos.db.getItem(row['item']));cargo.amount=row['quantity'];fit.cargo.append(cargo)
        fit.calculateModifiedAttributes();return fit
    try:
        market=Market.getInstance();items={item.ID:item for group in market.getShipRoot() for item in market.getShipList(group.ID)}
        catalog=json.loads((ROOT/'tools/android_reference/fixtures/catalog.json').read_text(encoding='utf-8'))
        compare(sorted(row['id'] for row in catalog['hulls']),sorted(items))
        inventory=[];hullfits={}
        for item_id,item in sorted(items.items()):
            fit=make(spec('Targeting '+item.name,item.name));hullfits[item_id]=fit
            inventory.append(dict(id=item_id,name=item.name,sensor_type=fit.scanType,
                holds={key:fit.ship.getModifiedItemAttr(key,default=None) for key in oracle['holds']}))
        available={key for key in oracle['holds'] if any((row['holds'][key] or 0)>0 for row in inventory)}
        selected=[];uncovered=set(available)
        while uncovered:
            row=max(inventory,key=lambda r:(len({key for key in uncovered if (r['holds'][key] or 0)>0}),-r['id']))
            coverage={key for key in uncovered if (row['holds'][key] or 0)>0};assert coverage
            selected.append(row['id']);uncovered-=coverage
        for sensor in sorted({row['sensor_type'] for row in inventory}):
            item_id=next(row['id'] for row in inventory if row['sensor_type']==sensor)
            if item_id not in selected:selected.append(item_id)
        for name in ('Vexor','Rifter','Caracal','Maller','Dominix','Raitaru','Leopard'):
            item_id=eos.db.getItem(name).ID
            if item_id not in selected:selected.append(item_id)
        cases=[]
        for item_id in selected:
            value=spec('Targeting '+items[item_id].name,items[item_id].name)
            cases.append(dict(spec=value,edits=[],expected=oracle['observe'](hullfits[item_id])))
        value=spec('No trained skills',level=0)
        cases.append(dict(spec=value,edits=[],expected=oracle['observe'](make(value))))
        def module(name,state='ONLINE',charge=None):return dict(name=name,state=state,charge=charge)
        for name,ship,mods in (
          ('Drone range','Vexor',[module('Drone Link Augmentor II')]),
          ('Targeting script','Vexor',[module('Sensor Booster II','ACTIVE','Targeting Range Script')]),
          ('Scan script','Vexor',[module('Sensor Booster II','ACTIVE','Scan Resolution Script')]),
          ('Sensor resistance','Vexor',[module('Signal Amplifier II')]),
          ('Afterburner','Vexor',[module('10MN Afterburner II','ACTIVE')]),
          ('Microwarpdrive','Vexor',[module('50MN Microwarpdrive II','ACTIVE')]),
          ('Armor mass','Dominix',[module('1600mm Steel Plates II')]),
          ('Warp speed','Vexor',[module('Medium Hyperspatial Velocity Optimizer II')]),
          ('Warp core','Vexor',[module('Warp Core Stabilizer II','ACTIVE')]),
          ('Cargo expansion','Vexor',[module('Expanded Cargohold II')])):
            value=spec(name,ship,mods);fit=make(value)
            cases.append(dict(spec=value,edits=[],expected=oracle['observe'](fit)))
            for m in fit.modules:m.state=FittingModuleState.OFFLINE
            fit.clear();fit.calculateModifiedAttributes()
            cases.append(dict(spec=deepcopy(value),edits=[dict(operation='set_module_states',args=dict(module_indices=[0],state='OFFLINE'))],expected=oracle['observe'](fit)))
        for skill in ('Drone Avionics','Advanced Drone Avionics','Long Range Targeting','Signature Analysis','Navigation','Evasive Maneuvering','Warp Drive Operation','Target Management'):
            value=spec('Skill '+skill);fit=make(value);fit.character.getSkill(eos.db.getItem(skill)).setLevel(0)
            fit.clear();fit.calculateModifiedAttributes()
            cases.append(dict(spec=value,edits=[dict(operation='set_skill_level',args=dict(skill=skill,level=0))],expected=oracle['observe'](fit)))
        value=spec('Cargo tooltip refresh');fit=make(value)
        cargo=Cargo(eos.db.getItem('Antimatter Charge M'));cargo.amount=123;fit.cargo.append(cargo)
        fit.clear();fit.calculateModifiedAttributes()
        cases.append(dict(spec=value,edits=[dict(operation='add_cargo',args=dict(item_id=cargo.item.ID,quantity=123))],expected=oracle['observe'](fit)))
        # Projected ECM and damping use existing linked-fit operations, never new initial scenario fields.
        for label,module_name in (('ECM','Multispectral ECM II'),('Damping','Remote Sensor Dampener II'),('Warp disruption','Warp Disruptor II')):
            value=spec('Projected '+label);source_value=spec(label+' source','Blackbird',[module(module_name,'ACTIVE')])
            target=make(value);src=make(source_value)
            session=eos.db.saveddata_session;session.add_all([src,target]);session.flush()
            target.projectedFitDict[src.ID]=src;session.flush();session.refresh(src)
            info=src.getProjectionInfo(target.ID);assert info is not None
            info.projectionRange=None;info.active=True;info.amount=1
            src.clear();src.calculateModifiedAttributes();target.clear();target.calculateModifiedAttributes()
            cases.append(dict(spec=value,edits=[],source_spec=source_value,expected=oracle['observe'](target)))
        for row in cases:
            if row['edits'] or 'source_spec' in row:row['initial']=oracle['observe'](make(row['spec']))
        assert not any(name.startswith('android_bridge') for name in sys.modules)
        for name,mod in list(sys.modules.items()):
            if name.split('.')[0] in ('eos','service','gui','config') and getattr(mod,'__file__',None):
                assert Path(mod.__file__).resolve().is_relative_to(source),name
        return dict(task='C03.1',source_commit=SOURCE_COMMIT,eos_settings=dict(configuration.settings),
            desktop_view_sha256=oracle['source_sha256'],hull_inventory=inventory,hold_attributes=list(oracle['holds']),
            available_holds=sorted(available),absent_holds=sorted(set(oracle['holds'])-available),reference_targets=oracle['radii'],cases=cases)
    finally:oracle['close']()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--check',type=Path);parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    args.source=args.source.resolve();args.database=args.database.resolve(strict=True);args.output=args.output.resolve()
    validate_source(args.source);compare(DEPENDENCIES,{n:importlib.metadata.version(n) for n in DEPENDENCIES})
    if args.worker:
        args.output.write_text(json.dumps(export(args.source,args.database),indent=2,allow_nan=False)+'\n',encoding='utf-8');return
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):raise ValueError('Use a new external output and retained database')
    baseline=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text(encoding='utf-8'))
    compare(baseline['database_logical_sha256'],logical_database_digest(args.database));before=digest_file(args.database)
    args.output.mkdir(parents=True,exist_ok=False)
    for name in ('targeting','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),'--database',str(args.database),
                '--output',str(args.output/(name+'.json')),'--worker'],cwd=args.source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    actual=json.loads((args.output/'targeting.json').read_text(encoding='utf-8'));compare(actual,json.loads((args.output/'repeat.json').read_text(encoding='utf-8')))
    if args.check:compare(json.loads(args.check.read_text(encoding='utf-8')),actual)
    compare(before,digest_file(args.database));validate_source(args.source)
    receipt=dict(task='C03.1',source_commit=SOURCE_COMMIT,database_sha256=before,database_logical_sha256=baseline['database_logical_sha256'],
        fresh_process_repeat=True,game_database_unchanged=True,cases=len(actual['cases']),hulls=len(actual['hull_inventory']),holds=len(actual['hold_attributes']),
        available_holds=actual['available_holds'],absent_holds=actual['absent_holds'],reference_sha256=digest_file(args.output/'targeting.json'))
    (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))


if __name__=='__main__':main()
