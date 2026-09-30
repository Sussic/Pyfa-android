"""Check B07.3 selected cargo actions against pinned commands and durable EOS replay."""
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
    fixture = ROOT / 'tools/android_reference/fixtures/cargo-transfers.json'
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
        evidence.update({'task': 'B07.3', 'host_only': True, 'database_sha256': before,
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
            {**deepcopy(empty), 'name': 'B07.3 Vexor'})
        actual, prior = saved(bridge), json.loads((args.output / 'before-restart.json').read_text())
        compare(prior, actual)
        for key in bridge._fits:
            compare(json.loads((args.output / ('cargo-before-' + key + '.json')).read_text()),
                    bridge.cargo_transfer_details(key))
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(actual['fits'])}))
        return

    class TransferTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()

        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1,
                'session_id': self.bridge.session_id, 'request_id': 'b073', 'operation': operation,
                'arguments': arguments, 'expected_revisions': {key: self.bridge._revisions[key]
                    if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response

        def create(self, case):
            initial = case['steps'][0]['result']
            modules = [({'empty_slot': m['slot']} if m['id'] is None else
                        {'name': m['name'], 'state': m['state'], 'charge': m['charge']})
                       for m in initial['modules']]
            return self.dispatch('create_fit', {'spec': {**deepcopy(empty),
                'name': 'B07.3 ' + case['name'], 'ship': case['ship'], 'modules': modules,
                'cargo': deepcopy(case['cargo'])}})['fits'][0]['id']

        def arguments(self, key, operation):
            return {'fit_id': key, 'direction': operation['kind'].upper(),
                    'positions': operation.get('positions', [operation.get('position')]), 'item_id': operation['cargo_item_id'],
                    'copy': operation['copy']}

        def compare_state(self, reference, key):
            actual = self.bridge.cargo_transfer_details(key)
            compare(reference['modules'], actual['modules'])
            compare(sorted(reference['cargo'], key=lambda row: row['id']),
                    sorted(actual['cargo'], key=lambda row: row['id']))
            compare(reference['recent'], self.bridge.recent_items()['item_ids'])
            for field in ('used_m3', 'capacity_m3'):
                self.assertTrue(isclose(reference[field], actual[field], rel_tol=1e-10, abs_tol=1e-9),
                                (field, reference[field], actual[field]))
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

        def sequence(self, case, key):
            last = case['steps'][0]['result']
            self.compare_state(last, key)
            for index, step in enumerate(case['steps'][1:], 1):
                operation = step['operation']
                previous = saved(self.bridge)
                target = self.bridge.cargo_transfer_details(key)['modules'][operation.get('position', 0)]
                noop = (operation['kind'] == 'to_cargo' and target['id'] is None or
                        operation['cargo_item_id'] is not None and
                        operation['cargo_item_id'] in (target['id'], target['charge_id']))
                accepted = step['changed'] or noop
                self.dispatch('transfer_cargo', self.arguments(key, operation), accepted)
                if not accepted:
                    compare(previous, saved(self.bridge))
                else:
                    last = step['result']
                try: self.compare_state(last, key)
                except Exception as error:
                    raise AssertionError(f"{case['name']} step {index} {operation}: {error}") from error
            return last

        def test_all_original_states(self):
            for case in expected['cases']:
                key = self.create(case)
                self.sequence(case, key)
            # Preserve the upstream failure as evidence; do not erase or adopt it.
            last = expected['cases'][-1]['steps']
            self.assertFalse(last[-1]['changed'])
            before = next(c['amount'] for c in last[-2]['result']['cargo'] if c['name'] == 'Small Shield Extender I')
            after = next(c['amount'] for c in last[-1]['result']['cargo'] if c['name'] == 'Small Shield Extender I')
            self.assertEqual(before * 2, after)

        def test_atomic_rejection_bulk_and_overflow(self):
            key = self.create(expected['cases'][0])
            valid = {'fit_id': key, 'direction': 'TO_CARGO', 'positions': [0], 'item_id': None, 'copy': True}
            before = saved(self.bridge)
            for fields in ({'positions': []}, {'positions': [0,0]}, {'positions': [True]},
                           {'positions': [0,999]}, {'positions': [-1]}, {'copy': 1},
                           {'direction': 'sideways'}, {'item_id': 222}, {'item_id': True},
                           {'direction': 'FROM_CARGO'}, {'direction': 'FROM_CARGO', 'positions': [0,1]}):
                self.dispatch('transfer_cargo', {**valid, **fields}, False)
                compare(before, saved(self.bridge))
            self.dispatch('transfer_cargo', valid, False, revision=0)
            compare(before, saved(self.bridge))
            from android_bridge import cargo_transfers
            actual_add = cargo_transfers._add
            count = 0
            def fail_second(*args):
                nonlocal count
                count += 1
                if count == 2: raise ValueError('Synthetic partial transfer failure')
                return actual_add(*args)
            with patch.object(cargo_transfers, '_add', side_effect=fail_second):
                self.dispatch('transfer_cargo', valid, False)
            compare(before, saved(self.bridge))
            self.dispatch('transfer_cargo', valid)
            gun = eos.db.getItem('Dual 150mm Railgun II').ID
            self.dispatch('set_cargo_quantity', {'fit_id': key, 'item_id': gun, 'quantity': 2**63-1})
            before = saved(self.bridge)
            self.dispatch('transfer_cargo', valid, False)
            compare(before, saved(self.bridge))
            # Two selected modules are one atomic command, including second-item failure.
            key = self.create(expected['cases'][0])
            self.dispatch('add_module', {'fit_id': key, 'item_id': gun})
            indices = [row['index'] for row in self.bridge.cargo_transfer_details(key)['modules'] if row['id']]
            self.assertEqual(2, len(indices))
            batch = {**valid, 'fit_id': key, 'positions': indices}
            before = saved(self.bridge); count = 0
            with patch.object(cargo_transfers, '_add', side_effect=fail_second):
                self.dispatch('transfer_cargo', batch, False)
            compare(before, saved(self.bridge))
            self.dispatch('transfer_cargo', batch)
            self.assertEqual(2, next(row['amount'] for row in self.bridge.cargo_transfer_details(key)['cargo'] if row['id'] == gun))
            self.dispatch('transfer_cargo', {**batch, 'copy': False})
            self.assertFalse(any(row['id'] for row in self.bridge.cargo_transfer_details(key)['modules']))

        def test_native_setup_matches_reference_inputs(self):
            history = []
            for case in expected['cases']:
                baseline = deepcopy(case['steps'][0]['result'])
                modules = [{'name': row['name'], 'state': row['state'], 'charge': row['charge']}
                           for row in baseline['modules'] if row['id'] is not None]
                key = self.dispatch('create_fit', {'spec': {**deepcopy(empty),
                    'name': case['name'], 'ship': case['ship'], 'modules': modules}})['fits'][0]['id']
                self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
                for row in case['cargo']:
                    item = eos.db.getItem(row['name'])
                    if self.bridge._fits[key].isStructure and item.category.name != 'Charge':
                        self.dispatch('add_module', {'fit_id': key, 'item_id': item.ID})
                        position = next(value['index'] for value in self.bridge.cargo_transfer_details(key)['modules']
                                        if value['id'] == item.ID)
                        self.dispatch('transfer_cargo', {'fit_id': key, 'direction': 'TO_CARGO',
                            'positions': [position], 'item_id': None, 'copy': False})
                        if row['amount'] != 1:
                            self.dispatch('set_cargo_quantity', {'fit_id': key, 'item_id': item.ID, 'quantity': row['amount']})
                    else:
                        self.dispatch('add_cargo', {'fit_id': key, 'item_id': item.ID, 'quantity': row['amount']})
                    history = [item.ID] + [value for value in history if value != item.ID][:19]
                baseline['recent'] = history[:]
                self.compare_state(baseline, key)

        def test_copy_restart_and_failed_save(self):
            self.bridge._reset_storage()
            self.bridge = BridgeSession.open(engine, args.output / 'durable.db', identity,
                {**deepcopy(empty), 'name': 'B07.3 Vexor'})
            for case in expected['cases']:
                key = self.create(case)
                last = self.sequence(case, key)
                copy = self.dispatch('duplicate_fit', {'fit_id': key,
                    'name': 'B07.3 copy ' + case['name']})['fits'][-1]['id']
                self.compare_state(last, copy)
            prior = saved(self.bridge)
            (args.output / 'before-restart.json').write_text(json.dumps(prior))
            for fit_id in self.bridge._fits:
                (args.output / ('cargo-before-' + fit_id + '.json')).write_text(
                    json.dumps(self.bridge.cargo_transfer_details(fit_id)))
            shutil.copyfile(args.output / 'durable.db', args.output / 'fits.db')
            with (args.output / 'restart.log').open('w', encoding='utf-8') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                    '--database', str(args.database), '--output', str(args.output),
                    '--source', str(args.source), '--restore'],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 1 + 2*len(expected['cases'])}, json.loads((args.output / 'restored.json').read_text()))
            key = self.create(expected['cases'][1])
            prior = saved(self.bridge)
            for operation in [dict(kind='to_cargo',position=0,cargo_item_id=None,copy=False),
                              expected['cases'][1]['steps'][1]['operation']]:
                with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic save failure')):
                    self.dispatch('transfer_cargo', self.arguments(key, operation), False)
                compare(prior, saved(self.bridge))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TransferTests))
    if result.testsRun != 4 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Cargo transfer regressions failed or attempted forbidden access')
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 4,
        'cases': len(expected['cases']), 'states': sum(len(case['steps']) for case in expected['cases']),
        'fresh_process_restore': True, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network}, indent=2) + '\n')


if __name__ == '__main__': main()
