# C03 - targeting/navigation and attribute inspection

## Current disposition - 2026-10-16

C03.1 is delivered at master 745fc1e2 / PR41. C03.2 implementation and local proof
are complete on codex/c03-item-inspector cddeff02. The
[delivery review](../evidence/c03-2-delivery-review.json) and
[reporter](../evidence/c03-2-final-reporter.json) retain actual tested revisions
and source-equivalence evidence. External publication/merge remains pending.
The inspector is integrated into local C04; this does not transfer all native
proof to a changed C04 APK. F07.33 remains owned by C06 as originally scoped.

No C03.2 implementation/reverification task is active. Reopen only for a specific
relevant change or finding. [STATUS](../STATUS.md) owns authorization and the
next action; ROADMAP records verified-local, not externally delivered.

## Historical scope, work and receipts

Original acceptance scope below is retained. Historical "current", "active",
"next" and incomplete-build notices are superseded by the disposition above.


Selected2026-10-03 after delivered C02, base `b88713b3`, branch
`codex/c03-targeting-attributes`. Live default/open PRs checked; no open PR or
active verification remains. Preserve the full F07 inventory and serialized EOS
architecture. C06 retains F07.33 skill requirements.

Two bounded child outcomes separate fit statistics from dataset-driven item
inspection. These are related parts of the approved C03 milestone, without new
approval gates. C03 remains active until both are delivered and verified.

- **C03.1 targeting/navigation and cargo details:** all F07.01–F07.30 together.
  Maximum targets/range, scan resolution and every original reference lock time,
  sensor type/strength/jam chance, drone control range, speed, alignment/mass/
  agility, signature/probe size, warp distance/core strength and all21 special
  holds. Preserve original aggregate and formatting; absence stays explicit.
  Use original EOS and unchanged pinned targetingMiscViewMinimal as the oracle.
  Cover representative hull/sensor/hold families, actual module/skill/modifier
  changes, cargo detail refresh, history/copy/GC, activity recreation and process
  restart. Match raw values/types, units, display and exact detail; reject malformed
  results, incorrect fixture hashes and changed fixture content. Native controls,
  screenshots, every inherited local gate and A10 remain required.
- **C03.2 complete ship/item/charge inspection:** F07.31–F07.32 and F07.34–F07.48
  together. Grouped current/base/raw attributes, description/traits, affectors,
  variations, effects/properties and every equipment detail family, refreshed
  after edits. Enumerate the pinned dataset's supported attributes/effects rather
  than sampling away members. Record its concrete matrix before implementation.
  Search, precise units, copyable text and native/offline detail behavior are
  required; later CSV/skills/price-refresh owners retain their dependencies.

Current implementation scope: C03.2; C03.1 is delivered. Complete the independent
inspector matrices, bridge/UI and native/regression checks before stable full
delivery verification. Group corrections before expensive checks and reuse proof
only when its inputs and prerequisites remain valid. Delivered C02/C03.1 stay closed.

## C03.1 implementation and focused readiness

Serialized EOS supplies the typed read-only targeting query; Compose exposes ten
main fields, precise nested details, every hold and all eight reference locks.
Details survive revision refresh and activity recreation. Numeric zero remains
the actual EOS result for absent holds; an explicit presence flag gives the
original tooltip's distinction without inventing a capacity or null result.

Two fresh unchanged pinned wx/EOS exports agree for53 cases. An exhaustive437-hull
inventory finds14 positive hold types and7 absent types. The matrix covers all
five sensor families, zero skills, module states, eight skill edits, cargo and
three linked electronic-warfare effects. Host matrix/read-only/GC, history,
copy isolation and fresh-process restart pass with the unchanged database.
The current fixture SHA256 is
`415bb29a328b0823da1c7ca0519646b505698edadeaebea2db6993ef0081f7a6`.
Focused evidence is retained externally in
`c03-targeting-reference-presence-20261003-1315` and
`c03-targeting-host-presence-20261003-1324`.

Sixteen focused validator tests pass, including all-field/type/unit/display and
member rejection, exact packaged hashes and CRLF-to-LF-only fixture equality.
Twenty-six inherited integration checks pass after adding the new persistent
runner flag to their expected set;7 history,7 resource and8 profile reuse guards
still reject unrelated source differences. Historical guards evaluate their
original delivered boundaries, not a weaker production reuse rule.

Source review confirms EOS formulas and original wx presentation, serialized
queries, revision identity, immutable strict DTOs, preserved inherited graph
metadata and process boundaries. No mutation, tolerance, timeout or performance
requirement is relaxed. No production exact-source exception was extended.

Preserved development failures: the initial oracle used an obsolete ECM item
name (corrected to the actual pinned Multispectral ECM II); two validator tests
assumed absent holds were null instead of EOS zero; one integration expectation
omitted the new runner flag. Corrected focused checks pass. Earlier exports and
build evidence remain historical, with their actual inputs, not relabelled.

Both updated APKs compile and lint passes (`build/c03-focused-build-final.log`);
engine staging includes the current presence-aware fixture. `git diff --check`
passes. Native execution and visual review are still outstanding.

Next: commit the coherent candidate, run the new
native pair and its actual-report summary against a verified268-fit C02 synthetic
baseline on a fresh offline AVD. This focused proof does not replace delivery.
After readiness and visual review, full delivery requires all115 gates,75 native
executions,325 persisted fits and215 reviewed screenshots on the final revision.

The first focused Android prepare attempt on `c4233aa5` hit its900-second
deadline. Run `c03-targeting-focused-20261003-135257` retains its APKs, raw log,
logcat and partial store (SHA256
`a54c65e2352ec138779bf874a3f5ec69bd835fdaf86df95359784233ee71221c`).
The store reached311 fits and case42's undo revision3; successive three-GC groups
continued through14:08:24. History replay rebuilds the whole retained graph;
this is progressing execution, not proof of a hung case. It is a failed attempt,
not partial delivery success. The earlier private seed helper's Windows manifest
separator lookup failure is also retained, with exact hash/size checks unchanged.

Preparation is now bounded at cases0–32,33–44 and45–52, followed by the original
full restored verification. All53 cases and every edit/undo/redo/GC/copy/UI
assertion remain; each stage still has900 seconds and existing operation limits.
UI undo/redo executes in the first stage while that history exists, and later
stages retain its original exact proof. Additional restart checks compare the
typed incoming graph/snapshots and prior observations; every inherited fit remains
unchanged. Native progress logs record each case's start, pass and elapsed time.
No product implementation, fixture, calculation, timeout or A10 criterion changed.
The staged validators (16 tests, including26 corruption subcases) and26 inherited
integration tests pass. The first staged-validator attempt is retained: its
"recent" corruption targeted a pre-cargo stage whose empty list was already
correct; it now targets the actual cargo stage. Typed previous graphs are validated
once before comparison, preserving every member/type check without repeated
revalidation. Both APKs build and lint passes (`build/c03-staged-build.log`).

Focused native run `c03-targeting-focused-20261003-141846` on `f739cbbd` passed
all four stages in604.188/545.235/724.516/49.766 seconds. The original900-second
deadlines and every assertion pass;325 fits (268 inherited) survive all boundaries.
All24 required targeting screenshots are visually reviewed against their hashes.

Its first summary failed because it expected only the named lowered skill.
Original EOS strict skill levels also record exact dependent skills as `None`.
The original failure, full logs, reports, APKs, screenshots and store are retained.
Two fresh pinned desktop EOS processes independently export all53 complete input
maps in the host-side companion `targeting-skill-inputs.json` (SHA256
`ea880615dc7ba080d15440c8eedd51d144e25a24ddff5b5f8ac5adfee425face`).
The witness binds the complete original specs/edits, source/settings/dataset,
normalized original targeting fixture hash and original character source hash.
Summary checks require those exact maps, including every null, and retain all
manifest/report, type and restart comparisons. Full reference verification now
repeats this companion export. It is expected-input proof, not Android test data;
the original packaged targeting fixture and every reported hash are unchanged.

The summary-only retry passes without any Android rerun and verifies all retained
native inputs remain byte-identical. Sixteen focused validator tests (29 corruption
subcases),37 actual-report corruptions and18 native protocol guards pass. Missing
dependents, null-to-zero changes and arbitrary extra null skills are rejected.
Source review confirms a summary/input-oracle correction only; product code,
APKs, native assertions, tolerances, timeouts and A10 requirements are unchanged.
Current next: commit the reviewed correction and start full115-gate delivery proof.

Full run `20261003-150233-9badd3ec-e6ca98` on `9badd3ec` passed58 gates through
headless capacitor. Defense calculations and restart passed; its22-test validator
then failed only the persistent-flag set expectation, missing `c031_phase`.
This original failure and logs remain. The repair adds that exact literal while
keeping every historical flag and the storage-preservation assertions.
Twenty-two defense validators and10 focused reuse guards pass. The existing
launcher/reporter reuse path admits only that complete exact-source replacement
at this58-gate boundary; unrelated test/native/engine/fixture differences fail.
Executed plan/host/build/execute function bodies and every completed input remain
identical. No new framework, fixture, numerical assertion or timeout changes.
Next: commit the repair, resume only the failed gate and remaining dependants,
and preserve all58 passing results. Full native/build delivery proof is outstanding.

## C03.1.1 — keyboard viewport repair (selected2026-10-04)

Parent C03.1 remains active. Screenshot review of the current full run found
`charge-edits-active.png` draws the scrolled Recent edits heading under status
icons while the software keyboard is open. Numerical/native charge tests passed;
this is a failed visual acceptance result, recorded by exact hash in the run's
`keyboard-visual-failure.json`. The run paused cleanly after variations with78
passing gates. Preserve all previous failures and original requirements.

