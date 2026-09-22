"""B04.1 full catalogue/search regression checks against independent desktop output."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import compare, digest_file, logical_database_digest
from tools.android_headless.check import DEPENDENCIES, NoDesktop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    args.database, args.output = args.database.resolve(strict=True), args.output.resolve()
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError('Use a new output outside the checkout and input database')
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    fixture = ROOT / 'tools/android_reference/fixtures/equipment.json'
    expected = json.loads(fixture.read_text(encoding='utf-8'))
    if not args.worker:
        baseline = json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())
        compare(baseline['database_logical_sha256'], logical_database_digest(args.database))
        before = digest_file(args.database)
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / 'tests.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--database', str(args.database),
                '--output', str(args.output / 'evidence.json'), '--worker'], check=True, stdout=log,
                stderr=subprocess.STDOUT, timeout=180)
        compare(before, digest_file(args.database))
        evidence = json.loads((args.output / 'evidence.json').read_text())
        evidence.update({'task': 'B04.1', 'host_only': True, 'database_sha256': before,
            'database_logical_sha256': baseline['database_logical_sha256'], 'game_database_unchanged': True,
            'reference_sha256': digest_file(fixture),
            'groups': len(expected['catalog']['groups']), 'items': len(expected['catalog']['items']),
            'search_queries': len(expected['searches'])})
        (args.output / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps(evidence))
        return
    guard, network = NoDesktop(), []
    sys.meta_path.insert(0, guard)
    def audit(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
            network.append(event)
            raise RuntimeError('Network is disabled')
    sys.addaudithook(audit)
    from android_bridge.engine import HeadlessEngine
    from android_bridge.market import EquipmentMarket
    from android_bridge.contract import BridgeSession
    engine = HeadlessEngine(args.database)
    market = EquipmentMarket(engine)
    case = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    del case['edit']
    fit = engine.create_fit(case)
    bridge = BridgeSession(engine, fit, case)

    class MarketTests(unittest.TestCase):
        def test_full_catalogue_and_every_membership_matches_desktop(self):
            compare(expected['catalog'], market.catalog())

        def test_all_independent_searches_repeat_on_same_worker(self):
            for _ in range(2):
                for query, ids in expected['searches'].items():
                    with self.subTest(query=query):
                        self.assertEqual(ids, market.search(query))

        def test_catalogue_results_cannot_mutate_cached_inputs(self):
            value = market.catalog()
            value['groups'][0]['item_ids'].append(-999)
            value['items'][0]['name'] = 'corrupted'
            value['roots'].clear()
            compare(expected['catalog'], market.catalog())

        def test_reading_does_not_edit_fit_or_recents(self):
            before = bridge.bootstrap(), bridge.organization(), engine.snapshot(fit)
            market.catalog()
            market.search('railgun t2')
            self.assertEqual(before, (bridge.bootstrap(), bridge.organization(), engine.snapshot(fit)))

        def test_worker_thread_ownership_is_enforced(self):
            failures = []
            def run():
                for call in (market.catalog, lambda: market.search('railgun')):
                    try:
                        call()
                    except RuntimeError as error:
                        failures.append(str(error))
            thread = threading.Thread(target=run)
            thread.start()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(2, len(failures))

        def test_invalid_input_and_hidden_items(self):
            for invalid in (None, True, 1, [], {}):
                with self.assertRaises(ValueError):
                    market.search(invalid)
            self.assertEqual([], market.search('Data Subverter'))
            self.assertEqual([], market.search('QA Damage'))
            self.assertEqual([], market.search('re:['))
            self.assertTrue(market.search('Prototype Iris'))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MarketTests))
    if result.testsRun != 6 or not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network:
        raise RuntimeError('Equipment tests failed, skipped or attempted forbidden access')
    args.output.write_text(json.dumps({'tests_passed': result.testsRun, 'desktop_import_attempts': guard.attempts,
        'network_attempts': network}, indent=2) + '\n')


if __name__ == '__main__':
    main()
