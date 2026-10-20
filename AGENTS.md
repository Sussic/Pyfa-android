# Android development instructions

## Goal

Build a personal, installable Android version of Pyfa whose fitting calculations,
features and saved fits work offline. The user expects Pyfa feature parity,
including projections, command bursts, all useful attributes and graphs. Bulk
operations (for example, changing ammunition across selected guns) are essential.
The user confirms usability; agents are responsible for technical correctness.

## Start a session

1. Read the current control point in [STATUS](docs/android/STATUS.md), then its task in
   [the roadmap](docs/android/ROADMAP.md). Historical next steps never authorize work.
2. Verify the live default branch and relevant open PRs/checks. Saved status is a
   pointer, not proof that a branch or test result is still current.
3. Read [scope](docs/android/SCOPE.md) and [architecture](docs/android/ARCHITECTURE.md)
   when the task touches product behavior or the engine boundary.
4. Select the user-authorized task or milestone with completed dependencies.
   Record its ID, scope and intended outcome in STATUS before implementation.
   A setup-only request does not authorize the next feature task. Do not interpret
   "continue" as an instruction to implement the whole roadmap at once.

## Keep tasks bounded

- Each task produces one reviewable outcome and names its acceptance checks.
  Freeze that accepted set; optional ideas go to their existing roadmap owner,
  not into the current milestone. Defects needed to meet acceptance still belong.
- Keep STATUS's current control point concise and authoritative. ROADMAP owns
  feature state/dependencies/order; task briefs own acceptance; receipts own proof.
  Supersede stale actionable text instead of adding competing next steps.
- Give infrastructure diagnosis a hypothesis, attempt/time/evidence budget, stop
  condition and fallback before execution. Exhausting the budget pauses that
  path; it does not authorize another monitor, guard or environment redesign.
  Preserve safety limits and useful failed evidence.
- Authorization for a milestone includes its related subtasks, necessary setup,
  fixes and required verification within the agreed scope. Continue through those
  subtasks without repeated "continue" prompts; child tasks organize the work and
  do not create new approval gates. Ask only for missing authentication, required
  system approval or a genuine scope/product decision. Do not expand into unrelated
  roadmap work, release publication or phone-data changes without authorization.
- If a task requires unrelated changes, split it into numbered child tasks before
  coding; retain the parent until every child is verified. Do not silently drop
  acceptance criteria to make a task appear small or complete.
- Check actual task dependencies before treating a blocked acceptance gate as a
  development blocker. Continue already-approved independent host/reference work
  in a small isolated source area while native acceptance is blocked; preserve
  frozen candidates and state exactly which integration/native proof remains.
- Recover routine implementation failures with focused fixes, checks and review
  within the selected outcome. Use justified task-specific time, memory and
  evidence budgets; existing caps remain binding. Escalate material scope, risk
  or permission changes, not each routine step. Resource failures do not authorize
  unlimited budget growth or another heavy run without its coordinated slot.
- Complete the selected outcome, focused validation and authorized delivery before
  starting another. Do not leave a task half-finished merely because a prototype
  launches. Checkpoint honestly if access or execution time prevents completion.
- Do not spawn other agents by default. Use them only when the current user request
  or applicable higher-priority instructions explicitly authorize delegation.
  When authorized, give agents distinct scopes; avoid overlapping work and repeat
  reviews of unchanged code unless new evidence or a required gate warrants them.

## Preserve the product

- The pinned desktop reference is the comparison target. Reuse this repository's
  EOS calculations wherever practical; do not independently approximate formulas
  in Kotlin or substitute another project's engine without evidence and a recorded
  decision. A10 retains Kotlin/Compose, Chaquopy and serialized EOS within its
  recorded feasibility limits; preserve that architecture and its required checks.
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
- Use the explicit Windows local verification launcher and exact-commit evidence
  in [LOCAL-VERIFICATION](docs/android/LOCAL-VERIFICATION.md). Full delivery keeps
  every desktop/reference, build/package and offline native gate, plus screenshot
  review. Focused development checks do not replace the complete required suite.
  Publish only the truthful `local/full-verification` result after full proof and
  review; an unexecuted Actions check is never a pass. Hosted workflows are manual
  fallbacks on the setup/B09.1 branch until that branch reaches the default branch.
  No unattended self-hosted runner is authorised. W02 setup alone did not
  authorize feature continuation. Follow current STATUS and explicit later owner
  authorization; historical pauses do not override a later scoped resumption.
  Setup success never supplies feature/native delivery evidence.
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
- Resume from the live repository and existing checkpoint; keep delivered work
  closed. Use focused checks while developing, then run every required check for
  the final revision. Reuse valid passing results and artifacts for an unchanged
  tested revision only when relevant inputs, dependencies, configuration and
  environment remain unchanged and the evidence is still applicable; do not rerun
  them merely because work resumed.
- Follow long-running checks through an existing watcher or completion notice.
  Investigate the specific failure before retrying; group related corrections,
  avoid duplicate log polling and bookkeeping, and update the checkpoint when a
  milestone, decision or blocker changes. Bound diagnostic log size and duration,
  and choose monitoring intervals appropriate to expected progress and required
  safety response times; preserve all safety gates. Explain material delays once.
- For quota, billing or access blocks, record the exact error and owner action
  once. Do not retry an unchanged block; continue independent authorized work
  within existing work-in-progress limits, or save the checkpoint and pause.
  After access returns, rerun only necessary failed or blocked jobs.
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

## Continue ready work

Continue ready, in-scope work automatically after each reviewed checkpoint. Maintain
a short dependency-aware ready queue. A blocked test, environment, or release gate
blocks only dependent work; continue independent implementation. Keep integration
frequent and unfinished work bounded. Stop and report only when remaining work
genuinely needs unavailable access/evidence or an owner decision/permission. Preserve
scope, data protection, resource limits, release qualification, and explicit pause
instructions.

Before execution, review the selected outcome’s plan: split it into bounded tasks
with clear interfaces, actual dependencies and testable exits, and correct gaps or
contradictions. At each meaningful checkpoint, briefly check that the next task
still serves the agreed outcome and is the highest-value ready work. When new
findings materially change the approach, update and review the affected plan
before continuing. Automatic continuation does not authorize new scope. Do not
repeat a whole-plan audit for every small edit; retain safety, resource, release
and explicit pause boundaries.

## Agent skills

### Issue tracker

For issue/spec tracking, read `docs/agents/issue-tracker.md`.
The configured tracker is GitHub Issues in `Sussic/Pyfa-android`.

### Triage labels

Before triage or label changes, read `docs/agents/triage-labels.md`
for the five canonical role mappings.

### Domain docs

Before codebase exploration, read `docs/agents/domain.md`
for the single-context layout and domain-document consumer rules.
