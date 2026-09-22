# Development and verification

## What exists today

This is a desktop Pyfa fork with an A01 desktop-reference harness and an A03–A05
[headless adapter](../../android_bridge/README.md). A06 adds the isolated
[Android project, toolchain and native commands](../../android/README.md).
A07 embeds EOS and the full pinned dataset, with native A01 numerical parity and
ARM64 package inspection; [evidence](evidence/a07-native.json) and STATUS record
the limits. A08 adds [native A04 projection evidence](evidence/a08-native.json)
with multiple-recipient invalidation and repeated removal. A09 adds
[native A05 command evidence](evidence/a09-native.json), including skills, implants
and recipient cleanup. A10 preserves those five native tests and adds a separate
fresh-process performance test with 123 desktop-matched snapshots. Its source-refresh
correction adds two forced-GC regressions: 29 headless tests plus eight utilities
now pass on Windows, alongside all independent references and real migration/backup.
[Decision and reproducible measurement boundaries](tasks/A10-embedding-feasibility.md). The separate
`Desktop reference` workflow validates the independent host oracle, desktop
migration compatibility and the separate headless adapter; it is not an Android
build. [Headless commands and evidence](../../tools/android_headless/README.md)
record the behavioral tests and fresh-process comparisons; A10 raises the count to 29.

B01 adds the typed bridge, B02 durable graph storage, B03.1 the fit library
lifecycle/search UI, and B03.2 organization/navigation. The required host suite
has **90 tests** with B04.2.1: 29 headless, 14 bridge, 14 persistence, 13 library,
six equipment discovery, six empty-hull and eight reference utilities, plus
independent calculation/catalogue/empty-hull exports and migration.
Native CI requires **20 executions**: five functional, separate A10 performance
and B01 contract, three B02 persistence phases, three B03.1 library phases and
four B03.2 organization/navigation phases, separate B04.1 equipment discovery and
two B04.2.1 empty-hull creation/restart phases. Earlier
counts above describe historical milestones, not permission to omit newer gates.
See [Windows setup](WINDOWS.md) for local builds and host verification; follow
[STATUS](STATUS.md) for current evidence and the authorized next task.

## Working A01 reference command

Follow [tools/android_reference/README.md](../../tools/android_reference/README.md)
for the isolated pinned checkout, Python 3.11 dependencies and exact commands.
The exporter uses the unmodified database builder/EOS, creates disposable data,
compares 38 statistics across an ammunition edit/restoration, and repeats in fresh
processes. Its checked-in fixture and runtime/data provenance are linked there.
Eight focused tests protect the comparator and database digest from false passes.
No inherited legacy test is claimed as repaired or passing by this work.

The upstream instructions are in [CONTRIBUTING.md](../../CONTRIBUTING.md). They
recommend Python 3.11, installing desktop requirements, generating translations
with `python scripts/compile_lang.py`, generating data with `python db_update.py`,
and starting `python pyfa.py`. These are upstream desktop UI instructions, not a
verified GUI launch in this Android project. The A01 harness calls the original
database builder with a disposable output path and does not need translations or
a display. It still needs genuine wx libraries through configuration imports.
Never run against a
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

## Native CI policy (A06)

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
