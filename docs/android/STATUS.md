# Android project status

Updated: 2026-09-30. **B07 delivered. B08 active.**

## Authorized queue

The active goal authorizes sequential eligible approved roadmap work, one coherent
outcome through review, required host/native checks and fork PR merge, then automatic
continuation. No releases, phone installation, billing changes, unrelated work or
delegation. No user decision or access blocker currently prevents B08.

## Latest delivery — B07.3 fitted transfers

[PR #31](https://github.com/Sussic/Pyfa-android/pull/31) merged as `ef364631`,
tested head `c43ba37a`. CI checkout `a9f20cb9` and the
merge share tree `c4ae2ebc`. Build **25 (`0.1.0-b07.3`)** adds selected
module/loaded-charge move and copy, cargo-to-fit loading and optional module swaps,
with EOS magazine quantities, legality and state/charge reconciliation.

- Independent original commands repeat **14 cases/80 states**. Four focused host
  tests pass values/history, native setup, invalid/stale/overflow/partial and
  failed-save rollback, copies and **29-fit fresh-process restart**.
- [Windows/reference CI](https://github.com/Sussic/Pyfa-android/actions/runs/36651689500)
  passes all required gates in **28m44s**.
- [Android/native CI](https://github.com/Sussic/Pyfa-android/actions/runs/36651689487)
  passes inherited and new offline touch/restart gates, both APKs, lint, signature,
  pinned data/licenses and ABI inspection in **47m15s**.
  All **85 fits** restore, including 28 new/copy fits; ten protocol guards pass.
- Artifact digest and tested tree match. All **six transfer screenshots** were
  reviewed; **20 deliberate report corruptions** are rejected. Retained
  [receipt](evidence/b07-3-native.json) and
  [raw report](evidence/b07-3-cargo-transfers-native.json) record exact provenance.

Original failed transfers can duplicate cargo; Android preserves the preceding
state atomically, with the raw desktop failure retained in the reference. Market
crystal presets remain 1000; audited fitted crystal/script transfers use one.
The initial native run exposed a phased-test registration omission, corrected
without removing checks. The [B07 task](tasks/B07-cargo-management.md) retains it.
B07 is complete within its boundary; **B09 owns undo/redo**. Next: **B08 fit notes**.

## Selected task — B08 fit notes

Selected on `codex/b08-fit-notes` from delivered master `93d020de`; live default
branch and no open PRs verified. Deliver F01.06 multiline Unicode notes, exact
whitespace/empty text, correct-fit saves, durable copy/restart and preserved drafts
across navigation/recreation. The pinned pane saves after one second and flushes
the previous fit on switching; structure editing is disabled. Preserve that UI
boundary and existing structure note data. Acceptance requires independent original
service/pane evidence, strict atomic edits, unchanged calculations/history, native
typing/navigation/recreation/restart and screenshot review, then final-head CI and
reviewed merge. [Task and checks](tasks/B08-fit-notes.md). B09 remains next.

The original service/pane reference repeats three fits/13 states. Four focused
host tests pass exact text, correct-fit/copy isolation, unchanged calculations,
atomic rejection/write recovery, legacy graphs and five-fit restart. The typed
note boundary and retained multiline editor are implemented. Both final local APKs,
lint (1m34s) and package inspection pass: 162 sources, pinned data/licenses and
ARM64/x86_64 dependencies. Required PR CI, native navigation/recreation/restart,
seven screenshot reviews and delivery remain outstanding. Local build 26 is not
yet emulator-verified.

## Delivered work to reuse

| Milestone | Delivery and retained evidence |
| --- | --- |
| B04 equipment/fitting | [PR #21](https://github.com/Sussic/Pyfa-android/pull/21), [task](tasks/B04-equipment-fitting.md). All B04 children remain closed. |
| B05 bulk editing | PRs [#22](https://github.com/Sussic/Pyfa-android/pull/22), [#23](https://github.com/Sussic/Pyfa-android/pull/23), [#24](https://github.com/Sussic/Pyfa-android/pull/24), [#25](https://github.com/Sussic/Pyfa-android/pull/25); [task](tasks/B05-bulk-editing.md). |
| B07.2 selected cargo actions | [PR #30](https://github.com/Sussic/Pyfa-android/pull/30), [receipt](evidence/b07-2-native.json), [task](tasks/B07-cargo-management.md). |
| B07.1 cargo stacks | [PR #29](https://github.com/Sussic/Pyfa-android/pull/29), [receipt](evidence/b07-1-native.json), [task](tasks/B07-cargo-management.md). |
| B06 modes/subsystems/structures | PRs [#26](https://github.com/Sussic/Pyfa-android/pull/26), [#27](https://github.com/Sussic/Pyfa-android/pull/27), [#28](https://github.com/Sussic/Pyfa-android/pull/28); [task](tasks/B06-hull-configuration.md), [latest receipt](evidence/b06-3-native.json). |

Earlier A/B milestones remain done as recorded in ROADMAP and their task/evidence
files. Do not reopen delivered work or rerun unchanged tested revisions.

## Forecast and installation limits

B08 notes comes next, then B09 undo/redo. Elapsed implementation estimates remain
**unknown** until each focused audit resolves scope; confidence is low. B07.3's
final Windows/Android runs took **28m44s/47m15s**.
CI corrections may require another full round; one-round delivery estimates are
not reliable.

Build 16 was the first meaningful development build; build 25 is the latest
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
