# Explicit Windows verification

W02 ports the complete native launcher to Windows WHPX while retaining the same
independent desktop/host scripts and native validators. The current run passes
76 of 78 gates: all 48 desktop/reference/host gates, five build/package gates,
and native initial through notes. History hit its 900-second phase timeout;
the final summary has not run. Complete demonstration is pending;
hosted workflows remain in place until actual full local results and screenshot
review establish their replacement. See [task](tasks/W02-windows-local-verification.md).

Run from this repository root in PowerShell with a clean, committed checkout.
The prepared launcher reuses `.venv/headless`, `.venv/reference`, the clean pinned
`build/reference-upstream`, JDK17, the existing SDK, readelf and the Gradle wrapper.
Optional `-SdkPath`, `-JdkPath` and `-SdkManager` select existing installations.
The default SDK manager is the checksum-verified Windows command tools 22 in
`%LOCALAPPDATA%/Android/Sdk/cmdline-tools/22.0/bin/sdkmanager.bat`.

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
All native process-restart boundaries and assertions remain in their existing
scripts. The user approved a Windows-only history phase-budget increase from 900
to 2400 seconds and one diagnostic retry; Linux retains 900 seconds. The final
summary still rejects missing, failed and skipped assertions.

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

The start command prints the absolute evidence path. Request pause from a second
PowerShell window, wait for the running command to return with `paused`, then
resume using that exact path:

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
Do not resume a failed mutation phase against partially changed synthetic data.
The current failed history phase requires a fresh native chain. The approved
`-RestartNative` recovery preserves the failed evidence, verifies retained APK
hashes, reuses unchanged host/build results and reconstructs the native prerequisites.
The history retry captures read-only progress every 30 seconds. If it fails, stop
and report the evidence; do not increase the timeout or retry again.

## Evidence and delivery

The default root is `%LOCALAPPDATA%/PyfaAndroid/PyfaDevelopment/evidence/`, outside
OneDrive and git. Each unique run contains `run.json` (exact commit/tree, commands,
exit codes and timings), full per-gate logs, APK copies, native raw reports, PNGs,
JUnit/lint results, emulator/image identity and `files.json` digests. It does not
upload them automatically. Successful native runs remove their disposable AVD;
failed/paused runs retain it for explicit recovery. Keep the reviewed evidence
receipt in the repository, without credentials or personal fitting data.
In the Codex Windows app the printed absolute path may resolve through its MSIX
`Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local` directory. Retain and use that
printed path; it is still outside the synced checkout.

Passing commands do not replace screenshot review. Review every required screen
and record filenames/digests, observations and the exact tested commit before
publishing a local result or merging. Local result reporting must use an explicit
local context; no hosted Actions name or run can be relabelled passed.

The local reporter and its 20 regression tests are prepared; no success status
has been published. The reporting checks can run independently:

```powershell
./.venv/headless/Scripts/python.exe -m unittest discover -s android/ci -p test_report_local.py -v
```

After a genuinely complete run, record `screenshots-reviewed.json` with the tested
commit and every native PNG's SHA-256, review flag and observation. The reporter
rejects incomplete runs, changed evidence, unreviewed images and unsupported
revision reuse. Preview its result before deliberately adding `--publish`:

```powershell
./.venv/headless/Scripts/python.exe android/ci/report_local.py --run 'C:/absolute/evidence/run-directory' --receipt-url 'https://github.com/Sussic/Pyfa-android/blob/COMMIT/docs/android/evidence/w02-local.json'
```

Replace `COMMIT` with the real committed receipt revision. The reporter currently
cannot accept the failed W02 run, and the final receipt does not yet exist.

Hosted retirement and any owner-only required-check configuration change remain
pending the demonstrated replacement. No runner service, paid service, release or
phone installation is part of this setup. Billing/spending settings remain unchanged.
After verified setup delivery, stop. PR #33/B09.1 delivery and B09.2 remain the
next roadmap work for a later explicit instruction.
