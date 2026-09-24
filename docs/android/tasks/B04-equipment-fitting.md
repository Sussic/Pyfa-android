# B04 — equipment browser and fitting

Authorized by explicit chat confirmation on 2026-09-22, including related fixes,
host/native verification, review, PR delivery/merge and automatic advancement.
Base `bd22ed6d83f7951813eb09c9d932470cad04ce0e`; B03 dependencies are delivered.
Retain Kotlin/Compose, Chaquopy, the serialized EOS worker and declarative graph
storage. No formula approximations, release publication or phone installation.

## Bounded children and complete acceptance

**B04.1 — Offline equipment discovery.** Port the pinned desktop Market's display
policy using bundled EOS data: all market roots/children, published and forced
items, variant parent/group/meta assignments, name search, meta filters and jump
from an item to its market group. Render reachable paginated native controls,
retain browser state across recreation and show empty/error states explicitly.
Compare complete enumerated groups/items/memberships against an independent
unmodified desktop Market export and fresh-process repeat; assert native query
identity and UI navigation offline. This child supplies discovery for F02.01;
recently *used* items are completed with actual mutations in B04.2, not replaced
by recently viewed items.

**B04.2 — Fitting editor and item history.** Retain the entire original B04 scope:

- Remove fixture-only creation: choose a supported hull, create an empty named
  fit, and persist/reopen it. Absent equipment attributes are explicitly absent,
  never fabricated zeroes or inherited sample-gun values (F01.01 continuation).
- Add, replace and remove modules, rigs and service modules, preserve positions,
  and expose EOS slot/resource/skill legality (F02.02). Structure-specific modes
  and the dedicated structure fixture remain B06/F02.08.
- Load/replace/unload compatible charges, scripts and crystals; incompatible
  operations are atomic failures, retaining previous inputs/results (F02.03).
  Include the desktop browser's charges-for-active-fit view.
- Swap/reorder modules with states/charges retained and independently checked
  rack/heat behavior (F02.04).
- Supported item variations reconcile state/charge exactly as desktop (F02.05).
  Existing addition inputs must not lose this capability; later addition editors
  reuse it and retain their assigned inventory rows.
- Explicit restriction override and re-enable match desktop removal/legality
  behavior, with visible consequences (F02.09). Resource overloads/skill warnings
  must follow EOS/desktop semantics rather than an invented validity rule.
- A persistent bounded recent-item list follows actual add/remove/replace use,
  including duplicate promotion, exactly 20 entries and abyssal exclusion. Opening
  an item is not usage. Native restart/UI checks finish F02.01.

B04 stays incomplete until both children pass. Bulk selection/fill remains B05;
modes/subsystems B06, cargo B07 and undo/redo B09 retain their full requirements.
The initial split added one leaf and one rollup. The later B04.2 split below
brings the total to 76 leaf tasks plus seven parents; no acceptance is dropped.

## Relevant pinned desktop audit

Source remains `8b04f3b271e614b3e103853b44a7851a63d79d0e`.
`service/market.py` owns forced publication, parent/meta/market assignments,
variant expansion, root/group visibility and 20-item recent storage.
`gui/builtinMarketBrowser/itemView.py` owns tree/search/meta and active-fit charges.
`gui/fitCommands/gui/localModule/{add,remove,replace}.py` records real item use;
merely selecting/searching an item does not call `storeRecentlyUsed`.
Read the corresponding calc commands and EOS fitting checks before B04.2 edits.
F02.01–F02.05/F02.09 and the existing F01.01 boundary remain acceptance sources.

## Required verification and delivery

Preserve all delivered host tests, independent references/repeats/migration,
offline native executions, APK/lint/signature/package gates and original
numerical tolerances/types/units. B04 started with 78 host tests and 17 native
executions; B04.1 raised these to 84 and 18. Add focused host and real native
workflow/failure/restart checks for each child. Validate complete catalogue sets,
not a few familiar items. Inspect actual phone-sized screenshots and retain raw
evidence/provenance. Update this brief, STATUS, ROADMAP and local checkpoint with
actual outcomes. No child is complete on a launch or host-only result.

## Implementation and review history

