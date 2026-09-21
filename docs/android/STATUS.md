# Android project status

Updated: 2026-09-21.

## Windows setup checkpoint (complete, 2026-09-21)

- `SETUP-WINDOWS`: branch `android/windows-development-setup`, based on
  `6ba3412ccf069ea5d051f0d0cd8b463b36f234b5` (`origin/master`). The folder was
  empty; cloned only the personal fork. Delivery review confirmed the base is still
  current and no setup PR exists to reuse. Scope: seven documentation files only;
  runtime sources, fixtures, build pins and CI requirements are unchanged. Check
  the branch PR for live checks/merge state, not this pre-merge checkpoint.
- Ready: Python 3.11.9 x64 in separate `.venv/headless` and `.venv/reference`,
  Temurin 17.0.20.1+1, verified Gradle 8.13 wrapper, SDK platform 36 revision 2,
  Build Tools 35.0.0. Gradle cache is in local AppData, outside OneDrive.
- Repository scripts prepared all six Android wheels and the pinned engine data.
  Debug/instrumentation APK builds, lint, signature and full data/source/ABI
  inspection pass. Debug APK: `android/app/build/outputs/apk/debug/app-debug.apk`
  (70,547,211 bytes); both ABIs contain 73 native libraries.
- **73 host tests pass**, plus all independent desktop references/repeats and
  real migration/backup. An initial concurrent persistence attempt had errors and
  was interrupted; all 14 tests then passed in isolation with their original
  assertions/timeouts and required count intact. The exact initial cause is unproven.
- No local setup blocker. The **13 native runtime executions remain CI checks**;
  none were run locally. The reference README path triggers both existing PR
  workflows; require their successful completion before merging this setup PR.
  No phone install, feature work, release or CI-policy change.
- Reproduce with [Windows setup](WINDOWS.md); dot-source `build/windows-env.ps1`.
  Final local delivery receipt: `build/WINDOWS-CHECKPOINT.md`. Build receipts/logs:
  `android/build/evidence/`; host outputs are located by
  `build/windows-check-path.txt`. Setup/workflow documentation and AGENTS are repaired.
- Exact next development action, when feature work is authorized: read B03's
  desktop organization audit and F01.03–F01.05, then begin **B03.2**. Its status and
  all acceptance checks remain unchanged; this bounded setup ends here.
- Fresh chat: open this workspace, read AGENTS, STATUS, ROADMAP and WINDOWS,
  check live `origin/master`, local changes and open PRs, then dot-source
  `. ./build/windows-env.ps1`. Start B03.2 only with explicit feature authorization;
  its brief is [B03](tasks/B03-fit-library.md) and its inventory is [PARITY](PARITY.md).

## Baseline and goal

- Personal fork: <https://github.com/Sussic/Pyfa-android>, default branch `master`.
- Desktop oracle remains unmodified source
  `8b04f3b271e614b3e103853b44a7851a63d79d0e`, tree
  `8db82315f8312b124dd24ef103e43496cee50b4a`. It matched upstream master on
  2026-09-12 and includes changes after v2.68.0; do not substitute that binary.
- Goal: personal offline Android Pyfa with full feature parity and usable bulk
  edits. A07 calculates its baseline fit through EOS offline on Android; full
  feature parity remains the goal.
- [Scope](SCOPE.md), [architecture](ARCHITECTURE.md), [development rules](DEVELOPMENT.md)
  and root AGENTS.md govern work. The inherited test suite is not a verified oracle.

## Delivered work

