#!/usr/bin/env python3
"""Run real B01 contract/recovery tests with pinned data and headless guards."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
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
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    import importlib.metadata
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES}, "host_dependencies")
    if sys.version_info[:2] != (3, 11):
        raise ValueError("The host contract checks use Python 3.11")
    args.database = args.database.resolve(strict=True)
    args.output = args.output.resolve()
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError("Output must be outside the checkout and input database")
    fixtures, cases, fixture_hashes = {}, {}, {}
    for kind, name in (("ammunition", "vexor"), ("projection", "projection"), ("command", "command")):
        path = ROOT / "tools/android_reference/fixtures" / (name + ".json")
        fixtures[kind] = json.loads(path.read_text(encoding="utf-8"))
        cases[kind] = json.loads((ROOT / "tools/android_reference" / (name + ".json")).read_text(encoding="utf-8"))
        compare(fixtures[kind]["inputs"], cases[kind], kind + ".inputs")
        fixture_hashes[kind] = digest_file(path)
    if args.worker:
        guard = NoDesktop()
        sys.meta_path.insert(0, guard)
        network_attempts = []

        def no_network(event, arguments):
            if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
                network_attempts.append(event)
                raise RuntimeError("Network is disabled during bridge tests")
        sys.addaudithook(no_network)
        from android_bridge import HeadlessEngine
        spec = importlib.util.spec_from_file_location("bridge_tests", Path(__file__).parent / "tests/test_contract.py")
        tests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tests)
        tests.ENGINE, tests.CASES, tests.EXPECTED = HeadlessEngine(args.database), cases, fixtures
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.ContractTests))
        if not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network_attempts:
            raise RuntimeError("Bridge tests failed, skipped or attempted forbidden operations")
        args.output.write_text(json.dumps({"tests_passed": result.testsRun,
            "desktop_import_attempts": guard.attempts, "network_attempts": network_attempts}, indent=2) + "\n", encoding="utf-8")
        return
    before = digest_file(args.database)
    logical = logical_database_digest(args.database)
    for expected in fixtures.values():
        compare(expected["database_logical_sha256"], logical)
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "tests.log").open("w", encoding="utf-8") as log:
        subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--database", str(args.database),
                        "--output", str(args.output / "tests.json"), "--worker"],
                       check=True, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    compare(before, digest_file(args.database), "unchanged_database")
    result = json.loads((args.output / "tests.json").read_text(encoding="utf-8"))
    result.update({"task": "B01", "host_only": True, "database_sha256": before,
                   "database_logical_sha256": logical, "reference_fixture_sha256": fixture_hashes,
                   "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                      for path in ("android_bridge/contract.py", "android_bridge/engine.py",
                                                   "tools/android_headless/tests/test_contract.py", "tools/android_headless/check_bridge.py")},
                   "all_three_reference_cases_matched": True, "game_database_unchanged": True})
    (args.output / "evidence.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "tests": result["tests_passed"], "host_only": True}))


if __name__ == "__main__":
    main()
