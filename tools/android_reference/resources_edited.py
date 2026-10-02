"""Independent resource witness for original desktop module editing vacancies.

Keep resources.json intact: directly constructed fits and edited fits have
different vacant-module inputs, which can also change EOS's scalar kind at zero.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (bootstrap, compare, digest_file,
    SOURCE_COMMIT, validate_source)


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FittingModuleState, FittingSlot, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from tools.android_reference.module_oracle import load as commands
    from tools.android_reference.resource_view_oracle import load as view
    original = json.loads((ROOT/'tools/android_reference/fixtures/resources.json').read_text(encoding='utf-8'))
    case = deepcopy(original['cases'][2])
    assert case['spec']['name'] == 'Offline guns' and case['execution'] == 'durable'
    spec = case['spec']
    oracle = commands(source)
    resource_view = view(source)
    try:
        fit = Fit(Ship(eos.db.getItem(spec['ship'])), name=spec['name'])
        fit.character = Character('Independent all V', defaultLevel=spec['skill_level'])
        fit.damagePattern = DamagePattern(**spec['damage_pattern'])
        fit.factorReload, fit.targetProfile, fit.implantLocation = spec['factor_reload'], None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity = FitSystemSecurity[spec['security']['system']], spec['security']['pilot']
        fit.ignoreRestrictions = spec['ignore_restrictions']
        eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush()
        service = oracle['service']
        service.getFit(fit.ID)
        service.fill(fit.ID)
        for module in spec['modules']:
            info = oracle['ModuleInfo'](eos.db.getItem(module['name']).ID,
                state=FittingModuleState[module['state']], chargeID=None)
            assert module['charge'] is None
            assert oracle['commands']['localAdd'](fit.ID, info).Do()
            service.fill(fit)
        service.recalc(fit)
        edited = deepcopy(spec)
        edited['modules'] = [{'empty_slot': FittingSlot(module.slot).name} if module.isEmpty else
            {'name': module.item.name, 'state': FittingModuleState(module.state).name,
             'charge': module.charge.name if module.charge else None} for module in fit.modules]
        result = resource_view['observe'](fit)
        # No expected value is taken from Android or inferred by normalization.
        return {'task':'C01.1', 'source_commit':SOURCE_COMMIT, 'case':2,
            'input':spec, 'edited_input':edited, 'resources':result,
            'eos_settings':dict(configuration.settings),
            'source_files':oracle['source_files'],
            'desktop_resource_view_sha256':resource_view['source_sha256']}
    finally:
        resource_view['close']()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    validate_source(args.source)
    if args.worker:
        args.output.write_text(json.dumps(export(args.source,args.database),indent=2,allow_nan=False)+'\n',encoding='utf-8')
        return
    assert not args.output.resolve().is_relative_to(ROOT)
    args.output.mkdir(parents=True,exist_ok=False)
    before = digest_file(args.database)
    for name in ('resources-edited','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),
                '--database',str(args.database),'--output',str(args.output/(name+'.json')),'--worker'],
                stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    result = json.loads((args.output/'resources-edited.json').read_text(encoding='utf-8'))
    compare(result,json.loads((args.output/'repeat.json').read_text(encoding='utf-8')))
    if args.check: compare(result,json.loads(args.check.read_text(encoding='utf-8')))
    assert before == digest_file(args.database)
    validate_source(args.source)
    (args.output/'evidence.json').write_text(json.dumps({'task':'C01.1','source_commit':SOURCE_COMMIT,
        'fresh_process_repeat':True,'game_database_unchanged':True,'database_sha256':before,
        'reference_sha256':digest_file(args.output/'resources-edited.json')},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'fresh_process_repeat':True,'reference':str(args.output/'resources-edited.json')}))


if __name__ == '__main__': main()
