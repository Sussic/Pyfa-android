# Android project status

Updated: 2026-09-23. **B04.2.3.2 delivered**; next **B04.2.3.3 — Rack ordering and heat behavior**.

## Current authorized work

- Explicit chat confirmation authorizes B04 and sequential eligible approved
  roadmap tasks, one outcome at a time through review/checks/PR merge. No releases,
  phone installs, billing changes, unrelated work or delegation.
- **B04.2.3.2 delivered** in [PR #20](https://github.com/Sussic/Pyfa-android/pull/20), merge
  `d14441eb771157127d768668200396cea3d2750a`, tested head
  `b0fa526cf1c0c9ce3d8038d39d908b56dccda43e`. The variation picker supports modules, drone stacks and
  fit-local implants with search/pagination, current inputs and disabled choices.
  Original family ordering, state/charge reconciliation, distinct drone stacks,
  cross-slot implant behavior and linked recipients match the pinned desktop.
  Atomic rejection/save recovery, independent copies, recreation and real restart
  retain inputs and values. Recent-use history stays unchanged. EOS remains.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35921791052) passes
  **108 host tests**, independent references/repeats and migration/backup.
  New variations cover **17 cases/55 states and all 5,226 families**, including
  six recipients. Full local Windows checks pass in 23 minutes of gate execution.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35921790783) passes
  both APKs, lint, signature, 150-source/data/license/ABI inspection and **26 offline
  native executions** on API36 x86_64. Strict types/units, 13 new protocol rejections
  and all 14 saved fits after restart pass. All **43 screenshots** reviewed.
  Downloaded raw validators and corruption probes pass; artifact digest and CI
  tree match the tested head. Local APK/lint/package checks also pass.
  [Audit](tasks/B04-equipment-fitting.md) and
  [raw receipt](evidence/b04-2-3-2-native.json) retain evidence and limitations.
- The first native run found a Compose crash returning to fitted items. Separate
  list composition scopes and stable row keys fix the tested transition. The
  observed 24m38s run justified a 30-minute workflow allowance; assertions and
  performance thresholds remain unchanged. A second run corrected the pagination
  test to use Gecko's actual 94-choice family; Hobgoblin quantity/order coverage
  remains. A transient Windows checkout trust failure cleared on a fresh runner
  with certificate validation unchanged.
- Next **B04.2.3.3**: audit original occupied/vacant same-rack swaps and positional
  heat, implement native ordering with preserved inputs, prove independent heat
  values and real restart. B04.2.3/B04.2/B04 remain incomplete until it passes.
  B05 bulk, B06 modes/subsystems, B07 cargo and B09 undo/redo retain full scope.
  **19 of 78 leaves done; 59 remain**, plus eight rollups. All 239 parity rows remain.
- Earlier deliveries: [charges / PR #19](https://github.com/Sussic/Pyfa-android/pull/19),
  [modules / PR #18](https://github.com/Sussic/Pyfa-android/pull/18),
  [empty hulls / PR #17](https://github.com/Sussic/Pyfa-android/pull/17),
  [equipment / PR #16](https://github.com/Sussic/Pyfa-android/pull/16).

## Resume and installed environment

Read AGENTS, [ROADMAP](ROADMAP.md) and the selected task. Verify local changes,
live fork master and open PRs. Work only in Sussic/Pyfa-android. Dot-source
`build/windows-env.ps1`: Python 3.11.9 reference/headless, JDK17.0.20.1+1,
SDK36/build35 and Gradle8.13. Reuse installed tools and local AppData Gradle cache.
[Windows guide](WINDOWS.md) and ignored `build/WINDOWS-CHECKPOINT.md` retain commands,
continuation paths and the forecast. No timed host suites alongside local Gradle.
Native CI uses Ubuntu/KVM; Windows builds alone do not establish Android support.
Keep all 108 host/26 native executions and raw type/unit/GC/restart/performance/screenshot gates,
one-day diagnostics, deliberate APK uploads only and no scheduled/releases jobs.

## Architecture and comparison target

Kotlin/Compose + Chaquopy + serialized EOS remain A10. Follow [scope](SCOPE.md),
[architecture](ARCHITECTURE.md) and [evidence rules](DEVELOPMENT.md). No Kotlin
formula approximations. Pinned desktop `8b04f3b271e614b3e103853b44a7851a63d79d0e`,
tree `8db82315f8312b124dd24ef103e43496cee50b4a`, logical dataset
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
EOS owns an exclusive in-memory session; separate locked SQLite stores declarative
graphs atomically. Navigation preferences stay separate. Preserve invalid files.
Keep desktop `gamedataCache=False`. Host Logbook 1.7.0.post0, SQLAlchemy 1.4.50 and
Greenlet 3.0.3; Android Greenlet 3.0.1 build 1 and chaquopy-libcxx 180000 build 0 remain.

## Remaining limits

Development build 14 (`0.1.0-b04.2.3.2`) supports hull/module/charge/variation workflow
testing and saved fits. ARM64 execution, older APIs, safe upgrades/downgrades and
user usability remain unverified; no full-parity claim. Both ABIs are packaged.
Phone model/API unconfirmed; native report transport needs API31+, app minSdk24.
No phone installation authorized or performed. Backup/transfer I05, stable signing
and upgrades R02, usability R03, full implant profiles/locations C07 and complete
projection/command matrices Q07 retain scope. Older builds reject newer fields
and preserve storage. Legacy tox remains unaudited. A10 measurements remain debug
emulator baselines. Restore-off opens the library while EOS rebuilds saved fits.
