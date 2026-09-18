#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/evidence

collect_screenshots() {
  for name in home about about-landscape fit; do
    adb exec-out cat "/sdcard/Download/pyfa-a07-$name.png" > "build/evidence/$name.png"
  done
}

collect_diagnostics() {
  local result=$?
  set +e
  if [ "$result" -ne 0 ]; then
    collect_screenshots
    adb exec-out screencap -p > build/evidence/failure.png
    adb logcat -d -t 300 AndroidRuntime:E TestRunner:I python.stderr:W '*:S' > build/evidence/failure-logcat.txt
  fi
  exit "$result"
}
trap collect_diagnostics EXIT

# The app is installed by connectedDebugAndroidTest after networking is disabled.
adb shell cmd connectivity airplane-mode enable
adb shell svc wifi disable
adb shell svc data disable
test "$(adb shell settings get global airplane_mode_on | tr -d '\r')" = 1
adb shell pm list packages io.github.sussic.pyfa.dev > build/evidence/prior-install.txt
if grep -q '^package:io.github.sussic.pyfa.dev$' build/evidence/prior-install.txt; then
  echo 'Expected a fresh emulator with no prior app installation.' >&2
  exit 1
fi
adb shell getprop ro.build.fingerprint > build/evidence/device-fingerprint.txt
adb shell getprop ro.product.cpu.abi > build/evidence/device-abi.txt
adb shell getprop ro.build.version.sdk > build/evidence/device-api.txt
# Read the installed package metadata without invoking a second, graphical QEMU
# binary (which needs audio libraries even when asked only for its version).
cat "${ANDROID_HOME}/emulator/source.properties" > build/evidence/emulator-version.txt
sdkmanager --list_installed > build/evidence/sdk-packages.txt
timeout 8m ./gradlew --no-daemon --console=plain :app:connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.notClass=io.github.sussic.pyfa.PerformanceTest,io.github.sussic.pyfa.BridgeContractTest,io.github.sussic.pyfa.PersistenceTest
collect_screenshots
adb exec-out cat /sdcard/Download/pyfa-a07-engine.json > build/evidence/engine-native.json
adb exec-out cat /sdcard/Download/pyfa-a08-projection.json > build/evidence/projection-native.json
adb exec-out cat /sdcard/Download/pyfa-a09-command.json > build/evidence/command-native.json
python3 ci/measure-performance.py
python3 ci/check-contract.py
python3 ci/check-persistence.py
python3 ci/summarize-tests.py
