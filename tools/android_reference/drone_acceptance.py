"""Independent C04 hull boundaries, linked recipients and ordinary variations."""
import argparse
from copy import deepcopy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import bootstrap, digest_file, snapshot
from tools.android_reference.drone_edits import PIN, observe

ATTRS={'range':'m','falloff':'m','trackingSpeed':'rad/s','maxVelocity':'m/s',
       'volume':'m3','droneBandwidthUsed':'Mbit/s'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'): p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args(); source=args.source.resolve(strict=True); output=args.output.resolve()
    assert not output.exists() and not output.is_relative_to(ROOT)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==PIN
    cfg=bootstrap(source,args.database); cfg.gamedataCache=False
    import config
    config.pyfaPath=str(source)
    import eos.db
    from eos.const import ImplantLocation, FitSystemSecurity, FittingModuleState
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from tools.android_reference.drone_oracle import load
    oracle=load(source); service=oracle['service']
    # The original variation AST loader predates Undo coverage. Bind its calc
    # classes to the identical source bodies loaded in named modules by the
    # drone loader, so their original relative imports work during Undo.
    oracle['variation_commands']['drone'].Do.__globals__.update(
        CalcAddLocalDroneCommand=oracle['drone_commands']['localAdd'],
        CalcRemoveLocalDroneCommand=oracle['drone_commands']['localRemove'])
    base=json.loads((ROOT/'tools/android_reference/vexor.json').read_text()); base.pop('edit')
    base.update(modules=[],drones=[])
    def make(spec):
        f=Fit(Ship(eos.db.getItem(spec['ship'])),name=spec['name'])
        f.character=Character('Synthetic all V',defaultLevel=spec['skill_level'])
        f.damagePattern=DamagePattern(**spec['damage_pattern'])
        f.factorReload=False; f.targetProfile=None; f.implantLocation=ImplantLocation.FIT
        f.systemSecurity=FitSystemSecurity.HISEC; f.pilotSecurity=0.0
        for row in spec['modules']:
            item=eos.db.getItem(row['name']); charge=eos.db.getItem(row['charge']) if row.get('charge') else None
            f.modules.append(oracle['ModuleInfo'](item.ID,state=FittingModuleState[row['state']],chargeID=charge.ID if charge else None).toModule())
        for row in spec['drones']:
            f.drones.append(oracle['DroneInfo'](row['amount'],row['active'],eos.db.getItem(row['name']).ID).toDrone())
        eos.db.saveddata_session.add(f); eos.db.saveddata_session.flush(); service.getFit(f.ID)
        return f
    def report(f):
        service.recalc(f.ID)
        f=service.getFit(f.ID)
        stats=snapshot(f)
        stats['scan_resolution']=dict(value=f.ship.getModifiedItemAttr('scanResolution'),unit='mm')
        return dict(core=observe(f),stats=stats,attributes=[{
            key:(d.maxRange if key=='range' else d.falloff if key=='falloff' else d.getModifiedItemAttr(key))
            for key in ATTRS} for d in f.drones])
    def command(f,op,a):
        if op=='change_variation': return oracle['variation_commands']['drone'](f.ID,[a['position']],a['item_id'])
        if op in ('add_drone','add_drone_stack'):
            item=eos.db.getItem(a['item_id'])
            amount=oracle['DroneInfo'].toDrone.__globals__['droneStackLimit'](f,item) if op=='add_drone_stack' else a['amount']
            return oracle['drone_commands']['add'](f.ID,item.ID,amount)
        kind=dict(set_drone_amount='changeAmount',remove_drones='remove',toggle_drones='toggleStates',clone_drone='clone')[op]
        return oracle['drone_commands'][kind](fitID=f.ID,**{('mainPosition' if k=='main_position' else k):v for k,v in a.items()})
    core=json.loads((ROOT/'tools/android_reference/fixtures/drone-core-edits.json').read_text())
    representatives=[]; seen=set()
    for case in core['cases']:
        if case['operation'] not in seen:
            representatives.append(case); seen.add(case['operation'])
    linked=[]
    for kind,ship,module,charge in (
            ('projection','Celestis','Remote Sensor Dampener I','Targeting Range Dampening Script'),
            ('command','Drake','Shield Command Burst I','Shield Harmonizing Charge')):
        cases=representatives+[dict(spec=dict(base,drones=[dict(name='Hobgoblin I',amount=5,active=3)]),
            operation='change_variation',arguments=dict(context='drone',position=0,item_id=2456))]
        for case in cases:
            spec=dict(deepcopy(case['spec']),ship=ship,name=f'C04 {kind} {case["operation"]}',
                      modules=[dict(name=module,state='ACTIVE',charge=charge)])
            owner=make(spec)
            target_specs=[dict(deepcopy(base),ship=hull,name=f'{spec["name"]} recipient {i}',
                              drones=[dict(name='Hobgoblin I',amount=2,active=1)])
                          for i,hull in enumerate(('Vexor','Caracal'))]
            targets=[make(s) for s in target_specs]
            unlinked=[report(f) for f in targets]
            for target in targets:
                container=target.commandFitDict if kind=='command' else target.projectedFitDict
                container[owner.ID]=owner
                eos.db.saveddata_session.flush(); eos.db.saveddata_session.refresh(owner)
                info=owner.getCommandInfo(target.ID) if kind=='command' else owner.getProjectionInfo(target.ID)
                info.active=True
                if kind=='projection': info.projectionRange,info.amount=0.0,1
            def all_reports(): return [report(owner),*[report(t) for t in targets]]
            before=all_reports()
            assert any(a['stats']!=b['stats'] for a,b in zip(unlinked,before[1:])),kind
            cmd=command(owner,case['operation'],case['arguments']); assert cmd.Do()
            after=all_reports(); assert cmd.Undo(); restored=all_reports()
            assert before==restored
            linked.append(dict(spec=spec,recipients=target_specs,link=kind,operation=case['operation'],
                arguments=case['arguments'],unlinked=unlinked,before=before,after=after,restored=restored))
    variations=[]
    old=json.loads((ROOT/'tools/android_reference/fixtures/variation-edits.json').read_text())
    for case in old['cases']:
        if case['name'] not in ('Drone stack quantity and ordering','Inactive drone stack'): continue
        spec=dict(deepcopy(base),name='C04 '+case['name'],ship=case['ship'],drones=case['drones'])
        f=make(spec); steps=[]
        for step in case['steps'][1:]:
            a={k:v for k,v in step['input'].items() if k!='name'}
            before=report(f); cmd=command(f,'change_variation',a); changed=bool(cmd.Do()); after=report(f)
            if changed:
                assert cmd.Undo(); restored=report(f); assert before==restored
                assert cmd.Do(); assert report(f)==after
            else: restored=before; assert before==after
            steps.append(dict(arguments=a,changed=changed,before=before,after=after,restored=restored))
        variations.append(dict(spec=spec,steps=steps))
    extra=[]
    for hull,name,op in (('Rifter','Hobgoblin I','add_drone_stack'),
                         ('Vexor',"'Excavator' Mining Drone",'add_drone'),
                         ('Rorqual',"'Excavator' Mining Drone",'add_drone_stack')):
        spec=dict(deepcopy(base),name='C04 boundary '+hull,ship=hull)
        f=make(spec); item=eos.db.getItem(name); assert item is not None,name
        a=dict(item_id=item.ID,**({'amount':1} if op=='add_drone' else {}))
        before=observe(f); cmd=command(f,op,a); accepted=bool(cmd.Do()); after=observe(f)
        if accepted: assert cmd.Undo()
        assert observe(f)==before
        extra.append(dict(spec=spec,operation=op,arguments=a,accepted=accepted,before=before,after=after,restored=before))
    files=dict(oracle['source_files'])
    for relative in ('eos/saveddata/drone.py','eos/saveddata/fit.py'):
        files[relative]=hashlib.sha256((source/relative).read_bytes()).hexdigest()
    result=dict(source_commit=PIN,source_files=files,database_sha256=digest_file(args.database),
        dependencies={name:importlib.metadata.version(name) for name in ('SQLAlchemy','logbook','wxPython')},
        python=sys.version,eos_settings=dict(cfg.settings),units=dict(attributes=ATTRS,core=core['units']),
        linked=linked,variations=variations,core_extra=extra,
        inherited_variation_reference_sha256=digest_file(ROOT/'tools/android_reference/fixtures/variation-edits.json'))
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(linked_cases=len(linked),variation_steps=sum(len(c['steps']) for c in variations),boundaries=len(extra))))


if __name__=='__main__': main()
