"""Export B06.1 hull-mode changes through the pinned original desktop command."""
import argparse
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare,
    digest_file, logical_database_digest, snapshot, validate_source)


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    import wx
    from logbook import Logger
    from eos.const import FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.mode import Mode
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.variation_oracle import load

    oracle = load(source)
    service = oracle['service']
    original_path = source / 'gui/fitCommands/calc/shipModeChange.py'
    raw = original_path.read_bytes()
    definitions = [node for node in ast.parse(raw, filename=str(original_path)).body
                   if isinstance(node, ast.ClassDef) and node.name == 'CalcChangeShipModeCommand']
    assert len(definitions) == 1
    namespace = {'wx': wx, 'pyfalog': Logger(__name__), 'Fit': type(service),
                 'Market': Market, 'Mode': Mode}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(original_path), 'exec'), namespace)
    command_type = namespace['CalcChangeShipModeCommand']

    def make_fit(ship_name):
        item = eos.db.getItem(ship_name)
        assert item is not None, ship_name
        fit = Fit(Ship(item), name='B06.1 ' + ship_name)
        fit.character = Character('Independent all V', defaultLevel=5)
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25,
                                          kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity = FitSystemSecurity.HISEC, 0.0
        eos.db.saveddata_session.add(fit)
        eos.db.saveddata_session.flush()
        service.getFit(fit.ID)
        service.fill(fit.ID)
        return fit

    def state(fit):
        service.recalc(fit.ID)
        result = snapshot(fit)
        result['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        return {'mode_id': fit.mode.item.ID if fit.mode else None,
                'mode_name': fit.mode.item.name if fit.mode else None, 'stats': result}

    cases = []
    for ship_name in ('Confessor', 'Jackdaw', 'Anhinga', 'Vexor'):
        fit = make_fit(ship_name)
        choices = [{'id': item.ID, 'name': item.name} for item in fit.ship.modeItems or ()]
        first = fit.mode.item.ID if fit.mode else None
        steps = [{'requested': None, 'result': state(fit)}]
        for choice in choices:
            command = command_type(fit.ID, choice['id'])
            assert command.Do()
            eos.db.saveddata_session.flush()
            service.recalc(fit.ID); service.fill(fit.ID)
            steps.append({'requested': choice['id'], 'result': state(fit)})
        if choices:
            command = command_type(fit.ID, first)
            assert command.Do()
            eos.db.saveddata_session.flush()
            service.recalc(fit.ID); service.fill(fit.ID)
            steps.append({'requested': first, 'result': state(fit)})
            compare(steps[0]['result'], steps[-1]['result'])
        cases.append({'ship': ship_name, 'choices': choices, 'steps': steps})
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT,
            'source_files': {'gui/fitCommands/calc/shipModeChange.py': hashlib.sha256(raw).hexdigest()},
            'eos_settings': dict(configuration.settings), 'cases': cases,
            'command': 'Original CalcChangeShipModeCommand.Do plus desktop GUI flush/recalc/fill.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'database', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    args.source, args.database, args.output = (
        args.source.resolve(), args.database.resolve(strict=True), args.output.resolve())
    validate_source(args.source)
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    if args.worker:
        args.output.write_text(json.dumps(export(args.source, args.database), indent=2,
                                          allow_nan=False) + '\n', encoding='utf-8')
        return
    if args.output.is_relative_to(ROOT):
        raise ValueError('Use a new output outside checkout')
    baseline = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())
    compare(baseline['database_logical_sha256'], logical_database_digest(args.database))
    before = digest_file(args.database)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ('hull-modes', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--source', str(args.source), '--database', str(args.database),
                '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'hull-modes.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    print(json.dumps({'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases']),
        'source_commit': actual['source_commit'], 'repeated': True}))


if __name__ == '__main__':
    main()
