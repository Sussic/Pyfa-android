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
}
if not required.issubset(tests):
    raise SystemExit(f"Required native assertions missing: {sorted(required - set(tests))}")
apk = root / "app/build/outputs/apk/debug/app-debug.apk"
evidence = root / "build/evidence"
screenshots = {}
for name in ("home", "about", "about-landscape"):
    data = (evidence / f"{name}.png").read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR" or len(data) < 33:
        raise SystemExit(f"Missing or invalid Android screenshot: {name}")
    width, height = struct.unpack(">II", data[16:24])
    if not width or not height:
        raise SystemExit(f"Empty Android screenshot: {name}")
    screenshots[name] = {"width": width, "height": height, "sha256": hashlib.sha256(data).hexdigest()}
summary = {
    "task": "A06",
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
    "engine_packaged": False,
    "engine_parity_tested": False,
}
(evidence / "native-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
        stream.write("### Android skeleton\n\n")
        stream.write(f"{len(tests)} native tests passed on API {summary['device']['api']} / {summary['device']['abi']}.\n\n")
        stream.write("Fresh install with airplane mode enabled; app has no Internet permission. EOS is not packaged or tested yet.\n\n")
        stream.write(f"APK: {summary['apk_bytes']} bytes; SHA-256 `{summary['apk_sha256']}`.\n")
