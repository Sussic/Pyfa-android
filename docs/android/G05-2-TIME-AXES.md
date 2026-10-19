# G05.2: remote repair across distance and time

## Scope and current checkpoint

The remote-repair comparison provides both repair rate (HP/s) and accumulated repair (HP), against either distance (km) or elapsed time (s), for one to eight selected fits. It plots outgoing shield, armor and hull repair after the selected distance gates. Capacitor transfer is excluded from the plotted HP total, and this is not a recipient-resistance, tank or diminishing-return calculation.

The two time-axis modes are implemented on the accepted selected-time and amount-distance baseline. Source review, the final independent finite/lifecycle numerical audit, all four full resource witnesses, the affected host regression, bounded host-JVM contract/shape proofs, and actual main/instrumentation Kotlin compilation have passed with the qualifications below. Android device execution and release qualification remain separate.

## Choosing a graph

| Horizontal axis | Ordinate | Secondary input and meaning |
| --- | --- | --- |
| Distance (km) | Repair rate (HP/s) | Blank selected time uses the unchanged current-rate route. A finite selected time uses the original cached rate at that time, independently clamped to 0–2500 seconds. Entering 0 is not the same as leaving time blank. |
| Distance (km) | Accumulated repair (HP) | A finite selected time is required. Blank is invalid; 0 is a real horizon and original start-event repair can already be nonzero. The requested time is preserved and its effective value is clamped to 0–2500 seconds. |
| Time (s) | Repair rate (HP/s) | The time range supplies the horizon. Optional secondary distance is entered in km; blank bypasses source distance gates, while 0 km is an actual range. |
| Time (s) | Accumulated repair (HP) | Uses original accumulated event amounts over the time range, with the same optional-distance semantics. It is never calculated by numerically integrating a sampled rate curve. |

Distance ranges remain ordered, finite and nonnegative, with finite metre normalization. Their original adaptive sampling remains limited to 201 points per fit. Time ranges instead accept ordered finite endpoints, including negative values, and independently clamp each endpoint to [0,2500]. For example, requested [-1,2501] becomes effective [0,2500], while [3000,4000] becomes [2500,2500]. The implementation does not sort endpoints, translate the window, or shorten it to fit a resource budget. Requested and effective values remain distinct in the response and visible labels.

For time-axis requests, the secondary time field must be null; a non-null value is rejected before fit preparation. The effective upper time endpoint is the cache-generation horizon. A secondary distance must be null or finite, non-boolean, nonnegative km whose conversion to metres remains finite. The requested distance is echoed in km, while effective distance is normalized to metres. Null remains null, and zero remains zero. The UI retains separate time-range, distance-range, selected-time and secondary-distance drafts when switching modes.

The current-rate distance route retains version 1. Strict version 2 also supports null-time current rate, selected-time distance rate, amount-distance, and both time ordinates. Existing request/context/fit/revision identities, fit order, assumptions and whole-request failure envelopes are preserved.

## Reading original time steps

Time curves preserve the original getter's branch and arithmetic order, including repeated coordinates, vertical changes, first-event overshoot and a source-qualified final segment that can run backward to the effective upper endpoint. Neither the adapter nor the chart sorts, clips, deduplicates, smooths or resamples these points. Chart bounds include an original overshoot rather than hiding it.

A retained original armor-only fixture, using an already-generated 80-second cache for a [0,0] window, returned x = [0,6,6,0] and y = [0,0,256,256]. This is historical getter-shape evidence, not a fresh zero-horizon cache expectation. The first qualifying event is processed before the later upper-bound termination branch. A zero-width window therefore does not justify replacing the result with a single zero, and a curve can contain an event beyond its nominal horizon. An initial-event-only curve may end at that event without a return point. Empty-cache and all-events-before-minimum cases can produce one point; two endpoints are not forced.

Rate at elapsed time 0 is cached-time behavior, not the blank-time current-fit calculation. Original cycle ordering, event overwrites, reload/spool behavior, final-cache snapshots and post-horizon events remain intact. Both internal rate segments and amount events are still generated even when only one final conversion is selected. One application map per fit is used in original key order.

Shield, armor and hull source columns always show CURRENT HP/s, including when the graph ordinate is HP. They are current source rates before distance application and use the fit's own reload settings, not the graph's ancillary-reload override. They should not be read as accumulated amounts or necessarily as the plotted applied rate.

## Cancellation and bounded failure

