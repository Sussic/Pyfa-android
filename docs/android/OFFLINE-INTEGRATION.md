# Profiles, atomic EFT import and capacitor graph integration

## Scope and source

This cloud source candidate integrates the reviewed C06 shared-profile graph,
I01 atomic EFT importer and G03 capacitor sampler into the current Android
Kotlin/Compose/Chaquopy application. It preserves the existing EOS engine and
ordinary fit-edit history implementation. There is no server dependency.

Input: `Pyfa-native-source-20261017-142340.zip`, SHA-256
`11bcad15f78104c023425fdfb8f761064472ba501a8d39cab564030f7fa5f4e9`.
All 459 source-manifest files were verified before extraction. The upload includes
dirty and untracked source; its checkpoint branch/HEAD is historical, not proof of
a current clean Git revision. The immutable extracted source is the patch base.

Do not apply the earlier isolated C06/I01/G03 patches after this integration.
Their reviewed implementations are already packaged under
`android_bridge/offline/`, with relative imports and the explicit native facade.
The previous isolated artifacts remain independent rollback/reference baselines.

## Persistence and history contract

- One profile/fit SQLite envelope remains the durable authority. Old fit-only
  stores migrate through the reviewed graph reader; profiles are not stored in a
  second independently committed file. Opening a legacy store is read-only until
  its first edit. Older apps refuse the new envelope; retain a recoverable app-data
  backup before qualification, because reverting source does not downgrade data.
- Built-in all-zero/all-five profiles are immutable. Clone one to customize it.
  A saved skill override affects every fit bound to that profile in one commit.
  Reverting an override is distinct from explicitly setting it to zero.
- Ordinary fit edits retain the original `EditHistory` action tokens and its
  field-level undo/redo rules. A shared timeline coordinates profile/import
  actions with those tokens. Shared actions require compatible participant
  histories; later assignments must be reversed before older profile edits.
- Derived skill projections are regenerated from profile authority during replay.
  Fit/profile/binding revisions remain monotonic. Receipts, recent use and
  modification ordering are not rolled back. Unrelated direct notes survive.
- Undo/redo history is session-local, matching the pre-existing application.
  Reopening restores saved fits and profiles, not the previous session's undo
  stack. Branching, history eviction and fit deletion invalidate shared actions
  coherently without discarding unrelated actions on surviving fits.
- A known rejected save preserves the confirmed graph and history. An unknown
  outcome disables further graph reads/writes until reopen; do not blindly retry
  a non-idempotent profile operation.

## EFT workflow

1. Supply separate EFT documents, select a profile, and preview. Limits remain
   16 documents and one MiB of original UTF-8 text in total.
2. The backend regenerates typed catalogue resolution and exact-line diagnostics.
   Invalid, ambiguous or unsupported entries prevent the entire batch from being
   committed. Preview JSON is never accepted as trusted fit input.
3. Persist the exact prepared request privately before executing it. The request
   binds original text/labels/order, request identity, dataset, graph generation
   and token, and profile identity/revision.
4. Execute one atomic graph transaction. After an unknown/transport outcome,
   reopen and retry the exact saved request, not a newly generated identity.
5. The bounded durable receipt ledger prevents duplicate creation across restart.
   A replay after an imported fit was deleted reports the missing ID and does not
   recreate it. Once the receipt ledger is full, new imports are rejected rather
   than evicting idempotency protection.

An import creates one shared undo action with a library anchor, so reversal can
be reached even when undo removes all imported fits. The receipt survives undo.

## Capacitor contract

The runtime exposes the reviewed version-1 sampler. Curves use EOS values and the
source-backed capacitor getter semantics, not a new Kotlin approximation.
Time is seconds, capacity GJ or percent, and recharge GJ/s. Duplicate x values are
ordered simulation events and must remain visible as vertical transitions.
Exhausted ranges are reported without invented extrapolation.

Limits: eight fits, 1,024 resolution intervals, 16,384 returned points total,
32,768 inspected simulation events per fit, up to 3,600 simulated seconds, and a
cooperative budget of at most 10,000 ms. EOS calculation and `getCapSimData` cannot
be interrupted inside their calls; cancellation/deadlines do not provide a hard
CPU/memory guarantee. Native sampling is serialized and stale results are dropped.
The wrapper calls EOS's public `clear()` after each query to bound the simulation
cache across different starting-capacity requests. Durable inputs/history are
unchanged. Cleanup failure closes the session instead of publishing uncertain
results.

## Verification and remaining qualification

See the accompanying test receipt for actual executed checks. Host EOS tests use
the available supplemental database SHA-256
`793c322ee202867e4346d4c73d81f47e721f2f60f3d1a3630477a05bfa5b85a8`.
This is not the pinned qualification database
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.

The subsequent cloud build checkpoint provisioned approved JDK 17, Gradle 8.13,
SDK 36 and build-tools 35.0.0, then compiled main and instrumentation Kotlin.
It regenerated the pinned logical database quoted above. Those compile results
do not establish Chaquopy JNI execution, Compose usability, native parity or
install-over-data behavior. Original supplemental host evidence remains labelled
as such; newer tests must name their actual dataset independently.

The owner deferred Android testing and transfer of ten missing inspector fixtures.
Those are qualification gates for dependent runtime checks, not a blanket pause
on independent integrated development. The next current slice is described in
[I01 outbound EFT](I01-OUTBOUND-EFT.md). Preserve the paused local state, all
existing release/data safeguards and actual evidence boundaries.
