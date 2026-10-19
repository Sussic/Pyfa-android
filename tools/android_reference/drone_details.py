"""Independent pinned EOS drone-family and existing-mutation observations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import bootstrap, digest_file
from tools.android_reference.drone_edits import PIN

ATTRS=('volume','droneBandwidthUsed','trackingSpeed','maxVelocity','signatureRadius','duration',
       'ECMDuration','energyNeutralizerDuration','accessDifficultyBonus','scanGravimetricStrengthBonus','scanLadarStrengthBonus',
       'scanMagnetometricStrengthBonus','scanRadarStrengthBonus','speedFactor','signatureRadiusBonus',
       'trackingSpeedBonus','maxRangeBonus','falloffBonus','scanResolutionBonus','maxTargetRangeBonus',
       'energyNeutralizerAmount')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'): p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    source=args.source.resolve(strict=True); database=args.database.resolve(strict=True)
    out=args.output.resolve()
    assert not out.exists() and not out.is_relative_to(ROOT)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==PIN
    cfg=bootstrap(source,database); cfg.gamedataCache=False
    import config
    config.pyfaPath=str(source)
    import eos.db
    from eos.const import ImplantLocation,FitSystemSecurity
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from tools.android_reference.drone_oracle import load
    oracle=load(source)
    specimen=json.loads((ROOT/'tools/android_reference/vexor.json').read_text()); specimen.pop('edit')
    specimen['modules']=[]
    names=('Hobgoblin I','Hobgoblin II','Mining Drone II','Salvage Drone I',
           'Light Shield Maintenance Bot I','Light Armor Maintenance Bot I','Light Hull Maintenance Bot I',
           'Hornet EC-300','Warrior SW-300','Acolyte EV-300','Acolyte TD-300','Hobgoblin SD-300','Warrior TP-300')
    cases=[]
    for skill in (0,5):
        for pattern in (dict(emAmount=25,thermalAmount=25,kineticAmount=25,explosiveAmount=25),
                        dict(emAmount=0,thermalAmount=100,kineticAmount=0,explosiveAmount=0)):
            f=Fit(Ship(eos.db.getItem('Vexor')),name=f'C04 details skills {skill} thermal {pattern["thermalAmount"]}')
            f.character=Character('Synthetic',defaultLevel=skill)
            f.damagePattern=DamagePattern(**pattern); f.implantLocation=ImplantLocation.FIT
            f.factorReload=False; f.targetProfile=None; f.systemSecurity=FitSystemSecurity.HISEC; f.pilotSecurity=0.0
            for name in names:
                f.drones.append(oracle['DroneInfo'](3,2,eos.db.getItem(name).ID).toDrone())
            for fraction in (0.25,0.75):
                # These are synthetic existing rolls made by original DroneInfo,
                # not a new mutation editing operation in the Android bridge.
                d=oracle['DroneInfo'](5,3,60478,baseItemID=2454,mutaplasmidID=60461,mutations={}).toDrone()
                for mutator in d.mutators.values():
                    mutator.value=mutator.minValue+(mutator.maxValue-mutator.minValue)*fraction
                f.drones.append(d)
            eos.db.saveddata_session.add(f); eos.db.saveddata_session.flush(); oracle['service'].getFit(f.ID)
            f.calculateModifiedAttributes()
            records=[]; observations=[]
            for d in f.drones:
                info=oracle['DroneInfo'].fromDrone(d)
                row=dict(name=d.item.name,amount=info.amount,active=info.amountActive)
                if d.isMutated:
                    row['mutation']=dict(base_item_id=info.baseItemID,mutaplasmid_id=info.mutaplasmidID,
                        attributes=[dict(attribute_id=k,value=v) for k,v in sorted(info.mutations.items())])
                records.append(row)
                values={attr:d.getModifiedItemAttr(attr) for attr in ATTRS}
                for layer in ('shield','armor','hull'):
                    values['hp_'+layer]=d.hp[layer]; values['ehp_'+layer]=d.ehp[layer]
                values['shield_regen']=d.calculateShieldRecharge()
                values['effective_shield_regen']=f.damagePattern.effectivify(d,values['shield_regen'],'shield')
                for key,value in (('dps',d.getDps(f.targetProfile)),('volley',d.getVolley(f.targetProfile))):
                    for kind in ('em','thermal','kinetic','explosive','total'):
                        values[key+'_'+kind]=getattr(value,kind) if d.dealsDamage else None
                values['mining_yield']=d.getMiningYPS() if d.mines else None
                values['mining_drain']=d.getMiningDPS() if d.mines else None
                remote=d.getRemoteReps()
                for kind,attr in (('shield','shieldBonus'),('armor','armorDamageAmount'),('hull','structureDamageAmount'),('capacitor','powerTransferAmount')):
                    values['remote_'+kind]=getattr(remote,kind) if d.getModifiedItemAttr(attr) is not None else None
                values.update(range=d.maxRange,falloff=d.falloff)
                observations.append(dict(item_id=d.itemID,name=d.fullName,group=d.item.group.name,
                    amount=d.amount,active=d.amountActive,metrics=values))
            # Original clone and undo of a rolled stack preserve its full values.
            cmd=oracle['drone_commands']['clone'](fitID=f.ID,position=13)
            assert cmd.Do()
            clone=oracle['DroneInfo'].fromDrone(f.drones[-1]); original=oracle['DroneInfo'].fromDrone(f.drones[13])
            assert vars(clone)==vars(original)
            assert cmd.Undo() and len(f.drones)==15
            spec=dict(specimen,name=f.name,skill_level=skill,damage_pattern=pattern,drones=records)
            cases.append(dict(spec=spec,stacks=observations,
                resources=dict(active=f.activeDrones,active_limit=f.extraAttributes['maxActiveDrones'],
                               bay_used=f.droneBayUsed,bay_capacity=f.ship.getModifiedItemAttr('droneCapacity'),
                               bandwidth_used=f.droneBandwidthUsed,bandwidth_capacity=f.ship.getModifiedItemAttr('droneBandwidth'))))
    files=oracle['source_files']
    for relative in ('eos/saveddata/drone.py','eos/saveddata/damagePattern.py','eos/saveddata/fit.py',
                     'eos/saveddata/mutatedMixin.py','eos/saveddata/mutator.py'):
        files[relative]=hashlib.sha256((source/relative).read_bytes()).hexdigest()
    out.write_text(json.dumps(dict(source_commit=PIN,source_files=files,database_sha256=digest_file(database),
                                   cases=cases,original_mutated_clone_undos=4),indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(cases=len(cases),stacks=sum(len(c['stacks']) for c in cases),output=str(out))))

if __name__=='__main__': main()
