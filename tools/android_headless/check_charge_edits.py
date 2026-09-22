"""Guarded charge parity, discovery, atomic failure and process-restore tests."""
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
        raise ValueError('Use a fresh output outside the checkout and input database')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/charge-edits.json'
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
        evidence.update({'task': 'B04.2.3.1', 'host_only': True, 'database_sha256': before,
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
    from android_bridge.charges import compatible
    engine = HeadlessEngine(args.database)
    import eos.db
    from eos.const import FittingModuleState
    from eos.saveddata.module import Module
    from android_bridge.market import EquipmentMarket

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'recent': bridge.recent_items(),
                'options': [bridge.charge_options(key) for key in bridge._fits], 'organization': bridge.organization()}
    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, None)
        compare(json.loads((args.output / 'before-restart.json').read_text()), saved(bridge))
        assert bridge.persistence_info['opened_existing'] and not guard.attempts and not network
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(bridge._fits)}))
        return
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit')
    empty['modules'], empty['drones'] = [], []
    observations, sets = [], []

    class ChargeTests(unittest.TestCase):
        def setUp(self):
            self.bridge = BridgeSession(engine)
        def tearDown(self):
            self.bridge._reset_storage()
        def dispatch(self, operation, arguments, ok=True, revision=None):
            named = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            response = json.loads(self.bridge.dispatch(json.dumps({'version': 1, 'session_id': self.bridge.session_id,
                'request_id': 'charge-edits', 'operation': operation, 'arguments': arguments,
                'expected_revisions': {key: self.bridge._revisions[key] if revision is None else revision for key in named}})))
            self.assertEqual('ok' if ok else 'error', response['status'], response.get('error'))
            return response
        def create(self, ship='Vexor', name='Synthetic charges', modules=()):
            return self.dispatch('create_fit', {'spec': {**deepcopy(empty), 'ship': ship, 'name': name, 'modules': list(modules)}})['fits'][0]['id']
        def change(self, key, position, charge, ok=True):
            return self.dispatch('set_module_charge', {'fit_id': key, 'position': position,
                'charge_id': engine._item(charge).ID if charge else None}, ok)
        def test_complete_original_commands_raw_values_and_all_recipients(self):
            for case in expected['cases']:
                with self.subTest(case=case['name']):
                    key = self.create(case['ship'], case['name'], case['modules'])
                    self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
                    recipients = []
                    for row in case.get('recipients', []):
                        target = self.create(row['ship'], row['name'])
                        self.dispatch('set_fit_restrictions', {'fit_id': target, 'ignore': False})
                        if case.get('link') == 'command':
                            self.dispatch('add_command', {'source_id': key, 'target_id': target, 'active': True})
                        else:
                            self.dispatch('add_projection', {'source_id': key, 'target_id': target, 'range_m': 0.0, 'active': True, 'amount': 1})
                        recipients.append(target)
                    rows = []
                    for step in case['steps']:
                        operation = step['input']
                        if operation:
                            same = self.bridge._fits[key].modules[operation['position']].chargeID == operation['charge_id']
                            before = saved(self.bridge)
                            result = self.dispatch('set_module_charge', {'fit_id': key,
                                'position': operation['position'], 'charge_id': operation['charge_id']}, step['changed'] or same)
                            if not step['changed']:
                                self.assertEqual(before['organization'], self.bridge.organization())
                                if not same:
                                    self.assertEqual(before, saved(self.bridge))
                        gc.collect()
                        options = self.bridge.charge_options(key)
                        modules = []
                        for row in step['result']['modules']:
                            mod = self.bridge._fits[key].modules[row['index']]
                            modules.append({'index': row['index'], 'id': mod.itemID, 'state': FittingModuleState(mod.state).name,
                                'charge_id': mod.chargeID, 'attributes': {name: {'value': mod.getModifiedItemAttr(name, None), 'unit': entry['unit']}
                                    for name, entry in row['attributes'].items()}})
                        actual = {'options': {k: v for k, v in options.items() if k not in ('version', 'fit_id', 'revision')},
                            'stats': self.bridge._snapshots[key]['stats'], 'modules': modules,
                            'recipients': [{'name': self.bridge._snapshots[target]['name'], 'stats': self.bridge._snapshots[target]['stats']} for target in recipients],
                            'recent': self.bridge.recent_items()['item_ids']}
                        compare(step['result'], actual, case['name'] + '.' + str(operation))
                        rows.append({'input': operation, 'changed': step['changed'], 'result': actual})
                    observations.append({'name': case['name'], 'steps': rows})
                    for fit_id in reversed(list(self.bridge._fits)):
                        self.dispatch('delete_fit', {'fit_id': fit_id, 'resolve_references': True})
        def test_complete_4242_module_compatibility_sets(self):
            for item in EquipmentMarket(engine).catalog()['items']:
                if item['category'] not in ('Module', 'Structure Module'):
                    continue
                try:
                    module = Module(eos.db.getItem(item['id']))
                except ValueError:
                    continue
                if module.slot in (1, 2, 3, 4, 8):
                    sets.append({'id': item['id'], 'charge_ids': sorted(value.ID for value in compatible(module))})
            self.assertEqual(4242, len(sets))
            compare(expected['compatibility'], sets)
        def test_overlapping_item_and_group_ids_and_read_only_worker_ownership(self):
            from eos.gamedata import Item, Group
            self.assertIs(eos.config.gamedataCache, False)
            overlap = eos.db.get_gamedata_session().query(Group.ID).join(Item, Item.ID == Group.ID).order_by(Group.ID).limit(3).all()
            self.assertEqual(3, len(overlap))
            for (identity,) in overlap:
                self.assertIsInstance(eos.db.getItem(identity), Item)
                self.assertIsInstance(eos.db.getGroup(identity), Group)
                self.assertIsInstance(eos.db.getItem(identity), Item)
            key = self.create(modules=expected['cases'][0]['modules'])
            before = saved(self.bridge)
            for _ in range(2):
                self.bridge.charge_options(key)
            self.assertEqual(before, saved(self.bridge))
            failures = []
            def foreign():
                try:
                    self.bridge.charge_options(key)
                except RuntimeError:
                    failures.append(True)
            thread = threading.Thread(target=foreign); thread.start(); thread.join()
            self.assertEqual([True], failures)
        def test_rejections_preserve_every_fit_history_and_modified_order(self):
            key = self.create(modules=expected['cases'][0]['modules'])
            self.dispatch('set_fit_restrictions', {'fit_id': key, 'ignore': False})
            before = saved(self.bridge)
            for charge in (True, 1.5, '1', -1, 0, 2147483648, 99999999, 34, engine._item('Antimatter Charge S').ID):
                self.dispatch('set_module_charge', {'fit_id': key, 'position': 0, 'charge_id': charge}, False)
            for position in (True, 1.5, '0', -1, 999, 2):
                self.dispatch('set_module_charge', {'fit_id': key, 'position': position, 'charge_id': None}, False)
            self.dispatch('set_module_charge', {'fit_id': key, 'position': 0, 'charge_id': None}, False, revision=0)
            self.assertEqual(before, saved(self.bridge))
        def test_active_fit_union_updates_after_module_changes(self):
            key = self.create(ship='Rupture')
            self.assertEqual([], self.bridge.charge_options(key)['items'])
            self.dispatch('add_module', {'fit_id': key, 'item_id': engine._item('Dual 150mm Railgun II').ID})
            first = self.bridge.charge_options(key)
            position = next(row['index'] for row in first['modules'] if row['item_id'])
            self.assertGreater(len(first['items']), 20)
            self.dispatch('replace_module', {'fit_id': key, 'position': position, 'item_id': engine._item('Heavy Missile Launcher II').ID})
            second = self.bridge.charge_options(key)
            self.assertNotEqual(first['items'], second['items'])
            self.dispatch('remove_module', {'fit_id': key, 'position': position})
            self.assertEqual([], self.bridge.charge_options(key)['items'])
        def test_failed_saves_independent_copies_and_fresh_process_restore(self):
            self.bridge = BridgeSession.open(engine, args.output / 'fits.db', identity,
                {**deepcopy(empty), 'modules': expected['cases'][0]['modules']})
            key = self.bridge.sample_id
            self.change(key, 0, 'Spike M')
            copied = self.dispatch('duplicate_fit', {'fit_id': key, 'name': 'Independent charge copy'})['fits']
            copy = next(row['id'] for row in copied if row['id'] != key)
            self.change(copy, 0, None)
            self.assertEqual('Spike M', self.bridge._snapshots[key]['modules'][0]['charge'])
            before = saved(self.bridge), (args.output / 'fits.db').read_bytes()
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic charge save failure')):
                self.change(key, 0, 'Iron Charge M', False)
            self.assertEqual(before, (saved(self.bridge), (args.output / 'fits.db').read_bytes()))
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            with (args.output / 'restart.log').open('w') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--restore'], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual({'matched': True, 'fits': 2}, json.loads((args.output / 'restored.json').read_text()))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ChargeTests))
    if result.testsRun != 6 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Charge regressions failed or attempted forbidden access')
    (args.output / 'observations.json').write_text(json.dumps({'cases': observations, 'compatibility': sets}, indent=2))
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': 6, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network, 'fresh_process_restore': True, 'cases': len(observations),
        'states': sum(len(case['steps']) for case in observations), 'modules': len(sets)}, indent=2) + '\n')


if __name__ == '__main__':
    main()
