"""Compare B06.1 bridge modes to pinned desktop commands and durable graph state."""
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
    fixture = ROOT / 'tools/android_reference/fixtures/hull-modes.json'
    expected = json.loads(fixture.read_text())
    identity = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    if not args.worker and not args.restore:
        compare(identity, logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                '--output', str(args.output), '--source', str(args.source), '--worker'],
                check=True, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update({'task': 'B06.1', 'host_only': True, 'database_sha256': before,
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
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit'); empty['modules'], empty['drones'] = [], []

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'records': deepcopy(bridge._records),
                'organization': bridge.organization(), 'recent': bridge.recent_items()}
    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, None)
        compare(json.loads((args.output / 'before-restart.json').read_text()), saved(bridge))
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(bridge._fits)}))
        return

    def comparable(value):
        if isinstance(value, dict):
            if value.keys() == {'value', 'unit'} and type(value['value']) in (int, float):
                return {'value': float(value['value']), 'unit': value['unit']}
            return {key: comparable(child) for key, child in value.items()}
        if isinstance(value, list):
            return [comparable(child) for child in value]
        return value

    class ModeTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1,
                'session_id': self.bridge.session_id, 'request_id': 'b061', 'operation': operation,
                'arguments': arguments, 'expected_revisions': {key: self.bridge._revisions[key]
                    if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response
        def create(self, ship):
            return self.dispatch('create_fit', {'spec': {**deepcopy(empty), 'name': 'B06.1 ' + ship,
                'ship': ship}})['fits'][0]['id']
        def stats(self, key):
            return comparable(deepcopy(self.bridge._snapshots[key]['stats']))
        def test_original_choices_and_all_raw_states(self):
            for case in expected['cases']:
                with self.subTest(ship=case['ship']):
                    key = self.create(case['ship'])
                    for step in case['steps']:
                        options = self.bridge.mode_options(key)
                        compare(case['choices'], options['choices'])
                        if step['requested'] is not None:
                            self.dispatch('change_mode', {'fit_id': key, 'item_id': step['requested']})
                        options = self.bridge.mode_options(key)
                        self.assertEqual(step['result']['mode_id'], options['current'])
                        reference = comparable(deepcopy(step['result']['stats']))
                        actual = self.stats(key)
                        for field in ('gun_optimal', 'gun_falloff'):
                            if reference[field]['value'] in (0.0, 1.0) and actual[field]['value'] is None:
                                reference[field]['value'] = None
                        compare(reference, actual, case['ship'] + '/' + str(step['requested']))
                    self.dispatch('delete_fit', {'fit_id': key, 'resolve_references': True})
        def test_invalid_cross_hull_stale_and_atomic_save(self):
            key = self.create('Confessor')
            before = saved(self.bridge)
            valid = expected['cases'][0]['choices'][1]['id']
            for value in (True, -1, 99999999, expected['cases'][1]['choices'][0]['id']):
                response = self.dispatch('change_mode', {'fit_id': key, 'item_id': value}, False)
                self.assertIn(response['error']['code'], ('INVALID_REQUEST', 'INVALID_EDIT'))
                compare(before, saved(self.bridge))
            self.dispatch('change_mode', {'fit_id': key, 'item_id': valid}, False, revision=0)
            compare(before, saved(self.bridge))
            self.bridge._reset_storage()
            self.bridge = BridgeSession.open(engine, args.output / 'failed.db', identity,
                {**deepcopy(empty), 'name': 'B06.1 Confessor', 'ship': 'Confessor'})
            key = self.bridge.sample_id
            before = saved(self.bridge)
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic save failure')):
                self.dispatch('change_mode', {'fit_id': key, 'item_id': valid}, False)
            compare(before, saved(self.bridge))
        def test_copy_reopen(self):
            self.bridge._reset_storage()
            self.bridge = BridgeSession.open(engine, args.output / 'durable.db', identity,
                {**deepcopy(empty), 'name': 'B06.1 Jackdaw', 'ship': 'Jackdaw'})
            key = self.bridge.sample_id
            selected = expected['cases'][1]['choices'][2]['id']
            self.dispatch('change_mode', {'fit_id': key, 'item_id': selected})
            copy = self.dispatch('duplicate_fit', {'fit_id': key, 'name': 'Jackdaw copy'})['fits'][-1]['id']
            self.assertEqual(selected, self.bridge.mode_options(copy)['current'])
            self.assertEqual(selected, self.bridge._records[copy]['spec']['mode'])
            self.assertEqual(self.stats(key), self.stats(copy))
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            # Copy the graph to the restore path only after all mutations commit.
            import shutil
            shutil.copyfile(args.output / 'durable.db', args.output / 'fits.db')
            with (args.output / 'restart.log').open('w') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--source', str(args.source), '--restore'],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 2}, json.loads((args.output / 'restored.json').read_text()))

        def test_legacy_default_graph_reopens_without_invented_field(self):
            self.bridge._reset_storage()
            spec = {**deepcopy(empty), 'name': 'B06.1 legacy default', 'ship': 'Confessor'}
            self.bridge = BridgeSession.open(engine, args.output / 'legacy.db', identity, spec)
            key = self.bridge.sample_id
            self.assertNotIn('mode', self.bridge._records[key]['spec'])
            before = saved(self.bridge)
            self.bridge._reset_storage()
            self.bridge = BridgeSession.open(engine, args.output / 'legacy.db', identity, spec)
            compare(before, saved(self.bridge))
            self.assertEqual(expected['cases'][0]['steps'][0]['result']['mode_id'],
                             self.bridge.mode_options(key)['current'])

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ModeTests))
    if result.testsRun != 4 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Mode regressions failed or attempted forbidden access')
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 4, 'cases': len(expected['cases']),
        'states': sum(len(case['steps']) for case in expected['cases']), 'fresh_process_restore': True,
        'desktop_import_attempts': guard.attempts, 'network_attempts': network}, indent=2) + '\n')


if __name__ == '__main__': main()
