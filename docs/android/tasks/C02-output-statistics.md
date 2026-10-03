# C02 — outgoing statistics

Selected2026-10-03, branch `codex/c02-output-statistics`, base `c887fd6b`.
One reviewable outcome covers all F06.01–F06.14, with one complete delivery suite.
The native statistics surface groups firepower/mining, bombing and outgoing
repair/transfer details. Preserve every field, view switch and desktop assumption.

EOS supplies weapon/drone/fighter/total damage, mining and outgoing repairs.
Pinned original full views define compact display, shares, spool details and
bomb signature/Red Giant/Covert Ops rounding. Calculations stay in Python;
Kotlin consumes strict typed results on the serialized worker. Missing results
stay unavailable. Related per-fit target-profile inputs require validation,
durable copy/history and restart; named-profile management remains D05.
Existing and future drone/fighter editors retain their C04/C05 ownership.

Acceptance: independent fresh original wx/EOS exports for turret, missile,
spool, drone/fighter, target-profile/no-profile, mining crystals/noncrystals,
bomb signature/resistance/Red Giant and all four outgoing types; real native
controls/details and fit/revision refresh, read-only/GC, mutation/rejection/no-op/
failed-save/history/copy/recreation/restart; strict numeric/units/null/fixture
and corrupted-report validation; every inherited host/build/package/offline
native gate, A10 requirements and actual screenshot review. Complete focused
implementation validation and summary preflight before full verification.

Implementation, source review and required local native verification complete.
The serialized EOS reader supplies both damage modes, all five actual damage
components (including pure breacher damage), current/initial/full spool values,
mining second/hour detail,24 bomb cells and four outgoing rows. Compose consumes
strict typed values and provides reversible views/details and validated per-fit
target assumptions. Profile edits use existing atomic storage/history; named
profiles, addition editors and module/global spool controls keep their roadmap owners.
Initial fighter and Red Giant inputs are limited to reproducing these statistics.

Two fresh unmodified wx/EOS exports agree on37 cases. The pinned compact/full
outgoing calculation and refresh ASTs are identical. Focused host checks pass
all37 cases, three read-only/GC repeats, profile apply/clear/undo/redo/no-op,
malformed/stale/failed-save rejection, copy and a fresh39-fit restart.
Twenty-five output schema/input/fixture/full-summary tests pass, including21
synthetic report corruptions and rejection of changed packaged fixture contents
even with an updated matching hash. Historical18 summary-source,25 history-source,
26 tank,22 defense, six fixture-adoption and22 truthful-reporter tests pass.
Both APKs, the new instrumented test and lint pass in the installed offline
Gradle environment. The final native report writer preserves decimal JSON types.
All105 inherited gates/order are retained, adding exactly four output gates.

Source review checked the EOS boundary, original formatting/rounding and units,
read-only caches, missing-value handling, strict profile/environment/fighter
validation, atomic mutation/revision/history/copy, fit-switch/recreation query
ownership, restart storage flag and raw transport/fixture provenance. A focused
matrix caught EOS TargetProfile deepcopy dropping HP/spatial fields: the reader
now shallow-copies only damage containers, retaining the immutable profile and
breacher inputs. Upstream EOS stays unchanged. No assertions, tolerances,
timeouts, process boundaries or A10 requirements were weakened. Historical
exact-source tests now inspect their actual delivered correction commits; their
reuse validators still reject every unrelated difference.

Preserve failed development attempts: the wrong breacher hull (Mamba; original
EOS requires Tholos), an oversized synthetic fighter squadron, the deep-copy HP
mismatch, and the initial no-op revision expectation (existing bridge refresh
revisions advance once while inputs/history/modification order remain stable).
Evidence remains under local c02-reference-20261003-0545/0555 and
c02-host-20261003-0615/0630 directories and build/c02-* logs. C01 proof stays closed.
All109 final gates and191 screenshot reviews now pass; see the final delivery
section and [exact-commit receipt](../evidence/c02-native.json). No hosted Actions
execution, release, phone installation or usability sign-off is claimed.

