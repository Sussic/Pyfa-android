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
./android/verify-local.ps1 -Action start -Mode desktop -Gate capacitor
./android/verify-local.ps1 -Action start -Mode desktop -Gate tank
./android/verify-local.ps1 -Action start -Mode desktop -Gate output
./android/verify-local.ps1 -Action start -Mode build
./android/verify-local.ps1 -Action start -Mode native
```

C02 extends the required plan to 109 gates: 60 reference/host, five build and
44 native gates (71 actual native test executions). Output adds37 independent
original wx/EOS cases and two persistent native phases;268 synthetic saved fits
and191 required screenshots retain all inherited acceptance checks. These are
requirements until the exact-commit receipt records execution and visual review.
The output focused pair covers calculations, target-profile history, failed-save
atomicity, copy and fresh-process persistence. Native phases retain their existing
900-second deadlines; the approved history-only Windows timeout is unchanged.

C01.3.2 extends the required plan to 105 gates: 58 reference/host, five build
and 42 native gates. Tank adds29 original desktop cases,21 focused
fixture/summary/transport regressions and two persistent native phases.
All prior gates remain required. These counts describe the required plan;
STATUS and the exact-commit receipt record actual execution.

C01.3.1 extended the required plan to 101 gates: 56 reference/host, five build
and 40 native gates. Defenses add fourteen original desktop cases, four individual
incoming-contribution witnesses, twenty-two fixture/schema/transport regressions
and separate native prepare/restored processes. Every inherited check remains.
For focused development, use `./android/verify-local.ps1 -Action start -Mode desktop -Gate defenses`.
Full delivery still requires `./android/verify-local.ps1 -Action start -Mode full`,
the reviewed screenshots and truthful exact-head local status. Existing pause/resume
commands apply to this run; no hosted dispatch is implied.

C01.2 extended the required plan to 97 gates: 54 reference/host, five build
and 38 native gates. Capacitor checks add twelve original desktop cases, ten
raw/fixture validator tests and two separate native prepare/restored processes.
These are requirements; STATUS records actual completed verification.

C01.1 extended the full plan to 93 gates: 52 reference/host, five build
and 36 native gates. Resource checks include fourteen original-desktop cases,
seven host tests, eleven validator regressions and three native resource processes.
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

The C02 profile-number/editor repair is an exact exception for the failed
`31cb2859` output-prepare run. The same `-RestartNative` command archives its
APKs, native evidence and actual commit stamps, retains only60 unchanged
reference/host gates, then rebuilds all five build/package gates and runs all44
native gates on a fresh disposable store. SHA256 guards accept only the reviewed
three Kotlin files and scoped launcher/reporting changes; engine, fixtures,
assertion removal and unrelated differences fail. This does not reuse native
results from an older application APK or claim an unexecuted hosted check.

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

## C01.1 edited resource reference

The direct fourteen-case resource fixture stays unchanged. Offline guns edited
through the original desktop service includes vacant slots; those can change EOS
zero scalar kinds without changing their values. The separately verified witness
is `resources-edited.json`; native preparation compares its exact physical slots,
raw kinds/values, units and displays. Reuse its receipt for unchanged reference
inputs. When changing resource/edit inputs, regenerate/check it independently:

```powershell
. ./build/windows-env.ps1
& $pyfaReference -I tools/android_reference/resources_edited.py --source build/reference-upstream --database android/build/engine/assets/engine/eve.db --output 'C:/absolute/new-reference-directory' --check tools/android_reference/fixtures/resources-edited.json
& $pyfaHeadless -I android/ci/test_resource_summary.py
```

A changed or added test fixture requires the engine-assets stage before Gradle:
use the complete build mode, then native/full verification as appropriate. Do not
reuse old staged assets merely because the application source stayed unchanged.
C01.1 retained 90 valid gates, three exact partial-store recoveries, every complete
native failure log and a missing-witness package failure; only affected builds and
prepare/restored/summary reran. Its receipt explicitly records the unavailable
first optional shared failure PNG/logcat. Required passing artifacts remain intact.

## Focused C01.3.2 tank checks

Use a fresh external directory for each reference or host evidence attempt:

```powershell
. ./build/windows-env.ps1
& $pyfaReference -I tools/android_reference/tank.py --source build/reference-upstream --database android/build/engine/assets/engine/eve.db --output 'C:/absolute/new-tank-reference-directory' --check tools/android_reference/fixtures/tank.json
& $pyfaHeadless -I tools/android_headless/check_tank.py --source build/reference-upstream --database android/build/engine/assets/engine/eve.db --output 'C:/absolute/new-tank-host-directory'
& $pyfaHeadless -I android/ci/test_tank_summary.py
```

The full launcher includes both tank phases after defenses, preserving all189
prior fits and their inputs/types, and restoring all230 fits in a new process.
Review its actual tank screenshots alongside every inherited screenshot.
Focused checks do not replace the full delivery suite or screenshot review.
