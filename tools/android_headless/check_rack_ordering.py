"""Guarded original rack/heat parity, atomic edits, copy and real restart."""
import argparse
import ast
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
        raise ValueError('Use a new output outside checkout and input database')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/rack-ordering.json'
    expected = json.loads(fixture.read_text())
    identity = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    if not args.worker and not args.restore:
        compare(identity, logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                '--output', str(args.output), '--worker'], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=360)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update({'task': 'B04.2.3.3', 'host_only': True, 'database_sha256': before,
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
                'racks': [bridge.rack_options(key) for key in bridge._fits],
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

    class OrderingTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1, 'session_id': self.bridge.session_id,
                'request_id': 'rack-ordering', 'operation': operation, 'arguments': arguments,
                'expected_revisions': {key: self.bridge._revisions[key] if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response
        def create(self, case=None):
            case = case or {'name': 'Empty ordering probe', 'ship': 'Rifter'}
            key = self.dispatch('create_fit', {'spec': {**deepcopy(empty), 'ship': case['ship'], 'name': case['name'],
                'modules': case.get('modules', [])}})['fits'][0]['id']
            self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
            return key
        def swap(self, key, first, second, ok=True):
            return self.dispatch('swap_modules', {'fit_id': key, 'from_position': first, 'to_position': second}, ok)
        def test_original_command_heat_and_every_recipient(self):
            for case in expected['cases']:
                with self.subTest(case=case['name']):
                    key = self.create(case)
                    recipients = []
                    for row in case.get('recipients', []):
                        target = self.create(row)
                        self.dispatch('add_command' if case.get('link') == 'command' else 'add_projection',
                            {'source_id': key, 'target_id': target, 'active': True,
                             **({} if case.get('link') == 'command' else {'range_m': 0.0, 'amount': 1})})
                        recipients.append(target)
                    steps = []
                    for step in case['steps']:
                        operation = step['input']
                        if operation: self.dispatch('swap_modules', {'fit_id': key, **operation})
                        gc.collect()
                        actual = {'rack': {'modules': self.bridge.rack_options(key)['modules']},
                            'stats': self.bridge._snapshots[key]['stats'],
                            'recipients': [{'name': self.bridge._snapshots[target]['name'], 'stats': self.bridge._snapshots[target]['stats']}
                                           for target in recipients], 'recent': self.bridge.recent_items()['item_ids']}
                        compare(step['result'], actual, case['name'] + '.' + str(operation))
                        steps.append({'input': operation, 'changed': step['changed'], 'result': actual})
                    observations.append({'name': case['name'], 'steps': steps})
                    for fit_id in reversed(list(self.bridge._fits)):
                        self.dispatch('delete_fit', {'fit_id': fit_id, 'resolve_references': True})
        def test_atomic_empty_source_cross_rack_and_strict_position_rejection(self):
            key = self.create(expected['cases'][0]); before = saved(self.bridge)
            for first, second in [(12,0),(3,4),(0,3),(True,1),(0,True),(0.0,1),(0,1.0),('0',1),
                                  (None,1),(-1,0),(0,-1),(999,0),(0,999)]:
                self.swap(key, first, second, False)
                self.assertEqual(before, saved(self.bridge))
            self.dispatch('swap_modules', {'fit_id': key, 'from_position': 0, 'to_position': 1}, False, revision=0)
            self.assertEqual(before, saved(self.bridge))
        def test_same_position_acknowledgment_preserves_inputs_and_modified_order(self):
            key = self.create(expected['cases'][0])
            self.dispatch('add_module', {'fit_id': key, 'item_id': engine._item('Damage Control II').ID})
            before = saved(self.bridge)
            self.swap(key, 0, 0)
            for row in before['fits']: row['revision'] += 1
            for row in before['racks']: row['revision'] += 1
            self.assertEqual(before, saved(self.bridge))
        def test_read_only_empty_view_worker_ownership_and_unavailable_heat(self):
            key = self.create(); before = saved(self.bridge)
            self.assertTrue(all(row['id'] is None and row['heat'] is None for row in self.bridge.rack_options(key)['modules']))
            self.assertEqual(before, saved(self.bridge))
            failures = []
            def foreign():
                try: self.bridge.rack_options(key)
                except RuntimeError: failures.append(True)
            thread = threading.Thread(target=foreign); thread.start(); thread.join()
            self.assertEqual([True], failures)
            heated = self.create(expected['cases'][0]); before = saved(self.bridge)
            with patch('android_bridge.thermodynamics.Thermodynamics.calcBurnCycles', side_effect=ZeroDivisionError):
                rows = self.bridge.rack_options(heated)['modules']
                self.assertTrue(all(row['heat']['seconds']['value'] is None and row['heat']['cycles']['value'] is None
                                    for row in rows if row['state'] == 'OVERHEATED'))
            self.assertEqual(before, saved(self.bridge))
        def test_original_heat_body_and_material_positional_changes(self):
            def body(path):
                return ast.dump(next(n for n in ast.parse(path.read_text(encoding='utf-8')).body
                                     if isinstance(n, ast.ClassDef) and n.name == 'Thermodynamics'))
            self.assertEqual(body(ROOT/'gui/builtinViewColumns/heat.py'), body(ROOT/'android_bridge/thermodynamics.py'))
            for case in expected['cases'][:3]:
                key = self.create(case)
                initial = self.bridge.rack_options(key)
                self.dispatch('swap_modules', {'fit_id': key, **case['steps'][1]['input']})
                later = self.bridge.rack_options(key)
                def estimates(options):
                    return sorted(row['heat']['seconds']['value'] for row in options['modules'] if row['heat'])
                self.assertNotEqual(estimates(initial), estimates(later))
        def test_failed_writes_independent_copies_and_real_process_restore(self):
            initial = {**deepcopy(empty), 'modules': deepcopy(expected['cases'][0]['modules'])}
            self.bridge = BridgeSession.open(engine, args.output/'fits.db', identity, initial)
            key = self.bridge.sample_id
            self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
            self.swap(key,0,1); self.swap(key,1,12)
            source = deepcopy(self.bridge._records[key])
            copy = next(row['id'] for row in self.dispatch('duplicate_fit', {'fit_id': key, 'name': 'Independent ordering copy'})['fits'] if row['id'] != key)
            self.swap(copy,12,0)
            self.assertEqual(source,self.bridge._records[key])
            before = saved(self.bridge), (args.output/'fits.db').read_bytes()
            with patch.object(self.bridge._store,'write',side_effect=OSError('synthetic ordering save failure')):
                self.swap(key,12,0,False)
            self.assertEqual(before,(saved(self.bridge),(args.output/'fits.db').read_bytes()))
            (args.output/'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            with (args.output/'restart.log').open('w') as log:
                subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),
                    '--output',str(args.output),'--restore'],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=90)
            self.assertEqual({'matched':True,'fits':2},json.loads((args.output/'restored.json').read_text()))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OrderingTests))
    if result.testsRun != 6 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Ordering regressions failed or attempted forbidden access')
    (args.output/'observations.json').write_text(json.dumps({'cases':observations},indent=2))
    (args.output/'evidence.json').write_text(json.dumps({'tests_passed':6,'desktop_import_attempts':guard.attempts,
        'network_attempts':network,'fresh_process_restore':True,'cases':len(observations),
        'states':sum(len(case['steps']) for case in observations)},indent=2)+'\n')


if __name__ == '__main__':
    main()
