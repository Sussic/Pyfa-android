"""Small independent original-command export for the first C04 worker slice.

This does not certify the complete milestone or replace the full reference gate.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import bootstrap, digest_file

PIN = '8b04f3b271e614b3e103853b44a7851a63d79d0e'


def observe(fit):
    fit.calculateModifiedAttributes()
    def damage(value):
        return {name:getattr(value,name) for name in ('em','thermal','kinetic','explosive','total')}
    return dict(drones=[dict(name=d.item.name, item_id=d.itemID, amount=d.amount,
                            active=d.amountActive) for d in fit.drones],
                active=fit.activeDrones, bay=fit.droneBayUsed,
                bandwidth=fit.droneBandwidthUsed, dps=damage(fit.getDroneDps()),
                volley=damage(fit.getDroneVolley()), mining=fit.droneYield)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.source = args.source.resolve(strict=True)
    args.database = args.database.resolve(strict=True)
    args.output = args.output.resolve()
    assert not args.output.exists() and not args.output.is_relative_to(ROOT)
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.source, text=True).strip() == PIN
    cfg = bootstrap(args.source, args.database)
    cfg.gamedataCache = False
    import config
    config.pyfaPath = str(args.source)
    import eos.db
    from eos.const import ImplantLocation, FitSystemSecurity
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from tools.android_reference.drone_oracle import load
    oracle = load(args.source)
    sample = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    sample.pop('edit')
    sample['modules'], sample['drones'] = [], []
    cases = []
    # Amount/activation combinations deliberately include desktop asymmetries.
    inputs = [
        ('coalesce inactive', [(2,0)], 'add_drone', dict(amount=2)),
        ('full stack appends', [(5,0)], 'add_drone', dict(amount=1)),
        ('active stack stays separate', [(2,1)], 'add_drone', dict(amount=1)),
        ('preset inactive stack', [], 'add_drone_stack', {}),
        ('increase partially active', [(5,3)], 'set_drone_amount', dict(position=0,amount=7)),
        ('decrease partially active', [(5,3)], 'set_drone_amount', dict(position=0,amount=2)),
        ('increase inactive', [(2,0)], 'set_drone_amount', dict(position=0,amount=9)),
        ('zero removes', [(2,1)], 'set_drone_amount', dict(position=0,amount=0)),
        ('remove selected partial', [(5,3),(2,1)], 'remove_drones', dict(positions=[0,1],amount=2)),
        ('remove selected all', [(5,3),(2,1)], 'remove_drones', dict(positions=[0,1],amount=2**31-1)),
        ('main active deactivates', [(5,3),(2,0)], 'toggle_drones', dict(main_position=0,positions=[1])),
        ('main only activates', [(2,0)], 'toggle_drones', dict(main_position=0,positions=[])),
        ('main inactive preserves partial', [(5,3),(2,0)], 'toggle_drones', dict(main_position=1,positions=[0])),
        ('clone partial', [(5,3)], 'clone_drone', dict(position=0)),
        ('oversubscribed clone', [(40,40)], 'clone_drone', dict(position=0)),
    ]
    for label, rows, operation, arguments in inputs:
        spec = {**sample, 'name': 'C04 ' + label,
                'drones': [dict(name='Hobgoblin I', amount=a, active=b) for a,b in rows]}
        f = Fit(Ship(eos.db.getItem(spec['ship'])), name=spec['name'])
        f.character = Character('All V', defaultLevel=5)
        f.damagePattern = DamagePattern(**spec['damage_pattern'])
        f.implantLocation = ImplantLocation.FIT
        f.factorReload, f.targetProfile = False, None
        f.systemSecurity, f.pilotSecurity = FitSystemSecurity.HISEC, 0.0
        item = eos.db.getItem('Hobgoblin I')
        for amount,active in rows:
            f.drones.append(oracle['DroneInfo'](amount,active,item.ID).toDrone())
        eos.db.saveddata_session.add(f)
        eos.db.saveddata_session.flush()
        oracle['service'].getFit(f.ID)
        before = observe(f)
        args_in = dict(arguments)
        if operation.startswith('add_drone'):
            args_in['item_id'] = item.ID
            amount = (oracle['DroneInfo'].toDrone.__globals__['droneStackLimit'](f,item)
                      if operation == 'add_drone_stack' else arguments['amount'])
            cmd = oracle['drone_commands']['add'](f.ID,item.ID,amount)
        else:
            kind = dict(set_drone_amount='changeAmount', remove_drones='remove',
                        toggle_drones='toggleStates', clone_drone='clone')[operation]
            kwargs = {('mainPosition' if key == 'main_position' else key): value
                      for key,value in arguments.items()}
            cmd = oracle['drone_commands'][kind](fitID=f.ID,**kwargs)
        assert cmd.Do(), label
        after = observe(f)
        assert cmd.Undo(), label
        restored = observe(f)
        assert restored == before, label
        cases.append(dict(spec=spec,operation=operation,arguments=args_in,before=before,
                          after=after,restored=restored))
    result = dict(stage='C04 worker core only', source_commit=PIN, source_files=oracle['source_files'],
                  units=dict(active='count',bay='m3',bandwidth='Mbit/s',dps='HP/s',volley='HP',mining='m3/s'),
                  database_sha256=digest_file(args.database),
                  dependencies={name:importlib.metadata.version(name) for name in ('SQLAlchemy','logbook','wxPython')},
                  cases=cases)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(cases=len(cases),original_undo_cases=len(cases),output=str(args.output))))


if __name__ == '__main__': main()
