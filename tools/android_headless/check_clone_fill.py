"""Guard B05.3 clone/fill parity, atomic storage and fresh-process recovery."""
import argparse
from copy import deepcopy
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
    args.database, args.output, args.source = (
        args.database.resolve(strict=True), args.output.resolve(), args.source.resolve(strict=True))
    validate_source(args.source)
    if args.output.is_relative_to(ROOT):
        raise ValueError('Use a fresh output outside checkout')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/clone-fill.json'
    expected = json.loads(fixture.read_text())
    identity = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    if not args.worker and not args.restore:
        compare(identity, logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                '--database', str(args.database), '--output', str(args.output),
                '--source', str(args.source), '--worker'], check=True,
                stdout=log, stderr=subprocess.STDOUT, timeout=360)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update({'task': 'B05.3', 'host_only': True, 'database_sha256': before,
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
    from eos.const import FittingModuleState, FittingSlot
    engine = HeadlessEngine(args.database)
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit'); empty['modules'], empty['drones'] = [], []

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'],
                'recent': bridge.recent_items(), 'records': deepcopy(bridge._records),
                'organization': bridge.organization()}
    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, None)
        compare(json.loads((args.output / 'before-restart.json').read_text()), saved(bridge))
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(bridge._fits)}))
        return

    observations = []
    class CloneFillTests(unittest.TestCase):
        def setUp(self):
            self.bridge = BridgeSession(engine)
        def tearDown(self):
            self.bridge._reset_storage()
        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({
                'version': 1, 'session_id': self.bridge.session_id,
                'request_id': 'clone-fill', 'operation': operation, 'arguments': arguments,
                'expected_revisions': {key: self.bridge._revisions[key] if revision is None else revision
                                       for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response
        def create(self, case):
            spec = {**deepcopy(empty), 'name': case['name'], 'ship': case['ship'],
                    'modules': deepcopy(case.get('modules', [])),
                    'ignore_restrictions': case.get('ignore_restrictions', False)}
            return self.dispatch('create_fit', {'spec': spec})['fits'][0]['id']
        def report(self, key, recipients):
            fit = self.bridge._fits[key]
            return {'stats': self.bridge._snapshots[key]['stats'],
                'modules': [{'index': i, 'id': module.itemID, 'slot': FittingSlot(module.slot).name,
                             'state': None if module.isEmpty else FittingModuleState(module.state).name,
                             'charge_id': module.chargeID} for i, module in enumerate(fit.modules)
                            if not module.isEmpty],
                'free_slots': {slot.name: fit.getSlotsFree(slot.value) for slot in (
                    FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH,
                    FittingSlot.RIG, FittingSlot.SERVICE)},
                'recipients': [{'name': self.bridge._snapshots[target]['name'],
                                'stats': self.bridge._snapshots[target]['stats']} for target in recipients],
                'recent': self.bridge.recent_items()['item_ids']}
        def test_original_commands_every_state_and_recipient(self):
            def comparable(value):
                if isinstance(value, dict):
                    if value.keys() == {'value', 'unit'} and type(value['value']) in (int, float):
                        return {'value': float(value['value']), 'unit': value['unit']}
                    return {key: comparable(child) for key, child in value.items()}
                if isinstance(value, list):
                    return [comparable(child) for child in value]
                return value
            def compare_report(reference, actual, label):
                reference = comparable(reference)
                actual = comparable(actual)
                # The pinned desktop snapshot reads a dummy/non-weapon's
                # default range as 0 or 1; A01 exposes absence as null.
                for source, target in [(reference, actual), *zip(
                        reference['recipients'], actual['recipients'])]:
                    for field in ('gun_optimal', 'gun_falloff'):
                        left, right = source['stats'][field], target['stats'][field]
                        if left['value'] in (0.0, 1.0) and right['value'] is None:
                            left['value'] = None
                compare(reference, actual, label)
            for case in expected['cases']:
                with self.subTest(case=case['name']):
                    key = self.create(case)
                    recipients = []
                    for row in case.get('recipients', []):
                        target = self.create(row)
                        self.dispatch('add_projection', {'source_id': key, 'target_id': target,
                            'range_m': 0.0, 'active': True, 'amount': 1})
                        recipients.append(target)
                    steps = []
                    for step in case['steps']:
                        operation = step['operation']
                        if operation:
                            kind = operation[0]
                            if kind == 'fill_item':
                                wire = 'fill_modules_item'
                                parameters = {'fit_id': key, 'item_id': engine._item(operation[1]).ID}
                            elif kind == 'fill_clone':
                                wire = 'fill_modules_clone'
                                parameters = {'fit_id': key, 'position': operation[1]}
                            elif kind == 'clone_pair':
                                wire = 'clone_selected_modules'
                                parameters = {'fit_id': key, 'module_indices': operation[1:]}
                            elif kind == 'clone_at':
                                wire = 'clone_module_at'
                                parameters = {'fit_id': key, 'source_position': operation[1],
                                              'destination_position': operation[2]}
                            else:
                                raise ValueError(kind)
                            response = self.dispatch(wire, parameters, ok=step['changed'])
                            if step['changed']:
                                self.assertEqual({key, *recipients}, {row['id'] for row in response['fits']})
                        actual = self.report(key, recipients)
                        compare_report(step['result'], actual, case['name'] + '.' + str(operation))
                        steps.append({'operation': operation, 'changed': step['changed'], 'result': actual})
                    observations.append({'name': case['name'], 'steps': steps})
        def test_preview_read_only_and_worker_ownership(self):
            key = self.create(expected['cases'][0])
            before = saved(self.bridge)
            identity_item = engine._item('Dual 150mm Railgun II').ID
            options = self.bridge.fill_item_options(key, identity_item)
            self.assertEqual(('HIGH', 4), (options['slot'], options['vacancies']))
            vacancies = self.bridge.clone_vacancy_options(key)['vacancies']
            self.assertEqual([9, 10, 11, 12], [row['index'] for row in vacancies if row['slot'] == 'HIGH'])
            self.assertEqual(before, saved(self.bridge))
            self.assertEqual(0, len(self.bridge._fits[key].modules))
            failures = []
            def foreign():
                try: self.bridge.fill_item_options(key, identity_item)
                except RuntimeError: failures.append(True)
            thread = threading.Thread(target=foreign); thread.start(); thread.join()
            self.assertEqual([True], failures)
            strategic = self.create({'name': 'Virtual strategic vacancies', 'ship': 'Tengu'})
            expected_vacancies = self.bridge.clone_vacancy_options(strategic)['vacancies']
            strategic_fit = self.bridge._fits[strategic]
            self.assertEqual(0, len(strategic_fit.modules))
            strategic_fit.fill()
            actual_vacancies = [{'index': i, 'slot': FittingSlot(module.slot).name}
                                for i, module in enumerate(strategic_fit.modules)
                                if module.isEmpty and module.slot in (1, 2, 3, 4, 8)]
            self.assertEqual(expected_vacancies, actual_vacancies)
        def test_strict_atomic_selection_and_stale_rejection(self):
            key = self.create(expected['cases'][4])
            before = saved(self.bridge)
            for indices in ([], [0, 0], [0, 1, 2, 3, 4], [True], [0.0], ['0'], [-1], [999], None):
                self.dispatch('clone_selected_modules', {'fit_id': key, 'module_indices': indices}, False)
                self.assertEqual(before, saved(self.bridge))
            self.dispatch('clone_selected_modules', {'fit_id': key, 'module_indices': [0]}, False, revision=0)
            self.assertEqual(before, saved(self.bridge))
            for position in (True, 0.0, '0', -1, 999, 4):
                self.dispatch('fill_modules_clone', {'fit_id': key, 'position': position}, False)
                self.assertEqual(before, saved(self.bridge))
        def test_failed_write_copy_and_fresh_restart(self):
            self.bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, empty)
            key = self.bridge.sample_id
            gun = engine._item('Dual 150mm Railgun II').ID
            self.dispatch('add_module', {'fit_id': key, 'item_id': gun})
            copy = next(row['id'] for row in self.dispatch('duplicate_fit',
                {'fit_id': key, 'name': 'Independent clone copy'})['fits'] if row['id'] != key)
            self.dispatch('clone_selected_modules', {'fit_id': copy, 'module_indices': [9]})
            self.assertEqual(1, sum(not module.isEmpty for module in self.bridge._fits[key].modules))
            before = saved(self.bridge), (args.output / 'fits.db').read_bytes()
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic clone save failure')):
                self.dispatch('fill_modules_clone', {'fit_id': key, 'position': 9}, False)
            self.assertEqual(before, (saved(self.bridge), (args.output / 'fits.db').read_bytes()))
            self.dispatch('fill_modules_clone', {'fit_id': key, 'position': 9})
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            with (args.output / 'restart.log').open('w') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                    '--database', str(args.database), '--output', str(args.output),
                    '--source', str(args.source), '--restore'],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 2}, json.loads((args.output / 'restored.json').read_text()))

    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(CloneFillTests))
    if result.testsRun != 4 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Clone/fill regressions failed or attempted forbidden access')
    (args.output / 'observations.json').write_text(json.dumps({'cases': observations}, indent=2))
    (args.output / 'evidence.json').write_text(json.dumps({
        'tests_passed': 4, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network, 'fresh_process_restore': True,
        'cases': len(observations), 'states': sum(len(case['steps']) for case in observations)},
        indent=2) + '\n')


if __name__ == '__main__':
    main()
