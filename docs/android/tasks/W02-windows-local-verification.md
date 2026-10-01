# W02 — Complete Windows local verification

Selected 2026-10-01 at the user's request before resuming B09.1/PR #33.
Branch `codex/windows-local-verification` starts at `e916e054`; existing feature
work remains intact. Deliver a focused setup PR into the B09.1 branch, then stop.
The active setup-only goal requires later explicit authorisation before feature
delivery or roadmap continuation. No feature task is removed.

## Outcome and acceptance

- [x] Reuse installed JDK17, SDK, separate Python environments and Gradle wrapper;
  verify WHPX and prepare a disposable API36 Google APIs x86_64 emulator.
- [x] Run every desktop/reference and host check locally, then both APK builds,
  lint, signature and full package/ABI inspection without concurrent timed suites.
- [ ] Port the Linux launcher while preserving every native execution, fresh
  offline installation, all assertions, process boundaries, raw-result validators
  and required screenshots. Run the complete suite on Windows and review images.
- [ ] Retain local full logs, APKs, screenshots and raw results tied to the exact
  clean tested commit, source/data/tool identities and emulator identity.
- [ ] Provide repeatable focused and complete commands, safe explicit pause/resume
  at verified boundaries, and truthful local result reporting. Never label an
  unexecuted Actions check as passed; preserve coverage when changing gates.
- [ ] Demonstrate the local replacement before retiring hosted checks; prepare
  any access-dependent repository change and its exact remaining owner action.
- [ ] Update existing instructions, review, commit/push/merge the setup PR after
  applicable checks, record B09.1 delivery and B09.2 as subsequent work, then stop.

No unattended self-hosted runner on the public repository, CPU/RAM caps, paid
service, alternative CI platform, release, phone installation or billing change.
Shared SDK packages may be reused; the test AVD and app data are disposable.
Report remaining hosted work, possible charges and exact start/pause/resume steps.

## Approved timeout decision and original failure

The failed local run completed 76/78 gates. Its history prepare attempt started
at 2026-10-01 16:40:13 +01:00 and the gate returned failure after 902.078 seconds,
with an explicit 900-second subprocess timeout. The diagnostic screenshot shows
`History fill-clone` (case 14/18) and `Saving history action`. The sequential test
checks each preceding case before advancing. Replay rebuilds the complete fit
graph, which offers a plausible explanation for cumulative cost. However, there
are no per-case timing logs or observations showing continued progress near the
deadline: these facts do not rule out a hang within case 14.

The approved change at `6792b03e` changes the outer Windows instrumentation limit
from 900 to 2400 seconds (15 to 40 minutes) for both history phases, prepare and
restored. Linux remains 900 seconds. This is a relaxation of the outer timeout
pass/fail criterion, not a proven fix. No functional assertion, raw-result value,
tolerance, per-operation wait, process-restart boundary, screenshot requirement,
or separate A10 performance requirement changes.

The rejected coverage-verifier edit would normalize exactly the new `import os`
and timeout expression back to their prior form before the existing whole-source
equality comparison. Other source differences would still fail; native subgate
and exclusion-list equality checks remain. `history_summary.py` is unchanged.
The failed 900-second attempt and all completed results retain their original
commit and outcome. Fresh native execution would be required after approval
because the failed phase already changed its disposable synthetic library.

Automatic approval review initially rejected that verifier exception as weakening
checks. The user subsequently approved this exact change and one diagnostic retry,
with timestamped progress evidence around case 14. Preserve the original failed
attempt. Reuse unchanged completed results; rebuild native prerequisite data because
the failed mutation phase has no pre-history snapshot. If the retry fails, stop
without another timeout increase. If it passes, deliver W02 and stop.

## Single diagnostic retry result — stopped

At tested commit `6792b03e91b181194afe42fc1752993df35e55dd`, history prepare and
restored both passed, with instrumentation times 1903.248 and 181.903 seconds.
The complete history gate took 2146.218 seconds. Its unchanged validator accepted
18 cases/108 states, two recipients, 111 restored fits, six required screenshots
and ten protocol rejections. At 988.875 seconds the diagnostic showed case 14;
at 1080.828 seconds it showed case 15. CPU time and the database modification
timestamp advanced between these observations, proving this retry progressed
beyond the original stopping point. All original failed results remain retained.

The aggregate summary then failed in 9.25 seconds with `FileNotFoundError` for
`native/apk-contents.json`; the complete run is **failed, 77/78 gates**. The native
restart archived the package-inspection report with failed native evidence and
cleared the active directory while reusing completed build results. The original
report exists under `failed-native-386b97f5/native/apk-contents.json` with SHA256
`0af69f542a4e8af15d5ae5a487e8258cb5342622da338232c33722ef99d3efbe`.
No restoration, code repair, summary rerun or further native attempt has occurred.
The owned emulator stopped. Six fresh history screenshots and the summary-failure
diagnostic await visual review; the other 119 required screenshots are reviewed.

The exact next setup action requires renewed instruction: repair preservation of
the unchanged build/package report and run only the outstanding aggregate summary,
then complete review and setup delivery. No timeout increase or history replay is
needed or proposed. No hosted gate has been retired, no full-pass result published,
and no setup PR merged. PR #33 remains open at `e916e054`; B09.1 delivery followed
by B09.2 remain future roadmap work requiring explicit authorisation.
