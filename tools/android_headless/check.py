#!/usr/bin/env python3
"""Verify A03/A04 against pinned desktop fixtures without desktop packages/networking."""

import argparse
import hashlib
import importlib.abc
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import canonical, compare, digest_file, logical_database_digest

DEPENDENCIES = {"logbook": "1.7.0.post0", "sqlalchemy": "1.4.50", "greenlet": "3.0.3"}
FORBIDDEN_PACKAGES = ("wxPython", "numpy", "cryptography", "pyyaml", "pillow")
FORBIDDEN_IMPORTS = {"wx", "gui", "service", "config"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


class NoDesktop(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempts = []

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in FORBIDDEN_IMPORTS:
            self.attempts.append(fullname)
            raise ImportError("Headless check forbids desktop import: " + fullname)


def worker(args):
    guard = NoDesktop()
    sys.meta_path.insert(0, guard)
    network_attempts = []

    def block_network(event, arguments):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            network_attempts.append(event)
            raise RuntimeError("Network is disabled during the headless calculation")

    sys.addaudithook(block_network)
    from android_bridge import HeadlessEngine
    test_file = "test_projection.py" if args.scenario == "projection" else "test_engine.py"
    spec = importlib.util.spec_from_file_location("headless_engine_tests", Path(__file__).parent / "tests" / test_file)
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    engine = HeadlessEngine(args.database)
    expected = read_json(args.expected)
    # Scenario inputs are independent of the expected numeric values.
    case = read_json(ROOT / "tools/android_reference" / ("projection.json" if args.scenario == "projection" else "vexor.json"))
    compare(expected["inputs"], case, "case_definition")
    states = tests.sample(engine, case)
    compare(expected["states"], states, args.scenario + "_states")
    compare(expected["dataset_metadata"], engine.metadata, "dataset_metadata")
    compare(expected["eos_settings"], engine.settings, "eos_settings")
    compare(expected["resolved_item_ids"], engine.resolved_item_ids, "resolved_item_ids")
    result = {"states": states, "dataset_metadata": engine.metadata,
              "resolved_item_ids": dict(engine.resolved_item_ids), "eos_settings": engine.settings}
    test_count = 0
    if args.worker == "tests":
        tests.ENGINE, tests.EXPECTED = engine, expected
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.EngineTests)
        run = unittest.TextTestRunner(verbosity=2).run(suite)
        if not run.wasSuccessful() or run.skipped or run.expectedFailures:
            raise RuntimeError("Headless behavioral tests failed or skipped")
        test_count = run.testsRun
    if guard.attempts or network_attempts:
        raise RuntimeError(f"Forbidden operations were attempted: {guard.attempts}, {network_attempts}")
    imported = {}
    for name, module in list(sys.modules.items()):
        if name.split(".")[0] in FORBIDDEN_IMPORTS:
            raise RuntimeError("Unexpected loaded desktop module: " + name)
        if name.split(".")[0] in {"eos", "utils", "android_bridge"} and getattr(module, "__file__", None):
            imported[name] = Path(module.__file__).resolve().relative_to(ROOT).as_posix()
    result["isolation"] = {"desktop_import_attempts": guard.attempts,
                           "network_attempts": network_attempts, "loaded_engine_modules": imported}
    result["tests_passed"] = test_count
    write_json(args.output, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--scenario", choices=("ammunition", "projection"), default="ammunition")
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New directory outside the development checkout")
    parser.add_argument("--worker", choices=("tests", "repeat"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.database = args.database.resolve(strict=True)
    case_name = "projection.json" if args.scenario == "projection" else "vexor.json"
    args.expected = (args.expected or ROOT / "tools/android_reference/fixtures" / case_name).resolve(strict=True)
    args.output = args.output.resolve()
    if sys.version_info[:2] != (3, 11):
        raise ValueError("Host comparisons use Python 3.11")
    versions = {name: importlib.metadata.version(name) for name in DEPENDENCIES}
    compare(DEPENDENCIES, versions, "headless_dependencies")
    for name in FORBIDDEN_PACKAGES:
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        raise ValueError("Use a clean headless environment without " + name)
    if args.worker:
        worker(args)
        return
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError("Output must be outside the checkout and must not contain the source database")
    expected = read_json(args.expected)
    database_hash = digest_file(args.database)
    logical_hash = logical_database_digest(args.database)
    compare(expected["database_logical_sha256"], logical_hash, "A01_database")
    args.output.mkdir(parents=True, exist_ok=False)
    for mode in ("tests", "repeat"):
        with (args.output / (mode + ".log")).open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()),
                            "--database", str(args.database), "--expected", str(args.expected),
                            "--output", str(args.output / (mode + ".json")), "--worker", mode,
                            "--scenario", args.scenario],
                           check=True, stdout=log, stderr=subprocess.STDOUT,
                           cwd=args.output, timeout=120)
    result = read_json(args.output / "tests.json")
    repeat = read_json(args.output / "repeat.json")
    for key in ("states", "dataset_metadata", "resolved_item_ids", "eos_settings", "isolation"):
        compare(result[key], repeat[key], "fresh_process." + key)
    compare(database_hash, digest_file(args.database), "unchanged_database_bytes")
    paths = sorted({p for directory in ("eos", "utils", "android_bridge", "tools/android_headless", "tools/android_reference")
                    for p in (ROOT / directory).rglob("*.py")})
    source_manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(
        p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in paths}
    evidence = {
        "python": platform.python_version(), "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
        "dependencies": versions, "absent_desktop_packages": list(FORBIDDEN_PACKAGES),
        "adapter_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        # Ignore the independent checkout nested by CI; the manifest separately
        # identifies the exact adapter/engine/check sources, including new files.
        "tracked_worktree_dirty": bool(subprocess.check_output([
            "git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"], text=True).strip()),
        "source_manifest_sha256": hashlib.sha256(canonical(source_manifest)).hexdigest(),
        "reference_source_commit": expected["source_commit"],
        "source_data_sha256": expected["source_data_sha256"],
        "reference_fixture_sha256": hashlib.sha256(args.expected.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "database_logical_sha256": logical_hash, "database_sha256": database_hash,
        "scenario": args.scenario,
        "scenario_sha256": hashlib.sha256((ROOT / "tools/android_reference" / case_name).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "stats_per_fit": len(result["states"]["initial"]["target"] if args.scenario == "projection" else result["states"]["initial"]),
        "fits_per_state": 2 if args.scenario == "projection" else 1, "states": len(result["states"]),
        "behavioral_tests_passed": result["tests_passed"],
        "checks": {("A04_comparison" if args.scenario == "projection" else "A01_comparison"): True,
                   "fresh_process_repeat": True, "no_desktop_imports": True,
                   "no_network_operations": True, "game_database_unchanged": True},
        "desktop_import_attempts": result["isolation"]["desktop_import_attempts"],
        "network_attempts": result["isolation"]["network_attempts"],
        "engine_modules_loaded": len(result["isolation"]["loaded_engine_modules"]),
        "android_runtime_tested": False,
    }
    write_json(args.output / "source-manifest.json", source_manifest)
    write_json(args.output / "evidence.json", evidence)
    print(json.dumps({"result": "PASS", "tests": result["tests_passed"], "checks": evidence["checks"]}))


if __name__ == "__main__":
    main()
