# Android project status

Updated: 2026-09-22. B04.2.1 delivered; exact next task **B04.2.2 — Module editing, legality and recent use**.

## Current authorized work

- Explicit chat confirmation authorizes B04 and then sequential eligible approved
  roadmap tasks, one outcome at a time, including review, checks and PR merges.
  No releases, phone installs, billing changes, unrelated work or delegation.
- **B04.2.1 — Arbitrary empty ship and structure creation** is delivered in
  [PR #17](https://github.com/Sussic/Pyfa-android/pull/17), merged as
  `307d5c07580c7f2f48cd7755acc63cc72c2108c9`. Tested head `645d6f45ae802fec415ed08cc0093314bbbd184b`.
- Create a named empty fit for any of **437 hulls** (419 ships, 18 structures),
  search/page the picker, retain selection/name on recreation, or start from the
  hull browser. Copy and reopen through the existing atomic store. All-V and
  no-equipment assumptions are visible. Absent gun ranges display “Unavailable”;
  calculated zeroes remain numeric. Existing example workflows remain.
- Independent pinned EOS export/repeat checks all **39 raw fields per hull**.
  [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35748120518) and
  the complete local suite pass **90 host tests**, independent references/repeats
  and migration/backup. No original fitted expectation or tolerance changed.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35748120466)
  passes both APKs, lint, signature, source/data/ABI inspection and **20 offline
  native executions** on API36 x86_64. All prior numerical, forced-GC and process
  restart gates remain required. The new native cases compare every hull and
  exercise picker/search/page/recreation/cancel, ship/structure creation, copy,
  atomic rejection and real process restart. All **20 screenshots** reviewed.
  [Task/audit](tasks/B04-equipment-fitting.md) and
  [raw results/provenance/screens](evidence/b04-2-1-native.json) retain evidence.
- **B04.2.2** is the exact next task: add/replace/remove modules, rigs and service
  modules, preserve positions/state limits, expose EOS legality/skill/resource
  warnings, restriction override/re-enable and persistent 20-item recent use.
  B04.2.3 retains charges/scripts/crystals, active-fit charges, fitted/addition
  variations and ordering. Parent B04/B04.2 remain incomplete; F02.01 is partial.
  16 of 76 leaf tasks are done; 60 remain, plus seven rollups.
- B04.1 remains delivered in [PR #16](https://github.com/Sussic/Pyfa-android/pull/16)
  with complete market discovery; B03.2 in [PR #15](https://github.com/Sussic/Pyfa-android/pull/15).
  Historical receipts and task details remain linked from the roadmap.

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

Keep all **90 host tests and 20 native executions**, independent raw-value
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

A01–A10, B01–B03.2, B04.1 and B04.2.1 are delivered. Historical task details, PR links and raw
receipts remain in [ROADMAP](ROADMAP.md), the task briefs and
[evidence](evidence). Windows setup was delivered in
[PR #14](https://github.com/Sussic/Pyfa-android/pull/14). All **239 parity rows**
remain in [PARITY](PARITY.md); no full-feature or user-usability sign-off is claimed.

Empty ship/structure creation is delivered. Module/legality/recent-use edits
remain B04.2.2; charges/variations/reordering remain B04.2.3. Structure modes
remain B06. Older builds reject saved empty-module fits and preserve the file.
Physical ARM64 and older APIs have not run; package
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
