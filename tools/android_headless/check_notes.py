"""Check B08 exact notes against pinned service/pane behavior and durable EOS replay."""
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
    fixture = ROOT / 'tools/android_reference/fixtures/notes.json'
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
        evidence.update({'task': 'B08', 'host_only': True, 'database_sha256': before,
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
    from android_bridge.store import StoreError
    engine = HeadlessEngine(args.database)
    import eos.db
    empty = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    empty.pop('edit'); empty['modules'], empty['drones'] = [], []

    def saved(bridge):
        return {'fits': json.loads(bridge.bootstrap())['fits'], 'records': deepcopy(bridge._records),
                'organization': bridge.organization(), 'recent': bridge.recent_items(), 'notes': {key: bridge.note_details(key) for key in bridge._fits}}

    if args.restore:
        bridge = BridgeSession.open(engine, args.output / 'fits.db', identity,
            {**deepcopy(empty), 'name': 'B08 Vexor'})
        actual, prior = saved(bridge), json.loads((args.output / 'before-restart.json').read_text())
        compare(prior, actual)
        (args.output / 'restored.json').write_text(json.dumps({'matched': True, 'fits': len(actual['fits'])}))
        return

    class NoteTests(unittest.TestCase):
        def setUp(self):
            self.bridge = BridgeSession(engine)
            self.bridge._dataset_identity = identity
        def tearDown(self): self.bridge._reset_storage()

        def send(self, operation, arguments, code=None, revision=None):
            keys = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
            result = json.loads(self.bridge.dispatch(json.dumps({'version': 1,
                'session_id': self.bridge.session_id, 'request_id': 'b08', 'operation': operation,
                'arguments': arguments, 'expected_revisions': {key: self.bridge._revisions[key]
                    if revision is None else revision for key in keys}})))
            self.assertEqual('ok' if code is None else 'error', result['status'], result.get('error'))
            if code is not None: self.assertEqual(code, result['error']['code'])
            return result

        def create(self, key, **extra):
            original = expected['initial'][key]
            spec = {**deepcopy(empty), 'name': 'B08 ' + key, 'ship': original['ship'], **extra}
            if original['notes'] is not None: spec['notes'] = original['notes']
            return self.send('create_fit', {'spec': spec})['fits'][0]['id']

        def test_exact_reference_text_isolation_and_calculations(self):
            keys = {key: self.create(key) for key in expected['initial']}
            original_stats = {key: self.bridge._snapshots[value]['stats'] for key,value in keys.items()}
            for key, original in expected['initial'].items():
                self.assertEqual(original['stats'].keys(), original_stats[key].keys())
                for name, value in original['stats'].items():
                    observed = original_stats[key][name]
                    compare(value['unit'], observed['unit'])
                    a,b = value['value'], observed['value']
                    if b is None and name in ('gun_optimal','gun_falloff') and a in (0,1):
                        continue  # Existing desktop-only absent-weapon representation.
                    if type(a) in (int,float) and type(b) in (int,float):
                        self.assertTrue(isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(key,name,a,b))
                    else: compare(a,b)
            for text in [expected['inputs'][name] for name in ('unicode', 'whitespace', 'beta', 'long')] + ['', ' ', '\r\n', '\x00']:
                prior_beta = self.bridge.note_details(keys['beta'])
                self.send('set_notes', {'fit_id': keys['alpha'], 'text': text})
                value = self.bridge.note_details(keys['alpha'])
                self.assertEqual(text, value['text']); self.assertEqual(len(text), value['characters'])
                self.assertTrue(value['editable'])
                compare(prior_beta, self.bridge.note_details(keys['beta']))
                for key, identity in keys.items(): compare(original_stats[key], self.bridge._snapshots[identity]['stats'])
                compare([], self.bridge.recent_items()['item_ids'])
            structure = self.bridge.note_details(keys['structure'])
            self.assertFalse(structure['editable'])
            self.assertEqual(expected['inputs']['structure'], structure['text'])
            self.send('set_notes', {'fit_id': keys['structure'], 'text': 'replace'}, 'INVALID_EDIT')
            compare(structure, self.bridge.note_details(keys['structure']))

        def test_malformed_stale_and_bad_saved_note_types(self):
            key = self.create('alpha')
            self.send('set_notes', {'fit_id': key, 'text': expected['inputs']['unicode']})
            before = saved(self.bridge)
            for text in [None, True, 3, [], {}, '\ud800']:
                self.send('set_notes', {'fit_id': key, 'text': text}, 'INVALID_REQUEST')
                compare(before, saved(self.bridge))
            self.send('set_notes', {'fit_id': key, 'text': 'stale'}, 'REVISION_CONFLICT', 0)
            compare(before, saved(self.bridge))
            graph = self.bridge._graph(self.bridge._records, self.bridge._revisions)
            self.bridge._validate_graph(graph, identity, engine.settings)
            for text in [None, True, 1, '\ud800']:
                corrupt = deepcopy(graph)
                corrupt['records'][key]['spec']['notes'] = text
                with self.assertRaises(StoreError):
                    self.bridge._validate_graph(corrupt, identity, engine.settings)
            compare(before, saved(self.bridge))

        def test_linked_fit_and_copy_notes_remain_independent(self):
            source, target = self.create('alpha'), self.create('beta')
            self.send('add_projection', {'source_id': source, 'target_id': target,
                'range_m': 0.0, 'active': True, 'amount': 1})
            self.send('set_notes', {'fit_id': target, 'text': expected['inputs']['beta']})
            stats = {key: value['stats'] for key,value in self.bridge._snapshots.items()}
            self.send('set_notes', {'fit_id': source, 'text': expected['inputs']['unicode']})
            for key,value in stats.items(): compare(value, self.bridge._snapshots[key]['stats'])
            self.assertEqual(expected['inputs']['beta'], self.bridge.note_details(target)['text'])
            result = self.send('duplicate_fit', {'fit_id': source, 'name': 'B08 copy'})
            copy = next(row['id'] for row in result['fits'] if row['name'] == 'B08 copy')
            self.assertEqual(self.bridge.note_details(source)['text'], self.bridge.note_details(copy)['text'])
            self.send('set_notes', {'fit_id': copy, 'text': 'independent copy'})
            self.assertEqual(expected['inputs']['unicode'], self.bridge.note_details(source)['text'])
            self.send('set_notes', {'fit_id': source, 'text': ''})
            self.assertEqual('independent copy', self.bridge.note_details(copy)['text'])
            compare([], self.bridge.recent_items()['item_ids'])

        def test_legacy_graph_failed_save_and_fresh_restart(self):
            self.bridge._reset_storage()
            self.bridge = BridgeSession.open(engine, args.output/'durable.db', identity,
                {**deepcopy(empty), 'name': 'B08 Vexor'})
            legacy = self.bridge.sample_id
            self.assertNotIn('notes', self.bridge._records[legacy]['spec'])
            self.assertEqual('', self.bridge.note_details(legacy)['text'])
            alpha, beta, structure = [self.create(key) for key in ('alpha','beta','structure')]
            for key,text in [(alpha,expected['inputs']['unicode']), (beta,expected['inputs']['long'])]:
                self.send('set_notes', {'fit_id':key,'text':text})
            result = self.send('duplicate_fit', {'fit_id': structure, 'name': 'B08 retained structure copy'})
            copied = next(row['id'] for row in result['fits'] if row['name']=='B08 retained structure copy')
            self.assertEqual(expected['copies']['structure'], self.bridge.note_details(copied)['text'])
            before = saved(self.bridge)
            with patch.object(self.bridge._store, 'write', side_effect=OSError('synthetic notes save failure')):
                self.send('set_notes', {'fit_id':alpha,'text':'must not commit'}, 'ENGINE_ERROR')
            compare(before, saved(self.bridge))
            self.assertNotIn('notes', self.bridge._records[legacy]['spec'])
            (args.output/'before-restart.json').write_text(json.dumps(saved(self.bridge)))
            shutil.copyfile(args.output/'durable.db', args.output/'fits.db')
            with (args.output/'restart.log').open('w',encoding='utf-8') as log:
                subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),
                    '--output',str(args.output),'--source',str(args.source),'--restore'],check=True,
                    stdout=log,stderr=subprocess.STDOUT,timeout=90)
            compare({'matched':True,'fits':5},json.loads((args.output/'restored.json').read_text()))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NoteTests))
    if result.testsRun != 4 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Notes regressions failed or attempted forbidden access')
    (args.output/'evidence.json').write_text(json.dumps({'tests_passed':4,'reference_fits':3,
        'reference_states':len(expected['steps']),'fresh_process_restore':True,'restored_fits':5,
        'desktop_import_attempts':guard.attempts,'network_attempts':network},indent=2)+'\n')


if __name__ == '__main__': main()
