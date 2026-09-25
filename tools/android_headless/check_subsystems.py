"""Compare B06.2 subsystem edits with the pinned desktop and durable graph."""
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
    fixture = ROOT / 'tools/android_reference/fixtures/subsystems.json'
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
        evidence.update({'task': 'B06.2', 'host_only': True, 'database_sha256': before,
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
    from eos.const import FittingSlot
    engine = HeadlessEngine(args.database)
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit'); empty['modules'], empty['drones'] = [], []
    operations = expected['cases'][0]['steps']
    by_name = {row['name']: row for rows in expected['choices'].values() for row in rows}

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'records': deepcopy(bridge._records),
                'organization': bridge.organization(), 'recent': bridge.recent_items()}

    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity,
            {**deepcopy(empty), 'name': 'B06.2 Tengu', 'ship': 'Tengu'})
        actual, prior = saved(bridge), json.loads((args.output / 'before-restart.json').read_text())
        compare(prior, actual)
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(actual['fits'])}))
        return

    class SubsystemTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1,
                'session_id': self.bridge.session_id, 'request_id': 'b062', 'operation': operation,
                'arguments': arguments, 'expected_revisions': {key: self.bridge._revisions[key]
                    if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response
        def create(self, ship):
            return self.dispatch('create_fit', {'spec': {**deepcopy(empty), 'name': 'B06.2 ' + ship,
                'ship': ship}})['fits'][0]['id']
        def action(self, key, operation, ok=True):
            name = operation[0]
            if name == 'add' and operation[1] == 'Heavy Missile Launcher II':
                item = by_name.get(operation[1])
                if item is None:
                    item = {'id': 2410}
                self.dispatch('add_module', {'fit_id': key, 'item_id': item['id']})
                details = self.bridge.fitting_details(key)
                position = next(row['index'] for row in details['modules'] if row['name'] == operation[1])
                from eos.db import getItem
                self.dispatch('set_module_charge', {'fit_id': key, 'position': position,
                    'charge_id': getItem(operation[2]).ID})
                return
            item = by_name[operation[1]]
            self.dispatch('set_subsystem', {'fit_id': key, 'kind': item['type'],
                'item_id': item['id'] if name != 'remove' else None}, ok)
        def observe(self, key):
            fit = self.bridge._fits[key]
            details = self.bridge.fitting_details(key)
            modules = [{field: row[field] for field in ('index', 'id', 'name', 'slot', 'state', 'charge', 'legal')}
                       for row in details['modules']]
            slots = [{'slot': 'SUBSYSTEM', 'used': fit.getSlotsUsed(FittingSlot.SUBSYSTEM.value),
                      'total': fit.getNumSlots(FittingSlot.SUBSYSTEM.value)}]
            slots += [{field: row[field] for field in ('slot', 'used', 'total')}
                      for slot in ('HIGH', 'MED', 'LOW', 'RIG', 'SERVICE')
                      for row in details['slots'] if row['slot'] == slot]
            resources = details['resources']
            return {'modules': modules, 'slots': slots, 'hardpoints': details['hardpoints'],
                    'resources': {'cpu_used': resources['cpu']['used'], 'cpu_total': resources['cpu']['total'],
                                  'powergrid_used': resources['powergrid']['used'],
                                  'powergrid_total': resources['powergrid']['total']},
                    'stats': self.bridge._snapshots[key]['stats']}
        def compare_state(self, original, actual, rejected=False):
            if not rejected and len(original['modules']) != len(actual['modules']):
                raise AssertionError(('module positions', [(r['slot'], r['id']) for r in original['modules']],
                    [(r['slot'], r['id']) for r in actual['modules']]))
            for key in ('modules', 'slots', 'hardpoints', 'resources'):
                if key == 'resources':
                    for name, a in original[key].items():
                        b = actual[key][name]
                        self.assertTrue(isclose(a, b, rel_tol=1e-10, abs_tol=1e-9), (name, a, b))
                elif key == 'modules' and rejected:
                    # The original failed add can reshuffle vacant dummies;
                    # bridge rejection keeps the prior durable graph atomic.
                    compare([r for r in original[key] if r['id'] is not None],
                            [r for r in actual[key] if r['id'] is not None], key)
                else: compare(original[key], actual[key], key)
            self.assertEqual(original['stats'].keys(), actual['stats'].keys())
            for key, left in original['stats'].items():
                right = actual['stats'][key]
                self.assertEqual(left['unit'], right['unit'], key)
                a, b = left['value'], right['value']
                if b is None and key in ('gun_optimal', 'gun_falloff'):
                    self.assertIn(a, (0, 1), key)
                elif type(a) in (int, float) and type(b) in (int, float):
                    self.assertTrue(isclose(a, b, rel_tol=1e-10, abs_tol=1e-9), (key, a, b))
                else: self.assertEqual(a, b, key)
        def test_all_original_states(self):
            key = self.create('Tengu')
            original, initial = operations[0]['result'], self.observe(key)
            for field in ('slots', 'hardpoints'):
                compare(original[field], initial[field], field)
            for index, step in enumerate(operations[1:], 1):
                before = saved(self.bridge) if not step['accepted'] else None
                self.action(key, step['operation'], step['accepted'])
                if before is not None: compare(before, saved(self.bridge))
                try:
                    self.compare_state(step['result'], self.observe(key), rejected=not step['accepted'])
                except (AssertionError, ValueError) as error:
                    raise AssertionError(f"Desktop step {index}: {step['operation']}: {error}") from error
        def test_all_hull_choices_and_atomic_invalids(self):
            for ship, choices in expected['choices'].items():
                key = self.create(ship)
                groups = self.bridge.subsystem_options(key)['groups']
                rows = [{'id': row['id'], 'name': row['name'], 'type': group['kind']}
                        for group in groups for row in group['choices']]
                compare(choices, rows)
            tengu = next(key for key, fit in self.bridge._fits.items() if fit.ship.item.name == 'Tengu')
            before = saved(self.bridge)
            for kind, item in ((127, 45589), (127, expected['choices']['Legion'][0]['id']),
                               (999, 45601), (127, -1)):
                self.dispatch('set_subsystem', {'fit_id': tengu, 'kind': kind, 'item_id': item}, False)
                compare(before, saved(self.bridge))
            self.dispatch('set_subsystem', {'fit_id': tengu, 'kind': 127, 'item_id': 45601}, False, revision=0)
            compare(before, saved(self.bridge))
        def test_illegal_launcher_copy_and_fresh_restart(self):
            self.bridge._reset_storage()
            (args.output / 'durable.db').unlink(missing_ok=True)
            self.bridge = BridgeSession.open(engine, args.output / 'durable.db', identity,
                {**deepcopy(empty), 'name': 'B06.2 Tengu', 'ship': 'Tengu'})
            key = self.bridge.sample_id
            for step in operations[1:9]:
                self.action(key, step['operation'], step['accepted'])
            self.compare_state(operations[8]['result'], self.observe(key))
            copy = self.dispatch('duplicate_fit', {'fit_id': key, 'name': 'B06.2 invalid copy'})['fits'][-1]['id']
            self.compare_state(operations[8]['result'], self.observe(copy))
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            shutil.copyfile(args.output / 'durable.db', args.output / 'fits.db')
            with (args.output / 'restart.log').open('w', encoding='utf-8') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--source', str(args.source), '--restore'],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 2}, json.loads((args.output / 'restored.json').read_text()))
            before = saved(self.bridge)
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic save failure')):
                self.dispatch('set_subsystem', {'fit_id': key, 'kind': 127, 'item_id': 45601}, False)
            compare(before, saved(self.bridge))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SubsystemTests))
    if result.testsRun != 3 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Subsystem regressions failed or attempted forbidden access')
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 3, 'cases': 1,
        'states': len(operations), 'choices': sum(map(len, expected['choices'].values())),
        'fresh_process_restore': True, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network}, indent=2) + '\n')


if __name__ == '__main__': main()
