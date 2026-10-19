# C05 fighter Recent-use parity fix

The current integrated candidate closes the explicit Recent-use gap in the
original C05 checkpoint. That artifact remains frozen; this is a cumulative
follow-on rather than a rewrite of its evidence.

## Original behavior retained

- A successful local fighter add promotes the requested type, deduplicated at the
  front of the existing bounded Recent list.
- A valid fighter rejected by hull/category legality still promotes the attempted
  type, as `GuiAddLocalFighterCommand.Do` does after its calc command returns false.
  Malformed requests, unknown/nonfighter inputs and stale revisions do not.
- Selected removals process descending indices and promote each removed type in
  that order. The lowest removed index ends at the front.
- Quantity-zero removal, variation changes, activation and ability edits do not
  promote Recent. These are distinct original commands, not aliases for removal.
- Undo preserves Recent; redo replays the original promotion even if another fit
  has since changed its order.

The helper returns successful used-item identities through the existing ordinary
transaction/history path. Normal valid-item rejection uses existing
`FittingRejected` recovery and atomic metadata-only graph publication. Fit inputs,
revisions and history remain exact; graph context generation can advance. Failed
metadata saves restore the previous durable graph and Recent list. An uncertain
save keeps existing fail-closed engine recovery requirements.

## Native integration

The equipment browser retains newest-first order. On confirmed non-unavailable
edit errors, native state must refresh both Recent and offline feature context,
so a metadata-only rejection cannot leave subsequent profile/export/graph requests
using the previous generation. Error visibility and unchanged fit/history remain
part of the contract. This also fixes the existing valid-module attempt route.

## Evidence and remaining scope

Source: `gui/fitCommands/gui/localFighter/add.py`, `remove.py`, `changeAmount.py`,
corresponding calc commands, `service/market.py`, and current durable graph paths.
Synthetic fits and the verified pinned logical database are used. See current
receipts for executed host/runtime/source tests and main/instrumentation compiler
results; compiled instrumentation is not Android execution.

The original checkpoint had only the narrower same-type shortcut. The current
follow-on is documented in C05-SIMILAR-SELECTION.md; its evidence is separate.
Projected fighters, deferred fixtures/device tests and release/usability gates
remain open. No local or device work is resumed.
