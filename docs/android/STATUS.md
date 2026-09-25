# Android project status

Updated: 2026-09-25. **B05.2 delivered. Next: B05.3 — Clone and fill modules.**

## Authorized work and latest delivery

- Explicit chat confirmation authorizes sequential eligible approved roadmap
  tasks, one outcome at a time through review/checks/PR merge, then automatic
  continuation. No releases, phone installs, billing changes, unrelated work or
  delegation. The goal remains active; no decision or access blocks the next task.
- **B05.1 delivered** in [PR #22](https://github.com/Sussic/Pyfa-android/pull/22), merge
  `18de3c72eea047aaa0f94ec4a809e34b79665b6d`, tested head `b031c985be5acfcf79e3b06c45079b0ea11564a0`.
  Select modules/reference and change ammunition with explicit selection-only or
  all-similar scopes. Exact target/skipped previews retain desktop asymmetric
  compatibility and related-variant grouping. EOS, serialized work, atomic saves,
  recipient updates and recent-item history remain unchanged.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35944859296)
  passes **120 host tests**, independent references/repeats and migration in
  **18m22s**. Local full validation passes **26 gates** in **29m47s**.
  Nine independent desktop cases cover **41 states/four recipients**; six focused
  host tests pass, including rejection, no-op history, failed saves and real restart.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35944859268)
  passes **30 offline native executions**, both APKs, lint, signature and
  153-source/data/license/ABI inspection in **24m45s**. All **18 saved fits**
  restore. All **56 screenshots** reviewed; artifact digest/CI tree, twelve raw
  validators, thirteen native-summary and ten numeric-transport corruption probes
  pass. Local APKs/lint/signature/package checks also pass.
- [Task audit](tasks/B05-bulk-editing.md) and [retained receipt](evidence/b05-1-native.json)
  record scope and limits. The initial CI round passed too; review then strengthened
  the touch test to prove all-similar edits outside selection, requiring one more
  full CI round. That native round then hit a transient ADB outage after the
  existing equipment test passed, while collecting its report. The failed
  artifact was retained and only the native job was rerun on a fresh runner.
  No production failure or weakened assertion was involved.
