"""Bounded debug measurements on the already-offline CI emulator.

Normal startup runs have no instrumentation in the app process. Edit/PSS work
uses a separate instrumentation process after these launches; existing functional
JUnit checks run first on their own fresh installation.
"""
import json
from pathlib import Path
import re
import subprocess
import time

root = Path(__file__).resolve().parents[1]
evidence = root / "build/evidence"
package = "io.github.sussic.pyfa.dev"
component = f"{package}/io.github.sussic.pyfa.MainActivity"


def adb(*args, check=True, timeout=30):
    return subprocess.run(["adb", *args], capture_output=True, text=True,
                          check=check, timeout=timeout)


def offline():
    assert adb("shell", "settings", "get", "global", "airplane_mode_on").stdout.strip() == "1"


offline()
# AGP cleans up its connected-test installation. Require that instead of silently
# measuring an existing database as a first install.
assert f"package:{package}" not in adb("shell", "pm", "list", "packages", package).stdout.splitlines()
for apk in ("app/build/outputs/apk/debug/app-debug.apk",
            "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"):
    result = adb("install", "-t", str(root / apk), timeout=120)
    assert "Success" in result.stdout, result.stdout + result.stderr

launches = []
for index in range(5):
    offline()
    adb("shell", "am", "force-stop", package)
    adb("shell", "run-as", package, "rm", "-f", "files/a10-startup.json")
    started = time.perf_counter()
    result = adb("shell", "am", "start", "-W", "-n", component, timeout=120)
    assert "Status: ok" in result.stdout, result.stdout + result.stderr
    (evidence / f"startup-{index}-am-start.txt").write_text(result.stdout)
    deadline = time.monotonic() + 120
    while True:
        # shell-v2 propagates cat's failure while the file is absent; exec-out
        # may return success despite a failed remote command.
        receipt = adb("shell", "run-as", package, "cat", "files/a10-startup.json", check=False)
        if receipt.returncode == 0:
            sample = json.loads(receipt.stdout)  # app writes atomically
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Launch {index} did not draw a ready fit: {receipt.stderr}")
        time.sleep(0.1)
    sample["adb_request_to_receipt_ms"] = (time.perf_counter() - started) * 1000
    sample["sample"] = "first_install" if index == 0 else f"cold_process_{index}"
    assert sample["database_installed"] is (index == 0)
    assert sample["pid"] not in {prior["pid"] for prior in launches}
    assert sample["ready_draw_elapsed_ms"] > sample["engine_ready_elapsed_ms"]
    assert sample["process_to_ready_draw_ms"] > sample["engine_start_to_ready_ms"] > 0
    assert sample["memory"]["total_pss_kb"] > 0
    launches.append(sample)
    # Incremental receipts survive a later failure without claiming completion.
    (evidence / "startup-native.json").write_text(json.dumps(launches, indent=2) + "\n")
    print(f"{sample['sample']}: process-to-ready-draw {sample['process_to_ready_draw_ms']:.1f} ms", flush=True)

adb("shell", "am", "force-stop", package)
adb("shell", "rm", "-f", "/sdcard/Download/pyfa-a10-performance.json")
offline()
runner = adb("shell", "am", "instrument", "-w", "-r", "-e", "class",
             "io.github.sussic.pyfa.PerformanceTest",
             f"{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner", timeout=240)
(evidence / "performance-instrumentation.txt").write_text(runner.stdout + runner.stderr)
assert re.search(r"OK \(1 test\)", runner.stdout), runner.stdout[-6000:]
assert "INSTRUMENTATION_CODE: -1" in runner.stdout, runner.stdout[-6000:]
assert not re.search(r"FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=", runner.stdout), runner.stdout[-6000:]
report = json.loads(adb("exec-out", "cat", "/sdcard/Download/pyfa-a10-performance.json").stdout)
assert report["pid"] not in {sample["pid"] for sample in launches}
assert report["all_snapshots_matched_desktop"] is True
(evidence / "performance-native.json").write_text(json.dumps(report, indent=2) + "\n")
print("A10 native edit measurements and desktop comparisons passed.")
