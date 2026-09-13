# Android project status

Updated: 2026-09-13.

## Baseline and goal

- Personal fork: <https://github.com/Sussic/Pyfa-android>, default branch `master`.
- Desktop oracle remains unmodified source
  `8b04f3b271e614b3e103853b44a7851a63d79d0e`, tree
  `8db82315f8312b124dd24ef103e43496cee50b4a`. It matched upstream master on
  2026-09-12 and includes changes after v2.68.0; do not substitute that binary.
- Goal: personal offline Android Pyfa with full feature parity and usable bulk
  edits. No APK, Android project or native runtime result exists yet.
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

## A04 completed and delivered

- [PR #4](https://github.com/Sussic/Pyfa-android/pull/4) merged as
  `4ab6b75fa29e4eccfb395369417c7f23c0ee8f22` after the first
  [Windows CI run](https://github.com/Sussic/Pyfa-android/actions/runs/34759292301)
  passed. Tested head: `ef0950fc78168ea9fe77a4792bf741e0c377c353`.
- [Independent desktop case and evidence](../../tools/android_reference/PROJECTIONS.md):
  a Celestis applies a scripted dampener to a Vexor. Both fits' 39 raw statistics
  match across 11 stages, including distance, inactive/active state, source script
  changes, removal and reapplication. Fresh processes match on both platforms.
- [Adapter](../../android_bridge/README.md) uses EOS projection relationships and
  in-memory IDs. Snapshots refresh invalidated recipients; removal clears the
  reverse relationship. Eight new tests include two recipients and repeated
  removal. No extra upstream patch, formula change or A01 expectation change.
- Linux and Windows passed all 18 headless behavioral tests, eight reference
  utility tests, independent A01/A04 desktop comparisons and the genuine desktop
  48-to-49 migration/backup regression. No headless desktop imports or network
  attempts occurred, and game-data bytes remained unchanged.
- Normalized code/input/fixture and logical data hashes agree across platforms.
  CI evidence records its actual PR merge checkout. Only evidence/documentation
  changed after the passing run. This establishes one host projection case;
  full projection families, stacking/cycles and Android execution remain unverified.

## Current work and exact next task

- Active task: **A05**, on `android/a05-command-reference`. Live master verified
  at `c48f18dd04fcbc87587aed99a5f8e9a1d9bd0a93`; no open PRs.
  **A01–A04 are done: 4 of 72 work items; 68 remain**, plus four
  parent rollups. ROADMAP owns task state; PARITY owns behavior/evidence rows.
- Intended outcome: **A05 — command-burst reference cases**. Build an independent pinned
  booster/recipient case covering source skills, implants and state changes;
  compare through the adapter and restore baseline on disable/removal.
- A06 is also ready, but continue the queue one task at a time. It introduces the
  Android skeleton and native CI; A07–A09 establish actual engine/ABI parity.

## Open questions and environment notes

- Host dependencies are Python 3.11, Logbook 1.7.0.post0, SQLAlchemy 1.4.50 and
  Greenlet 3.0.3. Their Android wheels/ABIs, phone latency/memory and APK size are
  not established. A07–A10 own those feasibility checks.
- Q07 still needs full projection/command stacking and cycle cases. Lazy GUI
  imports remain in some EOS makeRoom helpers; investigate the actual A05 path.
- The exact phone model/API level is unconfirmed; this does not block host or
  emulator work. SDK/toolchain pins belong to A06.
- Scratch runtimes and temporary databases can expire between sessions. Verify
  paths before reuse and rebuild from A01 if absent. An earlier workspace DB
  failed integrity for an unproven reason; fresh `/tmp` builds passed. Every
  verifier checks integrity/logical data identity; do not reuse corrupt data.

## Resume

Read AGENTS.md and this file; verify live master and open PRs, then select A05.
Read its relevant EOS/desktop sources and keep expected results independent of the
adapter. Do not restart prior research, implement the whole roadmap at once, or
mistake host tests for an Android build.
