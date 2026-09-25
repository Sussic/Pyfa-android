# Android project status

Updated: 2026-09-25. **B06.1 delivered. Next: B06.2 — Strategic-cruiser subsystems.**

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
  B05 is delivered through B05.4; B09 retains undo/redo work.

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

## Forecast after B06.1 delivery

| Next milestone | Remaining work | Elapsed estimate / confidence |
| --- | --- | --- |
| B06 hull configuration | B06.1 modes delivered; audit/implement B06.2 strategic-cruiser subsystems and B06.3 structure controls, each with independent desktop and native restart evidence. | **Unknown until the subsystem and structure audits resolve slot/bonus behavior**; low confidence. |
| B07 cargo | Audit stack counts and equipment/ammunition transfer commands; implement values and restart. | **Unknown until the stack/transfer audit resolves command behavior**; low confidence. |
| B08 fit notes | Audit desktop note editing; retain multiline/non-ASCII unsaved text across navigation and durable reopen. | **Unknown until the notes/navigation audit resolves scope**; low confidence. |

Allow roughly **25–40 minutes of CI waiting per full parallel round** from recent
Windows/Android runs; B06.1 took 23m57s/31m52s. Confidence is medium for one
passing round and low for elapsed delivery because subsystem/structure scope
is not yet audited. Build **16 was the first meaningful development build**;
build **20 (`0.1.0-b06.1`) is the latest
emulator-tested build**. The local debug APK is
`android/app/build/outputs/apk/debug/app-debug.apk`; no phone installation
occurs. Safe persistent phone use is **unknown until R02 signing/upgrade checks
and phone/API compatibility are resolved**. No user decision or access is needed
now; whole-queue elapsed time remains unknown until later audits and device/
upgrade gates resolve. Refresh this forecast after each delivered milestone.

## B05.4 delivered — Bulk variation and removal

Selected after B05.3 merge `0bef5a67`. Audit the pinned desktop selection,
variation-family filtering, replacement reconciliation, removal order and
recent-item rules. Deliver touch-accessible selection-only and all-similar
variation/removal with exact affected/skipped previews, one atomic serialized
save, independent desktop/host comparisons, native offline restart and final-head
CI. B09 keeps undo/redo; B06 keeps subsystem and hull-mode controls.

On `codex/b05-4-bulk-variation-removal`, the pinned original handlers and commands
pass eight cases/17 states in a fresh repeat. All-similar can include a different
variation family; the preview now uses pinned-family candidates from the bridge.
Four focused host checks pass, including a forced later replacement rejection,
failed-save recovery and process restart; the existing 17-case/5,226-family
variation regression passes. Local debug/test APK assembly and lint pass.
PR [#25](https://github.com/Sussic/Pyfa-android/pull/25) merged as
`4da3b2a09b7a395c7633c0b809d54e00644b0a61`, tested head `e1d8d344`.
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/36108925169)
passed in 22m24s and [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/36108925181)
passed in 33m02s on the final head: all retained host/reference/migration and
native type/unit/GC/performance/restart/APK/lint/signature/data/license/ABI
gates, four new fits, 29 restored fits and nine new protocol guards. All eight
B05.4 and seven affected B04 variation screenshots were reviewed. The retained
[receipt](evidence/b05-4-native.json) and [raw report](evidence/b05-4-variation-removal-native.json)
record offline touch/restart and matching CI/merge tree. The first Android run
found an existing variation Back action obscured by the keyboard after the new
preview grew; the final head collapses bulk controls for single edits and keeps
Back beside the filter. **Exact next task B06 — Hull-specific configuration**:
audit and split modes, strategic-cruiser subsystems and structure controls.

## B06.1 delivered — Hull modes

B06 is split into [mode, subsystem and structure children](tasks/B06-hull-configuration.md)
because the pinned desktop routes them through distinct EOS/command systems.
B06.1 starts on `codex/b06-1-hull-modes` from delivered master `5991fe99`.
The pinned mode menu changes `fit.mode`, recalculates/fills and commits; EOS
offers mode items for tactical destroyers and Anhinga. The bridge currently
starts with the EOS default but omits mode from its declarative graph, so the
selected outcome is strict hull-specific choice/edit, independent stats,
touch access and durable offline copy/restart. B06.2 retains subsystem changes;
B06.3 retains structure-specific controls. No decision or access block.

The pinned original mode command repeats four hull cases/16 raw-value states
in fresh processes, including Confessor, Jackdaw, Anhinga and no-mode Vexor.
Four focused host checks pass for all 16 states, cross-hull/stale rejection,
failed-save recovery, selected-mode copy/restart and older default-mode graphs.
The mode bridge preserves the legacy implicit default while storing explicit
changes. Local Kotlin/main+instrumented compilation, both debug APKs, lint and
APK source/data/license/ARM64/x86_64 inspection pass. PR
[#26](https://github.com/Sussic/Pyfa-android/pull/26) merged as `7f08c3d8`,
tested head `90688456`. [Windows/reference CI](https://github.com/Sussic/Pyfa-android/actions/runs/36116275320)
passed in 23m57s; [Android/native CI](https://github.com/Sussic/Pyfa-android/actions/runs/36116275344)
passed in 31m52s, including 16 independent states, five new/34 restored fits,
four protocol guards, fresh offline restart and all inherited native gates.
All four mode screenshots were reviewed. The [receipt](evidence/b06-1-native.json)
and [raw report](evidence/b06-1-hull-modes-native.json) retain matching
CI/merge tree, artifact provenance and limits. **Exact next task: B06.2 —
Strategic-cruiser subsystems.**

## Selected B06.2 — Strategic-cruiser subsystems

Selected on `codex/b06-2-subsystems` from delivered master `c102ae09`.
Deliver exact T3 cruiser subsystem choices, add/replace/remove, dynamic slot and
bonus reconciliation, fitting legality and charge/state handling, durable
offline copy/restart and touch controls. Compare original pinned desktop
commands and independent raw values before Android implementation; keep B06.3
structure behavior and B09 undo/redo separate. No access or product decision is
needed; the desktop command audit determines the focused case matrix.

The pinned original add/replace/remove sequence repeats 14 raw-value states
in fresh processes and enumerates 48 choices across four strategic cruisers.
The focused host suite passes three cases, including all states, strict choice
rejection, failed-save recovery and illegal charged-launcher copy/restart.
Local main/test Kotlin compilation, debug/test APKs, lint and package inspection
pass (158 bundled engine sources and both ABIs). Native execution, screenshot
review, final-head CI and PR merge remain.

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
