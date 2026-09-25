"""Compare B05.4 bulk variation/removal with pinned original desktop commands."""
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
        raise ValueError('Use fresh output outside checkout')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/bulk-variation-removal.json'
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
        evidence.update({'task': 'B05.4', 'host_only': True, 'database_sha256': before,
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
    from android_bridge.bulk_edits import positions, change_variations
    from android_bridge import fitting
    from eos.const import FittingModuleState, FittingSlot
    engine = HeadlessEngine(args.database)
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit'); empty['modules'], empty['drones'] = [], []

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'recent': bridge.recent_items(),
                'records': deepcopy(bridge._records), 'organization': bridge.organization()}
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

    observations = []
    class BulkEditTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1,
                'session_id': self.bridge.session_id, 'request_id': 'b054', 'operation': operation,
                'arguments': arguments, 'expected_revisions': {key: self.bridge._revisions[key]
                    if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response
        def create(self, case):
            spec = {**deepcopy(empty), 'ship': case['ship'], 'name': case['name'],
                'modules': deepcopy(case.get('modules', [])),
                'ignore_restrictions': case.get('ignore_restrictions', False)}
            return self.dispatch('create_fit', {'spec': spec})['fits'][0]['id']
        def report(self, key, recipients):
            fit = self.bridge._fits[key]
            def stats(target):
                value = deepcopy(self.bridge._snapshots[target]['stats'])
                value['scan_resolution'] = {'value': self.bridge._fits[target].ship.getModifiedItemAttr('scanResolution'),
                                            'unit': 'mm'}
                return value
            return {'stats': stats(key),
                'modules': [{'index': i, 'id': module.itemID, 'slot': FittingSlot(module.slot).name,
                             'state': FittingModuleState(module.state).name, 'charge_id': module.chargeID}
                            for i, module in enumerate(fit.modules) if not module.isEmpty],
                'free_slots': {slot.name: fit.getSlotsFree(slot.value) for slot in (
                    FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH, FittingSlot.RIG, FittingSlot.SERVICE)},
                'recipients': [{'name': self.bridge._snapshots[target]['name'], 'stats': stats(target)}
                               for target in recipients], 'recent': self.bridge.recent_items()['item_ids']}
        def test_original_cases_all_states_and_recipients(self):
            for case in expected['cases']:
                with self.subTest(case=case['name']):
                    key = self.create(case); recipients = []
                    for row in case.get('recipients', []):
                        target = self.create(row)
                        self.dispatch('add_projection', {'source_id': key, 'target_id': target,
                            'range_m': 0.0, 'active': True, 'amount': 1})
                        recipients.append(target)
                    for step in case['steps']:
                        operation = step['input']
                        if operation:
                            kind = operation['kind']
                            request = {name: value for name, value in operation.items() if name != 'kind'}
                            if kind == 'variation_direct':
                                # The desktop GUI command accepts an invalid mixed-slot list.
                                # The menu filters that slot; its successful output is identical.
                                kind = 'variation'
                            predicted = positions(engine, self.bridge._fits[key], request['main_position'],
                                request['selected_positions'], request['scope'],
                                'variation' if kind == 'variation' else 'remove')
                            if operation['kind'] != 'variation_direct':
                                compare(step['positions'], predicted, case['name'] + '.positions')
                            self.dispatch('change_bulk_variations' if kind == 'variation' else 'remove_bulk_modules',
                                {'fit_id': key, 'main_position': request['main_position'],
                                 'module_indices': request['selected_positions'], 'scope': request['scope'],
                                 **({'item_id': request['item_id']} if kind == 'variation' else {})})
                        actual = self.report(key, recipients)
                        reference = deepcopy(step['result'])
                        actual = comparable(actual); reference = comparable(reference)
                        for source, target in [(reference, actual), *zip(reference['recipients'], actual['recipients'])]:
                            for field in ('gun_optimal', 'gun_falloff'):
                                if source['stats'][field]['value'] in (0.0, 1.0) and target['stats'][field]['value'] is None:
                                    source['stats'][field]['value'] = None
                        compare(reference, actual, case['name'] + '.' + str(operation))
                    observations.append(case['name'])
                    for fit_id in reversed(list(self.bridge._fits)):
                        self.dispatch('delete_fit', {'fit_id': fit_id, 'resolve_references': True})
        def test_malformed_stale_and_failed_save(self):
            key = self.create(expected['cases'][0]); before = saved(self.bridge)
            valid = expected['cases'][0]['steps'][1]['input']
            base = {'fit_id': key, 'main_position': valid['main_position'],
                    'module_indices': valid['selected_positions'], 'scope': valid['scope'],
                    'item_id': valid['item_id']}
            for field, values in {'main_position': [True, -1, 999],
                    'module_indices': [[], [0, 0], [True], [-1], [999], [1, 2]],
                    'scope': ['ALL', None, True], 'item_id': [True, -1, 99999999]}.items():
                for value in values:
                    self.dispatch('change_bulk_variations', {**base, field: value}, False)
                    compare(before, saved(self.bridge))
            self.dispatch('change_bulk_variations', base, False, revision=0)
            compare(before, saved(self.bridge))
        def test_rejected_later_replacement_keeps_earlier_success(self):
            case = expected['cases'][1]
            key = self.create(case)
            original = fitting.new_module
            attempts = []
            def reject_second(engine, identity):
                module = original(engine, identity)
                attempts.append(module)
                if len(attempts) == 2:
                    module.fits = lambda _: False
                return module
            with patch('android_bridge.bulk_edits.fitting.new_module', side_effect=reject_second):
                change_variations(engine, self.bridge._fits[key], 0, [0], 'SIMILAR',
                                  engine._item('Dual 150mm Railgun II').ID)
            self.assertEqual(2, len(attempts))
            fit = self.bridge._fits[key]
            self.assertEqual([3106, 3106, 12346], [fit.modules[i].itemID for i in range(3)])
            self.assertEqual([], self.bridge.recent_items()['item_ids'])
            # The rejected candidate must not retain its new ORM identity or
            # disturb the earlier accepted candidate's EOS state and charge.
            self.assertEqual('Iron Charge M', fit.modules[2].charge.name)
        def test_worker_read_only_and_fresh_restart(self):
            self.bridge = BridgeSession.open(engine, args.output / 'fits.db', identity,
                {**deepcopy(empty), 'ship': 'Vexor', 'modules': deepcopy(expected['cases'][0]['modules'])})
            key = self.bridge.sample_id
            before = saved(self.bridge)
            failures = []
            def foreign():
                try: positions(engine, self.bridge._fits[key], 0, [0], 'SELECTED', 'remove')
                except RuntimeError: failures.append(True)
            thread = threading.Thread(target=foreign); thread.start(); thread.join()
            self.assertEqual([True], failures)
            compare(before, saved(self.bridge))
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic save failure')):
                self.dispatch('remove_bulk_modules', {'fit_id': key, 'main_position': 0,
                    'module_indices': [0, 1], 'scope': 'SELECTED'}, False)
            compare(before, saved(self.bridge))
            self.dispatch('remove_bulk_modules', {'fit_id': key, 'main_position': 0,
                'module_indices': [0, 1], 'scope': 'SELECTED'})
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            with (args.output / 'restart.log').open('w') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--source', str(args.source), '--restore'],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 1}, json.loads((args.output / 'restored.json').read_text()))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BulkEditTests))
    if result.testsRun != 4 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Bulk edit regressions failed or attempted forbidden access')
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 4, 'cases': len(observations),
        'states': sum(len(case['steps']) for case in expected['cases']), 'fresh_process_restore': True,
        'desktop_import_attempts': guard.attempts, 'network_attempts': network}, indent=2) + '\n')


if __name__ == '__main__': main()
