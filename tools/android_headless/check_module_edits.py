"""Guarded B04.2.2 parity, atomic edit/history and real process restore checks."""
import argparse
from copy import deepcopy
import gc
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
        raise ValueError('Use a fresh output outside the checkout and input database')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/module-edits.json'
    expected = json.loads(fixture.read_text(encoding='utf-8'))
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
        evidence.update({'task': 'B04.2.2', 'host_only': True, 'database_sha256': before,
            'database_logical_sha256': identity, 'game_database_unchanged': True,
            'reference_sha256': digest_file(fixture)})
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
    from android_bridge import fitting
    engine = HeadlessEngine(args.database)

    def saved_observation(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'recent': bridge.recent_items(),
                'details': [bridge.fitting_details(key) for key in bridge._fits], 'organization': bridge.organization()}

    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, None)
        compare(json.loads((args.output / 'before-restart.json').read_text()), saved_observation(bridge))
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(bridge._fits)}))
        return
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit')
    empty['modules'], empty['drones'] = [], []
    observations = []
    states = []

    class ModuleEditingTests(unittest.TestCase):
        def setUp(self):
            self.bridge = BridgeSession(engine)

        def tearDown(self):
            self.bridge._reset_storage()

        def dispatch(self, operation, arguments, ok=True):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1, 'session_id': self.bridge.session_id,
                'request_id': 'module-edits', 'operation': operation, 'arguments': arguments,
                'expected_revisions': {key: self.bridge._revisions[key] for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response

        def create(self, hull='Rifter', skills=5, modules=None, name='Synthetic module fit'):
            spec = {**deepcopy(empty), 'ship': hull, 'skill_level': skills, 'modules': modules or [], 'name': name}
            return self.dispatch('create_fit', {'spec': spec})['fits'][0]['id']

        def use(self, key, name, ok=True, position=None):
            identity = engine._item(name).ID
            return self.dispatch('add_module' if position is None else 'replace_module',
                {'fit_id': key, 'item_id': identity, **({'position': position} if position is not None else {})}, ok)

        def report(self, key):
            detail = self.bridge.fitting_details(key)
            return {**{k: v for k, v in detail.items() if k not in ('version', 'fit_id', 'revision')},
                    'stats': self.bridge._snapshots[key]['stats'], 'recent': self.bridge.recent_items()['item_ids']}

        def test_complete_original_command_matrix_and_all_raw_values(self):
            for case in expected['cases']:
                with self.subTest(case=case['name']):
                    key = self.create(case['ship'], case['skill_level'], case['initial_modules'], case['name'])
                    # Explicit editor initialization makes original desktop vacant
                    # positions comparable; normal empty-hull creation stays empty.
                    self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
                    recipients = []
                    for recipient in case['recipients']:
                        target = self.create(recipient['ship'], name=recipient['name'])
                        self.dispatch('set_fit_restrictions', {'fit_id': target, 'ignore': False})
                        self.dispatch('add_projection', {'source_id': key, 'target_id': target,
                            'range_m': 0.0, 'active': True, 'amount': 1})
                        recipients.append(target)
                    rows = []
                    for step in case['steps']:
                        operation = step['input']
                        if operation:
                            before = self.bridge.bootstrap(), self.bridge.organization()
                            name, *args = operation
                            if name in ('add', 'replace'):
                                self.use(key, args[-1], step['accepted'], args[0] if name == 'replace' else None)
                            elif name == 'remove':
                                self.dispatch('remove_module', {'fit_id': key, 'position': args[0]}, step['accepted'])
                            else:
                                self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': args[0]}, step['accepted'])
                            if not step['accepted']:
                                self.assertEqual(before, (self.bridge.bootstrap(), self.bridge.organization()))
                        gc.collect()
                        result = self.report(key)
                        result['recipients'] = [{'name': self.bridge._snapshots[target]['name'],
                            'stats': self.bridge._snapshots[target]['stats']} for target in recipients]
                        compare(step['result'], result, case['name'] + '.' + str(operation))
                        rows.append({'input': operation, 'accepted': step['accepted'], 'result': result})
                    observations.append({**case, 'steps': rows})
                    for fit_id in reversed(list(self.bridge._fits)):
                        self.dispatch('delete_fit', {'fit_id': fit_id, 'resolve_references': True})

        def test_default_state_for_every_4242_supported_catalogue_module(self):
            from eos.const import FittingModuleState, FittingSlot
            self.assertEqual(4242, len(expected['default_states']))
            for row in expected['default_states']:
                module = fitting.new_module(engine, row['id'])
                limit = 'ONLINE' if fitting.ONLINE_EFFECTS.intersection(module.item.effects) else 'ACTIVE'
                actual = {'id': module.itemID, 'name': module.item.name, 'slot': FittingSlot(module.slot).name,
                          'state': FittingModuleState(module.state).name, 'limit': limit}
                compare(row, actual)
                states.append(actual)

        def test_twenty_recent_ids_duplicate_promotion_and_abyssal_exclusion(self):
            history = []
            for row in expected['recent_history']:
                history = fitting.promote(engine, history, [row['id']])
                self.assertEqual(row['result'], history)
            # Exclusion also removes a previously retained abyssal entry.
            self.assertEqual([], fitting.promote(engine, [expected['abyssal_id']], [expected['abyssal_id']]))

        def test_actual_attempts_are_recent_but_reads_and_stale_or_malformed_edits_are_not(self):
            key = self.create('Kestrel')
            before = self.bridge.bootstrap(), self.bridge.organization()
            self.use(key, '200mm AutoCannon II', ok=False)
            self.assertEqual(before, (self.bridge.bootstrap(), self.bridge.organization()))
            self.assertEqual([engine._item('200mm AutoCannon II').ID], self.bridge._recent)
            before = saved_observation(self.bridge)
            for _ in range(2):
                self.bridge.fitting_details(key)
                self.bridge.recent_items()
            self.assertEqual(before, saved_observation(self.bridge))
            for value in (True, 1.5, '1', -1, 2147483648):
                self.dispatch('add_module', {'fit_id': key, 'item_id': value}, ok=False)
            self.dispatch('replace_module', {'fit_id': key, 'position': 999, 'item_id': 2048}, ok=False)
            self.dispatch('remove_module', {'fit_id': key, 'position': 0}, ok=False)
            self.assertEqual(before, saved_observation(self.bridge))
            self.dispatch('delete_fit', {'fit_id': key, 'resolve_references': False})
            self.assertEqual(before['recent'], self.bridge.recent_items())

        def test_saved_holes_override_hardpoints_copy_and_real_process_restart(self):
            self.bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, {**deepcopy(empty), 'ship': 'Kestrel'})
            key = self.bridge.sample_id
            self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': True})
            self.use(key, '200mm AutoCannon II')
            self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
            self.assertFalse(next(row for row in self.report(key)['modules'] if row['name'])['legal'])
            second = self.create()
            self.use(second, '200mm AutoCannon II')
            self.use(second, '150mm Light AutoCannon II')
            self.dispatch('remove_module', {'fit_id': second, 'position': 7})
            before_copy = deepcopy(self.report(second))
            copies = self.dispatch('duplicate_fit', {'fit_id': second, 'name': 'Independent copy'})['fits']
            copy = next(row['id'] for row in copies if row['id'] not in (key, second))
            self.use(copy, '125mm Gatling AutoCannon II')
            self.assertEqual(before_copy['modules'], self.report(second)['modules'])
            self.dispatch('set_fit_restrictions', {'fit_id': second, 'ignore': True})
            self.use(second, 'Capital Armor Repairer I')
            before = saved_observation(self.bridge), (args.output / 'fits.db').read_bytes()
            for target, name in ((copy, 'Damage Control II'), (key, '200mm AutoCannon II')):
                with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic failed save')):
                    self.use(target, name, ok=False)
                self.assertEqual(before, (saved_observation(self.bridge), (args.output / 'fits.db').read_bytes()))
            (args.output / 'before-restart.json').write_text(json.dumps(saved_observation(self.bridge)))
            with (args.output / 'restart.log').open('w') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--restore'], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 3}, json.loads((args.output / 'restored.json').read_text()))

        def test_empty_slots_reject_charge_and_state_edits_without_changes(self):
            key = self.create()
            self.use(key, '200mm AutoCannon II')
            before = saved_observation(self.bridge)
            self.dispatch('set_charges', {'fit_id': key, 'module_indices': [0], 'charge': None}, ok=False)
            self.dispatch('set_module_states', {'fit_id': key, 'module_indices': [0], 'state': 'ONLINE'}, ok=False)
            self.assertEqual(before, saved_observation(self.bridge))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ModuleEditingTests))
    if result.testsRun != 6 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Module editing regressions failed or attempted forbidden access')
    (args.output / 'observations.json').write_text(json.dumps({'cases': observations, 'default_states': states}, indent=2))
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 6, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network, 'fresh_process_restore': True, 'cases': len(observations),
        'steps': sum(len(case['steps']) for case in observations), 'default_states': len(states)}, indent=2) + '\n')


if __name__ == '__main__':
    main()
