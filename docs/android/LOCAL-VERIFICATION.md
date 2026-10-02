# Explicit Windows verification

W02 demonstrated the complete Windows WHPX replacement: 78 gates (48 independent
reference/host, five build/package, 25 native), all inherited offline assertions,
raw validators and reviewed screenshots. [Receipt](evidence/w02-local.json) records
actual commits, earlier failed launcher attempts and retained evidence. B09.1
feature delivery is resumed under explicit user authorization; setup proof remains valid.

## Start and focused checks

Run from the repository root in PowerShell, with a clean committed checkout:

```powershell
./android/verify-local.ps1 -Action plan -Mode full
./android/verify-local.ps1 -Action start -Mode full
./android/verify-local.ps1 -Action start -Mode desktop -Gate history
./android/verify-local.ps1 -Action start -Mode desktop -Gate history_mutations
./android/verify-local.ps1 -Action start -Mode desktop -Gate resources
./android/verify-local.ps1 -Action start -Mode build
./android/verify-local.ps1 -Action start -Mode native
```

C01.1 extends the full plan to 93 gates: 52 reference/host, five build
and 36 native gates. Resource checks include fourteen original-desktop cases,
seven host tests, eight validator regressions and three native resource processes.
Native mode continues to run every inherited prerequisite.

Full mode runs every required desktop/reference/host gate before Gradle and the
emulator. Build mode runs both APKs, lint, signature and full data/license/ABI
inspection. The focused history pair is development evidence, not a full pass.
Native mode rebuilds/inspects and runs the entire native chain: later phases need
previous synthetic saved fits and cannot run against arbitrary device data.

B09.2 extends the required full plan to 88 gates: 50 reference/host, five build
and 33 native gates. It adds four prepare/restore pairs (eight actual processes)
for all 28 remaining-mutation cases/168 states, bringing the required native
execution count to 60 and required screenshots to 146. Each new phase is a
separate resumable gate; process restart, offline assertions and earlier gates
remain required. History diagnostics also accompany those phases. Requirements
are not passing results; follow STATUS for the actual tested revision.

The launcher reuses `.venv/headless`, `.venv/reference`, clean pinned
`build/reference-upstream`, JDK17, installed SDK, readelf and the Gradle wrapper.
Optional `-SdkPath`, `-JdkPath`, `-SdkManager` select existing installations.
Default SDK manager: `%LOCALAPPDATA%/Android/Sdk/cmdline-tools/22.0/bin/sdkmanager.bat`.
Installed command tools22 were verified against the official archive SHA256
`90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a`.
The shared image is `system-images;android-36;google_apis;x86_64` revision7.
Existing emulator36.2.12 and usable WHPX were reused. No CPU/RAM override is added.

Each native run owns a disposable Pixel2 AVD. Its verified name, emulator serial,
API36/x86_64 and offline settings bind all commands; attached phones are untouched.
Windows uses direct `am instrument` for the initial five assertions, rejecting
missing, duplicated, failed, skipped or incomplete runner events before producing
JUnit. This replaces the failed Windows UTP gRPC result channel; every actual
assertion and fresh-install/uninstall boundary remains. Linux retains Gradle UTP.
The later phase scripts preserve process restart and raw-value checks. The user
approved a Windows-only outer history deadline of 2400 seconds per prepare/restored
phase; Linux retains 900 seconds. All assertions, numerical tolerances, per-operation
limits and A10 requirements are unchanged. The original 900-second failure remains
recorded. The single diagnostic retry captures screenshots, process activity and
CPU observations every 30 seconds. Valid supplemental database timestamps
showed continued writes; the diagnostic stat format was corrected for future runs.

## Pause and resume

Start prints the absolute run directory. In a second PowerShell window, request
a pause using that exact path. Wait for the first command to return paused, then
resume from the repository root:

```powershell
./android/verify-local.ps1 -Action pause -Run 'C:/absolute/evidence/run-directory'
./android/verify-local.ps1 -Action resume -Run 'C:/absolute/evidence/run-directory'
```

Pause stops after the current gate, without interrupting an assertion or save.
The owned emulator stops and its writable test data is retained. Resume requires
the same clean commit/tree, skips completed gates and retries unfinished work.
A file lock rejects a concurrent resume. Both desktop and native boundary
pause/resume were executed; the native run resumed after performance without
replaying it. Ctrl+C is an interrupted failure, not a verified pause.