Changing the axis, ordinate, selected fits, range, secondary input or assumptions invalidates the old graph and requests cancellation. Input drafts and selections are retained, but an in-flight worker keeps ownership until it actually finishes. Back, recreation and late callbacks do not open an overlapping work slot or publish a stale result. The default cooperative work budget remains 10 seconds, with the existing 1–10000 ms request contract. Cancellation and deadlines cannot interrupt an individual EOS call.

Each fit uses a request-local cache with finally cleanup. Invalid input, stale identity/context, cancellation, deadline, allocation admission or encoding failure discards the entire request. There is no partial graph, invented zero, reduced fit list, shortened horizon or downsampled fallback.

## Resource and wire limits

The unchanged whole-request allowance is 100,663,296 nominal allocation units across all fits. It is conservative host-layout-equivalent accounting, not Android heap bytes, RSS, a latency promise or a guarantee that every legal fit will be admitted. The ledger is monotonic with no cleanup refunds. The time implementation has explicitly bounded transient scalar/token coexistence reservations in addition to cumulative retained-object and schedule/cache costs.

The first complete no-reload amount witness was correctly refused at the default allowance during the seventh fit, with a complete error and cache cleanup. That failed attempt remains evidence. A reviewed time-only change then removed actual temporary RR accumulator/product objects and reserved 10,752 nominal units of bounded scalar coexistence scratch once per request. It preserved original arithmetic order, the guarded custom-object fallback, all prices and the allowance. It did not merely discount unchanged allocations.

All four final full eight-fit, 2500-second production-default witnesses now pass:

| Ordinate | Ancillary reload | Nominal units | Output points |
| --- | --- | ---: | ---: |
| Repair rate | Off | 65,631,104 | 58 |
| Repair rate | On | 47,557,632 | 612 |
| Accumulated repair | Off | 99,240,256 | 12,424 |
| Accumulated repair | On | 69,928,832 | 8,534 |

The tightest witness leaves 1,423,040 units, about 1.41% headroom, and produces 182,755 ASCII wire characters. Each request prepared all eight fits; independent repricing verified per-kind, per-fit and phase totals, final source bindings and cleanup. Separate unmodified production-route reruns asserted complete parsed-JSON equality. Their paired raw strings/arrays were not separately retained, so this is a bound execution assertion, not an independently replayed byte-for-byte wire comparison.

Each emitted time pair is precharged 1,152 units for retained output and serialization, with 32,768 base serialization characters reserved once. Exact encoder numeric tokens for x and y must total at most 62 characters before either coordinate is appended. Oversized integers are rejected before unbounded decimal conversion; the token probe has separately reserved bounded scratch. Encoding occurs once inside the reservation guard, with a post-encoding length invariant.

These unchanged charges imply an absolute ceiling of 87,210 time pairs across the whole request and 5,614,208 ASCII wire characters. Positive generation, conversion and other costs normally make admission stricter. The ceiling does not replace admission or give each fit a fresh allowance. Distance routes retain their existing sampling and fixed serialization policy.

The native boundary checks the real raw response string before JSON parsing, then checks each coordinate-array length and the cumulative total before downstream Double-list copies. The bridge has already materialized the raw string before this guard. The time-only strict parser bounds numeric tokens to 310 characters before substring/BigInteger creation and accepts only finite normalization; identity/revision/count metadata retain strict integer rules. Source-shaped coordinate validation allows the original degenerate step cases but rejects unrelated reversals. This checks the wire/shape contract, not the truth of hidden cache events. Native Double storage can round very large generic integers; at integral magnitudes of at least 2^53, shape admission conservatively permits collapsed change pairs. The shared chart retains original vertex order and also allocates references for extrema. No native heap-byte bound or exact arbitrary-integer chart representation is claimed.

## Evidence and remaining gates

Independent source review reproduced 11,715 original-getter synthetic cases and 7,380 scalar arithmetic cases. The actual extracted Kotlin shape validator passed 11,737 cases on the host JVM. All 22 actual request/codec contract methods passed using cached org.json/JUnit with the Android runner removed. These are host-JVM proofs, not Android compilation or model/UI/device execution. The Android remote-repair test sources now contain 42 methods: 22 contract, 15 model and 5 UI methods.

All 153 affected host regression methods passed exactly once in eight bounded chunks, with no skips or expected failures, 49.54 seconds total recorded chunk time, and 1,424 unchanged source/input bindings.

The finite original corpus contains 2,422 time curves, including 267 nonsorted shapes. Only 988 have the exact generation horizon needed for fresh-request comparison; the other 1,434 are retained-larger-horizon observations and remain historical shape evidence. Expected fresh boundary values come from frozen independent original maps and original AST execution, not candidate formulas or larger retained horizons relabelled as fresh caches.

