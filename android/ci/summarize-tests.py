"""Reject empty/skipped native suites and print concise, retainable evidence."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
reports = sorted((root / "app/build/outputs/androidTest-results/connected").rglob("TEST-*.xml"))
if not reports:
    raise SystemExit("No instrumented JUnit report was produced")
tests = []
for report in reports:
    suite = ET.parse(report).getroot()
    for case in suite.iter("testcase"):
        if any(case.find(tag) is not None for tag in ("skipped", "failure", "error")):
            raise SystemExit(f"Native test did not pass: {case.attrib}")
        tests.append(f"{case.attrib['classname']}.{case.attrib['name']}")
required = {
    "io.github.sussic.pyfa.AppShellTest.offlineLaunchShowsHonestStatusAndNavigatesBack",
    "io.github.sussic.pyfa.AppShellTest.aboutSurvivesActivityRecreationAndLandscapeWithSystemBack",
    "io.github.sussic.pyfa.EngineParityTest.bundledEngineMatchesIndependentDesktopAmmunitionStatesOffline",
    "io.github.sussic.pyfa.EngineParityTest.projectedEffectsMatchDesktopAndRefreshAllRecipientsOffline",
}
if not required.issubset(tests):
    raise SystemExit(f"Required native assertions missing: {sorted(required - set(tests))}")
apk = root / "app/build/outputs/apk/debug/app-debug.apk"
evidence = root / "build/evidence"
screenshots = {}
for name in ("home", "about", "about-landscape", "fit"):
    data = (evidence / f"{name}.png").read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR" or len(data) < 33:
        raise SystemExit(f"Missing or invalid Android screenshot: {name}")
    width, height = struct.unpack(">II", data[16:24])
    if not width or not height:
        raise SystemExit(f"Empty Android screenshot: {name}")
    screenshots[name] = {"width": width, "height": height, "sha256": hashlib.sha256(data).hexdigest()}
engine = json.loads((evidence / "engine-native.json").read_text())
contents = json.loads((evidence / "apk-contents.json").read_text())
assert engine["database_sha256"] == contents["database_sha256"]
assert engine["engine_source_sha256"] == contents["engine_source_sha256"]
assert engine["readonly_database"] and not engine["desktop_import_attempts"]
assert set(engine["states"]) == {"initial", "iron_ammunition", "restored"}
assert all(len(stats) == 38 for stats in engine["states"].values())
projection = json.loads((evidence / "projection-native.json").read_text())
for key in ("database_sha256", "database_logical_sha256", "engine_source_sha256", "source_data_sha256",
            "desktop_source_commit", "dataset_metadata"):
    assert projection[key] == engine[key], key
assert not projection["desktop_import_attempts"]
assert projection["same_worker_repeat_matched"] and projection["ammunition_after_projection_matched"]
assert len(projection["states"]) == 11
assert all(set(pair) == {"source", "target"} and all(len(stats) == 39 for stats in pair.values())
           for pair in projection["states"].values())
assert len(projection["multi_recipient"]) == 9 and len(projection["repeated_cycles"]) == 5
summary = {
    "task": "A08",
    "checkout_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "workflow_run": os.environ.get("GITHUB_RUN_ID"),
    "tests": tests,
    "screenshots": screenshots,
    "device": {name: (evidence / f"device-{name}.txt").read_text().strip() for name in ("fingerprint", "abi", "api")},
    "fresh_install": True,
    "airplane_mode": True,
    "app_internet_permission": False,
    "apk_bytes": apk.stat().st_size,
    "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
    "engine_packaged": True,
    "engine_parity_tested": "A01: 38 statistics across three ammunition states",
    "projection_parity_tested": "A04: 39 statistics per fit, two fits, 11 states; two recipients, nine phases, five apply/remove cycles; same-worker repeat",
    "projection_sequence_ms": projection["projection_sequence_ms"],
    "projection_repeat_sequence_ms": projection["repeat_sequence_ms"],
    "arm64_contents_verified": "arm64-v8a" in contents["abis"],
    "arm64_runtime_tested": False,
    "python_dependencies": engine["dependencies"],
    "engine_boot_ms": engine["boot_ms"],
    "edit_sequence_ms": engine["edit_sequence_ms"],
}
(evidence / "native-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
        stream.write("### Offline Android EOS\n\n")
        stream.write(f"{len(tests)} native tests passed on API {summary['device']['api']} / {summary['device']['abi']}.\n\n")
        stream.write("Fresh offline install; no Internet permission. A01's 38 raw statistics pass in three ammunition states. ARM64 APK contents verified; ARM64 execution untested.\n\n")
        stream.write("A04 projections: 39 raw statistics per fit across 11 states; multiple-recipient invalidation, link cleanup and repeated removal pass.\n\n")
        stream.write(f"APK: {summary['apk_bytes']} bytes; SHA-256 `{summary['apk_sha256']}`.\n")
