"""Check B07.1 cargo stacks against pinned commands and durable EOS replay."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from math import isclose
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import compare, digest_file, logical_database_digest, validate_source
from tools.android_headless.check import DEPENDENCIES, NoDesktop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT / 'build/reference-upstream')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    args.database, args.output, args.source = (
        args.database.resolve(strict=True), args.output.resolve(), args.source.resolve(strict=True))
    validate_source(args.source)
    if args.output.is_relative_to(ROOT):
        raise ValueError('Use fresh output outside checkout')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/cargo-stacks.json'
    expected = json.loads(fixture.read_text())
    identity = expected['database_logical_sha256']
    if not args.worker and not args.restore:
        compare(identity, logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--database', str(args.database), '--output', str(args.output),
                '--source', str(args.source), '--worker'],
                check=True, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update({'task': 'B07.1', 'host_only': True, 'database_sha256': before,
            'database_logical_sha256': identity, 'game_database_unchanged': True,
            'reference_sha256': digest_file(fixture)})
        (args.output / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps(evidence))
        return

    guard, network = NoDesktop(), []
    sys.meta_path.insert(0, guard)
    def audit(event, _):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
            network.append(event)
            raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    engine = HeadlessEngine(args.database)
    import eos.db
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit'); empty['modules'], empty['drones'] = [], []

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'records': deepcopy(bridge._records),
                'organization': bridge.organization(), 'recent': bridge.recent_items()}

    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity,
            {**deepcopy(empty), 'name': 'B07.1 Vexor'})
        actual, prior = saved(bridge), json.loads((args.output / 'before-restart.json').read_text())
        compare(prior, actual)
        for key in bridge._fits:
            compare(json.loads((args.output / ('cargo-before-' + key + '.json')).read_text()),
                    bridge.cargo_details(key))
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(actual['fits'])}))
        return

    class CargoTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()

        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1,
                'session_id': self.bridge.session_id, 'request_id': 'b071', 'operation': operation,
                'arguments': arguments, 'expected_revisions': {key: self.bridge._revisions[key]
                    if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response

        def create(self, ship):
            return self.dispatch('create_fit', {'spec': {**deepcopy(empty),
                'name': 'B07.1 ' + ship, 'ship': ship}})['fits'][0]['id']

        def action(self, key, operation, ok=True):
            action, name, amount = operation
            item_id = eos.db.getItem(name).ID
            method = {'add': 'add_cargo', 'set': 'set_cargo_quantity', 'remove': 'remove_cargo'}[action]
            return self.dispatch(method, {'fit_id': key, 'item_id': item_id,
                                          'quantity': amount}, ok)

        def compare_state(self, reference, key):
            actual = self.bridge.cargo_details(key)
            compare(reference['cargo'], actual['cargo'])
            for label, field in [('used_m3', 'used_m3'), ('capacity_m3', 'capacity_m3')]:
                self.assertTrue(isclose(reference[label], actual[field], rel_tol=1e-10,
                                        abs_tol=1e-9), (label, reference[label], actual[field]))
            self.assertEqual(reference['used_m3'] > reference['capacity_m3'], actual['over_capacity'])
            original, got = reference['stats'], self.bridge._snapshots[key]['stats']
            self.assertEqual(original.keys(), got.keys())
            for name, value in original.items():
                self.assertEqual(value['unit'], got[name]['unit'], name)
                a, b = value['value'], got[name]['value']
                if b is None and name in ('gun_optimal', 'gun_falloff'):
                    self.assertIn(a, (0, 1), name)
                elif type(a) in (int, float) and type(b) in (int, float):
                    self.assertTrue(isclose(a, b, rel_tol=1e-10, abs_tol=1e-9), (name, a, b))
                else: self.assertEqual(a, b, name)

        def test_all_original_states(self):
            for case in expected['cases']:
                key = self.create(case['ship'])
                for index, step in enumerate(case['steps']):
                    if step['operation'] is not None:
                        self.action(key, step['operation'], step['accepted'])
                    try: self.compare_state(step['result'], key)
                    except Exception as error:
                        raise AssertionError(f"{case['ship']} step {index}: {step['operation']}: {error}") from error

        def test_atomic_rejection_and_legacy_graph(self):
            key = self.create('Vexor')
            self.assertNotIn('cargo', self.bridge._records[key]['spec'])
            before = saved(self.bridge)
            valid = eos.db.getItem('Antimatter Charge S').ID
            for operation, item_id, quantity in [('add_cargo', valid, 0),
                    ('add_cargo', valid, True), ('add_cargo', -1, 1),
                    ('set_cargo_quantity', valid, 1), ('remove_cargo', valid, 1)]:
                self.dispatch(operation, {'fit_id': key, 'item_id': item_id,
                                          'quantity': quantity}, False)
            compare(before, saved(self.bridge))

        def test_copy_restart_and_failed_save(self):
            self.bridge._reset_storage()
            (args.output / 'durable.db').unlink(missing_ok=True)
            self.bridge = BridgeSession.open(engine, args.output / 'durable.db', identity,
                {**deepcopy(empty), 'name': 'B07.1 Vexor'})
            key = self.bridge.sample_id
            case = expected['cases'][0]
            for step in case['steps'][1:]:
                if step['accepted']:
                    self.action(key, step['operation'])
            self.compare_state(case['steps'][-1]['result'], key)
            copy = self.dispatch('duplicate_fit', {'fit_id': key, 'name': 'B07.1 cargo copy'})['fits'][-1]['id']
            self.compare_state(case['steps'][-1]['result'], copy)
            prior = saved(self.bridge)
            (args.output / 'before-restart.json').write_text(json.dumps(prior))
            for fit_id in self.bridge._fits:
                (args.output / ('cargo-before-' + fit_id + '.json')).write_text(
                    json.dumps(self.bridge.cargo_details(fit_id)))
            shutil.copyfile(args.output / 'durable.db', args.output / 'fits.db')
            with (args.output / 'restart.log').open('w', encoding='utf-8') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                    '--database', str(args.database), '--output', str(args.output),
                    '--source', str(args.source), '--restore'],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 2}, json.loads((args.output / 'restored.json').read_text()))
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic save failure')):
                self.action(key, ('add', 'Antimatter Charge S', 5), False)
            compare(prior, saved(self.bridge))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CargoTests))
    if result.testsRun != 3 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Cargo stack regressions failed or attempted forbidden access')
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 3,
        'cases': len(expected['cases']),
        'states': sum(len(case['steps']) for case in expected['cases']),
        'fresh_process_restore': True, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network}, indent=2) + '\n')


if __name__ == '__main__': main()
