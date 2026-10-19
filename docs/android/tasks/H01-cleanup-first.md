# H01 - cleanup-first implementation checklist

Completed locally 2026-10-16 after parent plan review and bounded execution release.
[STATUS](../STATUS.md) owns current execution; [ROADMAP](../ROADMAP.md) owns order.
H01.1: exact local checkpoint verified for all 2,328 selected source/config files,
32 local branch refs and 102 unique commits, with independent scope comparison
and four restore samples. All originals and Git objects remain in place.
H01.2: eight exact groups have retain/defer dispositions; no move or purge.
H01.3: source identity is now 35 / 0.1.0-c04 with static proof; new package/About
and R02 safe-upgrade proof remain distribution-only blockers.
H01.4: maintenance triggers below are deferred; none prevents C04 resumption.

Receipts: workspace task-2/h01-source-checkpoint-20261016/{manifest.json,
source.zip,result.json,RESTORE.md}, h01-classification-20261016.json and
h01-completion-20261016.json. The original helper allocation-assertion failure
is retained and explained in result.json; the declared 8 MiB total was unchanged.
Native/full builds still require a parent shared-host slot and fresh admission.
No additional generic user approval is needed for already released light work.

The checklist below records the accepted contract and triggers; completed H01.1/2
steps and their earlier release prerequisites are historical, not instructions
to repeat the checkpoint or ask for the same release.

H01.3 follow-on: reviewed POSIX cleanup v2 integrated on MSI 2026-10-17; exact
before/after hashes matched. Windows focused retention: 19 passed, 5 Linux-only
skipped. STATUS and task-2/cloud-integration-20261017 own the integration receipt.

## Shared boundaries and finite completion

Preserve C03.2 cddeff02, C04 2e518a2e plus working edits, phone prototype 72dd1673
and pinned reference 8b04f3b2. Keep existing memory, storage, ownership and evidence
limits. Credentials, signing keys, personal fits and session/account histories
do not belong in a source checkpoint. No whole-drive scans or reparse traversal.

H01 closes when H01.1/H01.2 are verified, concrete H01.3 issues are fixed before
their affected operation or retained explicitly as that operation's blocker, and
H01.4 follow-ups have their bounded triggers. A distribution-only blocker need
not prevent C04 development, but must not be called fixed. Optional refactors
cannot keep H01 open forever. Emulator resolution stays with C04, not H01.

For each implementation task, record exact inputs, changed paths, affected proof,
focused results and outcome. Reuse valid unchanged evidence; no repeated full
suites while the same blocker persists. Final technical delivery still requires
all applicable registered integration/native/offline/restart/screenshot checks;
R02 retains install-over-previous-build proof. Environment-blocked checks remain
explicitly unverified. Cleanup is not permission to waive gates or redesign them.

## H01.1 - recoverable exact source checkpoint (first)

- Paths: primary checkout
  C:/Users/HallT/OneDrive/Desktop/Documents/PyfaDevelopment and C03.2/C04 refs;
  C:/Users/HallT/.codex/worktrees/phone-ui-prototype/PyfaDevelopment; unique STATUS
  and build/usage-guard work in C:/Users/HallT/.codex/worktrees/3c02/PyfaDevelopment.
  Include all current edits and explicitly untracked android/ci/artifact_retention.py,
  test_drone_offline.py and test_drone_retention.py.
- Behavior/non-goals: record HEAD/refs and exact path/hash inventory; preserve
  binary-capable tracked diffs and byte copies of unique untracked source.
  Retain referenced commit objects. Before retiring a checkout use supported
  recoverable snapshots or a narrowly scoped verified Git bundle if needed.
  No whole-repository/cache/AVD archive, reset, stash, blanket ignore or discard.
- Dependency/approval: first after parent review and execution release. Admit a
  project-owned destination under current allocation limits and count checkpoint
  storage. No space/ownership means stop for that decision. Staging/commit/push
  and branch cleanup remain explicit boundaries; file preservation is not a commit.