B04.1 implements on-demand worker-owned catalogue/search and the native browser.
The isolated display-policy adaptation retains upstream notices and default
jargon; it imports no desktop services. Search retains desktop words/wildcards,
regex, default aliases and 100-row cap. The browser pages results and supports
meta filters, item-to-group navigation, empty states and activity recreation.
Recent use and fitting actions remain B04.2, so no full F02.01 or B04 completion.

The unmodified pinned Market exporter and fresh-process repeat pass for **718
groups, 6,822 items and 22 searches**. The exporter matches desktop `config.init`'s
`gamedataCache=False` before EOS imports; its actual search thread dispatches
through wx. An initial bootstrap using the default EOS cache failed on list
search tokens; no desktop methods were patched to bypass it. An earlier command
also correctly rejected the empty scratch DB before export. The verified A01
database was then used, with unchanged logical identity and file digest.

Six new guarded headless regressions pass, including every catalogue membership,
all 22 search results, repeat/cache isolation, unchanged fit/modification data,
invalid input and worker ownership. Local APK builds, lint, signature and package
inspection pass. The first required CI attempt passed all 84 host checks and 18
offline native executions on API 36 x86_64. Review then tightened the raw
catalogue/search/page comparator to require exact scalar types (float/bool/near-ID
mutations are rejected) and reduced equipment-screen spacing so group browsing
starts sooner. The screenshot checks now scroll the group list and destination
breadcrumb into view. Final-commit CI and screenshot review subsequently passed as recorded below.
B04.2 subsequently starts after this child's delivery, as recorded below.

## B04.1 delivered

