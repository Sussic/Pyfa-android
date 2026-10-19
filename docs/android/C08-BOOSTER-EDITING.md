# C08 local boosters and side effects

## Integrated scope

The booster editor exposes fitted boosters, source slot numbers, activation,
implemented side effects with original calculated names, original variation
choices, duration and selection-based removal/state changes. Slot numbers are EOS
values, not an invented three-slot maximum. Structures explicitly disable the
editor in accordance with the desktop booster pane.

Equipment additions use an EOS-backed add-options query. A non-booster returns
an explicit false flag, never a name/category guess. The query identifies the
current slot occupant and fit revision. Replacing an occupied slot requires an
explicit native confirmation bound to that revision, followed by one ordinary
bridge transaction. A changed fit rejects the stale confirmation.

## Atomic source semantics

New `fit_booster` replaces a matching slot and appends the new booster, with
constructor defaults: active, side effects off. An exact duplicate is rejected
without saved-state/history changes. Successful fitting and selected removal
promote original Recent use IDs through the same transaction/history path;
variations do not. Desktop GUI duplicate attempts also promote Recent use, but
this native rejected request deliberately preserves all saved state. Existing `add_booster` still rejects an
occupied slot, preserving earlier callers' contract.

`change_booster_variation` carries active state and matching effect-ID states;
new effects retain source defaults. It uses the original variation family,
eligibility and ordering: name order for large families, otherwise side-effect
chance rank. Replacement preserves the original remove/append ordering, not an
in-place row promise. Original GUI empty-slot materialization is retained on these edits.
The source item-ID removal workaround is retained without
importing desktop GUI modules. Existing durable history restores exact original
rows and logical identities on undo.

`toggle_boosters` uses the main row's inverse state for main plus selected rows.
`remove_boosters` removes selected unique positions in descending order.
The existing single-row `set_booster_side_effect` operation is retained. Details
show only implemented effects; the complete durable effect set is preserved.
All operations use the existing fit-revision, affected-graph, durable-commit and
shared history boundary. Linked-fit projection and command setup/removal now explicitly
rebind unchanged inspector identities around the existing EOS ORM refresh;
otherwise a reloaded booster could incorrectly acquire a new logical identity.
Legacy saved booster records remain unchanged.

Duration is the original modified boosterDuration in milliseconds, with the
source `formatAmount(duration/1000/60,3,0,3)` minute label. Unknown remains null.
No booster effect, probability, duration or fitting calculation is reimplemented
in Kotlin. Explicitly selected side effects are inputs, not random rolls.

## Evidence and limits

Executed host proof: 87 regression tests, eight independent source/EOS tests
including unarmed/armed stat comparisons, subsystem slot layout and all four
projection/command identity refresh boundaries, plus actual mobile runtime and
fresh-process restart. See package receipts for native compiler results. Source references are calc/booster, gui/booster/changeMeta,
helpers.py:BoosterInfo, itemVariationChange and boosterView. The previous reviewed
C05 candidate remains frozen. Pinned logical game data is used for new tests;
older supplemental-dataset receipts are not relabelled.

No device execution, screenshots, usability, upgrade or release acceptance is
implied by compilation. Ten inherited inspector fixtures and device testing
remain owner-deferred. Independent ready implementation continues; these gates
block only dependent qualification. Full backup and external interchange remain
separate roadmap work.
