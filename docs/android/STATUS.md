# Android project status

Updated: 2026-09-25. **B05.1 delivered. Next: B05.2 — Bulk module states.**

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
  B05 remains active until states, clone/fill and variation/removal are verified
  and delivered. Exact next task: **B05.2 — Bulk module states (F03.03)**. Record
  its selected branch/scope before implementation. B09 retains all undo/redo work.

## Selected B05.2 — Bulk module states

Branch `codex/b05-2-bulk-module-states` starts from delivered master
`e5098cc1ff017819f07c9afbdc99e0eab2a378d8`. Deliver one touch-accessible
action for selected versus all-similar module state changes: original cycle,
offline and overheat transitions, per-module supported-state fallback, fit-wide
restrictions, explicit affected/skipped results and atomic persistence. Compare
independent pinned desktop cases and recipients, then run focused host/native
checks, final-revision required CI, review and a focused PR. B05.3/B05.4 remain
outside this child. Transition/restriction audit is the next development step.

The pinned state-column command and EOS transition/fallback/restriction paths are
audited. A six-case/27-state independent desktop export and fresh-process repeat
pass with four linked recipients; five focused headless checks pass against it,
including malformed/stale requests, no-op history, failed save and restart.
Candidate build 17 compiles both APKs and passes local lint. Native execution,
complete regression, final-head CI, screenshot review and delivery remain pending.

## Forecast after B05.1 delivery

| Next milestone | Remaining work | Elapsed estimate / confidence |
| --- | --- | --- |
| B05 bulk editing | B05.2 state transitions/fallbacks, B05.3 clone/fill and B05.4 variation/removal; matching host/native and persistence evidence. | Total unknown until clone/fill/override termination is verified. B05.2 provisional **2–5 hours**, low confidence until its transition/restriction matrix is checked; based on the just-completed reference/UI/CI workflow. |
| B06 hull configuration | Modes, subsystems, structure controls, changing slots/bonuses and persistence. | Unknown until the mode/subsystem/structure audit resolves scope; low confidence. |
| B07 cargo | Stack counts and equipment/ammunition transfers, values and restart. | Unknown until the stack/transfer audit resolves command behavior; low confidence. |

Allow **25–35 minutes per full parallel CI round**: the previous B05.1 run took
28m09s on Android; final timings are above. Corrections or coverage refinements
add rounds. The touch-scope refinement and subsequent ADB report-transfer outage
explain this milestone's additional CI waiting time.
Build **16 (`0.1.0-b05.1`) is meaningful for development workflow testing now**:
library, hull/module/charge/variation/rack workflows plus bulk ammunition. The local
APK is `android/app/build/outputs/apk/debug/app-debug.apk`. Safe persistent phone
use remains **unknown until R02 signing/upgrade checks and phone/API compatibility
are resolved**. No phone installation occurs. No user decision/access is needed
now; whole-queue elapsed time remains unknown until later audits and device/upgrade
gates resolve. Refresh this forecast after each delivered milestone.

## Resume, environment and architecture

Read AGENTS, [ROADMAP](ROADMAP.md), the next task and ignored
`build/WINDOWS-CHECKPOINT.md`; verify local changes, live master and open PRs.
Work only in Sussic/Pyfa-android. Dot-source `build/windows-env.ps1` to reuse
Python3.11.9 reference/headless, JDK17.0.20.1+1, SDK36/build35 and Gradle8.13.
No timed host suites alongside local Gradle. Native CI uses Ubuntu/KVM; local
Windows builds alone do not establish Android execution. Preserve all 120 host/
30 native type/unit/GC/restart/performance/screenshot gates, one-day diagnostics,
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
