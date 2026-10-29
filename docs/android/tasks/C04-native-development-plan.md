# C04 native acceptance plan

## Current progress pointer - 23 October 2026

[The canonical tracker](../ROADMAP.md) owns current C04 progress; [STATUS](../STATUS.md) owns its execution pointer. This plan retains the acceptance contract, not launch permission. Runtime18 refused physical storage before Android (task-5/RUNTIME18-RESULT.json); no automatic retry. The qualified candidate still has 0/9 accepted native phases, 0/11 executions and 0/5 screenshot reviews; twelve reference/headless gates and the Windows harness do not close those criteria. Preserve the 190-gate full plan and API36 app acceptance; API35 OS-only diagnosis is separate. Earlier counts, cleanup/slot grants and next commands below are historical. All heavy tests are stopped; no cleanup or workload is authorized by this documentation update.


## Current execution contract - 2026-10-17

[STATUS](../STATUS.md) owns authorization and the single next action.
Bounded cleanup, implementation and small focused checks have parent release;
H01 is complete. The granted single comparison slot was released after read-only
admission failed on 2026-10-16: ten-second CPU 34.107% >25%; all checked source/
APK/frozen-binding, storage and memory conditions passed. Zero emulator launches;
no guest changed. See task-2/c04-quiet-admission-20261016/result.json. No automatic
retry; parent must select a quieter window or the existing alternative path.
A later parent grant after Beacon completion also stopped at admission on
2026-10-16 at 13:58:58 UTC: CPU48.711% over10.016s versus <=25%, with all other
checked bindings, storage, memory and independent CI-job conditions passing.
Zero emulator/app launches; no guest changes or automatic retry. Evidence:
task-2/c04-quiet-admission-after-beacon-20261016/result.json and handoff.json.
That slot is released. There is no active emulator/full-build slot. This section
supersedes historical launch, fresh-AVD, uncompiled and retry instructions below;
it does not itself release native execution.

Latest parent grant after Jita on 2026-10-17 stopped before launch: CPU66.349%
>25%, available RAM6,798,856,192B <8GiB; source/APK/full guest/storage and
process checks passed. Zero emulator/app/build executions. Slot released; no
unchanged retry. See task-2/c04-slot-admission-20261017/handoff.json. The current
host-resource blocker supersedes earlier pending-slot notices.

### Qualified external artifacts and preserved dirty source

