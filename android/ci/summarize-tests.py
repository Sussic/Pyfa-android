"""Reject empty/skipped native suites and print concise, retainable evidence."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import xml.etree.ElementTree as ET
from performance_summary import summarize
from contract_summary import summarize as summarize_contract
from persistence_summary import summarize as summarize_persistence
from library_summary import summarize as summarize_library

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
    "io.github.sussic.pyfa.EngineParityTest.commandBurstsMatchDesktopAndClearRecipientBonusesOffline",
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
command = json.loads((evidence / "command-native.json").read_text())
for key in ("database_sha256", "database_logical_sha256", "engine_source_sha256", "source_data_sha256",
            "desktop_source_commit", "dataset_metadata"):
    assert command[key] == engine[key], key
assert not command["desktop_import_attempts"]
assert command["same_worker_repeat_matched"] and command["ammunition_after_command_matched"]
assert command["projection_after_command_matched"]
assert len(command["states"]) == 19
assert all(set(pair) == {"source", "target"} and all(len(stats) == 39 for stats in pair.values())
           for pair in command["states"].values())
assert len(command["multi_recipient"]) == 18 and len(command["repeated_cycles"]) == 5
assert len(command["pending_command_bonuses"]) == 112
assert all(type(count) is int and count == 0 for count in command["pending_command_bonuses"].values())
performance = summarize(
    json.loads((evidence / "startup-native.json").read_text()),
    json.loads((evidence / "performance-native.json").read_text()), engine,
)
contract = summarize_contract(json.loads((evidence / "contract-native.json").read_text()), engine)
persistence = summarize_persistence(json.loads((evidence / "persistence-native.json").read_text(encoding="utf-8")), engine)
from navigation_summary import summarize as summarize_navigation
from market_summary import summarize as summarize_market
from empty_hull_summary import summarize as summarize_empty_hulls
from module_edit_summary import summarize as summarize_module_edits
from charge_edit_summary import summarize as summarize_charge_edits
from variation_edit_summary import summarize as summarize_variation_edits
from rack_ordering_summary import summarize as summarize_rack_ordering
from bulk_charge_summary import summarize as summarize_bulk_charges
from bulk_state_summary import summarize as summarize_bulk_states
from clone_fill_summary import summarize as summarize_clone_fill
from bulk_variation_removal_summary import summarize as summarize_bulk_variation_removal
from hull_mode_summary import summarize as summarize_hull_modes
from subsystem_summary import summarize as summarize_subsystems
summary = {
    "task": "B06.2",
    "subsystems": summarize_subsystems(json.loads((evidence / "subsystems-native.json").read_text(encoding="utf-8")), engine),
    "hull_modes": summarize_hull_modes(json.loads((evidence / "hull-modes-native.json").read_text(encoding="utf-8")), engine),
    "bulk_variation_removal": summarize_bulk_variation_removal(json.loads((evidence / "bulk-variation-removal-native.json").read_text(encoding="utf-8")), engine),
    "clone_fill": summarize_clone_fill(json.loads((evidence / "clone-fill-native.json").read_text(encoding="utf-8")), engine),
    "bulk_states": summarize_bulk_states(json.loads((evidence / "bulk-states-native.json").read_text(encoding="utf-8")), engine),
    "bulk_charges": summarize_bulk_charges(json.loads((evidence / "bulk-charges-native.json").read_text(encoding="utf-8")), engine),
    "rack_ordering": summarize_rack_ordering(json.loads((evidence / "rack-ordering-native.json").read_text(encoding="utf-8")), engine),
    "variation_edits": summarize_variation_edits(json.loads((evidence / "variation-edits-native.json").read_text(encoding="utf-8")), engine),
    "charge_edits": summarize_charge_edits(json.loads((evidence / "charge-edits-native.json").read_text(encoding="utf-8")), engine),
    "module_edits": summarize_module_edits(json.loads((evidence / "module-edits-native.json").read_text(encoding="utf-8")), engine),
    "empty_hulls": summarize_empty_hulls(json.loads((evidence / "empty-hulls-native.json").read_text(encoding="utf-8")), engine),
    "market": summarize_market(json.loads((evidence / "market-native.json").read_text(encoding="utf-8")), engine),
    "navigation": summarize_navigation(json.loads((evidence / "navigation-native.json").read_text(encoding="utf-8"))),
    "library": summarize_library(json.loads((evidence / "library-native.json").read_text(encoding="utf-8"))),
    "persistence_test": "io.github.sussic.pyfa.PersistenceTest",
    "persistence": persistence,
    "contract_test": "io.github.sussic.pyfa.BridgeContractTest.typedOperationsMatchDesktopAndPreserveCommittedRevisionsOffline",
    "contract": contract,
    "checkout_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "workflow_run": os.environ.get("GITHUB_RUN_ID"),
    "tests": tests,
    "performance_test": "io.github.sussic.pyfa.PerformanceTest.repeatedEditsMatchDesktopWithStableFitCountOffline",
    "performance": performance,
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
    "command_parity_tested": "A05: 39 statistics per fit, two fits, 19 states; two recipients, 18 phases, five apply/remove cycles; 112 empty pending-bonus observations; same-worker repeat",
    "command_sequence_ms": command["command_sequence_ms"],
    "command_repeat_sequence_ms": command["repeat_sequence_ms"],
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
        stream.write("A05 commands: 39 raw statistics per fit across 19 states; skills, mindlink, module/charge edits, all recipients, link removal and pending-bonus cleanup pass.\n\n")
        stream.write(f"APK: {summary['apk_bytes']} bytes; SHA-256 `{summary['apk_sha256']}`.\n")

if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
        stream.write("\nA10: five normal startup samples and a separate native test comparing 120 timed edits to desktop fixtures. Raw measurements and process-memory snapshots retained.\n")

if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
        stream.write("\nB01: a separate native typed-contract test validates 63 desktop snapshots, raw scalar types/units, atomic rejection, revisions and queued edits. Complete responses retained.\n")

if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
        stream.write("\nB02: three separate native processes retain fit identities, revisions, inputs and projection/command links; 45 snapshots match independent desktop values after saves and restarts. App data remains intact between phases.\n")
