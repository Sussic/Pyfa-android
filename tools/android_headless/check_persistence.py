#!/usr/bin/env python3
"""Verify B02 saves, true process restarts and interrupted SQLite commits."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_headless.check import DEPENDENCIES, NoDesktop
from tools.android_reference.reference import compare, digest_file, logical_database_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--identity", help=argparse.SUPPRESS)
    parser.add_argument("--store", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        raise ValueError("Persistence checks use Python 3.11")
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    args.database, args.output = args.database.resolve(strict=True), args.output.resolve()
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError("Output must be outside the checkout and input database")
    guard = NoDesktop()
    sys.meta_path.insert(0, guard)
    network_attempts = []

    def no_network(event, arguments):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            network_attempts.append(event)
            raise RuntimeError("Network is disabled during persistence checks")
    sys.addaudithook(no_network)
    spec = importlib.util.spec_from_file_location("persistence_tests", Path(__file__).parent / "tests/test_persistence.py")
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    if args.worker:
        tests.worker(args.worker, args.database, args.identity, args.store.resolve(), args.output)
        if guard.attempts or network_attempts:
            raise RuntimeError("Persistence worker attempted a forbidden operation")
        return
    fixtures = {name: ROOT / "tools/android_reference/fixtures" / (name + ".json")
                for name in ("vexor", "projection", "command")}
    before = digest_file(args.database)
    identity = logical_database_digest(args.database)
    for path in fixtures.values():
        compare(identity, json.loads(path.read_text(encoding="utf-8"))["database_logical_sha256"])
    tests.DATABASE, tests.IDENTITY = args.database, identity
    args.output.mkdir(parents=True, exist_ok=False)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.PersistenceTests)
    test_names = [test.id() for test in suite]
    with (args.output / "tests.log").open("w", encoding="utf-8") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    if (result.testsRun != 11 or not result.wasSuccessful() or result.skipped or
            result.expectedFailures or guard.attempts or network_attempts):
        raise RuntimeError("Persistence tests failed, skipped or attempted forbidden operations")
    compare(before, digest_file(args.database), "unchanged_game_database")
    evidence = {"task": "B02", "host_only": True, "tests_passed": result.testsRun, "test_names": test_names,
        "real_fresh_process_reopen": True, "retained_fit_graph_size": 9,
        "before_after_commit_process_death_tested": True, "initialization_process_death_tested": True,
        "ambiguous_commit_confirmation_tested": True, "confirmed_publication_failure_tested": True, "invalid_saved_files_preserved": True,
        "database_sha256": before, "database_logical_sha256": identity,
        "game_database_unchanged": True, "desktop_import_attempts": guard.attempts,
        "network_attempts": network_attempts,
        "reference_fixture_sha256": {name: digest_file(path) for name, path in fixtures.items()},
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for name in ("android_bridge/store.py", "android_bridge/contract.py",
                         "tools/android_headless/tests/test_persistence.py", "tools/android_headless/check_persistence.py")}}
    (args.output / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "tests": result.testsRun, "fresh_processes": True}))


if __name__ == "__main__":
    main()
