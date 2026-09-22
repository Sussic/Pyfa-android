# Android project status

Updated: 2026-09-22. No implementation task is active.

## B03.2 delivered; exact next task B04

- **B03.2 — Library organization and open-fit navigation** is delivered in
  [PR #15](https://github.com/Sussic/Pyfa-android/pull/15), merged as
  `60582d91a6cc1cb2cd8c4584478ae913d7b6ce90`. Tested head: `dc3565433048a142f5a919eb37279ee25868f497`.
  B03.1 and B03.2 are done, so parent **B03 is done**.
- Offline hull group/race browsing, hide/show empty groups and hulls, back-to-hull
  navigation, recently modified fits, ordered open views, close one/all and
  opt-in restart restoration are implemented. Opening/switching does not count
  as editing. Closing a view preserves the saved fit. Older saves retain unknown
  historical edit order. Search navigation clears keyboard focus.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35679131050) passes **78 tests**, all independent calculation
  references/repeats, the new desktop catalogue/repeat and real migration/backup.
  The independent unmodified Market catalogue matches **55 groups / 437 hulls**.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35679131057) passes APK builds, lint, signing, complete package
  inspection and **17 offline native executions** on API 36 x86_64. Four new
  processes verify three restart boundaries and 546 desktop statistics with exact
  scalar types/units. All 13 earlier executions remain required and pass.
- Eleven screenshots reviewed, including hulls/recents/open/closed views and the
  rename keyboard. Earlier attempts exposed nested test scrolling and a Compose
  test-dispatcher layout exception; the same checks now pass without relaxed
  assertions/timeouts.
  [Task, audit and fixes](tasks/B03-fit-library.md),
  [raw evidence, screenshots and provenance](evidence/b03-2-native.json).
- Local installed environment also passed 78 host tests, references/repeats,
  migration/backup, APK/test builds, lint, signing and package inspection. No
  local emulator/phone execution is claimed. EOS formulas, numerical fixtures,
  architecture, dependency pins, billing and artifact policy are unchanged.
- **Exact next task: B04 — Equipment browser and fitting.** It is ready and has
  not started. B03.2 authorization ends here; no release or phone installation.
  14 of 73 leaf work items are done; 59 remain, plus five parent rollups.

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

Keep all **78 host tests and 17 native executions**, independent raw-value
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

A01–A10 and B01–B03.2 are delivered. Historical task details, PR links and raw
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
