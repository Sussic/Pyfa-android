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

**B05.1 is delivered** from `codex/b05-1-bulk-ammunition`. It adds revision-bound
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
- [x] Native offline touch selection/scope/preview/action, empty fit, mixed skips,
  rotation, navigation, independent copy and real process restart pass. Retain raw
  reports, strict Kotlin decoder rejection checks and screenshots actually reviewed.
- [x] All existing 114 host tests, references/repeats/migration, 28 native executions,
  type/unit/GC/performance/restart gates, APKs/lint/signature/data/license/ABI
  checks remain required, extended with the new cases. No phone installation.
- [x] Review, both required CI jobs on final head, artifact provenance/raw checks,
  screenshot review, PR merge and evidence/status/forecast update complete.

## Evidence and forecast

Independent reference/repeat pass nine cases/41 states/four recipients (fixture
SHA `a13fe41af114f36834ed14be66f5714662346c0fd9bc710506262e69ff054a09`). Six focused
host tests pass in 28.741s. The completed delivery below supersedes the initial
pending-native forecast. [Current status](../STATUS.md) records the updated
remaining-task forecast and measured final CI times.

## B05.1 delivery

Delivered in [PR #22](https://github.com/Sussic/Pyfa-android/pull/22), tested head
`b031c985be5acfcf79e3b06c45079b0ea11564a0`, merge `18de3c72eea047aaa0f94ec4a809e34b79665b6d`.
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35944859296)
passes **120 host tests** and all independent reference/repeat/migration gates.
[Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35944859268)
passes **30 offline native executions**, both APKs, lint, signature and
153-source/data/license/ABI inspection. All **56 screenshots** were actually
reviewed, including six bulk-ammunition views. Artifact digest/CI tree and raw
validators/corruption probes pass. Local full 26-gate host and APK/package checks
also pass. [Retained evidence](../evidence/b05-1-native.json).

Build 16 is a development build. ARM64 execution, older APIs, user usability and
safe upgrades remain unverified. B05 stays active through B05.3 clone/fill and
B05.4 variation/removal. The parent's complete scope and B09 undo/redo
requirement remain unchanged.

## B05.2 selected scope and acceptance

Selected on `codex/b05-2-bulk-module-states` from B05.1 delivery master
`e5098cc1ff017819f07c9afbdc99e0eab2a378d8`. The desktop state-column click
uses the clicked module as the reference; a click outside the selection affects
only that module, while Alt targets all similar modules. Left cycles by the
original local state map, right asks for overheat and Ctrl asks for offline.
EOS `Module.getProposedState` clamps each target to a supported state, then
fit-wide `checkStates` favors the reference module. The native workflow will
expose reference, selected/all-similar scope and cycle/overheat/offline choices
without relying on modifier keys. B06 retains subsystem controls.

- [x] Execute pinned original state command and fresh-process repeat over
  mixed active/passive/overheat capabilities, restrictions, similar variants,
  no-ops and linked recipients. Compare exact positions, states, inputs and
  independent values with justified numeric tolerances.
- [x] Bridge rejects malformed/stale selections atomically, applies original
  reference-first transitions and fit-wide fallback, saves once and preserves
  charges, order, unrelated fits and recent use. Verify rejected durable writes
  leave graph/revisions/recipients unchanged.
- [x] Native touch workflow shows supported requested outcomes and skips, handles
  empty fits, recreation, fit switching, restart and all-similar modules outside
  selection. Show actual saved states after fit-wide reconciliation.
- [x] Retain all existing host/native, type/unit, GC, performance, restart,
  screenshot, APK/lint/signature/data/license/ABI gates; review and merge a
  focused final-head PR with verified artifact provenance and status forecast.

## B05.2 delivery

Delivered in [PR #23](https://github.com/Sussic/Pyfa-android/pull/23), tested head
`2e6bb7af1a9af6e552f0970561f83cf738fb328f`, merge
`eb7e3039bf612e4c6672bf8af10db32ad6ab90aa`. The pinned original command
passes six cases/27 states/four recipients and a fresh-process repeat; five
focused host tests cover parity, rejection, atomic recovery and restart.
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/36083151800)
passes the complete **125-host-test** suite. [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/36083151805)
attempt 2 passes **32 offline native executions**, both APKs, lint, signature,
source/data/license/ABI checks and process restart. All **61 screenshots** were
visually reviewed. Artifact SHA-256 and CI merge tree match; 13 raw validators,
nine native protocol guards and ten deliberate report corruptions pass.
[Retained receipt and five views](../evidence/b05-2-native.json) preserve the
synthetic B05.2 evidence. The initial native UI test exposed an omitted skipped
preview row, corrected on the tested head. Final-head Android attempt 1 lost ADB
while transferring a prior empty-hull report; one same-head native-only retry
passed without changing gates.

Build 17 is a development build tested on an API36 x86_64 emulator. ARM64
execution, older APIs, phone usability and safe upgrades remain unverified.
Exact next task **B05.3 — Clone and fill modules**; B05.4 variation/removal and
B09 undo/redo remain in scope later.

## B05.3 selected scope and acceptance

Selected on `codex/b05-3-clone-fill` from delivered master `266b682a`.
Deliver F03.04 and cloning in F03.05: fill vacancies from a market item or
fitted source and clone selected fitted modules into explicit vacant positions
in one touch action. Preserve the original command's order, EOS legality,
restriction override, charge/state inputs and market-history distinction.
B05.4 retains variation and removal; B09 retains undo/redo.

- [ ] Execute pinned original fill-add, fill-clone and single clone commands;
  repeat in a fresh process. Cover capacity, early EOS rejection, override,
  retained state/charge, no-op/recent history and linked recipients.
- [ ] Verify one serialized, revision-bound bridge edit, strict selection and
  vacancy validation, deterministic selected-group mapping, atomic failure
  recovery, saved graph/revisions/history and independent values.
- [ ] Verify touch previews/actions, empty and mixed racks, fit switch,
  recreation and real offline process restart. Retain raw reports, decoder
  rejection checks and reviewed screenshots.
- [ ] Retain all host/native reference, type/unit, GC, performance, restart,
  APK/lint/signature/data/license/ABI gates; review and merge a focused
  final-head PR with artifact provenance and updated status forecast.
