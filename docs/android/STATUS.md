# Android project status

Updated: 2026-10-02. **W02 summary-routing repair authorised; B09.1 preserved in PR #33.**

## Selected setup — W02 Windows local verification

The active goal is complete local build/test setup and delivery, then stop.
Branch `codex/windows-local-verification`
starts from PR #33 head `e916e054`; all B09.1 feature work is preserved. This setup
will use a focused PR into the B09.1 branch before PR #33 returns to delivery.
[Acceptance and scope](tasks/W02-windows-local-verification.md): reuse installed
SDK/JDK/Python/Gradle, disposable WHPX API36 x86_64 emulator, full desktop and
native coverage, offline install/restart/raw validation and screenshot review,
commit-bound local logs/APKs/evidence, repeatable start/pause/resume commands and
truthful required result reporting. Demonstrate local replacement before retiring
hosted checks. No unattended runner, CPU/RAM caps, paid service, release or phone
installation. B09.1 delivery and then B09.2 await later explicit authorisation.

Desktop run `36661924082` passes the unchanged PR head in 29m34s. Android run
`36661923971` attempt 1 was cancelled at 50m06 during emulator testing; attempt 2
also exceeded the 50-minute job ceiling (50m09s). No hosted retry is pending. Neither cancelled/unexecuted native check is passing evidence.
The single approved diagnostic retry at `6792b03e` passed history: prepare
1903.248 seconds, restored 181.903 seconds, total gate 2146.218 seconds. Its raw
validator confirms 18 original cases/108 states, two recipients, 111 restored
fits and ten protocol rejections. The Windows outer deadline is 2400 seconds per
phase; Linux remains 900. Assertions, tolerances, operation limits, restart checks,
screenshots and A10 requirements are unchanged. Exact native-source comparison
and 20 reporting/parser regression tests passed before this run.

Diagnostics show case 14 (`fill-clone`) at 988.875 seconds and case 15
(`clone-selected`) at 1080.828 seconds. The same process's CPU time increased
from 17:19 to 18:56; successful supplemental database observations advanced its
modification timestamp by 80 seconds. This establishes progress beyond case 14
in this retry. The original 900-second failure remains in the archive and log 083.

**Full verification failed at 77/78 gates:** `native:summary` raised
`FileNotFoundError` for `native/apk-contents.json` (log 109). Native restart archived
that build/package report and cleared the active evidence directory while retaining
the 53 valid host/build results; the report was not restored. Its original copy
is retained under `failed-native-386b97f5/native/apk-contents.json`. No report has
been copied back, no summary rerun or further emulator run has been launched,
and no full-pass receipt/status has been published. The owned emulator stopped;
`adb devices` is empty. All fresh native execution gates passed, but the final
aggregate validation remains unsuccessful.

Local evidence is retained at
`%LOCALAPPDATA%/PyfaAndroid/PyfaDevelopment/evidence/20261001-143805-f7d2ad31-99b296`
(Codex resolves it through Package LocalCache). The 53 host/build gates retain
their actual `f7d2ad31` commit; fresh native gates retain `6792b03e`. Both APKs,
full logs, raw reports, diagnostic images and original failed results remain local.
There are 119 fresh required screenshot reviews; six history screenshots and the
summary-failure diagnostic are retained but not yet reviewed. API36 Google APIs
x86_64 revision7 and emulator36.2.12 reuse the installed WHPX environment.

The user now authorises only the evidence-routing repair, focused checks and
outstanding aggregate summary. First validate the archived report against this
run and retained APKs; preserve all 77 completed results and their actual commits.
If evidence cannot be validated or completed stages need rerunning, stop and
explain. On success, finish screenshot review and setup delivery, then stop.
No timeout increase or history retry is authorised. Start/pause/resume commands remain in
[LOCAL-VERIFICATION](LOCAL-VERIFICATION.md). No setup PR was opened or merged;
hosted workflows remain unchanged. PR #33 is still open at `e916e054`; feature
delivery and subsequent B09.2 work require later explicit authorisation.

## Authorized queue

The active goal authorises W02 implementation, required verification, review and
setup PR delivery, followed by stopping. Preserve PR #33 without merging its feature
work. B09.1 completion and then B09.2 are recorded next tasks for later explicit
resumption. No releases, phone installation, billing changes, unrelated work or
delegation.

## Latest delivery — B08 fit notes

