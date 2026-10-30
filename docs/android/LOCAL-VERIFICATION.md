# Explicit Windows verification

## Current execution and artifact accounting

[EXECUTION](../../EXECUTION.md) explains the current Initia/MSI workflow;
[execution-policy.json](../../execution-policy.json) owns all live resource values.
The launcher loads that file and records its hash. It counts project roots once
by filesystem identity, including checkouts, owned tools/caches and evidence.
Add external generated roots with -ArtifactRoot. Shared installations are charged
once by ownership. The legacy -ArtifactBudgetGiB override has been retired.

Resuming an old run retains its accounting roots and as-run limit in history;
it uses the current policy for new writes instead of restoring a legacy cap.
Project-storage decisions use the JSON prompt threshold. Physical disk checks
reserve the JSON floor plus forecast copies/build/AVD writes. Stored evidence is
preserved when admission fails. Current output locations come from the policy.

Dated resource values in the sections below describe past attempts only. Use
the policy loader for future jobs; archived launch descriptors require new
policy-bound execution rather than unchanged replay.

Successful cleanup requires all planned gates to pass, an intact file manifest,
registered AVD identities, a stopped emulator and paths wholly inside that run.
It covers avd, avd-rN and avd-c04-rN. Junctions, redirected paths, unexpected
contents, unregistered runtimes and evidence-referenced runtime files fail closed.
A hash-bound runtime-cleanup.json records completion. Historical receipts keep
their original validation contract. Paused/failed guests remain until triaged;
explicit native retries create a fresh runtime without destroying the failed one.
A storage decision pauses only the writes needing it; continue independent work.

Keep one reusable build output location and reuse unchanged hash-verified APKs.
No historical artifacts are automatically deduplicated or evicted by this change.
The current external C04 build directory must be included with -ArtifactRoot when
using the integrated launcher. Execution admission and sustained-pressure handling
come from the current policy, separately from artifact accounting.

W02 demonstrated the complete Windows WHPX replacement: 78 gates (48 independent
reference/host, five build/package, 25 native), all inherited offline assertions,
raw validators and reviewed screenshots. [Receipt](evidence/w02-local.json) records
actual commits, earlier failed launcher attempts and retained evidence. B09.1
feature delivery is resumed under explicit user authorization; setup proof remains valid.

## Reuse a qualified external C04 build for focused development

`android/ci/check-drones.py` accepts `--verified-inputs <absolute-descriptor.json>`
and `--verified-inputs-sha256 <reviewed-SHA256>` together. Without both options,
its existing clean-Git requirement and conventional APK paths remain unchanged.
This explicit mode preserves the actual dirty status and records `commit: null`;
the original build source and the executing helpers have separate identities.
It never supplies full-delivery or `local/full-verification` evidence. The full
reporter's default `validate_native` call rejects snapshot-mode reports.

Use a small external JSON descriptor, not a source copy or another launcher:

```json
{
  "version": 1,
  "source_manifest": {"path": "<absolute-existing-source-map>", "sha256": "<SHA256>"},
  "qualification": {"path": "<absolute-existing-package-result>", "sha256": "<SHA256>"},
  "apks": {"app": "<absolute-app-APK>", "test": "<absolute-test-APK>"},
  "reviewed_changes": {
    "android/ci/check-drones.py": {"before": "<qualified-hash>", "after": "<reviewed-current-hash>"}
  }
}
```

The source map reuses the existing `candidate` fields (`root`, `head`, `branch`,
`status`, `files`) and `candidate_sha256_map_binding.sha256`: SHA256 of UTF-8
ordinal-sorted `path + NUL + lowercase SHA256 + LF`. The package result must bind
that same source map, report unchanged maintained sources, passing assembly/lint/
package qualification, and identify both APK hashes/sizes in `outputs`. Its
hash-bound lint/package child receipts must still match. Preserve the original
source map, receipts and failed attempts; never rewrite them for helper changes.

