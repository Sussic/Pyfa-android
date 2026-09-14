# Android project status

Updated: 2026-09-14.

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

## A07 completed and delivered

- [PR #7](https://github.com/Sussic/Pyfa-android/pull/7) merged as
  `6fcd50fcca9911aca1d0871fc89b26f671fe0350`. Tested head:
  `a4182bd17462dbfe79ddf0dde8cb700429fa89cb`; the merge tree matches it.
- [Android native CI](https://github.com/Sussic/Pyfa-android/actions/runs/34846081342)
  passed build, lint, signing, source/data/ABI inspection and **three native tests**.
  A fresh API 36 x86_64 installation, with networking disabled before install,
  calculated the A01 Vexor: **38 raw statistics and units in three ammunition states**
  match the untouched independent desktop fixture. Both guns change together;
  drone control range is visible. Four native screenshots were reviewed.
- APK: **70,361,140 bytes**. Bundled database: **99,897,344 bytes**, matching A01's
  logical digest. Both ARM64 and x86_64 packages contain the required native code:
  73 ELF libraries per ABI with dependency closure checked. **ARM64 was not run.**
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/34846081350)
  passed 35 host tests, independent A01/A04/A05 comparisons and real 48-to-49
  migration/backup compatibility. One new upstream correction uses a proper
  `fromlist` list in migration imports; formulas and expected fixtures are unchanged.
- [Commands and dependency decisions](../../android/README.md),
  [durable raw values/provenance/evidence](evidence/a07-native.json).
  Native Python is 3.11.14 (build host 3.11.16); pure Logbook/SQLAlchemy and pinned
  Android Greenlet/libc++ wheels work for this baseline. Data is read-only, fits
  remain in memory, and a process-owned Kotlin worker serializes engine calls.
- This is a sample fitting milestone, not the full editor. Native projections,
  commands, saved-fit persistence, process restart/upgrade behavior and physical
  phone operation remain unverified. APK upload is still manual opt-in.

## Current work and exact next task

- No active task; A07 is delivered. **A01–A07 are done: 7 of 72 work items;
  65 remain**, plus four parent rollups. ROADMAP owns task state; PARITY owns
  behavior/evidence rows. A07 baseline evidence is partial where rows require more.
- Exact next task: **A08 — Android projection parity**. Run A04's independent
  linked Celestis/Vexor cases through the Android bridge, including range/script
  edits, removal/restoration and stale-cache checks. Keep the fixture independent
  and preserve the passing A07 offline/ammunition/native package checks.
- A09 then verifies command bursts on Android. Continue one task at a time.

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

Read AGENTS.md and this file; verify live master and open PRs, then select A08.
Read Android build instructions and the A04 projection fixture/adapter boundary.
Reuse the verified source/data/wheel pipeline and existing background worker.
Expected values stay in the test APK. Keep A01 checks and add real Android
projection assertions; host projection results alone do not close A08.