## Full-run history registration repair

Run `20261003-063304-4b42c02f-3dd323` at `4b42c02f` passed54 gates.
Gate55 failed at the unchanged full-history-coverage assertion: C02 added
`set_target_profile`, but the remaining-action witness set had not exercised it.
All28 original cases passed; the other22 tests, including durable failures and
restart, passed. Preserve `logs/054-headless-history_mutations.log`, its worker
`tests.log` and `failed-history-registration-4b42c02f/run.json`.

The repair adds eight apply/clear/undo/redo observations using original C02 cases35
and36, with exact revisions, cursors, labels, profiles, outputs and recent-use
preservation. The coverage assertion, all original cases,23-test count, numeric
tolerances,900-second host deadline and every native/A10 requirement stay intact.
A focused execution of the actual new witness passes. Its first private harness
attempt omitted BridgeSession from the execution namespace; that diagnostic log
is retained and the corrected focused execution passes. No product/fixture changes.

Reuse is limited to the exact original `4b42c02f` and its preceding54 gates.
SHA256 guards accept only the reviewed witness extension; every other harness,
engine, fixture or completed-boundary change fails. Seven focused guards include
an actual failed-constructor integration retaining every tested commit and the
failed attempt. The22 reporter and six inherited adoption tests also pass.
Resume the existing run, retry this gate and continue pending dependants; no full
chain restart or earlier-gate rerun is needed.

## Full-run resource boundary correction

The history retry at `118a4a4a` passed;55 gates are retained. The resource gate
failed because its C01.1 test still expected every fighter-bearing diagnostic
input to be unsupported. C02 intentionally accepts validated initial fighter
inputs. Preserve `logs/056-headless-resources.log`, its worker `tests.log` and
`failed-resource-boundary-118a4a4a/run.json`.

A focused error-category correction still failed on an accepted case. Rather
than retrying unchanged, one direct diagnostic checked all four ephemeral cases:
incompatible turret/launcher states and Firbolg squad size9 (EOS maximum6) reject
with INVALID_EDIT;20 valid squads of6 are accepted with explicit tube/bay
overloads. The corrected test requires every original desktop resource value,
unit/type/display/overload flag and exact retained fighter input for that case,
and keeps exact rejection/data preservation for the other three. This reflects
C02's existing supported schema; no product code, fixture or capacity assertion
was weakened. The full14-case resource matrix and fresh-process restoration stay.

Focused seven resource tests and11 raw validators pass. Seven exact-source and
actual failed-constructor tests prove retention of the55 gates and original
mixed commit stamps; seven prior witness guards,22 reporter and six inherited
adoption checks pass. Reuse permits only this exact resource test correction
from `118a4a4a`, unchanged executed host/build ASTs and the55-gate boundary.
The earlier54-gate witness proof remains independently validated. Preserve the
first focused failure and the subsequent diagnostic/corrected logs. A quoting
typo in the new guard regression file was repaired before its seven tests passed;
the failed focused log remains.

## Native profile serialization and editor refresh

The same run at `31cb2859` passed106 gates, including every inherited native,
offline, restart and A10 gate, before C02 prepare failed on an exact decimal-kind
assertion. Android JSONObject writes integral Double profile values as integers.
Original uniform0.0/1.0 profiles therefore produced integer zero effective drone
damage instead of the reference decimal zero. A focused EOS reproduction proves
both cases; mixed-profile14 remains unchanged. All numbers and type assertions
remain exact; no fixture or reported result is rewritten.

Repair `eab3e092` preserves only the target-profile path's decimal representation
in CreateFit and SetTargetProfile requests. Other request fields use the original
JSONObject serialization; clearing a profile keeps its existing null encoding.
Native assertions check all eight fields for original cases14/15/16/35/36.
Both APKs and offline lint pass. The focused native retry passed all37 calculation
cases, protocol guards, screenshots and profile HP history, then failed because
the editor's expanded state was discarded during a revision refresh.