For version1, `reviewed_changes` must list exactly every current difference from the original
map, with exact before/after hashes. Only these six reviewed helper/test/docs
paths are eligible: `android/ci/check-drones.py`, `android/ci/drone_delivery.py`,
`android/ci/test_drone_runner.py`, `android/ci/test_drone_delivery.py`,
`docs/android/LOCAL-VERIFICATION.md`, and
`docs/android/tasks/C04-native-development-plan.md`. It is an eligibility list,
not an automatic exclusion: unchanged files need no entry. Any inventory,
production, Kotlin instrumentation, fixture, dataset or build-configuration
change stops reuse. Review the descriptor and its digest independently before
execution. Do not regenerate a new trusted descriptor merely to accept a mismatch.

Version2 adds one mandatory `documentation_review` reference (`path` and
`sha256`) to the same descriptor. All original source names, HEAD/branch,
build/helper/APK hashes, qualification receipts, default clean-Git behavior and
full-delivery restrictions remain checked. This does not allow arbitrary Markdown
changes. In addition to the six existing eligible paths, only `AGENTS.md`,
`docs/android/ROADMAP.md`, `docs/android/STATUS.md` and the already eligible
`docs/android/tasks/C04-native-development-plan.md` may use this reviewed control
document path. `reviewed_changes` still lists every source difference exactly.

