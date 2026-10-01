# Android project status

Updated: 2026-10-02. **B09.1 verified; PR #33 delivery in progress.**

## Selected outcome — B09.1 module edit history

The user explicitly resumed development and superseded the setup-only stop.
Review and deliver PR #33, then automatically select B09.2 and subsequent eligible
approved work, one coherent outcome at a time. Reuse installed local verification
and retained valid evidence. No hosted dispatch without asking the user; no setup
repeat, new infrastructure, unrelated refactoring, release, phone installation or
billing change. No delegation or access blocker currently exists.

PR #33 branch `codex/b09-1-edit-history` retains W02 setup delivered in PR #34.
Live master is `72b01c4c`; current product inputs match the tested native revision
`6792b03e` exactly. [Local setup receipt](evidence/w02-local.json) proves all 78
required gates; host/build ran at `f7d2ad31`, native execution at `6792b03e`, final
aggregate at `5952c1bf`. Actual commits and earlier failures remain unchanged.
Explicit `local/full-verification` passes at `5b07bc50`; no hosted native pass is
claimed. The cancelled Actions attempts remain recorded.

B09.1 matches independent original GUI/calc commands and wx processors in 18
cases/108 states, grouping/branching, per-fit isolation and the 100-action limit.
Six retained host tests cover linked recipients, monotonic revisions, notes,
stale/malformed requests, failed-save recovery, copy and fresh-process reopening.
Native touch/recreation/restart confirms all 111 fits and ten protocol rejections.
Six history screens (and all inherited screens) are reviewed. The focused final
raw validator rejects 21 deliberate report corruptions. Review found no blocking
issue. [Feature receipt](evidence/b09-1-native.json) and
[raw history](evidence/b09-1-history-native.json) preserve evidence and limits.

Next action: push the delivery receipt/docs, publish the validated local result
for the exact PR head and merge PR #33 after checks pass. Then select **B09.2**:
remaining supported rename/hull/cargo/addition/linked-effect history and mandatory
extension checks for future mutations. B09 remains active until B09.2 is verified.

W02 is delivered; [commands and evidence](LOCAL-VERIFICATION.md) apply. Master will
receive the demonstrated manual hosted fallback policy with PR #33. No owner
configuration step remains. ARM64, older APIs, phone usability and signing/upgrades
remain unverified; session history is not persisted, confirmed fit inputs are.

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

Build 16 was the first meaningful development build; build 27 is the latest
locally emulator-tested development build. The local debug APK is
`android/app/build/outputs/apk/debug/app-debug.apk`. Safe persistent phone use
remains **unknown** until R02 signing/upgrade checks and phone/API compatibility
are resolved. Phone usability, older APIs and ARM64 execution remain unverified;
no phone installation or release publication occurs.

## Resume, environment and architecture

Read AGENTS, [ROADMAP](ROADMAP.md), the next task and ignored
`build/WINDOWS-CHECKPOINT.md`; verify local changes, live master and open PRs.
Work only in Sussic/Pyfa-android. Dot-source `build/windows-env.ps1` to reuse
Python3.11.9 reference/headless, JDK17.0.20.1+1, SDK36/build35 and Gradle8.13.
No timed host suites alongside local Gradle. Windows WHPX full native execution
and screenshot review now provide required local evidence; APK builds alone do not. Preserve all inherited
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
