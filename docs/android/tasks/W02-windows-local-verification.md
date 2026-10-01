# W02 — Complete Windows local verification

Selected 2026-10-01 at the user's request before resuming B09.1/PR #33.
Branch `codex/windows-local-verification` starts at `e916e054`; existing feature
work remains intact. Deliver a focused setup PR into the B09.1 branch, then return
to its delivery and the already approved roadmap. No feature task is removed.

## Outcome and acceptance

- [ ] Reuse installed JDK17, SDK, separate Python environments and Gradle wrapper;
  verify WHPX and prepare a disposable API36 Google APIs x86_64 emulator.
- [ ] Run every desktop/reference and host check locally, then both APK builds,
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
  applicable checks, then resume B09.1 and B09.2 automatically.

No unattended self-hosted runner on the public repository, CPU/RAM caps, paid
service, alternative CI platform, release, phone installation or billing change.
Shared SDK packages may be reused; the test AVD and app data are disposable.
Report remaining hosted work, possible charges and exact start/pause/resume steps.