- Verification/rollback: compare source bytes/hashes and included paths; check
  patch parseability without applying it; confirm unique refs remain available.
  Restore a small representative sample to an admitted temporary location,
  without overwriting live files or running app/tests. Preserve all originals.
- Done: one recoverable manifest covers every edited/untracked source and unique
  ref in scope, with exclusions, destination and restore instructions. No Android
  build or regression suite is needed.

## H01.2 - supported entrypoints and artifact disposition

- Paths: primary build/, android/build/, android/app/build/, .venv/;
  workspace C:/Users/HallT/Documents/Codex/2026-10-13/task-2;
  project PyfaAndroid/PyfaDevelopment evidence/development/gradle-home roots;
  worktrees 1241/3c02; LOCAL-VERIFICATION.md and android/verify-local.ps1.
- Behavior/non-goals: identify the supported normal launcher/current guard and
  pinned input bindings. Classify a first batch of at most eight exact candidate
  groups from existing inventories and shallow targeted reads: active inputs,
  frozen evidence, regenerable outputs, historical helpers. One disposition
  manifest records owner/current use, producer, dependency references, content
  identity, allocation, regeneration source and restore route. Unknowns stay.
- Preserve: 1241 needs ignored-content and ownership checks before archival.
  3c02 has a unique usage guard; establish owner/live use without operating it or
  reading account data. Keep phone prototype and build/reference-upstream.
  build/ is not wholly disposable. Preserve pinned APKs, reference expectations,
  source/tool caches needed for offline rebuilding and useful failed evidence.
- Evidence limits: workspace c04-reclaim-inventory-20261014.json recorded generated
  asset/env/pip copies; c04-pixel-diagnostic/outcome.json records a later allocation
  and already-completed single-file cleanup. These are dated, not current reclaim
  totals/deletion approval. Sparse logical sizes are not physical allocation;
  candidate manifests can overlap. Ordinary and Codex-package PyfaAndroid
  evidence paths had the same filesystem ID: revalidate identity and never
  double-count pathname aliases or hardlinks.
- Dependency/approval: H01.1 first. Prefer manifest-backed recoverable quarantine
  or owner-managed archive over purge, after checking exact-path consumers.
  Moving still needs authorized execution. Copies need headroom; same-volume
  quarantine may reclaim nothing. Cross-volume moves, worktree removal, purge,
  resource expansion or external destinations are not implicit approvals.
- Verification/rollback: reuse valid artifact_retention.py ownership/identity/
  redirect/evidence-hash machinery, not another scanner. Freshly revalidate only
  selected candidates before future mutations; confirm retained APK/reference/
  evidence hashes and restore mapping afterward. Any changed retention code needs
  focused foreign-path/live-process/missing-proof tests and launcher integration.
  Pure classification needs no app suite. No new whole-tree scans or builds merely
  to justify deletion. Retain originals until recovery is verified.
- Done: supported entrypoints and the batch have explicit retain/archive/
  regenerate dispositions and truthful outcomes. No mandatory reclaim target.
  Deferred items stay with owner/reason; another batch is a separate outcome.

## H01.3 - concrete safety and distribution blockers

- Paths: android/app/build.gradle.kts (audit-time identity: 0.1.0-c03.2/versionCode 34),
  MainActivity.kt About display, R02 packaging and exact ownership/path defects
  demonstrated by H01.2. The old Cargo-to-Drones routing bug is already fixed;
  do not relabel audit concerns as new confirmed bugs.
- Behavior/non-goals: before distribution, identify the real candidate/build
  unambiguously and establish monotonic versions with R02 signing/data retention.
  A label change alone does not finish R02. Correct proven unsafe path/cleanup
  handling before that operation while retaining provenance guards. No formulas,
  phone migration, new feature or general security rewrite.
- Dependency/approval: H01.1 before edits; H01.2 establishes any cleanup defect.
  Code/tests require resumed scope. Secret/device access, resource changes,
  signing operations and publication retain their explicit approval boundaries.
