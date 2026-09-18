"""Run the production fit store through three processes without clearing data."""
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
evidence = root / "build/evidence"
package = "io.github.sussic.pyfa.dev"


def adb(*args, timeout=30):
    return subprocess.run(["adb", *args], capture_output=True, text=True,
                          check=True, timeout=timeout).stdout


assert adb("shell", "settings", "get", "global", "airplane_mode_on").strip() == "1"
assert f"package:{package}" in adb("shell", "pm", "list", "packages", package).splitlines()
prior_pids = {row["pid"] for row in json.loads((evidence / "startup-native.json").read_text(encoding="utf-8"))}
for name in ("performance", "contract"):
    prior_pids.add(json.loads((evidence / f"{name}-native.json").read_text(encoding="utf-8"))["pid"])
reports = []
for phase in ("prepare", "reopen_edit", "verify"):
    adb("shell", "am", "force-stop", package)
    path = f"/sdcard/Download/pyfa-b02-{phase}.json"
    adb("shell", "rm", "-f", path)
    output = adb("shell", "am", "instrument", "-w", "-r", "-e", "class",
                 "io.github.sussic.pyfa.PersistenceTest", "-e", "b02_phase", phase,
                 f"{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner", timeout=240)
    (evidence / f"persistence-{phase}-instrumentation.txt").write_text(output, encoding="utf-8")
    assert re.search(r"OK \(1 test\)", output), output[-6000:]
    assert "INSTRUMENTATION_CODE: -1" in output, output[-6000:]
    assert not re.search(r"FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=", output), output[-6000:]
    report = json.loads(adb("exec-out", "cat", path))
    assert report["pid"] not in prior_pids and report["task"] == "B02" and report["phase"] == phase
    prior_pids.add(report["pid"])
    reports.append(report)
    (evidence / f"persistence-{phase}-native.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
(evidence / "persistence-native.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
print("B02 passed in three separate processes with saved app data retained.")
