"""Export B06.2 strategic-cruiser subsystem changes via pinned desktop commands."""
import argparse
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


OPERATIONS = [
    ('add', 'Tengu Offensive - Accelerated Ejection Bay'),
    ('add', 'Heavy Missile Launcher II', 'Scourge Heavy Missile'),
    ('add', 'Tengu Defensive - Supplemental Screening'),
    ('add', 'Tengu Propulsion - Chassis Optimization'),
    ('add', 'Tengu Core - Augmented Graviton Reactor'),
    ('add', 'Tengu Offensive - Support Processor'),
    ('replace', 'Tengu Offensive - Accelerated Ejection Bay', 'Tengu Offensive - Support Processor'),
    ('remove', 'Tengu Offensive - Accelerated Ejection Bay'),
    ('add', 'Tengu Offensive - Accelerated Ejection Bay'),
    ('replace', 'Tengu Defensive - Covert Reconfiguration', 'Tengu Defensive - Supplemental Screening'),
    ('remove', 'Tengu Defensive - Covert Reconfiguration'),
    ('add', 'Tengu Defensive - Supplemental Screening'),
    ('add', 'Legion Core - Augmented Antimatter Reactor'),
]


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FitSystemSecurity, FittingHardpoint, FittingModuleState, FittingSlot, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from tools.android_reference.module_oracle import load

    oracle = load(source)
    service = oracle['service']

    def item(name):
        value = eos.db.getItem(name)
        assert value is not None, name
        return value

    def make_fit(ship):
        fit = Fit(Ship(item(ship)), name='B06.2 ' + ship)
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
        values = snapshot(fit)
        values['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        slots = [{'slot': slot.name, 'used': fit.getSlotsUsed(slot.value),
                  'total': fit.getNumSlots(slot.value)} for slot in
                 (FittingSlot.SUBSYSTEM, FittingSlot.HIGH, FittingSlot.MED,
                  FittingSlot.LOW, FittingSlot.RIG, FittingSlot.SERVICE)]
        modules = [{'index': index, 'id': mod.itemID, 'name': mod.item.name if mod.item else None,
                    'slot': FittingSlot(mod.slot).name, 'state': FittingModuleState(mod.state).name,
                    'charge': mod.charge.name if mod.charge else None,
                    'legal': None if mod.isEmpty else mod.fits(fit)}
                   for index, mod in enumerate(fit.modules)]
        return {'modules': modules, 'slots': slots,
                'hardpoints': [{'kind': kind.name, 'used': fit.getHardpointsUsed(kind),
                                'total': fit.ship.getModifiedItemAttr(attribute)}
                               for kind, attribute in ((FittingHardpoint.TURRET, 'turretSlotsLeft'),
                                                       (FittingHardpoint.MISSILE, 'launcherSlotsLeft'))],
                'resources': {'cpu_used': fit.cpuUsed, 'cpu_total': fit.ship.getModifiedItemAttr('cpuOutput'),
                              'powergrid_used': fit.pgUsed, 'powergrid_total': fit.ship.getModifiedItemAttr('powerOutput')},
                'stats': values}

    fit = make_fit('Tengu')
    steps = [{'operation': None, 'accepted': True, 'result': observe(fit)}]
    for operation in OPERATIONS:
        name = operation[0]
        if name in ('add', 'replace'):
            value = item(operation[1])
            info = oracle['ModuleInfo'](value.ID,
                chargeID=item(operation[2]).ID if name == 'add' and len(operation) == 3 else None)
            if name == 'add':
                command = oracle['commands']['localAdd'](fit.ID, info)
            else:
                old = item(operation[2])
                position = next(index for index, mod in enumerate(fit.modules) if mod.itemID == old.ID)
                command = oracle['commands']['localReplace'](fit.ID, position, info)
        elif name == 'remove':
            value = item(operation[1])
            position = next(index for index, mod in enumerate(fit.modules) if mod.itemID == value.ID)
            command = oracle['commands']['localRemove'](fit.ID, [position])
        else:
            raise ValueError(name)
        accepted = command.Do()
        if command.needsGuiRecalc:
            eos.db.saveddata_session.flush()
            service.recalc(fit)
        service.fill(fit)
        eos.db.saveddata_session.commit()
        steps.append({'operation': list(operation), 'accepted': accepted, 'result': observe(fit)})

    choices = {}
    for ship in ('Tengu', 'Legion', 'Loki', 'Proteus', 'Vexor'):
        current = make_fit(ship)
        rows = []
        for value in eos.db.getItemsByCategory('Subsystem'):
            if current.canFit(value):
                from eos.saveddata.module import Module
                rows.append({'id': value.ID, 'name': value.name,
                             'type': int(Module(value).getModifiedItemAttr('subSystemSlot'))})
        choices[ship] = sorted(rows, key=lambda row: (row['type'], row['id']))
    assert {key: len(value) for key, value in choices.items()} == {
        'Tengu': 12, 'Legion': 12, 'Loki': 12, 'Proteus': 12, 'Vexor': 0}
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
            'eos_settings': dict(configuration.settings), 'choices': choices,
            'cases': [{'ship': 'Tengu', 'steps': steps}],
            'command': 'Original local add/replace/remove Do plus desktop GUI flush/recalc/fill.'}


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
    for name in ('subsystems', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--source', str(args.source), '--database', str(args.database),
                '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'subsystems.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    print(json.dumps({'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases']),
        'source_commit': actual['source_commit'], 'repeated': True}))


if __name__ == '__main__':
    main()
