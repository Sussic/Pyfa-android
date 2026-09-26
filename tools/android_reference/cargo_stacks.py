"""Export B07.1 cargo stack commands from the unchanged pinned desktop source."""
import argparse
import ast
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare,
    digest_file, logical_database_digest, snapshot, validate_source)


CASES = (
    ('Vexor', (
        ('add', 'Antimatter Charge S', 1),
        ('add', 'Antimatter Charge S', 9),
        ('set', 'Antimatter Charge S', 1500),
        ('remove', 'Antimatter Charge S', 10),
        ('add', '200mm AutoCannon II', 2),
        ('add', 'Small Standard Container', 1),
        ('remove', 'Antimatter Charge S', 10000),
        ('set', '200mm AutoCannon II', 1),
        ('remove', '200mm AutoCannon II', 1),
        ('remove', '200mm AutoCannon II', 1),
        ('add', 'Small Standard Container', 4),
        ('set', 'Small Standard Container', 1),
    )),
    ('Astrahus', (
        ('add', 'Antimatter Charge S', 1000),
        ('add', 'Antimatter Charge S', 1),
        ('remove', 'Antimatter Charge S', 1001),
    )),
)


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    import wx
    from logbook import Logger
    from eos.const import FitSystemSecurity, ImplantLocation
    from eos.saveddata.cargo import Cargo
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from service.market import Market
    from utils.repr import makeReprStr
    from tools.android_reference.module_oracle import load

    oracle = load(source)
    service = oracle['service']
    source_files = dict(oracle['source_files'])

    def original(relative, name, namespace):
        path = source / relative
        source_files[relative] = digest_file(path)
        tree = ast.parse(path.read_bytes(), filename=str(path))
        nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name]
        if len(nodes) != 1:
            raise ValueError('Missing pinned desktop class: ' + relative)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        return namespace[name]

    common = {'wx': wx, 'Cargo': Cargo, 'Market': Market, 'makeReprStr': makeReprStr,
              'Fit': type(service), 'pyfalog': Logger('independent-cargo-oracle')}
    CargoInfo = original('gui/fitCommands/helpers.py', 'CargoInfo', common)
    common['CargoInfo'] = CargoInfo
    commands = {}
    for action, name in (('add', 'CalcAddCargoCommand'),
                         ('set', 'CalcChangeCargoAmountCommand'),
                         ('remove', 'CalcRemoveCargoCommand')):
        commands[action] = original('gui/fitCommands/calc/cargo/' +
                                    ('changeAmount' if action == 'set' else action) + '.py',
                                    name, common)

    def item(name):
        result = eos.db.getItem(name)
        assert result is not None, name
        return result

    def make_fit(ship):
        hull = item(ship)
        fit = Fit(Citadel(hull) if hull.category.name == 'Structure' else Ship(hull),
                  name='B07.1 ' + ship)
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

    def observe(fit):
        service.recalc(fit.ID)
        stats = snapshot(fit)
        stats['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'),
                                    'unit': 'mm'}
        return {'cargo': [{'id': cargo.itemID, 'name': cargo.item.name,
                           'amount': cargo.amount, 'unit_volume_m3': cargo.getModifiedItemAttr('volume')}
                          for cargo in fit.cargo],
                'used_m3': fit.cargoBayUsed,
                'capacity_m3': fit.ship.getModifiedItemAttr('capacity'),
                'stats': stats}

    cases = []
    for ship, operations in CASES:
        fit = make_fit(ship)
        steps = [{'operation': None, 'accepted': True, 'result': observe(fit)}]
        for action, name, amount in operations:
            command = commands[action](fit.ID, CargoInfo(item(name).ID, amount))
            accepted = command.Do()
            eos.db.saveddata_session.flush()
            service.recalc(fit.ID)
            eos.db.saveddata_session.commit()
            steps.append({'operation': [action, name, amount], 'accepted': accepted,
                          'result': observe(fit)})
        cases.append({'ship': ship, 'steps': steps})

    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': source_files,
            'database_logical_sha256': logical_database_digest(database),
            'eos_settings': dict(configuration.settings), 'cases': cases,
            'command': 'Original CalcAdd/Change/RemoveCargoCommand.Do with desktop recalc and commit.'}


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
    for name in ('cargo-stacks', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--source', str(args.source), '--database', str(args.database),
                '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'cargo-stacks.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    print(json.dumps({'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases']),
        'source_commit': actual['source_commit'], 'repeated': True}))


if __name__ == '__main__':
    main()
