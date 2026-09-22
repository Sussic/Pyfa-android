# Android project status

Updated: 2026-09-22. B04.1 delivered; exact next task **B04.2 — Fitting editor and item history**.

## Current authorized work

- Explicit chat confirmation supersedes the earlier B03.2 stopping instruction.
  Continue B04, then sequential eligible approved roadmap tasks, one outcome at
  a time, including required checks, review and PR merges. No releases, phone
  installs, billing changes or unrelated work.
- **B04.1 — Offline equipment discovery** is delivered in
  [PR #16](https://github.com/Sussic/Pyfa-android/pull/16), merged as
  `794f4b1c80f714432d8dff8709d8e33682bfbf00`. Tested head: `6f53682807372d82b610b15d3ee57b64a8ebeee3`.
- Browse all bundled desktop market groups and published/forced items, search
  words/wildcards/regex/default jargon, filter meta variants, page results and
  jump to an item's group. Browser state survives activity recreation. Reads
  preserve saved fits and modification order; EOS owns all data on its worker.
- Independent pinned desktop export and fresh-process repeat exactly match
  **718 groups, 6,822 items and 22 searches**. Raw IDs/types/memberships are exact.
  [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35741516902)
  passes **84 host tests**, independent references/repeats and migration/backup.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35741516907)
  passes APK/test builds, lint, signature, source/data/ABI package inspection and
  **18 offline native executions** on API 36 x86_64. All prior numerical,
  persistence/restart and forced-GC gates remain required and pass.
- All **16 screenshots** reviewed. Review tightened numeric-type validation and
  reduced equipment-screen spacing; final CI tests those changes. Local focused
  evidence covers the new six host tests, eight utilities, independent export/
  repeat, APK builds/lint/signature/package checks. Full 84-test evidence is CI.
  [Task/audit](tasks/B04-equipment-fitting.md),
  [raw evidence, screenshots and provenance](evidence/b04-1-native.json).
- **B04.2** retains arbitrary-hull creation, module/rig/service edits, compatible
  charges/scripts/crystals, reorder/variations, restrictions/legality and actual
  persistent recent-item use. Discovery is partial F02.01; B04 remains active.
  15 of 74 leaf tasks are done; 59 remain, plus six rollups.
- B03.2 remains delivered in [PR #15](https://github.com/Sussic/Pyfa-android/pull/15)
  (`60582d91a6cc1cb2cd8c4584478ae913d7b6ce90`);
  [its task](tasks/B03-fit-library.md) and
  [receipt](evidence/b03-2-native.json) retain historical evidence.

## Resume and installed environment

Read AGENTS, this file, [ROADMAP](ROADMAP.md) and the authorized task. Check local
changes, live fork master and open PRs before writing. Work only in
[Sussic/Pyfa-android](https://github.com/Sussic/Pyfa-android).

Dot-source `. ./build/windows-env.ps1`. Reuse Python 3.11.9 x64 in separate
`.venv/headless` and `.venv/reference`, Temurin 17.0.20.1+1, Gradle 8.13,
SDK platform 36 revision 2 and Build Tools 35.0.0. The Gradle cache lives in local
AppData outside OneDrive. [Windows guide](WINDOWS.md) has commands; the local
`build/WINDOWS-CHECKPOINT.md` records receipts and continuation details. Do not
replace the installed environment or run timed host suites alongside Gradle.

Keep all **84 host tests and 18 native executions**, independent raw-value
validators, process restarts, forced-GC regressions and screenshot review.
Native CI uses Ubuntu/KVM; the local Windows setup does not claim native runtime
coverage. One-day diagnostics retention, deliberate APK uploads only, no scheduled
runs or automatic releases remain the policy.

## Architecture and comparison target

- Kotlin/Compose + Chaquopy + serialized EOS remain the A10 decision. Use the
  [scope](SCOPE.md), [architecture](ARCHITECTURE.md) and
  [evidence rules](DEVELOPMENT.md). Do not approximate fitting formulas in Kotlin.
- Independent desktop source: `8b04f3b271e614b3e103853b44a7851a63d79d0e`, tree
  `8db82315f8312b124dd24ef103e43496cee50b4a`. Do not substitute a release binary.
  Logical dataset SHA-256:
  `5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
- EOS retains an exclusive in-memory session. Durable declarative inputs live in
  the separate locked SQLite graph store. Graph format 1 is nonempty; format 2
  means intentionally empty. Existing files are never replaced by a sample.
  Optional edit-order metadata commits with inputs. Navigation preferences use a
  separate atomic file; invalid preferences are preserved with session-only use.
- Host pins remain Logbook 1.7.0.post0, SQLAlchemy 1.4.50, Greenlet 3.0.3.
  Android uses Greenlet 3.0.1 build 1 and chaquopy-libcxx 180000 build 0;
  all six Android wheels are pinned and verified.

## Prior delivery and remaining limits

A01–A10, B01–B03.2 and B04.1 are delivered. Historical task details, PR links and raw
receipts remain in [ROADMAP](ROADMAP.md), the task briefs and
[evidence](evidence). Windows setup was delivered in
[PR #14](https://github.com/Sussic/Pyfa-android/pull/14). All **239 parity rows**
remain in [PARITY](PARITY.md); no full-feature or user-usability sign-off is claimed.

Creation still uses Vexor/Celestis/Vulture fixtures; arbitrary hull/equipment
editing remains B04/C work. Physical ARM64 and older APIs have not run; package
contents support both ABIs. The phone model/API is unconfirmed. Native report
transport currently needs API 31+, while the app declares minSdk 24.

User backup/transfer remains I05; stable signing and install-over-existing-data
upgrade/downgrade checks remain R02; usability sign-off remains R03. New graph
metadata is rejected by older builds. Q07 retains complete projection/command
stacking/cycle cases; C07 retains complete implant replacement/location behavior.
Legacy tox tests remain unaudited, including missing paths and early-return
placeholders; they are not part of the passing evidence. Recheck integrity and
logical dataset identity before reusing temporary databases.

A10 measurements are bounded debug/emulator baselines, not phone/release or peak
memory guarantees. With restore disabled, subsequent normal launches now draw
the library without an active view, while EOS still rebuilds saved fits. Do not
compare those whole-launch times directly with A10's ready-fit baseline.
