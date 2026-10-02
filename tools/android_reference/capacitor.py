"""C01.2 independent pinned desktop capacitor simulation and presentation."""
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
    from tools.android_reference.capacitor_view_oracle import load
    oracle = load(source)
    base = deepcopy(json.loads((ROOT/'tools/android_reference/vexor.json').read_text(encoding='utf-8')))
    del base['edit']
    base.update(modules=[], drones=[], ignore_restrictions=False, cargo=[])
    def module(name, state='ACTIVE', charge=None): return dict(name=name,state=state,charge=charge)
    def spec(name, modules=()): return {**deepcopy(base),'name':name,'modules':list(modules)}
    cases = [dict(spec=spec('Empty capacitor')),
        dict(spec=spec('Active repair', [module('Medium Armor Repairer II')])),
        dict(spec=spec('Online repair', [module('Medium Armor Repairer II','ONLINE')])),
        dict(spec=spec('Offline repair', [module('Medium Armor Repairer II','OFFLINE')])),
        dict(spec=spec('Active propulsion and repair',[module('10MN Afterburner II'),module('Medium Armor Repairer II')])),
        dict(spec=spec('Battery idle',[module('Large Cap Battery II','ONLINE')])),
        dict(spec=spec('Battery active repair',[module('Large Cap Battery II','ONLINE'),module('Medium Armor Repairer II')])),
        dict(spec=spec('Battery offline',[module('Large Cap Battery II','OFFLINE')])),
        dict(spec=spec('Cap recharge',[module('Cap Recharger II','ONLINE')])),
        dict(spec=spec('Projected neutralizer'), source=spec('Neutralizer source',[module('Medium Energy Neutralizer II')]), projection=dict(range_m=0.0,active=True,amount=1)),
        dict(spec=spec('Battery projected neutralizer',[module('Large Cap Battery II','ONLINE')]), source=spec('Battery neutralizer source',[module('Medium Energy Neutralizer II')]),projection=dict(range_m=0.0,active=True,amount=1)),
        dict(spec=spec('Inactive projected neutralizer'), source=spec('Inactive neutralizer source',[module('Medium Energy Neutralizer II')]),projection=dict(range_m=0.0,active=False,amount=1))]
    def make(value):
        fit=Fit(Ship(eos.db.getItem(value['ship'])),name=value['name'])
        fit.character=Character('Independent capacitor skills',defaultLevel=value['skill_level'])
        fit.damagePattern=DamagePattern(**value['damage_pattern'])
        fit.factorReload,fit.targetProfile,fit.implantLocation=value['factor_reload'],None,ImplantLocation.FIT
        fit.systemSecurity=FitSystemSecurity[value['security']['system']];fit.pilotSecurity=value['security']['pilot']
        for row in value['modules']:
            m=Module(eos.db.getItem(row['name']));m.state=FittingModuleState[row['state']]
            if row['charge']:m.charge=eos.db.getItem(row['charge'])
            fit.modules.append(m)
        eos.db.saveddata_session.add(fit);eos.db.saveddata_session.flush();fit.calculateModifiedAttributes()
        if not fit.fits: raise ValueError('Invalid independent capacitor equipment '+value['name'])
        return fit
    try:
        for row in cases:
            fit=make(row['spec'])
            if 'source' in row:
                sender=make(row['source']);fit.projectedFitDict[sender.ID]=sender
                eos.db.saveddata_session.flush();eos.db.saveddata_session.refresh(sender)
                sender.clear();sender.calculateModifiedAttributes()
                info=sender.getProjectionInfo(fit.ID)
                info.projectionRange,info.active,info.amount=0.0,row['projection']['active'],1
                fit.clear();fit.calculateModifiedAttributes()
            row['expected']=oracle['observe'](fit)
        assert {r['expected']['stability']['kind'] for r in cases}=={'stable','depletion'}
        assert any(r['expected']['capacitor']['effective_excess']['value'] is not None for r in cases)
        assert not any(n.startswith('android_bridge') for n in sys.modules)
        for name,mod in list(sys.modules.items()):
            if name.split('.')[0] in ('eos','service','gui','config') and getattr(mod,'__file__',None):
                assert Path(mod.__file__).resolve().is_relative_to(source),name
        return dict(task='C01.2',source_commit=SOURCE_COMMIT,eos_settings=dict(configuration.settings),
            desktop_capacitor_view_sha256=oracle['source_sha256'],cases=cases)
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
    for name in ('capacitor','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),
                '--database',str(args.database),'--output',str(args.output/(name+'.json')),'--worker'],
                cwd=args.source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    actual=json.loads((args.output/'capacitor.json').read_text())
    compare(actual,json.loads((args.output/'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()),actual)
    compare(before,digest_file(args.database)); validate_source(args.source)
    receipt=dict(task='C01.2',source_commit=SOURCE_COMMIT,database_sha256=before,
        database_logical_sha256=baseline['database_logical_sha256'],fresh_process_repeat=True,
        game_database_unchanged=True,cases=len(actual['cases']),capacitor_values=7,
        reference_sha256=digest_file(args.output/'capacitor.json'))
    (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__': main()
