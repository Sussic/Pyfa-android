"""Run B01 alone after the unchanged A10 measurement process has stopped."""
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
adb("shell", "am", "force-stop", package)
path = "/sdcard/Download/pyfa-b01-contract.json"
adb("shell", "rm", "-f", path)
output = adb("shell", "am", "instrument", "-w", "-r", "-e", "class",
             "io.github.sussic.pyfa.BridgeContractTest",
             f"{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner", timeout=240)
(evidence / "contract-instrumentation.txt").write_text(output)
assert re.search(r"OK \(1 test\)", output), output[-6000:]
assert "INSTRUMENTATION_CODE: -1" in output, output[-6000:]
assert not re.search(r"FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=", output), output[-6000:]
report = json.loads(adb("exec-out", "cat", path))
prior_pids = {row["pid"] for row in json.loads((evidence / "startup-native.json").read_text())}
prior_pids.add(json.loads((evidence / "performance-native.json").read_text())["pid"])
assert report["pid"] not in prior_pids
assert report["task"] == "B01"
(evidence / "contract-native.json").write_text(json.dumps(report, indent=2) + "\n")
print("B01 isolated native contract test passed; raw response evidence retained.")