For the current merged candidate, use the canonical
[qualified external C04 build procedure](../LOCAL-VERIFICATION.md#reuse-a-qualified-external-c04-build-for-focused-development).
Its explicit verified-input mode supersedes historical clean-checkout and
hardcoded APK-path assumptions for focused development only. It preserves the
original build-source binding, separately binds reviewed executing helpers and
rejects every unreviewed or product/test/input change. Default clean-Git and full
delivery requirements remain unchanged. Current qualification and authorization
come from STATUS and the parent handoff, not dated APK examples in this history.
No runtime phase is authorized or recorded as passing by this procedure link.

### Candidate and finite acceptance

C04 2e518a2e is implemented; Kotlin and debug APK builds succeeded. Compare
preserved later test/harness edits with package inputs before reuse; HEAD alone
does not establish provenance. C03.2 cddeff02 is locally verified and unpublished.
Reuse proof only within documented input/source-equivalence boundaries.
The later source identity correction is versionCode 35 / 0.1.0-c04; no APK has
been rebuilt for it. Old package hashes/manifests retain their original inputs.
Do not claim the corrected label, compiled package or safe upgrade from static
checks. An OS-only diagnostic can keep its old bound APKs without installing them.

Close the existing contract, fresh-ui, core, linked, conservation,
conservation-restored, prepare, restored and mutation-ui phases, their exact
assertions, offline/recreation/restart proof and five screenshot reviews.
Preserve the registered 190-gate full plan and A10 requirements. Valid unchanged
evidence is reusable; a changed APK does not automatically inherit native proof.
A passing phase alone does not complete the milestone. The historical acceptance
table retains required outputs; its execution status is superseded by STATUS
and the latest retained phase receipts.

The approved active-count conservation decision is resolved. Preserving existing
rolled values belongs to C04; creating/editing mutations belongs to C10.
Fighters, new UI design and optional features do not extend C04. Defects needed
to meet its accepted behavior remain required fixes.

### One proposed diagnostic, then a decision

H01's cleanup handoff is complete. For C04's next parent-coordinated slot, perform one bounded
read-only admission assessment of source bindings, ownership, shared workload,
memory/storage and host CPU. This is later than STATUS's current H01 next action.
Diagnostic execution follows parent plan review and coordinated resource release
within the user-approved limits. Propose ONE quiet-host comparison boot using the
reviewed lower-pixel profile/launcher: 540x960/210 dpi, 2 vCPUs, 2048 MiB,
below-normal priority, unchanged WHPX/renderer/Vulkan-off and all existing
memory/storage/ownership protections. Acceptance-device requirements stay intact.

Proposed quiet-host condition: a ten-second mean host CPU at or below 25%, with
competing heavy work coordinated, not killed. This is a conservative experiment
condition contrasting the old 57.1% baseline, not a measured Pyfa requirement or
permission to change host settings. Record process attribution where readable;
unavailable counters stay unknown.

Retain the existing 1200-second outer hard timeout, earlier failure stops,
16 MiB total/8 MiB host-evidence envelopes, configuration restoration and owned
process cleanup. Do not extend budgets for more traces. If collection code
changes, review its changed scope only; frozen sources/receipts remain immutable.
Stop on the first observed SystemUI failure, failed safety gate or timeout, or
after the existing bounded settled observation. No app install or product tests
belong to this comparison. Success is responsive settled UI without observed ANR
during that observation; it is not C04 acceptance or proof of sole causation.

If admission fails or the same boot failure recurs, STOP this diagnostic path.
Record the result once and propose a supported alternative execution environment
or explicitly authorized disposable test device. Do not continue guard versions,
renderer/priority/limit/resolution changes without a distinct evidence-backed
hypothesis and separately bounded decision. No personal phone wipe/install,
software download/purchase or resource expansion is implicit in this fallback.
Independent authorized product work may later proceed, but cannot close the
blocked native acceptance by proxy.

After diagnostic success, the remaining C04 phases still require resumed scope
and a coordinated resource slot. Reuse valid builds/proof; stop on a substantive
failure, correct its cause, then rerun affected proof and required final coverage.

### Delivery boundary

Native acceptance, full registered evidence and screenshot review close the
technical milestone, not merge/publication/release. ROADMAP brings packaging
and early real-device feedback forward without waiving final parity/usability.

<details>
<summary>Historical plans and checkpoints - evidence, not executable instructions</summary>


Approved pixel diagnostic outcome checkpoint (2026-10-14): user approved the
exact duplicate cleanup and one lower-resolution boot at 12:21:09 UTC. Only
inspector-command-expected.json (18,515,517 bytes) was deleted after fresh
identity/hash/link/APK-member checks. The retained APK and unique evidence remain.

The reviewed wrapper passed 22 focused host tests, including real guard-timeout
restoration. A first test-fixture reserve failure is preserved; production caps
were unchanged. Final bindings and fresh preparation/admission passed. One boot
ran at 540x960 / 210 dpi, with the same 2 vCPUs, 2048 MiB, below-normal priority,
WHPX, SwiftShader and Vulkan-off. Original acceptance-device requirements remain.

Boot completed in 56.359s (R13: 70.125s), but the same KeyguardService ANR recurred
after 20,002ms. Both PNGs decode; settled screenshot visibly shows System UI is
not responding. Guest PSI avg10 CPU-some88.11%, IO-some18.62%, memory-some0.12%.
Host baseline CPU averaged57.06%; native-interval CPU averaged94.09% on8 logical
processors. Sampled disk read latency max6.710ms, write max0.325ms, queue max2.
Own and current launcher job CPU-rate flags were0; more distant ancestors remain
unmeasured. Full allocation scans are diagnostic overhead with retained intervals.

Pixel reduction did not cure the ANR. Host contention is now measured, so this
is not a low-host-contention control and does not establish priority causality.
Warm userdata and changed host conditions also prevent a strict causal A/B claim.
No app execution, full UI rerun or clean acceptance gate occurred.

Guard0/noabort in96.531s, peak job commit3,108,257,792B, no cap events or remaining
PIDs. Launcher had no measurement/budget error, cancellation or remaining watcher.
Original config restored byte-for-byte (SHA256212b419b8847e17942d178c0035c5695d242fbdef89a7f80e5bcaba4aff86ed0).
Post-run host audit0/noabort15.91s verified source/APKs, stopped guest and locator.
Launch growth3,168,492B; audit host evidence3,082,467B, within16MiB total/8MiB host
envelopes. Audit surplus15,561,908B above8GiB reserve is a snapshot before final
small receipts/checkpoints; future admission must be fresh.

Completed authorized diagnostic. No further deletion, cap/priority change or
native retry. Next proposal should identify CPU/scheduling pressure with bounded
host attribution or a targeted trace before selecting another treatment. All
pending C04 native acceptance phases remain pending. Canonical evidence:
task-2/c04-pixel-diagnostic/outcome.json and outcome-review.json; raw screenshots,
ANR logs, host counters, restoration and guard receipts are in the same directory.


Next boot diagnostic PLAN checkpoint (2026-10-14): read-only follow-up and
independent plan review completed. R12 enforces below-normal priority, not a
numerical CPU-rate cap; inherited ancestor limits and host CPU/disk latency
were not measured in R13. One isolated540x960/210dpi boot is within development
scope, retaining all CPU/RAM/priority limits and acceptance-device requirements.
No native execution is authorized by this planning checkpoint.
Canonical plan: task-2/c04-next-boot-plan-20261014.json; exact cleanup proof:
c04-next-boot-evidence-20261014.json. Proposes only one18,515,517B generated
inspector-command-expected.json, matching the retained APK member. No deletion.
16MiB total new-allocation allowance plus512KiB planning/receipts; fresh exact
cleanup approval/revalidation, implementation review and admission still needed.
No more diagnostic-version copies; prior evidence/pins remain immutable.


R13 boot-only diagnostic checkpoint (2026-10-14): authorized R12 binding
and independent review completed; 26 host checks passed. Fresh memory/storage
admission passed. Existing 2048MiB/2-core guest was reused without a full copy,
app launch/install/reset or profile change. Boot completed in70.125s.

SystemUI PID920 ANR was captured: KeyguardService waited20168ms, ErrorId
4729b681-a5dd-4394-8cec-16dffb328215. Guest PSI avg10 CPU-some84.10%,
IO-some31.28%, IO-full3.57%, memory-some0.12%. Renderer activity was high;
multiple other platform apps also ANRed. Current windows showed SystemUI and
launcher ANR dialogs. Lastanr separately reported no ANR; discrepancy is retained
and unexplained. Later Binder failure belonged to Google Play Services PID2420,
not SystemUI. Evidence supports boot infrastructure contention, not a proven
internal blocked stack, host root cause, memory exhaustion or verified remedy.

Automated evidence watcher crossed its4MiB stop threshold. Native guard ended
88/operator cancellation after195.657s with no remaining job PIDs. This generic
label reflects the watcher, not a human cancel or memory/telemetry failure.
Peak job commit3,270,836,224B remained below3,899,998,208B; no cap notification.
Screenshot was interrupted at451,282B, lacks terminal PNG IEND and is invalid.
No completed diagnostic receipt/snapshot; zero clean UI gates accepted.

R12 now has one real live native-path recovery: ADB PID45276 at105.344s,
initial Win32 error5 followed by native-format success on the same0x101000
handle. Identity/job/liveness verified; sample remains incomplete with null
aggregate private telemetry. Initial failure preserved.

Independent outcome review and post-run audit passed: unchanged source/APKs,
guest58entries retained, no emulator/QEMU/ADB. Audit measured4,563,126B R13
evidence within the8MiB monitored envelope (not an OS quota). Total allocation
25,768,682,027B left1,121,749B above the mandatory8GiB reserve under32GiB cap.
These are audit snapshots before final small reports/checkpoints. The base
reserve fits, but another8MiB evidence allowance does not; fresh admission is
mandatory. No deletion, security/quota change, commit, push, merge or release.

Next proposal only: a separately approved lower-pixel-count boot experiment,
holding RAM/cores/renderer/caps constant, after defensible storage admission.
Lower resolution is a testable hypothesis, not a proven fix. No further native
retry or full UI rerun is authorized by this completed diagnostic. All seven
pending C04 native phases remain unaccepted. Preserve all prior evidence.
Evidence: task-2/c04-r13-interpretation-20261014.json,
c04-r13-audit-outcome-20261014.json, c04-r13-guest-inventory-20261014.json,
c04-boot-r13-artifacts/emulator-early-logcat.log and boot-windows.log.


R11/R12 host telemetry checkpoint (2026-10-14): the user authorized a
minimal Git-only reproduction and reviewed guard correction. Android stayed
stopped. No deletion, security/privilege change, quota increase or cap change.

The existing identity handle already requested 0x101000 (limited query plus
synchronize), documented as sufficient for image path and modern memory APIs.
R11 ran exactly three git --version cases, after eight host tests passed.
Its held-handle probe reproduced error 5 while Git PID22924 remained unsignaled:
same creation identity and owned-job membership before/after; Win32 path query
failed, native-format query and PSAPI both returned the identical full native
path, then Win32 query failed again. Memory was readable on that same limited
handle. Stronger-query conhost handles also showed error5. This is evidence for
an API-format fallback, not proof of Windows' internal failure mechanism or a
blanket privileges deficit. No administrator/security remedy is justified.

New pyfa_job_budget_r12.py preserves R8 and its evidence. It makes one native
path query on the same held limited handle after error5/31, validates full native
path and UTF16 length, rechecks creation/job/live state, and reads memory using
that same handle. Unknown identity still fails closed. Raw initial failure stays
recorded; recovered samples remain incomplete and aggregate counters stay null.
All caps, ownership rules and abort control flow are unchanged.

Independent source review cleared the correction. A test-fixture syntax error
was preserved and corrected in test_pyfa_telemetry_r12b.py. All 18 regressions
passed in 0.113s, including failed native lookup, malformed/truncated paths,
Unicode length, identity/job/lifetime errors and the retained live R11 replay.
Three real Git cases then passed under R12: outer guard0/noabort, 14.765s,
peak27,250,688 bytes and no remaining PIDs. Wrapper19 observations contained
zero live native recoveries; three error rows were exited processes absent from
the next job list. This is ordinary real-process smoke plus replay validation,
NOT a demonstrated live R12 fallback recovery or proof the R10b cause is fixed.
Independent outcome review confirmed these exact limits; no forced-recovery
churn or Android retry followed.

Final host audit passed in 13.578s. R9 guest inventory/locator remain unchanged;
no emulator/QEMU/ADB. Entire stage growth at audit was 2,179,248 bytes, below
the 3 MiB bound and previous spare preparation space. Remaining preparation
surplus was 10,693,218 bytes above the required 8 GiB reserve. Fresh admission
is mandatory before any future native stage. Failed and successful evidence
are preserved; no product code, commit, push, merge or release change.

Next exact stage: separately review and bind the tested R12 guard into a fresh
boot-only diagnostic with unchanged limits and fresh storage admission. Do not
run full UI or advance native product phases; System UI ANR diagnosis and product
acceptance remain blocked. No additional host retry is needed just to force a
native fallback sample. The original R8 guard and bound R10b attempt are frozen.
Evidence: task-2/c04-r12-telemetry-validation-20261014.json,
c04-r12-independent-review-20261014.json, c04-git-identity-r11-artifacts/raw.jsonl,
c04-r12b-host-tests-guard and c04-r12b-validation-guard.


Boot-only R10b diagnostic checkpoint (2026-10-14): the authorized targeted
ANR investigation reviewed retained boot evidence and prepared a boot-only run
with early filtered logcat, guest pressure/proc counters, process mapping and
positive visible-ANR windows. Existing memory/storage limits stayed unchanged;
captured output capped at 6 MiB, incremental growth at 128 MiB within the existing
8 GiB reservation. No further cleanup, copies of full artifacts or quota increase.

Independent review fixed deadline/accounting boundaries. The first host suite
passed 20/21; its mock cleanup accidentally suppressed the expected exception.
Original sources/results were preserved. R10b corrected only that mock and
attempt paths, passed independent review and all 21 host tests in 3.055s.
Fresh preparation passed in 24.5s with 25,755,098,881 allocated bytes.

The native guard then stopped BEFORE ANDROID during source verification:
exit 88, unreadable live process telemetry, 1.594s, peak job commit 35,237,888
bytes. PID24428 was a live job member; both full executable-path queries returned
Windows error 5 while its creation identity and memory counters were readable.
Parent path was verified Git; child git.exe name alone is not executable proof.
Cause is unexplained, not proven exit race, cap pressure or sibling interference.
Guard failed closed, no cap notifications and no remaining owned processes.
No observation marker, emulator/ADB actions, app test or new boot logs occurred.
Independent outcome review confirmed this interpretation. No native retry made.

Final host audit passed in 12.969s: R9 guest inventory/locator still match exactly
(56 entries); no emulator/QEMU/ADB; all bound failed evidence retained. Storage
admission still passes with only 12,872,466 bytes beyond the mandatory 8 GiB
preparation reserve at audit. Any future native launch needs fresh admission.

ANR cause remains unproven. R9 RT throttling at guest uptime 184.072 follows the
screenshots and cannot establish the original trigger. R8/R9 Binder request
1,056,768 exceeds largest free 1,040,384 bytes; target process unknown, not proof
of disk or global RAM exhaustion. R4 pressure metrics relate to a keyboard ANR.
No retained actual OOM kill, I/O error or corruption event identified; disk
latency unmeasured and persistent userdata remains a possible untested factor.

Product acceptance remains blocked: zero clean UI gates, seven later native
phases pending, no full delivery. Next bounded stage: host-only investigation
of executable-path telemetry denial before considering another boot-only run.
Do not weaken unknown-telemetry handling, change guest profile, dismiss ANR,
delete evidence, increase quota or repeat full UI without an agreed next stage.
No product code change, commit, push, merge or release in this diagnostic.
Evidence: task-2/c04-r10b-diagnostic-outcome-20261014.json,
c04-r10b-independent-review-20261014.json, c04-boot-r10b-run/result.json,
c04-boot-r10b-tests-guard/output.log and c04-r10b-audit-guard/result.json.


Approved cleanup and R9 diagnostic outcome (2026-10-14): user approval
received at 09:48 UTC for the exact duplicate generated test-assets directory.
Fresh validation matched all 44 files to retained APK contents and retained build
copies, verified paths/link counts/static pins, then removed only those files
and the now-empty approved directory. Recovered 167,489,868 allocated file bytes.
All current APKs, retained copies, source, unique evidence and guest were preserved.
No other cleanup or quota increase. Fresh storage admission passed afterward.

R9 source integration passed independent review, 37 host checks (0.391s), and
fresh guest/source/storage preparation (20.859s). One full fresh-UI method then
passed its original assertions in 77.006s. All seven capture hashes were retained.
The health collector stopped the harness with exit 1: this API36 window dump
omitted mCurrentFocus, so required focus evidence was incomplete. The same dump
positively shows a System UI ANR window with shown/onScreen/visible true.
Primary and independent review confirm the dialog obscures ALL FOUR screenshots.
Zero clean UI gates accepted; no phase-success receipt, final app archive, batch
success or accepted handoff was produced. Seven later native phases remain pending.

The native guard had no abort or cap notification: 218.047s, peak job commit
3,472,642,048 bytes (427,356,160 below unchanged cap), no remaining owned PIDs.
Independent process inspection found no emulator/QEMU/ADB. Failure guest inventory
is retained with 56 entries; it is not a successful native handoff. Future work
must preserve/rearchive this new state, not reuse the pre-R9 graph assumption.

Post-run host audit passed in 17.235s. Next preparation storage admission still
passes, with only 17,912,634 bytes beyond its mandatory 8 GiB reserve at audit.
Any future native launch needs fresh admission. No additional deletion authorized.
System UI cause remains unknown: activity lastanr reports none despite the visible
window, and bounded logcat tails lack the triggering reason/stack. Do not treat
negative lastanr or passing assertions as responsiveness or visual acceptance.

Next bounded diagnostic: recognize positive visible-ANR window blocks without
relaxing unknown-schema handling, and retain targeted boot-time ANR evidence
before repeating UI. No renderer/RAM/CPU change or dialog dismissal is justified
by the current evidence. No further native retry, commit, push, merge or release.
Evidence: task-2/c04-approved-asset-cleanup-20261014.json,
c04-r9-diagnostic-outcome-20261014.json, c04-r9-independent-review-20261014.json,
c04-r9-failed-guest-inventory-20261014.json and c04-fresh-ui-r9-artifacts.


ANR diagnosis / cleanup proposal (2026-10-14): READ-ONLY evidence review
found a System UI ANR window already in R4 with Vulkan enabled, before that
attempt reached reset/reinstall/UI. R4 also records a separate keyboard startup
ANR and high guest pressure. This rules out a uniquely Vulkan-off explanation;
the System UI root cause remains unproven. R8 passed app assertions but all four
screenshots show a System UI dialog; zero clean UI gates remain accepted.

Small proposed correction: retain last-ANR/window/logcat evidence after BOTH
instrumentation outcomes, after raw screenshots and before shutdown. New unbound
c04_ui_health_evidence.py passed independent review and 11 host-only fake-device
tests (0.312s; guard 1.078s; peak 15,314,944 bytes; no remaining PIDs). No native
integration or cure is claimed; frozen R8 sources/APKs remain untouched.

Exact cleanup proposal, NOT executed: delete only the generated duplicate
task-2/c04-history-test-build/app-build/intermediates/assets/debugAndroidTest/mergeDebugAndroidTestAssets
directory. Its 44 files occupy 167,489,868 bytes, each matching both retained current
test APK contents and a retained earlier build copy; no external hardlinks or
static-pin references. This covers the last audited 83,304,031-byte preparation
deficit with 84,185,837 bytes projected spare before new evidence growth. Explicit
cleanup approval and fresh storage admission are still required. No deletion,
quota increase, native run, production change, commit, push, merge or release.

Evidence: task-2/c04-anr-diagnosis-and-cleanup-proposal-20261014.json,
c04-reclaim-asset-proof-20261014.json and c04-ui-health-host-tests-guard/output.log.


R8 one-shot retry outcome (2026-10-14): complete fresh-UI instrumentation
passed (one method, 67.315s), and all seven receipt/capture hashes, database
size/hash, final state archive, resource guards and owned cleanup passed.
Native guard exited 0 in 296.578s, with peak job commit 3,496,210,432 bytes,
403,787,776 below the unchanged job cap; no cap notifications or remaining
owned PIDs. Seal guard passed in 8.390s; independent process inspection found
no emulator/QEMU/ADB. This run is complete and the heavy slot is released.

VISUAL ACCEPTANCE BLOCKED: primary and independent review found the same
System UI isn't responding dialog covering all four fresh screenshots.
Retain the native assertion/resource evidence, but count zero clean UI gates;
this is not full Batch A or C04 acceptance. No further native batch or retry
started. Cause of the System UI failure is not established by retained logs.

Telemetry correction: one immediate same-held-handle full-path requery for
errors 5/31, requiring successful full path, unchanged positive creation,
confirmed job membership and nonsignaled lifetime. Persistent unknown identity
retains the original fail-closed rule; errors and incomplete/null aggregates
are preserved. No increased rights, ownership substitution, sleeps or caps.
Independent review cleared final guard 03c1cc542fa005dd76bc5c06f2327c0ed8ced9c52f723aeeac105dad9c9a224c.
Thirteen host regressions passed; eight real probes observed only terminal
error 31, not historical R7 live error 5. Twenty-four cohort checks passed.
R8 telemetry had one 5-to-5 requery, zero successful recoveries; that ADB PID
departed before final membership, so the original departure rule applied.
Do not claim the requery cured R7 or infer the historical access-denial cause.

Final allocated artifact storage: 25,853,107,807 bytes; remaining quota:
8,506,630,561 bytes. The current run stayed within its runtime storage policy,
but a NEW preparation requiring 8,589,934,592 bytes is short by 83,304,031 bytes.
No deletion or quota change occurred. Fresh future admission must fail closed
unless legitimate authorized space recovery first restores that reserve.

Next bounded work proposal: diagnose System UI health from preserved evidence
and prepare an explicit storage recovery plan; any new native execution needs
coordinator approval and fresh admission. Seven later native phases remain
pending. No source assertions, production code, APKs or phone data changed.
Evidence: task-2/c04-r8-diagnostic-outcome-20261014.json,
c04-r8-screenshot-review-20261014.json, c04-r8-telemetry-investigation.json,
c04-fresh-ui-r8-run/result.json and c04-fresh-ui-r8-handoff.json.


R7 approved one-method diagnostic outcome (2026-10-14): fresh storage and
host admission passed. Artifact headroom was 8,683,419,784 bytes against the
8,589,934,592-byte preparation growth allowance; the 93,485,192-byte surplus
was not the runtime growth ceiling. No quota increase or cleanup occurred.

Vulkan-off was verified and boot completed in 76.672s. At 131.297s the guard
stopped with exit 88, unreadable live process telemetry: owned adb.exe PID
14840 had QueryFullProcessImageNameW error 5 (access denied) while still live
in the job. Identity verification failed despite readable memory counters.
Independent review confirmed the fail-closed outcome; cause is unproven.
Do not ignore the error or substitute a process name for full identity.

Kernel job peak was 3,301,117,952 bytes; cap notifications were empty.
Minimum host RAM/available commit were 9,411,018,752 / 24,532,111,360 bytes;
maximum baseline drops were 3,139,629,056 / 3,635,728,384 bytes. No owned PIDs
remained; separate process inspection found no emulator/QEMU/ADB.

Partial prior-state archival is preserved. Complete archive receipt, reset,
reinstall, fresh-UI method, provisional UI captures and native acceptance
did not occur. No retry or further batch started. Vulkan memory savings
remain inconclusive. A later attempt requires fresh guest/source admission.
Post-run artifact allocation: 25,681,673,377 bytes;
remaining quota: 8,678,064,991 bytes;
surplus over the next 8 GiB preparation allowance: 88,130,399 bytes.

Next bounded proposal: investigate the live-process identity-query failure
using retained telemetry and a reviewed host-only reproduction, preserving
full identity verification and all resource limits; native retry requires
coordinator approval. Evidence: task-2/c04-r7-diagnostic-outcome-20261014.json,
c04-fresh-ui-r7-run/result.json and c04-r7-outcome-audit-guard/result.json.


R7 host-only diagnostic readiness (2026-10-14): independent final-source review
cleared; all 22 focused host tests passed (0.343s; guarded job 1.625s, peak
24,797,184 bytes). Full guest/source preparation passed in 36.797s, peak
35,467,264 bytes, 51 guest inventory entries and 637 bound dependencies.
Both guards exited 0 with no abort or remaining owned PIDs. No R7 native
execution occurred; emulator/QEMU/ADB inspection was empty.

R6 sampled QEMU private memory reached 3,826,733,056 bytes, about 98.8% of
owned private memory at that complete sample. This identifies the dominant
process, not a proven renderer leak. Proposed single-variable diagnostic:
append -feature -Vulkan, retain 2048 MiB guest RAM and all existing APKs,
assertions and budgets, run the complete fresh-UI method alone, and capture
strict receipts before the mandatory final storage scan. Runtime Vulkan-off
proof is required. Any success is labelled diagnostic, not full Batch A or
C04 acceptance; seven further native phases remain pending.

Native launch remains held for coordinator release while sibling workloads
have resumed. Preparation storage was 25,675,721,493 bytes, only 94,082,283
bytes below the 32 GiB cap minus the mandatory 8 GiB preparation reserve.
Fresh launch admission must recheck this narrow margin; no cleanup or cap
change is authorized. Runtime config SHA256:
1e68f2dd8ce0a00e5100d602bc8be942d097dbd823c78c38278131f89a27b427.
Evidence/plan: task-2/C04-memory-diagnostic-plan-20261014.md,
c04-r7-diagnostic-readiness-20261014.json, c04-continuation-r7-tests-guard,
and c04-remaining-a-r7-prepare-guard. Prior attempt evidence remains intact.


R6 quiet-slot outcome (2026-10-14 03:14 UTC): fresh admission and runtime preflight passed;
prior guest state was archived, APKs reinstalled and cold-state checks passed.
DroneUiTest instrumentation log reports OK(1 test),76.069s, including the reviewed
history waits and original assertions. The batch was interrupted before phase
receipt/screenshot collection; this is not a completed accepted native gate.
Core/linked did not start; B/C remain unstarted.

Guard exit88 at229.156s: kernel job memory-limit notification, reported peak
3,907,584,000 bytes versus configured3,899,998,208-byte job cap. Preserve this
reported7,585,792-byte excess; no threshold adjustment was made. Maximum whole-
host commit-headroom drop3,687,534,592 bytes remained below4,000,000,000; minimum
RAM10,078,990,336/commit24,971,784,192 bytes. This is distinct from R5's host-wide
baseline-drop stop. No owned PIDs remained, and separate process inspection found
no emulator/QEMU/ADB. The quiet slot is released; no further native attempt is
running or scheduled. The guest now contains the new test APK and completed UI
activity; any future attempt must preserve/reinspect that new state, not reuse
R4/R5 old-package assumptions. Evidence: task-2/c04-remaining-a-r6-run,
c04-remaining-a-r6-artifacts/fresh-ui.log and c04-batch-a-r6-outcome-20261014.json.

Guard semantics clarification: host() reads GetPerformanceInfo and computes
available commit as CommitLimit minus CommitTotal. The baseline-drop condition
is baseline available commit minus current available commit >4,000,000,000 bytes
(or the same drop in available RAM); it is separate from the absolute4GiB
available RAM/commit reserve. The baseline is the FIRST admission reading and
is not reset after the10-second admission interval, preparation, or emulator boot.
For R5, all209 samples and baseline had the same59,668,307,968-byte commit limit.
System commit rose30,585,098,240 ->34,588,696,576 bytes, exactly matching the
4,003,598,336-byte available-commit drop. Available commit remained
25,079,611,392 bytes, so the4GiB reserve was not the stopping condition. This is
whole-host accounting, not attribution to Pyfa or siblings. If the system commit
limit changes, available-commit drop also reflects that limit change and is not
identical to commit-total growth. No guard/config/threshold bytes were changed.
Coordinator has asked Beacon/Jita to finish current bounded tests and hold new
heavy launches; R6 native launch remains held until explicit quiet confirmation.

C04 ready checkpoint (2026-10-14 03:02 UTC): R6 interruption provenance passed independent
review, binding generation and44 focused host tests (5.723s; guard7.5s,
peak29,429,760 bytes). Fresh preparation passed41.344s, peak33,230,848 bytes,
49 guest entries/520 bound dependencies. Storage25,535,019,869 bytes satisfies
the32GiB cap with8GiB preparation reserve. No owned processes remain.

Native launch is held for a coordinator-confirmed meaningfully quieter slot after
the R5 host-commit baseline stop. R6 retains unchanged APKs, renderer, memory,
deadlines and strict proof checks. R5 remains an interrupted offline admission;
R4 remains the last preserved installed-pair/app-graph baseline. No C04 native
execution with the rebuilt test APK has completed; B/C remain unstarted.
Prepared runtime SHA256 0ff0c6f8bda1597b671375d3bae7b18895029e4bc5a4071607f917a698e65119.
Evidence: task-2/c04-continuation-r6-tests-guard,
c04-remaining-a-r6-prepare-guard and C04-current-handoff-20261014.md.

C04 continuation checkpoint (2026-10-14 02:51 UTC): R5 archival-only repair
passed independent review and38 focused host tests; fresh preparation passed
29.968s with46 guest entries and25,526,875,772 allocated bytes. Historical empty
or malformed artifacts now retain exact bytes/hash plus diagnostic-only status;
fresh proof requirements and all resource limits remain unchanged.

R5 native Batch A was stopped by the guard at124.188s during offline admission,
BEFORE archive/reset/reinstall/native tests. Available host commit fell by
4,003,598,336 bytes from baseline, exceeding the unchanged4,000,000,000 threshold.
Peak owned job commit3,660,419,072 bytes; no kernel-cap notification. Minimum host
RAM10,352,689,152/commit25,079,611,392 bytes; no owned processes remained. The
whole-host delta does not establish attribution to another project. B/C remain
unstarted and the rebuilt test APK has not yet run natively. Evidence is retained
in task-2/c04-remaining-a-r5-run, c04-remaining-a-r5-artifacts and
c04-batch-a-r5-outcome-20261014.json. No automatic retry or cap/profile change;
read-only stop review and resource coordination precede the next bounded attempt.

C04 continuation checkpoint (2026-10-14 02:38 UTC): the rebuilt test APK remains
verified (SHA256 7cb37646055f2b8032fed39cf33758ad780da39eaa161e8c9c2d3a4ebbb8487b).
The reviewed storage scanner passed 10 focused tests and a clean bounded repeat:
37.407s original versus 15.235s optimized, matching file/directory counts and
allocation within measured monitor-log growth. The initial benchmark's terminal
process-telemetry error remains retained and is not claimed as a clean pass.
R4 passed 31 harness tests and fresh preparation (42.344s, 44 guest entries).
Native runtime preparation then completed within its unchanged 60s deadline.

R4 Batch A booted and passed identity/offline/old-APK checks, but stopped BEFORE
APK reinstall, reset, or native instrumentation while preserving prior evidence:
the historical startup receipt existed with zero raw bytes; archival code wrongly
required it to parse as JSON. Existing graph/tar and all failure evidence remain.
Guard exit1, no guard abort, 108.437s, peak3,590,651,904 bytes; minimum host RAM
11,173,679,104/commit25,852,424,192 bytes; no owned processes remained. B/C did not
start. A separate reviewed R5 fix will preserve opaque prior bytes (including
empty/malformed data) with explicit diagnostic status, retaining strict fresh
proof checks. No cap, renderer, APK, assertion or deadline change is planned.
Evidence: task-2/c04-fast-storage-check-r2, c04-fast-storage-r2-guard,
c04-continuation-r4-tests-guard, c04-remaining-a-r4-prepare-guard,
c04-remaining-a-r4-run, c04-remaining-a-r4-artifacts and
c04-batch-a-r4-outcome-20261014.json. C04 remains incomplete; no publication.

C04 continuation progress (2026-10-14 02:15 UTC): test APK rebuild passed,
new SHA256 7cb37646055f2b8032fed39cf33758ad780da39eaa161e8c9c2d3a4ebbb8487b;
unchanged app APK 9cf74b04a2ff8bfc6ce191e2b632246cf1da7780331749aaf0fb566ead54d25d.
Build/signature/source checks completed in523.89s, peak1,695,887,360 bytes;
minimum RAM12,870,443,008/commit27,540,828,160, no owned processes remained.
R3 independent review and31 focused host checks passed. Review fixed stale shared
screenshots: archive before clearing exact five owned paths, then verify absence.
Host preparation passed62.14s with44 guest entries and25,515,128,197 allocated
bytes inside32GiB cap plus8GiB preparation reserve. R3 native controller then
stopped BEFORE emulator/ADB launch at60.547s on the unchanged preparation
deadline; peak33,611,776 bytes and no remaining owned PIDs. No native tests ran.

Retained timing profile passed47.641s: static/source proofs2.594s, guest full
hash inventory5.125s, allocated-storage scan39.344s. Work continues on a narrow
scanner optimization removing redundant metadata calls, with identical allocated
byte/hardlink/reparse/error semantics and independent review/guarded equivalence
checks. No inventory/storage check, deadline, cap or assertion is being removed.
Evidence: task-2/c04-history-test-build, c04-history-test-build-guard,
c04-continuation-r3-tests-guard, c04-remaining-a-r3-prepare-guard,
c04-remaining-a-r3-run and c04-r3-preparation-profile. All old evidence, APKs and
guest disks remain preserved; source/APK candidate unchanged during diagnosis.

C04 resumed execution (2026-10-14 01:56 UTC): explicitly authorized to rebuild the
changed test APK, refresh exact bindings and run guarded A/B/C sequentially while
other projects use their own bounded workloads. This supersedes the prior global
heavy-slot wait. One offline rebuild is active in task-2/c04-history-test-build,
using a new build directory and preserved historical APKs. Native work waits for
that build, source/package verification and independent r3 continuation review.
All owned heavy processes remain capped at 3,899,998,208 bytes plus 100,000,000
monitor reserve; 8GiB RAM admission and 4GiB running RAM/commit reserves remain.
No source changes during build, cap increases, software installation, physical
phone work, publication, commit, push, merge or release are authorized here.

C04 UI history diagnosis/fix (2026-10-14 01:08 UTC): host-only stage complete;
Beacon owns the heavy slot. DroneUiTest now waits for same-fit settled history,
exactly one library revision advance and refreshed drone details for all six
undo/redo actions. Original identity/content assertions are unchanged. The prior
ready predicate could accept an unchanged one-stack view before undo completed.
No production code changed. Independent actual-diff review found no blocker.

The exact seven-operation headless add/stack/undo/variation/undo/redo/undo sequence
passed six assertion groups against unchanged bridge/EOS sources: the full record
and original logical ID are restored by undo. Guarded duration 6.969s, peak job
commit 79,429,632 bytes under 268,435,456, monitor peak 13,549,568 under 100,000,000;
2GiB host RAM/commit reserves, no owned processes left. The retained first attempt
failed only in diagnostic Windows platform-cache initialization before the engine
sequence; corrected r2 passed. This verifies bridge identity, not native timing.

Evidence: task-2/c04-ui-history-fix-outcome-20261014.json,
c04-ui-history-host-r2/result.json and c04-ui-history-host-r2-guard/result.json.
The host receipt pins the prepatch test; its only changed recorded source is
DroneUiTest.kt (new SHA256 5523e8d0915a6469fdfedab21ebf387415d822febeb05d0e16d598cf6babe516).
The helper is uncompiled and unexecuted on Android. git diff --check passed.

Native limits remain unchanged: 4,000,000,000 total less 100,000,000 monitor,
rounded down to 4KiB gives job cap 3,899,998,208 (1,792 bytes rounding slack).
Independent review establishes the UI failure before guard termination only;
notification occurrence times are unavailable, so memory-denial/assertion
causality remains unresolved. Preserve the reported peak's 868,352-byte excess.

Next bounded stage, after heavy-slot coordination: build/verify a new test APK,
record exact final source/APK pair bindings, review the preserved warm partial
guest boundary, refresh continuation/dependency manifests, then validate native UI.
Existing source_proof correctly rejects the changed test; do not weaken it or
bind old test APK evidence to this helper. Original three contract passes retain
their original source/APK bindings; no C04/full gate is newly passed. App/engine
sources are unchanged, but any future product change needs fresh applicable
build/package/native proof. No build, emulator/ADB, phone, commit, publication,
merge, release or cap increase occurred in this stage.

C04 Batch A outcome (2026-10-14 00:52 UTC): failed; heavy slot released.
The missing lock-PID fix passed 24 host-only checks (0.546s; guarded peak
27,308,032 bytes). An absent entire lock directory now requires an independent
idle emulator/QEMU process snapshot; live PID, incomplete/malformed/redirected
locks and unreadable process ownership still block. No lock was deleted.
Fresh preserved-guest preparation passed in53.953s, peak52,920,320 bytes, with
40 inventory entries and45 runtime pins. Both host stages used a256MiB owned
cap plus100M monitor reserve and2GiB available-RAM/commit reserves; native limits
remain4GB total,8GiB admission,4GiB running reserves and unchanged timeouts.

Authorized Batch A launched on unchanged candidate2e518a2e and exact installed
APKs. Boot50.344s, effective offline proof, APK hashes and cold-app admission
passed. The fresh-ui method executed1/failed1 (JUnit36.985s): atDroneUiTest.kt:90,
undo after ordinary variation expected original objectKey
fa0df1d46110431b98e6dcd767133eff but observed157c36d380024f3a9ddd7d3eb8cd3de6.
Core/linked executed0; B/C did not start. Original3 contract passes are preserved,
not repeated or counted as three full gates. No UI/full-delivery pass is claimed.

The guard independently exited88 on kernel job memory-limit notifications for
QEMU/crashpad. Reported peak3,900,866,560 bytes vs configured3,899,998,208 cap plus
100,000,000 monitor reserve;182.344s total/141.0s observation. Eight incomplete
samples leave aggregate sampled peaks unavailable. Minimum freeRAM11,691,761,664
and commit27,209,289,728 bytes; host-drop stops did not trigger. Whether memory
pressure contributed to the UI assertion is unresolved. Job termination left no
owned PIDs; a separate process snapshot confirmed no Pyfa/Android processes.
Graceful sync/stop receipts were not reached. Guest disks and all raw evidence
remain preserved, including partial UI state; no physical-phone action occurred.

Evidence: task-2/c04-batch-a-outcome-20261014.json,
c04-remaining-a-r2-run/result.json, c04-remaining-a-r2-artifacts/fresh-ui.log,
c04-continuation-final-tests-guard-4 and c04-remaining-a-prepare-guard-4.
Next bounded work: host-only diagnosis of variation undo identity and owned QEMU
memory pressure, then plan a separately coordinated retry. The guest is now warm;
do not repeat cold admission/install wrappers or advance B/C blindly. No push,
merge, release, budget increase or removal of an acceptance check occurred.


C04 remaining-sequence preparation (2026-10-13 17:07 UTC): command/state/evidence manifest ready;
Jita owns heavy slot. No emulator, ADB, package change, engine regeneration or native
execution. Evidence: task-2/c04-remaining-sequence.json (22 pinned source/evidence/
seed files), c04-sequence-prepare-v2-guard. Preparation exit0 in12.141s, peak job
commit55,234,560 bytes under256MB, no remaining owned PIDs. An initial receipt-writer
syntax error failed before work; its log is retained in c04-sequence-prepare-guard.

Gate mapping: the3 passing DroneContractTest methods are contract-phase evidence
inside ONE native:c04-delivery gate, not3 independently completed full gates. Reuse
the exact retained contract.log/result, APK and source hashes; no repeat is required
for subsequent seed boundaries. Native delivery still needs8 executions (11 total),
all receipts,5 screenshots and aggregate validator success. acceptance:c04-split-merge
also needs exact-candidate reference/host/native proof; neither gate is marked passed.

Prepared sequence, one owned AVD and no concurrent native phases:

| Batch | Existing phases | Executions | Required state boundary |
| --- | --- | ---: | --- |
| A | fresh-ui -> core -> linked | 3 | Current installed pair; no reinstall/reset/seed. Capture first-start receipt,4 screenshots, UI receipt,18 core cases,14 linked cases and6 variations. |
| B | conservation -> conservation-restored | 2 | Preserve A state/evidence, reinstall only owned synthetic debug packages, install verified14-fit conservation seed; no reset between paired process-restart phases. |
| C | prepare -> restored -> mutation-ui | 3 | Preserve B state/evidence, reinstall owned pair with verified4-fit details seed; no reset through8-fit reopen and mutation UI; capture fifth screenshot. |

Both existing seeds verified read-only: exact graph/fixture hashes, SQLite payload
checksum and4/14 expected fit records. No seed regeneration or contract repetition.
Force-stop before each native invocation; repeated method names are the distinct
required before/restart phases. Archive receipts/graphs before any reinstall. A failure
stops the batch and preserves state; no blind continuation, reset or automatic retry.
Combine provenance-linked contract evidence with new logs in canonical phase order,
then use existing validate_native; inspect all PNGs at full size before UI acceptance.

Budget unchanged:4GB total (kernel3,899,998,208 + monitor100M),2 cores/2048MiB guest,
10s host admission >=8GiB RAM,4GiB RAM/commit reserves,4GB per-domain host-drop stops,
10GiB host disk minimum. Proposed batch cap remains1200s post-launch, with60s prep,
300s boot,120s offline,900s per instrumentation; a phase cannot extend its enclosing
batch cap. Three batches mean at most60 minutes post-launch total plus admission/
prep/cleanup, not an ETA. Remaining EOS/UI peak memory/runtime is unmeasured.
Artifact allocation25,002,790,309 bytes leaves9,356,948,059 within32GiB; after the
required8GiB reserve, slack767,013,467 bytes. Recheck each batch; no second AVD/clone.

Fresh-app distinction: absence-before-install and exact offline APK installation
are proved on the resumed OS. First UI/engine startup and cold data extraction are
not. Before A, check files/game/eve-<hash>.db, files/a10-startup.json, saved graph and
C04 witnesses absent; unexpected warm state is preserved/reported, never deleted to
manufacture proof. Then require startup database_installed=true and exact99,897,344-byte
bundled database hash, UI/recreation receipts and visual review. Fresh-AVD/full-run
policy remains separately unfulfilled; do not mislabel this guest as a clean OS.

Execution manifest is not a launched or turnkey batch: the cohort continuation
entrypoints and fresh runtime guest/dependency pins still need assembly/validation
before launch. The old contract-only entrypoint must not run against installed
packages. Next task is that bounded continuation wiring, then parent slot release
and runtime admission. All190 full gates, upgrade/other ABI/user sign-off remain.

C04 contract native outcome (2026-10-13 16:53 UTC): PASS; heavy slot released after owned cleanup.
Fresh36-entry guest review and20 dependency pins bound the accepted effective-offline
helper; launch config SHA256
ac74c0361e6640cad90da5952a129cae81c5128b95e539cc299bd7a36fae1375.
Boot passed at60.422s inside300s. Owned AVD/qemu/API36/x86_64 identities passed.
Phone service was ready on first poll. Effective-offline proof passed first poll in
2.453s: airplane mode on, Wi-Fi disabled, no active default or current networks.
Mandatory disable commands succeeded; telephony preferences remained diagnostic.

Both packages were absent before installation; both exact verified APKs installed
successfully (5.047s/1.344s). Existing DroneContractTest executed3 tests and all3
passed, confirmed by the strict named-event/count/terminal parser. The contract
runner took22.047s. Candidate product/test sources remain2e518a2e with the existing
verified APK hashes. This is actual native evidence, separate from host mocks.

Guard exit0,139.532s total /122.219s emulator observation, no abort reason. Kernel
peak job commit3,562,004,480 bytes within3,899,998,208 plus100,000,000 monitor reserve.
Readable observed WS/private peaks3,252,211,712/3,565,510,656 remain partial:9 incomplete
samples leave aggregate sampled peaks null. Maximum host physical/commit-headroom
drops3,437,232,128/3,628,498,944 stayed below4GB. Minimum free RAM9,006,616,576 bytes
and commit headroom25,264,955,392 bytes. No cap notification recorded (not a guarantee
of no denied allocation). Guest sync, owned-emulator stop and private ADB stop all
returned0; remaining job PIDs[]. All state/logs preserved; no physical-phone action.

Evidence: task-2/effective-contract-outcome.json, c04-effective-contract-run/result.json,
c04-effective-contract-artifacts/boot-complete.json, offline-proof.json, commands.json,
contract.log and contract-result.json. The preserved guest now contains both installed
packages; its preparation manifest is stale. Do not rerun the absence/install wrapper.
Next bounded accepted phase: fresh-ui, planned from this installed state and scheduled
through the parent heavy-slot owner. No next phase launched. No UI/screenshot/restart/
upgrade/full-delivery claim; remaining C04 work and all190 full gates stay required.

Offline assertion semantics correction (2026-10-13 16:46 UTC): no emulator/ADB/phone work;
Beacon owns the heavy slot. DEVELOPMENT.md:106 requires networking unavailable.
Existing native checks require airplane mode and INTERNET permission denied, not
DataSettingsManager preference flags false. Android16's current isUserDataEnabled
and isDataEnabled(apn) fields concern preferences/policy/provisioning; radio power,
registration and connectivity are separate. Snapshot58's true fields are current,
not historical, but coexist with radio off, unattached network requests, airplane1,
Wi-Fi disabled, no default network and empty Current Networks. The added false-bit
requirement was therefore an unnecessary platform-specific acceptance condition.

Corrected only the C04 harness: retain mandatory phone readiness/disable commands
and current airplane/Wi-Fi/no-default/no-current-network proof. Capture telephony
once as diagnostics; its preference bits or dump availability do not establish
connectivity. Reject unknown/partial/duplicate/timed-out connectivity output.
The receipt no longer claims mobile_data_disabled. Why the preference stayed true
is unproved; command exit0 ignores a boolean result and early subscription mapping
was changing, so a readiness race is plausible, not established. Prior failure
outcome remains preserved: no APK or native test ran, and snapshot reclassification
is not a native pass. No app or native-test source changed.

Independent review passed helper SHA256
2594fe266f52058e82e0dfaec1f2648923e36761ae4ee0b7a02adcfe9b9183bc.
24 mocked host tests passed in0.196s;2 retained-output replay checks passed in0.011s.
Both256MB guards exited0 with no remaining owned processes. Earlier27-test evidence
belongs to the prior assertion version and is preserved, not counted as new proof.
Evidence: task-2/offline-effective-diagnosis.json, offline-effective-tests-guard,
offline-captured-replay-guard and offline-memory-attribution.json.

At the near-threshold complete sample, host commit loss was3,984,920,576 bytes vs
owned private3,623,862,272 (QEMU3,579,207,680). The361,058,304-byte difference before
monitor accounting remains unattributed, not proof of another process/Beacon cause.
Global/private/shared/kernel counters and release timing are not a causal breakdown.
Keep all caps/stops unchanged. Next: after parent slot release, refresh stale guest
and dependency pins into new paths and run only the existing bounded contract stage.
No launch now; all190 full gates remain required.

Offline-fixed boot-to-contract outcome (2026-10-13 16:37 UTC): stopped at prerequisite failure;
heavy slot released. Boot passed at37.594s; owned AVD/qemu/API36/x86_64 identities
passed. Phone service was found on the first poll; the prior missing-service
failure did not recur. Both Pyfa packages were absent before setup.

Airplane, Wi-Fi and mobile-data disable commands all returned0. Current airplane
mode was1, Wi-Fi disabled, active default network none and current networks empty.
Nevertheless, after59 state polls within the120s prerequisite, phone0 still had
mIsDataEnabled=true, isDataEnabled(internet)=true and isUserDataEnabled=true.
The stricter gate refused offline proof. Initial TelephonyDebugService dumps timed
out; later complete dumps confirmed the enabled data settings. The ineffective
disable's cause is unresolved. Installation attempts0; all3 native contract tests
blocked before installation, executed0/passed0. Prior27 mocked checks remain
host-only evidence and were not rerun. No phone action or automatic retry.

Guard exit1 from prerequisite exception, no guard stop reason. Kernel peak job
commit3,632,209,920 bytes below3,899,998,208 plus100,000,000 monitor reserve. Readable
observed WS/private peaks3,327,799,296/3,642,945,536 are partial:14 incomplete samples
leave aggregate sampled peaks null. Maximum physical/commit-headroom drops were
3,598,000,128/3,984,920,576 bytes; the latter was15,079,424 bytes below its4GB stop.
Minimum free RAM9,372,282,880 and commit headroom25,501,380,608 bytes. Cap notifications
empty (not proof of no denied allocation). Owned emulator stopped; private ADB
shutdown returned0; remaining job PIDs[]. Guest and all logs retained.

Evidence: task-2/offline-contract-outcome.json; c04-offline-contract-run/result.json;
c04-offline-contract-artifacts/offline-state-58-telephony.log and failure service,
phone and logcat captures. Next bounded stage: diagnose ineffective data disable
from retained evidence before another reviewed/authorized run. Do not bypass the
offline gate. Refreshed guest manifest is now stale. All190 full gates remain.

Offline-fixed boot-to-contract preparation (2026-10-13 16:31 UTC): prepared, launch held for
parent confirmation of Beacon PostgreSQL cleanup/heavy-slot release. No emulator,
ADB, phone action, APK installation or native test ran. Preserved the same guest
and prior evidence; refreshed32 guest entries and20 dependency pins into new paths.
Both APK hashes and184 embedded engine sources still match the candidate2e518a2e.

New launch config: task-2/offline-contract-config.json, SHA256
8c9ad0481a3ef14b91ab018e20c2d0e8506eeef250b395d72f633251cf018e32.
Guest review: offline-contract-guest-review.json, SHA256
60d1210dded6f49cd0bf454bf3d74b49ab5581c0524fb16fa592806a41b15bf9.
Readiness: offline-contract-readiness.json; fresh output c04-offline-contract-run
is absent. Preparation guard exit0,18.609s, peak job commit54,251,520 bytes under
256MB total; remaining owned PIDs[]. Evidence: offline-contract-prepare-guard.

Launch keeps4,000,000,000-byte total budget (3,899,998,208 kernel commit cap plus
100,000,000 monitor reserve), per-domain4GB host-drop stops,4GiB RAM/commit reserves,
10s admission with>=8GiB free RAM,300s boot,120s offline prerequisite,900s contract,
1200s post-launch guard and60s preparation limits. Current artifact allocation
24,710,526,952 bytes plus8GiB reserve fits32GiB. Runtime rechecks every admission.
Next: only after parent release, execute the prepared guard/entry for the same
three-test contract phase.27 prior mocked checks are not guest/native results.

Offline prerequisite diagnosis/fix (2026-10-13 16:20 UTC): Beacon owns the heavy slot. No
emulator, ADB/device command, APK install or native test was started in this stage.
The retained failure is still svc data disable exit20, "Can't find service: phone".
The AVD config enables its GSM modem; guest logs show radio HAL/process startup.
They do not establish why the framework phone Binder was missing. Expected
telephony absence is not proved; readiness delay/crash remains unresolved.

Demonstrated harness omission: native_suite.py already waits up to120s for phone
Binder readiness, but both C04 entry paths skipped that gate. Android16 svc maps
data disable to cmd phone data disable, whose successful shell return does not
alone establish disabled data. An airplane setting alone is insufficient proof.

The shared check-drones.py helper now uses one120s deadline for phone readiness,
mandatory airplane/Wi-Fi/mobile-data disable and current-state settling. It requires
telephony-data capability, airplane=1, disabled Wi-Fi and data for every dumped
phone, no default network and no current networks. TelephonyDebugService supplies
live data settings; dumpsys phone does not. Unknown, incomplete, timed-out and
historical-only output fails closed. Failure diagnostics have a separate20s cap.
Both C04 call sites block installation/instrumentation until offline-proof.json.

Focused host-only verification:27 tests passed in1.231s. Guard exit0, duration4.188s,
kernel peak job commit22,716,416 bytes within256MB total; remaining job PIDs[].
Tests use synthetic/mocked outputs, not native evidence. Independent review found
and corrected incomplete-dump acceptance and multi-phone tail indentation.
Evidence: task-2/offline-prerequisite-tests-v2-guard/{output.log,result.json},
offline-prerequisite-diagnosis.json; helper SHA256
2f2c26dd970cf9c81e0ec4f4dd527a51d5345e2eb7019bfb1784bf10d521156b.

Next bounded stage is held for parent heavy-slot release: refresh the preserved
single guest manifest and dependency pins into new evidence paths, then run the
existing boot-to-contract stage with this prerequisite. Existing run configs and
guest pins are stale and must not be reused. Capture the missing-service diagnosis
on any failure; do not bypass the gate. No commit/push/merge/release or phone action.
All190 full gates and screenshot review remain required.

Boot-to-contract outcome (2026-10-13, 15:57 UTC): stage stopped at its outcome and
heavy slot released. Android sys.boot_completed=1 confirmed at119.406s, inside the
existing300s limit. Owned AVD/qemu/API36/x86_64 identities passed; both Pyfa packages
were absent. Offline setup then failed: svc data disable returned20 with
"cmd: Can't find service: phone". Airplane and Wi-Fi commands returned0, but final
offline proof was not reached. Installation attempts0; native test bodies0. This is
an emulator prerequisite failure, not an APK/install/test-body result. No retry.

Guard exit1 reflects the launcher exception, with no guard memory/host-stop reason.
Peak job commit3,511,025,664 bytes under3,899,998,208 plus100,000,000 monitor reserve.
Readable observed WS/private peaks3,221,065,728/3,500,380,160 bytes are partial;
six incomplete samples leave aggregate sampled peaks null. Maximum host physical
and commit-headroom drops3,289,919,488/3,459,088,384 bytes stayed below4GB. Minimum
available RAM8.859GiB and commit headroom23.748GiB. No cap notification recorded.
Owned emulator cleanup completed; private ADB stop returned0; remaining job PIDs[].
All guest state/logs preserved; no physical-phone action, APK install or native check.

Evidence: task-2/resumed-contract-outcome.json, c04-resumed-contract-run/result.json,
c04-resumed-contract-artifacts/boot-complete.json, commands.json and offline-data.log.
Next bounded work: diagnose the missing emulator phone service/offline prerequisite
before another authorized run. Do not bypass offline verification or count this as
native proof. Resumed guest is not fresh-install/full-delivery proof. All190 full
gates remain required; no commit/push/merge/release or further stage launched.

Boot-to-contract readiness (2026-10-13, 15:54 UTC): prepared only; parent heavy-slot
release required after Jita recovery. No emulator/ADB/native work started. Existing
boot deadline is300s (local_verification.py), so no new180s fallback is needed.
After sys.boot_completed=1 and owned AVD/API36/x86_64 identity checks, require both
Pyfa packages absent, disable only this emulator's connectivity, install the exact
previously verified app/test pair, then run C04 contract/DroneContractTest once.
Its three existing methods verify details schema/units/identity/counts, queued
selection isolation, and eight operation encodings/invalid edits. Keep the existing
strict instrumentation parser and900s phase deadline, additionally bounded by the
1200s post-launch guard and60s preparation guard. Other ADB commands cap at120s.

Prepared18 fingerprints include current guest manifest, headless QEMU, private ADB,
runner/parser/phase inventory and both APKs. App SHA9cf74b04a2ff8bfc6ce191e2b632246cf1da7780331749aaf0fb566ead54d25d;
test SHA6473af41f5a569dd982307d23320c9fa25da089803f5ef74929811964f8e9235.
Candidate2e518a2e product/test source is unchanged; all184 packaged engine-source
fingerprints and four fixture assets matched. Prior signature/package evidence is
reused for identical binaries. Artifact allocation24,120,912,754 bytes plus8GiB
reserve fits32GiB; repeated runtime storage checks remain enabled.

Three mocked launcher-flow checks passed0.156s, covering success ordering, boot
timeout and refusal of an existing app; these are not native proof. First shell
attempt failed before Python and remains retained. Preparation passed24.438s,
remaining owned processes empty. No unrelated passed checks were rerun.
Resumed OS guest is not fresh-install/full-delivery evidence; no uninstall/clear,
seed replacement, phone work or automatic retry is authorized by this stage.

Inputs: task-2/resumed-contract-config.json SHA256
9b2df4b90a04481ba371eaaa5d7614660f2da2fe8ee016c4a8e1474c145a5b12.
Evidence: resumed-contract-readiness.json, resumed-contract-prepare-guard,
resumed-contract-flow-tests-v2.log. Next after parent release: run prepared config
into new c04-resumed-contract-run, retain unchanged4GB owned/kernel policy, separate
4GB host-drop stops, both4GiB absolute reserves and fresh10s>=8GiB admission.
All190 full gates remain required. No commit/push/merge/release or phone changes.

4GB diagnostic-stop observation (2026-10-13, 15:41 UTC): heavy slot released; all
owned processes stopped. Authorized single observation ran30.454s and stopped at
its deadline (42.422s excluding10s admission), not a sampled memory/host stop.
Linux kernel boot and Android init reached; APEX decompression continued through
guest24.740s. Android boot completion is unproven; no APK/native checks or phone work.

User-authorized guard change keeps the kernel job cap3,899,998,208 bytes plus
100,000,000 monitor reserve. Baseline physical and commit-headroom drops are tracked
separately and stop above4,000,000,000 bytes, never summed. Absolute available RAM
and commit reserves are both4GiB. Four tiny boundary tests passed0.634s, including
real denied allocation under a39,997,440-byte job cap followed by owned cleanup.
Independent review passed code and all10 launch pins including actual headless
QEMU/current29-entry guest manifest. No cap increase or monitoring framework added.
Observed job memory-limit notifications now stop the job; Windows delivery is not
guaranteed, and no notification is not proof no allocation was denied.

Measured job peak commit2,687,217,664 bytes; readable observed WS/private peaks
1,466,060,800/2,699,747,328 bytes. Two incomplete samples leave aggregate sampled
peaks null. Normal churn reconciled; no unresolved members. Maximum host physical
and commit-headroom drops1,921,818,624/2,919,596,032 bytes; minimum available RAM
10.109GiB and commit headroom24.215GiB. No kernel-cap notification recorded. These
are distinct memory domains and do not establish a global hard physical ceiling.

Evidence: task-2/startup-budget4g-outcome.json, startup-budget4g-independent-review.json,
host-budget4g-tests.log and c04-startup-budget4g-observation. Guard SHA256:
7ebd52deb3183fc879d06d2f867397724bba40d6c58a96da70f00a339f601501.
Next, if authorized: one bounded boot-completion diagnostic with unchanged caps,
fresh admission and refreshed guest pins; no automatic retry. Retained initialized
guest is diagnostic-only, never fresh-install proof. All190 gates remain required.
No commit/push/merge/release or phone changes.

Initialized-guest observation outcome (2026-10-13, 15:30 UTC): heavy slot released;
all owned processes stopped and no automatic retry. Exact prepared config and its
pinned dependencies passed the 10s admission and guest-state checks. The one actual
observation stopped after 4.859s (14.125s excluding admission), exit88, because host
commit headroom dropped 2,698,199,040 bytes and crossed the existing 1 GiB delta stop.
Available physical RAM dropped only 391,319,552 bytes; minimum RAM 12,566,257,664
and commit headroom 26,354,900,992 bytes. No hard job cap or absolute reserve stop.

Normal helper churn reconciled successfully (late PID51912 resolved; no unreadable
live members). Two incomplete samples leave aggregate sampled peaks null. Kernel
peak job commit 2,642,276,352 bytes under 3,899,998,208; readable observed WS/private
peaks 365,543,424/2,611,408,896 bytes are partial. Actual headless QEMU private commit
reached 2,572,713,984 bytes. Logs show QEMU main loop and operational WHPX, but no
Linux kernel or Android boot-complete evidence. No APK/native checks; not ready for
first native check. This initialized guest is not fresh-install verification.

Evidence: task-2/startup-initialized-outcome.json, c04-startup-initialized-observation
and c04-startup-initialized-artifacts/emulator.log (lines859,867-868,914). Preserve
all changed guest state. Next decision: reconcile the 1 GiB global commit-headroom
drop stop with the observed startup commitment before another authorized run;
retain current stops meanwhile. A future preparation must refresh guest inventory
and pin actual qemu-system-x86_64-headless.exe (the prior config pinned the regular
QEMU binary, while emulator-selected headless QEMU was recorded by the sampler).
No phone changes, commits, pushes, merges or releases. All190 gates remain required.

Initialized-guest readiness checkpoint (2026-10-13, 15:21 UTC): prepared one actual
30-second startup observation; no emulator was started and Beacon owns the heavy
slot. The prior attempt normalized userdata to 6 GiB and left partial disks, stale
lock PID46300 and snapshot directories. All18 guest entries and locator are pinned
and preserved; the recorded owner is absent. Existing -no-snapshot flags remain.
This reused guest is diagnostic-only, never fresh-install verification; successful
boot and the first native check remain undecided until measured startup evidence.

New explicit reviewed-guest mode requires exact inventory/locator/config agreement
and rejects a still-live lock owner. The original empty-guest check stays intact
when no review is supplied. Guarded prepare passed in 11.562s, peak job commit
19,673,088 bytes; mismatched partition review rejected, no owned processes remain.
Artifact allocation 21,554,239,965 bytes plus 8 GiB reserve fits the 32 GiB limit.
No unrelated passed suite was rerun; no phone preparation or APK operation occurred.

Prepared inputs: task-2/startup-initialized-observe-config.json, SHA256
5b4e47aad132a916f74976a683361db7e7db9d99546252323d07988d7c7103ab.
Evidence: task-2/startup-initialized-readiness.json and startup-initialized-prepare-guard.
Next, only after coordinated slot release: run that config once into the new
c04-startup-initialized-observation directory. Fresh 10s host admission, exact
code/SDK/guest pins, lock-owner and port checks remain mandatory. Preserve every
prior failure. All190 full gates remain required; no commit/push/merge/release.

Membership-churn fix checkpoint (2026-10-13, 15:08 UTC): the workspace diagnostic
sampler retains its single bounded refresh and records late new/departed members
as incomplete coverage. Next-poll reconciliation records readable survivors or
exits before measurement; ordinary churn no longer aborts a kernel-contained job.
Live telemetry/ownership failures, hard aggregate job commit, host reserve/drop
stops and cleanup remain enforced. Aggregate sampled peaks stay null when any
sample is incomplete; processes entirely between polls remain unobserved.

Six tiny regressions passed in 5.172s (5.734s guarded total). The assembled real
nested OwnedCommand/guard path forced two births after the refresh: PID44608 was
read next poll and PID49500 exited unmeasured. No unresolved/remaining members.
Injected inaccessible-live counters still stopped only the owned job. Outer peak
job commit 135,204,864 bytes under 155,996,160, plus 100,000,000 monitor reserve;
readable observed WS peak 215,420,928 bytes is partial. No emulator or phone work.
Evidence: task-2/membership-churn-outcome.json, membership-churn-tests-guard and
membership-churn-validation. Tested guard SHA256:
a1c2e74d52ad617213a6f624cca34ab6295eed4cc17134b8a73201a60d97623f.
Next: Jita retains the next heavy slot. Before a coordinated emulator diagnostic,
review reuse of the initialized retained AVD and create fresh pinned launch inputs;
old launch pins are stale and its empty-AVD precondition must not be bypassed.
All190 full gates remain required. No commit/push/merge/release or phone changes.

Validated-config observation checkpoint (2026-10-13, 14:52 UTC): heavy slot
released; no automatic retry. Fresh baseline and exact pinned fingerprints passed.
The emulator ran 7.969s (30.563s including preparation), then the existing bounded
membership rule stopped it: new owned PID15652 appeared after the single refresh
while short-lived cmd/qemu-img helpers were starting/exiting. No unreadable live
PID was reported; one new member had not yet been measured. The incomplete sample
and all raw memberships were retained, and all owned processes exited.

Log evidence reached WHPX availability/system checks and console-port setup, but
no guest kernel boot/completion is established. Reported peak job commit was
153.1 MB; readable observed working set/private peaks 163.6/166.6 MB are partial,
not aggregate guarantees (aggregate peaks correctly null). Minimum host RAM was
11.80 GiB; maximum RAM/commit-headroom drops 515.1/427.4 MiB. No memory stop fired.
No APK/native test ran. Not ready for a native slice. Next: review bounded handling
of normal owned child bursts with tiny tests before any coordinated retry; preserve
the now-initialized diagnostic AVD and review resume semantics. No new copies.
Evidence: task-2/startup-final-outcome.json and c04-startup-final-observation.

Physical-device feasibility was inspected read-only for the user's used spare.
Existing APK supports API24+/ARM64, but runners intentionally require owned
API36/x86_64 emulators and perform global network changes, package uninstalls and
synthetic fit-database replacement. Proposed optional phone development mode
must be additive, explicit-serial/user/package, with a distinct test package if
needed; user setup/trust/install/reset approval remains required. No runner or
phone was changed. Detail: task-2/physical-device-feasibility.json. All190 full
gates remain required; no commit/push/merge/release occurred.

Assembled startup validation checkpoint (2026-10-13, 14:46 UTC): ready for
parent slot release; no emulator was launched. Marker-validation failures now
persist collected host/process/identity counters and their exact error before
owned cleanup. A bounded refresh handles a marker appearing between snapshots.
The real launcher propagates early child failures and pins the reviewed module
path/hash; the final configuration pins guard, launcher and retention source.

Four assembled checks passed under a 256 MB guard: changed fingerprint rejected
before launch; real preparation plus full 6.406s timed Python-child observation;
early child exit 7 retained/propagated; deliberate marker mismatch persisted with
process/host data before cleanup. Tests used the production entrypoint, real
storage/ownership preparation and unchanged host thresholds; only child type,
output paths, smaller owned budget and shorter observation were substituted.
Elapsed 67.953s including three fresh 10s baselines and real storage scans;
121.0 MB peak sampled working set, zero incomplete outer samples, no owned PIDs
left. No code changed after validation; final hashes were checked again.

Ready files in task-2: startup-final-observe-config.json and
startup-final-readiness.json; evidence in startup-assembled-validation and
startup-assembled-validation-guard. The fresh final output directory is unused.
Wait for parent heavy-slot release after Beacon; no automatic launch/retry.
All failed evidence remains. Existing 60s preparation/30s observation timing,
4 GB owned cap, 4 GiB reserve, 1 GiB host delta stops and stable >=8 GiB admission
remain; there is no total physical-RAM guarantee. No APK/native test, global
setting change, unrelated process kill, commit/push/merge/release occurred.

Follow-up observation failure (2026-10-13, 14:36 UTC): heavy slot released;
no automatic retry. Fresh baseline passed, but the single attempt ended after
9.422s total. The workspace's older artifact_retention.py shadowed the reviewed
repository module and lacked OwnedCommand.wait. Launcher context cleanup stopped
the emulator immediately; the guard rejected its now-unobservable start marker.
The emulator log is empty and guest boot is not established. All owned PIDs exited.
Saved samples cover preparation only; the final marker-validation sample was not
persisted, so these numbers do not establish complete emulator memory accounting.
Minimum saved host RAM was 12.09 GiB; no resource stop was reported.

The launcher now loads the repository retention module by exact absolute path,
checks the wait API before launch, and records dependency path/hash. Two tiny
regressions passed under 256 MB, including the actual observe launch/marker/wait
path with a Python child only. No emulator retry or APK/native test ran. Evidence:
task-2/startup-followup-failure.json, c04-startup-followup-observation and
startup-dependency-tests. Next: await parent coordination; preserve failed logs
and marker, recheck guest state and persist marker-error samples before any
separately authorized attempt. Docker/WSL and user sessions were untouched.
No commit/push/merge/release.

Startup sequencing correction (2026-10-13, 14:20 UTC): prepared only; no
emulator/native launch. The empty owned diagnostic AVD was verified and reused
without creating another AVD or copying disk images. Ownership/configuration and
aggregate storage admission passed, including both canonical and packaged
LocalAppData roots with filesystem-identity deduplication. Preparation completed
in 8.766s under a 256 MB guard (53.2 MB sampled working set), no owned PIDs left.

The guard now separates a 60-second preparation deadline from a 30-second
observation interval beginning after the emulator's process launch. PID,
creation time, executable and job membership validate the launch marker; old
markers are rejected. Periodic storage scans run in the owned launcher while
the independent guard continues sampling. Three tiny timing tests passed in
4.157s guarded elapsed: delayed launch receives its full interval, absent marker
hits preparation deadline, and foreign marker is rejected. One outer exit-race
sample kept unavailable counters as errors/nulls; live coverage was not lost.

Ready evidence/config in task-2: startup-followup-readiness.json,
c04-startup-followup-prepared/preparation.json, observation-clock-tests and
startup-followup-observe-config.json. Await parent heavy-slot release after Jita;
do not launch automatically. Existing 4 GB owned cap, 4 GiB reserve, 1 GiB host
baseline-drop stops and stable >=8 GiB baseline are unchanged. No physical-RAM
ceiling claim. Old evidence is preserved; no commit/push/merge/release.

Startup observation checkpoint (2026-10-13, 14:11 UTC): the released heavy
slot was used once and is now released. Three tiny stricter-host-stop checks
passed. All 11 admission readings stayed above 8 GiB. The owned command stopped
at its 30-second limit (30.141s elapsed), with complete sampled coverage and all
seven owned PIDs gone. Storage preparation/accounting consumed most of that
window: emulator.exe began at 14:11:47.832 UTC, only about 2.2 seconds before
termination. QEMU/crashpad processes were captured; the log contains frontend
initialization only. Guest boot was not established and no APK/native test ran.
Peak job commit was 68.9 MB; owned-plus-monitor sampled working set 127.7 MB,
private commit 81.7 MB. Minimum host available RAM was 12.28 GiB; no 4 GiB reserve
or 1 GiB baseline-drop stop fired. Old failed AVDs/evidence were preserved; only
a small device configuration was copied to the new private scratch AVD.
This is not a 30-second guest observation or proof of a 4 GB physical-RAM ceiling.

Evidence in task-2: startup-observation-outcome.json, c04-startup-observation,
c04-startup-observation-artifacts and host-stop-tests. Next: await parent
coordination, with no automatic retry. A separately authorized follow-up should
complete storage preparation before starting the emulator observation clock,
retaining existing cap/reserves/delta stops and periodic storage accounting.
Docker/WSL and user sessions were untouched. No commit/push/merge/release.

Telemetry recovery checkpoint (2026-10-13, after user readiness at 13:53 UTC):
candidate 2e518a2e and local edits were consistent; the prior owned job no longer
existed. The workspace telemetry helper now retains identity/membership/query
errors, uses system-wide GetPerformanceInfo commit counters, handles a startup
race with one bounded refresh, and reports incomplete totals as unknown. Five
tiny synthetic checks passed in 4.656s guarded elapsed, 86.5 MB sampled working
set under 256 MB, no owned processes left. The unchanged focused tank corruption
summary passed all 30 corruption subcases in 21.520s (22.828s guarded), 76.5 MB
sampled working set, complete sample coverage and at least 9.15 GiB host available
RAM. Its timed stacks showed active repeated metadata comparisons; the earlier
whole-batch timeout had no per-test timings and does not establish a deadlock.
The rest of the inherited batch was not rerun. Historical interrupted/failed
results remain intact. App/test/engine sources and verified APKs are unchanged.

Evidence in task-2: telemetry-readiness.json, telemetry-tests-resumed-guard,
telemetry-validation-resumed and tank-focused-guard. A separate manual review
checked Windows structures/units, failure handling and owned-only cleanup.
No 4 GB total physical-RAM guarantee is claimed; sampling and uncharged memory
remain limitations. The native slot stays closed while Beacon compile-only goes
first. Next bounded stage: after parent coordination, prepare a single 30-second
startup diagnostic with a stable 8 GiB admission baseline and tiny-tested stricter
host stops (4 GiB reserve / 1 GiB baseline delta), preserving failed AVDs. Those
stricter stop thresholds remain proposed, not yet implemented. No emulator,
native test, commit, push, merge or release ran in this recovery stage.

## Retention review and memory investigation

Latest retention/review checkpoint (2026-10-13): changes remain local and
uncommitted. Final review preserves prior external artifact roots and the stricter
saved limit on resume, bounds command waits by the remaining timeout, and validates
cleanup ownership/receipt integrity. Thirty-two C04/retention tests passed (5.159s
test time; 15.187s guarded elapsed), 97 MB peak sampled working set under a reduced
256 MB budget, no owned processes left. Inherited compatibility logged 45 passes,
including all 32 plan/reporter tests; the tank corruption-summary test timed out
under the 90-second guard (99.359s elapsed). That batch is incomplete, not passing.
No native retry, commit, push, merge or release was performed.

The native host-memory collapse remains unattributed. RAM had fallen by 1.88 GiB
before emulator launch. The largest adjacent-sample loss was 3.73 GiB available
RAM and 3.92 GiB commit headroom over 3.266s while sampled private usage was flat.
The monitor silently omitted unreadable processes and did not retain their raw
job memberships or process identities. AVD disk initialization overlapped the
drop; no guest boot was established. The 12:54 UTC snapshot found no emulator,
QEMU, ADB or Java; the existing WSL VM predates the attempt and was untouched.
Low owned private commit does not exonerate Pyfa or implicate unrelated apps.
Job-charged commit and sampled working sets do not guarantee total host RAM use.
Evidence: task-2/pyfa-memory-investigation.json, pyfa-memory-current.json,
c04-budget-contract/{samples.jsonl,result.json}, c04-retention-review/result.json
and c04-retention-inherited/{output.log,result.json}.

Next bounded stage: repair memory-observation coverage offline and validate with
tiny synthetic checks. Any native retry requires a separately coordinated slot
and explicit approval after review of the accounting limitations; none is started.
Keep the 4 GB cap, preserve failed guests/evidence and unrelated sessions. The
32 GiB retention policy is implemented but full native delivery remains unverified.

## Latest bounded execution checkpoint

Updated: 2026-10-13. C04 remains active on codex/c04-drone-editing,
stacked locally from C03.2. Tested source: 2e518a2eb61e20df13836278402950a2ba4918af.
Local development/tests are authorized; publication/merge/release are not.

The approved active-count conservation implementation and all prior bounded
host evidence remain intact. See tasks/C04-active-count-decision.md and
evidence/c04-conservation-development.json. No production source changed in
this bounded execution batch.

Current Kotlin sources compiled and both debug APKs built successfully under
the user-approved aggregate 4 GB decimal workload budget. A Windows Job Object
enforced 3,899,998,208 bytes aggregate committed memory with 100,000,000 bytes
reserved for the monitor. Descendants ran below normal priority, with one
Gradle worker and no shared daemon. Working set and host reserves were sampled
every 0.5 seconds. This is not a hard aggregate physical-RAM guarantee.
Small allocation and owned-process cancellation probes passed.

The offline build passed 75 tasks in 7m36s. Reported job commit peaked at
2.040 GB, sampled workload working set at 1.998 GB, and minimum observed host
free RAM was 8.46 GiB. Both APK signatures and bundled database/184-source/
ARM64/x86_64 contents passed verification. No memory cap was reached.

OneDrive prevented generated-directory removals. Generated source content was
refreshed with exact file-list/hash checks; the successful app build used an
external output directory and verified existing Python dependency caches.
All old APKs, source and evidence remain; no software was installed.

Native tests remain UNEXECUTED. Default emulator userdata needed 12 GiB free.
A requested 2 GiB userdata setting was normalized by the emulator to 6 GiB;
the existing 10 GiB free-disk watchdog stopped startup. All owned processes
exited. Lint admission also stopped before execution. No screenshots or full
verification are claimed; all 190 required full gates remain required.

Next: after approved disk cleanup, reuse successful APKs and run focused
native/offline/touch/restart tests under the unchanged 4 GB memory cap, then
lint and screenshot review. Coordinate complete inherited plus C04 proof.
The five old Oct5 inspection AVD runtime folders are not current test inputs.
Cleanup is not yet authorized; preserve all reports/screenshots/logs outside avd.

Current receipt and exact commands/results:
C:/Users/HallT/Documents/Codex/2026-10-13/task-2/c04-budget-checkpoint.json
The native plan's older uncompiled/resource-hold notices are superseded by
this measured execution checkpoint. No merge, release, publication, prototype,
C05 or C10 editing occurred.


## Historical plan and checkpoints

Status: Kotlin compile proof is retained only for `9c5042f9`. Expanded native
sources are uncompiled; all native executions remain unexecuted. No F08 row is complete. Jita released the heavy slot for the
bounded compile-only check below; that check is complete and its slot released.
Coordinate slot ownership again before further heavy work.
The user selected [active-count conservation](C04-active-count-decision.md). The
current batch includes split/merge and existing-roll conservation; older
unresolved-decision notices later in this history are superseded.

## Existing proof and source review

Preserve `77ef700a` and its [host receipt](../evidence/c04-integrated-development.json):
four detail/mutation groups, 60 stacks / 2,820 metric comparisons, fresh-process
mutation persistence, and five core regression groups / 15 original command
cases. That earlier review changed no Python calculations. The latest acceptance
checkpoint fixes graph-rebuild inspector IDs and justifies the recorded linked
and mutation-recovery regressions; do not repeat checks merely on task resume.

The integrated review covers command dispatch/history/capture/restore, pinned
original command expectations, detail transport/units/absence, native worker
serialization, controls/navigation, runner selection and persistence startup.
Three concrete integration findings are corrected:

1. Drone addition from Cargo's equipment browser left `showCargo` true, hiding
   the requested Drones screen behind route priority. Clear it on successful add.
2. Remove/toggle selections were not copied before enqueueing. Snapshot both
   lists so later caller edits cannot change an already queued command.
3. New native tests would join the inherited five-test initial suite. Exclude
   all C04 classes there and execute them explicitly below. Register `c04_phase`
   with the diagnostic runner so these persistence tests use durable storage.

New test assets contain independent original expectations only; the host seed
builder produces synthetic existing saved inputs, not expected calculations.
No production mutation-seeding endpoint or C10 edit action was introduced.

## Exact prerequisites and resources

Use the clean reviewed C04 commit in the real checkout
`C:/Users/HallT/OneDrive/Desktop/Documents/PyfaDevelopment`. Record its SHA,
full build command/output/exit, package hashes and generated engine manifest in
a new evidence directory. Do not use stale APKs from C03.2. The focused runner
checks clean source, packaged Python hashes and reference asset identity; the
fresh build log and sealed commit supply Kotlin build provenance.

Existing paths verified read-only on 2026-10-13:

- Python: `.venv/headless/Scripts/python.exe` (3.11 environment).
- JDK: `build/tools/jdk-17.0.20.1+1/bin/java.exe`.
- SDK: `C:/Users/HallT/AppData/Local/Android/Sdk`, including `platform-tools/adb.exe`,
  `emulator/emulator.exe`, `cmdline-tools/22.0/bin/avdmanager.bat` and the installed
  `system-images/android-36/google_apis/x86_64/source.properties`.
- Gradle cache: `C:/Users/HallT/AppData/Local/PyfaAndroid/PyfaDevelopment/gradle-home`.
- Bundled game database: `android/build/engine/assets/engine/eve.db`; verify its
  exact SHA against the original drone-detail fixture before creating the seed.

Use cached dependencies only; six wheel files and the pinned Gradle distributions
must already be present. A missing package/cache entry is a blocker, not permission
to install or download. Gradle remains `-Xmx3g`, maximum two workers. Build and
emulator phases run sequentially, with no Jita/Beacon/Docker test overlap.

Create one new disposable `pyfa-c04-<unique-run>` Pixel 2 AVD, API36 Google APIs
x86_64, under that new evidence directory's `avd` folder. Use WHPX after its
readiness check, two guest cores, 2048 MiB guest RAM, SwiftShader, no snapshots,
no audio, no cameras and no visible window. Do not reuse an earlier verification
AVD or a phone. Reserve an unused even port in 5560..5678 and record the exact
serial. Confirm its AVD name, emulator flag, API and ABI before installation.

Budget at least 8 GiB free physical RAM and 10 GiB free disk as conservative
planning headroom, not measured requirements or a performance claim. The latest
read-only observation at this checkpoint was 5.42 GiB RAM and 15.19 GiB disk,
below native RAM admission; recheck both immediately before starting. Do not delete old evidence
or change swap/VM settings to meet this budget. Boot deadline: 300 seconds;
each of the nine instrumentation phases: 900 seconds; individual adb operations:
120 seconds. A timeout is a failure to investigate, not permission to extend it.

## Build and prepare after the hold lifts

Set `JAVA_HOME`, `ANDROID_HOME`, `ANDROID_SDK_ROOT`, `GRADLE_USER_HOME`, UTF-8 and
PATH as in `android/verify-local.ps1`, using the verified paths above. Do not invoke
its `-Mode native` for this bounded batch: that rebuilds and executes the inherited
chain. Retain stdout/stderr and nonzero exits for every command below.

```powershell
# From repository root, only after heavy-slot release:
.\.venv\headless\Scripts\python.exe -I -B android/prepare-engine.py
# From android/:
.\gradlew.bat --offline --no-daemon --console=plain --max-workers=2 :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
# Then package/signature checks from the existing build gate:
& "$env:ANDROID_HOME/build-tools/35.0.0/apksigner.bat" verify --verbose --print-certs app/build/outputs/apk/debug/app-debug.apk
..\.venv\headless\Scripts\python.exe -I -B ci/verify-apk.py
# From repository root, with a NEW external seed output directory:
.\.venv\headless\Scripts\python.exe -I -B android/ci/prepare-drone-seed.py --database android/build/engine/assets/engine/eve.db --output <new-seed-directory>
.\.venv\headless\Scripts\python.exe -I -B android/ci/prepare-drone-seed.py --database android/build/engine/assets/engine/eve.db --family conservation --output <new-conservation-seed-directory>
```

Stop on source/package divergence, build error or missing cached dependency. Fix
the specific issue, commit a new candidate and rebuild only what changed. Do not
mark the authored Kotlin tests as passing based on source inspection.

Create the new AVD using the installed avdmanager and launch the emulator with
`Start-Process -WindowStyle Hidden`; retain the process ID/log and use:
`-avd <new-name> -port <reserved-port> -accel on -memory 2048 -cores 2 -no-window
-gpu swiftshader_indirect -no-snapshot -noaudio -no-boot-anim -camera-back none`.
Set `ANDROID_AVD_HOME` to the new evidence directory's `avd` folder. Do not start
another AVD while this one exists. A failing runner preserves this test app and
all evidence for diagnosis; do not blindly rerun against or clear it.

```powershell
.\.venv\headless\Scripts\python.exe -I -B android/ci/check-drones.py --serial <owned-emulator-serial> --avd <new-pyfa-c04-name> --seed <seed-directory> --conservation-seed <conservation-seed-directory> --evidence <new-native-evidence-directory> --heavy-slot-released
```

The flag records a prerequisite already coordinated by the operator; it does not
grant resource ownership. The runner refuses an existing app installation and
does not build, install tools, start or stop emulators. It installs only the two
debug APKs into the checked disposable device. It retains the first fresh-install
UI evidence before uninstalling its own synthetic installation and reinstalling
with the conservation seed, retains its before/reopen evidence, then reinstalls
with the existing-mutation seed. No user app data is involved.

## Authored executions and expected evidence

| Phase | Native executions | Required outcome |
| --- | ---: | --- |
| contract | 3 | Strict complete details/units/identity/count codec; eight operation encodings; immutable queued selections |
| fresh-ui | 1 | Offline first launch, Cargo→browser→Drones, add/add-stack, clone, quantity/resource warning, bulk activation/removal, undo/redo, recreation preserving identities/selection |
| core | 1 | 18 original core/hull cases; before/Do/Undo/Redo counts, output, resources and IDs; stale/invalid atomic rejection |
| linked | 1 | 14 projection/command cases with two recipients and unaffected fit; six ordinary-variation steps; original calculations and identity/history |
| conservation | 1 | 14 approved count/EOS cases, exact mutation compatibility, identity/history, atomic rejection and overflow |
| conservation-restored | 1 | New process/session reopens all 14 conservation fits with complete graph/details intact |
| prepare | 1 | 60 independent stacks / 2,820 raw metrics; exact existing rolls; clone/undo/redo IDs; quantity/toggle isolation; stale/invalid rejection leaves details/history/SQLite unchanged; fit duplication has independent IDs |
| restored | 1 | Force-stop and new process/session; all eight saved fits, rolled values, IDs, revisions, complete graph and metrics restored offline |
| mutation-ui | 1 | Separate existing rolls, no ordinary variation route for mutated stack, details/selection retained after activity recreation |

Eleven authored executions, five screenshots (including ordinary variation and conserved split/merge), original fixture and APK/seed
hashes, per-phase logs, durable before/reopen receipts and a final development-only
JSON result are required. Inspect every screenshot at full size; test success
alone does not approve layout, clipping, keyboard behavior or touch usability.
The runner's parser requires each named test's start and success events, exact
count and terminal success code; malformed/partial output must fail closed.

## Still outside this bounded proof

The split/merge decision is resolved. F08.03 still needs native and full proof. C04 gate registration,
original core/linked/variation native matrix authoring and host acceptance are now
complete, but native execution remains open. Multi-window/landscape edge cases,
upgrade migration, physical ARM64/older APIs and user usability remain open. Existing host tests cover injected post-mutation and durable-save failures;
the authored native test covers transport rejection atomicity, not native disk
fault injection. Do not conflate these.

The full plan preserves the 175 inherited gates and adds 15 C04 gates for
190 required gates. Its explicit split/merge acceptance gate validates the
approved policy and requires successful exact-candidate reference/host/native
evidence; the user decision alone cannot satisfy it. This
focused runner remains development-only. Run the final exact candidate only
after coordination. No push, PR, merge, release,
prototype work, C05 work or software installation is authorized by this plan.

## Completed compile-only admission (2026-10-13)

[Receipt](../evidence/c04-compile-development.json): the original 8 GiB RAM /
10 GiB disk conservative native admission is unchanged. The received resource
report (6.04 GiB RAM, 15.29 GiB disk) did not admit an emulator/native run.

A separately bounded compile-only configuration used one worker, no parallel
tasks, a single-use Gradle JVM with `-Xmx2g`, 768 MiB maximum metaspace and
256 MiB reserved code cache, plus in-process Kotlin compilation. Entry checks
required 5.5 GiB free physical RAM, 6 GiB commit headroom and 10 GiB free disk.
Three-second monitoring would stop only the owned process tree below 1.5 GiB
free RAM, 2 GiB commit headroom or 10 GiB disk, or after 900 seconds.

The offline dry run found `installDebugPythonRequirements`. The real compile
explicitly excluded Python extraction, requirement installation, source merging
and proxy generation and disabled toolchain/SDK downloads. It targeted only
`:app:compileDebugKotlin` and `:app:compileDebugAndroidTestKotlin`, reusing existing
prerequisites. No engine preparation, software/dependency installation, APK
assembly, lint/package verification, emulator launch or test execution occurred.

Both compiler targets passed on `9c5042f9` in 3m54s (29 tasks: six executed,
23 up-to-date). Initial measured RAM was 5.92 GiB; minimum observed free RAM
4.10 GiB, commit headroom 15.46 GiB and disk 15.38 GiB. The existing clipboard
deprecation warning in `InspectionView.kt` was the only diagnostic. This shows
that this compile configuration fit the observed headroom; it does not establish
a minimum runtime requirement or relax native admission.

The subsequent lightweight gate/core/linked/variation acceptance stage is
complete; see the checkpoint below. Split/merge still awaits the user decision.
Runtime, package, screenshot, upgrade and usability evidence remain separate.

## C04 acceptance preparation checkpoint (2026-10-13)

The remaining lightweight gate and acceptance work is complete. The current
source adds independent original-command expectations for 14 linked-recipient
cases, six ordinary-variation steps and three hull boundaries. Seven projection
and seven command cases each cover the source, two recipients and an unrelated
fit, full statistics/units, revision propagation, all six core operations plus
variation, post-mutation exception and durable-save rollback, undo/redo identities
and a fresh-process reopen. Ordinary variations also cover invalid index/item/
family, no-op history and redo-branch rejection. All six commands now contribute
original Do/Undo witnesses to exhaustive history-operation coverage.

This found a product bug: rebuilding projection links can refresh ORM drone
objects after their inspector IDs have been bound. A rejected edit then exposes
new IDs despite restoring the saved records. `BridgeSession._rebuild` now restores
all inspector identities after links and calculation are rebuilt. Both linked
groups and the existing four detail/mutation groups, including durable recovery
and a fresh process, pass. Failed attempts remain preserved in the receipt.

The exact inherited 175-gate sequence is retained as the full plan's prefix.
Eleven C04 host gates, one bounded native-delivery gate and one explicit
split/merge acceptance gate bring the required plan to 188. The launcher stops
full runs before expensive work while that decision is unresolved; the reporter
also rejects missing C04 gates or the unresolved decision. There is no bypass
switch. Eleven checker/parser tests and 58 inherited plan/report/tank checker tests
passed; these are host harness checks, not native or full-delivery passes.

Nine native executions in seven phases and four screenshots are authored. The
new matrix compares 18 core/boundary cases, 14 linked cases and six variation
steps with original expectations. Fresh UI adds ordinary variation and undo;
restart receipts now retain the complete graph and details for independent
rechecking. These changed Android tests are **uncompiled and unexecuted**. The
earlier successful Kotlin receipt applies only to `9c5042f9`; it does not cover
this source or the new packaged Python graph-rebuild fix.

[Acceptance receipt](../evidence/c04-acceptance-development.json) retains exact
source/fixture hashes, commands, successful outputs and earlier failures. The
[split/merge decision](C04-active-count-decision.md) remains unresolved: choose
desktop semantics with an explicit F08.03 active-count exception, or conservation
with a desktop-target exception and explicit split allocation. Neither is a
default. After that choice, implement and verify its witnesses. Coordinate the
heavy slot and require at least 8 GiB free RAM / 10 GiB free disk before native
work, then build the exact candidate, run native/offline/restart/touch checks,
review screenshots and run/report the complete inherited plus C04 plan. No F08
row is complete. No native/full execution, software installation, publication,
merge, release, prototype or next-stage work occurred in this checkpoint.

Integrated launcher retries use `avd-c04-r<N>` / `pyfa-local-<run>-r<N>-c04`;
each explicit native restart receives a fresh C04 AVD. Previous C04 AVD data
and failure evidence remain intact. The inherited AVD stays separate.

## Approved conservation implementation checkpoint (2026-10-13)

The user chose to preserve total active drone counts during split/merge, matching
F08.03. This resolves the semantic decision and supersedes older unresolved
decision notices below/in prior receipts. The deterministic split allocation is
`movedActive = min(splitAmount, originalActive)`; the original stack retains the
remainder. Thus 5 stored / 3 active split by 2 becomes 3/1 + 2/2. Merging 3/0 and
2/2 becomes 5/2. The destination identity survives; a split retains the original
identity and gives its appended stack a fresh one. Merge rejects different item
types, bases, mutaplasmids or exact rolls, self-merges and count overflow.

The two operations use the existing serialized worker, transactional revisions,
linked invalidation, graph history and durable storage. Typed native controls
provide split quantity and merge of two selected compatible stacks. Eight drone
operations now have explicit history witnesses. Mutation creation/editing remains
outside scope.

[Conservation evidence](../evidence/c04-conservation-development.json): 14 explicit
count-table cases plus four projection/command cases passed pinned-EOS numeric
comparisons, identity and recipient revisions, stale/injected mutation/save
rollback, undo/redo/branching, duplicate isolation and all 18 fresh-process store
reopens. Fourteen malformed/boundary requests, including merge overflow, rejected
atomically. Expectations come from literal approved count tables evaluated with
pinned EOS, not from Android edits and not from unchanged desktop split/merge
commands. Independent regeneration matched the fixture. Thirteen C04 checker
tests and 58 inherited checker tests passed. The synthetic 14-fit conservation
seed was written and reopened successfully. The first restart test omitted its
later history-witness fits from its expected snapshot; that harness error and its
failed evidence are retained, and the corrected full check passed.

The required full plan is 190 gates: unchanged inherited 175-gate prefix, 13 C04
host gates, the C04 native delivery gate and the split/merge acceptance gate. The
last gate now validates the approved policy plus successful exact-candidate
reference/host/native proof; it cannot pass solely because the decision exists.
The reporter independently enforces these requirements. Future native attempts
get separate seed and AVD paths; emulator disks are excluded from the artifact
manifest while evidence and synthetic seed files remain included.

Eleven native executions in nine phases and five screenshots are authored,
including conservation of existing rolls and a separate fresh-process reopen.
Current Android sources are uncompiled and all native executions remain
unexecuted. The compile receipt at `9c5042f9` remains exact-source historical proof
only. No F08 row or full milestone is complete on these host checks.

Next: wait for dot's fresh shared-memory check and explicit heavy-slot grant;
then build the exact candidate, verify packages, execute offline native/touch/
restart checks, inspect all screenshots and complete the inherited plus C04 full
verification. No emulator/build/heavy check, merge, release, publication, software
installation, prototype or next-stage work occurred in this checkpoint.

</details>
