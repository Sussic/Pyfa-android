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

## Pending timeout decision

The failed local run completed 76/78 gates. Its history prepare attempt started
at 2026-10-01 16:40:13 +01:00 and the gate returned failure after 902.078 seconds,
with an explicit 900-second subprocess timeout. The diagnostic screenshot shows
`History fill-clone` (case 14/18) and `Saving history action`. The sequential test
checks each preceding case before advancing. Replay rebuilds the complete fit
graph, which offers a plausible explanation for cumulative cost. However, there
are no per-case timing logs or observations showing continued progress near the
deadline: these facts do not rule out a hang within case 14.

The current uncommitted proposal changes the outer Windows instrumentation limit
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
