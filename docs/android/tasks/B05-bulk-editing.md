# B05 — Bulk weapon/module editing

## Outcome and baseline

One touch action edits the intended module group with explicit mixed-selection
behavior. B04 delivered in PR21; implementation starts from `d599ccb8523ecf9c75c0ac3963b6e53b8f1fe473`.
Desktop pin remains `8b04f3b271e614b3e103853b44a7851a63d79d0e`, logical database
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
[Roadmap](../ROADMAP.md) owns status. Kotlin/Compose, Chaquopy, serialized EOS,
the existing graph store, skill/settings pins and all prior gates remain.

## Bounded deliveries

| Child | Owned behavior | Minimum outcome |
| --- | --- | --- |
| B05.1 | F03.01–F03.02 | Native multi-selection and explicit selection-only/all-similar ammunition scopes, target/skip preview, independent mixed ammo/script/crystal and recipient/restart evidence. |
| B05.2 | F03.03 | Original cycle/offline/overheat commands, supported state fallback across selected modules and all-similar scope; explicit outcomes and persistence. |
| B05.3 | F03.04 and cloning part of F03.05 | Clone into vacancies, clone selected modules in one action, fill from a market item or fitted clone; states/charges, stopping/legality/history rules. |
| B05.4 | Variation/removal part of F03.05 | Complete selected or similar module operations, matching variation-family filtering, rejected replacements and removal/history order. |

B05 remains active until all four are delivered. F03.06–F03.07 undo/redo remain
B09 and must encompass these actions as one user action later. Hull modes and
subsystems remain B06, cargo B07, additional heat/reload/spool options C09,
mutation UI C10 and persistent interaction preferences I06.02. These boundaries
retain the existing inventory rather than imply completion of those behaviors.

## Desktop audit (2026-09-24)

- `gui/fitCommands/helpers.py:getSimilarModPositions` includes the reference
  module, exact item IDs, and modules with the same non-null group/market group
  and equal effect sets. “Same type” is therefore not merely equal item ID.
- `gui/builtinContextMenus/moduleAmmoChange.py:handleAmmoSwitch` chooses all
  similar modules when the preference/modifier XOR is true. Otherwise it walks
  selected modules in fit order, retaining modules whose complete public charge
  set is a subset of the reference module's charge set. The chosen charge must
  then pass the calculation command's per-module EOS validity check. A mixed
  selection can intentionally leave some selected modules unchanged, even if
  they individually accept a particular charge. Empty unload is supported.
- `calc/module/changeCharges.py` skips unchanged/invalid entries, recalculates
  and checks states after actual changes. Its GUI wrapper recalculates when
  required, fills vacancies and commits once. It does not promote recent use.
  B05.1 exposes both scopes directly and names affected/skipped modules before
  mutation; malformed/stale selections reject the whole request. Intentional
  desktop filtering is distinguished from an atomic durable-write failure.
- `fittingView.py:click` uses the clicked module as the state reference; a click
  outside selection acts only on that module. Alt applies all similar modules.
  `CalcChangeLocalModuleStatesCommand` computes the reference transition through
  EOS `Module.getProposedState`, then clamps each other module to its supported
  state. Left cycles, right requests overheated, Ctrl requests offline. It then
  checks fit-wide state restrictions with the reference module preferred.
- `gui/localModule/fillAdd.py` repeats original adds until the first rejection,
  storing the attempted market item in recent use even when no module fits.
  `fillClone.py` snapshots `ModuleInfo` from the fitted source and repeats adds;
  it retains inputs and does not promote recent use. A stopping attempt can
  recalculate/restore before the one final fill/commit. Override behavior and
  termination must be probed before claiming a safe equivalent.
- `fittingView.py:startDrag` selects a single occupied source. Ctrl-drag routes
  to `GuiCloneLocalModuleCommand`, whose calculation body deep-copies into a
  vacant destination after EOS legality checks. Desktop drag itself is single
  source; the inventory's selected-group cloning remains an Android one-action
  composition to verify, not a claimed original multi-drag capability.
- `itemVariationChange.py:__handleModule` filters selection by complete equal
  variation families; Alt/Ctrl uses all similar modules. `changeMetas.py` applies
  original replacements in order and retains state/charge reconciliation.
  `itemRemove.py` supports selected or Alt/Ctrl-similar removal. Original removal
  frees all positions before reconcile/fill, then promotes removed IDs in reverse
  position order (subsystems before ordinary modules).

## B05.1 implementation and acceptance

The selected child is **B05.1** on `codex/b05-1-bulk-ammunition`. Add revision-bound
bulk charge discovery/preview and one serialized mutation. Native selection,
reference module and scope are explicit; show current charges, exact targets,
skips and empty results. Revalidate on fit/revision changes, preserve selection
through recreation when still valid, and clear stale selections after external
edits. Every accepted action commits once with all affected recipients.

- [x] Independent original desktop handler/command execution and fresh-process
  repeat cover exact-type/related variants, asymmetric mixed compatibility,
  all-similar versus selection, unload/no-op, ammo/scripts/crystals, fit-wide
  state reconciliation and multiple projection/command recipients.
- [x] Focused host checks compare exact IDs/positions/types/units/inputs and raw
  values (existing justified floating tolerance only); malformed/duplicate/stale
  selection and failed-save rollback preserve graph, revisions and history.
- [ ] Native offline touch selection/scope/preview/action, empty fit, mixed skips,
  rotation, navigation, independent copy and real process restart pass. Retain raw
  reports, strict Kotlin decoder rejection checks and screenshots actually reviewed.
- [ ] All existing 114 host tests, references/repeats/migration, 28 native executions,
  type/unit/GC/performance/restart gates, APKs/lint/signature/data/license/ABI
  checks remain required, extended with the new cases. No phone installation.
- [ ] Review, both required CI jobs on final head, artifact provenance/raw checks,
  screenshot review, PR merge and evidence/status/forecast update complete.

## Evidence and forecast

Independent reference/repeat pass nine cases/41 states/four recipients (fixture
SHA `a13fe41af114f36834ed14be66f5714662346c0fd9bc710506262e69ff054a09`). Six focused
host tests pass in 28.741s. Local APKs/lint/signature/153-source/data/license/ABI
inspection pass. Native implementation and instrumentation compile; execution
and full regression/CI/evidence review/delivery remain pending. Provisional B05.1
remaining 2–5 hours, moderate-to-low confidence until the first native workflow.
B05 total remains unknown until clone/fill/override termination is verified.
Observed B04 full local checks take about 30 minutes; parallel CI takes 25–35
minutes per round, plus corrections/review. B06 and B07 remain unknown until
their specific audits. No access or product decision is needed now.
