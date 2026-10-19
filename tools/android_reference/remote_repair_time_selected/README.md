# G05.2a selected-time distance verification

This lane compares independently exported original values with the candidate's
existing serialized native-session route. It is not an Android execution claim.
The accumulated-distance, rate-time, and accumulated-time children remain open.

## Independence

`compare.py` imports no EOS or candidate math. Coordinates, order, duplicates,
lengths and zero values compare exactly; nonzero HP/s uses relative 1e-10 and
absolute 1e-9 tolerances inherited from G05.1. Expected arrays are only from
hash-bound independent original receipts on the pinned physical/logical dataset.
Horizon-warmed preflight point probes MUST NOT be reused for a fresh shorter
horizon. Only matching distance curves at the receipt's generation horizon are
reusable. `export_original.py` adds fresh-cache first-cycle/depletion/spool
boundaries from original metadata with nextafter and ±1e-5 neighbors.

`candidate.py` uses real runtime -> NativeSession -> sampler calls. Its reserve
hook forwards all charges to the production RepairReservation, recording counts
without removing admission. Complete graph, revisions, snapshots, transient
history, object identities and synthetic durable-store bytes must remain equal
around each graph read. Expected source columns remain current HP/s even when
selected-time rates differ. No game database is copied.

## Execution

Pure suite from the repository root:

    python -B -m unittest tools.android_reference.remote_repair_time_selected.test_compare

EOS exporters/candidates require explicit `--execute`, an outer 180-second timeout,
1-GiB address-space cap, before/after input hashes, and the parent's coordinated
serial slot. External run scripts/receipts bind exact commands and logs. A command
that did not start, failed, or stopped at a resource rejection is not a pass.

## Open gates

Parent evidence matrix tracks the finite accepted set. Default allocation policy
is a conservative nominal unit ledger, not an Android memory estimate. Successful
source comparisons cannot establish clean pinned-source reproduction, Android
execution, offline/upgrade/visual/accessibility/ARM64 or release qualification.
