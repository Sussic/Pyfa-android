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

- **A04:** [PR #4](https://github.com/Sussic/Pyfa-android/pull/4), linked Celestis
  dampener reference: 39 statistics per fit in 11 stages, eight projection tests,
  two recipients and removal cleanup. [Details/evidence](../../tools/android_reference/PROJECTIONS.md).

## A05 completed and delivered

- [PR #5](https://github.com/Sussic/Pyfa-android/pull/5) merged as
  `ac3eb238e2314b7afee08f5c1d8c5d8628fe44af` after the first
  [Windows CI run](https://github.com/Sussic/Pyfa-android/actions/runs/34760339495)
  passed. Tested head: `96d8d4749c9723f89f60b1cee66a551a2b7ece39`.
- [Independent command case and evidence](../../tools/android_reference/COMMANDS.md):
  a Vulture applies Shield Extension/Harmonizing to a Vexor. Both fits' 39 raw
  statistics match in 19 stages, covering two skills, mindlink addition/state/
  removal, module/link toggles, charge changes and repeated command removal.
- [Adapter](../../android_bridge/README.md) adds command links and validated skill,
  fit-local implant and module-state edits. EOS performs every calculation and
  recipient invalidation. Removed links clear their reverse association. No
  upstream patch or A01/A04 fixture/exporter changes were needed.
- Linux and Windows passed **27 headless behavioral tests** (10 ammunition,
  8 projection, 9 command), eight reference utility checks, the independent A05
  reference and real desktop 48-to-49 migration/backup regression. Windows also
  rebuilt A01 data and rechecked A01/A04 desktop references. Fresh processes match.
- No headless desktop imports or network attempts occurred; game-data bytes were
  unchanged. Normalized source/input/fixture and logical data hashes agree across
  platforms. CI evidence identifies its actual PR merge checkout. Only evidence
  and documentation changed after the passing run.
- This is one host command case. Full burst coverage, command overlap/cycles,
  persistence, UI behavior and Android execution remain unverified.

## Current work and exact next task

- No task active. **A01–A05 are done: 5 of 72 work items; 67 remain**, plus four
  parent rollups. ROADMAP owns task state; PARITY owns behavior/evidence rows.
- Next: **A06 — Android skeleton and native CI**. Pin the toolchain, build an
  installable APK and run an emulator test containing a real app assertion.
  Configure deliberate APK delivery, concurrency, timeouts and retention within
  existing limits. This skeleton does not yet claim EOS calculation parity.
- A07 then bundles data and boots EOS on Android; A08/A09 run the established
  projection/command fixtures on Android. Continue one task at a time.

## Open questions and environment notes

- Host dependencies are Python 3.11, Logbook 1.7.0.post0, SQLAlchemy 1.4.50 and
  Greenlet 3.0.3. Their Android wheels/ABIs, phone latency/memory and APK size are
  not established. A07–A10 own those feasibility checks.
- Q07 still needs full projection/command stacking and cycle cases. Lazy GUI
  imports remain in some EOS makeRoom helpers. A05 avoids them with vacant-slot
  implant addition; C07 owns complete replacement/set/location behavior.
- The exact phone model/API level is unconfirmed; this does not block host or
  emulator work. SDK/toolchain pins belong to A06.
- Scratch runtimes and temporary databases can expire between sessions. Verify
  paths before reuse and rebuild from A01 if absent. An earlier workspace DB
  failed integrity for an unproven reason; fresh `/tmp` builds passed. Every
  verifier checks integrity/logical data identity; do not reuse corrupt data.

## Resume

Read AGENTS.md and this file; verify live master and open PRs, then select A06.
Read the native build scope and verify current official toolchain/package support
when selecting pins. Preserve independent EOS expectations and all existing host
checks. Do not implement the whole roadmap at once or mistake an app skeleton for
full Android fitting parity.
