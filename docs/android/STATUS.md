# Android project status

Updated: 2026-09-23. Active: **B04.2.3.2 — Fitted and addition variations**.

## Current authorized work

- Explicit chat confirmation authorizes B04 and sequential eligible approved
  roadmap tasks, one outcome at a time through review/checks/PR merge. No releases,
  phone installs, billing changes, unrelated work or delegation.
- **B04.2.3.1 is delivered** in [PR #19](https://github.com/Sussic/Pyfa-android/pull/19),
  merge `a1c784532035ebf7b5e75fc42ee74d5d2d5e3266`, tested head
  `b6b24010b45bff5e0fdcbc2c1c80fcd0693807a2`. Load, replace and unload compatible
  ammunition, scripts and crystals from a module or active-fit charge browser.
  Search/pagination, recreation, atomic rejection/save recovery, independent copies
  and process restart retain inputs and exact values. Charge edits leave actual
  recent-use history unchanged. EOS and the atomic graph architecture remain.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35790288102) passes
  **102 host tests**, all independent references/repeats and migration/backup.
  New charge evidence covers **14 cases/74 states and all 4,242 compatibility sets**,
  with two projection and two command recipients. Full local Windows verification
  passes in 19 minutes; focused charge checks pass in about four minutes.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35790287983) passes
  both APKs, lint, signature, 149-source/data/license/ABI inspection and **24 offline
  native executions** on API36 x86_64. Strict numeric kinds/units, 11 protocol
  rejections and all 12 saved fits across restart pass. All **35 screenshots**
  reviewed. Downloaded raw validators and deliberate corruption probes pass;
  artifact digest and CI tree match the tested head. Local APK/lint/package checks
  also pass. [Audit](tasks/B04-equipment-fitting.md) and
  [raw receipt](evidence/b04-2-3-1-native.json) retain the evidence and limits.
- Selected **B04.2.3.2 — Fitted and addition variations** on
  `codex/b04-2-3-2-variations` from clean delivered master
  `6c8b217a4615cff70d5616ab6947c831b098cb8e`; live master verified and no open PRs. Audit
  original variation commands and existing addition inputs; implement supported
  switches with desktop state/charge/location reconciliation, atomic failure and
  save/restart. Require independent raw values and native workflow evidence.
  Preserve all 102 host and 24 native gates. B04.2.3.3 ordering/heat follows.
  Implementation is in [PR #20](https://github.com/Sussic/Pyfa-android/pull/20).
  Final independent reference/repeat passes 17 cases/55 states and all 5,226
  families, including state fallback and cross-slot implants. Local 22 gates/108
  host tests and APK/lint/signature/package checks pass. First Windows CI passes
  all 108 host tests; native CI retained the earlier gates but exposed a Compose
  crash returning from choices to fitted items. Isolate the two list composition
  scopes with stable row keys and rerun required native evidence before delivery.
  The measured first native run reached that failure after 24m38s; workflow time
  allowance is now 30 minutes for the remaining workflows/restart. Assertions,
  performance thresholds and scope remain unchanged. No .2 completion claim.
  The ignored checkpoint retains exact runs, paths and current verification.
- B04.2.3, B04.2 and B04 remain incomplete. B05 bulk edits, B06 modes/subsystems,
  B07 cargo and B09 undo/redo retain their accepted scope. **18 of 78 leaf tasks
  done; 60 remain**, plus eight rollups. All 239 parity rows remain.
- Earlier deliveries: [B04.2.2 / PR #18](https://github.com/Sussic/Pyfa-android/pull/18)
  modules/legality/recent use; [B04.2.1 / PR #17](https://github.com/Sussic/Pyfa-android/pull/17)
  all 437 empty hulls; [B04.1 / PR #16](https://github.com/Sussic/Pyfa-android/pull/16)
  complete equipment discovery. Receipts remain in the roadmap and evidence folder.

## Resume and installed environment

Read AGENTS, this file, [ROADMAP](ROADMAP.md) and the selected task. Check local
changes, live fork master and open PRs before writing. Work only in
[Sussic/Pyfa-android](https://github.com/Sussic/Pyfa-android).

Dot-source `. ./build/windows-env.ps1`. Reuse Python 3.11.9 x64 in separate
`.venv/headless` and `.venv/reference`, Temurin 17.0.20.1+1, Gradle 8.13,
SDK platform 36 revision 2 and Build Tools 35.0.0. The Gradle cache lives in local
AppData outside OneDrive. [Windows guide](WINDOWS.md) has commands; the concise
`build/WINDOWS-CHECKPOINT.md` retains continuation details and the forecast, updated
after each delivered milestone. Timed host tests never run alongside local Gradle.

Keep all **102 host tests and 24 native executions**, independent raw-value/type/
unit validators, process restarts, forced-GC regressions and screenshot review.
Native CI uses Ubuntu/KVM; Windows builds alone do not establish Android support.
One-day diagnostics retention, deliberate APK uploads only, no scheduled runs or
automatic releases remain the policy.

## Architecture and comparison target

- Kotlin/Compose + Chaquopy + serialized EOS remain the A10 decision. Follow
  [scope](SCOPE.md), [architecture](ARCHITECTURE.md) and [evidence rules](DEVELOPMENT.md).
  Do not approximate fitting formulas in Kotlin.
- Pinned desktop source `8b04f3b271e614b3e103853b44a7851a63d79d0e`, tree
  `8db82315f8312b124dd24ef103e43496cee50b4a`; logical dataset SHA-256
  `5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
- EOS retains an exclusive in-memory session. Declarative inputs use a separate
  locked SQLite graph store. Format 1 is nonempty; format 2 is intentionally empty.
  Never replace existing files with a sample. Input/edit-order metadata commits
  atomically; navigation preferences remain separate. Preserve invalid files.
- Adapter initialization now matches desktop `gamedataCache=False`, avoiding
  item/group integer-key collisions without upstream EOS or formula changes.
- Host pins: Logbook 1.7.0.post0, SQLAlchemy 1.4.50, Greenlet 3.0.3. Android uses
  Greenlet 3.0.1 build 1 and chaquopy-libcxx 180000 build 0; all six wheels verified.

## Remaining limits

Development build 13 (`0.1.0-b04.2.3.1`) supports meaningful hull/module/charge
workflow testing. Physical ARM64, older APIs, safe upgrades/downgrades and user
usability remain unverified; no full feature-parity claim. Both ABIs are packaged.
Phone model/API is unconfirmed; native report transport needs API31+ while the app
declares minSdk24. No phone installation is authorized or performed.

Backup/transfer remains I05, stable signing and install-over-existing-data tests
R02, usability R03. Older builds reject new vacancy/restriction/history fields and
preserve their file. Q07 retains complete projection/command stacking/cycle cases;
C07 retains complete implant replacement/location behavior. Legacy tox tests remain
unaudited and are not part of passing evidence. Verify integrity/logical identity
before reusing temporary databases. A10 measurements remain bounded debug/emulator
baselines, not phone/release or peak-memory guarantees. With restore off, launches
draw the library without an active view while EOS still rebuilds saved fits.
