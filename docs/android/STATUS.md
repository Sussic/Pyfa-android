# Android project status

Updated: 2026-09-27. **B07.1 delivered. B07.2 selected and active.**

## Authorized queue

The active goal authorizes sequential eligible approved roadmap work, one coherent
outcome through review, required host/native checks and fork PR merge, then automatic
continuation. No releases, phone installation, billing changes, unrelated work or
delegation. No user decision or access blocker currently prevents B07.2.

## Latest delivery — B07.1 cargo stacks and quantities

[PR #29](https://github.com/Sussic/Pyfa-android/pull/29) merged as `fd80b2fc`,
tested head `bc06de79`. CI checkout `5a5711f5` and the merge share tree `2437d335`.
Build **23 (`0.1.0-b07.1`)** adds cargo through the offline equipment browser,
edits/removes stack quantities, displays EOS used/capacity values and preserves
exact stacks through atomic saves, copy and process restart. Older graphs without
cargo still replay. Quantity actions use numeric input and dismiss the keyboard.

- Independent original desktop commands repeat **two cases/17 states** in fresh
  processes. Includes stack merging, partial/full removal, container volume,
  over-capacity Vexor (500/480 m³) and charge cargo on zero-capacity Astrahus.
- Three focused host tests pass reference states, invalid edits, legacy graphs,
  failed-save recovery, copy and fresh-process restart without desktop/network imports.
- [Windows/reference CI](https://github.com/Sussic/Pyfa-android/actions/runs/36277865653)
  passes every required host/reference/migration gate in **25m24s**.
- [Android/native CI](https://github.com/Sussic/Pyfa-android/actions/runs/36277865678)
  passes all inherited gates plus offline cargo touch/restart, both APKs, lint,
  signature and 160-source/data/license/ABI inspection in **35m37s**. All **47 fits**
  restore, including three new cargo fits; six protocol guards pass.
- Artifact digest and tested tree match. All **six final cargo screenshots** were
  reviewed, and **12 deliberate report corruptions** were rejected. The retained
  [receipt](evidence/b07-1-native.json) and [raw report](evidence/b07-1-cargo-stacks-native.json)
  record exact provenance, numeric kinds, state values and limits.

Earlier native rounds exposed equipment-to-charge navigation and two bugs in the
new test/report assertions (JSON numeric-kind serialization, then native nulls
compared using a desktop-only mapping). They are fixed and the final head passes;
no gate was weakened. [B07 task evidence](tasks/B07-cargo-management.md) records the details.

## Selected task — B07.2

Deliver original multi-selected cargo quantity/removal, including zero-to-remove,
ammunition presets, fill-to-capacity boundaries and variation/quantity merges.
Selected on `codex/b07-2-cargo-actions` from delivered master `062e8e09`, with no
open PR. The intended outcome is touch-accessible selected cargo actions with
independent command/value comparisons, atomic saves and native offline copy/restart.
The adapter and touch controls are implemented. Independent desktop export repeats
five cases/37 states; three focused host checks pass selection/history, menu choices,
volume guards, atomic rejection/save failure and 11-fit fresh restart. Kotlin and
instrumentation compilation pass. Review added a positive existing-stack fill
case; its refreshed export/repeat and three host checks pass. Both final local APKs,
lint and 160-source/data/license/ARM64/x86_64 package inspection pass.
Native offline execution, screenshots and final-head CI/merge remain required.
Head `7ef87f71` passed Windows CI (36284141825, 25m26s). Native run
36284141813 passed all inherited phases, then the new cargo test failed because
it used one Back tap to leave the browser's selected/search/root hierarchy.
The test now follows all three levels and asserts the cargo screen is visible;
no product behavior or required gate changed. Corrected native CI is required.
Use original pinned commands for independent fixtures, preserve serialized EOS and
atomic graph/history behavior, then verify native touch, copy and offline restart.
F04.01 remains partial until selected-stack actions are delivered. B07.3 retains
fitted equipment/charge transfers; B09 owns undo/redo. B07 remains active.

## Delivered work to reuse

| Milestone | Delivery and retained evidence |
| --- | --- |
| B04 equipment/fitting | [PR #21](https://github.com/Sussic/Pyfa-android/pull/21), [task](tasks/B04-equipment-fitting.md). All B04 children remain closed. |
| B05 bulk editing | PRs [#22](https://github.com/Sussic/Pyfa-android/pull/22), [#23](https://github.com/Sussic/Pyfa-android/pull/23), [#24](https://github.com/Sussic/Pyfa-android/pull/24), [#25](https://github.com/Sussic/Pyfa-android/pull/25); [task](tasks/B05-bulk-editing.md). |
| B06 modes/subsystems/structures | PRs [#26](https://github.com/Sussic/Pyfa-android/pull/26), [#27](https://github.com/Sussic/Pyfa-android/pull/27), [#28](https://github.com/Sussic/Pyfa-android/pull/28); [task](tasks/B06-hull-configuration.md), [latest receipt](evidence/b06-3-native.json). |

Earlier A/B milestones remain done as recorded in ROADMAP and their task/evidence
files. Do not reopen delivered work or rerun unchanged tested revisions.

## Forecast and installation limits

B07.2 selected actions/presets/fill/variations comes next, then B07.3 transfers,
B08 notes and B09 undo/redo. Elapsed implementation estimates remain **unknown**
until each focused command/state audit resolves its remaining scope; confidence
is low. A full parallel CI round currently takes roughly **25–40 minutes**;
B07.1's final Windows/Android runs took 25m24s/35m37s. Multiple correction rounds
were needed for B07.1, so a one-round delivery estimate is not reliable.

Build 16 was the first meaningful development build; build 23 is the latest
emulator-tested build. The local debug APK is
`android/app/build/outputs/apk/debug/app-debug.apk`. Safe persistent phone use
remains **unknown** until R02 signing/upgrade checks and phone/API compatibility
are resolved. Phone usability, older APIs and ARM64 execution remain unverified;
no phone installation or release publication occurs.

## Resume, environment and architecture

Read AGENTS, [ROADMAP](ROADMAP.md), the next task and ignored
`build/WINDOWS-CHECKPOINT.md`; verify local changes, live master and open PRs.
Work only in Sussic/Pyfa-android. Dot-source `build/windows-env.ps1` to reuse
Python3.11.9 reference/headless, JDK17.0.20.1+1, SDK36/build35 and Gradle8.13.
No timed host suites alongside local Gradle. Native CI uses Ubuntu/KVM; local
Windows builds alone do not establish Android execution. Preserve all inherited
host/native type/unit/GC/restart/performance/screenshot gates, one-day diagnostics,
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
