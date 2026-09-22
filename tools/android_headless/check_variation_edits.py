"""Guarded variation parity, worker ownership, atomic failure and restart checks."""
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
        raise ValueError('Use a fresh output outside checkout and input database')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/variation-edits.json'
    expected = json.loads(fixture.read_text())
    identity = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256']
    if not args.worker and not args.restore:
        compare(identity, logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                '--output', str(args.output), '--worker'], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update({'task': 'B04.2.3.2', 'host_only': True, 'database_sha256': before,
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
    from android_bridge.variations import choices
    from android_bridge.market import EquipmentMarket
    engine = HeadlessEngine(args.database)
    from android_bridge.market_policy import MarketPolicy
    import eos.db
    from eos.const import FittingModuleState, ImplantLocation
    from eos.saveddata.module import Module

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'recent': bridge.recent_items(),
                'options': [bridge.variation_options(key) for key in bridge._fits],
                'organization': bridge.organization(), 'records': deepcopy(bridge._records)}
    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, None)
        compare(json.loads((args.output / 'before-restart.json').read_text()), saved(bridge))
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(bridge._fits)}))
        return
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit'); empty['modules'], empty['drones'] = [], []
    observations, families = [], []

    class VariationTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1, 'session_id': self.bridge.session_id,
                'request_id': 'variation-edits', 'operation': operation, 'arguments': arguments,
                'expected_revisions': {key: self.bridge._revisions[key] if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response
        def create(self, case=None):
            case = case or {'name': 'Variation probe', 'ship': 'Rifter'}
            key = self.dispatch('create_fit', {'spec': {**deepcopy(empty), 'ship': case['ship'], 'name': case['name'],
                'modules': case.get('modules', []), 'drones': case.get('drones', []),
                'ignore_restrictions': case.get('ignore_restrictions', False)}})['fits'][0]['id']
            for implant in case.get('implants', []):
                self.dispatch('add_implant', {'fit_id': key, 'implant': implant['name'], 'active': implant['active']})
            self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': case.get('ignore_restrictions', False)})
            return key
        def change(self, key, context, position, item, ok=True):
            return self.dispatch('change_variation', {'fit_id': key, 'context': context, 'position': position,
                'item_id': engine._item(item).ID}, ok)
        def test_original_commands_raw_values_and_every_recipient(self):
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
                        if operation:
                            target = next(row for row in self.bridge.variation_options(key)['targets']
                                          if row['context'] == operation['context'] and row['index'] == operation['position'])
                            same = target['item_id'] == operation['item_id']
                            before = saved(self.bridge)
                            response = self.dispatch('change_variation', {'fit_id': key,
                                **{k: v for k, v in operation.items() if k != 'name'}}, step['changed'] or same)
                            if not step['changed']:
                                # B01 acknowledges every accepted request with a
                                # new revision, even when declarative inputs did
                                # not change. All other state must remain exact.
                                if same:
                                    acknowledged = {row['id'] for row in response['fits']}
                                    for row in before['fits']:
                                        if row['id'] in acknowledged: row['revision'] += 1
                                    for row in before['options']:
                                        if row['fit_id'] in acknowledged: row['revision'] += 1
                                self.assertEqual(before, saved(self.bridge))
                        gc.collect()
                        fit = self.bridge._fits[key]
                        options = self.bridge.variation_options(key)
                        modules = []
                        for row in step['result']['modules']:
                            mod = fit.modules[row['index']]
                            modules.append({'index': row['index'], 'id': mod.itemID, 'state': FittingModuleState(mod.state).name,
                                'charge_id': mod.chargeID, 'attributes': {name: {'value': mod.getModifiedItemAttr(name, None), 'unit': entry['unit']}
                                    for name, entry in row['attributes'].items()}})
                        actual = {'options': {'targets': options['targets']}, 'stats': self.bridge._snapshots[key]['stats'],
                            'modules': modules, 'drones': [{'index': i, 'id': drone.itemID, 'amount': drone.amount, 'active': drone.amountActive}
                                for i, drone in enumerate(fit.drones)],
                            'implants': [{'index': i, 'id': implant.itemID, 'slot': implant.slot, 'active': implant.active}
                                for i, implant in enumerate(fit.implants)], 'implant_location': ImplantLocation(fit.implantLocation).name,
                            'recipients': [{'name': self.bridge._snapshots[target]['name'], 'stats': self.bridge._snapshots[target]['stats']}
                                           for target in recipients], 'recent': self.bridge.recent_items()['item_ids']}
                        compare(step['result'], actual, case['name'] + '.' + str(operation))
                        steps.append({'input': operation, 'changed': step['changed'], 'result': actual})
                    observations.append({'name': case['name'], 'steps': steps})
                    for fit_id in reversed(list(self.bridge._fits)):
                        self.dispatch('delete_fit', {'fit_id': fit_id, 'resolve_references': True})
        def test_complete_5226_original_families_order_and_enablement(self):
            key = self.create(); policy = MarketPolicy()
            for row in EquipmentMarket(engine).catalog()['items']:
                category = row['category']
                if category not in ('Module', 'Structure Module', 'Drone', 'Implant'): continue
                item = eos.db.getItem(row['id'])
                if category in ('Module', 'Structure Module'):
                    try: module = Module(item)
                    except ValueError: continue
                    if module.slot not in (1, 2, 3, 4, 8): continue
                    context = 'module'
                elif category == 'Drone': context = 'drone'
                else:
                    if 'implantness' not in item.attributes: continue
                    context = 'implant'
                families.append({'id': item.ID, 'context': context, 'choices': choices(engine, self.bridge._fits[key], item, context, policy)})
            self.assertEqual(5226, len(families))
            compare(expected['families'], families)
        def test_atomic_invalid_family_category_position_revision_and_scalar_types(self):
            key = self.create(expected['cases'][0]); before = saved(self.bridge)
            valid = engine._item('Dual 150mm Railgun I').ID
            base = {'fit_id': key, 'context': 'module', 'position': 0, 'item_id': valid}
            for field, values in {'context': ['cargo', '', 1, None], 'position': [True, 0.0, '0', -1, 999, 1],
                                  'item_id': [True, float(valid), str(valid), 0, -1, 2147483648, 99999999, 34,
                                              engine._item('150mm Railgun II').ID, engine._item('Hobgoblin II').ID]}.items():
                for value in values: self.dispatch('change_variation', {**base, field: value}, False)
            self.dispatch('change_variation', base, False, revision=0)
            self.assertEqual(before, saved(self.bridge))
        def test_read_only_empty_options_and_worker_ownership(self):
            key = self.create(); before = saved(self.bridge)
            self.assertEqual([], self.bridge.variation_options(key)['targets'])
            self.assertEqual(before, saved(self.bridge))
            failures = []
            def foreign():
                try: self.bridge.variation_options(key)
                except RuntimeError: failures.append(True)
            thread = threading.Thread(target=foreign); thread.start(); thread.join()
            self.assertEqual([True], failures)
        def test_fit_restriction_failure_preserves_recent_use_and_every_input(self):
            key = self.create()
            self.dispatch('add_module', {'fit_id': key, 'item_id': engine._item('Damage Control I').ID})
            other = self.create({'name': 'No turret hardpoints', 'ship': 'Kestrel', 'ignore_restrictions': True,
                                 'modules': [{'name': '200mm AutoCannon I', 'state': 'ACTIVE', 'charge': 'EMP S'}]})
            self.dispatch('set_fit_restrictions', {'fit_id': other, 'ignore': False})
            before = saved(self.bridge)
            self.change(other, 'module', 0, '200mm AutoCannon II', False)
            self.assertEqual(before, saved(self.bridge))
        def test_failed_writes_independent_copies_and_real_process_restore(self):
            case = expected['cases'][10]
            initial = {**deepcopy(empty), 'drones': deepcopy(case['drones']), 'modules': deepcopy(expected['cases'][0]['modules'])}
            self.bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, initial)
            key = self.bridge.sample_id
            self.dispatch('add_implant', {'fit_id': key, 'implant': "Eifyr and Co. 'Rogue' Navigation NN-601", 'active': True})
            self.change(key, 'drone', 0, 'Hobgoblin II')
            self.change(key, 'module', 0, 'Dual 150mm Railgun I')
            self.change(key, 'implant', 0, "Eifyr and Co. 'Rogue' Navigation NN-605")
            self.dispatch('add_implant', {'fit_id': key, 'implant': 'Genolution Core Augmentation CA-1', 'active': False})
            self.dispatch('add_implant', {'fit_id': key, 'implant': 'Genolution Core Augmentation CA-2', 'active': True})
            duplicate = saved(self.bridge)
            self.change(key, 'implant', 1, 'Genolution Core Augmentation CA-2', False)
            self.assertEqual(duplicate, saved(self.bridge))
            self.change(key, 'implant', 1, 'Genolution Core Augmentation CA-3')
            self.assertEqual(4, len(self.bridge._fits[key].implants))
            source = deepcopy(self.bridge._records[key])
            copy = next(row['id'] for row in self.dispatch('duplicate_fit', {'fit_id': key, 'name': 'Independent variation copy'})['fits'] if row['id'] != key)
            self.change(copy, 'drone', 2, 'Hobgoblin I')
            self.change(copy, 'module', 0, 'Dual 150mm Railgun II')
            self.change(copy, 'implant', 0, "Eifyr and Co. 'Rogue' Navigation NN-601")
            self.assertEqual(source, self.bridge._records[key])
            before = saved(self.bridge), (args.output / 'fits.db').read_bytes()
            for context, position, name in [('drone', 2, 'Hobgoblin I'), ('module', 0, 'Dual 150mm Railgun II'),
                                            ('implant', 0, "Eifyr and Co. 'Rogue' Navigation NN-601")]:
                with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic variation save failure')):
                    self.change(key, context, position, name, False)
                self.assertEqual(before, (saved(self.bridge), (args.output / 'fits.db').read_bytes()))
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            with (args.output / 'restart.log').open('w') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--restore'], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 2}, json.loads((args.output / 'restored.json').read_text()))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(VariationTests))
    if result.testsRun != 6 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Variation regressions failed or attempted forbidden access')
    (args.output / 'observations.json').write_text(json.dumps({'cases': observations, 'families': families}, indent=2))
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 6, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network, 'fresh_process_restore': True, 'cases': len(observations),
        'states': sum(len(case['steps']) for case in observations), 'families': len(families)}, indent=2) + '\n')


if __name__ == '__main__':
    main()
