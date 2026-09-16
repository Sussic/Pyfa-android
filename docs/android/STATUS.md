# Android project status

Updated: 2026-09-16.

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

## A07–A09 completed and delivered

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

## Current work and exact next task

- No active task; A09 is delivered. **A01–A09 are done: 9 of 72 work items;
  63 remain**, plus four parent rollups. All 239 parity rows remain; evidence
  stays partial where rows require broader behavior or UI/persistence checks.
- Exact next task: **A10 — Decide embedding feasibility**. Measure full startup,
  edit/recalculation latency, memory and APK size for single and interacting fits.
  Record device/API/ABI details and measurement boundaries, the supported pins,
  remaining hardware gaps and an evidence-based decision to retain or revise the
  embedding approach. Reuse the A01/A04/A05 fixtures and existing native worker.
- B01 follows that decision with a typed bridge contract. Continue one task at a time.

## Open questions and environment notes

- Host dependencies remain Logbook 1.7.0.post0, SQLAlchemy 1.4.50 and Greenlet
  3.0.3. Android uses Greenlet 3.0.1 build 1 and chaquopy-libcxx 180000 build 0;
  all six input wheels are pinned/verified. Do not substitute desktop native wheels.
- A07 measured about 5.29 s for Python boot through first fit creation and 0.67 s
  for its edit/report sequence on this emulator. These exclude parts of cold
  startup and are not single-edit benchmarks. A10 owns full latency/memory work.
- Q07 still needs full projection/command stacking and cycle cases. Lazy GUI
  imports remain in some EOS makeRoom helpers. A05 avoids them with vacant-slot
  implant addition; C07 owns complete replacement/set/location behavior.
- The exact phone model/API level is unconfirmed; this does not block host or
  emulator work. The app declares minSdk 24 but runtime has been tested only on API 36.
  Native report transport uses API 31+ UI automation pipes; lower APIs need an
  appropriate evidence transport before running that suite.
- Lint reports one missing-data-extraction-rules warning. Storage/upgrade tasks
  must define backup/transfer behavior before persistent-use releases. Stable
  signing and upgrade preservation remain R02 work.
- This workspace lacked KVM and local Java SDK downloads failed. Native build,
  installation and tests succeeded on GitHub's Ubuntu runner; no local APK build
  is claimed. Use the native workflow and recorded toolchain. Its KVM check now waits for
  udev events and runs before the expensive build.
- Scratch runtimes and temporary databases can expire between sessions. Verify
  paths before reuse and rebuild from A01 if absent. An earlier workspace DB
  failed integrity for an unproven reason; fresh `/tmp` builds passed. Every
  verifier checks integrity/logical data identity; do not reuse corrupt data.

## Resume

Read AGENTS.md and this file; verify live master and open PRs, then select A10.
Read the architecture feasibility gate and concise A07–A09 task/evidence summaries.
Existing timings exclude parts of startup and are whole sequences, not individual
edit benchmarks. Add the measurements A10 needs while preserving all five native
tests. Keep ARM64 package inspection distinct from actual ARM64 execution.