- B04 was delivered in [PR #21](https://github.com/Sussic/Pyfa-android/pull/21).
  B05 remains active through clone/fill and variation/removal. B09 retains all
  undo/redo work.

## B05.2 delivered — Bulk module states (F03.03)

[PR #23](https://github.com/Sussic/Pyfa-android/pull/23) merged as
`eb7e3039bf612e4c6672bf8af10db32ad6ab90aa`, tested head
`2e6bb7af1a9af6e552f0970561f83cf738fb328f`. Build 17 exposes
selection-only/all-similar cycle, overheat and offline actions, EOS-supported
fallbacks, explicit skipped/actual saved states and atomic fit/recipient saves.
The original pinned desktop command passes six cases/27 states/four linked
recipients and a fresh-process repeat; five focused host tests cover invalid
requests, history, failed saves, copies and restart.

[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/36083151800)
passes **125 host tests** and all independent reference/migration gates in
**22m28s**. [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/36083151805)
attempt 2 passes **32 offline native executions**, both APKs, lint, signature,
source/data/license/ABI checks and restart in **31m06s**. Artifact digest and
CI merge tree match; all 13 raw validators, nine native protocol guards and ten
deliberate report corruptions pass. All **61 screenshots** were visually
reviewed. [Receipt and retained B05.2 raw evidence](evidence/b05-2-native.json)
record provenance and limits. The initial native test found an omitted skipped
preview row; the corrected final head passed. Final-head Android attempt 1 lost
ADB during transfer of an earlier empty-hull report; a same-head native-only
retry passed with no gate weakened. ARM64 execution, older APIs, phone usability
and safe upgrades remain unverified.

## Selected B05.3 — Clone and fill modules

Exact next task **B05.3 (F03.04 and cloning part of F03.05)**. Audit the pinned
desktop fill-add, fill-clone and single-module clone commands for stopping,
legality, override, retained state/charge and recent-item rules. Then deliver
touch-accessible cloning of a selected group and filling vacancies from a market
item or fitted module, with independent desktop/host comparisons, atomic saves,
native offline persistence and all required final-head checks. B05.4
variation/removal stays separate; do not start it before B05.3 delivery.

## Forecast after B05.2 delivery

| Next milestone | Remaining work | Elapsed estimate / confidence |
| --- | --- | --- |
| B05 bulk editing | B05.3 clone/fill and B05.4 variation/removal, each with original-command comparisons, native touch/persistence and PR delivery. | **Unknown until the clone/fill stopping and override audit resolves behavior**; low confidence. B05.2's two CI rounds plus one transient native retry show that a failed gate can add a full round. |
| B06 hull configuration | Modes, subsystems, structure controls, changing slots/bonuses and persistence. | **Unknown until the mode/subsystem/structure audit resolves scope**; low confidence. |
| B07 cargo | Stack counts and equipment/ammunition transfers, values and restart. | **Unknown until the stack/transfer audit resolves command behavior**; low confidence. |

Allow roughly **25–35 minutes per full parallel CI round** from recent checks;
this final round took 22m28s on Windows and 31m06s on Android. B05.2 took an
extra round to fix the preview and one native-only retry for transient ADB
report transfer; those are material delays, not a reduced gate. Build **16 was
the first meaningful development build**; build **17 (`0.1.0-b05.2`) is the latest
emulator-tested build**, adding bulk states to the library/hull/module/charge/
variation/rack and bulk ammunition workflows. The local debug APK is
`android/app/build/outputs/apk/debug/app-debug.apk`; no phone installation
occurs. Safe persistent phone use is **unknown until R02 signing/upgrade checks
and phone/API compatibility are resolved**. No user decision or access is needed
now; whole-queue elapsed time remains unknown until later audits and device/
upgrade gates resolve. Refresh this forecast after each delivered milestone.

## Resume, environment and architecture

Read AGENTS, [ROADMAP](ROADMAP.md), the next task and ignored
`build/WINDOWS-CHECKPOINT.md`; verify local changes, live master and open PRs.
Work only in Sussic/Pyfa-android. Dot-source `build/windows-env.ps1` to reuse
Python3.11.9 reference/headless, JDK17.0.20.1+1, SDK36/build35 and Gradle8.13.
No timed host suites alongside local Gradle. Native CI uses Ubuntu/KVM; local
Windows builds alone do not establish Android execution. Preserve all 125 host/
32 native type/unit/GC/restart/performance/screenshot gates, one-day diagnostics,
deliberate APK uploads only and no scheduled/release jobs.

Kotlin/Compose + Chaquopy + serialized EOS remain A10. Follow [scope](SCOPE.md),
[architecture](ARCHITECTURE.md) and [evidence rules](DEVELOPMENT.md). No Kotlin
formula approximations. Desktop pin `8b04f3b271e614b3e103853b44a7851a63d79d0e`,
tree `8db82315f8312b124dd24ef103e43496cee50b4a`, logical dataset
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
EOS owns an exclusive in-memory session; separate locked SQLite stores declarative
graphs atomically. Navigation preferences stay separate. Preserve invalid files.
Keep desktop `gamedataCache=False`. Host Logbook1.7.0.post0, SQLAlchemy1.4.50 and
Greenlet3.0.3; Android Greenlet3.0.1 build1 and chaquopy-libcxx180000 build0 remain.

ARM64 execution, older APIs, safe upgrades/downgrades and user usability remain
unverified. Both ABIs are packaged. Phone model/API unconfirmed; native report
transport requires API31+, app minSdk24. I05 backup/transfer, R02 signing/upgrades,
R03 usability, C07 full implant profiles/locations and Q07 complete projection/
command matrices retain scope. Older builds reject newer fields and preserve
storage. Legacy tox remains unaudited; A10 measurements are debug emulator baselines.
Full parity is not established. Restore-off opens the library while saved fits rebuild.