The final ten source-bound processes retain 2,249 observed reads, 2,138 successful series, 86,691 points and 195 complete errors. These totals include repeated baselines, recoveries and compatibility checks, rather than unique independent original witnesses. Four additional unmodified production resource-counterpart calls are excluded from these retained totals; their parsed-semantic equality remains an assertion-bound check.

Independent retained-array comparisons passed for 1,748 time curves / 64,135 points, including 150 nonsorted original-shaped curves: 988 direct exact-horizon curves (956 lifecycle and 32 resource), 592 fresh original-AST boundary curves, 104 fresh clamp/signed-zero curves, and 64 full-eight-fit clamp/one-point curves. A further 254 selected-distance rate/amount curves / 18,174 points match their originals. Fourteen current-rate version-1/version-2 pairs establish complete compatibility equality, not new independent current-rate golden curves. There are 6,006 current HP/s source-column comparisons. Ordered coordinates and requested/effective echoes are compared exactly; y retains relative 1e-10 / absolute 1e-9 tolerance with exact original zero, without tolerance widening.

The matrix includes ordinary, drone, spool and ancillary behavior, linked edits/undo/redo, and a separate durable reopen/deletion process. Both final fresh lanes retain 84 complete errors and 52 independently checked same-request baseline-equal immediate recoveries each. Together the 104 recoveries cover 96 phase-specific refusal/cancellation/deadline/stale cases and eight genuine ledger guards: four cumulative signed-63 counter refusals and four priced arithmetic overflow refusals. This is not a claim of immediate recovery for every one of the 195 errors, nor of physical allocator exhaustion for injected refusals.

The first final fresh amount attempt is retained separately and excluded from accepted totals: it stopped after 414 reads because the harness overconstrained the wording of a correctly returned real counter-overflow refusal. The reviewed retry separated real counter overflow from priced arithmetic overflow and left production code unchanged. Earlier pre-scalar successes and the initial resource refusal are also historical evidence, not relabelled as final-freeze acceptance.

Actual guarded offline main and instrumentation Kotlin compilation passed 33 tasks in 179.49 seconds. All 946 compile-bound source/input paths, shared bytes and modes, the database and existing minimal Git metadata remained unchanged. The 93 staged bridge files were verified; the inherited missing inspector-attributes fixture remained an explicit staging qualification. The expected preparation exit for that missing fixture was not a compiler failure, and this candidate's actual compilation passed without a failed compile attempt. All 42 Android remote-repair methods compiled only; none were executed as Android instrumentation or on a device. The separately executed 22 host-JVM contract methods and 11,737 extracted shape cases do not change that distinction.

Reconstructed/supplemental source and dataset qualifications remain: the physical dataset hash is reverified, while the logical hash is inherited rather than recomputed. Each final EOS process has 539 verified before-run source/helper snapshots and exact before/after bindings; the recorded candidate-module imports do not constitute a complete interpreter/third-party dependency manifest. Retained arrays support independent numerical replay. Internal-map/cycle equality, raw-input equality, cleanup, durable immutability and unmodified counterpart equality remain source-bound execution assertions because paired candidate internal arrays and before/after durable database bytes were not independently retained.

The retained seed output and persisted checkpoint, including the store SHA, match. The separate reopen process rejects the old request and asserts seed durable equality, unchanged boot bytes and empty histories before deletion. Its premanifest omitted the input store/checkpoint, so this is a retained seed/checkpoint anchor plus bound execution assertions, not retrospective before-boot manifest proof. Fixture-ID normalization, four inherited spool representation differences and two linked dependent-skill undo differences remain explicit. In the qualified source_a/source_b non-capital undo fixtures, the original dependent skill None resolves to zero while the candidate All-V restoration resolves to five; this does not establish general dependent-prerequisite undo parity or universal raw-state equality. The local minimal Git metadata used for source enumeration does not establish an independently clean upstream pin.

Exact-byte delivery verification is owned by the external final package-audit receipt for the delivered artifact, not inferred from this source/compile document. Its verified result determines package completion. Android execution, offline operation, visual/accessibility verification, ARM64, missing inspector-fixture qualifications, clean-pin, MSI integration and release remain separate open gates. Previous selected-time and amount-distance documents remain historical checkpoints; this document records the combined mode semantics and accepted source, numerical, resource, host and compile evidence without extending those results to the remaining gates.
