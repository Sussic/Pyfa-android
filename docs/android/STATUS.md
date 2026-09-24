# Android project status

Updated: 2026-09-24. **B04 delivered. Next: B05 — Bulk weapon/module editing.**

## Current authorized work

- Explicit chat confirmation authorizes sequential eligible approved roadmap
  tasks, one outcome at a time through review/checks/PR merge. No releases, phone
  installs, billing changes, unrelated work or delegation. The goal remains active.
- **B04.2.3.3 and B04 delivered** in [PR #21](https://github.com/Sussic/Pyfa-android/pull/21),
  merge `9e5f3706db2f4e6b8e30a4c30cdf66715b30ed59`, tested head
  `c9e8cec217f11561f36302e53b9b7d2c472d7e0b`. Move or swap fitted modules within a
  rack, preserving states/charges, and inspect original desktop positional heat.
  Atomic save/recovery, recipients, selection/recreation and real restart pass.
  EOS and the unchanged Thermodynamics class remain the calculation source.
- [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35933294633)
  passes **114 host tests**, independent references/repeats and migration gates
  in **22m11s**. Local validation passes **24 gates** in **30m27s**. Ordering covers
  **nine cases/48 states/four recipients** against the independent desktop pin.
- [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35933294598)
  passes both APKs, lint, signature, 152-source/data/license/ABI inspection and
  **28 offline native executions** in **27m12s**. All **50 screenshots** reviewed;
  all **16 saved fits** restored. Artifact digest/tree, raw validators, 13 summary
  corruption probes and 11 numeric transport probes pass. Local APK/lint/package
  checks pass. [Task audit](tasks/B04-equipment-fitting.md) and
  [receipt](evidence/b04-2-3-3-native.json) retain evidence and limits.
- Extra CI rounds resolved an emulator report-transfer failure, a source-audit
  path unavailable in the sparse checkout, and an exact error-code expectation
  at the Kotlin/Python boundary. No checks, type/unit rules or tolerances were weakened.
- B04 covers discovery, hull creation, modules/legality/history, charges,
  variations and ordering/heat. Full parity is not established. B05 bulk, B06
  modes/subsystems, B07 cargo, B09 undo/redo and C09 heat options retain scope.
- **Exact next task B05:** audit selection/fill/mixed-compatibility behaviors,
  bound the task in a brief, then implement native bulk actions with independent
  desktop, atomicity and persistence evidence. No current access or product decision blocks it.

## Forecast after B04 delivery

| Next milestone | Remaining work | Elapsed estimate / confidence |
| --- | --- | --- |
| B05 bulk editing | Selection, multi-module ammo/state/fill and mixed compatibility; reference, host/native checks and delivery. | Unknown until the selection/fill/mixed-compatibility audit resolves command families; low confidence before that audit. |
| B06 hull configuration | Modes, subsystems and structure controls; changing slots/bonuses and persistence. | Unknown until the mode/subsystem/structure audit resolves scope; low confidence. |
| B07 cargo | Stack quantities and equipment/ammo transfers with restart and desktop comparisons. | Unknown until the stack/transfer audit resolves command behavior; low confidence. |

Allow **25–35 minutes per full CI round** based on the latest 22m11s Windows and
27m12s Android jobs running together; corrections can require another round.
B04's extra rounds above were the material delay. Build **15 (`0.1.0-b04.2.3.3`)
is meaningful for development workflow testing now**, including saved fits and
rack heat. Safe persistent phone use is **unknown until R02 signing/upgrade
checks and phone/API compatibility are resolved**. No phone installation occurs.
No decision/access needed now; whole-queue time remains unknown until later audits
and device/upgrade gates resolve. Refresh this forecast after each milestone.

## Resume and installed environment

Read AGENTS, [ROADMAP](ROADMAP.md) and the selected task. Verify local changes,
live fork master and open PRs. Work only in Sussic/Pyfa-android. Dot-source
`build/windows-env.ps1`: Python 3.11.9 reference/headless, JDK17.0.20.1+1,
SDK36/build35 and Gradle8.13. Reuse installed tools and local AppData Gradle cache.
[Windows guide](WINDOWS.md) and ignored `build/WINDOWS-CHECKPOINT.md` retain commands,
continuation paths and forecast. No timed host suites alongside local Gradle.
Native CI uses Ubuntu/KVM; Windows builds alone do not establish Android support.
Keep all 114 host/28 native executions and raw type/unit/GC/restart/performance/screenshot
checks, one-day diagnostics, deliberate APK uploads only and no scheduled/release jobs.

## Architecture and remaining limits

Kotlin/Compose + Chaquopy + serialized EOS remain A10. Follow [scope](SCOPE.md),
[architecture](ARCHITECTURE.md) and [evidence rules](DEVELOPMENT.md). No Kotlin
formula approximations. Pinned desktop `8b04f3b271e614b3e103853b44a7851a63d79d0e`,
tree `8db82315f8312b124dd24ef103e43496cee50b4a`, logical dataset
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
EOS owns an exclusive in-memory session; separate locked SQLite stores declarative
graphs atomically. Navigation preferences stay separate. Preserve invalid files.
Keep desktop `gamedataCache=False`. Host Logbook 1.7.0.post0, SQLAlchemy 1.4.50 and
Greenlet 3.0.3; Android Greenlet 3.0.1 build 1 and chaquopy-libcxx 180000 build 0 remain.

ARM64 execution, older APIs, safe upgrades/downgrades and user usability remain
unverified. Both ABIs are packaged. Phone model/API unconfirmed; native report
transport needs API31+, app minSdk24. Backup/transfer I05, stable signing/upgrades
R02, usability R03, full implant profiles/locations C07 and complete projection/
command matrices Q07 retain scope. Older builds reject newer fields and preserve
storage. Legacy tox remains unaudited. A10 measurements are debug emulator baselines.
Restore-off opens the library while EOS rebuilds saved fits.
