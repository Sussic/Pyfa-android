# Android project status

Updated: 2026-09-30. **B08 delivered. B09 ready.**

## Authorized queue

The active goal authorizes sequential eligible approved roadmap work, one coherent
outcome through review, required host/native checks and fork PR merge, then automatic
continuation. No releases, phone installation, billing changes, unrelated work or
delegation. No user decision or access blocker currently prevents B09.

## Latest delivery — B08 fit notes

[PR #32](https://github.com/Sussic/Pyfa-android/pull/32) merged as `d6110359`,
tested head `02171308`. CI checkout `15d4c7e4` and
the merge share tree `14f3c7cc`. Build **26 (`0.1.0-b08`)** adds
exact multiline Unicode notes, one-second autosave and navigation flush, retained
drafts through activity recreation and failed saves, and explicit conflict choices.
Stored structure notes remain read-only and survive copies/restart.

- The independent original service/pane and EOS copy repeat **three fits/13 states**.
  Four host tests pass exact text/counts, fit/copy isolation, unchanged calculations
  and recent history, invalid/stale/write-failure recovery, legacy graphs and
  **five-fit fresh-process restart**.
- [Windows/reference CI](https://github.com/Sussic/Pyfa-android/actions/runs/36657441169)
  passes all required gates in **28m44s**.
- [Android/native CI](https://github.com/Sussic/Pyfa-android/actions/runs/36657441195)
  passes inherited and new offline workflows, both APKs, lint, signature, pinned
  data/licenses and ABI inspection in **34m24s**.
  All **90 fits** restore; ten malformed notes protocol cases are rejected.
- Artifact digest and tested tree match. **Seven notes screenshots** were reviewed;
  **20 deliberate report corruptions** are rejected. Retained
  [receipt](evidence/b08-native.json) and [raw report](evidence/b08-notes-native.json)
  record provenance and observed results.

Pending drafts remain in memory until a save is confirmed; unconfirmed process
death is not a draft-persistence guarantee. B08 is complete within the pinned notes
boundary. **B09 undo/redo** is the exact next eligible task; B05 is delivered.

## Delivered work to reuse

| Milestone | Delivery and retained evidence |
| --- | --- |
| B04 equipment/fitting | [PR #21](https://github.com/Sussic/Pyfa-android/pull/21), [task](tasks/B04-equipment-fitting.md). All B04 children remain closed. |
| B05 bulk editing | PRs [#22](https://github.com/Sussic/Pyfa-android/pull/22), [#23](https://github.com/Sussic/Pyfa-android/pull/23), [#24](https://github.com/Sussic/Pyfa-android/pull/24), [#25](https://github.com/Sussic/Pyfa-android/pull/25); [task](tasks/B05-bulk-editing.md). |
| B07.3 fitted transfers | [PR #31](https://github.com/Sussic/Pyfa-android/pull/31), [receipt](evidence/b07-3-native.json), [task](tasks/B07-cargo-management.md). |
| B07.2 selected cargo actions | [PR #30](https://github.com/Sussic/Pyfa-android/pull/30), [receipt](evidence/b07-2-native.json), [task](tasks/B07-cargo-management.md). |
| B07.1 cargo stacks | [PR #29](https://github.com/Sussic/Pyfa-android/pull/29), [receipt](evidence/b07-1-native.json), [task](tasks/B07-cargo-management.md). |
| B06 modes/subsystems/structures | PRs [#26](https://github.com/Sussic/Pyfa-android/pull/26), [#27](https://github.com/Sussic/Pyfa-android/pull/27), [#28](https://github.com/Sussic/Pyfa-android/pull/28); [task](tasks/B06-hull-configuration.md), [latest receipt](evidence/b06-3-native.json). |

Earlier A/B milestones remain done as recorded in ROADMAP and their task/evidence
files. Do not reopen delivered work or rerun unchanged tested revisions.

## Forecast and installation limits

B09 undo/redo comes next. Elapsed implementation estimates remain **unknown**
until its focused audit resolves scope; confidence is low. B08's final Windows/
Android runs took **28m44s/34m24s**.
CI corrections may require another full round; one-round delivery estimates are
not reliable.

Build 16 was the first meaningful development build; build 26 is the latest
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
