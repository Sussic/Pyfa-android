# Explicit Windows verification

W02 ports the complete native launcher to Windows WHPX while retaining the same
independent desktop/host scripts and native validators. Demonstration is pending;
hosted workflows remain in place until actual full local results and screenshot
review establish their replacement. See [task](tasks/W02-windows-local-verification.md).

Run from this repository root in PowerShell with a clean, committed checkout.
The prepared launcher reuses `.venv/headless`, `.venv/reference`, the clean pinned
`build/reference-upstream`, JDK17, the existing SDK, readelf and the Gradle wrapper.
Optional `-SdkPath`, `-JdkPath` and `-SdkManager` select existing installations.
The default SDK manager is the checksum-verified Windows command tools in
`build/tools/android-command-tools/cmdline-tools/bin/sdkmanager.bat`.

The emulator requires `system-images;android-36;google_apis;x86_64`, the same API,
tag and ABI as the hosted suite. Installed shared images are reused; each native
run creates its own Pixel2 AVD under its run directory. WHPX must report usable.
No CPU/RAM limit is supplied. A specific `ANDROID_SERIAL` and the AVD identity
bind every command to this disposable emulator; attached phones are untouched.

## Start and focused checks

```powershell
./android/verify-local.ps1 -Action plan -Mode full
./android/verify-local.ps1 -Action start -Mode full
```

Full verification runs all independent reference and host gates first, then APKs,
lint/signature/package inspection, then every offline native gate and the existing
raw-result summary. Timed host suites never overlap Gradle or emulator work.
All native process-restart boundaries and per-phase limits remain in their existing
scripts. The final summary still rejects missing, failed and skipped assertions.

```powershell
./android/verify-local.ps1 -Action start -Mode desktop -Gate history
./android/verify-local.ps1 -Action start -Mode build
./android/verify-local.ps1 -Action start -Mode native
```

The focused desktop pair compares the original command exporter and headless
history regression against the pinned bundled dataset. It is explicitly a focused
result, not a full-suite pass. Native mode rebuilds/inspects and runs the complete
native chain, since later phases require earlier synthetic saved fits. It does not
run an invalid isolated late phase against arbitrary device data.

## Pause and resume

The start command prints the absolute evidence path. Use that exact path:

```powershell
./android/verify-local.ps1 -Action pause -Run 'C:/absolute/evidence/run-directory'
./android/verify-local.ps1 -Action resume -Run 'C:/absolute/evidence/run-directory'
```

Pause requests stop after the current gate completes; they do not interrupt a
save or drop a required phase. The disposable emulator stops, with its writable
app data retained for explicit resume. Resume requires the same clean commit and
tree, skips confirmed completed gates and retries only the failed/unfinished gate.
Interrupted work is never marked passed. Do not use Ctrl+C as a successful pause;
it records an interrupted failure. A file lock prevents two processes sharing a run.

## Evidence and delivery

The default root is `%LOCALAPPDATA%/PyfaAndroid/PyfaDevelopment/evidence/`, outside
OneDrive and git. Each unique run contains `run.json` (exact commit/tree, commands,
exit codes and timings), full per-gate logs, APK copies, native raw reports, PNGs,
JUnit/lint results, emulator/image identity and `files.json` digests. It does not
upload them automatically. Successful native runs remove their disposable AVD;
failed/paused runs retain it for explicit recovery. Keep the reviewed evidence
receipt in the repository, without credentials or personal fitting data.

Passing commands do not replace screenshot review. Review every required screen
and record filenames/digests, observations and the exact tested commit before
publishing a local result or merging. Local result reporting must use an explicit
local context; no hosted Actions name or run can be relabelled passed.

Hosted retirement and any owner-only required-check configuration change remain
pending the demonstrated replacement. No runner service, paid service, release or
phone installation is part of this setup. Billing/spending settings remain unchanged.
