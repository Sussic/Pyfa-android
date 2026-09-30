"""Check B07.2 selected cargo actions against pinned commands and durable EOS replay."""
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
from types import SimpleNamespace

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
    fixture = ROOT / 'tools/android_reference/fixtures/cargo-actions.json'
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
        evidence.update({'task': 'B07.2', 'host_only': True, 'database_sha256': before,
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
            {**deepcopy(empty), 'name': 'B07.2 Vexor'})
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
                'session_id': self.bridge.session_id, 'request_id': 'b072', 'operation': operation,
                'arguments': arguments, 'expected_revisions': {key: self.bridge._revisions[key]
                    if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response

        def create(self, ship):
            return self.dispatch('create_fit', {'spec': {**deepcopy(empty),
                'name': 'B07.2 ' + ship, 'ship': ship}})['fits'][0]['id']

        def action(self, key, operation, ok=True):
            kind = operation['kind']
            arguments = {'fit_id': key}
            if 'item' in operation:
                arguments['item_id'] = eos.db.getItem(operation['item']).ID
            if 'selected' in operation:
                arguments['item_ids'] = [eos.db.getItem(name).ID for name in operation['selected']]
            if 'quantity' in operation:
                arguments['quantity'] = operation['quantity']
            if kind.startswith('fill_'):
                arguments['from_cargo'] = kind == 'fill_cargo'
            if kind == 'variation':
                arguments['main_item_id'] = eos.db.getItem(operation['main']).ID
            method = {'add': 'add_cargo', 'quantity': 'set_cargo_quantities',
                'remove': 'remove_cargos', 'preset': 'add_cargo_preset',
                'fill_market': 'fill_cargo', 'fill_cargo': 'fill_cargo',
                'variation': 'change_cargo_variations'}[kind]
            return self.dispatch(method, arguments, ok)

        def compare_state(self, reference, key):
            actual = self.bridge.cargo_details(key)
            compare(reference['cargo'], actual['cargo'])
            compare(reference['recent'], self.bridge.recent_items()['item_ids'])
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
                        operation, outcome = step['operation'], step['outcome']
                        if operation['kind'] in ('preset', 'fill_market', 'fill_cargo', 'variation'):
                            item_id = eos.db.getItem(operation.get('main', operation['item'])).ID
                            options = self.bridge.cargo_action_options(key, item_id,
                                operation['kind'] in ('fill_cargo', 'variation'))
                            if operation['kind'] == 'variation':
                                compare(outcome['variations'], options['variations'])
                            else:
                                field = 'preset_quantity' if operation['kind'] == 'preset' else 'fill_quantity'
                                quantity = (outcome['submitted'][0]['quantity'] if outcome['submitted'] else
                                            0 if outcome['visible'] else None)
                                compare(quantity, options[field])
                        self.action(key, step['operation'], step['outcome']['visible'])
                    try: self.compare_state(step['result'], key)
                    except Exception as error:
                        raise AssertionError(f"{case['ship']} step {index}: {step['operation']}: {error}") from error

        def test_atomic_rejection_and_legacy_graph(self):
            key = self.create('Vexor')
            self.assertNotIn('cargo', self.bridge._records[key]['spec'])
            self.action(key, {'kind': 'add', 'item': '200mm AutoCannon I', 'quantity': 2})
            self.action(key, {'kind': 'add', 'item': 'Antimatter Charge S', 'quantity': 3})
            gun, ammo, other = (eos.db.getItem(name).ID for name in
                ('200mm AutoCannon I', 'Antimatter Charge S', '200mm AutoCannon II'))
            before = saved(self.bridge)
            for boundary in expected['synthetic_volume_boundaries']:
                fake = SimpleNamespace(ID=ammo, isCharge=True, isCommodity=False, marketGroup=None,
                    category=SimpleNamespace(ID=8), attributes={'volume': SimpleNamespace(value=boundary['volume'])})
                with patch('android_bridge.fitting.item', return_value=fake):
                    options = self.bridge.cargo_action_options(key, ammo, False)
                    self.assertTrue(boundary['visible'])
                    self.assertEqual(boundary['submitted_count'], options['fill_quantity'])
                    self.assertEqual(0, options['fill_quantity'])
            compare(before, saved(self.bridge))
            bad = [('set_cargo_quantities', {'item_ids': ids, 'quantity': quantity})
                   for ids, quantity in [([], 1), ([gun, gun], 1), ([gun, other], 2),
                     ([True], 1), ([gun], True), ([gun], -1), ([gun], 2**63), ([gun], 1.0)]]
            bad += [('remove_cargos', {'item_ids': [ammo, other]}),
                ('add_cargo_preset', {'item_id': gun}),
                ('fill_cargo', {'item_id': gun, 'from_cargo': False}),
                ('fill_cargo', {'item_id': other, 'from_cargo': True}),
                ('fill_cargo', {'item_id': ammo, 'from_cargo': 1}),
                ('change_cargo_variations', {'main_item_id': other, 'item_ids': [gun], 'item_id': other}),
                ('change_cargo_variations', {'main_item_id': gun, 'item_ids': [gun], 'item_id': ammo})]
            for method, arguments in bad:
                self.dispatch(method, {'fit_id': key, **arguments}, False)
                compare(before, saved(self.bridge))
            self.dispatch('set_cargo_quantities', {'fit_id': key, 'item_ids': [gun, ammo],
                'quantity': 5}, False, revision=1)
            compare(before, saved(self.bridge))
            # A failure after the first removal must restore the complete graph.
            with patch('android_bridge.cargo.change', side_effect=ValueError('synthetic add failure')):
                self.dispatch('change_cargo_variations', {'fit_id': key, 'main_item_id': gun,
                    'item_ids': [gun, ammo], 'item_id': other}, False)
            compare(before, saved(self.bridge))
            # Safe addition overflow must not leave the old stack removed.
            self.action(key, {'kind': 'add', 'item': '200mm AutoCannon II', 'quantity': 2**63 - 1})
            before = saved(self.bridge)
            self.dispatch('change_cargo_variations', {'fit_id': key, 'main_item_id': gun,
                'item_ids': [gun, other], 'item_id': other}, False)
            compare(before, saved(self.bridge))

        def test_copy_restart_and_failed_save(self):
            self.bridge._reset_storage()
            self.bridge = BridgeSession.open(engine, args.output / 'durable.db', identity,
                {**deepcopy(empty), 'name': 'B07.2 Vexor'})
            for case in expected['cases']:
                key = self.create(case['ship'])
                for step in case['steps'][1:]:
                    self.action(key, step['operation'], step['outcome']['visible'])
                self.compare_state(case['steps'][-1]['result'], key)
                copy = self.dispatch('duplicate_fit', {'fit_id': key,
                    'name': 'B07.2 copy ' + case['name']})['fits'][-1]['id']
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
            self.assertEqual({'matched': True, 'fits': 11}, json.loads((args.output / 'restored.json').read_text()))
            key = self.bridge.sample_id
            self.action(key, {'kind': 'preset', 'item': 'Antimatter Charge S'})
            self.action(key, {'kind': 'preset', 'item': 'Core Scanner Probe I'})
            prior = saved(self.bridge)
            for operation in [
                    {'kind': 'quantity', 'selected': ['Antimatter Charge S', 'Core Scanner Probe I'], 'quantity': 0},
                    {'kind': 'remove', 'selected': ['Antimatter Charge S', 'Core Scanner Probe I']},
                    {'kind': 'preset', 'item': 'Core Scanner Probe I'},
                    {'kind': 'fill_cargo', 'item': 'Antimatter Charge S'}]:
                with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic save failure')):
                    self.action(key, operation, False)
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
