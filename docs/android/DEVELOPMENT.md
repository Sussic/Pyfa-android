# Development and verification

## What exists today

This is a desktop Pyfa fork with Android project instructions. There is no Android
Gradle project, working Android test suite or APK yet. A06 introduces the actual
build workflow after the early dependency investigation. Do not add a green
placeholder workflow or report a successful docs check as an Android build.

The upstream instructions are in [CONTRIBUTING.md](../../CONTRIBUTING.md). They
recommend Python 3.11, installing desktop requirements, generating translations
with `python scripts/compile_lang.py`, generating data with `python db_update.py`,
and starting `python pyfa.py`. These are upstream instructions, not commands
verified in this Android project. A01 records the working environment and exact
commands, including any display/system packages needed. Never run against a
developer's personal saved-fit database.

The old tox configuration and tests need auditing; missing paths and early-return
assertions are recorded in STATUS. Repair only what the chosen reference case
needs. Do not turn A01 into an unrelated rewrite of every inherited test.

## Reference comparisons

Keep the unmodified pinned desktop reference separate from the Android adapter.
Reference fixture records must include:

- Source commit, dataset identity/hash and dependency/runtime versions.
- Full fit inputs: items/charges/states, quantities, character skills, implants,
  boosters, settings, patterns, environments and connected fits where relevant.
- Expected raw values and units, not only screenshots or rounded display strings.
- Per-field numeric tolerances justified by representation/algorithm; identifiers,
  counts, states and relationships compare exactly.
- How to reproduce the result, and which effective edits should change which
  outputs (for example, removing a projected web restores the baseline velocity).

Use synthetic fits. Refresh expected values only for an explained upstream/data
change with a reviewed diff. Do not generate expectations and actual values via
the same new adapter. A changing source fit must invalidate dependent results;
tests must exercise edits, removal and reapplication, not just initial creation.

## Validation by task

| Change | Required evidence |
| --- | --- |
| Documentation only | Review, valid local references/dependencies and `git diff --check`. |
| Python adapter/calculation | Focused behavioral tests plus pinned desktop comparisons. |
| Android packaging/bridge | APK build, native boot/call test, actual packaged libraries/data. |
| UI or storage | Focused instrumented workflow tests; screenshot review where layout matters. |
| Offline behavior | Fresh install/first launch with networking unavailable, then edit/save/reopen. |
| Final install/update | Actual supported-device install and upgrade preserving fits and relationships. |

Successful tests must assert meaningful outputs. An emulator boot, empty activity,
mock engine, skipped scenario or early-return test is insufficient for parity.
Record native runtime evidence for each ABI actually tested; building an arm64 APK
does not mean it was executed on arm64 hardware.

## CI to implement in A06

- Pin a compatible JDK, Gradle wrapper (including distribution checksum), Android
  plugin/SDK, Kotlin, embedded Python and dependencies after the compatibility
  investigation. Record working commands here when they actually exist.
- Use least-required workflow permissions and pin third-party actions to reviewed
  commits. Builds/tests should not require personal access tokens or EVE login.
- Run focused host tests and native build/tests for relevant changes. Avoid
  duplicate push+PR runs for the same task branch. Use concurrency to cancel
  superseded runs on that branch, a timeout, and an explicit manual APK build.
- Do not schedule routine emulator builds. Documentation-only edits should not
  start native builds unless a genuine required gate demands them.
- Start without large persistent emulator caches. Upload concise reports/failure
  screenshots with one-day retention; upload an installable APK only on deliberate
  build runs. Preserve required evidence and checks; surface storage blockers.
- Use a suitable hosted runner and verify acceleration before retrying an emulator
  failure. No paid runner, spending-limit change or quota workaround by default.
- Inspect one useful error excerpt, batch fixes and rerun only after a relevant
  change. Never poll by dumping full logs or repeatedly retry a quota failure.

## Delivery

Implementation branches and PRs use the task ID. The PR explains the user-visible
outcome, scope, verification and remaining limitations. Delivery follows the user
authorization in the current session; these docs do not independently grant or
require permission to merge/publish. Update STATUS and the roadmap before ending.

Early APKs are development builds. Before repeated user-facing updates, R02 must
establish a stable signing identity, versioning and an install-over-existing-app
test. Never commit signing secrets or silently require uninstalling saved fits.