For a committed launcher repair **before any native gate passed**, explicit
`-AdoptLauncherFix` can reuse completed host/build results. It requires only the
three launcher files to differ, identical executed host/build function ASTs and
an identical plan. Every retained gate keeps its actual tested commit. Once
native work passed, changed test inputs need fresh applicable verification.
For a failed native mutation chain without a valid prerequisite snapshot,
`-RestartNative` archives prior raw evidence/JUnit/reviews, verifies the retained
APK hashes and rebuilds the entire native prerequisite chain. It permits only
reviewed launcher/reporting/diagnostic changes and the exact approved history
import/timeout expression while retaining host/build inputs and tested commits.
Do not use ordinary resume against a partially mutated test library.

## Summary-only recovery and fixture identity

A failed aggregate summary can be repaired without rerunning completed gates:

```powershell
./.venv/headless/Scripts/python.exe -I android/ci/summary_repair.py --run 'C:/absolute/evidence/run-directory'
```

Use only after diagnosing and authorizing the concrete correction. The helper
validates archived package evidence against original build logs, retained APKs,
source/database/library bytes and native reports, and preserves every failed run
snapshot. An unchanged summary commit cannot be retried. The fixture guard requires
reported hashes to match exact retained verified test-APK fixture bytes, and those
bytes to match the correct independent reference after CRLF-to-LF normalization
only. Content, other whitespace, missing fixtures and wrong hashes fail. Native
assertions, tolerances and A10 requirements remain unchanged. W02 retained its
original UTP/readiness/history failures and all three aggregate failures (missing
package report, contract normalized hash, then persistence normalized hash).
The final aggregate summary records its actual new tested commit separately
from the 77 reused results. No completed stage was replayed for these repairs.

## Evidence and required local result

Default evidence: `%LOCALAPPDATA%/PyfaAndroid/PyfaDevelopment/evidence/`, outside
OneDrive/git. Codex MSIX may resolve this through its Package LocalCache; use the
printed canonical path. Each run retains exact commit/tree, commands, exit codes,
timings, full logs, both APKs, lint/JUnit, raw reports, PNGs, source/data/tool and
emulator identities, plus file digests. It performs no automatic upload.
Successful runs remove their disposable AVD; paused/failed runs retain it.

Review every required screenshot; retain `screenshots-reviewed.json` with names,
hashes, observations and the tested commit. Then validate/publish the explicitly
local result, using the repository receipt URL for the delivery commit:

```powershell
./.venv/headless/Scripts/python.exe -I android/ci/report_local.py --run 'C:/absolute/evidence/run-directory' --receipt-url 'https://github.com/Sussic/Pyfa-android/blob/DELIVERY_COMMIT/docs/android/evidence/w02-local.json'
# Add --publish only after review and the commit has been pushed.
```

The reporter checks full completion, manifest/log hashes, successful latest
attempts, actual tested commits, source equivalence and screenshot review.
It publishes `local/full-verification`; it never creates an Actions success.
Delivery may reuse proof only when execution/product inputs remain identical;
permitted post-proof changes are the named reporting tests/code, instructions,
receipt/docs and manual workflow policy. Product/test changes require new proof.

## Hosted fallback and costs

Both workflow files retain `workflow_dispatch` as deliberate hosted fallbacks,
read-only permission, pinned tools/actions, concurrency, existing time limits,
one-day diagnostics and opt-in APK upload. Automatic PR triggers are retired only
after the local demonstration. PR #33 delivered B09.1 and setup to master on 2026-10-02; both hosted workflows
are now deliberate manual fallbacks on the default branch.
No release or scheduled job is added. No branch protection/rulesets were found;
no owner access step is currently required. If future rules require Actions names,
replace those names with `local/full-verification` after owner review, rather than
fabricating a hosted pass.

No runner service, paid platform or billing setting changed. Standard hosted
runners for public repositories are free; larger runners and storage over the
account allowance may incur charges ([GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
Manual fallback still uses hosted execution/storage. Local work uses ordinary
hardware, electricity/network and disk space; keep evidence only as needed.
Feature/ARM64/older-API/upgrade/phone usability acceptance remains separate.