Repair `4408f796` places profile expansion, selected page and raw/effective choice
before the temporary loading branch, scoped to the selected fit. The exact Clear
action, existing60-second UI waits,120-second requests,900-second C02 phases and
all original comparisons remain. The focused prepare/restart pair passes on a
fresh disposable API36 emulator seeded from a validated230-fit prior report.
Its actual summary passes all37 outputs,268 fits,copy/history,manifest/settings,
packaged fixture bytes and18 protocol rejection checks. Evidence:
`c02-profile-focused-20261003-101218`; earlier failures/preflight logs are retained.

The changed app APK requires fresh final build/package and native proof. Eight
source/constructor regression tests accept only these exact three Kotlin changes
and retain only60 unchanged reference/host gates. They reject any other profile,
fixture, engine, host execution, assertion or boundary difference. The original
106 results and failure remain archived with their actual commit stamps; they do
not become passes for the new APK. Affected22 reporter, seven resource-reuse,
seven witness and six prior-adoption regressions pass. Final delivery still needs
all109 gates,191 actual screenshot reviews and actual-report corruption checks.

## Final local delivery proof

Tested code `1b4630d31efe64770be5fd283a274ec2b7dd8561`, run
`20261003-063304-4b42c02f-3dd323`:109 gates pass (60 reference/host, five
build/package,44 native),71 actual native executions,268 saved fits including
230 inherited,191 actual screenshot reviews and36 actual-report corruptions
rejected. Two independent fresh original exports cover37 legal synthetic cases.
All14 inventory rows now link concrete reference/native evidence. Package/lint,
offline installation, serialized EOS, GC/read-only, numeric kinds/units/display,
profile history/copy/recreation, fresh-process restoration and A10 checks remain.
The screenshots record minor inherited scrolled-header/status-bar overlap;
the statistics and detail rows remain readable. User usability is not signed off.

The final Android repair reused only60 unchanged host/reference gates with exact
source guards, then rebuilt and ran native verification on the final APKs. At74
gates, charge prepare instrumentation passed but ADB went offline. Same-AVD raw
report and seven screenshots were empty, while the store contained partial new
fits. Those bytes/diagnostics and failed logs125/127 remain in
`failed-charge-empty-evidence-1b4630d3`. A fresh native chain was necessary;65
valid non-native gates stayed retained. Its first boot lacked41MB of the required
disk space. Removing only verified inactive disposable AVDs freed space; their
APKs/screenshots/reports/logs remain. Installed environments were reused.

At cargo actions, prepare instrumentation passed but collection truncated when
ADB disconnected. The unchanged same-AVD prepared report was recovered with
before/after SHA equality, prior store/PID checks, installed APK hashes and five
screenshots. A targeted restored phase passed native assertions but private
isolated Python ignored PYTHONUTF8 and misdecoded Unicode names. Its summary
failure remains logged153. No strings/hashes were rewritten. Direct byte
collection found the actual restored report empty (failed155). Only that
read-only restored phase was reexecuted with verified UTF8 collection; original
prepare remained intact. The unchanged original cargo summary then passed.
`cargo-transport-recovery.json` binds actual raw phase bytes, combined report,
source, APKs and original prepare instrumentation; archives preserve all failures.
The outstanding23 native gates and final summary subsequently passed.

An additional private corruption-helper attempt failed before execution because
its file was Windows1252. Original bytes are preserved; changing only the private
file encoding to UTF8 allowed all36 actual-report corruptions to be rejected.
No tracked implementation/fixture/validator change or native rerun was needed.

No test data, reported hashes, functional assertions, numerical tolerances,
per-operation limits, process boundaries, timeouts or A10 requirements changed.
Final source review and diff checks cover the coherent implementation and its
concrete corrections. Delivery publishes only the truthful local result. Next
approved outcome after merge is C03 targeting/navigation and attribute inspection.
