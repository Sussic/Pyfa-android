# D01.2 projected-module contract

Cloud candidate independently source-reviewed and tested: 157 host tests, nine
source-reference methods and actual mobile-runtime seed/fresh-process reopen
passed. Main and instrumentation Kotlin compiled (33 tasks, 155 seconds elapsed);
ten new instrumentation methods were not executed. D03.1 remains an immutable
independent baseline. This slice does not claim device qualification.

## Persistence and compatibility

`spec.projected_modules` is optional. When absent, legacy records retain their
exact eight-family inspector identity representation. Existing `environments`
replays once as a verified ordered prefix of EOS `projectedModules`; new ordinary
rows form the suffix. Environment rows are visible read-only. New rows require
actual EOS `isModule` and `isType('projected')`, not category/name guesses.

Each ordinary row contains name, actual state, nullable charge name, nullable
range in metres, and optional nonnegative integral raw `spool_cycles`. Explicit
zero and absence differ. Ranges are canonical native/EOS binary64 values;
non-exactly-representable integral JSON values are rejected, not silently rounded.
Signed zero is normalized to positive zero before persistence. Non-cycle/fractional spool, mutation, projected RAH,
unknown fields, negative/nonfinite ranges and unsupported item types fail.

First individual projector creation adds the optional spec key and optional
`inspection_ids.projected_modules` family. The family covers the entire ordered
collection including environment prefix; after the last ordinary removal, explicit
empty suffix and its remaining environment identities remain. Undo can restore the
old absent representation. Copy receives new logical IDs. Rebuild/profile changes
and fresh restart restore exact recorded IDs and raw inputs.

The original projected ORM relationship lacks `order_by` and managed positions.
Each of five source-refresh paths therefore records unique ORM module IDs after
its existing flush. After refresh it verifies exact membership, restores the old
in-memory order before numerical calculation, and then restores logical IDs.
This changes neither collection membership nor SQL positions. Missing or duplicate
IDs fail closed. This bookkeeping prevents identical-item rows swapping inputs
and IDs under a different reload order.

## Read and edit API

Version-1 reads echo fit ID and revision: `projected_module_details`,
`projected_module_options(fit_id, position)`, and
`projected_module_add_options(fit_id, item_id)`. Rows retain original collection
positions and unique logical object keys. At most 1024 rows and 8192 choices per
charge/variation menu; native presentation is paged. No expanded inspector context.

Seven ordinary operations are `add_projected_module`,
`set_projected_module_state`, `set_projected_module_charge`,
`change_projected_module_variation`, `set_projected_module_range`,
`set_projected_module_spool`, and `remove_projected_module`.
Every request requires the exact fit revision; existing-row edits additionally
require position and a 32-character lowercase hexadecimal object key. State
requests use source proposal names inactive/active/overheat. Null charge clears,
null range uses default, null cycles resets. EOS owns valid charge/state choices,
recipient immunity, heat, range falloff and effects. No local rack capacity rule
is imposed on projected variations. Structures refuse individual projection.

## Original command policy

Add/remove: flush, inner recalc and state check; outer conditional flush/recalc,
then fill. State/charge/range: no added preflush before inner recalc/check, outer
conditional flush/recalc and fill. Spool: outer flush/recalc/fill. Variation removes
and reconstructs/appends in source order; replacement gets a new object key and
default range because original ModuleInfo omits projectionRange. It preserves
supported state/charge/spool inputs subject to source compatibility rules.

The bridge alone commits atomically. Native graph undo restores exact previous
captured inputs, including range and identities. Original desktop removal undo
can lose range; that source loss must be reported, never copied into native undo.
Individual projected modules do not project onward from their recipient. EFT
preview explicitly warns that these objects, states, charges, ranges and spool
inputs are omitted. Existing LOCAL read preparation and capacitor cache handling
remain intact.

## Remaining qualification

Independent original-command numerical/ordering comparisons, adversarial refresh
and integrated host/runtime regression passed on the final frozen source. Main
and instrumentation Kotlin compilation also passed. Remaining qualification is
separate: deferred Android execution,
accessibility/screenshots and the ten missing frozen inspector fixtures. Dataset
provenance and historical supplemental-test disclaimers remain unchanged.
