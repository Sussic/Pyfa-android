# Android project status

Updated: 2026-09-25. **B05.3 delivered. Next: B05.4 — Variation and removal.**

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
  B05 remains active through variation/removal. B09 retains all
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

## B05.3 delivered — Clone and fill modules (F03.04/F03.05)

[PR #24](https://github.com/Sussic/Pyfa-android/pull/24) merged as
`0bef5a67eaba0fa797973cef296b52b8f1588d0c`, tested head
`bd122061e55045136c549d7fbb0cb276132a6109`. Build 18 adds market and
fitted-source fill, chosen-vacancy clone and selected-group clone. EOS determines
stopping, legality and override; state/charge and the market-history distinction
survive atomic offline saves. The pinned original commands pass seven cases/17
states and a fresh-process repeat; four focused host tests pass.

[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/36098964569)
passes all existing host/reference/migration gates in **19m02s**.
[Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/36098964629)
passes **34 offline native executions**, both APKs, lint, signature,
source/data/license/ABI and real restart in **26m23s**. All **69 screenshots**
were reviewed. The retained [receipt](evidence/b05-3-native.json) and
[raw report](evidence/b05-3-clone-fill-native.json) record artifact digest,
matching CI/merge tree, 14 validators, seven new protocol guards, ten rejected
report corruptions and 25 restored fits. The first native run exposed a Compose
test assertion on a parent Card; a later attempt lost ADB while transferring a
prior report, then revealed the new test phase used ephemeral diagnostic storage.
The corrected final head passed without changing engine gates. ARM64 execution,
older APIs, phone usability and safe upgrades remain unverified.

## Forecast after B05.3 delivery

| Next milestone | Remaining work | Elapsed estimate / confidence |
| --- | --- | --- |
| B05 bulk editing | B05.4 selected/similar variation and removal, original-command comparisons, native touch/persistence and PR delivery. | **Roughly 2–5 hours if the audit confirms bounded command scope**, low confidence; otherwise unknown until its variation/removal audit resolves the difference. |
| B06 hull configuration | Modes, subsystems, structure controls, changing slots/bonuses and persistence. | **Unknown until the mode/subsystem/structure audit resolves scope**; low confidence. |
| B07 cargo | Stack counts and equipment/ammunition transfers, values and restart. | **Unknown until the stack/transfer audit resolves command behavior**; low confidence. |

Allow roughly **25–40 minutes of CI waiting per full parallel round** from recent
Windows/Android runs; this final round took 19m02s/26m23s. Confidence is medium
for one passing round and low for elapsed delivery because B05.3 required two
test-harness corrections and one transient ADB retry. Build **16 was the first
meaningful development build**; build **18 (`0.1.0-b05.3`) is the latest
emulator-tested build**. The local debug APK is
`android/app/build/outputs/apk/debug/app-debug.apk`; no phone installation
occurs. Safe persistent phone use is **unknown until R02 signing/upgrade checks
and phone/API compatibility are resolved**. No user decision or access is needed
now; whole-queue elapsed time remains unknown until later audits and device/
upgrade gates resolve. Refresh this forecast after each delivered milestone.

## Selected B05.4 — Bulk variation and removal

Selected after B05.3 merge `0bef5a67`. Audit the pinned desktop selection,
variation-family filtering, replacement reconciliation, removal order and
recent-item rules. Deliver touch-accessible selection-only and all-similar
variation/removal with exact affected/skipped previews, one atomic serialized
save, independent desktop/host comparisons, native offline restart and final-head
CI. B09 keeps undo/redo; B06 keeps subsystem and hull-mode controls.

## Resume, environment and architecture

Read AGENTS, [ROADMAP](ROADMAP.md), the next task and ignored
`build/WINDOWS-CHECKPOINT.md`; verify local changes, live master and open PRs.
Work only in Sussic/Pyfa-android. Dot-source `build/windows-env.ps1` to reuse
Python3.11.9 reference/headless, JDK17.0.20.1+1, SDK36/build35 and Gradle8.13.
No timed host suites alongside local Gradle. Native CI uses Ubuntu/KVM; local
Windows builds alone do not establish Android execution. Preserve all 125 host/
34 native type/unit/GC/restart/performance/screenshot gates, one-day diagnostics,
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
