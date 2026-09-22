"""Four offline B03.2 processes, retaining all earlier fit and navigation data."""
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
evidence = root / "build/evidence"
package = "io.github.sussic.pyfa.dev"


def adb(*args, timeout=30):
    return subprocess.run(["adb", *args], capture_output=True, text=True, check=True, timeout=timeout).stdout


assert adb("shell", "settings", "get", "global", "airplane_mode_on").strip() == "1"
assert f"package:{package}" in adb("shell", "pm", "list", "packages", package).splitlines()
prior = {row["pid"] for row in json.loads((evidence / "library-native.json").read_text())}
reports = []
for phase in ("prepare", "restored", "disabled", "closed"):
    adb("shell", "am", "force-stop", package)
    path = f"/sdcard/Download/pyfa-b032-{phase}.json"
    adb("shell", "rm", "-f", path)
    output = adb("shell", "am", "instrument", "-w", "-r", "-e", "class",
        "io.github.sussic.pyfa.LibraryNavigationTest", "-e", "b032_phase", phase,
        f"{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner", timeout=240)
    (evidence / f"navigation-{phase}-instrumentation.txt").write_text(output, encoding="utf-8")
    assert re.search(r"OK \(1 test\)", output), output[-6000:]
    assert "INSTRUMENTATION_CODE: -1" in output, output[-6000:]
    assert not re.search(r"FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=", output), output[-6000:]
    report = json.loads(adb("exec-out", "cat", path))
    assert report["pid"] not in prior
    prior.add(report["pid"])
    reports.append(report)
    (evidence / f"navigation-{phase}-native.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name in {"prepare": ("recent", "hull", "open"), "restored": ("closed",), "disabled": (), "closed": ()}[phase]:
        png = subprocess.check_output(["adb", "exec-out", "cat", f"/sdcard/Download/pyfa-b032-{name}.png"], timeout=30)
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        (evidence / f"navigation-{name}.png").write_bytes(png)
(evidence / "navigation-native.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
from navigation_summary import summarize
print(json.dumps(summarize(reports), indent=2))