The separately reviewed and hash-pinned JSON record has exactly these fields:
`version: 1`, `source_manifest` (identical to the descriptor's reference),
`qualified_source_binding_sha256`, `executing_source_binding_sha256`,
`reviewed_changes`, and `review_notes`. Both bindings use the complete source-map
algorithm above. Its changes and nonempty per-file review notes must cover
exactly the changed documents from the four named control paths; each before/
after hash must equal the descriptor and actual source. The record is an explicit
review attestation, not a machine judgement that modified instructions are safe.
Review the actual changed instructions and acceptance text before pinning it.

Routine tracker edits therefore require renewed exact source/control bindings;
they do not require rebuilding unchanged APK bytes or erase applicable build/lint/
package proof. Never edit a frozen receipt, suppress a source mismatch, silently
refresh a review after instructions change, or reuse a stale record. The complete
executing binding also makes a changed helper invalidate this documentation
review. Qualify and pin final helper/test/tracker bytes together, then retain the
original build identity separately. Use the existing `resolve_inputs` entrypoint
for offline provenance resolution; it starts no Android transport. Descriptor
eligibility does not provide resource admission, a heavy slot or native evidence.

After separately coordinated admission and disposable API36/x86_64 emulator
setup, use the same focused sequence:

```powershell
& <headless-python> -I -B android/ci/check-drones.py `
  --verified-inputs <absolute-descriptor.json> --verified-inputs-sha256 <reviewed-SHA256> `
  --serial <owned-emulator-serial> --avd <new-pyfa-c04-name> `
  --seed <new-details-seed> --conservation-seed <new-conservation-seed> `
  --evidence <new-external-evidence-directory> --heavy-slot-released
```

The runner validates source/receipt/APK bindings before any ADB action and again
at closure, retains packaged engine/independent fixture checks and records both
source identities, actual Git status, APK paths/hashes and all reviewed changes
in `inputs.json`. Its validator rechecks snapshot provenance only with the
explicit descriptor digest. All nine phases, eleven executions, offline/restart
checks, five screenshot reviews, deadlines and existing resource/ownership
protections remain required. Missing, changed or unbound evidence fails closed;
preserve it and correct the specific cause. This option neither creates an AVD
nor starts a service, downloads dependencies, rebuilds an APK or grants a slot.
Focused helper tests live in `test_drone_runner.py` and `test_drone_delivery.py`;
their synthetic host results do not establish Android runtime acceptance.

## Start and focused checks

Run from the repository root in PowerShell, with a clean committed checkout:

```powershell
./android/verify-local.ps1 -Action plan -Mode full
./android/verify-local.ps1 -Action start -Mode full
./android/verify-local.ps1 -Action start -Mode desktop -Gate history
./android/verify-local.ps1 -Action start -Mode desktop -Gate history_mutations
./android/verify-local.ps1 -Action start -Mode desktop -Gate resources
./android/verify-local.ps1 -Action start -Mode desktop -Gate capacitor
./android/verify-local.ps1 -Action start -Mode desktop -Gate tank
./android/verify-local.ps1 -Action start -Mode desktop -Gate output
./android/verify-local.ps1 -Action start -Mode desktop -Gate targeting
./android/verify-local.ps1 -Action start -Mode build
./android/verify-local.ps1 -Action start -Mode native
```

C03.2 currently adds35 retained inspector host gates: independent fresh/repeated
exports for18 families, separate implementation comparisons for14, presentation
regressions, complete worker-payload isolation and booster lifecycle comparisons.
The current plan has175 gates (97 host, five build,73 native). Fitted contexts additionally retain
cold/recalculated mode/cargo/implant/booster states; their native comparison remains
required. Focus one existing inspector family with
`./android/verify-local.ps1 -Action start -Mode desktop -Gate inspector_contexts`
(or another `inspector_<family>`). Reference-only families have no invented host
comparison. Sorting and plain text are Kotlin presentation behavior:
it has an independent reference gate
and a native/UI-helper comparison, with no fabricated host implementation gate.
The23 inspector native phases and independent summary run after every inherited
native gate: canonical and repeated-module identity each have two fresh restarts;
five context groups each have two fresh restarts; linked and four UI methods
retain full payloads and19 PNGs. This adds33 actual native executions (109 total).
The additional targeting prepare3 process separates construction from UI checks;
it preserves all assertions and the900s phase deadline rather than extending it.
Independent groups clear only this run's verified offline synthetic emulator
store after inherited evidence is retained. Complete prior artifact/runner
integrity is required before each restore. All115 delivered C03.1 gates retain
their original order and assertions. Full publication additionally requires
actual-report corruption proof and review of every inherited and new screenshot.
The summary now derives549 actual-report corruption rejections across21 report
groups:42 canonical checks in each of three workers,20 identity checks,25 in
each of15 context phases and14 for each linked kind. It first validates each
unchanged actual report, then mutates its payload and recomputes checksums.
Publication repeats the checks and compares the complete mutation proof; a
boolean or altered receipt cannot substitute. Context mutations use one streamed
temporary file at a time and remove it after validation. The retained C03.2 run
completed all175 gates and549 corruption checks, with234 hash-bound screenshot
reviews; [STATUS](STATUS.md) identifies its tested revision and local owner.
The [local delivery receipt](evidence/c03-2-delivery-review.json) records bounded
source/log/APK/review checks and successful full reporter validation on2026-10-13.
[Reporter output](evidence/c03-2-final-reporter.json) binds local commitf28341d4 to
tested source91088c0d; subsequent receipt/docs edits require source equivalence.
No status was published. Publication still requires a pushed delivery commit,
every actual artifact, complete screenshot review and the unmodified final reporter. Its
actual-payload/corruption validation is resource-heavy (the retained inspector
summary took462.172s); coordinate that step with other local verification owners.
The bounded review does not replace it or authorize a full-suite restart.

`headless:inspector_lifecycle` compares every original cold/warm field for all99
booster shapes in four fresh workers (25/25/25/24). Each retains the existing180s
worker limit. The inherited bridge gate still executes its18 complete tests;
no assertion or deadline is removed. Focus the lifecycle gate with
`./android/verify-local.ps1 -Action start -Mode desktop -Gate inspector_lifecycle`.
An initial combined19-test run passed158.798s; a repeated run hit180s while
executing the catalogue test after lifecycle completed. That failure remains
retained; partitioning the additional work preserves every required comparison.

C03.1 extends the required plan to 115 gates: 62 reference/host, five build and
48 native gates (75 actual native test executions). Targeting/navigation adds53
independent original wx/EOS cases, all437 hulls' hold inventory, all21 holds and
eight reference lock sizes. Three bounded prepare stages and a restored phase
follow C02, retaining
all earlier cases and gates;325 synthetic fits and215 required screenshots are
required. These are
requirements until the exact-commit receipt records execution and visual review.
The targeting focused pair covers module/skill/cargo/projected modifiers, history,
copy isolation, precise details and fresh-process persistence. The inherited output
pair retains target-profile and failed-save checks. Each targeting prepare stage
keeps the900-second deadline and original per-operation limits. The additional
process boundaries compare the exact typed graph, snapshots, inherited fits and
previous observations before continuing; no case or history replay is dropped.
Native phases keep their existing
900-second deadlines; the approved history-only Windows timeout is unchanged.

C01.3.2 extends the required plan to 105 gates: 58 reference/host, five build
and 42 native gates. Tank adds29 original desktop cases,21 focused
fixture/summary/transport regressions and two persistent native phases.
All prior gates remain required. These counts describe the required plan;
STATUS and the exact-commit receipt record actual execution.

C01.3.1 extended the required plan to 101 gates: 56 reference/host, five build
and 40 native gates. Defenses add fourteen original desktop cases, four individual
incoming-contribution witnesses, twenty-two fixture/schema/transport regressions
and separate native prepare/restored processes. Every inherited check remains.
For focused development, use `./android/verify-local.ps1 -Action start -Mode desktop -Gate defenses`.
Full delivery still requires `./android/verify-local.ps1 -Action start -Mode full`,
the reviewed screenshots and truthful exact-head local status. Existing pause/resume
commands apply to this run; no hosted dispatch is implied.

C01.2 extended the required plan to 97 gates: 54 reference/host, five build
and 38 native gates. Capacitor checks add twelve original desktop cases, ten
raw/fixture validator tests and two separate native prepare/restored processes.
These are requirements; STATUS records actual completed verification.

C01.1 extended the full plan to 93 gates: 52 reference/host, five build
and 36 native gates. Resource checks include fourteen original-desktop cases,
seven host tests, eleven validator regressions and three native resource processes.
Native mode continues to run every inherited prerequisite.

Full mode runs every required desktop/reference/host gate before Gradle and the
emulator. Build mode runs both APKs, lint, signature and full data/license/ABI
inspection. The focused history pair is development evidence, not a full pass.
Native mode rebuilds/inspects and runs the entire native chain: later phases need
previous synthetic saved fits and cannot run against arbitrary device data.

B09.2 extends the required full plan to 88 gates: 50 reference/host, five build
and 33 native gates. It adds four prepare/restore pairs (eight actual processes)
for all 28 remaining-mutation cases/168 states, bringing the required native
execution count to 60 and required screenshots to 146. Each new phase is a
separate resumable gate; process restart, offline assertions and earlier gates
remain required. History diagnostics also accompany those phases. Requirements
are not passing results; follow STATUS for the actual tested revision.

The launcher reuses `.venv/headless`, `.venv/reference`, clean pinned
`build/reference-upstream`, JDK17, installed SDK, readelf and the Gradle wrapper.
Optional `-SdkPath`, `-JdkPath`, `-SdkManager` select existing installations.
`-PythonPath` selects an existing pinned Python 3.11 headless interpreter;
`-ReferencePython` and `-Source` forward the helper's existing reference-runtime
and pinned desktop-source options. Defaults remain checkout-local. Missing
Python fails with the explicit path option; build/native/full start or resume
also rejects a missing JDK17 before dispatch. Plan and desktop actions do not
require a JDK or replace an inherited JAVA_HOME with a nonexistent path.
These options install nothing and retain source, clean-checkout, dependency,
resource, native and final acceptance checks.
Default SDK manager: `%LOCALAPPDATA%/Android/Sdk/cmdline-tools/22.0/bin/sdkmanager.bat`.
Installed command tools22 were verified against the official archive SHA256
`90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a`.
The shared image is `system-images;android-36;google_apis;x86_64` revision7.
Existing emulator36.2.12 and usable WHPX were reused. No CPU/RAM override is added.

Each native run owns a disposable Pixel2 AVD. Its verified name, emulator serial,
API36/x86_64 and offline settings bind all commands; attached phones are untouched.
Windows uses direct `am instrument` for the initial five assertions, rejecting
missing, duplicated, failed, skipped or incomplete runner events before producing
JUnit. This replaces the failed Windows UTP gRPC result channel; every actual
assertion and fresh-install/uninstall boundary remains. Linux retains Gradle UTP.
The later phase scripts preserve process restart and raw-value checks. The user
approved a Windows-only outer history deadline of 2400 seconds per prepare/restored
phase; Linux retains 900 seconds. All assertions, numerical tolerances, per-operation
limits and A10 requirements are unchanged. The original 900-second failure remains
recorded. The single diagnostic retry captures screenshots, process activity and
CPU observations every 30 seconds. Valid supplemental database timestamps
showed continued writes; the diagnostic stat format was corrected for future runs.

## Pause and resume

Start prints the absolute run directory. In a second PowerShell window, request
a pause using that exact path. Wait for the first command to return paused, then
resume from the repository root:

```powershell
./android/verify-local.ps1 -Action pause -Run 'C:/absolute/evidence/run-directory'
./android/verify-local.ps1 -Action resume -Run 'C:/absolute/evidence/run-directory'
```

Pause stops after the current gate, without interrupting an assertion or save.
The owned emulator stops and its writable test data is retained. Resume requires
the same clean commit/tree, skips completed gates and retries unfinished work.
A file lock rejects a concurrent resume. Both desktop and native boundary
pause/resume were executed; the native run resumed after performance without
replaying it. Ctrl+C is an interrupted failure, not a verified pause.

For a committed launcher repair **before any native gate passed**, explicit
`-AdoptLauncherFix` can reuse completed host/build results. It requires only the
three launcher files to differ, identical executed host/build function ASTs and
an identical plan. Every retained gate keeps its actual tested commit. Once
native work passed, changed test inputs need fresh applicable verification.
For a failed native mutation chain without a valid prerequisite snapshot,
`-RestartNative` archives prior raw evidence/JUnit/reviews, verifies the retained
APK hashes and rebuilds the entire native prerequisite chain. It permits only
reviewed launcher/reporting/diagnostic changes and the exact approved history
import/timeout expression while retaining host/build inputs and tested commits.
Do not use ordinary resume against a partially mutated test library.

The C02 profile-number/editor repair is an exact exception for the failed
`31cb2859` output-prepare run. The same `-RestartNative` command archives its
APKs, native evidence and actual commit stamps, retains only60 unchanged
reference/host gates, then rebuilds all five build/package gates and runs all44
native gates on a fresh disposable store. SHA256 guards accept only the reviewed
three Kotlin files and scoped launcher/reporting changes; engine, fixtures,
assertion removal and unrelated differences fail. This does not reuse native
results from an older application APK or claim an unexecuted hosted check.

## Summary-only recovery and fixture identity

A failed aggregate summary can be repaired without rerunning completed gates:

```powershell
./.venv/headless/Scripts/python.exe -I android/ci/summary_repair.py --run 'C:/absolute/evidence/run-directory'
```

Use only after diagnosing and authorizing the concrete correction. The helper
validates archived package evidence against original build logs, retained APKs,
source/database/library bytes and native reports, and preserves every failed run
snapshot. An unchanged summary commit cannot be retried. The fixture guard requires
reported hashes to match exact retained verified test-APK fixture bytes, and those
bytes to match the correct independent reference after CRLF-to-LF normalization
only. Content, other whitespace, missing fixtures and wrong hashes fail. Native
assertions, tolerances and A10 requirements remain unchanged. W02 retained its
original UTP/readiness/history failures and all three aggregate failures (missing
package report, contract normalized hash, then persistence normalized hash).
The final aggregate summary records its actual new tested commit separately
from the 77 reused results. No completed stage was replayed for these repairs.

## Evidence and required local result

Default evidence: `%LOCALAPPDATA%/PyfaAndroid/PyfaDevelopment/evidence/`, outside
OneDrive/git. Codex MSIX may resolve this through its Package LocalCache; use the
printed canonical path. Each run retains exact commit/tree, commands, exit codes,
timings, full logs, both APKs, lint/JUnit, raw reports, PNGs, source/data/tool and
emulator identities, plus file digests. It performs no automatic upload.
Successful runs remove their disposable AVD; paused/failed runs retain it.

Review every required screenshot; retain `screenshots-reviewed.json` with names,
hashes, observations and the tested commit. Then validate/publish the explicitly
local result, using the repository receipt URL for the delivery commit:

```powershell
./.venv/headless/Scripts/python.exe -I android/ci/report_local.py --run 'C:/absolute/evidence/run-directory' --receipt-url 'https://github.com/Sussic/Pyfa-android/blob/DELIVERY_COMMIT/docs/android/evidence/w02-local.json'
# Add --publish only after review and the commit has been pushed.
```

The reporter checks full completion, manifest/log hashes, successful latest
attempts, actual tested commits, source equivalence and screenshot review.
It publishes `local/full-verification`; it never creates an Actions success.
Delivery may reuse proof only when execution/product inputs remain identical;
permitted post-proof changes are the named reporting tests/code, instructions,
receipt/docs and manual workflow policy. Product/test changes require new proof.

## Hosted fallback and costs

Both workflow files retain `workflow_dispatch` as deliberate hosted fallbacks,
read-only permission, pinned tools/actions, concurrency, existing time limits,
one-day diagnostics and opt-in APK upload. Automatic PR triggers are retired only
after the local demonstration. PR #33 delivered B09.1 and setup to master on 2026-10-02; both hosted workflows
are now deliberate manual fallbacks on the default branch.
No release or scheduled job is added. No branch protection/rulesets were found;
no owner access step is currently required. If future rules require Actions names,
replace those names with `local/full-verification` after owner review, rather than
fabricating a hosted pass.

No runner service, paid platform or billing setting changed. Standard hosted
runners for public repositories are free; larger runners and storage over the
account allowance may incur charges ([GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
Manual fallback still uses hosted execution/storage. Local work uses ordinary
hardware, electricity/network and disk space; keep evidence only as needed.
Feature/ARM64/older-API/upgrade/phone usability acceptance remains separate.

## C01.1 edited resource reference

The direct fourteen-case resource fixture stays unchanged. Offline guns edited
through the original desktop service includes vacant slots; those can change EOS
zero scalar kinds without changing their values. The separately verified witness
is `resources-edited.json`; native preparation compares its exact physical slots,
raw kinds/values, units and displays. Reuse its receipt for unchanged reference
inputs. When changing resource/edit inputs, regenerate/check it independently:

```powershell
. ./build/windows-env.ps1
& $pyfaReference -I tools/android_reference/resources_edited.py --source build/reference-upstream --database android/build/engine/assets/engine/eve.db --output 'C:/absolute/new-reference-directory' --check tools/android_reference/fixtures/resources-edited.json
& $pyfaHeadless -I android/ci/test_resource_summary.py
```

A changed or added test fixture requires the engine-assets stage before Gradle:
use the complete build mode, then native/full verification as appropriate. Do not
reuse old staged assets merely because the application source stayed unchanged.
C01.1 retained 90 valid gates, three exact partial-store recoveries, every complete
native failure log and a missing-witness package failure; only affected builds and
prepare/restored/summary reran. Its receipt explicitly records the unavailable
first optional shared failure PNG/logcat. Required passing artifacts remain intact.

## Focused C01.3.2 tank checks

Use a fresh external directory for each reference or host evidence attempt:

```powershell
. ./build/windows-env.ps1
& $pyfaReference -I tools/android_reference/tank.py --source build/reference-upstream --database android/build/engine/assets/engine/eve.db --output 'C:/absolute/new-tank-reference-directory' --check tools/android_reference/fixtures/tank.json
& $pyfaHeadless -I tools/android_headless/check_tank.py --source build/reference-upstream --database android/build/engine/assets/engine/eve.db --output 'C:/absolute/new-tank-host-directory'
& $pyfaHeadless -I android/ci/test_tank_summary.py
```

The full launcher includes both tank phases after defenses, preserving all189
prior fits and their inputs/types, and restoring all230 fits in a new process.
Review its actual tank screenshots alongside every inherited screenshot.
Focused checks do not replace the full delivery suite or screenshot review.

C03.2 context reference now records805 direct and805 reconstructed states,3030
targets in each set. Original fitted identities/slots/side-effect flags and every
property remain required. Reconstructed expectations are selected only for actual
history/copy/restart; after history the next booster side-effect edit starts from
an independent fresh original-EOS baseline. A direct active-toggle's transient ORM
timestamp is not carried across that reconstruction. Cold construction and warm
recalculation assertions remain distinct. API/native phase counts,900s deadlines,
192MiB heap, all115 inherited gates, full174 plan and549 actual-report corruptions
are unchanged. The preserved direct-model-only reference receipt describes its
historical inputs; it is not proof for these changed context test assets.

C03.2 targeting verification retains all174 original gates and adds prepare3:
175 required gates/109 executions. Prepare2 constructs all53 cases (324 fits);
prepare3 runs every existing UI/copy/recreation assertion (325 fits), then a fresh
process restores everything. Each phase retains900s; no assertion,120s operation,
192MiB heap, numerical tolerance, screenshot or A10 requirement is reduced.
# Isolated October 18 supplemental D01.9 registration

The focused plan is available through
`python -I -B android/ci/local_verification.py plan --mode native --gate projected_module_charges`.
It reuses the existing build/package steps and one supplemental native_suite step;
the default 190-gate full plan is unchanged. The step uses existing Run.execute,
ArtifactBudget, C04 owner setup and the two-APK installation helper. It refuses
existing app installations, retains offline checks, compares installed APK hashes,
requires denied INTERNET permission, and validates exactly nine methods with
`offline_features_phase=projected_module_charges`. It refuses Python optimization.
The historical initial step now selects its exact five methods positively.

This local harness delta has host/static evidence only. No Android execution, fresh
process restart, screenshot/accessibility review, full qualification, upgrade or
data-retention gate is completed by it. It does not adopt the user's Pixel_9a API35
AVD; the existing owner still requires its approved API36 project profile. Complete
source/APKs, reviewed target configuration, current retention accounting, the outer
r12 guard and fresh native admission remain prerequisites before any start. The
owner's one-attempt OS-only CPU waiver does not change native admission.

## Focused G05.2 remote-repair adapter

The opt-in plan is
`python -I -B android/ci/local_verification.py plan --mode native --gate remote_repair_graph`.
It retains `dependencies`, `engine-assets`, `apks-lint`, `signature` and `package`
before one supplemental native phase. Default190, initial5, projected9 and
shield22 remain unchanged. The plan command itself does not execute those gates.

The phase selects exactly 42 existing methods: 22 in
`OfflineRemoteRepairContractTest`, 15 in `OfflineRemoteRepairModelTest`, and 5 in
`OfflineRemoteRepairUiTest`, with `offline_features_phase=remote_repair_graph`.
Its immutable explicit selectors must match the current Kotlin source inventory.
It reuses the existing C04 owner, serial-bound transport, API36/x86_64 identity,
fresh-install requirement, offline checks, two installed APK hashes and denied
INTERNET permission. Three class calls remain within the owner's unchanged
1200-second deadline. Missing, skipped, duplicate, extra or failed test events,
changed sources and mismatched retained raw logs cannot produce a pass receipt.
Python optimization is refused before transport.

The isolated source delta is prepared for narrow review and new synthetic host
checks; these checks are not yet execution evidence. They validate parser and
owner wiring using mocked transport, without invoking SDK tools or an emulator.
The earlier 58 pure-Python checks and 15 smoke-harness checks are not rerun for
copied files. Host checks do not establish Android compilation, instrumentation,
restart, screenshot/accessibility review, complete delivery or release identity.

Actual native startup still requires complete source-bound build inputs/APKs,
compatible owned run state, fresh resource admission and a coordinated heavy
slot. `start_emulator` reserves zero only for its own existing AVD directory;
it reserves 8 GiB for a new one. This does not waive the reviewed standing
build/native reservation. No compatible G05.2 reuse path is currently established,
and the new-run reservation does not fit the unchanged 32 GiB retention cap.
The frozen 956-file candidate, original checkout and all prior AVD data remain
preserved. No command in this section authorizes using the user's phone.
