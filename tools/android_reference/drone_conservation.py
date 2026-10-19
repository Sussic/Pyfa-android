"""Approved F08.03 count tables, evaluated by pinned EOS, not Android edits.

The count tables deliberately differ from desktop split/merge commands. Preserve
that distinction in every receipt; the pinned EOS still supplies calculations.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import bootstrap,digest_file,snapshot
from tools.android_reference.drone_edits import PIN,observe

POLICY=dict(id='F08.03-conserve-v1',active_counts='conserve',split_allocation='moved_active=min(requested,original_active)',
            merge_compatibility='same item, base, mutaplasmid and exact ordered rolls',destination_identity='retained',
            authority='User decision 2026-10-13: preserve total active drone counts during split/merge, matching F08.03')
ATTRS=('range','falloff','trackingSpeed','maxVelocity','volume','droneBandwidthUsed',
       'hp_shield','hp_armor','hp_hull','ehp_shield','ehp_armor','ehp_hull')

def main():
    p=argparse.ArgumentParser()
    for n in ('source','database','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();source=a.source.resolve(strict=True);out=a.output.resolve()
    assert not out.exists() and not out.is_relative_to(ROOT)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==PIN
    cfg=bootstrap(source,a.database);cfg.gamedataCache=False
    import config
    config.pyfaPath=str(source)
    import eos.db
    from eos.const import ImplantLocation,FitSystemSecurity,FittingModuleState
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from tools.android_reference.drone_oracle import load
    oracle=load(source);service=oracle['service']
    base=json.loads((ROOT/'tools/android_reference/vexor.json').read_text());base.pop('edit');base['modules']=[]
    rolls=json.loads((ROOT/'tools/android_reference/fixtures/drone-details.json').read_text())['cases'][-1]['spec']['drones'][13:15]
    def row(kind,n,active):
        r=deepcopy(rolls[kind-1]) if kind else dict(name='Hobgoblin I')
        r.update(amount=n,active=active);return r
    def rows(values):return [row(*v) for v in values]
    # Literal, reviewable before/after counts; no production policy function.
    tables=[
      ('split inactive',[(0,5,0)],'split_drone',dict(position=0,amount=2),[(0,3,0),(0,2,0)],True),
      ('split partial',[(0,5,3)],'split_drone',dict(position=0,amount=2),[(0,3,1),(0,2,2)],True),
      ('split beyond active',[(0,5,2)],'split_drone',dict(position=0,amount=3),[(0,2,0),(0,3,2)],True),
      ('split all active',[(0,5,5)],'split_drone',dict(position=0,amount=2),[(0,3,3),(0,2,2)],True),
      ('split one',[(0,2,1)],'split_drone',dict(position=0,amount=1),[(0,1,0),(0,1,1)],True),
      ('split quarter roll',[(1,5,3),(2,2,1)],'split_drone',dict(position=0,amount=2),[(1,3,1),(2,2,1),(1,2,2)],True),
      ('split three-quarter roll',[(1,2,1),(2,5,2)],'split_drone',dict(position=1,amount=3),[(1,2,1),(2,2,0),(2,3,2)],True),
      ('merge into inactive',[(0,3,0),(0,2,2)],'merge_drones',dict(source_position=1,destination_position=0),[(0,5,2)],True),
      ('merge into active',[(0,3,3),(0,2,0)],'merge_drones',dict(source_position=1,destination_position=0),[(0,5,3)],True),
      ('merge partial reverse',[(0,4,2),(0,3,1)],'merge_drones',dict(source_position=0,destination_position=1),[(0,7,3)],True),
      ('merge identical rolls',[(1,2,1),(1,3,2),(2,2,1)],'merge_drones',dict(source_position=0,destination_position=1),[(1,5,3),(2,2,1)],True),
      ('merge inactive rolls',[(2,2,0),(2,3,0)],'merge_drones',dict(source_position=1,destination_position=0),[(2,5,0)],True),
      ('reject distinct rolls',[(1,2,1),(2,3,2)],'merge_drones',dict(source_position=0,destination_position=1),[(1,2,1),(2,3,2)],False),
      ('reject distinct types',[(0,2,1),(1,3,2)],'merge_drones',dict(source_position=0,destination_position=1),[(0,2,1),(1,3,2)],False),
    ]
    def make(spec):
        f=Fit(Ship(eos.db.getItem(spec['ship'])),name=spec['name'])
        f.character=Character('Synthetic',defaultLevel=spec['skill_level']);f.damagePattern=DamagePattern(**spec['damage_pattern'])
        f.implantLocation=ImplantLocation.FIT;f.factorReload=False;f.targetProfile=None;f.systemSecurity=FitSystemSecurity.HISEC;f.pilotSecurity=0.0
        for r in spec['modules']:
            charge=eos.db.getItem(r['charge']) if r.get('charge') else None
            f.modules.append(oracle['ModuleInfo'](eos.db.getItem(r['name']).ID,state=FittingModuleState[r['state']],chargeID=charge.ID if charge else None).toModule())
        for r in spec['drones']:
            m=r.get('mutation');kw={} if m is None else dict(baseItemID=m['base_item_id'],mutaplasmidID=m['mutaplasmid_id'],mutations={v['attribute_id']:v['value'] for v in m['attributes']})
            f.drones.append(oracle['DroneInfo'](r['amount'],r['active'],eos.db.getItem(r['name']).ID,**kw).toDrone())
        eos.db.saveddata_session.add(f);eos.db.saveddata_session.flush();service.getFit(f.ID);return f
    def report(f):
        service.recalc(f.ID);f=service.getFit(f.ID)
        stats=snapshot(f);stats['scan_resolution']=dict(value=f.ship.getModifiedItemAttr('scanResolution'),unit='mm')
        values=[]
        for d in f.drones:
            m={n:d.getModifiedItemAttr(n) for n in ATTRS[2:6]};m.update(range=d.maxRange,falloff=d.falloff)
            for layer in ('shield','armor','hull'):m['hp_'+layer]=d.hp[layer];m['ehp_'+layer]=d.ehp[layer]
            values.append(m)
        return dict(core=observe(f),stats=stats,metrics=values)
    cases=[]
    for label,before,operation,args,after,accepted in tables:
        spec=dict(deepcopy(base),name='C04 conserve '+label,drones=rows(before))
        revised=dict(deepcopy(spec),drones=rows(after))
        assert sum(r['amount'] for r in spec['drones'])==sum(r['amount'] for r in revised['drones'])
        assert sum(r['active'] for r in spec['drones'])==sum(r['active'] for r in revised['drones'])
        cases.append(dict(spec=spec,operation=operation,arguments=args,accepted=accepted,after_rows=revised['drones'],
                          before=report(make(spec)),after=report(make(revised))))
    linked=[]
    prior=json.loads((ROOT/'tools/android_reference/fixtures/drone-acceptance.json').read_text())
    for kind in ('projection','command'):
        template=next(c for c in prior['linked'] if c['link']==kind)
        for case in (cases[1],cases[7]):
            spec=dict(deepcopy(template['spec']),name=case['spec']['name']+' '+kind,drones=deepcopy(case['spec']['drones']))
            def linked_report(drone_rows):
                owner=make(dict(deepcopy(spec),drones=deepcopy(drone_rows)));targets=[make(s) for s in template['recipients']]
                unlinked=[report(f) for f in targets]
                for target in targets:
                    (target.commandFitDict if kind=='command' else target.projectedFitDict)[owner.ID]=owner
                    eos.db.saveddata_session.flush();eos.db.saveddata_session.refresh(owner)
                    info=owner.getCommandInfo(target.ID) if kind=='command' else owner.getProjectionInfo(target.ID);info.active=True
                    if kind=='projection':info.projectionRange,info.amount=0.0,1
                result=[report(owner),*[report(f) for f in targets]]
                assert any(a['stats']!=b['stats'] for a,b in zip(unlinked,result[1:]));return result
            linked.append(dict(spec=spec,recipients=template['recipients'],link=kind,operation=case['operation'],arguments=case['arguments'],
                after_rows=case['after_rows'],before=linked_report(spec['drones']),after=linked_report(case['after_rows'])))
    files=dict(oracle['source_files'])
    for n in ('eos/saveddata/drone.py','eos/saveddata/fit.py','eos/saveddata/mutatedMixin.py','eos/saveddata/mutator.py'):
        files[n]=digest_file(source/n)
    result=dict(policy=POLICY,expectation_kind='approved literal count tables with independent pinned EOS calculations',source_commit=PIN,
                source_files=files,database_sha256=digest_file(a.database),cases=cases,linked=linked,metrics=list(ATTRS))
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(cases=len(cases),linked=len(linked),sha256=digest_file(out))))

if __name__=='__main__':main()