Bounded scope: activity IME resize, consume Scaffold insets, keyboard-aware
viewport padding/clipping; a test tag and native geometry assertions against
actual system/IME insets. Retain all existing charge matrix, compatibility,
rejection, recreation, copy and restart assertions. No fitting calculations,
fixtures, storage behavior, numerical tolerance or existing timeout changes.
Acceptance: focused offline native keyboard/search/recreation/back proof and
actual screenshot review; both APKs/lint/package; complete stable-candidate full
verification and all215 existing required screenshots before parent delivery.
Use the existing test framework and local launcher. Android's official
[edge-to-edge setup](https://developer.android.com/develop/ui/compose/system/setup-e2e)
and [inset consumption](https://developer.android.com/develop/ui/compose/system/insets-ui)
provide the platform handling, without dependency or infrastructure changes.

Focused keyboard proof `c031-keyboard-focused-20261004-042420` on `e2005c92`
passes offline ephemeral storage, query retention, recreation and dismissal.
All3 original screenshots are hash-verified and visually reviewed. Open/recreated
viewport top63/bottom1048 and input top880/bottom1048 stay inside actual1920px
window/status63/IME872 bounds; closed viewport bottom1857 with IME0. Five strict
geometry validator tests pass. Both APKs/lint/signature/package pass. Earlier
catalog-readiness, boot-service and transfer failures retain their logs/images.
Disk exhaustion was resolved by deleting only stopped owned disposable probe
AVDs while retaining captured evidence; original screenshots unavailable after
one failed transfer are not represented as recovered or approved.

Historical full run `20261003-150233-9badd3ec-e6ca98` preserves interrupted
cargo prerequisite failures (actual66 versus required57; original interrupted
store unavailable), native restarts and the System UI/IME failure. Its exact10-fit
store remains in `library-ime-failure/partial-graph.sqlite3`, SHA256
`88a12f9f65cd1843986546114e78e452cc84b377654e651b43758a3a803af039`.
The original9 IDs/revisions match prior B02 proof. Temporary tracked checkpoint
editing also hit the clean-tree guard; restoring the exact tree allowed resume.
The final historical run paused after78 gates for the actual visual defect.

## C03.1.2 — validator metadata indexing (selected2026-10-04)

Fresh full run `20261004-042857-bfbbe157-2dd1cc` passed61 gates through host output.
All desktop references, original targeting/skill-input exports and host regression
matrices passed. Targeting prepare/restored engine processes completed; its
16-test summary validator subprocess then exceeded the unchanged60-second limit.
The raw failure and partial host artifacts remain in that run. No native/build
gate has executed there and no full success is claimed.

Bounded scope: profile and index repeated inherited numeric-metadata prefix
lookups while preserving every existing comparison. No application, engine,
fixture, tolerance, restart boundary or deadline changes. Acceptance requires
prefix-filter equivalence (including overlapping IDs and boundary characters),
all16 original tests/29 corruption subcases within the existing60 seconds, and
the full delivery suite/215 screenshot review. Keep completed61-gate inputs exact;
reuse only through the installed launcher/reporter's narrowly proven source seam.
The failed targeting gate and all remaining prerequisites must execute after repair.

Retained diagnostic profiles show one complete synthetic summary spent12.458 of
13.683 seconds in6,432 metadata filters/30,089,983 prefix calls. The equivalent
prefix trie takes1.606 seconds for the same full summary; all582,166 exact-value
calls and19 typed-wrapper validations remain. The new boundary/overlapping-ID
regression compares every indexed subset to the original filter directly.
All16 original tests and29 corruption subcases plus that regression pass as17
tests in21.215 seconds (21.532 subprocess seconds), inside the unchanged60 seconds.
Twelve source-reuse guards reject removed assertions/corruptions, weaker prefix
boundaries, changed deadlines/fixtures/engine/app, missing gates, executed failed
gate reuse and a different baseline. Application/APKs, fixtures, numerical
tolerances, native900-second deadlines and A10 checks are unchanged.
Full proof and215 screenshot review remain outstanding.

## C03.1.3 — keyboard-ready charge selection (selected2026-10-04)

Full candidate `9272c2a5` passed76 gates through native module editing. Charge
prepare then failed its existing `charge-item-29001` visibility assertion after
filtering Tracking Speed Script with the IME opening. The retained actual image
shows the search field at the keyboard edge and the result below the viewport;
the fixed status-bar boundary is clear. This suggests a platform resize/scroll
timing race; a focused reproduction must establish the correction.

The exact failed9-fit store is retained in the full run's
`charge-keyboard-failure/partial-graph.sqlite3`, SHA256
`3da2ad960d331403d7a51f94b1e690ee15435b273c7331da47f2007a586a2f6b`.
Its original8 IDs/revisions match the preceding module report. Main run state
was preserved during diagnostic extraction; original instrumentation and image
hashes are bound in `charge-keyboard-failure/receipt.json`.

Bounded outcome: synchronize actual keyboard/layout readiness before scrolling
to a filtered charge, and extend the existing ephemeral probe to assert/select/
load that script with the IME open. Keep original visibility, numerical, restart,
geometry and persistence assertions, tolerances and deadlines. Acceptance requires
focused offline native proof and reviewed screenshots, then the complete stable
delivery suite. Previous native results remain historical if the test APK changes;
reuse unchanged host inputs only with exact source/prerequisite proof.

First focused candidate `9564f0ca` passes all5 build/package checks. Its first
probe attempt stopped before instrumentation on the emulator's12GB free-space
prerequisite; stopped owned no-snapshot RAM files were removed with receipts,
preserving userdata/evidence. The next probe passed its existing geometry,
recreation and dismissal assertions, then exposed an incorrect added navigation
step: the equipment charge picker returns directly home, not to equipment.
Remove that extra step before retrying; filtered-script proof remains pending.

Corrected candidate `db59358a` also passes all5 build/package gates. Its probe
displayed/selected/loaded Tracking Speed Script, then failed a new assertion that
incorrectly assumed the options list contained only fitted modules. The bridge
also exposes vacant rack slots. Check the exact target index0 instead; the
selected module's charge must still equal29001. Use the original full test's
selection helper in the probe and retain its filtered-result screenshot through
an observation callback, so the focused proof exercises that exact interaction.
The original full-test assertions and numerical matrix remain intact.

The existing explicit native-restart/reporter path gains a narrowly pinned source
proof for the exact ChargeEditingTest repair. It retains only62 unchanged host/
reference gates, validates their original log hashes and composes the existing
`bfbbe157`→`9272c2a5` metadata proof separately. All older build/native results are
archived; every native gate requires the new test APK and a fresh store. If all5
build gates already passed for the exact new commit, their actual logs and APKs
are imported with their original execution stamps and validated source manifest.
Otherwise the installed build gates execute normally. No hosted job, service,
SDK/tool setup or required assertion/tolerance/deadline changes.

Seventeen focused source/build-provenance regressions reject other engine/app/
fixture changes, altered assertions/deadlines, wrong/incomplete/failed build
proof, corrupted logs/APKs/manifests and changed gate order. Constructor/import
tests preserve older commit stamps and require all fresh native gates. Twenty-two
reporter and8 inherited output-reuse regressions also pass. Actual native proof
and full screenshot review remain pending. The platform idle wait shares the
existing10-second bound, following [UiAutomation's documented global timeout](https://developer.android.com/reference/android/app/UiAutomation#waitForIdle(long,%20long)).

## C03.1.3.1 — evidence-list ownership (selected2026-10-04)

Stable `c85a20a3` passes all5 build/package gates,47 retained source/reporter
regressions and the focused offline keyboard/filter/select/load probe. All5 actual
screenshots are hash-verified and reviewed in
`c031-keyboard-focused-20261004-062405/screenshot-review.json`. The installed full
restart imports62 host/reference and5 same-commit build gates, then passes the5
native initial tests. A separate post-restart provenance validator rejects its
metadata: the completed and retained-host lists share an object, so importing
build gates extends both. Requested pause completes cleanly after initial at68.
No full pass or passing status has been published.

Bounded correction: give the completed list independent ownership; retain exactly
the original62 host gates, and add a constructor/import integration regression.
Restore only that metadata from the immutable archived76-gate prior run. Prove
the exact CI-only source pair and unchanged app/test APKs, retain all valid logs,
initial native proof and store, and adopt through the existing explicit launcher
seam. Every remaining native gate, screenshot and performance requirement still
must execute. Acceptance includes actual post-adoption provenance validation,
source-mutation rejection checks and the complete full delivery suite.

Implemented independent completed-list ownership and a regression that appends a
build gate after construction and requires the recorded host list to stay62.
Six additional alias-adoption regressions pin the exact launcher source pair,
reject any Android/test/fixture/native-gate changes or altered list copy, and
preserve the original paused snapshot/completed inputs. The existing explicit
AdoptLauncherFix seam accepts only this exact paused68-gate source/proof pair;
it derives the corrected62 entries from the immutable archived76-gate run and
retains every actual execution stamp, original snapshot, APK and store. All
remaining native gates are still required.23 source/provenance,22 reporter and8
inherited reuse regressions pass. Actual post-adoption validation remains next.

## C03.1 final verification and review — 2026-10-04

The preceding pending statements describe retained development checkpoints.
Candidate `f462a1e7b7ed179484a7b19a17e003d2b204ef10` now passes the complete local
run `20261004-042857-bfbbe157-2dd1cc`: all115 gates,75 required native executions,
325 saved fits with268 inherited fits intact,215 reviewed screenshots and37
rejections of corruptions to the four actual targeting reports. The
[receipt](../evidence/c03-1-native.json) binds raw logs, APKs, reports, screenshot
hashes/observations and every exact-source reuse prerequisite. No hosted workflow
was dispatched or labelled passing. Fork PR delivery remains the next step;
C03 remains active until complete inspector child C03.2 is also delivered.

All62 reference/host and5 build gates pass. The unchanged pinned wx/EOS oracle
supplies53 cases and complete437-hull hold enumeration. Native proof preserves
every original value/type/unit/display/detail comparison, module/skill/cargo/
projection change, edit/undo/redo/GC/copy witness and prior-stage graph. All three
targeting preparations and the final restored process pass with their original
900-second bounds. Every inherited offline, restart, numerical and A10 gate also
passes; the recorded Windows history bound remains unchanged.

The charge-test synchronization shares its original ten-second deadline with
platform layout idleness. The original compatibility/state/copy/restart matrix
passes on the completed full run. The focused `c85a20a3` probe actually filters,
selects and loads Tracking Speed Script29001 through that same selection helper;
all five transfer-verified images were reviewed. Its one native call is separate
from the required75. CI independent-list ownership passes53 focused regressions
and real post-adoption provenance validation. Host/build inputs retain their
actual tested commits; no older Android result is relabelled as current.

An initial full-run `fit.png` transfer was truncated. Its original bytes are
retained in `initial-png-recovery/fit-truncated.png`. The unchanged existing
offline shell UI test ran in separate ephemeral storage against matching APKs:
the first UI pass had a failed artifact transfer; after diagnosed transport
recovery the UI passed again. Source-before/source-after/local SHA256 checks and
full PNG decoding establish the recovered image, then full-size review confirms
the visible controls and statistics. Only that image was replaced; the full run
and325-fit store were untouched. Both successful supplementary UI calls and the
failed transfer/logs remain explicitly recorded. Delivery has78 successful native
calls overall:75 required,1 focused and2 supplementary, with no inflated gate count.

Final source review confirms EOS worker ownership, serialized execution and
fit/revision identity checks. Generation tokens discard obsolete loads; the view
renders only current matching results and retains expanded details per fit.
Strict immutable decoding requires complete ordered eight-lock/21-hold families,
correct units and numeric kinds, finite values and consistent availability.
Warp-core strength retains its signed original value; hold absence is explicit
while precise zero remains the actual EOS result. No Kotlin fitting formula,
engine/fixture change, tolerance or performance relaxation is introduced.

All production images are legible within system/keyboard boundaries. Three
inherited resource-probe images have low-contrast status-bar icons because
ResourceProbeTest replaces content with a default light MaterialTheme; the
production activity uses the explicit dark scheme. Their statistics/details are
readable and native assertions pass. This test-content limitation is recorded
in individual review observations; it is not an unrecorded product correction.
API36 x86_64 runtime and ARM64 package inspection do not establish ARM64 runtime,
older APIs, signing/upgrade or user usability. Full feature parity stays open.

## C03.2 — complete offline inspector (selected2026-10-04)

C03.1 delivered in [PR #41](https://github.com/Sussic/Pyfa-android/pull/41), merge
`745fc1e2cbc0127d69a3b228243a9a49ff303786`, after source review, exact-head passing
`local/full-verification` and all recorded acceptance proof. C03.2 is now eligible
and selected on `codex/c03-item-inspector` from that live default; no open PR.

Scope remains all F07.31–F07.32 and F07.34–F07.48 together: current/base/raw ship,
fitted/base-item and loaded-charge attributes; description/traits/copy, affectors,
variation comparisons, effects/properties and every equipment detail family.
F07.33 recursive skill editing/navigation stays with C06. CSV export and optional
price refresh retain their later owners; unavailable cached prices must be honest.

Before implementation, enumerate complete attribute/effect IDs at the pinned
dataset and every original supported detail branch, not selected examples. Record
the source-to-field/unit/mode matrix and concrete numerical cases. Use original
EOS calculations, the existing serialized bridge and native Compose inspection;
do not approximate formulas in Kotlin or introduce a separate engine/infrastructure.

Acceptance must compare independently pinned desktop current/base/raw results,
all enumerated members and equipment families, affectors/stacking/unused states,
variations and effect/property metadata. Native checks cover offline navigation,
search/copy/detail expansion, edit/reversal refresh, malformed results, recreation
and fresh-process restart without corrupting saved fits. Focused implementation
checks precede one stable full candidate with all inherited gates, screenshots
and A10 requirements. Exact next: inspect item-stat tabs and equipment columns,
enumerate the complete dataset and write that matrix before coding.

### C03.2 development checkpoint — 2026-10-04

The [complete acceptance matrix](C03-2-inspector-matrix.md) was recorded before
implementation. The independent pinned exporter enumerates2860 attributes,
3419 effects,60 units,1590 groups and114 terminal equipment paths, including all
nested command-burst conditions. Metadata enumeration is not runtime path proof.

Worker-owned inspection now resolves current fitted/base/charge identities,
returns grouped current/effective-base/raw attributes and original unit formatting,
and exposes effects, affectors, supported properties, variation metadata and
equipment presentation. Base-item inspection also works without an active fit.
Original equipment/comparison/grouping bodies are isolated without desktop imports;
service fit lookups use the worker fit and numeric metadata lookups preserve the
original service integer coercions. No Kotlin fitting formula is introduced.

Actually executed focused checks: independent pinned wx/EOS export for24 Vexor,
module, charge, drone and base targets; separate headless comparison passes1149
ordered normal/raw rows. Three AST regression checks preserve all isolated original
equipment methods, comparison formatting and grouping statements. A private EOS
smoke exercised Vexor/module/charge query serialization. Raw `cloaked=False` retains
its actual boolean type. `git diff --check` passes at this checkpoint.

The same24 independent targets now also compare unchanged original misc/range/
capacitor equipment columns. Initial comparison exposed missing reference ORM
owner relationships; the exporter now adds/flushes the original fit before EOS
calculation, matching desktop ownership. The corrected independent export and
separate comparison pass all1149 rows and applicable original columns. Reference
imports are confined to the clean pinned checkout and exclude the adapter.

The expanded schema2 fixture now covers133 independent original fits and612
inspection targets, retaining all58165 ordered normal/raw rows plus precise
current/effective-base values, numeric/boolean kinds, metadata IDs and units.
Equipment comparisons execute unchanged pinned misc/range/capacitor methods.
Family selection derives actual group/effect dispatch from the original source
and checks legal hulls across the complete437-hull catalogue; only the booster
addition still needs its own fitted construction. Seven families have no published
market items in this dataset; their original paths remain required synthetic/raw
legacy probes, not silently removed acceptance criteria. All command charges and
affector/effect/property/variation details still require their complete matrices.

The broader comparison caught a raw-only Sizeclass=0 value being formatted despite
normal-mode suppression. Raw values are now retained without that invalid normal
conversion. Cargo keeps its actual modified-attribute container/stack properties;
volume and total volume follow the original Python presentation. Legitimate infinite
diagnostic property values use explicit signed-infinity metadata, not invalid JSON
numbers or fabricated zero. A full-payload smoke passes133 cases/307 fitted plus
matching base targets, with desktop imports blocked and finite JSON serialization.

The immutable native decoder and serialized worker APIs are implemented and
`:app:compileDebugKotlin --offline --no-daemon` passes, including the final API
revision. This is focused Kotlin compilation using existing staged inputs, not an
updated packaged engine/native runtime/full verification result. Native UI,
decoding regressions, offline recreation/restart, full gates and screenshots are
still required. No C03.2 delivery or feature-row completion is claimed.

Subsequent focused expansion passes152 independent cases/726 targets/67501
ordered rows with precise values/types/units and original equipment columns,
including all19 published command-burst charges. Full-payload smoke now passes364
fitted and corresponding base targets with desktop imports blocked. Inspector UI
is connected to the fit screen and equipment browser, including fitted affector
source navigation. Latest UI compilation passes. A canonical native comparison
and read-only graph test is added; final test compilation passes, but native
execution remains pending. Expected
inspector data is staged only into test assets, never production calculations.

Original effects and variation presentation now execute unchanged pinned methods
for all178 unique items in the152-case attribute matrix: complete effect lists,
original variation families/differing columns, and106110 normal/raw cells pass
separate headless comparison. The3 original presentation AST checks pass again.
Build run20261004-104349-3e58ac91-201d6c passes all5 focused package gates at3e58ac91.
Focused native attempt c032-inspection-focused-20261004-104714 failed before any
comparison: the diagnostic runner selected temporary storage, while the read-only
assertion requires persistent storage. The c032 phase now retains persistent
storage and is excluded from the inherited exact5-test initial phase. Corrected
canonical attributes and178-item metadata tests compile; execution remains pending.
The earlier SDK-manager environment omission is retained in failed focused attempt
c032-inspection-focused-20261004-104702; supplying the existing installed path
resolved it without setup changes. No failure is counted as a pass.

All60 unit definitions and289 formatting witnesses now pass the independent
original formatter against the headless adapter, with matching disabled global
query cache, pinned source, complete database digest and EOS settings. The reusable
exporter/fixture retain valid rig classes, Boolean inputs, known/zero catalogue
references and signed/fractional/large values. This is host evidence, not an
additional native unit probe. Corrected package run20261004-105159-aabcd9d5-ddf9dc
passes5 build gates. Native startup run c032-inspection-focused-20261004-105414
failed because the disposable userdata partition required12288MB with9077MB free.
Removing only the stopped failed104714 AVD retained its logs and resolved the
space condition; corrected native run c032-inspection-focused-20261004-105616 is
executing its two assertions. No native pass is claimed before runner validation.

The105616 native run is terminal: both assertions failed on decoder bugs. Original
metadata proves offline/overheat are valid effect types; these are now explicit
accepted enum members, while unknown types remain rejected. Matching source-target
item IDs now normalize both integer representations before comparison; the exact
identity assertion is retained. No assertion or tolerance is removed. Correction
compilation passes, including added native regressions for malformed scalar/raw
values, identities, enum members, missing raw rows, duplicated effects and duplicate
JSON fields. Package and native rerun remain pending.

Packagee40bcad5 passes all5 gates in20261004-110150-e40bcad5-ce4b11. Its corrected
focused native run c032-inspection-focused-20261004-110459 passes both assertions
(44.57s reported runner time), including canonical attributes/equipment,178 full
base effects/variation families, malformed guards and unchanged saved graph. This
is bounded development proof, not a full/native UI/restart/performance pass.

Current source now isolates unchanged original formatOperator/sortAttrDisplayName/
buildAttributeView/buildModuleView bodies. The native tree retains original grouped
counts, duplicate suppression, projected roots, ordering, alternate attribute names
and penalized/resisted modifier presentation; raw unused/unchanged entries remain
available separately. Source inspection still follows fitted targets when known.
The independent original recorder passes152 cases/16975 complete tree rows against
the headless worker;4 source AST tests pass. The verifier's first attempt imported
saved-data classes before engine initialization and failed; moving that import
after the established HeadlessEngine boundary resolved it without production EOS
changes. Updated NoDesktop full payloads pass364 fitted plus matching base targets.
Updated UI, immutable tree decoder and canonical tree tests compile; current tree
packaging/native execution and linked/edit coverage remain pending.

Independent property proof now executes unchanged pinned ItemProperties.PopulateList
getters for152 cases:57216 complete members/28726 supported values pass separate
headless comparison with the matching synthetic character name. Exact portable
primitive display, including None/False/zero and signed infinity, is preserved;
structured values retain typed members and unsupported diagnostics are explicit.
Only SQLAlchemy association-proxy cache-name process addresses are normalized,
retaining the member and rejecting collisions. Initial oracle failures from proxy
name collision, address-bearing cache names and title-colliding getter labels were
corrected without removing rows or weakening comparisons. Two focused regressions,
four original-source AST checks and152-case/364-target NoDesktop full payloads pass.
Updated UI/strict decoder/malformed guards compile in the local Android test build.
These are host/compilation checks; no new native runtime proof is claimed. Native
fitted-property comparisons must map operational saved-data IDs independently from
graph roles while preserving exact catalogue identities; do not skip those fields.

Linked inspector references now extend the original A04/A05 exporters using an
optional observer; their default output path is unchanged. Complete original
source/attribute trees, precise/normal/raw attributes and equipment columns pass
separate NoDesktop verification through all11 projection states (5586 tree rows,
18997 ordered attribute rows) and19 command states (10454/34561). Original fitting
snapshots and restoration assertions are retained. Inputs include range/falloff,
script changes, source skills/mindlink, module/link activity and repeated removal/
reapplication. Exact state inventories reject missing or extra phases. The first
extended attribute export failed because extracting only the observer released
its wx.App; retaining the original oracle object fixed the lifetime. Corrected
complete fixtures pass; earlier tree-only passes are not full attribute evidence.
Native linked inspection, source navigation and history/restart remain pending.

Equipment return tracing now records unchanged original methods without editing
their bodies. All152 cases pass original/Android value and executed-return identity
comparisons across raw/EHP probes;52 of the114 inventory returns are witnessed.
The retained fixture lists all62 outstanding returns explicitly, including the4
configurable attribute/property column returns outside the current5-method adapter.
Seven published legacy families are absent: ECCM, Fighter Bomber, Fighter Drone,
Gang Coordinator, Projected ECCM, Sensor Backup Array and Ship Modifiers. Booster
Quafe Zero Classic remains an addition-specific case. No catalogue coverage claim
substitutes for these missing witnesses. Initial export failed on a relative SQLite
URI; resolving the read-only path fixed it. Six original-AST/property regressions
pass. No production calculation or model changes were needed for tracing.

Independent booster/legacy/conditional probes now pass unchanged original methods
against the headless adapter. All311 published boosters retain exact duration and
metadata units in active/inactive states;35 explicit synthetic inputs cover all7
absent published legacy families without introducing production catalogue types.
The58 conditional probes retain absent/zero/nonzero behavior, slot modifiers,
assault duration, mining zero-drain, charge/probe detail and all5 ancillary/capacitor
groups with raw/EHP, charged multipliers, reload and uncharged remote fallback.
Unexpected exceptions fail the comparison. Original ECM with missing strengths
raises TypeError before its None guard; its exact declared exception is retained
and contributes no return hit. Combined fixture coverage is103/114, with11 explicit
gaps:4 mode/no-fit returns,4 configurable column returns and3 original guards.
These remain open for domain/source analysis; no required path is deleted or
counted as exercised without execution. Six original-AST/property regressions pass.
This extends host proof only; native booster/legacy/conditional execution remains
pending along with source/UI/history/restart verification.

The original configurable AttributeDisplay/PropertyDisplay bodies are now isolated
unchanged in the worker presentation module and protected by the existing source
AST check. Worker volume/stack display calls the original attribute formatter;
full inspection still retains explicit absent/zero values where a compact column
would be blank. The extended fixture passes97 configured CPU/power/volume/arbitrary
attribute/property and mode/no-selected-fit witnesses, including fitted/base/direct
lookups, missing/zero/false, signed/large values and stack quantities0/1/5. Eight
worker stack cases independently compare original nonzero formatting plus precise
volume/total and absent/zero distinctions. All6 original-AST/property regressions
and152-case/364-fitted-plus-base NoDesktop full payloads pass. The four mode/no-fit
and four configurable return gaps are closed by execution; combined coverage is
111/114. Original ECM return40 and electronic-drone return62/64 remain unwitnessed
pending explicit source/numeric-domain analysis. No return is removed or falsely
counted. New Python helpers are not yet packaged or executed natively.

The3 original guards now retain exact source/algebra classifications plus2793
independent original-method domain witnesses:1572 outputs and1221 explicit original
missing-value exceptions match the headless code. ECM calls max/min before its None
guard; numeric values make the guard false, while missing values raise beforehand.
The two electronic-drone guards follow an entered nonzero branch and strictly
increasing absolute-magnitude selection from zero, so finite values cannot restore
zero. Missing loop values raise beforehand. Source shapes are asserted exactly in
both pinned and isolated methods. Executed coverage remains111/114: no classification
is counted as a runtime hit or deletes an inventory row. The initial proof exporter
failed by treating a lambda expression body as a statement list; restricting block
inspection to lists corrected it without changing any source/domain assertion.

Complete effect reference now passes all3419 definitions, including unassigned
metadata, and3016 assigned IDs across1274 complete actual item lists. The original
PopulateList supplies presentation; metadata and real associations are independently
enumerated from the pinned database. The first catalogue attempt rejected duplicate
names. Two pairs (11058/11062 and6076/12798) now retain every ID in separate explicitly
unowned catalogue layers; SQL confirms no duplicate-name pair coexists on an item.
All1274 full base-inspector payloads pass NoDesktop/finite JSON and exact effect-list
checks. These wider inputs prove boosterSideEffect is a valid original type; the
native codec now accepts it explicitly and rejects unknown runtime strings while
retaining early/normal/late and truthful absence. Unknown-runtime regression and a
third offline native test comparing every assigned ID/item and unchanged saved graph
compile successfully. All8 newer reference fixtures are staged only into test assets
on the next build; staging source changes are not a package or native runtime pass.
Six original-presentation/property regressions pass. Installed verification now
adds25 retained inspector host gates to all115 inherited gates (partial140 total).
Reference gates export twice in fresh independent processes and compare both entire
outputs against the pinned fixture; implementation gates run separately. Logs,
generated files and provenance receipts remain in each local run. Three plan/routing
regressions and23 reporter regressions pass; the publisher rejects the partial plan
until actual inspector native gates are integrated. The combined NoDesktop payload
gate passes152 cases/364 fitted and matching base targets plus1274 catalogue base
payloads and complete effect lists. Reference/implementation guard-domain wrappers
also pass. No complete native/UI/restart or delivery claim follows from these checks.

Native attribute/affector test now iterates every152 independent cases and asserts
726 fitted/base targets, preserving original malformed-payload regressions and
per-case saved-graph comparisons. Fixture input audit confirms no cargo, restriction
override or initial relationship/implant/booster input is omitted; the four
environment and two fighter cases use existing typed construction. Local Kotlin
test compilation passes. At86057359, build20261004-122411-86057359-6797a4 passes
all five local package gates. Focused offline122631 passes all three native tests
in360.218s: all152 cases/726 fitted-base targets,178 complete effects/variation
families and1274 actual item witnesses/3016 assigned effect IDs. API36 x86_64,
airplane mode/INTERNET denial, immutable decoding, malformed-payload regressions
and saved-graph preservation are checked. This supersedes the first-case-only
attribute proof; it does not establish UI, property, linked edit or restart parity.

Independent saved SQL identity graphs now pass152 cases and two fresh original
regenerations. Original raw SQL queries and separate mapped-table reads retain
every ID, module position, catalogue item/charge ID, amount and activity input.
Initial fighter activity mismatch (raw SQLite1 versus mapped BooleanTrue) is
corrected by explicitly retaining SQLite0/1 representation in the diagnostic.
Native property comparison compiles, retaining57216 ordered members and exact
catalogue identities. Only saved fit/module/drone/fighter IDs are translated by
independent table roles; owner fit identity/name and primitive ID displays remain
asserted. The33MB original property fixture streams one case at a time. Runtime
property execution is pending. New identities reference/headless gates bring the
partial installed plan to142 (27 inspector host additions, all115 inherited).
Three plan/routing and23 reporter regressions pass. Installed NoDesktop full
payload gate compares28618 fitted property members and all matching base properties
in152 cases, plus all1274 catalogue payload/effect lists; all pass. Full publisher
still fails closed pending complete native/UI/restart gates. Only the confirmed
stopped disposable122631 AVD was removed; evidence/APKs/setup are retained.

At17715de0, build20261004-124258-17715de0-39e3f9 passes all five package gates.
Focused124510 fails before APK installation/tests: `svc data disable` exits20,
`Can't find service: phone`. Boot completion preceded binder availability. The
private focused launcher now uses the installed full suite's required120s phone
service wait before disabling data; offline assertions and900s test deadline are
retained. Only that confirmed stopped disposable AVD was removed; diagnostics
and APKs remain retained. Native properties are still unexecuted.

Comparison UI had reversed equal-key ties and discarded previous ordering on
column switches. A shared native presentation helper now executes stable sorting
over previous order and reverses the comparator, with source-equivalent0/missing
price treatment, missing attribute sort key0, and Unicode code-point name order.
Every absent display remains explicit. Independent unchanged PopulateList export
records5509 transitions across all178 families plus11 explicitly virtual cached-
price/missing-value/tie/Unicode transitions; virtual inputs modify no game data or
price record. The fourth offline native test uses exactly the UI helper, compares
every ordered ID sequence and unchanged saved graph, and compiles. It is not yet
runtime/UI-control proof. Six original-presentation/property regressions and three
plan/23 reporter regressions pass. Sorting has a reference-only host gate because
its implementation is Kotlin; no host substitute is counted. Partial plan143
(28 added inspector host gates, all115 inherited) still cannot publish full proof.

Initial actual-control UI test now compiles for offline ship entry, original
current/base precision, case-insensitive search, copy, raw mode and retained
selection/search/expanded detail across activity recreation. It is isolated from
the inherited five-test launch. Three preservation/routing regressions pass after
the exclusion update; no inherited phase/assertion changed. UI runtime and the
rest of the full matrix remain unverified. Current packaged8bb69dde four-test
transport/property/sorting run is live; it uses immutable APKs from that exact
commit and does not contain the newly compiled UI test.

At8bb69dde, focused125821 passes all four native tests in343.892s on verified
build20261004-125607-8bb69dde-4f448b APKs:152 cases/726 targets,57216 property
members,178 effect/variation families,1274 actual effect witnesses/3016 assigned
IDs and5520 original sort transitions. Saved SQL identities are translated only
through independent roles; every catalogue ID and primitive display stays exact.
Offline, immutable decoding, malformed payloads and unchanged saved graph pass.
The binder readiness correction retains all assertions. This supersedes unexecuted
property/sorting status, but remains transport/helper proof rather than UI/restart.

Real original wx HTML windows now export178 description/traits pairs and six
explicit absence/markup/paragraph/Unicode probes; two fresh complete exports match.
Native transport/text and search/copy/recreation tests compile. Plain copy uses
native HTML parsing, preserving every word, Unicode and paragraph boundary. The
comparison explicitly normalizes outer layout padding, CRLF and runs of empty
layout lines to one newline; it never joins separate paragraphs or removes text.
Original ToText has no textual image cells, so native object-replacement cells
are omitted. Raw description/traits bytes remain compared separately to original
database values. UI tests stage three screenshots for later actual review. No
text/UI runtime or screenshot-review pass is claimed. Partial plan144 retains
all115 inherited gates and adds29 host gates; text/sorting have independent
reference plus native implementation checks, with no fabricated Python substitute.
Three preservation/routing and23 reporter regressions pass. Full publisher remains
fail-closed until the complete inspector native/UI/restart gates are integrated.

Focused UI131443 stops before installation/tests: emulator reports available
12280.38MB, required12288MB to create userdata. Storage requirement is unchanged.
Verified identical APK copies from completed122631/125821 runs are deduplicated
with explicit parent/hash/size references; original build APKs/manifests and all
test/failure logs remain retained. The UI focuser uses verified parent APKs directly.
No UI test or screenshot pass occurred. Native text now removes actual ImageSpan
cells only, preserving literal U+FFFC Unicode; a seventh original window probe
and two fresh full text exports pass, and370-field native comparison compiles.

Native e0e48260 package20261004-131957 passes all five gates. Focused offline
UI132212 passes both actual tests in66.765s:178 description/trait pairs plus seven
probes (370 fields), original raw bytes, ship search/current/base/full-precision
clipboard, activity recreation and unchanged saved graph. This supersedes the
unexecuted text/UI status above. All three captured screenshots were inspected:
ship and raw detail are readable; recreation retains the correct values but a
temporary Android clipboard overlay obscures its lower portion. Capture timing
now waits for that system preview before recreation; corrected screenshots require
another execution with the next stable UI coverage batch.

Still unverified: all-tab UI, linked changes/reversal, full malformed-report
coverage, fresh-process restart, final full native/performance gates and complete
screenshots. No C03.2 PR or delivery claim exists. Exact next: finish UI/linked/
restart coverage and complete final verification/review/delivery.

Expanded105177a6 build132813 passes all five gates, but UI132957 fails the
effect-detail assertion after the expand-control tap. The original text test
passes; the entire focused run is correctly failed despite adb returning zero.
No revised screenshot pass is claimed. Retained failure logcat and before/after
Compose semantics diagnostics will determine expansion state/input timing before
any product correction or acceptance change.

Diagnostic69238648 build133347 passes all five gates; offline UI133533 passes
both tests in66.388s, including description/trait copy, effect search/detail and
comparison sort controls. Actual before/after unmerged semantics show effect2188
appearing after its tap; the earlier failure is intermittent, not reproduced with
the diagnostic timing. Tests now settle the IME and wait up to10s for the detail
after one tap, retaining the exact detail assertion without retrying a tap.
All three current screenshots were reviewed: readable ship/raw/recreated views,
with clipboard overlay absent. This closes only those focused screenshot cases.
New real property controls compare original commandBonus zero, modeItems None,
and callable unavailability/reason/copy; module0 pagination traverses every original
123-member page forward and backward. The large original property fixture streams
one independent case with source/dataset assertions. Kotlin compile and diffcheck
pass; runtime for this new batch and the remaining matrix remain unverified.

Atff361b68 build133949 passes all five gates and offline UI134140 passes both
tests in90.431s. Actual property zero/None/unavailable/copy, all five module pages
forward/backward and endpoint-disabled controls pass; effect detail remains exact
with the bounded synchronization. Next batch compares every rendered ship affector
label with the independent flattened source/attribute trees in friendly/internal
modes, adds unchanged-data UI tags, and checks original module misc/range/capacitor
display/detail plus CPU/power/volume current/base and loaded-charge damage values.
Six screenshots are configured. This batch compiles and diffcheck passes; actual
runtime, screenshot review and remaining linked/restart/full proof are pending.

At838fda0c build134836 passes all five gates and offline UI135046 passes both
tests in117.369s. Every rendered ship affector label matches original source/
attribute trees in friendly/internal modes; module equipment display/detail,
CPU/power/volume current/base and loaded-charge damage controls pass, preserving
the saved graph. Six screenshots were inspected. Ship/raw/recreation/equipment/
charge are readable; affector controls are readable but expanded rows fall below
the captured viewport. The capture now scrolls further without altering data.

The existing serialized-worker diagnostic boundary now accepts only unit-input
witnesses and calls the same EOS inspector formatter. Native assertions compare
all60 original unit definitions/289 formatting witnesses, Boolean types and five
malformed inputs, preserving the graph and offline permission requirements. Host
validation passes all289 witnesses/seven malformed inputs plus the complete
152-case/364 fitted+matching-base/1274-item payload/effect/property regression with
desktop imports blocked. Native compilation and diffcheck pass; actual native unit
execution and corrected screenshot review remain pending. No fitting formula or
reference expectation is added to Kotlin or the diagnostic implementation.

Nativee4e30011 build135743 passes all five package gates. Focused140013 passes
the unit method in27.557s (60 definitions/289 formatting witnesses/five malformed
inputs) and both UI tests in69.975s. Offline permissions, Boolean input types and
saved-graph preservation remain asserted. The revised affector image was reviewed:
its source card is reached but a transient clipboard preview obscures lower rows.
Capture now records copy time and waits only for remaining10s preview expiry,
then scrolls1200 pixels to include expanded rows. Compilation/diffcheck pass;
new screenshot execution remains pending. Portable bytecode line mapping was
also checked against actual adapter AST returns:98 misc+3 range text+1 range
tooltip+4 capacitor text+4 capacitor tooltip+2 attribute+2 property =114 exact.
This proves trace portability on the host, not Android equipment-probe execution.
The next batch also adds explicit native NaN/infinity input rejection (seven
malformed unit inputs total). Those new assertions compile; their execution is
pending and does not inherit the five-input native result above.

At3f66d3ef build140837 passes all five gates; focused141049 unit method passes
in25.439s including all seven malformed inputs, and both UI tests pass in79.08s.
All six screenshots were inspected: expanded affector mass/velocity rows are
readable without the clipboard overlay; other five views remain readable.
Source-free recorder prototype and actual serialized-worker diagnostic both
match the complete original152-case/726-target equipment-path fixture:52 executed
real-case paths and all114 definition identities/counts. Previous trace is
restored, desktop imports blocked, and immutable code metadata is cached.
Canonical native assertions now compare every original raw/EHP value and returned
ID plus exact target counts, preserving property/affector/identity/graph checks.
Compilation passes including the final cardinality assertion; native execution
is pending. Remaining probes/guard classifications are
explicitly separate; no52-path proof claims the111/114 complete probe coverage.

Native1a572e60 build142056 passes all five package gates. Focused142310 passes
all five canonical tests in329.897s (launcher337.0s), including152 cases/726
targets/52 actual equipment return paths/all114 definitions, preserving every
prior property/affector/SQL identity/metadata/catalogue/sorting/unit assertion.
The source-free recorder now exposes a reusable traced call with restoration
on exceptions. Input-only DEBUG probes exercise35 legacy/58 conditional inputs,
311 real bundled EOS boosters in both active states and97 configured columns;
actual booster duration unit metadata comes from the bundled database.
Host comparison against the complete original fixture passes, including original
exception text, all values/types/returned IDs and111/114 combined path coverage.
Desktop imports are blocked, tracing and booster membership restored, injected
expectation fields rejected. An initial nonexistent DB getter failed before
booster execution; corrected to existing getAttributeInfo with eager unit loading,
then reran successfully. The full152-case recorder regression also passes after
refactoring. New native worker endpoint/assertions and Kotlin compilation pass;
native probe execution and full delivery remain pending.

Build6e531308 passes all five package gates. Focused143531 stopped before emulator
creation because PYFA_SDKMANAGER was omitted; corrected to installed22.0 path.
Focused143548 then exited before installation: emulator required12288MB and had
12009.17MB. Failed-run logs remain retained; no native assertions executed.
The stopped superseded failed full-run20261002-014149 AVD (2GB) was removed only
after failed-status/commit/path/no-link/CIM owner checks. Logs, APKs and delivered
downstream proof remain retained; paused runs/setup tools were untouched.
Meanwhile the source-free actual guard helper matches all2793 independent cases:
1572 outputs/1221 exact original TypeErrors, previous trace restored, malformed
and injected expectation fields rejected. Native assertions preserve those full
outputs/exceptions and assert the three classified paths never appear as runtime
hits. Both native probe and guard assertions compile. Their combined package/
execution is next; no storage threshold or test timeout changed.

Focusedbd565f66/144052 ran seven tests in780.095s and failed two: the first
unit-test snapshot wait exceeded120s during startup, and equipment-probe setup
unconditionally read an absent ignore_restrictions key. No full native pass is
claimed. The other five methods have successful instrumentation markers,
including the complete2793 guard domains, canonical attributes/properties/path
traces, metadata/catalogue and comparison sorting; complete evidence remains the
earlier1a572e60 suite until a corrected candidate passes. The fixture-key setup
now follows the existing canonical optional-field assertions. Startup timing is
retained and its120s limit unchanged; any recurrence needs investigation.

Host reproduction confirmed a stale module target: removing the first of two
identical railguns resolves its old slot/type tuple to the other object. SQL row
IDs alone also cannot survive EOS graph rebuild. Logical32-hex inspector IDs now
live in weak per-fit/object mappings, are captured in optional inspection_ids
record metadata and restored across rebuild. Public EOS properties remain
unchanged. Saved graphs validate family/value/duplicate identities and restore
exact counts; legacy records receive deterministic IDs in memory, without
rewriting bytes on open. New fitted Android requests require a saved object key;
selection/source navigation retains it and follows moved positions. Removed or
replaced objects reject the prior key. Existing catalogue IDs and positional
reference probes remain distinct.

Actual host repeated-module/reorder/stale-slot/removal/undo-redo/EOS rebuild
checks pass. Two fresh-process restores preserve every ID; two legacy restores
repeat deterministic IDs and preserve saved bytes. An initial history regression
found redo after no-op spare-slot padding restoring2 modules with16 identities.
Replay now trims only IDs whose removed rows are proven empty, preserving all
occupied identity comparisons and existing no-op semantics. Focused padding
passes, followed by all six unchanged history regressions/18 desktop cases/
108 states and fresh-process restore (97.923s), at local165218; prior failures
145452/165004 retained. Native repeated-module assertions compile; execution and
actual control/restart tests remain required. The installed worker-payload gate
now calls actual source-free probe/guard helpers as well as every inherited
canonical assertion. An initial extra probe fit shifted original SQL IDs;
the probe calls were moved after canonical checks rather than normalizing IDs
or weakening expectations. Corrected full payload execution passes152 cases/
364 fitted plus matching base payloads,1274 complete catalogue items/28618 fitted
property members and all matching base properties, all60 units/289 witnesses,
seven malformed unit inputs, complete original equipment probes/2793 guard
domains, trace/booster restoration and malformed rejection. Desktop imports
remain blocked and exact canonical IDs preserved. Latest Kotlin compilation
passes including the fitted-target identity requirement and source navigation.
The failed144052 owned AVD was removed only after terminal status/commit/path/
no-link/CIM checks; logs and verified APK parent remain. Eight-test native and
updated UI controls on the corrected batch remain pending.

Buildcf988893 passes all five gates; eight-test native170402 is running on its
immutable APKs. Startup/unit and complete equipment-probe methods have successful
markers, but the class result remains pending. New actual UI coverage is authored
for selected repeated modules through reorder/removal/undo-redo, missing-target
warning with no stale title, restored original current/base damage values and
comparison variation navigation with original name/raw cells. It adds five
captures (identity/moved/removed/restored/variation) while retaining both existing
UI methods and their six captures. The only product edit is a semantic tag on the
existing missing-target message. Compilation/execution are deliberately pending
until the native run finishes, avoiding concurrent heavy host work during its
startup/performance checks. No test timeout or assertion was changed.

Nativecf988893/170402 finishes eight tests in572.899s with one failure: identity
test SwapModules was rejected by Kotlin encoding because its helper supplied no
expected_revisions. The guard behaved correctly; no runtime contract change is
needed. Both new edit helpers now read the current fit revision and supply the
explicit map. The other seven methods have successful markers, including startup/
unit formatting, complete equipment probes,2793 domains and the complete canonical
properties/SQL identity/path comparison. The class result remains failed and its
logs/APK parent retained. Owned stopped170402 AVD was removed after terminal
status/commit/path/no-link/CIM checks. Latest compilation passes in13s for corrected
native identity method and all three UI methods. Private development launcher now
requires separate unit and corrected identity OK1 results, UI OK3 and all eleven
PNG captures; every earlier assertion/capture is retained. Full delivery remains
pending independent linked/restart/report/performance and full-suite gates.

Atf6c2c330 build171901 passes all five gates; focused172255 terminates
passed_focused_only. Cold unit formatting OK1, corrected repeated-module identity
OK1/7.26s, and all three actual-control UI tests OK3/132.5s. Eleven PNGs were
visually reviewed: readable current/base/precision, raw search/copy, recreation,
affector source/operator detail, equipment CPU/power/volume, loaded charge,
selected-module movement/restoration, explicit removal warning without stale
item title and original variation values. No clipboard overlay or IME obscures
these captures. Screenshot review establishes these views only, not every matrix
row. The final eight-method class, native fresh-process/linked proof, actual raw
report validation, full inherited suite/A10 and delivery remain required.

Native identity restart phases are authored for prepare/restored1/restored2,
with original values for both repeated modules, exact keys/protocol/graph/all-fit
comparison, distinct PID chain and empty reopened histories.5b8672ef compiles and
build173404 passes five gates. First run173634 fails the persistence-enabled
assertion in66.437s: the runner did not recognize the new phase argument, selecting
ephemeral diagnostics. Added the argument to the existing durable-routing list;
all earlier routes are retained. Also corrected the original fixture lookup to
use its module list order (there is no index field). The bounded raw-report
validator is authored but awaits actual successful reports; it preserves original
REL1e-10/ABS1e-9 and verifies settings' original numeric-type witness. These fixes
do not establish restart support before execution. Failed logs remain retained.

Corrected47eb45e0 build174140 passes all five gates; focused174358 passes all
three native phases: prepare58.922s, restored1 4.295s, restored2 3.717s, each OK1
and complete successful instrumentation markers. Three distinct PIDs preserve
the original repeated modules/72 precise attribute rows, both stable keys/full
inspection payloads, entire durable graph and all fit snapshots. Every reopened
history is empty; prepare retained nonempty redo history before the boundary.
All three raw reports have source-device SHA256 before/after and byte-size checks.
The strict host validator passes actual reports and rejects twenty actual-report
corruptions, including wrong source/dataset/settings/worker/persistence/PID,
history, original values/units/equipment, durable key and revision bindings and
numeric-type metadata. This proves the repeated-module restart witness only;
all-target families, linked edits/inspection navigation, complete integrated
reports/full native suite/A10/screenshots/review/delivery remain pending.

The next compiled native linked method retains all11 projection and19 command
states plus undo/redo after every edit (31+55 observations). It compares both fit
statistics with original value/unit wrappers, every original fitted/base attribute,
equipment and source/attribute tree, resolves fitted modifier sources and verifies
query graph preservation.9e build175310 passes five gates; wrapper correction451
build175602 also passes five gates. Focusedlinked175837 fails86.918s in the initial
projection state: test base index0 mismatched the required null base position.
The runtime target guard correctly rejects this. Native base target and host
base fit/revision/position expectations are corrected without omitting base rows;
explicit runtime source/dataset/settings/numeric-type/worker/import witnesses
were added to the same correction batch. Linked runtime/full-report success is
still unverified. Failed logs remain retained; no delivery claim follows.

Correctedd34d8c38 build180359 passes all five gates. Linked180753 fails123.524s
at a later projection history reversal with Java OutOfMemoryError:
"growth limit201326592" and "<1% of heap free after GC". Completed earlier
projection observations have successful markers, but no complete pass is claimed.
The test retained every full inspector payload and all10/18MiB original-state
fixtures in memory. It now reads only the requested independent original state,
checks the complete state-name inventory separately, hashes asset bytes through
a64KiB buffer and writes every original full payload directly to an app-local
report stream. It also avoids cloning original inspection data when extracting
statistic value/unit pairs. The same report schema, all31+55 observations,
original comparisons, navigation and graph checks are retained. Report transfer
streams the file rather than constructing another whole-report string. Compilation
passes in6s; no app heap setting, memory requirement or120s/900s limit changes.
The corrected runtime/raw-report proof remains unexecuted. Failed logs are retained.

3a2c2bad build181723 passes all five gates. Streaming-linked182058 runs342.516s:
all31 projection and55 command observation markers pass; the final required
command cross-fit source-navigation assertion fails. No complete pass is claimed.
EOS registers command modules on the recipient without changing their fitted
owner. Bridge navigation now resolves actual object membership among saved fits,
preserving every original registered-source field and both tree-builder labels.
UI source buttons use the resolved library name. Nonnull fitted source targets
must have saved owner keys; the cross-fit assertion remains required. The actual
host command witness resolves Shield Command Burst II to the original Vulture
module and durable key while preserving the original recipient label. Android
compilation/runtime proof is pending; no heap/time bound or scope changes.
Android Kotlin/native-test compilation passes64s. Actual command-owner regression
passes full original payload equality excluding the two navigation fields, fitted
source queries, both tree links and original recipient labels. Four independent
pinned presentation AST/regression tests pass in0.564s. These focused checks do
not replace the required linked native execution or complete delivery suite.

Owner-resolutionae775c08 build20261004-220944-ae775c08-393e1d passes all5 gates.
Focusedc032-linked-focused-20261004-221359 passes nativeOK1 in396.161s;
terminal wrapperpassed_focused_only, session91707 ended and emulator stopped.
Both actual complete raw reports were device hash/size verified and independently
validated: projection11 original states/31 history observations/1054 targets/
33325 precise attributes/15750 tree rows/362 sources including21 cross-fit;
command19 states/55 observations/1870 targets/63085 precise attributes/30272
rows/778 sources including42 cross-fit. All original comparisons and full
source navigation/history/query-preservation assertions remain. No full-delivery
claim. Host report validation now additionally recomputes source/cross-fit counts
from exact metadata, requiring saved owners, item agreement, nonnegative integer
positions and32hex durable keys. Actual-report corruption checks are running.
Next real UI source-button verification must cover both projection and command
owners and original fitted source values; previous UI proof does not cover those
buttons. Then complete remaining family/edit/restart/full-integration requirements.
Actual complete projection/command reports pass the stronger validator;28 actual
report corruptions are rejected (14 per kind), covering owner/item/key/index,
source/cross-fit counters, original values, stale revision, state, fixture hash,
worker/settings types and extra fields. The raw reports and rejection receipt
remain in focused221359/native. Native APK input is unchanged by this stricter
host validation and documentation checkpoint; no APK rebuild is implied.

The real source-button UI method is authored for projection and command cases in
both grouping modes. It streams one independent original linked state, validates
source/dataset pins, creates actual source/recipient fits and original add inputs,
checks the actual saved-owner button label, clicks the source, binds fit/index/
item/durable key and compares every original precise/normal/raw source attribute,
unit and group with unchanged REL1e-10/ABS1e-9. It requires the actual selected fit
and unchanged saved graph. Eight owner/source captures are added; all previous
three methods/eleven captures remain required. Initial compilation10s passes;
packaged/native execution and screenshot review are pending. Focused local UI
wrapper now requires all4 methods/19 captures and both exact linked fixture assets.
No native gate/full delivery claim follows from compilation.
4159ec71 build222856 passes all five gates. Focused223126 unitsOK1/28.209s and
identityOK1/14.094s pass; UI four tests112.445s has one failure in the new source
method: incorrect inspection-tab-Affected by tag, while the UI and existing test
use inspection-tab-Affected-by. All previous three UI methods pass. No source
navigation pass is claimed. Corrected tag is batched with explicit expand-all/
grouping checkbox state-setting and assertions, avoiding a retention assumption
when the selected fit changes. Original source/attribute comparisons, both modes,
fit/object identities and graph/capture assertions remain. Failed logs retained.

Corrected2d5153c5 build223700 passes all five gates. Focused223909 unitsOK1/
47.835s, identityOK1/6.123s and UI4/174.51s pass; all19 images were inspected
individually and readable. Both modes/type source buttons name actual saved
owners and navigate to the expected module/fit/durable key with unchanged graph.
Every original source precise/normal/raw attribute/group/unit matches. Existing
ship/raw/copy/recreation/affector/equipment/charge/identity/removal/restoration/
variation captures remain readable. New source captures currently show fitted
module headers; added real raw current/base widget assertions now compile8s and
will capture original changed capacitorNeed(27.0/36.0) and buffDuration
(103499.99999999999/60000.0). These visible-value additions require focused
execution. Full suite still requires all4UI methods/19captures.

Inherited defense/tank/output/targeting reporters retain the five exact core-field
and copy-input assertions, validate optional eight-family metadata/counts/32hex
IDs and uniqueness across fits, and reject reused copy identities. A complete
independent mode inventory contains6 families/18 choices: Confessor/Svipul/
Jackdaw/Hecate/Anhinga/Skua. The earlier B06 fixture omitted3 families and could
not validate all default modes. Original pinned EOS module-path/dependency/source/
logical-dataset checks and original modeItems produce the new distinct fixture;
required reference-inventory regeneration compares it exactly. All original
inventory members remain unchanged. An initial output-path collision with the
SQL identity fixture was restored; bytes match the immutable tested APK exactly.
Final99 focused inherited/schema/plan tests pass53.016s; expanded installed host
gate passes and both actual linked graphs validate. Initial96-test run had9
failures:6 from assuming no-mode Vexor had choices,2 stale phase inventories and1
old total-gate count. Corrected explicit inventories preserve original115 gates
plus29 added host gates and both exact new phase arguments. No inherited
calculation/copy/restart assertion is dropped. Full native gate/report/restart
integration and final stable-candidate verification remain required.


08db1a53 build230132 passes all five gates. Focused source UI230613 passes
OK1/100.663s. All eight device hash/size-verified captures reviewed individually:
actual source owners and original current/base capacitorNeed27.0/36.0 and
buffDuration103499.99999999999/60000.0 visible in both grouping modes. Long raw
values remain readable; no keyboard/clipboard overlay. Full final UI retains
all four methods/19 captures.

Native integration now explicitly inventories canonical8, linked1 and UI4 methods.
The canonical and linked phases keep separate900s deadlines: their previously
observed572.899s and396.161s must not be combined under one deadline. No method,
assertion, heap bound or operation limit is dropped. Strict runner validation
requires exactly one start/pass pair per selected method and rejects wrong counts,
skips, incomplete/duplicate/substituted events or terminal codes. Three new
regressions plus three preserved plan regressions pass; actual retained UI4 and
linked1 logs also validate. First combined test command lacked android/ci on
PYTHONPATH and failed to import the existing plan test; the corrected six-test run
passes. Full native/report gate integration and all-family restart proof remain
required; no full verification status is published.


Canonical restart integration now saves all152 cases/726 fitted and base targets
as streamed per-fit JSON lines, including full protocol numeric kinds and actual
mapped-table roles. Independent original attribute/group/unit/equipment,
property/affector/SQL membership and path assertions remain unchanged at prepare.
Two explicit fresh-process phases recheck every target, durable key, full payload,
empty histories, typed graph/all-fit snapshots,152/726 counts, complete existing
six-context inventory and unchanged payload SHA. They require different PIDs and
ordered prior phases. SQL replay IDs translate only after complete mapped-table
membership and existing property-reference checks; no value or field is dropped.
Private focused driver retains each phase's device hash/size-verified manifest
and full payload lines, and force-stops between phases. Each phase retains900s.
Compilation of initial stream/restore implementation passes25s; typed kinds and
explicit restart selectors compile22s; final SQL-role integration compilation passes21s. Seven focused phase/plan regressions pass0.190s. Native execution is not
yet proven. Mode/cargo/implant/booster fitted cases, full report collector,
all-family edit/reversal proof and complete stable-candidate delivery remain.


71a19c16 build232030 passes all five package/build gates. Focused native232335
is live on the existing owner: canonical8 then two distinct force-stopped restores,
each900s. Retained native170402 runner order shows preparation last; the focused
driver explicitly rejects any order where another method follows preparation,
and full graph/all-fit comparisons enforce the same boundary. No additional phase
or deadline increase is needed for that order check. No native pass claimed yet.

The strict canonical host validator independently checks all152 original input
sets, complete raw mapped SQL memberships (with proven row-ID translations only),
726 original attributes/groups/units/equipment, typed payloads/durable identities,
exact context counts and unchanged retained state across two restores. Its comments
explicitly distinguish unchanged preparation bytes from actual restarted-worker
observations, which still require successful native assertions. Explicit null ammo
and omitted empty fighter-list defaults are documented CreateFit representations;
no actual field/value is ignored. Decoder/SQL membership mutation regressions pass
2 tests0.006s. Expanded installed host gate requires these tests. Complete actual
report validation/corruption checks remain pending until device artifacts exist.

The expanded exact installed inspector host gate passes18 tests0.434s;
git diff --check passes. Actual complete canonical reports remain pending.


Focused71a19c16 native232335 terminal passed_focused_only: canonicalOK8/507.115s,
restored1OK1/93.53s and restored2OK1/99.885s. PIDs2714/4276/4344 are distinct;
all152 cases/726 targets preserve complete typed payloads, graph/all-fit snapshots,
durable keys and original values after both force-stops. All reopened histories
are empty. Each69,075,195-byte stream was device size/hash verified before/after
pull and shares SHA cf338a485a7e5bd6ffcc530579c10da9b95c8fcf4953beae8e3bf866a1ce92df.
Independent host validation of all three retained streams/states passes against
original input sets/SQL memberships, original attributes/groups/units,57,216
properties, both affector-tree views, effects and variation presentation/values.
Published/normal/metadata flags, all row field sets, source saved memberships,
variation highlights and unavailable-price None values are checked explicitly.
All29 actual-report mutations fail, with payload hashes recomputed before checking:
wrong values/units/targets/keys, missing/extra members, metadata/groups/properties/
effects/trees/source destinations/SQL roles/highlights/zero prices/counts/processes/
inputs/core fields. No hash mismatch shortcut establishes those rejections.
Expanded exact installed host gate passes18 tests0.339s; git diff --check passes.
The focused receipt records native source71a19c16 separately from the later host
validator's LF-normalized source hash. These are preparation bytes preserved by
restart plus successful actual restarted-worker assertions; no uncollected raw
restarted observation report is claimed. Remaining fitted contexts, flat-affector
metadata completeness, actual full gate collector and final verification remain.

2026-10-05 remaining-context reference checkpoint: independent pinned EOS plus
unchanged original attribute/property/equipment/tree methods now generate107
cases/805 states/3030 targets. All six mode families/18 choices, mixed cargo,
fit-local implant and99 slot/side-effect shapes selected from the complete311
published boosters are retained. Original raw afflictions include before/after,
operator/stacking/used/changed, fitted owner/type/item identity; mapped SQL roles
cover cargo/implants/boosters/side effects/mode as well as the inherited tables.
Full public and unavailable property members remain in the lossless gzip fixture.

The reversal guard caught missing original service clear/recalculate and the
original cold booster-owner registration behavior. Both construction and recreated
observations remain explicit; subsequent recalculated reversals must match complete
baseline attributes/equipment/both trees. Direct original setters establish
expectations, not Android controls, typed undo/redo, staleness or restart proof.
The new family is reference-only until its actual native comparison is integrated;
the publisher still rejects the partial145 plan. All115 inherited gates/order/
assertions remain. Existing installed launcher accepts focused inspector-family
gates, without starting a host substitute for reference-only families.

Nine focused fixture/coverage/mutation/launcher/native-boundary regressions pass
3.346s. The direct repeat job lost its tool/process owner before producing a
result; no pass is inferred. Next: run the installed focused reference gate on
the clean checkpoint, then implement the minimal fitted booster persistence
prerequisite and typed/native queries for every remaining target family. C08
still owns booster editing UI. Full C03.2 verification/delivery remains required.

Installed clean7750d748 focused reference run084011-4cc806 passes140.328s: both
fresh independent exports match every fixture field and unchanged database bytes.
The entire retained evidence manifest verifies. Fixture retains180834 precise
attributes,163057 properties,31278 raw afflictions and78308 original tree rows.
[Focused receipt](../evidence/c03-2-context-reference.json) does not claim native
comparison, typed undo/redo or full delivery. The earlier direct owner interruption
remains uncounted. No emulator/build/UI run was necessary for this reference-only
checkpoint.

Bounded C03.2.1 prerequisite, within the retained parent outcome: add worker-owned
booster state to durable records and typed bridge operations required to establish
inspector edit/removal/staleness/history/restart behavior. Preserve old saves and
their exact record representation when no boosters exist, every side-effect state,
complete saved identity families and all inherited assertions. Acceptance: malformed
input/slot/effect/duplicate guards, atomic failed-save rollback, complete original
context comparison, native typed operations, copy/undo/redo and two fresh process
restores. C08 remains responsible for the user-facing booster editing controls.
This child does not reduce any C03.2 acceptance criterion or create another approval
gate. C03.2 stays active until all target families and full verification are delivered.

C03.2.1 first implementation: original EOS booster models are captured in an
optional full record field; absent boosters preserve the old record byte shape.
Four typed Kotlin operations add/remove, toggle activation and select original
side-effect flags. Original slots are not limited to legacy1–3; all published
slots through504 are exercised. Replay checks complete exact effect membership,
slot identity and all flags before attaching any restored object. History labels
are explicit; copy creates fresh inspector keys and undo restores saved keys.
CI metadata preserves every original core field, checks the extra full booster
field/identity counts, and compares every copied flag rather than dropping it.

Existing guarded headless bridge suite now requires18 tests: all14 inherited
cases plus four booster cases. Actual focused090000 passes38.412s with no network
or desktop import attempts and unchanged database bytes. This covers311 complete
published records with933 typed mutations, original precise Standard Crash
attributes, history/copy/staleness, malformed replay, post-change failure recovery,
rejected durable write and same-process storage reopening with empty history.
The initial085000 failure selected the source from a multi-fit copy response;
the test now identifies the exact new fit and retains its fresh-key assertion.
The corrected17-case085400 also passed before complete311 coverage was added.
Inspector/presentation/canonical/identity/history28 guards pass0.283s.

These host checks do not establish native booster support, two fresh Android
restarts or every original context payload. Source hash retention additionally
includes the new worker/history modules. Next: build/package verification on a
clean stable checkpoint, then complete native remaining-context queries and
strict actual report collection without narrowing the parent acceptance criteria.

Stable57aaa978 installed build085750-412933 passes all five dependency/assets/
APK-lint/signature/package gates. Exact-source bridge18 tests42.579s also pass,
including retained new booster/history module hashes. Every build artifact hash
and all retained bridge source hashes verify. [Focused receipt](../evidence/c03-2-booster-storage.json).
No native execution, screenshot, two-process restore, complete context payload
or full verification pass is claimed. C03.2.1 remains active. Next: complete
independent flat-affector metadata and streaming native full-context comparisons,
then actual native report/restart collection and the stable full suite.

The separate canonical raw-affector exporter now retains152 cases/726 targets/
5588 rows, including107 unused and983 unchanged entries. It materializes and
checks the existing independent original attributes before observing cache-
sensitive metadata. Source positions use original object identity; complete SQL
memberships remain present. Separate host verification compares all17 protocol
fields, including exact SQL IDs, source navigation, stacking and before/after
values. Direct export and comparison pass; seven inherited-plan/native-boundary
guards pass0.263s. The installed partial plan is147 gates (115 inherited plus32
inspector host); native gates and publication remain incomplete. Next: retain
fresh repeated installed metadata evidence, then streaming native complete-
context comparisons and actual restart/report collection.

Installed28791d74 metadata091734 passes independent fresh/repeat52.109s and
headless22.750s; all ten artifact hashes verify. Complete original raw-field
comparison now also validates the three retained69MB canonical streams, using
only independently proven saved SQL/UUID mappings.37 actual-report corruptions
with recomputed hashes are rejected, including before/after/operator/stacking/
used/changed/source-ID and missing-row changes. [Focused receipt](../evidence/c03-2-affector-metadata.json).
These are preparation observations plus unchanged persisted bytes; no new native
execution or fresh restarted-worker stream is claimed. Remaining fitted contexts,
actual collector/restart proof and stable full delivery stay required.

Remaining-context native implementation uses five explicit900s phases and a
gzip stream with one original case in memory. Exact phase counts sum to107
cases/805 original states/3030 targets; all attributes/groupings/units, complete
properties, equipment, both trees and raw afflictions are compared. Independent
SQL membership proves identity mappings. Mutations use typed edits; reversals
exercise undo/redo, removed/recreated targets reject stale identities, copies
retain every core field with fresh keys. Cold booster recreation remains separate
from warmed undo restoration. Each phase has two real fresh-observation restart
selectors with empty-history assertions and typed graph/all-fit capture. The
fixture is instrumentation-only. Eleven selector/plan/native-boundary guards
pass0.243s. Build/native execution remain unverified; next: stable installed build
then focused context phases, followed by strict host report collection/validation.

Installedfb2438ab092900, fbd730e6093140 and correctedc42caaab093428 builds pass
all five gates. Review corrected Cargo's original `item.name` lookup. Android
asset merge expanded `.gz`; the preflight093337 failed before native launch,
then `.bin` packaging preserved exact compressed bytes. Native093713 never ran
a test: emulator fatal `Available: 5837.81 MB ... need 12288.00 MB`. No qemu/
emulator owner remains. Failed logs/config retained; completed-run AVDs have
almost no reclaimable data and an older paused image is preserved. Owner action
requested: free at least7GB on C:. No unchanged retry or partition reduction.

Independent remaining-context metadata fills the existing178-item fixture gap:
all127 current context items now have original effects and variation families/
columns/normal/raw cells. Direct export and headless comparison pass7552 cells.
Native streaming comparisons additionally check metadata/highlighting and honest
unavailable values; runtime/pins are retained. Strict host collection validates
every original state, undo/redo/copy, full current saved inputs and flags, SQL/
UUID identity, full payload fields and fresh restart graph/all-fit/pid proof.
Original null mode override can represent the independently observed hull
default, while CreateFit receives its explicit item ID; the only SQL translation
requires that exact independently selected item. No mode value is ignored.
Thirty combined guards pass4.177s, including real805-state membership/input/
coverage mutations; existing three canonical streams still validate. New native
collector and metadata/runtime additions are unverified on Android. Partial149
plan preserves115 inherited gates plus34 host inspector gates and remains
fail-closed for publication. Next: retain installed metadata fresh-repeat proof,
then stable build and native execution once space is available.

Stabled0f24779 installed remaining-item metadata095721 passes fresh/repeat71.344s
and host47.937s; build095842 passes all five gates. All retained manifests and
exact compressed-context/item-metadata APK bytes verify. [Focused preparation
receipt](../evidence/c03-2-context-preparation.json) explicitly retains the native
startup capacity failure and claims no context execution or full delivery.
Next: complete actual native/report gate integration while capacity is blocked,
then execute all context phases/restores after owner-confirmed space returns.

2026-10-05 C03.2 native collection prerequisite: canonical preparation and each
restart now retain complete fresh worker-produced typed target payloads in a
separate JSONL/state pair, with actual phase/PID/hash and live final graph/all-fit
state. Existing preparation/replay assertions and bytes remain intact. The
independent canonical validator has an explicit fresh mode; legacy receipts
continue to describe retained preparation bytes, without acquiring fresh claims.
Fresh rows require exact phase/PID/header membership, complete original payload
comparisons and distinct restart hashes with full graph preservation.

`inspection_delivery.py` declares23 actual phases: canonical and repeated-module
identity each with two restarts, five complete contexts each with two restarts,
linked inspection and four UI methods. It names19 required PNGs. The local
`inspection_native.py` collector restricts mutations to this exact run's API36
offline emulator, force-stops before every phase, clears its synthetic app store
only at independent group starts and retains runner events plus exact device
before/after SHA/size proof for every artifact. Restarts require all previous
artifacts and strict runner membership. Collection receipts explicitly exclude
independent validation, screenshot review and delivery. The collector is not yet
wired into full verification; publisher remains fail-closed.

Twenty-one focused host guards pass3.877s: collector ownership/pull/restart
integrity, instrumentation events, canonical freshness, complete context
guards, plan preservation and inherited native boundary. Mutations reject
preparation bytes as fresh, wrong phase/worker, missing/substituted/reordered or
escaped retained files and changed device bytes. The installed inspector
presentation host gate now runs these guards. No new native proof exists;
compilation is pending. No emulator retry or disk-capacity recheck was made.

Exactdc70a7d9 installed build102619 now passes all five gates: dependencies13.843s,
engine assets6.531s, APKs/lint70.468s, signature/package retained in the
[collection preparation receipt](../evidence/c03-2-collection-preparation.json).
All10 artifact manifest hashes/sizes and both exact context fixture bytes in the
test APK verify. Its exact presentation host command passes28 tests4.030s. A
focused launcher request for `inspector_presentation` was rejected as an unknown
selector before execution; this is recorded, not claimed as a launcher pass.
The direct command matches the installed full host gate. New Kotlin compiles;
new collector and fresh reporting have no native execution proof. Full plan
integration, actual-report validation/corruptions and screenshot review remain
required; the149-gate partial plan and publisher guard remain unchanged.

2026-10-05 installed native/report integration: the full plan now has173 gates
(96 host, five build,72 native), preserving every115 inherited gate in exact
relative order. `native_suite.py` retains its inherited byte contract. The23
inspector phases and independent summary run after inherited native summary,
adding33 actual executions for108 total. Independent fixture groups reset only
the run-owned API36 offline synthetic emulator; all inherited and prior group
evidence remains retained. Phase timeout900s, operation120s, heap192MiB, A10,
numeric tolerances and every comparison remain unchanged.

`inspection_summary.py` independently validates all exact phase/runner/device/
file contracts, three fresh complete canonical streams, three repeated-module
identity reports, all five complete context groups with two fresh restarts each,
both linked reports and19 PNGs. It invokes the original full payload validators
with pinned fixtures/settings. PNG CRCs, complete pixel streams and dimensions
are checked; all19 retained actual1080×1920 UI captures pass (earlier source,
no fresh UI or screenshot-review claim). Its summary includes all artifact
hashes and explicitly declares absent actual-report corruption proof and
screenshot review. Publication independently repeats report validation, requires
all inspector files in the retained manifest and rejects both absent and
falsified corruption proof. Thirty-seven combined host/plan/boundary/PNG/
publication guards pass4.315s. New integration has no native execution proof.
Next: implement and retain complete actual-report corruption checks, then stable
full verification after owner-confirmed capacity returns. No emulator or capacity
retry/recheck was made.

2026-10-05 actual-report mutation integration: `inspection_mutations.py` preserves
all37 existing canonical,20 identity and28 linked cases in tracked source.
Those85 mutations now pass against the actual retained device reports from
canonical232335, identity174358 and linked221359; canonical execution explicitly
uses legacy mode and acquires no fresh-worker claim. Identity original value,
unit and equipment mutations consistently alter every stored/observed protocol
copy, so they exercise independent expectations rather than mere copy mismatch.
Mutations are applied outside the rejection catcher; accepted corruptions or
unrelated runtime errors never become passing checks.

The complete native summary additionally requires five phase/PID/header mutations
for each canonical worker (42 each), and25 streamed observation/state mutations
for every context phase/restart. Baselines must validate first; altered payload
checksums are recomputed before checking fields. Temporary context files stay in
the owned evidence directory, are processed singly and are unlinked afterwards.
The fixed contract is549 rejections across21 groups. Publication independently
replays and compares the complete proof, including mutation hashes. No separate
boolean can bypass the checks. All39 focused inspector/plan/boundary/executor
guards pass4.561s. Fresh canonical/context mutations and the expanded native
chain remain unexecuted; native capacity is unchanged and not retried/rechecked.
Next: focused bridge replay of remaining-context construction/recalculation
lifecycle against independent cold/warm states, then native/full verification
after owner-confirmed capacity returns. Every existing state remains required.

2026-10-05 C03.2.1 lifecycle correction: focused typed BridgeSession replay found
Standard Crash construction's full booster trees/raw metadata already warm
(17 rows versus original15); numeric attributes, equipment and fitted properties
matched. Its original recalculated state matched17 rows. Booster mutation had
calculated immediately, then the existing transaction cleared/calculated its
complete affected graph again. `boosters.change` now clears the fit and defers
calculation to that existing graph boundary. Restore/copy/rebuild behavior and
all comparison tolerances remain intact; no expected state or field is omitted.

A separate mismatch was the process-local Item `ABYSSAL_TYPES` getter cache:
the independent sequential export had already read base properties before the
booster cases. Fresh group/restart workers had not, changing availability from
original nonportable-cache ValueError to initial None. Native independent groups
after slice0 and every restart now perform a base inspection read before their
first fitted observation and assert unchanged saved graph. Slice0 initial stays
unprimed, matching the reference's first case. No game/saved data or expected
property value is altered. Focused replay then matches both complete Crash
states, including every17-field raw affector and both original trees.

The new regression loops all99 original booster shapes across cold and warm
states, including base targets, all attributes/groups/units/equipment, complete
properties with proven SQL mappings, both original trees and every raw field.
Together with all existing history/copy/rollback/store/reopen/all311 catalogue
regressions,19 tests pass158.798s within unchanged180s. The bridge evidence driver
now also retains the compressed-context fixture and imported comparator hashes;
that added retention and native compilation await exact-revision checks. Native
execution/full delivery remain blocked by the previously reported capacity issue.

Exact528b7d80 rerun110102 hit the unchanged180s bound after the new lifecycle
test passed, during all311-catalogue mutations; its log is retained. The earlier
combined19-test run passed158.798s but left inadequate margin. The added99-shape
test now runs separately in four fresh workers25/25/25/24, each bounded180s.
The inherited bridge gate retains all18 original methods and assertions. A real
focused `headless:inspector_lifecycle` gate is added; plan174 comprises97 host,
five build and72 native, retaining every115 inherited gate in exact order.

Stable `da398141` installed lifecycle110836 passes four workers
45.718s/50.379s/37.156s/34.158s, exact indices0–98,198 complete cold/warm states.
All18 inherited bridge tests pass37.284s separately in core111323. Build111517
passes all five gates, including corrected native cache priming compilation.
All retained manifests,11 comparator/bridge source hashes and four reference
fixture hashes verify; both context test APK assets match exact source bytes.
Thirty-nine focused guards pass4.368s. Additional direct bridge replay matches
all eight mode/cargo/implant construction baselines16 states/68 full target
payloads. [Lifecycle receipt](../evidence/c03-2-lifecycle.json) retains the timeout
and truthful host/build scope; it establishes no native execution or full pass.
All test owners are terminal. Exact next: context native phases/two restarts,
then stable full proof/A10/all actual corruptions/screenshot review after the
already-requested disk capacity intervention. Do not retry an unchanged block
or start the next roadmap outcome before C03.2 delivery.


2026-10-05 owner capacity intervention resolved: one query165,660,053,504 bytes
free (154.28GiB; unchanged12GiB prerequisite). Native112934 booted successfully,
then contexts0 failed26.668s comparing first base ABYSSAL_TYPES availability.
The independent exporter starts with an empty fit set, whereas native durable
bootstrap automatically creates the original A01 Vexor; its modules load the
EOS abyssal cache. Host replay of that exact startup reproduces the mismatch.
The isolated context test now commits an authentic empty GraphStore before EOS
starts, refuses an existing file, confirms the commit and proves empty startup
library/graph. Only the collector-owned synthetic emulator store is involved.
No product bootstrap, original expected field, tolerance or assertion changes.
The independent context report validator requires that exact empty graph and
compares fresh restart startup graphs against the retained final graph. Host
replay with this prerequisite passes all eight nonbooster cold/warm baselines
(16 states/68 full targets);15 collector/report guards pass4.250s. The initial
incorrect unittest invocation lacked android/ci import search paths and produced
four import errors; corrected configured invocation passes. Corrected native
build/execution and full delivery remain pending.


Native113909/f2a4b500 diagnostic114802 retain all startup attempts and failures.
Mobile-data service startup can report command success before the global setting
settles; the private owner now retries readiness within120s and requires both
mobile_data=0 andwifi_on=0 before retaining its unchanged final assertions.
An attempted removal of those added assertions was denied by automatic approval
review; it was not executed. Diagnostics subsequently passed both assertions.
The empty context store then failed native restoration26.066s; retained Python
traceback identifies sqlite3.OperationalError: no such table: mutatorsDrones in
_reset_storage. The default SingletonThreadPool relies on Python thread-local
connection state across separate Chaquopy JNI calls. Android startup now binds
EOS metadata and its existing ORM session to one StaticPool SQLite connection
before any fit exists, disposes the unused initial engine and requires every
mapped table. EOS remains serialized on the same Java worker; no formulas,
upstream code, persistent graph rules or reference expectations are changed.
A direct test of actual mobile_runtime.boot/bridge_bootstrap verifies all mapped
tables survive an ORM connection release and all8/16/68 complete baseline targets
still match. Native proof and all A10/full delivery gates remain pending.

2026-10-05 resumption preserves the separate prototype worktree and defers broad
navigation/visual redesign. One prerequisite check: C:146,029,305,856 bytes free
(136.0GiB), unchanged12GiB prerequisite; WHPX usable, installed tools/image and
clean pinned reference present. No Pyfa verification process was running.

Native115502 reached mode edits after corrected empty bootstrap/SQLite lifetime,
but compared zero physical modules against17 original command-created vacancies.
The independent reference now executes pinned CalcChangeShipModeCommand and its
original fit.fill boundary. Export120402 and independent repeat122716 match;
complete host checks then match all six mode families through history/copy.

Cargo undo exposed a distinct lifecycle: direct original amount reversal retains
its ORM modified datetime diagnostic, while B01/B02/B09 fresh-graph reconstruction
creates a new object with modified=None. Independent export now retains every
original direct state AND separately rebuilds its exact inputs using original EOS
models/calculation, recording every reconstructed getter/attribute/equipment/tree
and raw affector field. History/copy/restart use that matching expectation; normal
edits still use direct expectations. No diagnostic field or original state is
dropped, no value comes from Android and tolerances/deadlines remain unchanged.
All107 cases/805 direct states/3030 targets remain, plus complete replay states.

Expanded export123226 passes independent fixture validation. Complete host context0
passes all eight cases and366 target observations, including mode/cargo/implant
edits, undo/redo, removal and copy. Thirteen reference/report/collector guards pass
27.507s, including missing replay/member/property/vacancy and restriction corruption
rejections. The first private diagnostic retry used a stale branch condition and
failed before cargo; its log is retained separately. Corrected driver passes.
Two initial unittest invocations failed solely on isolated import search paths and
an incorrect test-module name; no passing claim is attached to them. Final reference
regeneration, booster history groups, native/report and full proof remain pending.

Final corrected export124210 and fresh repeat124627 match SHA2566ec423bc0988b40f62d45717a73b501729f575eec383638ce7a2c207eb23b73a.
After independent history reconstruction, subsequent booster side-effect edits
also start from fresh original EOS objects, preserving timestamp diagnostics.
Complete host8-case/366-observation and25-booster/1612-observation checks pass;
14 focused guards pass15.275s. Tracked context-lifecycle receipt records exact
retained bytes and unchanged context0 inputs; native/full remains pending.
Prototype efficiency review reused read-only: early existing JSON/history/IME and
visual checks, batched reporting/provenance/transfer validation before stable full.
No retrospective rerun, new infrastructure or delivery-gate change.

Stable full132053/fb35ca91 passed36 gates before inherited13-case library test
failed equality on intentionally regenerated inspector identities. Exact complete
copy inputs/links remain compared, every copied identity now validates shape,
count/uniqueness and source disjointness; the entire original source record must
remain unchanged after independent copy edits. All13 focused EOS cases pass45.201s.
Existing resume mechanism gains an exact fb35ca91/pre-library36-gate test-delta
guard, preserving unchanged execution bodies and refusing product/test weakening
or unrelated changes. Five plan/negative guard tests pass0.501s. A test syntax
mistake preceded this pass and is not passing evidence. No product/APK change.
Resume existing full at library; all remaining/native/report/final review required.

Full132053 resumed750e4a7d:55 completed gates; history_mutations failed its complete
registered-operation assertion on four newly added booster commands. Preserve all28
original cases/durable tests and add actual independent booster undo/redo witnesses:
17 fit/30 complete target observations pass. Batched reporter validates exact
fb35ca91-to750-to-correction provenance and every retained gate;31 guards pass3.314s.
No product/APK change or gate relaxation. Resume same full failed history gate,
retaining55 passes; native/full/report/final screenshot review remain pending.

Full same-owner e9a2baa2 passes79 gates. Context metadata fails solely its old
context-fixture digest: all127 items/effects/variations exactly match the fresh
independent export; new digest matches decompressed final context fixture bytes.
Repair that single provenance field only. Exact79-prefix/source/delta reuse guard
rejects changed metadata values/product/affected gates; reporter validates all
three source-adoption hops with per-gate membership.32 guards pass4.856s.
Full/native/report/final screenshot proof remains pending; resume failed gate.

Full4a8f6c75 passes97 host/reference +5 build/package +20 native gates before
CargoActionTest times out waiting for the Core Scanner Probe I equipment query
in the final structure case. The saved failure image still has the focused
query and open IME; preserve every action/restart comparison and timeout.
The test now uses the existing charge-test IME/accessibility-layout wait before
scrolling and physically tapping Search, asserting unobscured button geometry.
A focused ephemeral long-name Astrahus probe repeats four real searches. Native
reports retain every query/identity/geometry observation; three focused reporter
tests reject missing searches, wrong identity and obstructed/nonfinite geometry.
Native probe/build remain pending. Failed graph retained unchanged: SHA256
76c14c1027f5236af869a9069c64d57f42440aba947d72c0aba46f1ee2c89d83.
87 completed-run screenshots already inspected with hashes; final coverage pending.

One-turn report fix on d96f8243: require cargo search witnesses to be a JSON
array of objects. Previously an empty object or empty string passed the restored
empty-search check. Two JSON regression tests cover ten malformed inputs; all
five focused search-validator tests pass (0.001s). Existing count, identity,
completion and keyboard geometry assertions remain unchanged. Native probe and
full delivery proof remain pending; no verification restart or merge this turn.

Goal resume: focused d96f8243 build passes all5 gates, but its four-search probe
failed before first search completion. Retained Android DropBox records confirm
System UI service startup ANR at23:20:48, preceding the failed keyboard request
at23:22:34. Read-only owned-AVD diagnostics confirm the saved graph hash unchanged.
Use explicit physical field focus as in the existing charge probe, and require
healthy launcher/window focus before the next focused execution. Keep every
IME/layout/geometry assertion and timeout; no engine or product UI change.

Correction af2ed23c build232815 passes5 gates; focused native probe passes four
real keyboard searches and eight reviewed PNGs. Application APK and persistent
graph hashes remain unchanged.59 focused source/recovery/search/report/plan tests
pass7.169s; actual recovered-store validation preserves all47 original inputs,
revisions and recent history while removing only9 known partial fits. Exact
4a8f6c75-to-correction source guard retains97 host/20 native gates, substitutes
the verified5 build records and refuses altered logs/artifacts/fixture/product
inputs or completed prefix. The remaining native/report checks still execute.
[Focused receipt](../evidence/c03-2-cargo-search-preflight.json).

Full515428bd cargo preparation passes1 native test272.018s, but collection fails
on the stale zero-byte optional failure screenshot. Same-commit report recovery
finds preparation JSON also zero bytes after emulator reboot; no report/gate pass.
Guest has8.4GiB free. Controlled artifact143,360-byte probe reproduces zero bytes
after console shutdown without sync, and exact bytes/checksum after guest sync.
Add mandatory sync before stopping the owned emulator, propagating flush failure.
Actual post-prepare graph rollback validates every47 prior record/revision/input
against the original pre-gate checkpoint; exactly10 known unaccepted fits are
discarded and the checkpoint's recent history restored. Repeat the entire cargo
gate and fresh-process restore; all122 valid completed gates remain retained.
[Durability receipt](../evidence/c03-2-artifact-durability.json).

## C03.2 bounded targeting-phase correction — 2026-10-06

Full owner132053 at9736218e retains147 passing gates; final targeting preparation
exceeded900s after its8 remaining fixtures passed, while UI checks were incomplete.
Raw diagnostics and actual failure image are checksum-archived locally. This is
an incomplete phase, not a native assertion pass or evidence of a platform ANR.
Separate final fixture construction (324 fits) and existing UI/copy/recreation work
(325 fits) into prepare2/prepare3 processes. Original prepare0/prepare1 and final
restoration remain required. Keep every assertion, all53 cases,900s per process,
120s operations,192MiB heap, all numerical tolerances and A10 requirements.
The extra process adds a required gate/execution:175/109.549 actual-report
corruptions and234 screenshot reviews remain required. Focused targeting17 tests
and plan7 tests pass; changed instrumentation build/native execution and exact
retained-source/APK/store recovery validation remain pending. Do not retry the
unchanged failed candidate or discard previously valid evidence.

Correction bec2c0eb passes50 focused checks (17 targeting,7 plan,26 tank/plan).
Official build030306 passes all5 gates; app APK remains byte-identical SHA256
7b23d95980033e8b301a6211d3b4ad7e1b6fb69dec9d991e8860a6303e5e1a3f.
[Build-only receipt](../evidence/c03-2-targeting-phase-build.json). Native recovery/reuse
guards and affected phase execution remain pending; no full pass.

The stopped owned AVD yielded324 synthetic fits and a retained checkpoint identical
to the passing prepare1 report. Recovery validation rejects changes to all313
verified fits, numeric kinds/revisions/modification metadata, and unrelated additions.
Supported graph transaction on a copy excludes11 exact final-case/source records
and restores verified recent inputs. All313 EOS snapshots match retained native
results with REL1e-10/ABS1e-9;8 source/recovery tests pass15.042s.
[Recovery-only receipt](../evidence/c03-2-targeting-recovery.json). Original store
preserved, recovered copy not installed. Artifact/APK reuse and launcher adoption
remain pending; no native retry or full delivery pass.

Guarded targeting adoption reuses142 unchanged host/native rows with their original
tested commits plus5 exact passing build rows; all147 completed gates stay retained.
Source/plan, raw log/artifact/APK/package/state and supported recovery guards precede
installation. Only root failed-run logcat is excluded from passing evidence hashes;
nested same-name files remain checked. Previous cargo provenance routes to archived
original APK/package/state.79 focused tests pass (36 cargo,11 targeting retry,25
publication,7 plan); diff check passes. Native resume and full delivery pending.

Resume933c4306 stopped in isolated preflight before archiving/installing or any
native execution: missing repository import path, then UTF-8 decoding prerequisite.
Batch repair adds explicit root import and UTF-8 reads; actual313-fit recovery
passes in -I mode, alongside72 isolated source/recovery/publication tests16.380s.
Original973 failure snapshot,147 passing gate rows and untouched device store remain
mandatory. Native resume is still pending; no rerun or pass claim for failed phases.