- Verification/rollback: package/version/manifest identity checks and approved
  device About/install-over-previous-build proof preserving fits/relationships.
  A proven retention issue gets its smallest reproducer and existing focused
  ownership/redirect/manifest tests plus relevant launcher integration. Preserve
  pre-change source and prior package references; never uninstall personal data
  as rollback. Retain required final integration checks for changed inputs.
- Done: the finite evidenced issue list is verified fixed or explicitly blocks
  only its affected operation. Packaging remains a distribution blocker until
  R02 proof passes; native infrastructure failure remains separately with C04.

## H01.4 - targeted maintenance with narrow triggers

All items depend on H01.1 and parent release of implementation/test scope. Select one at a
time when triggered; keep public contracts and existing safety gates. Preserve
pre-change source/receipts, revert only the isolated diff on regression, and run
applicable final integration checks after focused checks. No broad rewrite.

### H01.4a - historical harness cases

Trigger: before changing verification-resume behavior again.
Paths: android/ci/local_verification.py, report_local.py, existing pending_* tests.
Isolate historical commit/hash exceptions in one compatibility module/registry;
keep the normal launch/current validation path direct. Preserve exact allowed
diffs, tested revisions, rejection behavior and required gates; no generalized
migration framework or weaker provenance matching.
Verify old accepted cases, near-miss/hash-change rejection, old receipt readback,
current plan equivalence and focused launcher/reporter integration.
Done: the selected historical cases are isolated with equivalent outcomes,
not every script modernized. Original receipts and helper versions remain intact.

### H01.4b - explicit existing navigation state

Trigger: before extending routing or integrating approved U01.
Paths: MainActivity.kt, existing editor callbacks, DroneUiTest and library/
navigation restoration tests. Replace independent show* flags with one explicit
route, destination arguments and return state. Preserve fit identity, selection,
drafts, scroll and recreation; no new framework, redesign or feature is required.
Verify Cargo -> equipment -> Drones, module/charge/variation return, inspection
base/detail return, Back, fit switching and activity/process restoration using
visible-state assertions. Retain the already-fixed route-priority regression.
Affected native workflows/screenshots and final integration are required; pending
environment access cannot be reported as a pass.
Done: those existing routes have unambiguous state with unchanged accepted behavior.
This internal refactor does not imply U01 design approval.

### H01.4c - diagnostic/runtime separation

Trigger: only when the next runtime/diagnostic change would otherwise add mixed
responsibilities; defer if it does not help that bounded task.
Paths: EngineRuntime.kt and mobile_runtime.py diagnostic/benchmark helpers and
their callers. Extract only the touched helper group behind its existing debug
boundary; retain the single engine worker, startup, typed dispatch and
mutation/publication order. No engine rewrite or new service framework.
Verify release rejection of debug-only calls, debug dispatch on the same worker,
response contracts and affected startup/bridge integration.
Done: that named helper group is separate with equivalent behavior, not every
large file split. Preserve old source/bindings for isolated rollback.

### H01.4d - incremental standards for changed adapter/harness code

Trigger: alongside the next android_bridge/ or android/ci/ change, not a standalone
formatting campaign. Record conventions for formatting/imports, public types and
explicit error handling, using existing Python 3.11/compiler/Android lint tools.
If a new formatter/static checker is proposed, pin it and obtain required
installation/dependency approval; do not install implicitly or block unrelated
work because it is absent. Baseline old findings explicitly and apply checks to
changed scope; never exempt new correctness failures silently.
Verify selected modules and meaningful affected behavior, then normal final
checks at delivery. Keep mechanical formatting separate from semantic changes,
preserve prior bytes and avoid upstream desktop churn.
Done: changed scope follows recorded rules with no unrelated reformatting;
legacy desktop tox/style debt remains outside H01.

## Handoff

Record completed dispositions and deferred triggers once in STATUS. Return to
C04's bounded admission/diagnostic when authorized, or select already-permitted
independent roadmap work if native execution remains blocked. Keep R02 identity/
upgrade proof before distribution. Full offline parity, projections, commands,
graphs and saved fits remain required. Cleanup completion establishes neither a
safe reclaimable total nor an everyday-use release.
