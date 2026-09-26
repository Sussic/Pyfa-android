"""Export B06.3 structure service commands from the pinned desktop source."""
import argparse
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
    ('Astrahus', (
        ('add', 'Standup Manufacturing Plant I'),
        ('add', 'Standup Reprocessing Facility I'),
        ('add', 'Standup Research Lab I'),
        ('add', 'Standup Invention Lab I'),
        ('replace', 'Standup Manufacturing Plant I', 'Standup Invention Lab I'),
        ('remove', 'Standup Reprocessing Facility I'),
        ('add', 'Standup Reprocessing Facility I'),
        ('add', 'Standup Capital Shipyard I'),
        ('add', '200mm AutoCannon II'),
    )),
    ('Fortizar', (
        ('add', 'Standup Market Hub I'),
        ('add', 'Standup Manufacturing Plant I'),
        ('add', 'Standup Reprocessing Facility I'),
        ('remove', 'Standup Manufacturing Plant I'),
    )),
    ('Athanor', (
        ('add', 'Standup Moon Drill I'),
        ('add', 'Standup Composite Reactor I'),
        ('add', 'Standup Reprocessing Facility I'),
        ('add', 'Standup Research Lab I'),
    )),
    ('Ansiblex Jump Bridge', (
        ('add', 'Standup Conduit Generator I'),
        ('add', 'Standup Manufacturing Plant I'),
        ('remove', 'Standup Conduit Generator I'),
    )),
    ('Metenox Moon Drill', (
        ('add', 'Standup Metenox Moon Drill'),
        ('add', 'Standup Conduit Generator I'),
    )),
)


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FitSystemSecurity, FittingModuleState, FittingSlot, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship
    from tools.android_reference.module_oracle import load

    oracle = load(source)
    service = oracle['service']

    def item(name):
        value = eos.db.getItem(name)
        assert value is not None, name
        return value

    def make_fit(ship):
        hull = item(ship)
        fit = Fit(Citadel(hull) if hull.category.name == 'Structure' else Ship(hull),
                  name='B06.3 ' + ship)
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
        return {'modules': [{'index': index, 'id': module.itemID,
                             'name': module.item.name if module.item else None,
                             'slot': FittingSlot(module.slot).name,
                             'state': FittingModuleState(module.state).name,
                             'charge': module.charge.name if module.charge else None,
                             'legal': None if module.isEmpty else module.fits(fit)}
                            for index, module in enumerate(fit.modules)],
                'slots': [{'slot': slot.name, 'used': fit.getSlotsUsed(slot.value),
                           'total': fit.getNumSlots(slot.value)} for slot in
                          (FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH,
                           FittingSlot.RIG, FittingSlot.SERVICE)],
                'resources': {'cpu_used': fit.cpuUsed,
                              'cpu_total': fit.ship.getModifiedItemAttr('cpuOutput'),
                              'powergrid_used': fit.pgUsed,
                              'powergrid_total': fit.ship.getModifiedItemAttr('powerOutput')},
                'stats': stats}

    cases = []
    for ship, operations in CASES:
        fit = make_fit(ship)
        steps = [{'operation': None, 'accepted': True, 'result': observe(fit)}]
        for operation in operations:
            action, name, *rest = operation
            if action in ('add', 'replace'):
                value = item(name if action == 'add' else rest[0])
                info = oracle['ModuleInfo'](value.ID)
                if action == 'add':
                    command = oracle['commands']['localAdd'](fit.ID, info)
                else:
                    old = item(name)
                    position = next(index for index, module in enumerate(fit.modules)
                                    if module.itemID == old.ID)
                    command = oracle['commands']['localReplace'](fit.ID, position, info)
            elif action == 'remove':
                old = item(name)
                position = next(index for index, module in enumerate(fit.modules)
                                if module.itemID == old.ID)
                command = oracle['commands']['localRemove'](fit.ID, [position])
            else:
                raise ValueError(action)
            accepted = command.Do()
            if command.needsGuiRecalc:
                eos.db.saveddata_session.flush()
                service.recalc(fit)
            service.fill(fit)
            eos.db.saveddata_session.commit()
            steps.append({'operation': list(operation), 'accepted': accepted, 'result': observe(fit)})
        cases.append({'ship': ship, 'steps': steps})

    service_items = []
    for value in eos.db.getItemsByCategory('Structure Module'):
        if not value.published:
            continue
        try:
            module = Module(value)
        except ValueError:
            continue
        if not module.isInvalid and module.slot == FittingSlot.SERVICE:
            service_items.append(value)
    choices = {}
    for hull in eos.db.getItemsByCategory('Structure'):
        fit = make_fit(hull.name)
        choices[hull.name] = {'capacity': int(fit.getNumSlots(FittingSlot.SERVICE.value)),
                              'items': [{'id': value.ID, 'name': value.name} for value in service_items
                                        if fit.canFit(value)]}
    choices['Vexor'] = {'capacity': 0, 'items': []}
    for row in choices.values():
        row['items'].sort(key=lambda choice: choice['id'])
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
            'database_logical_sha256': logical_database_digest(database),
            'eos_settings': dict(configuration.settings), 'choices': choices, 'cases': cases,
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
    for name in ('structures', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--source', str(args.source), '--database', str(args.database),
                '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'structures.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    print(json.dumps({'cases': len(actual['cases']),
        'states': sum(len(case['steps']) for case in actual['cases']),
        'hulls': len(actual['choices']), 'source_commit': actual['source_commit'], 'repeated': True}))


if __name__ == '__main__':
    main()
