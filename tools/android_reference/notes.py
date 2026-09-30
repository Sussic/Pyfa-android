"""Export B08 notes service and navigation behavior from the pinned desktop."""
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


def export(source, database):
    from copy import deepcopy
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.notes_oracle import load
    oracle = load(source)
    service = oracle['service']
    service.serviceFittingOptions['additionsLabels'] = 1
    market = Market.getInstance()
    market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'] = []
    fits = {}
    for key, hull in [('alpha', 'Vexor'), ('beta', 'Punisher'), ('structure', 'Astrahus')]:
        item = eos.db.getItem(hull)
        fit = Fit(Citadel(item) if item.category.name == 'Structure' else Ship(item), name='Notes ' + key)
        fit.character = Character('Independent all V', defaultLevel=5)
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity = FitSystemSecurity.HISEC, 0.0
        eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush()
        service.getFit(fit.ID); service.recalc(fit.ID)
        fits[key] = fit
    service.editNotes(fits['structure'].ID, 'Stored structure note\n保持')
    initial = {}
    for key, fit in fits.items():
        stats = snapshot(fit)
        stats['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        initial[key] = {'ship': fit.ship.item.name, 'notes': fit.notes, 'stats': stats}
    inputs = {'unicode': 'Doctrine: αβ — 探索 🚀\nSecond line\n e\u0301 and é\t  ',
              'whitespace': '  leading\n\ntrailing  \n', 'beta': 'Independent β fit\n42',
              'long': ('Offline note 漢字 🚀\n' * 256), 'structure': fits['structure'].notes}
    steps = []
    def record(kind, key=None, text=None):
        view = oracle['view']
        steps.append({'action': kind, 'fit': key, 'text': text,
            'saved': {key: value.notes for key, value in fits.items()},
            'display': view.editNotes.GetValue(), 'disabled': oracle['page'].disabled,
            'timer': view.changeTimer.pending, 'label': oracle['label'](),
            'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'])})
    def select(key):
        oracle['select'](fits[key] if key else None); record('select', key)
    def type_text(key):
        oracle['type_text'](inputs[key] if key else ''); record('type', text=inputs[key] if key else '')
    def save(): oracle['save'](); record('save')
    select('alpha'); type_text('unicode'); save()
    type_text('whitespace'); select('beta')
    type_text('beta'); select('alpha')
    type_text(None); save()
    type_text('long'); save()
    copies = {key: deepcopy(fit).notes for key,fit in fits.items()}
    select('structure'); select(None)
    try:
        service.editNotes(None, 'No active fit')
    except TypeError as failure:
        no_active_error = str(failure)
    else:
        raise AssertionError('Original service accepted an absent fit ID')
    assert copies == {key: fit.notes for key, fit in fits.items()}
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(source), name
    oracle['source_files']['eos/saveddata/fit.py'] = digest_file(source / 'eos/saveddata/fit.py')
    return {'source_commit': SOURCE_COMMIT, 'source_files': oracle['source_files'],
        'database_logical_sha256': logical_database_digest(database),
        'eos_settings': dict(configuration.settings), 'initial': initial, 'inputs': inputs,
        'steps': steps, 'copies': copies, 'no_active_error': no_active_error,
        'boundary': 'Unchanged original editNotes, NotesView event methods and EOS deepcopy; inert text/timer ports, real wx events and SQLite commits.'}


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
    for name in ('notes', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--source', str(args.source), '--database', str(args.database),
                '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=360)
    actual = json.loads((args.output / 'notes.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database)); validate_source(args.source)
    print(json.dumps({'fits': len(actual['initial']), 'states': len(actual['steps']),
        'source_commit': actual['source_commit'], 'repeated': True}))


if __name__ == '__main__':
    main()