[PR #16](https://github.com/Sussic/Pyfa-android/pull/16) merged as
`794f4b1c80f714432d8dff8709d8e33682bfbf00` after review of tested head `6f53682807372d82b610b15d3ee57b64a8ebeee3`.
[Final Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35741516902)
passes 84 host tests and all independent references/repeats/migration.
[Final Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35741516907)
passes both APK builds, lint, signature/package verification and all 18 offline
native executions. All 16 screenshots were reviewed; the five equipment views
and full raw catalogue/search observations are retained in the
[delivery receipt](../evidence/b04-1-native.json). Catalogue scalar types are
exact; earlier numeric tolerances remain unchanged. API36 x86_64 ran; ARM64
package contents only. No physical-device, upgrade or usability claim is made.

Exact next task: **B04.2 — Fitting editor and item history**, automatically
authorized by the current sequential roadmap request. Parent B04 remains active.

## B04.2 active

Selected on `codex/b04-2-fitting-editor` from delivered master
`fd24947bbebbcb3f9d40d6c29d1f8a31dffcfbac`; no open PRs at selection. The complete
B04.2 acceptance above is retained. Initial audit identifies the existing
fixture-only nonempty-module contract and sample-gun statistic assumptions as
necessary fixes for arbitrary empty hulls. Adapt the pinned desktop fitting
commands around EOS, preserving the committed graph's atomic failure recovery.
Require independent numerical/legality/charge/reorder/restriction references,
focused host checks and native edit/rejection/recreation/restart workflows in
addition to every delivered gate. No implementation or new verification is
claimed by this task-selection checkpoint.

### B04.2 implementation children

The audit exposes a contract/statistics change for empty hulls, followed by
separate fitting mutation families. Before code changes, split into:

- **B04.2.1 — Arbitrary empty ship and structure creation** (delivered): choose any
  of the 437 independently enumerated bundled hulls, create/name/save/copy/reopen
  empty fits, and replace sample-gun assumptions with explicit absent values.
  Compare the complete hull set and raw statistics against the pinned original
  ship/Citadel construction and EOS; preserve the existing fitted reference
  values and exact scalar types. Native full-set comparison and representative
  touch/recreation/rejection/restart checks are required. Modes/subsystem editing
  and structure fitting matrices retain their B06 ownership.
- **B04.2.2 — Module editing, legality and recent use**: F02.02 and F02.09 plus
  the recent-use portion of F02.01; add/replace/remove normal, rig and service
  modules, preserve positions/state limits, show resources/skill warnings and
  retain desktop restriction override/re-enable semantics. Persist real use in
  a 20-entry promoted list with abyssal exclusion. No recently viewed substitute.
- **B04.2.3 — Charges, variations and rack ordering**: complete F02.03–F02.05,
  including scripts/crystals, active-fit charges, fitted and existing addition
  variations, state/charge reconciliation and positional heat effects. Extend
  recent-use behavior only where the audited desktop operations record it.

Complete, review and deliver each child before advancing. All existing parent
requirements, atomic failure/restart checks and independent native evidence
remain mandatory. B04.2.1 used branch `codex/b04-2-1-empty-hulls`.

### B04.2.1 implementation and verification

The new-fit picker searches/pages all 437 bundled hulls and retains the selected
hull/name across activity recreation. The existing hull browser opens the same
picker with its hull selected. Original EOS Ship/Citadel construction and the
existing atomic graph path handle empty creation, naming, independent copies and
restart. All-V/no-equipment assumptions are visible. The existing example-fit
workflow remains available. Gun optimal/falloff are explicitly absent and display
"Unavailable"; calculated zero damage retains its numeric type. No formulas,
original fitted fixtures, dependency pins or storage schema changed. See the
[contract and compatibility boundary](../ARCHITECTURE.md#b0421-empty-hull-boundary).

The independent exporter runs original EOS constructors for every hull from the
unmodified desktop Market, with explicit skills/settings/security/damage and no
modules, drones, implants or linked additions. It compares two fresh processes;
the unchanged original A01/A04/A05 exporters remain required. The new fixture is
test-only. Floating values keep relative `1e-10` / absolute `1e-9` tolerances;
integers, booleans, identifiers, units and nulls are exact.

Focused local checks passed for 437 hulls (419 ships and 18 structures), 39 fields
each, plus six guarded bridge tests covering absence, failed mutations/saves,
independent copies and real process restart. Required native coverage now adds
complete typed hull observations and picker/search/page/recreation/cancel/name,
ship/structure creation, rejection/copy and process-restart workflows. All 84
prior host tests and 18 prior native executions remain required, becoming 90 and
20 respectively. The complete 90-test local Windows suite passes, including all
independent references/repeats and migration/backup. Local APK/test builds, lint,
signature and inspection of 147 source files, the dataset and both ABI packages
pass. Native CI, screenshot review and delivery subsequently passed as recorded below. Review of the
raw comparator rejects seven mutations of nulls/types/units/values; no earlier
scalar assertion or numerical tolerance was relaxed.

## B04.2.1 delivered

[PR #17](https://github.com/Sussic/Pyfa-android/pull/17) merged as
`307d5c07580c7f2f48cd7755acc63cc72c2108c9` after review of tested head `645d6f45ae802fec415ed08cc0093314bbbd184b`.
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35748120518) passes
90 host tests, independent references/repeats and migration/backup; the complete
installed local suite also passes. [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35748120466)
passes APK/test builds, lint, signature/package checks and all 20 offline native
executions. All 437 hulls and 39 fields match the independent reference; native
creation/copy/rejection and process restart preserve prior and new saved fits.
All 20 screenshots reviewed. Full raw observations, provenance and four new
screens remain in the [delivery receipt](../evidence/b04-2-1-native.json).

Only API36 x86_64 ran; ARM64 package contents were verified. No physical-device,
upgrade/downgrade or usability sign-off is claimed. Exact next task:
**B04.2.2 — Module editing, legality and recent use**, automatically authorized.
B04.2/B04 remain incomplete until every retained child acceptance check passes.

## B04.2.2 active

Selected on `codex/b04-2-2-module-editing` from delivered master
`9e16cf21d9ba0f117419e99ac3d5e544b9196541`; no open PRs. Retain the complete
module/rig/service mutation, slot/state, legality/restriction and actual recent-use
scope above. The outcome must be reachable through the equipment browser and fit
editor and survive saved-data restart with atomic rejection. Audit the original
desktop commands and enumerate the reference matrix before implementation.
All 90 host tests, independent references, 20 native executions and APK/package/
signature gates remain mandatory. Charges/variations/reordering remain B04.2.3,
bulk editing B05 and structure modes/subsystems B06. No new implementation or
verification is claimed by this selection checkpoint.

### B04.2.2 reference matrix and boundary decisions

Before adapter implementation, use original EOS and the pinned calculation
command bodies for add/remove/replace, `ModuleInfo`, `activeStateLimit`,
`Fit.checkStates`, `Fit.recalc` and `Character.checkRequirements`. The isolated
oracle loads these definitions unchanged from the verified checkout, with real
wx, Market and EOS. It does not import the Android adapter or replace calculation
methods. Definition loading avoids unrelated desktop login/window imports;
desktop window event dispatch is outside this oracle. Record source-file hashes,
full operation inputs, raw values/units and two fresh-process results.

The matrix covers high/medium/low/rig/service slots, first matching empty slot,
removal holes and same-slot replacement; active/default-online policies; limits
on online/active groups; slot, hardpoint, hull, capital, rig-size and group
restrictions; explicit override and reverse-order re-enable (desktop deliberately
ignores hardpoint limits during removal); allowed CPU/PG/calibration overload and
recursive missing-skill warnings (rig skill requirements excluded as desktop).
Also check unchanged existing charged/stateful neighbours, copies, saved reload,
linked recipient invalidation, malformed inputs and rejected durable writes.

Recent use is the desktop command history, including attempted valid-item
add/replace commands rejected by fitting restrictions. Opening/searching an item
is not use. Record the attempted item's history separately from the unchanged
fit on a legality rejection; malformed/stale requests and failed storage writes
must not change either. Keep at most 20 IDs, promote duplicates, exclude abyssal
items, and retain the list across an empty library and process restart.

Existing fits and empty-hull snapshots retain their current positions until a
module edit. Then original `fill()` materializes vacant slots without moving
occupied positions. Persist explicit vacant slots and restriction state so
reload/copy cannot compact holes, discard overrides or silently remove an
over-hardpoint fit retained by desktop re-enable. Expose vacant slots explicitly
in the typed native boundary; retain every existing scalar assertion and gate.

### B04.2.2 implementation checkpoint

The worker adapts the audited module commands around unchanged EOS. Declarative
vacancies and optional restriction/history fields preserve holes, overrides and
recent attempts in the atomic graph store. Legality rejection restores all fit
inputs/revisions/results before separately confirming the attempted recent item;
malformed requests and rejected writes preserve history too. Re-enable retains
desktop's over-hardpoint behavior, and saved/copy reconstruction preserves it.
The native editor provides racks, add/replace/remove, explicit restriction
controls, resource/skill warnings and recent-use browsing. Vacant snapshot entries
are explicit typed alternatives with no invented name/state. Original scalar
assertions remain; old tests explicitly require occupied module state as before.

Six focused host checks pass eleven cases/91 states and all 4,242 default states,
with real restart, failed saves, copies and headless/network guards. The matrix
includes two projection recipients, shared recent history and strategic-cruiser
subsystem vacancies retained for B06. The test found unassigned ORM owners on
new vacancies; flushing after `fill()` fixes snapshots before durable commit.
Review aligns replacement acceptance with desktop's recalculation order.
The complete Windows suite passed 96 tests before these final refinements.
Local APK/test builds, lint, signature and source/data/ABI inspection passed.
Two native phases now require every reference value/type, UI workflows, 13
malformed-protocol rejections, unchanged prior fits, 20-item visible order and
fresh-process retention, with seven screenshots. Final build/CI, visual review
and delivery remain outstanding. Existing gates and tolerances remain required.

PR #18's first Windows run (35759228642) passes all 96 tests and independent
references/repeats/migration. Android run 35759228624 passes every one of the 22
instrumented executions, then the final report validator rejects
`globalDefaultSpoolupPercentage`: JSONObject writes the original decimal as an
integer. The diagnostic report now preserves the original numeric-kind metadata;
settings values still compare exactly. Wrong-kind and sub-tolerance setting
mutations are rejected. This is a report-transport correction, with no formula,
fixture, production behavior or tolerance change. The local rebuild passes;
fresh final CI remains required. All seven new screens from this run were
inspected; final-run review still covers all 27 required screens.

The second run (Windows 35761981241, Android 35761981271) again passes 96 host
tests and all 22 instrumented executions, but its strict type-map comparison
correctly detects that capture occurred after EngineRuntime's earlier JSON
serialization. Capture moves into that worker method, before its first writer,
with an early native assertion against the independent setting types. A probe
using the installed JDK/JSON library reproduces the first-writer normalization
and verifies that early type metadata survives both writer boundaries with exact
values. No fitting behavior or reference expectation changes.

## B04.2.2 delivered

[PR #18](https://github.com/Sussic/Pyfa-android/pull/18) merged as
`b4b254071a3bdcddbd88ec5711feccc374d264fc` after review of tested head `cf9c51857cd37615c2ff9e2b592d3a6bb24dd1ae`.
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35775027054) passes
all 96 host tests, independent exports/repeats and migration/backup.
[Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35775027092) passes
both APKs, lint, signature/package checks and all 22 offline native executions.
The 91 fitting states and 4,242 defaults match the independent original commands;
native editing, warnings, restriction confirmation/recreation, history, copy and
real restart retain exact identities/types/values. Thirteen malformed protocol
cases are rejected. All 27 screenshots reviewed; the seven module screens and
complete raw/provenance results remain in the [receipt](../evidence/b04-2-2-native.json).

Only API36 x86_64 ran; ARM64 package contents were verified. Physical-device,
upgrade/downgrade and user usability evidence remain future gates. Exact next:
**B04.2.3 — Charges, variations and rack ordering**, automatically authorized.
B04.2/B04 remain incomplete until all retained child acceptance passes.

## B04.2.3 active

Selected from delivered master `6c71af9a6be24c1da783f51ab76fd018f21c52a7` on
`codex/b04-2-3-charges-variations-ordering`, with a clean tree and no open PRs.
Complete F02.03–F02.05 as specified above: charge/script/crystal operations and
active-fit charge discovery; fitted and existing-addition variations with exact
state/charge/location reconciliation; module swaps and positional heat effects.
Audit unchanged pinned commands, then define independent raw-value cases before
adapter changes. Keep atomic rejection/save/restart, recipient invalidation,
all prior 96 host tests and 22 native executions, APK/lint/signature/package
checks and actual screenshot review. B05 bulk and B06 modes retain their scope.

### B04.2.3 implementation children

Before adapter changes, separate the audited command families into three focused
deliveries. This adds two leaves and one parent: 78 leaves plus eight parents.

- **B04.2.3.1 — Charge editing and active-fit discovery** (active): native
  load/replace/unload for compatible ammunition, scripts and crystals, a complete
  compatible-charge picker and active-fit charge view. Independent original
  `Ammo.getModuleFlatAmmo`, browser union and charge commands verify complete
  sets, numeric effects, unchanged states, linked recipients and empty/rejected
  cases. Failed writes, copy, recreation and real process restart are required.
- **B04.2.3.2 — Fitted and addition variations**: all retained F02.05 behavior,
  including existing addition inputs, desktop state/charge/location reconciliation,
  independent values and native workflows/restart. Later addition editors retain
  their separately assigned requirements.
- **B04.2.3.3 — Rack ordering and heat behavior**: F02.04 swaps across occupied
  and vacant positions in the same rack, with retained state/charge and independent
  heat behavior, native workflows and restart.

The parent remains active until all three pass. Review and merge one child before
starting the next, retaining every prior host/native gate. No acceptance is moved
out of B04. This split does not authorize unrelated additions or formula changes.

### B04.2.3.1 audit and reference matrix

Original `CalcChangeModuleChargesCommand` checks charge category and EOS
`isValidCharge`, keeps module state, recalculates, checks other states and lets the
GUI recalculate again when needed, then fills vacancies. It does not record recent
use. The single-target mobile operation rejects incompatible inputs atomically;
the existing bulk boundary remains unchanged for B05. Selecting an already loaded
charge is a no-op for saved inputs. Discovery uses original `getValidCharges` plus
Market publicity; active-fit discovery is the union over local modules, not the
projected additions. It refreshes after fit edits and active-fit changes.

The independent matrix covers hybrid/projectile/missile ammunition, laser/mining
crystals, tracking/sensor/dampener scripts, cap-booster volume, ancillary paste,
structure missiles, command charges, no-charge equipment and empty fits, including
two projection and two command recipients. Compare complete charge sets for every
supported catalogue module, strict identities/types/units and raw fit/module
attributes. Original command and browser-method bodies execute unmodified; only
their window identifier is supplied by the isolated reference harness.

The first reference enumeration exposed EOS's optional global query cache mixing
item/group integer IDs. Desktop `config.init` disables that cache. The reference
now uses the same setting before EOS imports; the adapter must do likewise before
charge discovery can call the original EOS methods safely. No EOS formulas or
upstream sources change. Retain all prior correctness/performance gates to check
the runtime effect of this initialization correction.

### B04.2.3.1 development checkpoint

The charge picker/worker operation, complete compatible/active-fit discovery and
native test phases are implemented locally. The independent two-process export
passes 14 cases/74 states and 4,242 compatibility sets with unchanged database.
The first focused test run exposed stale recipient observations in the new
reference harness; the corrected reference calculates invalidated recipients
before reading, as the prior module oracle does. Corrected Windows export digest:
`113db7f76d776984989b3163bfd587ffe01e6ddacefba3e279b052274625be30`.
This is an observation fix before delivery, not a tolerance or EOS formula change.
Six focused host checks pass, including atomic rejection/save failure, all charge
sets, recipient updates, copies and process restart. The full local Windows gate
also passes all 102 host tests, independent reference repeats and migration.
Local builds of both APKs, lint, signature and package/data/license/ABI inspection
pass with 149 engine sources. Native CI, visual review and delivery remain outstanding.
Required totals are 102 host tests,
24 native executions and 35 screenshots.


### B04.2.3.1 delivered

[PR #19](https://github.com/Sussic/Pyfa-android/pull/19) merged as
`a1c784532035ebf7b5e75fc42ee74d5d2d5e3266` after review of head
`b6b24010b45bff5e0fdcbc2c1c80fcd0693807a2`.
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35790288102)
passes all 102 host tests, independent references/repeats and migration/backup.
[Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35790287983)
passes both APKs, lint, signature/package checks and all 24 offline native
executions. The first PR CI round passed: Windows 16m27s, Android 17m23s.

All 14 charge cases/74 states and 4,242 compatible sets match the independent
original command/Ammo/browser method. Four linked recipients, atomic rejection,
unchanged history, scripts/crystals, UI recreation and 12 saved fits after a real
restart pass. Eleven malformed protocol inputs are rejected. All 35 screenshots
viewed; the eight new charge screens and raw/provenance reports are retained in
the [receipt](../evidence/b04-2-3-1-native.json). Raw validators rerun on the download;
artifact SHA-256 and CI tree match the reviewed head. Nine report corruptions are
rejected, including missing cases/sets, changed history, same PID, wrong numeric
kind and a 1e-12 settings mutation. No required check or tolerance was weakened.

Only API36 x86_64 ran; both ABIs were inspected. Physical-device/upgrade/usability
limits remain. Next authorized task: **B04.2.3.2 — Fitted and addition variations**.

### B04.2.3.2 selected scope and desktop audit

Selected on `codex/b04-2-3-2-variations` from delivered master `6c8b217a`.
The existing bridge accepts local modules, drone stacks and fit-local implants,
plus linked fits. Expose single-item variations for those three local contexts;
changes to linked source fits must invalidate every recipient. Fighter, booster,
cargo and directly projected addition editors retain their assigned later rows.

Pinned `itemVariationChange.py` obtains complete families from Market, excludes
abyssal meta group 15, sorts modules/drones by remapped meta group, meta level and
name, sorts implants by name, and enables local choices with EOS `fit.canFit`.
Variation edits do not promote recent use. Original module `changeMetas` copies
ModuleInfo, retains valid state (otherwise getMaxState), keeps compatible charge
and unloads incompatible charge after replacement/legality/state reconciliation.
Drone `changeMetas` removes the selected stack and appends a distinct replacement
with unchanged total/active quantities, without merging. Implant `changeMeta`
uses slot replacement and retains activation; this bridge's location remains FIT.
Drone capture must record the edited stacks rather than replay the original spec.

Acceptance: independent unchanged desktop command/menu definitions and complete
supported catalogue families; meaningful raw-value cases for charge retention/
unloading, offline/online/active/overheated state, drone stack order/quantities,
implant activation/location and linked recipients. Native controls must provide
search/pagination, disabled choices and current input details. Require strict
wire types/revisions, atomic malformed/incompatible/stale/write failures, unchanged
recent history, independent copy, recreation and actual process restart. Preserve
all 102 host tests, 24 native executions and raw-value/type/unit/GC/performance/
screenshot gates. Implement no new calculation formulas or storage architecture.

The independent reference now passes 16 cases/51 states and all 5,226 supported
families in two fresh processes. It includes the only audited mixed-state family:
active Breach Control becomes online when changed to Damage Control II, and
switching back retains online. Windows export SHA-256 is
`62141d902d3e7b71d95f29f44e03418f28e4386973f0d6bd7c30ab288681ed4b`.
Native/host delivery checks remain in progress; this reference alone does not
establish Android support. The new host checks add six tests to the prior 102;
the two native phases add to the prior 24 and require eight new screenshots.

Review identified a family that spans implant slots (Genolution/Source). Desktop
can keep the selected implant and add or replace the occupant of the chosen
variation's different slot. Add explicit original-command coverage, atomic
duplicate-target rejection, copy/restart and native workflow checks. This raises
the final matrix to 17 cases/55 states; full verification is in progress. Picker
wording explains this behavior. The original GUI can fail on an already fitted
target; the bridge returns a structured atomic rejection instead.
B04.2.3/B04.2/B04 stay incomplete until their remaining children pass.

First PR #20 verification: full local 22 gates/108 host tests, independent
17-case/55-state reference/repeat, both APKs/lint/signature/package pass. Windows
run `35798892136` passes all 108 host tests. Native run `35798891774` passes the
retained suites, then fails in `VariationEditor.kt` returning from variation
choices to target cards (`FocusOwnerImpl` cast to `ComposableLambdaImpl`). Split
those lists into separate composition scopes with stable row keys; retain the
same recreation/save/navigation regression. This run took 24m38s before the
remaining UI/restart checks, so allow 30 minutes at workflow level without changing
test assertions or performance limits. New native evidence is required.

Second native run `35918007006` passes the repaired recreation/edit/return
transition, then exposes an incorrect pagination fixture: Hobgoblin has five
choices in the independent export. Use a temporary Gecko fit with its actual
94-choice family to assert next/previous pages, recreation and empty filtering,
then remove it and retain the original Hobgoblin quantity/order workflow. Record
actual pagination identity/count/page values and require them in the raw checker.
Windows run `35918007020` passes on attempt two; its first runner failed checkout
certificate validation before tests, and a fresh runner passed both checkouts
with unchanged TLS validation. No test or required coverage is removed.

### B04.2.3.2 delivery evidence

Delivered in [PR #20](https://github.com/Sussic/Pyfa-android/pull/20), merge `d14441eb771157127d768668200396cea3d2750a`;
tested head `b0fa526cf1c0c9ce3d8038d39d908b56dccda43e`. The final Windows reference/repeat SHA is
`0723086610da6b97887831b1cf58126111c7562780710ccd83e151b650cdcd75`. All 17 cases/55 states and 5,226 families pass, with six recipients,
state fallback, cross-slot implants, atomic failures, unchanged history and copy/
restart. Windows CI `35921791052` passes 108 host tests; Android CI `35921790783`
passes 26 native executions, both APKs, lint, signature and package inspection of
150 sources/data/licenses/ABIs. All 43 screenshots reviewed;
strict raw validators/corruption probes pass, artifact digest and CI tree match.
See [raw receipt](../evidence/b04-2-3-2-native.json). Local 22 gates/108 tests and final
APK checks also pass. The Compose transition correction retains its regression;
no formulas, protocol assertions or performance thresholds were weakened.
Build 14 is a development build. ARM64 execution, older APIs, phone upgrades and
usability remain unverified. Next: **B04.2.3.3 — Rack ordering and heat behavior**.

## B04.2.3.3 active

Selected from clean delivered master `1e72427aa87c8331c25027a6fa080977712c5566`
on `codex/b04-2-3-3-rack-ordering`. Live fork master matches; no open PRs.
Deliver F02.04: swap occupied/vacant positions within a rack while retaining
module identity, state, charge and other inputs. Audit original swap commands and
positional heat before defining independent raw-value cases. Expose reachable
native ordering controls and verify atomic invalid/stale/write failures, linked
recipients, unchanged recent use, independent copies, recreation and real restart.
Preserve all 108 host tests/26 native executions, raw types/units, performance/GC
gates and actual screenshot review. No EOS formula changes. B04 remains incomplete
until this child passes; B05 bulk and C09 heat options retain their full scope.

### Desktop ordering audit and initial reference

`fittingView.startDrag` rejects an empty source; `swapItems` accepts only the same
rack. `CalcSwapLocalModuleCommand` frees both positions, then replaces them with
the original objects, preserving state/charge. The GUI command commits and emits
FitChanged without recording recent use; identical source/destination is a no-op.
The touch editor therefore selects a fitted source and an occupied or vacant
destination. Empty-source attempts are rejected before mutation. A first reference
probe called the command with an unreachable empty source and exposed an ORM
deleted-vacancy error; the corrected cases follow the actual startDrag guard.

Positional heat is the pinned `Thermodynamics` class in
`gui/builtinViewColumns/heat.py`, separate from EOS but using its modified
attributes. Preserve its complete class body and 600-second simulation, including
the different duration/speed precedence in the estimator and display. Kotlin
formats raw results only. Non-overheated modules have no burnout estimate;
calculation failure must be visibly unavailable. Heat options remain C09.

The independent original swap/heat export and fresh-process repeat pass for
**nine cases/48 states** across high/medium/low/rig/service racks, mixed states,
charges/scripts/crystals, vacancies and four linked recipients. Initial reference
SHA `afbc1bef55a806a7c431d6c5f67c22fc552504ef7df198a00987716689a7172a`;
data/source unchanged. Android comparison and native evidence remain pending.

### Implementation and local checks

The worker-owned `swap_modules` operation validates occupied source/same-rack
destination, retains original objects and uses the existing atomic graph save.
`rack_options` returns strict integer positions/cycles and decimal seconds/
probabilities. The complete original Thermodynamics body is reused; EOS formulas
remain untouched. A native rack editor supports swap/move, cancellation, visible
states/charges/heat and selection recreation. Revision changes clear stale
selection; opening another fit defaults to its high rack.

Six focused host checks pass, including original raw heat values, all recipients,
failed writes, independent copies, forced GC and a real restart. Both local APKs,
lint, signature and 152-source/data/license/ABI package inspection pass. The full
114-host suite and 28 native executions remain required before delivery. Native
tests retain complete raw observations, ten malformed protocol cases, seven
screens and two separate production-storage processes. No gate was weakened.

First CI round: Windows `35928790741` completed the numerical/copy/save/restart
cases but failed the heat-body audit because the sparse application checkout has
no `gui` directory. Read that body from the already-verified independent pinned
checkout, validating its commit and recorded file hash. Retain the AST equality
assertion. Native `35928791055` attempt one passed the inherited B03.1 library
instrumentation and in-app full-report comparison, then ADB returned only 2,048
bytes and reported the device offline. A fresh-runner retry was started; the
corrected commit supersedes it. No product failure or heat mismatch was observed
in these failures, but complete native ordering evidence is still required.

Corrected-head Windows `35930553789` passes all 114 tests and independent exports
in 21m55s. Android `35930553774` passes all 28 instrumentation executions, including
the complete 48-state heat matrix and both ordering workflows/restart. Its raw
summary then rejects a mistaken expectation: a negative position is caught by
the strict Kotlin encoder as `INVALID_REQUEST`, while valid out-of-fit integers
reach Python and return `INVALID_EDIT`. Correct that exact expected code; retain
every rejection and atomic-state assertion. Validate the captured reports and
screens, then obtain green required CI on the final head before delivery.
