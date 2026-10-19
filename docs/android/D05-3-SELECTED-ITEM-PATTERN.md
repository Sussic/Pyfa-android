# D05.3: selected-item incoming damage pattern

## Bounded outcome

Equipment offers **Use as incoming damage pattern** for an eligible bundled item when a saved fit is active. Values come from the item's base EM, thermal, kinetic and explosive attributes, not fitted weapon/charge damage, overrides or caller-supplied values. Missing and falsey zero attributes become integer zero; other exact supported numeric kinds remain intact. Eligible drones and other non-charge items are not arbitrarily excluded.

The action creates or updates the protected `damage:selected_ammo` singleton, named **Selected Ammo**, and binds the current fit atomically. Existing holders and affected linked fits recalculate in the same shared graph action. Outgoing equipment, charge selection and the global pattern are unchanged. The special entry can be selected or detached through the ordinary pattern library, but cannot be renamed, directly edited, duplicated or deleted. Builtin duplication remains supported.

An identical value/binding request is a no-op. Equal values with a different binding change only the relevant binding/current fit and affected links. Changed raw numeric kinds count as a real pattern update. One shared history action covers the library and all participants; undo/redo uses the existing conflict rules and monotonic revisions.

## Protocol and persistence

The damage request/state/response protocol is version 2. `item_options` is read-like and publishes no bridge/save/feature mutation; `apply_item` requires the exact current saved-fit revision and session/dataset/generation context. Values are resolved and validated again at mutation time. Older stored graph-envelope versions remain strictly validated, read-only normalized without a write, and migrate on the first effective commit to outer version 7 / damage ledger version 2. Reversal does not downgrade schemas.

Equipment uses a separate selected-item model, preserving drafts in the full pattern library. Item, fit, context, navigation and reopen epochs reject obsolete asynchronous completions, including Back/reopen/fit ABA changes. Pending requests prevent double application. Recoverable reads/refusals preserve the authoritative graph; uncertain writes disable mutation until a fresh reopen determines the durable result.

## Explicit boundaries

Only finite, nonnegative, supported values with a positive total are assignable. Eligible zero-total or invalid items display an unavailable reason and refuse without replacing an existing valid pattern. Original zero-total fallback is not Uniform and remains an explicit parity gap. Global/default patterns, custom or projected reactive-armor pattern binding, interchange and new graph families are not included.

The native singleton, action-time durability and immediate all-affected refresh deliberately correct original transient duplicate/commit/stale-cache behavior. These are not claimed as exact desktop lifecycle parity. Original numeric comparisons use explicitly recalculated matching states, with six documented row exclusions. All existing graph families, raw/effective shield regeneration and projected distance/time rate/accumulated modes remain required.

Existing caps remain: damage requests 16,384 bytes, state responses 524,288 bytes, pages 50 rows, shared history 100 actions, eight graph fits, and unchanged projected/ewar nominal-work admission. No dataset or EOS formula was changed.

## Evidence and qualifications

The original finite reference preflight passed 60 total numerical observations, including five fresh-fit reopen observations, plus 1,206 graph samples. Candidate attempt 2 passed its complete scheduled 55 observations, 1,206 graph samples and 90 damage-route wires across two fresh processes. It covers stale/refused inputs, shared history, old-schema migration, unchanged main-store reopen and uncertain-write recovery. Candidate attempt 1 is retained as failed: its harness incorrectly treated lazy redundant revision-floor cache filling as an effective counter mutation. A narrowly reviewed helper correction retains exact authority/store/history checks, effective-floor equality and only the exact documented raw cache closure for successful no-ops. Product source was unchanged.

All 576 selected Python host methods ran exactly once in 45 fresh-admitted chunks. All 53 exact Kotlin codec/model methods passed with explicit synchronous host support stubs. These are not Android framework, shipping EngineRuntime, Compose scheduling, rendering or device execution claims.

The separately compiled actual-wire consumer covered all 90 damage-route rows, including seven protected native early rejections, and rejected 460 malformed variants of actual wires. Nineteen other-route rows are explicitly outside that codec qualification. Guarded offline main and instrumentation Kotlin compilation passed all 33 tasks in 228.947 seconds. Instrumentation was compiled only, not executed. The inherited engine-staging inspector-attributes fixture limitation is retained explicitly. Exact archive, reconstruction and Library verification belong to external receipts and are not inferred from successful compilation.

Inherited reconstructed-source/supplemental-data, build-metadata and inspector-fixture qualifications remain. Device/offline-device, visual/accessibility, ARM64, signing/upgrade and release gates remain open. No push, install, release or local MSI action is included. The pending prior manual transfer is not superseded by this cloud checkpoint.
