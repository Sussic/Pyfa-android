"""Compare B06.3 structure services with pinned desktop and durable EOS state."""
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
    fixture = ROOT / 'tools/android_reference/fixtures/structures.json'
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
        evidence.update({'task': 'B06.3', 'host_only': True, 'database_sha256': before,
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
    by_name = {item['name']: item['id'] for row in expected['choices'].values()
               for item in row['items']}

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'records': deepcopy(bridge._records),
                'organization': bridge.organization(), 'recent': bridge.recent_items()}

    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity,
            {**deepcopy(empty), 'name': 'B06.3 Astrahus', 'ship': 'Astrahus'})
        actual, prior = saved(bridge), json.loads((args.output / 'before-restart.json').read_text())
        compare(prior, actual)
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(actual['fits'])}))
        return

    class StructureTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()

        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1,
                'session_id': self.bridge.session_id, 'request_id': 'b063', 'operation': operation,
                'arguments': arguments, 'expected_revisions': {key: self.bridge._revisions[key]
                    if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response

        def create(self, ship):
            return self.dispatch('create_fit', {'spec': {**deepcopy(empty),
                'name': 'B06.3 ' + ship, 'ship': ship}})['fits'][0]['id']

        def action(self, key, operation, ok=True):
            name, label, *rest = operation
            if name == 'add':
                item_id = by_name.get(label)
                if item_id is None:
                    from eos.db import getItem
                    item_id = getItem(label).ID
                return self.dispatch('add_module', {'fit_id': key, 'item_id': item_id}, ok)
            position = next(row['index'] for row in self.bridge.fitting_details(key)['modules']
                            if row['name'] == label)
            if name == 'replace':
                return self.dispatch('replace_module', {'fit_id': key, 'position': position,
                    'item_id': by_name[rest[0]]}, ok)
            if name == 'remove':
                return self.dispatch('remove_module', {'fit_id': key, 'position': position}, ok)
            raise ValueError(name)

        def observe(self, key):
            details = self.bridge.fitting_details(key)
            modules = [{field: row[field] for field in ('index', 'id', 'name', 'slot', 'state', 'charge', 'legal')}
                       for row in details['modules']]
            slots = [{field: row[field] for field in ('slot', 'used', 'total')}
                     for row in details['slots']]
            resources = details['resources']
            return {'modules': modules, 'slots': slots,
                    'resources': {'cpu_used': resources['cpu']['used'],
                                  'cpu_total': resources['cpu']['total'],
                                  'powergrid_used': resources['powergrid']['used'],
                                  'powergrid_total': resources['powergrid']['total']},
                    'stats': self.bridge._snapshots[key]['stats']}

        def compare_state(self, original, actual, rejected=False, initial=False):
            left, right = original['modules'], actual['modules']
            if rejected or initial:
                left = [row for row in left if row['id'] is not None]
                right = [row for row in right if row['id'] is not None]
            compare(left, right, 'modules')
            compare(original['slots'], actual['slots'], 'slots')
            for name, left in original['resources'].items():
                right = actual['resources'][name]
                self.assertTrue(isclose(left, right, rel_tol=1e-10, abs_tol=1e-9),
                                (name, left, right))
            self.assertEqual(original['stats'].keys(), actual['stats'].keys())
            for name, left in original['stats'].items():
                right = actual['stats'][name]
                self.assertEqual(left['unit'], right['unit'], name)
                a, b = left['value'], right['value']
                if b is None and name in ('gun_optimal', 'gun_falloff'):
                    self.assertIn(a, (0, 1), name)
                elif type(a) in (int, float) and type(b) in (int, float):
                    self.assertTrue(isclose(a, b, rel_tol=1e-10, abs_tol=1e-9), (name, a, b))
                else: self.assertEqual(a, b, name)

        def test_all_original_structure_states(self):
            for case in expected['cases']:
                key = self.create(case['ship'])
                for index, step in enumerate(case['steps']):
                    before = saved(self.bridge) if index and not step['accepted'] else None
                    if index: self.action(key, step['operation'], step['accepted'])
                    if before is not None:
                        after = saved(self.bridge)
                        compare({name: value for name, value in before.items() if name != 'recent'},
                                {name: value for name, value in after.items() if name != 'recent'})
                    try:
                        self.compare_state(step['result'], self.observe(key),
                            rejected=not step['accepted'], initial=index == 0)
                    except (AssertionError, ValueError) as error:
                        raise AssertionError(f"{case['ship']} step {index}: {step['operation']}: {error}") from error

        def test_all_hull_choices_and_rejections(self):
            keys = {}
            for ship, choices in expected['choices'].items():
                key = self.create(ship)
                keys[ship] = key
                current = self.bridge.structure_service_options(key)
                compare(choices['capacity'], current['capacity'])
                compare(choices['items'], current['choices'])
                compare(ship != 'Vexor', current['is_structure'])
            ansiblex = keys['Ansiblex Jump Bridge']
            before = saved(self.bridge)
            self.dispatch('add_module', {'fit_id': ansiblex, 'item_id': by_name['Standup Manufacturing Plant I']}, False)
            self.dispatch('add_module', {'fit_id': ansiblex, 'item_id': -1}, False)
            self.dispatch('add_module', {'fit_id': ansiblex, 'item_id': by_name['Standup Conduit Generator I']}, False,
                          revision=0)
            after = saved(self.bridge)
            # Desktop records an attempted valid market add as recent even when
            # its hull restriction rejects the fitting. The fit graph stays atomic.
            compare({key: value for key, value in before.items() if key != 'recent'},
                    {key: value for key, value in after.items() if key != 'recent'})
            compare([by_name['Standup Manufacturing Plant I']], after['recent']['item_ids'])

        def test_bonus_copy_restart_and_failed_save(self):
            self.bridge._reset_storage()
            (args.output / 'durable.db').unlink(missing_ok=True)
            self.bridge = BridgeSession.open(engine, args.output / 'durable.db', identity,
                {**deepcopy(empty), 'name': 'B06.3 Astrahus', 'ship': 'Astrahus'})
            key = self.bridge.sample_id
            case = expected['cases'][0]
            self.action(key, case['steps'][1]['operation'])
            self.compare_state(case['steps'][1]['result'], self.observe(key))
            copy = self.dispatch('duplicate_fit', {'fit_id': key, 'name': 'B06.3 structure copy'})['fits'][-1]['id']
            self.compare_state(case['steps'][1]['result'], self.observe(copy))
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            shutil.copyfile(args.output / 'durable.db', args.output / 'fits.db')
            with (args.output / 'restart.log').open('w', encoding='utf-8') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                    '--database', str(args.database), '--output', str(args.output),
                    '--source', str(args.source), '--restore'],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 2}, json.loads((args.output / 'restored.json').read_text()))
            before = saved(self.bridge)
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic save failure')):
                self.dispatch('remove_module', {'fit_id': key, 'position': next(row['index']
                    for row in self.bridge.fitting_details(key)['modules']
                    if row['name'] == 'Standup Manufacturing Plant I')}, False)
            compare(before, saved(self.bridge))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StructureTests))
    if result.testsRun != 3 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Structure regressions failed or attempted forbidden access')
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 3,
        'cases': len(expected['cases']),
        'states': sum(len(case['steps']) for case in expected['cases']),
        'hulls': len(expected['choices']),
        'service_choices': sum(len(row['items']) for row in expected['choices'].values()),
        'fresh_process_restore': True, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network}, indent=2) + '\n')


if __name__ == '__main__': main()
