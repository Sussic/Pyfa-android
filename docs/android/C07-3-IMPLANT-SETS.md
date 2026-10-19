# C07.3 reusable offline implant sets

Status: source-reviewed implementation, finite original/candidate comparison, fresh reopen, composed host regression, actual native codec/model and retained-wire host proof, and offline Android compilation passed with the qualifications below. Exact archive/evidence and Library acceptance belong to external receipts, not to compilation or this document. Device and release acceptance remain open.

## Bounded outcome

Browse and apply the original predefined catalogue; create, rename, duplicate, delete and edit ordered custom recipes; save a fit's currently applied collection as a new set; and atomically merge a set into fit-local implants or an editable offline character. Management and character application work without a fit loaded. Predefined sets are read-only browse/apply recipes, not editable or directly duplicable custom records.

Sets contain ordered type IDs, not activation, destination identities, defaults or live bindings. Later template edits/deletion never change an earlier application. Preserve actual slots, including 79, and original remove/append ordering:

- Fit application skips exact type duplicates, preserving their order, activation and inspector identities; other incoming slots replace/append active rows. Unrelated slots survive. Applying to dormant local implants does not switch the fit's implant source.
- Character application recreates every incoming row active with fresh identities, including repeated application of the same types, while preserving unrelated slots. Built-ins remain protected. Shared-profile and linked-recipient recalculation commits once.
- Save-current uses the authoritative FIT or CHARACTER applied collection, including inactive rows, without modifying it. Empty save-current is rejected; empty custom recipes are valid. Applying a saved recipe recreates new rows active.
- Custom names are trimmed, exact-case unique and Unicode/control-safe. Duplicate-name save-current rejection and unchanged-rename no-op are explicit native consistency differences from the original GUI routes.

Template changes use library history only. Fit application uses its affected fit closure without a template/library dependency, so it can be reversed after template deletion. Character application retains the existing shared-authority timeline, not a live template binding. Strict stale-target/context checks, monotonic revisions, true no-ops at exhausted counters, dirty skill drafts, worker ownership and uncertain-write reopen requirements remain intact.

## Persistence and acceptance contract

Profile-fit envelope v6 adds a detached version-1 set ledger; profile format 2 and existing store/fit-graph schemas remain unchanged. Legacy v1–v5 reads/no-ops do not write migration; the first effective authorized edit writes v6 atomically. Malformed/future/mixed schemas refuse without rewrite. Dedicated implant-set wire v1 preserves feature-v2 and import/export outer-v1. Complete prospective state/bridge publication is checked before durable write.

Both current and dormant collections retain unchanged resource accounting: projected request 134,217,728 nominal units, graph/EWAR 100,663,296 and cold reservation 16,384. These are not measured Android heap guarantees. All existing graphs remain, including G05 current/selected-time rate-distance, amount-distance, rate-time and amount-time; no smaller output, truncated recipe or raised cap substitutes for acceptance.

## Retained results

- Original catalogue: all 56 presets across 23 families, 334 ordered genuine members, no filtering or repeated slots; the grade-less Genolution entry and non-slot-sorted recipes are preserved.
- Finite original/candidate comparison: 26 named states, 114 named fit observations, 342 named raw scalars and 24 G07 points. Separately retained intermediate mutations contribute 348 additional scalars. All 714 scalar encodings compare exactly, including numeric kinds and signed-zero bits, without tolerance. Four fresh-process reopens passed; no-fit reopen adds no invented fit observations.
- Affected host regression: **484 retained inherited successes plus 52 freshly executed C07.3 successes**, exactly the selected 536 methods, without skips or guard breaches. This is not one fresh 536-method run. Three failed campaigns and reviewed test-only corrections remain retained. Count-only resource and detached-surrogate publication witnesses are not numerical parity or malformed-surrogate SQLite reopen proof.
- Actual Kotlin codec/model host compilation and all 92 selected methods passed: 33 inherited, 30 new contract and 29 new model methods, with explicit support stubs. This does not execute Android, Compose rendering or EngineRuntime.
- Offline main/instrumentation Kotlin compilation passed all 33 actionable tasks in 177.112 seconds. All 493 declared methods across 135 instrumentation classes compiled, including C07.3's 30 contract, 29 model and three UI methods. None was executed on Android.
- Independently accepted actual-wire attempt 3 compiled in 22.019 seconds and consumed the retained stream in 2.884 seconds, both exit 0 without guard/postflight errors. It covered 102 events: 101 full request/response codec paths plus one explicitly asserted protected-profile native early rejection; 59 reads, 33 effective commits, six no-ops, three definite failures including that rejection, and one injected uncertain result. All 56 builtin details, 393 response-recipe rows including repeats, 12 operations and 13 coverage witnesses were checked. Attempts 1/2 failed consumer-only premises and remain failed. Inactive different-item slot replacement and same-item already-active recreation are separate witnesses; same-item inactive recreation is not witnessed by this wire. Host wire proof does not execute model lifecycle, EngineRuntime or Android; the separate 92-method host result covers model tests.

Runtime comparison/host source freeze: `8541960641298b4c68cf891f570931632471ca378bf570bf5635fa31f3a15a4e`. Android compile freeze: `81c5599fd438776349e34ec966978c3f3a913dd8380baacfe68efd87432b0800`, retained in `host-correction-3/before/SOURCE-FREEZE.json` before the final pure-Python test correction. Production/native code remained unchanged by that correction. The final source rebind covers the accepted corrected evidence consumer plus documentation, not a documentation-only change; historical compile/runtime manifests and consumer variants remain separate. Native-wire acceptance is bound by `REVIEW-NATIVE-WIRE-RESULT.json`, SHA256 `622ef773111a43e2772df513ed30967b96dfceda8c07a96dc049e86ef30d03d8`.

R3 migration used the reviewed mutable-fixture design. Its original SQLite preimage bytes were not retained; the verified prehash, immutable seed authority, admission/result chain and migrated postimage were retained. They establish the accepted finite migration evidence, not independently reparseable or byte-for-byte reconstructable original SQLite preimage bytes.

Inherited reconstructed/supplemental source/data, non-clean-pin build metadata and missing inspector-fixture qualifications remain. Engine staging stopped at the owner-deferred inspector fixture after staging production sources; successful compilation is not full fixture preparation. Exact-package/Library acceptance is established only by its external receipts. MSI integration, device/offline/visual/accessibility/ARM64, signing/upgrade and release gates remain open.

Global/default implant preferences remain I06.01; additions interchange remains I02.06 and backup/restore I05.02. Destructive collection transfer, ESI, new graph families and live template binding are outside this child. [STATUS](STATUS.md) owns the current execution entry point.
