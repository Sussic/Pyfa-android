"""C01.3.1 independent pinned desktop defenses simulation and presentation."""
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
    from tools.android_reference.defenses_view_oracle import load
    oracle = load(source)
    base = deepcopy(json.loads((ROOT/'tools/android_reference/vexor.json').read_text(encoding='utf-8')))
    del base['edit']
    base.update(modules=[], drones=[], ignore_restrictions=False, cargo=[])
    def module(name, state='ACTIVE', charge=None): return dict(name=name,state=state,charge=charge)
    def spec(name, modules=()): return {**deepcopy(base),'name':name,'modules':list(modules)}
    cases=[]
    amounts=('emAmount','thermalAmount','kineticAmount','explosiveAmount')
    patterns=[('Uniform',(25,25,25,25)),('EM',(1,0,0,0)),('Thermal',(0,1,0,0)),
        ('Kinetic',(0,0,1,0)),('Explosive',(0,0,0,1)),('Mixed',(3,7,11,19))]
    for name,values in patterns:
        value=spec(name+' incoming');value['damage_pattern']=dict(zip(amounts,values));cases.append(dict(spec=value))
    for name,mods in [
        ('Hardener active',[module('Multispectrum Shield Hardener II')]),
        ('Hardener online',[module('Multispectrum Shield Hardener II','ONLINE')]),
        ('Hardener offline',[module('Multispectrum Shield Hardener II','OFFLINE')]),
        ('Armor plate',[module('1600mm Steel Plates II','ONLINE')]),
        ('Shield extender',[module('Large Shield Extender II','ONLINE')]),
        ('Damage control',[module('Damage Control II','ONLINE')]),
        ('Hull bulkheads',[module('Reinforced Bulkheads II','ONLINE')]),
        ('Armor membrane',[module('Multispectrum Energized Membrane II','ONLINE')])]:
        cases.append(dict(spec=spec(name,mods)))
    def make(value):
        fit=Fit(Ship(eos.db.getItem(value['ship'])),name=value['name'])
        fit.character=Character('Independent defenses skills',defaultLevel=value['skill_level'])
        fit.damagePattern=DamagePattern(**value['damage_pattern'])
        fit.factorReload,fit.targetProfile,fit.implantLocation=value['factor_reload'],None,ImplantLocation.FIT
        fit.systemSecurity=FitSystemSecurity[value['security']['system']];fit.pilotSecurity=value['security']['pilot']
        for row in value['modules']:
            m=Module(eos.db.getItem(row['name']));m.state=FittingModuleState[row['state']]
            if row['charge']:m.charge=eos.db.getItem(row['charge'])
            fit.modules.append(m)
        eos.db.saveddata_session.add(fit);eos.db.saveddata_session.flush();fit.calculateModifiedAttributes()
        if not fit.fits: raise ValueError('Invalid independent defenses equipment '+value['name'])
        return fit
    try:
        for row in cases:
            fit=make(row['spec'])
            row['expected']=oracle['observe'](fit)
        edits=[]
        original=make(spec('Incoming edit witness'))
        initial=oracle['observe'](original)['defenses']
        for field in amounts:
            pattern=dict(zip(amounts,(25,25,25,25)));pattern[field]=50
            original.damagePattern=DamagePattern(**pattern);original.clear();original.calculateModifiedAttributes()
            edits.append(dict(field=field,pattern=pattern,expected=oracle['observe'](original)['defenses']))
        assert len(cases)==14
        assert len({r['expected']['defenses']['layers']['shield']['ehp']['value'] for r in cases})>4
        assert not any(n.startswith('android_bridge') for n in sys.modules)
        for name,mod in list(sys.modules.items()):
            if name.split('.')[0] in ('eos','service','gui','config') and getattr(mod,'__file__',None):
                assert Path(mod.__file__).resolve().is_relative_to(source),name
        return dict(task='C01.3.1',source_commit=SOURCE_COMMIT,eos_settings=dict(configuration.settings),
            desktop_defenses_view_sha256=oracle['source_sha256'],cases=cases,pattern_edits=dict(initial=initial,steps=edits))
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
    for name in ('defenses','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),
                '--database',str(args.database),'--output',str(args.output/(name+'.json')),'--worker'],
                cwd=args.source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    actual=json.loads((args.output/'defenses.json').read_text())
    compare(actual,json.loads((args.output/'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()),actual)
    compare(before,digest_file(args.database)); validate_source(args.source)
    receipt=dict(task='C01.3.1',source_commit=SOURCE_COMMIT,database_sha256=before,
        database_logical_sha256=baseline['database_logical_sha256'],fresh_process_repeat=True,
        game_database_unchanged=True,cases=len(actual['cases']),defense_layers=3,resistances=12,
        reference_sha256=digest_file(args.output/'defenses.json'))
    (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__': main()
