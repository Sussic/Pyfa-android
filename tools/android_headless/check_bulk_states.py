"""Compare B05.2 bulk state transitions with original desktop command results."""
import argparse
from copy import deepcopy
import gc
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import threading
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
    args.database, args.output = args.database.resolve(strict=True), args.output.resolve()
    args.source = args.source.resolve(strict=True)
    validate_source(args.source)
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError('Use a new output outside checkout and input database')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/bulk-states.json'
    expected = json.loads(fixture.read_text())
    identity = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    if not args.worker and not args.restore:
        compare(identity, logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                '--output', str(args.output), '--source', str(args.source), '--worker'],
                check=True, stdout=log, stderr=subprocess.STDOUT, timeout=360)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update({'task': 'B05.2', 'host_only': True, 'database_sha256': before,
            'database_logical_sha256': identity, 'game_database_unchanged': True, 'reference_sha256': digest_file(fixture)})
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
    engine = HeadlessEngine(args.database)

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'recent': bridge.recent_items(),
                'options': [bridge.bulk_state_options(key) for key in bridge._fits],
                'organization': bridge.organization(), 'records': deepcopy(bridge._records)}
    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, None)
        compare(json.loads((args.output / 'before-restart.json').read_text()), saved(bridge))
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(bridge._fits)}))
        return
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit'); empty['modules'], empty['drones'] = [], []
    observations = []
    from eos.const import FittingModuleState, FittingSlot

    class BulkStateTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1, 'session_id': self.bridge.session_id,
                'request_id': 'bulk-states', 'operation': operation, 'arguments': arguments,
                'expected_revisions': {key: self.bridge._revisions[key] if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response
        def create(self, case=None):
            case = case or {'name': 'Empty state probe', 'ship': 'Rifter'}
            key = self.dispatch('create_fit', {'spec': {**deepcopy(empty), 'ship': case['ship'], 'name': case['name'],
                'modules': case.get('modules', [])}})['fits'][0]['id']
            self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
            return key
        def change(self, key, step=1, ok=True):
            return self.dispatch('set_bulk_states', {'fit_id': key, **expected['cases'][0]['steps'][step]['input']}, ok)
        def test_original_commands_states_and_recipients(self):
            for case in expected['cases']:
                with self.subTest(case=case['name']):
                    key = self.create(case); recipients = []
                    for row in case.get('recipients', []):
                        target = self.create(row)
                        self.dispatch('add_command' if case.get('link') == 'command' else 'add_projection',
                            {'source_id': key, 'target_id': target, 'active': True,
                             **({} if case.get('link') == 'command' else {'range_m': 0.0, 'amount': 1})})
                        recipients.append(target)
                    steps = []
                    for step in case['steps']:
                        operation = step['input']
                        if operation:
                            before = saved(self.bridge)
                            response = self.dispatch('set_bulk_states', {'fit_id': key, **operation})
                            self.assertEqual({key, *recipients}, {row['id'] for row in response['fits']})
                            if not step['changed']:
                                self.assertEqual(before['organization'], self.bridge.organization())
                        gc.collect()
                        fit = self.bridge._fits[key]
                        options = self.bridge.bulk_state_options(key)
                        actual = {'options': {k: v for k, v in options.items() if k not in ('version', 'fit_id', 'revision')},
                            'modules': [{'index': i, 'id': m.itemID, 'slot': FittingSlot(m.slot).name,
                                         'state': FittingModuleState(m.state).name if not m.isEmpty else None,
                                         'charge_id': m.chargeID} for i, m in enumerate(fit.modules)],
                            'stats': self.bridge._snapshots[key]['stats'],
                            'recipients': [{'name': self.bridge._snapshots[target]['name'], 'stats': self.bridge._snapshots[target]['stats']}
                                           for target in recipients], 'recent': self.bridge.recent_items()['item_ids']}
                        compare(step['result'], actual, case['name'] + '.' + str(operation))
                        steps.append({'input': operation, 'changed': step['changed'], 'result': actual})
                    observations.append({'name': case['name'], 'steps': steps})
                    for fit_id in reversed(list(self.bridge._fits)):
                        self.dispatch('delete_fit', {'fit_id': fit_id, 'resolve_references': True})
        def test_atomic_invalid_and_stale_selection(self):
            key = self.create(expected['cases'][0]); before = saved(self.bridge)
            args = {'fit_id': key, **expected['cases'][0]['steps'][1]['input']}
            for field, values in {
                    'main_position': [True, 0.0, '0', None, -1, 999, 4],
                    'module_indices': [[], [0, 0], [True], [0.0], ['0'], [-1], [999], [0, 4], [1, 2], None],
                    'scope': ['ALL', '', True, None],
                    'click': ['middle', '', True, None]}.items():
                for value in values:
                    self.dispatch('set_bulk_states', {**args, field: value}, False)
                    self.assertEqual(before, saved(self.bridge))
            self.dispatch('set_bulk_states', args, False, revision=0)
            self.assertEqual(before, saved(self.bridge))
        def test_no_op_similar_outside_selection_and_unchanged_history(self):
            key = self.create(expected['cases'][2])
            no_op = expected['cases'][2]['steps'][1]['input']
            before = saved(self.bridge)
            self.dispatch('set_bulk_states', {'fit_id': key, **no_op})
            for row in before['fits']: row['revision'] += 1
            for row in before['options']: row['revision'] += 1
            self.assertEqual(before, saved(self.bridge))
            key2 = self.create(expected['cases'][1])
            before = saved(self.bridge)
            similar = expected['cases'][1]['steps'][2]['input']
            self.dispatch('set_bulk_states', {'fit_id': key2, **similar})
            self.assertEqual(before['recent'], self.bridge.recent_items())
            self.assertEqual(before['records'][key], self.bridge._records[key])
        def test_read_only_empty_and_worker_ownership(self):
            key = self.create(); before = saved(self.bridge)
            self.assertTrue(all(row['item_id'] is None and not row['similar_candidates']
                                for row in self.bridge.bulk_state_options(key)['modules']))
            self.assertEqual(before, saved(self.bridge))
            failures = []
            def foreign():
                try: self.bridge.bulk_state_options(key)
                except RuntimeError: failures.append(True)
            thread = threading.Thread(target=foreign); thread.start(); thread.join()
            self.assertEqual([True], failures)
        def test_failed_write_independent_copy_and_fresh_restart(self):
            initial = {**deepcopy(empty), 'modules': deepcopy(expected['cases'][0]['modules'])}
            self.bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, initial)
            key = self.bridge.sample_id
            self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
            self.change(key)
            original = deepcopy(self.bridge._records[key])
            copy = next(row['id'] for row in self.dispatch('duplicate_fit', {'fit_id': key, 'name': 'Independent state copy'})['fits'] if row['id'] != key)
            self.change(copy, 2)
            self.assertEqual(original, self.bridge._records[key])
            before = saved(self.bridge), (args.output / 'fits.db').read_bytes()
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic state save failure')):
                self.change(key, 3, False)
            self.assertEqual(before, (saved(self.bridge), (args.output / 'fits.db').read_bytes()))
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            with (args.output / 'restart.log').open('w') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--source', str(args.source), '--restore'],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 2}, json.loads((args.output / 'restored.json').read_text()))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BulkStateTests))
    if result.testsRun != 5 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Bulk state regressions failed or attempted forbidden access')
    (args.output / 'observations.json').write_text(json.dumps({'cases': observations}, indent=2))
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 5, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network, 'fresh_process_restore': True, 'cases': len(observations),
        'states': sum(len(case['steps']) for case in observations)}, indent=2) + '\n')


if __name__ == '__main__': main()
