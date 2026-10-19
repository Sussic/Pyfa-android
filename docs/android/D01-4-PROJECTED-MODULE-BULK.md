# D01.4 selected projected-module controls

This bounded F15.06 slice extends the existing single-row screen with state,
nullable range and removal for selected editable modules. It does not implement
mixed object-family bulk selection or claim complete D01/D02 parity.

## Atomic bridge contract

- `set_projected_module_states(fit_id, selection, state)` uses explicit source
  action IDs `inactive`, `active`, `overheat`.
- `set_projected_module_ranges(fit_id, selection, range_m)` accepts null or exact
  finite nonnegative binary64 metres; null and zero remain distinct.
- `remove_projected_modules(fit_id, selection)` removes all captured rows.

Selection is an ordered list of 1..1024 exact `{position, object_key}` objects.
Positions and stable keys must be unique; every identity and editable row is
validated before mutation. Legacy environment rows remain read-only. Expected
fit revisions and the current session are mandatory, as with single-row edits.
No repeated public single-row dispatch is used. One successful semantic action
has one graph commit and one undo entry. An unchanged complete saved graph may still publish a new revision but creates no
semantic undo entry. Unchanged selected rows can still cause original GUI
reconciliation of other objects, in which case that real graph change is undoable.
Confirmed failed-write rollback restores the whole graph, IDs and history;
uncertain-write failures keep the existing fail-closed reopen requirement.

## Source command policy

Original `gui/fitCommands/gui/projectedChangeStates.py`,
`projectedChangeProjectionRange.py`, `projectedRemove.py`, and their corresponding
`calc/module/` commands are authoritative.

States are proposed for all selected modules and reconciled once when changed.
Ranges reconcile each changed row in captured selection order. Removal reconciles
and flushes after each removed row in descending position order. Each helper uses
one final GUI conditional recalculation/fill. The final need-recalculate flag is
the last command's value, not an OR of earlier flags; a final unchanged range
therefore still requests the outer recalculation. Original graph-state side
effects, including scrambler/MWD and assistance restrictions, remain meaningful.
Graph undo deliberately restores complete exact inputs rather than lossy source
command snapshots. Unselected range, charge and spool values are preserved unless
original state reconciliation legitimately changes states.

## Admission

No constants are widened. At most N+1 helper recalculation roots (state at most 2)
fit the existing 4T selected-fit row allowance and ordinary 8H reservation. No helper
runs a capacitor simulator; existing 8F cap admission remains applicable. The three
operations join the explicit audited allowlist. Production guards still run before
EOS effects and before capacitor simulation at their existing distinct boundaries.

## Qualification

Implementation, independent source comparison, actual mobile-runtime seed/reopen
and main/instrumentation Kotlin compilation passed. All 176 discovered host methods
passed across bounded chunks; the 330s monolithic attempt did not finish. Eight
new native methods compiled, not executed. Receipts retain these distinct proofs. Android execution, the ten
missing inspector fixtures, pinned-clean-source proof and release usability remain
open. No device acceptance is implied by compiled instrumentation.
