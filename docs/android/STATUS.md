# Android project status

Updated: 2026-09-22. Active: **B04.2.3.1 — Charge editing and active-fit discovery**.

## Current authorized work

- Explicit chat confirmation authorizes B04 and sequential eligible approved
  roadmap tasks, one outcome at a time, including review/checks/PR merges.
  No releases, phone installs, billing changes, unrelated work or delegation.
- **B04.2.2** is delivered in [PR #18](https://github.com/Sussic/Pyfa-android/pull/18),
  merge `b4b254071a3bdcddbd88ec5711feccc374d264fc`, tested head `cf9c51857cd37615c2ff9e2b592d3a6bb24dd1ae`.
  Add/replace/remove modules, rigs and structure services through the native
  editor/browser. Preserve vacancies and desktop default/state/restriction rules;
  show resource/recursive skill warnings and explicit override/re-enable effects.
  Actual use persists as 20 newest-first IDs with duplicate promotion and abyssal
  exclusion. Valid-item legality rejects enter history; stale/malformed/failed
  saves preserve both fit and history. EOS and atomic graph architecture remain.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35775027054) passes
  **96 host tests**, all independent references/repeats and migration/backup.
  The new oracle covers **11 cases/91 states and 4,242 module defaults**, including
  two recipients, resource/skill warnings, restrictions and subsystem vacancies.
  Local full/focused host tests and APK/lint/signature/package checks also pass.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35775027092) passes
  both APKs, lint, signature, 148-source/data/ABI inspection and **22 offline native
  executions** on API36 x86_64. UI edits/recreation, exact typed reference values,
  13 malformed protocol rejections, copies/history and process restart pass.
  All **27 screenshots** reviewed. The initial report-writer type loss was fixed
  by preserving original numeric types; settings stay exact and no gate weakened.
  [Audit](tasks/B04-equipment-fitting.md) and [raw receipt](evidence/b04-2-2-native.json)
  retain the evidence and limitations.
- **B04.2.3** selected on `codex/b04-2-3-charges-variations-ordering` from clean
  delivered master `6c71af9a6be24c1da783f51ab76fd018f21c52a7`; no open PRs.
  Outcome: compatible charge load/replace/unload, active-fit charge discovery,
  module and existing-addition variations, and rack swaps preserving state/charge
  and EOS heat behavior. Audit original commands before implementation; require
  independent raw values and native edit/failure/recreation/restart evidence.
  Preserve all 96 host and 22 native gates. Before code changes, split the three
  command families into B04.2.3.1 charges/discovery (active), B04.2.3.2 variations
  and B04.2.3.3 ordering/heat. Parent acceptance remains intact. The first child
  requires complete desktop charge sets, ammo/script/crystal raw-value cases,
  atomic failures, linked recipients and native edit/recreation/restart checks.
  Charge controls and typed options are implemented locally. The independent
  export/repeat and six focused host tests pass 14 cases/74 states and all 4,242
  compatible sets, including recipient updates, rejection, copies and restart.
  The full local Windows gate passes all 102 host tests, independent repeats and
  migration checks. Both APKs, lint, signature and 149-source/data/ABI package
  inspection pass locally; native CI, visual review and merge remain.
  The desktop cache setting and recipient-observation corrections are documented
  in the task brief. Next after this child: **B04.2.3.2 — Fitted and addition variations**.
- This task completes charges/scripts/crystals, active-fit
  charges, fitted/addition variations and rack ordering with independent values,
  native workflows and restart. B04/B04.2 remain incomplete; B05 bulk and B06 modes/
  subsystems retain their scope. **17 of 78 leaf tasks done; 61 remain**, plus eight
  rollups. All 239 parity rows remain; no full-feature/usability claim is made.
- Prior B04.2.1 [PR #17](https://github.com/Sussic/Pyfa-android/pull/17) delivered
  all 437 empty hulls; B04.1 [PR #16](https://github.com/Sussic/Pyfa-android/pull/16)
  delivered complete equipment discovery. Earlier receipts remain in the roadmap.

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

Keep all **96 host tests and 22 native executions**, independent raw-value
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

A01–A10, B01–B03.2, B04.1, B04.2.1 and B04.2.2 are delivered. Historical task details, PR links and raw
receipts remain in [ROADMAP](ROADMAP.md), the task briefs and
[evidence](evidence). Windows setup was delivered in
[PR #14](https://github.com/Sussic/Pyfa-android/pull/14). All **239 parity rows**
remain in [PARITY](PARITY.md); no full-feature or user-usability sign-off is claimed.

Empty ship/structure creation and module/legality/recent-use edits are delivered.
Charges/variations/reordering remain B04.2.3; modes/subsystems remain B06. Older
builds reject new vacancy/restriction/history inputs and preserve the file.
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
