"""Complete empty-hull bridge parity plus atomic lifecycle/restart regressions."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import compare, digest_file, logical_database_digest
from tools.android_headless.check import DEPENDENCIES, NoDesktop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    args.database, args.output = args.database.resolve(strict=True), args.output.resolve()
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError('Use an output outside the checkout and input database')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/empty-hulls.json'
    expected = json.loads(fixture.read_text(encoding='utf-8'))
    identity = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    if not args.worker and not args.restore:
        compare(identity, logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                '--output', str(args.output), '--worker'], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update({'task': 'B04.2.1', 'host_only': True, 'database_sha256': before,
            'database_logical_sha256': identity, 'game_database_unchanged': True,
            'reference_sha256': digest_file(fixture), 'hulls': len(expected['hulls']), 'statistics_per_hull': 39})
        (args.output / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps(evidence))
        return
    guard, network = NoDesktop(), []
    sys.meta_path.insert(0, guard)
    def audit(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
            network.append(event)
            raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.catalog import hull_catalog
    engine = HeadlessEngine(args.database)
    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, None)
        before = json.loads((args.output / 'before-restart.json').read_text())
        compare(before, json.loads(bridge.bootstrap())['fits'])
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(before)}))
        return
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit')
    empty['modules'], empty['drones'] = [], []
    by_name = {row['name']: row for row in expected['hulls']}
    observations = []

    class EmptyHullTests(unittest.TestCase):
        def setUp(self):
            self.bridge = BridgeSession(engine)

        def tearDown(self):
            self.bridge._reset_storage()

        def dispatch(self, operation, arguments, ok=True):
            named = arguments.get('fit_id')
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1, 'session_id': self.bridge.session_id,
                'request_id': 'empty-hulls', 'operation': operation, 'arguments': arguments,
                'expected_revisions': {named: self.bridge._revisions[named]} if named else {}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response

        def create(self, hull, name=None):
            spec = deepcopy(empty)
            spec.update(ship=hull, name=name or 'Empty ' + hull)
            return self.dispatch('create_fit', {'spec': spec})['fits'][0]

        def test_all_437_hulls_and_every_raw_statistic(self):
            self.assertEqual(sorted(row['id'] for row in expected['hulls']), sorted(row['id'] for row in hull_catalog(engine)['hulls']))
            for row in expected['hulls']:
                with self.subTest(hull=row['name']):
                    fit = self.create(row['name'])
                    compare(row['stats'], fit['stats'])
                    self.assertEqual([], fit['modules'])
                    self.assertEqual(row['name'], fit['ship'])
                    self.assertEqual([], self.bridge.get_fit(fit['id']).drones)
                    observations.append({'id': row['id'], 'name': fit['ship'], 'stats': fit['stats']})
                    self.dispatch('delete_fit', {'fit_id': fit['id'], 'resolve_references': False})

        def test_absent_gun_ranges_are_distinct_from_calculated_zero(self):
            fit = self.create('Rifter')
            self.assertIsNone(fit['stats']['gun_optimal']['value'])
            self.assertIsNone(fit['stats']['gun_falloff']['value'])
            self.assertEqual(0, fit['stats']['total_dps']['value'])
            self.assertIsNotNone(fit['stats']['total_dps']['value'])
            self.assertEqual(39, len(fit['stats']))

        def test_non_hull_creation_is_atomic(self):
            self.create('Astrahus')
            before = self.bridge.bootstrap(), self.bridge.organization()
            for name in ('Dual 150mm Railgun II', 'No such hull'):
                spec = {**deepcopy(empty), 'ship': name}
                self.dispatch('create_fit', {'spec': spec}, ok=False)
                self.assertEqual(before, (self.bridge.bootstrap(), self.bridge.organization()))

        def test_duplicate_empty_hull_remains_independent(self):
            fit = self.create('Capsule', 'Capsule Ω')
            copied = self.dispatch('duplicate_fit', {'fit_id': fit['id'], 'name': 'Copy Δ'})['fits']
            other = next(row for row in copied if row['id'] != fit['id'])
            self.dispatch('rename_fit', {'fit_id': other['id'], 'name': 'Renamed copy'})
            self.assertEqual('Capsule Ω', self.bridge.get_fit(fit['id']).name)
            compare(by_name['Capsule']['stats'], other['stats'])

        def test_empty_ship_and_structure_survive_restart_and_failed_save(self):
            self.bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, {**deepcopy(empty), 'ship': 'Rifter'})
            structure = self.create('Astrahus')
            self.create('Capsule')
            before = self.bridge.bootstrap(), (args.output / 'fits.db').read_bytes()
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic rejected save')):
                self.dispatch('rename_fit', {'fit_id': structure['id'], 'name': 'Must not persist'}, ok=False)
            self.assertEqual(before, (self.bridge.bootstrap(), (args.output / 'fits.db').read_bytes()))
            (args.output / 'before-restart.json').write_text(json.dumps(json.loads(self.bridge.bootstrap())['fits']))
            with (args.output / 'restart.log').open('w') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--restore'], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 3}, json.loads((args.output / 'restored.json').read_text()))

        def test_empty_module_operations_reject_without_mutating_fit(self):
            fit = self.create('Rifter')
            before = self.bridge.bootstrap()
            for operation, args in [('set_charges', {'charge': 'Antimatter Charge M'}),
                                    ('set_module_states', {'state': 'ACTIVE'})]:
                self.dispatch(operation, {'fit_id': fit['id'], 'module_indices': [0], **args}, ok=False)
                self.assertEqual(before, self.bridge.bootstrap())

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EmptyHullTests))
    if result.testsRun != 6 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Empty hull regressions failed or attempted forbidden access')
    (args.output / 'observations.json').write_text(json.dumps(observations, indent=2))
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 6,
        'desktop_import_attempts': guard.attempts, 'network_attempts': network,
        'fresh_process_restore': True, 'hull_observations': len(observations)}, indent=2) + '\n')


if __name__ == '__main__':
    main()
