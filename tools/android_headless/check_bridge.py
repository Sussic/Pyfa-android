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
    parser.add_argument('--lifecycle', action='store_true', help='Complete booster cold/warm regression in four bounded workers')
    parser.add_argument('--lifecycle-slice', type=int, choices=range(4), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.lifecycle_slice is not None and not args.worker: parser.error('--lifecycle-slice requires --worker')
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
        lifecycle_test='test_every_booster_shape_cold_warm_complete_original_inspection'
        if args.lifecycle_slice is None:
            names=[name for name in unittest.defaultTestLoader.getTestCaseNames(tests.ContractTests) if name!=lifecycle_test]
            compare(18,len(names),'preserved_bridge_tests')
            suite=unittest.TestSuite(tests.ContractTests(name) for name in names)
        else:
            tests.LIFECYCLE_SLICE=args.lifecycle_slice
            suite=unittest.TestSuite([tests.ContractTests(lifecycle_test)])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful() or result.skipped or result.expectedFailures or guard.attempts or network_attempts:
            raise RuntimeError("Bridge tests failed, skipped or attempted forbidden operations")
        args.output.write_text(json.dumps({"tests_passed": result.testsRun,
            "desktop_import_attempts": guard.attempts, "network_attempts": network_attempts,
            "lifecycle_slice":args.lifecycle_slice,"booster_shape_indices":tests.LIFECYCLE_COVERAGE}, indent=2) + "\n", encoding="utf-8")
        return
    before = digest_file(args.database)
    logical = logical_database_digest(args.database)
    for expected in fixtures.values():
        compare(expected["database_logical_sha256"], logical)
    context_fixture = ROOT / 'tools/android_reference/fixtures/inspector-contexts.json.gz'
    fixture_hashes['inspector_contexts'] = digest_file(context_fixture)
    args.output.mkdir(parents=True, exist_ok=False)
    workers=range(4) if args.lifecycle else (None,)
    results=[]
    for part in workers:
        stem='tests' if part is None else 'lifecycle-'+str(part)
        with (args.output / (stem+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--database',str(args.database),
                            '--output',str(args.output/(stem+'.json')),'--worker',
                            *([] if part is None else ['--lifecycle-slice',str(part)])],
                           check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        worker=json.loads((args.output/(stem+'.json')).read_text(encoding='utf-8'))
        compare(part,worker['lifecycle_slice'])
        compare([] if part is None else list(range(part*25,min(99,(part+1)*25))),worker['booster_shape_indices'])
        results.append(worker)
    compare(before, digest_file(args.database), "unchanged_database")
    result=dict(tests_passed=sum(row['tests_passed'] for row in results),workers=results,
                desktop_import_attempts=[value for row in results for value in row['desktop_import_attempts']],
                network_attempts=[value for row in results for value in row['network_attempts']])
    if args.lifecycle:compare(list(range(99)),[index for row in results for index in row['booster_shape_indices']])
    result.update({"task": "C03.2.1" if args.lifecycle else "B01", "host_only": True, "database_sha256": before,
                   "database_logical_sha256": logical, "reference_fixture_sha256": fixture_hashes,
                   "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                      for path in ("android_bridge/contract.py", "android_bridge/engine.py",
                                                   "android_bridge/boosters.py", "android_bridge/history.py",
                                                   "tools/android_headless/tests/test_contract.py", "tools/android_headless/check_bridge.py",
                                                   "android/ci/inspection_context_summary.py", "android/ci/inspection_canonical_summary.py",
                                                   "android/ci/inspection_identity_summary.py", "android/ci/inspection_links_summary.py",
                                                   "android/ci/market_summary.py")},
                   "all_three_reference_cases_matched": not args.lifecycle, "game_database_unchanged": True,
                   "complete_booster_lifecycle_shapes":99 if args.lifecycle else 0,
                   "worker_timeout_seconds":180})
    (args.output / "evidence.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "tests": result["tests_passed"], "host_only": True}))


if __name__ == "__main__":
    main()