[PR #32](https://github.com/Sussic/Pyfa-android/pull/32) merged as `d6110359`,
tested head `02171308`. CI checkout `15d4c7e4` and
the merge share tree `14f3c7cc`. Build **26 (`0.1.0-b08`)** adds
exact multiline Unicode notes, one-second autosave and navigation flush, retained
drafts through activity recreation and failed saves, and explicit conflict choices.
Stored structure notes remain read-only and survive copies/restart.

- The independent original service/pane and EOS copy repeat **three fits/13 states**.
  Four host tests pass exact text/counts, fit/copy isolation, unchanged calculations
  and recent history, invalid/stale/write-failure recovery, legacy graphs and
  **five-fit fresh-process restart**.
- [Windows/reference CI](https://github.com/Sussic/Pyfa-android/actions/runs/36657441169)
  passes all required gates in **28m44s**.
- [Android/native CI](https://github.com/Sussic/Pyfa-android/actions/runs/36657441195)
  passes inherited and new offline workflows, both APKs, lint, signature, pinned
  data/licenses and ABI inspection in **34m24s**.
  All **90 fits** restore; ten malformed notes protocol cases are rejected.
- Artifact digest and tested tree match. **Seven notes screenshots** were reviewed;
  **20 deliberate report corruptions** are rejected. Retained
  [receipt](evidence/b08-native.json) and [raw report](evidence/b08-notes-native.json)
  record provenance and observed results.

Pending drafts remain in memory until a save is confirmed; unconfirmed process
death is not a draft-persistence guarantee. B08 is complete within the pinned notes
boundary. **B09 undo/redo** is the exact next eligible task; B05 is delivered.

## Selected task — B09.1 edit history

Selected `codex/b09-1-edit-history` from delivered master `72b01c4c`; live default
master and no open PRs verified. B05 satisfies B09's dependency. B09 is split into
single/bulk module undo/redo (B09.1), then remaining supported mutations and future
extension requirements (B09.2); the parent remains open until both are verified.
B09.1 will retain desktop per-fit 100-action grouping/branching, native undo/redo
controls, safe selection state and atomic EOS replay with saved reversed values.
Acceptance includes independent original-command/processor evidence, host failure
and restart checks, offline native touch/recreation/restart, screenshot review and
all required final-head CI. [Task and checks](tasks/B09-undo-redo.md). No new product
inputs, schema migration, release or phone actions. Next child: **B09.2**.
Independent original history now repeats 18 cases/108 states and verifies the
100-action limit. Six focused host tests pass; final APKs/lint (1m43s) and 163-source
package/ABI inspection pass. Required CI, native evidence/screenshots and delivery remain
pending. B09.2 is not started.

## Delivered work to reuse

| Milestone | Delivery and retained evidence |
| --- | --- |
| B04 equipment/fitting | [PR #21](https://github.com/Sussic/Pyfa-android/pull/21), [task](tasks/B04-equipment-fitting.md). All B04 children remain closed. |
| B05 bulk editing | PRs [#22](https://github.com/Sussic/Pyfa-android/pull/22), [#23](https://github.com/Sussic/Pyfa-android/pull/23), [#24](https://github.com/Sussic/Pyfa-android/pull/24), [#25](https://github.com/Sussic/Pyfa-android/pull/25); [task](tasks/B05-bulk-editing.md). |
| B07.3 fitted transfers | [PR #31](https://github.com/Sussic/Pyfa-android/pull/31), [receipt](evidence/b07-3-native.json), [task](tasks/B07-cargo-management.md). |
| B07.2 selected cargo actions | [PR #30](https://github.com/Sussic/Pyfa-android/pull/30), [receipt](evidence/b07-2-native.json), [task](tasks/B07-cargo-management.md). |
| B07.1 cargo stacks | [PR #29](https://github.com/Sussic/Pyfa-android/pull/29), [receipt](evidence/b07-1-native.json), [task](tasks/B07-cargo-management.md). |
| B06 modes/subsystems/structures | PRs [#26](https://github.com/Sussic/Pyfa-android/pull/26), [#27](https://github.com/Sussic/Pyfa-android/pull/27), [#28](https://github.com/Sussic/Pyfa-android/pull/28); [task](tasks/B06-hull-configuration.md), [latest receipt](evidence/b06-3-native.json). |

Earlier A/B milestones remain done as recorded in ROADMAP and their task/evidence
files. Do not reopen delivered work or rerun unchanged tested revisions.

## Forecast and installation limits

B09 undo/redo comes next. Elapsed implementation estimates remain **unknown**
until its focused audit resolves scope; confidence is low. B08's final Windows/
Android runs took **28m44s/34m24s**.
CI corrections may require another full round; one-round delivery estimates are
not reliable.

Build 16 was the first meaningful development build; build 26 is the latest
emulator-tested build. The local debug APK is
`android/app/build/outputs/apk/debug/app-debug.apk`. Safe persistent phone use
remains **unknown** until R02 signing/upgrade checks and phone/API compatibility
are resolved. Phone usability, older APIs and ARM64 execution remain unverified;
no phone installation or release publication occurs.

## Resume, environment and architecture

Read AGENTS, [ROADMAP](ROADMAP.md), the next task and ignored
`build/WINDOWS-CHECKPOINT.md`; verify local changes, live master and open PRs.
Work only in Sussic/Pyfa-android. Dot-source `build/windows-env.ps1` to reuse
Python3.11.9 reference/headless, JDK17.0.20.1+1, SDK36/build35 and Gradle8.13.
No timed host suites alongside local Gradle. Native CI uses Ubuntu/KVM; local
Windows builds alone do not establish Android execution. Preserve all inherited
host/native type/unit/GC/restart/performance/screenshot gates, one-day diagnostics,
deliberate APK uploads only and no scheduled/release jobs.

Kotlin/Compose + Chaquopy + serialized EOS remain A10. Follow [scope](SCOPE.md),
[architecture](ARCHITECTURE.md) and [evidence rules](DEVELOPMENT.md). No Kotlin
formula approximations. Desktop pin `8b04f3b271e614b3e103853b44a7851a63d79d0e`,
tree `8db82315f8312b124dd24ef103e43496cee50b4a`, logical dataset
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
EOS owns an exclusive in-memory session; separate locked SQLite stores declarative
graphs atomically. Navigation preferences stay separate. Preserve invalid files.
Keep desktop `gamedataCache=False`. Host Logbook1.7.0.post0, SQLAlchemy1.4.50 and
Greenlet3.0.3; Android Greenlet3.0.1 build1 and chaquopy-libcxx180000 build0 remain.

ARM64 execution, older APIs, safe upgrades/downgrades and user usability remain
unverified. Both ABIs are packaged. Phone model/API unconfirmed; native report
transport requires API31+, app minSdk24. I05 backup/transfer, R02 signing/upgrades,
R03 usability, C07 full implant profiles/locations and Q07 complete projection/
command matrices retain scope. Older builds reject newer fields and preserve
storage. Legacy tox remains unaudited; A10 measurements are debug emulator baselines.
Full parity is not established. Restore-off opens the library while saved fits rebuild.