- Setup: agent instructions, scope, architecture, bounded roadmap and evidence rules.
- **A01:** [PR #1](https://github.com/Sussic/Pyfa-android/pull/1), reproducible pinned
  data and desktop reference: 38 statistics in three ammunition states, eight
  utility tests, Linux/Windows agreement. [Commands/evidence](../../tools/android_reference/README.md).
- **A02:** [PR #2](https://github.com/Sussic/Pyfa-android/pull/2), [239 parity rows](PARITY.md)
  across 23 families and an [audit of 162 source surfaces](PARITY_AUDIT.md).
  The roadmap has 72 work items plus four parent rollups. At A02, Android evidence
  slots started empty; partial desktop evidence is labeled explicitly.
- **A03:** [PR #3](https://github.com/Sussic/Pyfa-android/pull/3), minimal headless
  EOS session, read-only data, group ammunition edits and ten behavioral tests.
  Lazy desktop config import preserves real migration backups. [Details/evidence](../../tools/android_headless/README.md).

- **A04:** [PR #4](https://github.com/Sussic/Pyfa-android/pull/4), linked Celestis
  dampener reference: 39 statistics per fit in 11 stages, eight projection tests,
  two recipients and removal cleanup. [Details/evidence](../../tools/android_reference/PROJECTIONS.md).

- **A05:** [PR #5](https://github.com/Sussic/Pyfa-android/pull/5), Vulture command
  bursts applied to a Vexor: 39 raw statistics per fit across 19 stages. Adapter
  edits cover links, skills, implants and module states. Linux/Windows passed
  **27 headless tests**, eight utility checks and the real desktop migration/backup
  regression. [Command case and evidence](../../tools/android_reference/COMMANDS.md).

- **A06:** [PR #6](https://github.com/Sussic/Pyfa-android/pull/6), native Compose
  shell, offline About/navigation/recreation tests and build/CI setup.
  [Historical receipt](evidence/a06-native.json).

## A07–A10 completed and delivered

- **A07:** [PR #7](https://github.com/Sussic/Pyfa-android/pull/7) embedded EOS and
  the pinned dataset. A01's 38 statistics in three ammunition states passed
  offline on Android; both guns change together and drone control range is visible.
  [Historical native/Windows evidence](evidence/a07-native.json) records the
  dependency decisions, two upstream compatibility patches and limitations.
- **A08:** [PR #8](https://github.com/Sussic/Pyfa-android/pull/8) established native
  A04 projection parity: 39 statistics per fit in 11 states, multiple recipients,
  repeated removal and same-worker reuse. [Historical evidence](evidence/a08-native.json).
- **A09:** [PR #9](https://github.com/Sussic/Pyfa-android/pull/9) merged as
  `bba96d3d74c5bbc3441f4180e1010a57d5db10e3`. Tested head: `e5e249b9ac95b9144d16f99de4801473661ffa05`.
  [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35161269681) passed build, lint, signing,
  source/data/ABI inspection and **five native tests** on a fresh offline
  API 36 x86_64 installation, with no failures, errors or skips.
- A05's unchanged desktop fixture matches **39 raw statistics and units on each
  of two fits across 19 command states**: source skills, mindlink changes,
  burst/module/link state, charges and removal/reapplication. Eighteen additional
  phases verify two recipients and an unlinked control, reading recipient two first.
  Five apply/remove cycles verify both link directions and restored values;
  all 112 pending-command-bonus observations are empty. The full probe repeats on
  the same worker, then A01 ammunition and A04 projection comparisons pass again.
- Host checks passed nine command regression tests with independent fixture
  comparison/fresh-process repeat, eight reference utility tests and the mobile
  runtime sequence. Independent code review found no blocker. EOS, the adapter,
  golden fixtures, dependency versions and CI storage/billing policy are unchanged.
- [A09 task and limits](tasks/A09-android-command-parity.md),
  [raw native values, JUnit and provenance](evidence/a09-native.json),
  [build/test commands](../../android/README.md).
- This proves the bounded A05 Vulture case. The UI remains the Vexor ammunition
  sample; D03/C06/C07/C09 retain the editors, other bursts, shared profiles,
  overlapping sources and interactions. ARM64 package contents are verified;
  ARM64 execution, physical phones, persistence and upgrades remain unverified.

## A10 result

- **A10:** [PR #10](https://github.com/Sussic/Pyfa-android/pull/10), merged as
  `7d16aa226df1b80e5e2f21740ac2587b3e0ac1f3`; tested head `ca331deb09756e3d3ccaec175a16dd52553746aa`.
  [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35288937092) and
  [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35288937029) pass on the first run.
- Decision: **retain Kotlin/Compose + Chaquopy + serialized EOS** for B01.
  Normal debug/emulator process-to-ready-draw: 2.960 s first install, 2.008 s
  median of four subsequent process launches. Edit medians: 10.258 ms ammunition,
  21.703 ms projection range, 60.421 ms projection links, 35.950 ms command charge,
  60.140 ms command links; two recipients for graph operations.
- Normal ready-fit PSS is 154.1–184.8 MiB. Instrumented cumulative snapshots with
  nine retained fits reach 231.3 MiB at command setup and 200.5 MiB after edits;
  these are not peaks or a leak test. Dual-ABI debug APK: 70,395,255 bytes.
- Fixed source modules losing calculated bonuses after ORM relationship refresh:
  recalculate sources in all four projection/command add/remove paths. Two forced-GC
  regressions fail before and pass after the fix. EOS formulas/fixtures stay unchanged.
- Five native functional tests plus one separate performance test pass; 100 measured
  edits, 20 warmups and three setups all match the independent desktop fixtures.
  Windows passes all 37 host tests, independent references and real migration/backup.
  Local 29 headless tests, eight utilities and 123 benchmark snapshots also pass.
- [Decision/method/limits](tasks/A10-embedding-feasibility.md) and
  [durable raw evidence](evidence/a10-native.json). ARM64 contents are verified;
  physical/ARM64/older-API execution, release performance and large/long-lived graphs
  remain unverified. This is feasibility, not full Pyfa parity or usability sign-off.

## B01 result

- **B01:** [PR #11](https://github.com/Sussic/Pyfa-android/pull/11), merged as
  `edca0e795aa086edd90db1bf5f216dcd1c704c53`. Tested head: `3963d553193b9983c464bd51bb99cdeeabe15f5b`.
- Typed versioned Kotlin/Python operations carry raw values/units, stable fit IDs,
  revisions and structured errors. Successful mutations update transitive recipients
  together; failed edits rebuild the committed graph. Unknown transport outcomes or
  failed recovery make the session unavailable until restart, preserving the last valid UI fit.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35295023667) passes build/lint/signing/package checks and
  **seven native tests**: original five, separate A10 performance, separate B01 contract.
  B01 compares 63 desktop snapshots × 39 raw statistics with exact scalar types/units,
  checks stale revisions, queued bulk edits, partial-create recovery and 15 codec rejections.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35295023583) passes **51 host tests** (29 existing,
  14 contract, eight reference utilities), all independent references and real migration/backup.
  An initial runner encoding error was fixed with explicit UTF-8; fixture checks were preserved.
  Local mobile recovery plus all 123 benchmark observations also pass. EOS formulas,
  the headless adapter, independent fixtures and all 239 parity rows remain intact.
- [Contract/task/limits](tasks/B01-typed-bridge.md) and [durable evidence](evidence/b01-native.json).
  B01 established the 39-field sample view and existing adapter edits. Full editing,
  physical/ARM64/older-API execution and usability sign-off remain later work.

## B02 result

- **B02:** [PR #12](https://github.com/Sussic/Pyfa-android/pull/12), merged as
  `9d96e0d8e8fc0fcb0a6a03023fb7cfe1a8ed8238`. Tested head: `225d0d15d8195e148aca5233c88b8b3a57086495`.
- Complete committed fit graphs now save atomically in app-private SQLite and
  reopen through EOS with stable IDs/revisions and projection/command links.
  Invalid or incompatible files are preserved; ambiguous saves require restart.
  Existing direct-engine diagnostics run in isolated ephemeral processes.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35389186247) passes build/lint/signing/package checks and **ten native
  test executions**: original five, A10 performance, B01 contract and three B02
  phases. Nine fits persist through two process restarts; 45 snapshots × 39 raw
  statistics match desktop fixtures, including types/units and two-recipient edits.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35389186269) passes **65 host tests**, all independent references and
  the real migration/backup check. Local 65 tests plus the three-process mobile
  wrapper check pass. Fourteen new fault/restart tests protect prior saves and
  confirmed newer commits. Formulas, fixtures and all 239 parity rows are unchanged.
- [Storage contract and limits](tasks/B02-local-persistence.md),
  [durable evidence](evidence/b02-native.json). Physical/ARM64/older-API execution,
  user backup/restore, dataset migration, upgrades and full fit editing remain
  unverified or assigned to later tasks.

## B03.1 completed and exact next task

- **B03.1:** [PR #13](https://github.com/Sussic/Pyfa-android/pull/13), merged as `bc6434b67846aba1bae6aa450afe5817b6560645`. Tested head `1468ab9513aa4d69cb17a48b384c27357a8d64e7`.
- Native saved-fit controls create from Vexor/Celestis/Vulture examples, search names/hulls, open, rename, independently copy and confirm/cancel deletion. Copies retain incoming linked-source identities; source deletion removes links and recalculates recipients in the same durable save.
- Last-fit deletion commits an explicit empty marker and reopening stays empty. Nonempty B02 stores retain format 1; format 2 permits only the empty graph. Fixed source-before-recipient calculation for command-source copies and Chaquopy's null sample ID on empty startup. No EOS formulas or golden values changed.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35415142241) passes every build/package gate and **13 native test executions**, including three new production-storage UI/restart phases. Ten retained two-recipient snapshots × 39 raw statistics match desktop fixtures, with exact scalar types and units. All nine pre-existing synthetic fits remain unchanged, both restart boundaries match, and empty-reopen/create/delete passes.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35415142288) and local checks pass **73 host tests**. Independent references, real desktop migration/backup and all previous native gates remain intact. Seven screenshots reviewed, including the rename keyboard and empty state.
- [Task, desktop audit and limits](tasks/B03-fit-library.md); [raw evidence](evidence/b03-1-native.json). Creation is fixture-based; full hull/equipment editing remains B04/C work. Physical/ARM64/older-API execution, backup/restore/upgrades and user usability remain unverified.
- B03 was split before implementation: B03.1 lifecycle/search is done; **B03.2 — Library organization and open-fit navigation** is ready. B03 stays incomplete until both children pass. All 239 parity rows remain.
- **13 of 73 leaf work items done; 60 remain**, plus five parent rollups. Exact next task: **B03.2** — group/race/hull browsing and empty-group visibility, recently modified fits, multiple open fits, close one/all and optional restart restoration. Continue one task at a time.

## Open questions and environment notes

- Host dependencies remain Logbook 1.7.0.post0, SQLAlchemy 1.4.50 and Greenlet
  3.0.3. Android uses Greenlet 3.0.1 build 1 and chaquopy-libcxx 180000 build 0;
  all six input wheels are pinned/verified. Do not substitute desktop native wheels.
- A10 measurements are debug/emulator baselines with explicit clock and memory
  boundaries. Do not compare earlier whole-probe timers to individual edits or
  infer physical-phone/release performance. Keep raw sample counts and stage sizes.
- Q07 still needs full projection/command stacking and cycle cases. Lazy GUI
  imports remain in some EOS makeRoom helpers. A05 avoids them with vacant-slot
  implant addition; C07 owns complete replacement/set/location behavior.
- The exact phone model/API level is unconfirmed; this does not block host or
  emulator work. The app declares minSdk 24 but runtime has been tested only on API 36.
  Native report transport uses API 31+ UI automation pipes; lower APIs need an
  appropriate evidence transport before running that suite.
- Local lint passes with `DataExtractionRules` and `UnusedResources` warnings,
  plus an `AutoboxingStateCreation` hint. B02 fit storage uses the app-private
  no-backup directory. Complete user backup/restore and transfer policy remain I05 work;
  stable signing and upgrade preservation remain R02 work.
- The earlier Linux workspace lacked KVM and had Java download failures; that
  limitation does not describe the current Windows checkout. See the Windows
  setup checkpoint above for local build/check results. Full native runtime
  evidence still uses the Ubuntu/KVM workflow; its KVM check waits for udev and
  runs before the expensive build. No physical-phone installation is part of setup.
- Scratch runtimes and temporary databases can expire between sessions. Verify
  paths before reuse and rebuild from A01 if absent. An earlier workspace DB
  failed integrity for an unproven reason; fresh `/tmp` builds passed. Every
  verifier checks integrity/logical data identity; do not reuse corrupt data.

## Resume

Read AGENTS.md and this file; verify live master/open PRs and follow the current
authorized scope. B03.2 is the next feature task; this setup does not start it.
Read B03's desktop organization audit and F01.03–F01.05 before implementation;
preserve the parent until both children pass. Recently modified fits and recently
opened fits are different concepts. Selection is currently process-local.

Preserve the lifecycle contract: new rename/copy/delete operations return the full
surviving library; older edits return affected snapshots. Fit IDs/revisions stay
stable. The engine still requires an exclusive in-memory EOS session, with durable
inputs in the separate locked graph store. Nonempty stores use graph format 1;
format 2 is exclusively the intentionally empty state. Startup results can be
null and EngineState.Empty is a valid ready state. Never reseed an existing file.

Keep all 73 host tests and 13 native executions, the three new UI/restart phases,
all prior parity/forced-GC checks, and the independent raw-value validators.
No formula, oracle-fixture or parity-inventory coverage may be removed. A10's
measurements are ephemeral engine baselines, not durable lifecycle timings.
