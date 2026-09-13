# Android project status

Updated: 2026-09-13.

## Baseline and goal

- Personal fork: <https://github.com/Sussic/Pyfa-android>, default branch `master`.
- Desktop oracle remains unmodified source
  `8b04f3b271e614b3e103853b44a7851a63d79d0e`, tree
  `8db82315f8312b124dd24ef103e43496cee50b4a`. It matched upstream master on
  2026-09-12 and includes changes after v2.68.0; do not substitute that binary.
- Goal: personal offline Android Pyfa with full feature parity and usable bulk
  edits. A06's Android shell is built and natively tested; EOS has not run on
  Android yet.
- [Scope](SCOPE.md), [architecture](ARCHITECTURE.md), [development rules](DEVELOPMENT.md)
  and root AGENTS.md govern work. The inherited test suite is not a verified oracle.

## Delivered work

- Setup: agent instructions, scope, architecture, bounded roadmap and evidence rules.
- **A01:** [PR #1](https://github.com/Sussic/Pyfa-android/pull/1), reproducible pinned
  data and desktop reference: 38 statistics in three ammunition states, eight
  utility tests, Linux/Windows agreement. [Commands/evidence](../../tools/android_reference/README.md).
- **A02:** [PR #2](https://github.com/Sussic/Pyfa-android/pull/2), [239 parity rows](PARITY.md)
  across 23 families and an [audit of 162 source surfaces](PARITY_AUDIT.md).
  The roadmap has 72 work items plus four parent rollups. All Android evidence
  slots remain empty; partial desktop evidence is labeled explicitly.
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

## A06 completed and delivered

- [PR #6](https://github.com/Sussic/Pyfa-android/pull/6) merged as
  `07ecf9f6c4f5412232f0ea2e49f201096b1bb9b4` after the final
  [native CI run](https://github.com/Sussic/Pyfa-android/actions/runs/34763124199)
  passed. Tested head: `b7bf3d14786b6f9ed6693fcba41bfa6c727179b1`.
- [Android project, pinned toolchain and commands](../../android/README.md):
  Kotlin/Compose shell, honest unavailable fitting status and versioned About
  screen. No Internet permission. The original GPL license is verified inside
  the development APK. Existing EOS, adapter, host fixtures and CI are unchanged.
- Built and installed a **10,334,009-byte APK** on a fresh Android 16 / API 36
  x86_64 emulator. Networking was disabled before installation. **Two native tests
  passed** with zero failures/errors/skips: navigation, activity recreation,
  landscape scrolling and Back behavior. Three actual Android screenshots were
  retained and visually reviewed. [Evidence receipt](evidence/a06-native.json).
- CI pins actions, verifies KVM access, uses a 25-minute timeout and branch/PR
  concurrency, and retains concise evidence for one day. No schedules, duplicate
  push runs or persistent caches. APK upload is opt-in through manual dispatch
  after successful checks; the upload dispatch itself was not exercised in A06.
- Initial setup/diagnostic issues are fixed and recorded in the evidence receipt.
  The final merge tree matches the tested head. Only documentation/evidence changed
  afterward. The shell has no EOS, bundled game data or saved fits, and establishes
  no Android calculation parity, ARM64 runtime or physical-phone result.

## Current work and exact next task

- No active task; A06 is delivered. **A01–A06 are done: 6 of 72 work items;
  66 remain**, plus four
  parent rollups. ROADMAP owns task state; PARITY owns behavior/evidence rows.
- Exact next task: **A07 — Bundle data and boot EOS on Android**. A fresh offline
  launch must calculate A01 through embedded Python, with an x86_64 native test
  and verified ARM64 package contents. Keep desktop expectations independent.
  A08/A09 then run projection/command fixtures on Android. Continue one task at a time.

## Open questions and environment notes

- Host dependencies are Python 3.11, Logbook 1.7.0.post0, SQLAlchemy 1.4.50 and
  Greenlet 3.0.3. Chaquopy 17.0.0 / Python 3.11 is provisional, not packaged yet.
  Android wheels/ABIs, engine latency/memory and full-data APK size remain unknown;
  A07–A10 own those checks. Extend native CI path filters when EOS is bundled.
- Q07 still needs full projection/command stacking and cycle cases. Lazy GUI
  imports remain in some EOS makeRoom helpers. A05 avoids them with vacant-slot
  implant addition; C07 owns complete replacement/set/location behavior.
- The exact phone model/API level is unconfirmed; this does not block host or
  emulator work. A06 declares minSdk 24 but has tested runtime only on API 36.
- Lint reports one missing-data-extraction-rules warning. Storage/upgrade tasks
  must define backup/transfer behavior before persistent-use releases. Stable
  signing and upgrade preservation remain R02 work.
- This workspace lacked KVM and local Java SDK downloads failed. Native build,
  installation and tests succeeded on GitHub's Ubuntu runner; no local APK build
  is claimed. Use A06's reproducible workflow and recorded toolchain.
- Scratch runtimes and temporary databases can expire between sessions. Verify
  paths before reuse and rebuild from A01 if absent. An earlier workspace DB
  failed integrity for an unproven reason; fresh `/tmp` builds passed. Every
  verifier checks integrity/logical data identity; do not reuse corrupt data.

## Resume

Read AGENTS.md and this file; verify live master and open PRs, then select A07.
Read the Android build instructions and headless adapter boundary, verify real
Android wheels and package the pinned data. Preserve independent EOS expectations
and host checks. Do not mistake the native shell for full Android fitting parity.
