"""Independently calculate every bundled empty hull with pinned desktop EOS."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (
    SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare, digest_file,
    logical_database_digest, snapshot, validate_source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    args.source, args.database, args.output = args.source.resolve(), args.database.resolve(strict=True), args.output.resolve()
    validate_source(args.source)
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    if args.worker:
        configuration = bootstrap(args.source, args.database)
        import config
        config.pyfaPath = str(args.source)
        import eos.db
        from eos.const import FitSystemSecurity, ImplantLocation
        from eos.saveddata.character import Character
        from eos.saveddata.citadel import Citadel
        from eos.saveddata.damagePattern import DamagePattern
        from eos.saveddata.fit import Fit
        from eos.saveddata.ship import Ship
        from service.market import Market
        market = Market.getInstance()
        hulls = {item.ID: item for group in market.getShipRoot() for item in market.getShipList(group.ID)}
        expected_catalog = json.loads((ROOT / 'tools/android_reference/fixtures/catalog.json').read_text())
        compare(sorted(item['id'] for item in expected_catalog['hulls']), sorted(hulls))
        results = []
        for id, item in sorted(hulls.items()):
            # The original service.fit.newFit selects Ship/Citadel identically;
            # construct original EOS objects with explicit reproducible inputs.
            # No desktop service or engine method is patched or substituted.
            hull = Ship(item) if item.category.name == 'Ship' else Citadel(item)
            fit = Fit(hull, name='Empty ' + item.name)
            fit.character = Character('Independent all-V skills', defaultLevel=5)
            fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
            fit.targetProfile = None
            fit.factorReload = False
            fit.implantLocation = ImplantLocation.FIT
            fit.systemSecurity = FitSystemSecurity.HISEC
            fit.pilotSecurity = 0.0
            fit.ignoreRestrictions = False
            fit.calculateModifiedAttributes()
            assert fit.fits and not fit.modules and not fit.drones
            stats = snapshot(fit)
            stats['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
            assert len(stats) == 39 and stats['gun_optimal']['value'] is None and stats['gun_falloff']['value'] is None
            results.append({'id': id, 'name': item.name, 'category': item.category.name, 'stats': stats})
        assert not any(name.startswith('android_bridge') for name in sys.modules)
        for name, module in list(sys.modules.items()):
            if name.split('.')[0] in ('eos', 'service', 'config') and getattr(module, '__file__', None):
                assert Path(module.__file__).resolve().is_relative_to(args.source), name
        result = {'source_commit': SOURCE_COMMIT, 'eos_settings': dict(configuration.settings),
            'inputs': {'skill_level': 5, 'factor_reload': False, 'system_security': 'HISEC',
                'pilot_security': 0.0, 'uniform_damage': [25, 25, 25, 25], 'modules': [], 'drones': [],
                'implants': [], 'boosters': [], 'projections': [], 'commands': [], 'environments': []},
            'hulls': results}
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        return
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError('Use a new output outside the checkout and input database')
    baseline = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())
    compare(baseline['database_logical_sha256'], logical_database_digest(args.database))
    before = digest_file(args.database)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ('hulls', 'repeat'):
        with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', str(args.source),
                '--database', str(args.database), '--output', str(args.output / (name + '.json')), '--worker'],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
    actual = json.loads((args.output / 'hulls.json').read_text())
    compare(actual, json.loads((args.output / 'repeat.json').read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database))
    validate_source(args.source)
    receipt = {'task': 'B04.2.1', 'source_commit': SOURCE_COMMIT,
        'database_logical_sha256': baseline['database_logical_sha256'], 'database_sha256': before,
        'fresh_process_repeat': True, 'game_database_unchanged': True,
        'reference_sha256': digest_file(args.output / 'hulls.json'), 'hulls': len(actual['hulls']),
        'statistics_per_hull': 39, 'null_means_absent': True}
    (args.output / 'evidence.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
