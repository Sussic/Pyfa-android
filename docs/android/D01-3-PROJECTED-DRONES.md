# D01.3 individual projected-drone contract

Baseline: immutable reviewed D01.2 ZIP recorded in BASELINE.json. One bounded
native workflow, no device qualification. Numerical EOS and original command
semantics remain the authority. The integrated records and native controls are source-reviewed. Final host/native
qualification and cumulative delivery evidence are recorded in their receipts.

## Records

Optional `spec.projected_drones` ordered list, each exact record has `name`,
`amount` (1..2^31-1 integer), `active` (0..amount integer), `range_m` (null or
finite nonnegative canonical binary64 metres). Item types are unique per fit,
with at most 1024 stored stacks as a serialization boundary. Neither boundary
is a game limit or evaluation admission. Reject unknown fields, charge,
mutations, duplicate types and nonprojectable items explicitly.

Optional `inspection_ids.projected_drones` appears iff the spec field appears;
legacy eight-family records and the independent optional projected-module family
remain unchanged. Empty optional records persist after removing the final stack;
undo can restore prior absence. Refresh order and logical identities must survive
all five relationship-refresh paths. Copy creates independent logical IDs.

## Bridge surface

- `projected_drone_details(fit_id)`: structure flag and `stacks` rows with index,
  object_key, item_id, name, amount, active, range_m, editable and unavailable_reason.
- `projected_drone_add_options(fit_id, item_id)`: authoritative is_drone,
  is_projectable, is_structure, enabled and unavailable_reason.
- `projected_drone_options(fit_id, position)`: current item/object identity,
  variation choices, whether activation is allowed and explicit reason.
- Add: `add_projected_drone(fit_id,item_id)` adds one, active one for new stack;
  existing stack increases active count only if already partly/fully active.
- Set total: `set_projected_drone_amount(fit_id,position,object_key,amount)`;
  zero removes. Active count changes by the quantity delta only if previously
  active, then clamps to 0..new total, matching the source command.
- Set enabled: `set_projected_drone_active(fit_id,position,object_key,active)`;
  bool desired. Already-active partial stack remains partial on redundant true.
  False deactivates; a subsequent true activates the entire stack only if
  `canBeApplied(fit)` allows it. Denied activation retains the original no-op
  result while its GUI wrapper still flushes/recalculates/fills.
- Range: `set_projected_drone_range(fit_id,position,object_key,range_m)`.
- Variation: `change_projected_drone_variation(fit_id,position,object_key,item_id)`.
  Source semantics remove old stack and append replacement, merging into an
  existing destination type if present. Existing destination range/active policy
  wins; a new replacement resets range because original DroneInfo omits it.
- Removal: `remove_projected_drone(fit_id,position,object_key,amount)` with positive
  integer quantity; UI Remove one sends 1, Remove stack sends current total.
  Remaining active becomes min(old active,new total), unlike quantity editing.

Each edit carries existing session/exact fit revision. No-op UI actions skip
unnecessary dispatch. Original wrappers flush/recalculate/fill; do not insert
projection-module checkStates, local drone bay/bandwidth/hull limits, or Recent
promotion. Native undo/redo restores exact captured state, including range and
partial-active counts; original lossy undo is documented instead of copied.

## Native workflow

Dedicated single-stack screen, equipment Add one, total/partial-active display,
quantity and nullable km range with unchanged-text raw-metre preservation,
activation, source variation list, Remove one/stack and existing history.
Retain stale drafts until explicit review, reject completions from old fit/session,
clear discarded request keys, and provide safe equipment/fit navigation. Base-item
inspection is explicitly labelled; closed effective inspector contexts unchanged.
Show evaluation-budget refusals and unsupported inputs rather than losing data.

## Required proof

Source-reference numerical snapshots for all nine actual effect families,
partial-state/removal/merge behavior, unaffected onward projections, source command
ordering, admission boundaries and full rollback, graph/profile/history/restart,
adversarial five-path refresh, canonical JSON, source-consistent EFT loss warning,
host regression, main/instrumentation Kotlin compilation and independent review.
Device interaction and frozen inspector fixtures remain deferred, not completed.

## Explicit resource behavior

Actual proposed incoming active counts are admitted before effects; huge inactive
quantities remain representable. A scoped import reservation is stronger than
ordinary editing, with old-graph preflight before staging and guaranteed scope
restoration. Confirmed admission refusals preserve saved inputs and report a resource reason.
Uncertain-write failures retain their existing fail-closed reopen requirement.
The detailed source/count/capacitor contract and all measured boundaries are in
the cumulative delivery's ADMISSION-CONTRACT.md. They do not promise a universal
EOS wall-clock ceiling or device responsiveness.
