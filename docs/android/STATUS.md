# Android project status

Updated: 2026-10-03. **C01.3.1 delivered; C01.3.2 active.**

The active user-authorized goal continues sequential ready, approved roadmap work,
one reviewed outcome through required local checks, push and merge at a time.
W02, B09.1 and B09.2 are delivered. No hosted dispatch, delegation, release, phone
installation, unrelated setup/refactoring or billing changes are authorized here.

## Selected outcome — C01.3.2 repair, tank and spool

Selected from delivered master `2d941fd9` on `codex/c01-3-2-tank-details`.
Deliver all F05.23–F05.27 together: passive shield recharge, active shield,
armor and hull repairs, raw/effective reinforced/sustained values, capacitor
limits and projected repair contributions, armor pre/full/current spool details.
EOS remains the calculation authority; preserve original desktop units,
formatting, applicable states and explicit unavailable values. Any required
assumption edit must preserve typed inputs, history and offline persistence.
Acceptance: independent original wx/EOS fixtures for capacitor-limited/stable,
projected repair, active/offline/removal and spool states; strict protocol and
report rejection, read-only/refresh/history/copy/recreation/restart checks;
APK/lint/package, every inherited local gate and actual screenshot review.
Use focused checks during implementation. Complete implementation, fixtures and
summary validators before one full verification; retain valid existing evidence.
Live master and absence of open PRs verified before selection. No run is active.

Implementation/source review complete. Two fresh original wx/EOS exports agree
for29 cases. Focused host matrix, read-only/GC, state/removal/projection history,
copy and process restart pass. Expanded21 fixture/summary/transport regressions
and all22 inherited defense validator tests pass. Development app/test APK builds
and lint pass for build31. The original invalid spool fixture/hull attempts and
corrected reference evidence remain retained. Full/native verification and actual
screenshot review remain outstanding; no full delivery or hosted pass is claimed.

Full run `20261003-011943-7a0aaa27-72c5cf` paused after nine valid gates
when the labelled falloff witness proved to be inside the mutadaptive optimal.
Pinned EOS shows that repairer has zero falloff. Only case25 is corrected to
the ordinary armor repairer at verified10500m optimal plus3000m falloff; two
fresh original exports agree on reduced nonzero21.3HP/s (zero-range42.7HP/s).
All28 other cases and fixture metadata are unchanged; packaged-byte/reference
checks remain strict. Twenty-one affected validator tests, five exact pending
source/reuse guards and twenty-two reporter regressions pass. Product/native
test code is unchanged. The same full run resumes with all nine completed
gates retained under exact source hashes; no native/build gate has executed yet.

## Latest outcome — C01.3.1 defenses and incoming damage

Selected from delivered master `adafcadc` on codex/c01-3-1-defense-details.
F05.16–F05.22: all twelve shield/armor/hull resistances, each resistance
multiplier, raw and selected-pattern effective HP per layer and total, HP/EHP
toggle, and all four independently editable incoming damage contributions.
Preserve precise typed EOS results, current-fit/revision refresh, offline durable
inputs and global Undo/Redo. Named pattern management remains D05.
Required: independent original wx/EOS states for single/mixed patterns, fitted
resistance/HP modifiers, active/offline changes; rejection/read-only/history/copy
and fresh-process persistence checks; APK/lint/package and the full inherited
local/native suite, screenshot review and actual-report corruption rejection.
C01.3.2 follows only after this outcome's review, checks, push and merge; it owns
F05.23–F05.27 passive/active reinforced/sustained tank and spool details.

