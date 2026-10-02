"""B09.2 remaining mutation reversals against independent original commands."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from math import isclose
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
    for name in ('database', 'output', 'source'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--matrix-only', action='store_true', help='Focused development comparison; not complete verification')
    args = parser.parse_args()
    args.database, args.output, args.source = args.database.resolve(strict=True), args.output.resolve(), args.source.resolve(strict=True)
    validate_source(args.source)
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/history-mutations.json'
    expected = json.loads(fixture.read_text(encoding='utf-8'))
    identity = expected['database_logical_sha256']
    if args.output.is_relative_to(ROOT): raise ValueError('Use fresh output outside checkout')
    if not args.worker and not args.restore:
        compare(identity, logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                '--output', str(args.output), '--source', str(args.source), '--worker',
                *(['--matrix-only'] if args.matrix_only else [])],
                stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update(task='B09.2', host_only=True, database_sha256=before, database_logical_sha256=identity,
            reference_sha256=digest_file(fixture), game_database_unchanged=True)
        (args.output / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps(evidence)); return
    guard, network = NoDesktop(), []
    sys.meta_path.insert(0, guard)
    def audit(event, _):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
            network.append(event); raise RuntimeError('Network disabled')
    sys.addaudithook(audit)
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.history import LABELS, MODULE_LABELS
    engine = HeadlessEngine(args.database)

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'records': deepcopy(bridge._records),
            'recent': bridge.recent_items(), 'organization': bridge.organization()}
    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, None)
        compare(json.loads((args.output / 'before-restart.json').read_text()), saved(bridge))
        assert all(bridge.history_details(key)['undo_count'] == bridge.history_details(key)['redo_count'] == 0 for key in bridge._fits)
        (args.output / 'restored.json').write_text(json.dumps({'fits': len(bridge._fits), 'history_empty': True}))
        return

    class MutationHistoryTests(unittest.TestCase):
        def setUp(self): self.bridge = BridgeSession(engine)
        def tearDown(self): self.bridge._reset_storage()
        def send(self, operation, arguments, code=None, stale=False):
            keys = {arguments[k] for k in ('fit_id', 'source_id', 'target_id') if k in arguments}
            result = json.loads(self.bridge.dispatch(json.dumps({'version': 1, 'session_id': self.bridge.session_id,
                'request_id': 'mutation-history', 'operation': operation, 'arguments': arguments,
                'expected_revisions': {key: 0 if stale else self.bridge._revisions[key] for key in keys}})))
            self.assertEqual('ok' if code is None else 'error', result['status'], result.get('error'))
            if code: self.assertEqual(code, result['error']['code'])
            return result
        def create(self, spec): return self.send('create_fit', {'spec': deepcopy(spec)})['fits'][0]['id']
        def observe(self, key, linked=None):
            fit, record = self.bridge._fits[key], self.bridge._records[key]
            return {'name': fit.name, 'notes': fit.notes or '', 'stats': self.bridge._snapshots[key]['stats'],
                'mode': fit.mode.item.ID if fit.mode else None,
                'modules': [m for m in self.bridge._snapshots[key]['modules'] if 'empty_slot' not in m],
                'drones': record['spec']['drones'], 'implants': record['implants'],
                'cargo': [dict(name=c.item.name, amount=c.amount) for c in sorted(fit.cargo,
                    key=lambda c: (c.item.group.category.name, c.item.group.name, c.item.name))],
                'skill_override': record['skills'].get('Gunnery', record['spec']['skill_level']),
                'recent': self.bridge.recent_items()['item_ids'],
                'projections': [dict(source_name=self.bridge._fits[e['source_id']].name,
                    **{k: v for k, v in e.items() if k != 'source_id'}) for e in record['projections']],
                'commands': [dict(source_name=self.bridge._fits[e['source_id']].name,
                    **{k: v for k, v in e.items() if k != 'source_id'}) for e in record['commands']],
                'linked_stats': self.bridge._snapshots[linked]['stats'] if linked else None}
        def equal(self, wanted, actual, case, action):
            compare(wanted.keys(), actual.keys())
            for field in wanted:
                if field == 'recent' and case['operation'] in ('remove_cargo', 'add_implant', 'remove_implant'):
                    # Explicit pre-existing phone boundary: partial cargo removal
                    # promotes the selected item (the original calc command has
                    # no GUI side effect); implants do not enter phone equipment
                    # recent use. Assert the exact policy, never drop the field.
                    phone_recent = ([case['arguments']['item_id']] if case['operation'] == 'remove_cargo'
                        and action != 'initial' else [])
                    compare(phone_recent, actual[field], path='phone_recent')
                    continue
                if field in ('stats', 'linked_stats') and wanted[field] is not None:
                    compare(wanted[field].keys(), actual[field].keys())
                    for name, row in wanted[field].items():
                        other = actual[field][name]; compare(row['unit'], other['unit'])
                        a, b = row['value'], other['value']
                        if name in ('gun_optimal', 'gun_falloff') and b is None and a in (0, 1): continue
                        if type(a) in (int, float) and type(b) in (int, float):
                            self.assertTrue(isclose(a, b, rel_tol=1e-10, abs_tol=1e-9), (field, name, a, b))
                        else: compare(a, b)
                else: compare(wanted[field], actual[field], path=field)
        def setup_case(self, case):
            spec = deepcopy(case['spec']); implants = spec.pop('implants'); spec['implants'] = []
            key = self.create(spec)
            for implant in implants:
                self.send('add_implant', dict(fit_id=key, implant=implant['name'], active=implant['active']))
            source = self.create(case['source_spec']) if case['source_spec'] else None
            if case['setup_link']:
                operation = 'add_projection' if 'projection' in case['operation'] else 'add_command'
                args = dict(source_id=source, target_id=key, active=True)
                if operation == 'add_projection': args.update(range_m=0.0, amount=1)
                self.send(operation, args)
            return key, source
        def test_all_remaining_original_actions_and_reversals(self):
            covered, contexts, observations = set(), set(), []
            for case in expected['cases']:
                print('B09.2 original comparison:', case['name'], flush=True)
                with self.subTest(case=case['name']):
                    self.bridge._reset_storage(); self.bridge = BridgeSession(engine)
                    key, source = self.setup_case(case)
                    # Fixture setup establishes existing links; its action remains
                    # in the cursor and is never counted as the action under test.
                    baseline = self.bridge.history_details(key)['undo_count']
                    source_cursor = ({k: v for k, v in self.bridge.history_details(source).items() if k != 'revision'}
                        if source else None)
                    states = []
                    for step in case['steps']:
                        prior = self.bridge._revisions[key]
                        if step['action'] == 'do':
                            covered.add(case['operation'])
                            if case['operation'] == 'change_variation': contexts.add(case['arguments']['context'])
                            owner = dict(source_id=source, target_id=key) if source else dict(fit_id=key)
                            self.send(case['operation'], dict(**owner, **case['arguments']))
                        elif step['action'] != 'initial': self.send(step['action'], dict(fit_id=key))
                        if step['action'] != 'initial': self.assertGreater(self.bridge._revisions[key], prior)
                        self.equal(step['result'], self.observe(key, source), case, step['action'])
                        done = step['action'] in ('do', 'redo')
                        cursor = self.bridge.history_details(key)
                        self.assertEqual(baseline + int(done), cursor['undo_count'])
                        self.assertEqual(int(step['action'] == 'undo'), cursor['redo_count'])
                        if source: compare(source_cursor, {k: v for k, v in self.bridge.history_details(source).items() if k != 'revision'})
                        states.append(self.observe(key, source))
                    observations.append({'name': case['name'], 'states': states})
            compare(set(LABELS) - set(MODULE_LABELS), covered - {'change_variation'})
            compare({'implant', 'drone'}, contexts)
            (args.output / 'observations.json').write_text(json.dumps(observations, indent=2, allow_nan=False) + '\n')

        def test_durable_failures_stale_requests_notes_and_fresh_restart(self):
            self.bridge._reset_storage()
            self.bridge = BridgeSession.open(engine, args.output / 'fits.db', identity, expected['cases'][0]['spec'])
            for case in expected['cases']:
                print('B09.2 durable failure/reversal:', case['name'], flush=True)
                with self.subTest(case=case['name']):
                    key, source = self.setup_case(case)
                    owner = dict(source_id=source, target_id=key) if source else dict(fit_id=key)
                    arguments = dict(**owner, **case['arguments'])
                    def reject_save(operation, inputs):
                        before = saved(self.bridge)
                        cursors = {k: deepcopy(self.bridge.history_details(k)) for k in self.bridge._fits}
                        database_hash = digest_file(args.output / 'fits.db')
                        with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic B09.2 save failure')):
                            self.send(operation, inputs, 'ENGINE_ERROR')
                        compare(before, saved(self.bridge))
                        compare(cursors, {k: self.bridge.history_details(k) for k in self.bridge._fits})
                        compare(database_hash, digest_file(args.output / 'fits.db'))
                    reject_save(case['operation'], arguments)
                    self.send(case['operation'], arguments)
                    note = 'Later independent notes survive reversal — 保持'
                    self.send('set_notes', dict(fit_id=key, text=note))
                    reject_save('undo', dict(fit_id=key))
                    self.send('undo', dict(fit_id=key))
                    self.assertEqual(note, self.bridge.note_details(key)['text'])
                    before = saved(self.bridge)
                    cursor = deepcopy(self.bridge.history_details(key))
                    self.send('redo', dict(fit_id=key), 'REVISION_CONFLICT', stale=True)
                    self.send('redo', dict(fit_id=key, extra=True), 'INVALID_REQUEST')
                    compare(before, saved(self.bridge)); compare(cursor, self.bridge.history_details(key))
                    reject_save('redo', dict(fit_id=key))
                    self.send('redo', dict(fit_id=key))
                    self.assertEqual(note, self.bridge.note_details(key)['text'])
                    self.send('undo', dict(fit_id=key))
            count = len(self.bridge._fits)
            (args.output / 'before-restart.json').write_text(json.dumps(saved(self.bridge), allow_nan=False))
            with (args.output / 'restart.log').open('w', encoding='utf-8') as log:
                subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                    '--output', str(args.output), '--source', str(args.source), '--restore'],
                    stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
            compare({'fits': count, 'history_empty': True}, json.loads((args.output / 'restored.json').read_text()))

        def test_recent_redo_repromotes_after_another_fit(self):
            case = expected['interleaved_recent']; key, other = self.create(case['spec']), self.create(case['other_spec'])
            self.send('add_cargo', dict(fit_id=other, item_id=case['item_id'], quantity=1))
            self.send('remove_cargo', dict(fit_id=other, item_id=case['item_id'], quantity=1))
            observations = []
            for step in case['steps']:
                action = step['action']
                if action == 'do': self.send('add_cargo', dict(fit_id=key, item_id=case['item_id'], quantity=150))
                elif action in ('undo', 'redo'): self.send(action, dict(fit_id=key))
                elif action == 'other': self.send('add_cargo', dict(fit_id=other, item_id=case['other_item_id'], quantity=1))
                owner, unrelated = self.observe(key), self.observe(other)
                self.equal(step['owner'], owner, {'operation': 'add_cargo'}, action)
                self.equal(step['other'], unrelated, {'operation': 'add_cargo'}, action)
                for id_, field in ((key, 'owner_history'), (other, 'other_history')):
                    row = self.bridge.history_details(id_); undo, redo = row['undo_count'], row['redo_count']
                    compare(step[field], dict(undo_count=undo, redo_count=redo, can_undo=undo > 0, can_redo=redo > 0))
                observations.append(dict(action=action, owner=owner, other=unrelated))
            (args.output / 'interleaved-recent.json').write_text(json.dumps(observations, indent=2, allow_nan=False) + '\n')

    suite = (unittest.TestSuite([MutationHistoryTests('test_all_remaining_original_actions_and_reversals'),
        MutationHistoryTests('test_recent_redo_repromotes_after_another_fit')])
        if args.matrix_only else unittest.defaultTestLoader.loadTestsFromTestCase(MutationHistoryTests))
    if not args.matrix_only:
        from tools.android_headless.test_history_registration import HistoryRegistrationTest
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(HistoryRegistrationTest))
        sys.path.insert(0, str(ROOT / 'android/ci'))
        from test_mutation_history_summary import FixtureBytesTest, MutationStateTest
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(FixtureBytesTest))
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MutationStateTest))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != (2 if args.matrix_only else 22) or not result.wasSuccessful() or result.skipped or guard.attempts or network:
        raise RuntimeError('Mutation history regression failed or attempted forbidden access')
    (args.output / 'evidence.json').write_text(json.dumps({'tests_passed': result.testsRun, 'reference_cases': len(expected['cases']),
        'reference_states': sum(len(c['steps']) for c in expected['cases']),
        'interleaved_recent_steps': len(expected['interleaved_recent']['steps']),
        'complete_verification': not args.matrix_only, 'fresh_process_restore': not args.matrix_only,
        'restored': json.loads((args.output / 'restored.json').read_text()) if not args.matrix_only else None,
        'desktop_import_attempts': guard.attempts, 'network_attempts': network}, indent=2) + '\n')


if __name__ == '__main__': main()
