# Android development instructions

## Goal

Build a personal, installable Android version of Pyfa whose fitting calculations,
features and saved fits work offline. The user expects Pyfa feature parity,
including projections, command bursts, all useful attributes and graphs. Bulk
operations (for example, changing ammunition across selected guns) are essential.
The user confirms usability; agents are responsible for technical correctness.

## Start a session

1. Read [current status](docs/android/STATUS.md), then the next task in
   [the roadmap](docs/android/ROADMAP.md). Read only that task's relevant sources.
2. Verify the live default branch and relevant open PRs/checks. Saved status is a
   pointer, not proof that a branch or test result is still current.
3. Read [scope](docs/android/SCOPE.md) and [architecture](docs/android/ARCHITECTURE.md)
   when the task touches product behavior or the engine boundary.
4. Select one ready task with completed dependencies. Record its ID and intended
   outcome in STATUS before implementation. Do not interpret "continue" as an
   instruction to implement the whole roadmap at once.

## Keep tasks bounded

- Each task produces one reviewable outcome and names its acceptance checks.
- If a task requires unrelated changes, split it into numbered child tasks before
  coding; retain the parent until every child is verified. Do not silently drop
  acceptance criteria to make a task appear small or complete.
- Complete the selected outcome, focused validation and authorized delivery before
  starting another. Do not leave a task half-finished merely because a prototype
  launches. Checkpoint honestly if access or execution time prevents completion.
- Do not spawn other agents by default. Use them only when the current user request
  or applicable higher-priority instructions explicitly authorize delegation.

## Preserve the product

- The pinned desktop reference is the comparison target. Reuse this repository's
  EOS calculations wherever practical; do not independently approximate formulas
  in Kotlin or substitute another project's engine without evidence and a recorded
  decision. The proposed embedding approach still needs its feasibility tests.
- Keep the full feature inventory. An unimplemented field must never silently
  display a fabricated zero or a seemingly valid default result.
- A phone UI may reorganize desktop interactions. It must retain their capabilities,
  including module selection, bulk edits, undo/redo and detailed attributes.
- Calculations, the initial game dataset and fit storage must work without a PC,
  server, account login or first-launch download. Optional network refresh uses
  cached data offline and exposes its age.
- Preserve upstream source history, license files and notices. Keep Android
  additions isolated and changes to upstream code small enough to review and sync.
- No unsolicited market automation, hosting backend, telemetry, subscriptions,
  iOS port or Play Store launch. See SCOPE for the actual agreed boundary.

## Validate what changed

- Follow [development and evidence rules](docs/android/DEVELOPMENT.md). Do not
  describe planned commands, inherited placeholders or skipped tests as passing.
- Compare matching source revision, dataset, skills, settings and fit state.
  Expected values come from the independent pinned desktop reference, not from
  the Android implementation under test. Record units and justified tolerances.
- Engine changes need meaningful regression cases. Android behavior needs native
  build/test evidence; host-only Python tests cannot establish Android support.
- For documentation-only changes, inspect scope, links and task dependencies and
  run `git diff --check`. Do not start emulator runs or create placeholder tests.
- Never weaken a required check to get a green build. Record inherited failures
  separately, with a focused excerpt and an actionable next step.

## Git, CI and storage

- Work only in `Sussic/Pyfa-android` unless explicitly asked otherwise. Never open
  an upstream PR or push to `pyfa-org/Pyfa` as part of routine personal-fork work.
- Use a task branch such as `android/a01-desktop-reference` for implementation
  and a focused PR into this fork. Follow current-session delivery authorization;
  do not invent a mandatory approval step. Small documentation setup/status
  changes may be committed directly when authorized.
- Batch related fixes before expensive CI. Check for an existing run for the same
  commit before triggering another. Cancel superseded branch runs once workflows
  support concurrency; do not cancel another active task's run.
- Keep billing/spending settings unchanged. Avoid duplicate APK uploads, full
  workspace archives, permanent emulator images and unbounded caches. Initial CI
  policy is one-day retention for diagnostic/test artifacts, no scheduled runs,
  no automatic release publishing, and APK uploads only on deliberate build runs.
- If required evidence cannot be retained within quota, record the blocker. Do
  not delete releases, bypass gates or change budgets to make the run succeed.
- Retry only when something relevant changed or a transient failure cleared.
  Report automatic approval denials and the exact blocked action. Use a genuinely
  safer supported alternative when available, never another route to evade denial.
- Keep credentials, character tokens, personal fits and signing keys out of git,
  logs and public test fixtures. Use synthetic examples for reproducible tests.

## Finish a session

Update the selected task status and STATUS with the outcome, branch/PR or commit,
checks actually run, any blocker, and one exact next task. Keep STATUS concise;
leave long logs in CI and code details in the relevant task/PR. Report implemented,
tested and still unverified behavior separately. Full completion requires every
inventory row verified, offline and upgrade checks passed, and user usability
sign-off; a working APK alone is not feature parity.