Implementation/source review complete. Two fresh unmodified wx/EOS exports agree
for fourteen cases and four individual contribution witnesses. Host matrix,
read-only/GC, input/history/rejection/no-op/failed-save/copy and fresh-process
restart pass; twenty-two fixture/schema/transport regressions and the extended
original history matrix pass. Ten historical capacitor source/package guards pass.
All 101 required local gates pass on `e0778290`: 56 reference/host, five build
and 40 native gates, with 67 native executions and all A10 requirements retained.
All 189 fits, including 174 inherited fits, survive process restart. All 165
required screenshots are reviewed; 23 actual-report corruptions are rejected.
[Receipt](evidence/c01-3-1-native.json) binds gate commits, logs, APK hashes and QA.
The existing full run completed without native retries; its passing results were
preserved across continuations. The earlier development diagnostics-accessor
compile failure and repaired app/test/lint run remain recorded. No assertion,
tolerance, timeout or performance criterion changed. Hosted checks were not run.
[PR #38](https://github.com/Sussic/Pyfa-android/pull/38) merged as `e937fef4`
from reviewed head `b1795eb1`; merge/head trees match. Its exact-head
`local/full-verification` passed. C01.3.1 is closed. Exact next is C01.3.2
repair/tank/spool, keeping all F05.23–F05.27 checks in one coherent deliverable.

## Latest delivery — C01.2 capacitor

Selected from `2cb602f3` on `codex/c01-2-capacitor-details` in `7594e7ec`.
Read-only capacitor query, strict typed DTO and current-fit screen are implemented;
capacity/effective capacity, recharge/use/delta/effective excess, resistance and
stable percent versus depletion seconds use EOS and pinned desktop presentation.
Two fresh original wx/EOS exports agree for twelve independent cases. Focused
host matrix/read-only/history/copy/thread/restart checks and ten fixture/raw
validator tests pass. All 97 required local gates pass: 54 reference/host, five
build and 38 native gates, including 65 required native executions and all A10
requirements. All 174 fits survive restart; 159 required screenshots plus the
optional capacitor failure diagnostic are reviewed. Twenty-two actual-report
corruptions and ten exact runner/source/package guards pass.
[Receipt](evidence/c01-2-native.json) binds actual gate commits and APK hashes.
Reviewed product code is `855c87c3`; exact persistent test-runner repair is
`7775b40a`. Ninety-four prior gates are retained under strict source/package/store
proof; only test APK/package and capacitor phases/summary reran. App APK unchanged.
Initial host/import/shell failures, B05.4 transport failures/recovery and capacitor
ephemeral-storage rejection remain recorded. The optional shared B05.4 failure
logcat was overwritten by the capacitor failure before archival and is explicitly
unavailable; required passing evidence and original failed command logs remain.
No assertions, tolerances, timeouts or performance requirements changed.
PR #37 merged as1c3beef9 from reviewed headca052755; merge/head trees match.
The exact-head local/full-verification status passed. Hosted checks were not run.
Exact next is C01.3 defenses/tank, beginning with its bounded defenses child.

## Previous delivery — C01.1 fitting resources

[PR #36](https://github.com/Sussic/Pyfa-android/pull/36) merged as `7e457c97` from
reviewed head `c5b187c0`; merge/head trees match. Reviewed/tested code is `e310303f`.
[Task](tasks/C01-fit-statistics.md), [receipt](evidence/c01-1-native.json).
F05.01–F05.11 expose all eleven used/capacity pairs, original compact formatting,
units, detail/raw precision, explicit unavailable scalars and textual overload.
Current fit/revision refresh, Undo/Redo, read-only queries, recreation and restart
pass through serialized EOS; no Kotlin fitting formula or mutation operation added.
The earlier 39 calculation fields and all inherited acceptance gates remain intact.

All **93 local gates**, **63 required native executions**, **158 saved fits** and
**154 required screenshots** pass; the optional failed-run screenshot is also
reviewed (155 total). Thirty-one actual-report corruptions are rejected. Fourteen
independent original wx/EOS cases cover overload for every pair. A separate original
desktop editing witness retains Offline guns' vacant slots and their exact zero
scalar kinds. Two fresh exports of each reference agree. Seven original host tests,
eleven fixture/type tests and eighteen source/asset/recovery regressions pass.

Three native harness/input failures and a missing-witness staging failure remain
recorded. Exact source guards and three separately validated recoveries preserve
all 147 inherited inputs, revisions, metadata and EOS statistics. The original
resource fixture and app APK remain byte-identical; the sole new test asset is the
independently verified edited witness. Reported hashes match retained verified APK
bytes; packaged/reference bytes match after CRLF-to-LF normalization only. No
assertion, tolerance, timeout, restart or A10 requirement was weakened.

Complete failed instrumentation logs, partial stores and APKs are retained. The
first optional shared failure PNG/logcat were overwritten by the second failure
and are explicitly unavailable, never passing evidence. Later diagnostics are
archived by hash. Required passing screenshots are intact. Four provisional
fighter/over-hardpoint cases use isolated real EOS diagnostics; C05 editor and
fighter persistence are not claimed.

Next selected outcome: **C01.3 defenses and tank** (F05.16–F05.27).
C01.2 is closed in [PR #37](https://github.com/Sussic/Pyfa-android/pull/37).
Keep the parent active until defenses and tank acceptance both pass.

## Previous deliveries

B09.2 [PR #35](https://github.com/Sussic/Pyfa-android/pull/35) merged as `7b780c51`
from reviewed head `c7cbb8af`; trees match. [Receipt](evidence/b09-2-native.json)
records 88 local gates, 60 native executions, 147 fits, 146 reviewed screenshots,
28 cases/168 states and preserved failures. Its 39 supported history actions and
seven boundaries remain covered; later mutations must extend their disposition.
B09.1 [PR #33](https://github.com/Sussic/Pyfa-android/pull/33) merged as `3143d771`
from `9b586d89`, with matching trees and [receipt](evidence/b09-1-native.json).
W02 [setup](tasks/W02-windows-local-verification.md) remains delivered. Both hosted
workflows are deliberate manual fallbacks; no Actions success is represented by
these local results. No owner configuration step currently remains.

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

## Resume and limits

Read AGENTS, [ROADMAP](ROADMAP.md), the selected task and ignored
`build/WINDOWS-CHECKPOINT.md`; verify live master/open PRs and preserve local work.
Use only Sussic/Pyfa-android. [Local commands/evidence](LOCAL-VERIFICATION.md) apply.
Reuse `build/windows-env.ps1`: Python3.11.9 reference/headless, JDK17.0.20.1+1,
SDK36/build35, Gradle8.13 and installed WHPX. No timed host suite alongside Gradle.
Keep every inherited functional/type/unit/GC/restart/performance/screenshot gate.

Build **30** is the latest locally emulator-tested development build; the debug
APK is `android/app/build/outputs/apk/debug/app-debug.apk`. Forecasts for remaining
implementation are unknown. A working APK is not full Pyfa parity. User usability,
ARM64 execution, older APIs, signing/upgrades and safe persistent phone use remain
unverified. No release or phone installation occurs.

Retain Kotlin/Compose + Chaquopy + serialized EOS within A10; follow
[scope](SCOPE.md), [architecture](ARCHITECTURE.md) and [evidence](DEVELOPMENT.md).
Desktop pin `8b04f3b271e614b3e103853b44a7851a63d79d0e`, tree
`8db82315f8312b124dd24ef103e43496cee50b4a`; logical dataset
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
EOS owns an exclusive in-memory session; separate locked SQLite stores declarative
graphs atomically. Navigation preferences remain separate; preserve invalid files.
Desktop `gamedataCache=False`. Host Logbook1.7.0.post0/SQLAlchemy1.4.50/Greenlet3.0.3,
Android Greenlet3.0.1 build1/chaquopy-libcxx180000 build0 remain pinned.

Both ABIs are packaged; native report transport requires API31+, app minSdk24.
I05 transfer, R02 upgrade/signing, R03 usability, C07 complete implant profiles and
Q07 full linked-effect matrices retain scope. Older builds reject newer fields and
preserve storage. Legacy tox remains unaudited; A10 is a debug-emulator baseline.
History is session-local; saved inputs persist. Full parity remains unproven.
