#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/evidence

collect_diagnostics() {
  local result=$?
  set +e
  for name in home about about-landscape; do
    adb exec-out run-as io.github.sussic.pyfa.dev cat "files/a06-screenshots/$name.png" > "build/evidence/$name.png"
    if [ ! -s "build/evidence/$name.png" ]; then rm -f "build/evidence/$name.png"; fi
  done
  if [ "$result" -ne 0 ]; then
    adb exec-out screencap -p > build/evidence/failure.png
    adb logcat -d -t 300 AndroidRuntime:E TestRunner:I '*:S' > build/evidence/failure-logcat.txt
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
timeout 8m ./gradlew --no-daemon --console=plain :app:connectedDebugAndroidTest
python3 ci/summarize-tests.py
