# G07 mobility comparison

## Integrated scope

Compare up to eight saved fits through the shared native graph surface. All five
original modes are retained: speed (m/s), distance (km), momentum (Gkg⋅m/s), bump
speed (m/s), and bump distance (km). Time defaults to 0–30 seconds. Bump modes
expose target mass, default 1300 million kilograms; bump distance also exposes
target inertia, default 0.015. Draft target inputs survive switching modes, but
only applicable inputs cross the calculation boundary.

For bump modes, x is the source ship's acceleration time before impact. Bump
distance is the target's total post-impact drift, not distance at x seconds.
The original graph's extra column named Agility actually displays fit align time;
this UI labels maximum speed and align time distinctly from the target inertia.

## Source fidelity

`mobility_math.py` retains the original GPL notice and unchanged calculation
method bodies from `graphs/data/fitMobility/getter.py`. Only its desktop sampler
base/import is replaced by a plain base because the adapter invokes the original
common-data and point methods directly. There is no Kotlin fitting calculation.
`graphs/wrapper.py` confirms fit maximum speed uses modified maxVelocity. The
original graph normalizes target Mkg to kg, distance metres to km, and momentum
kg⋅m/s to Gkg⋅m/s; the adapter follows those exact conversions.

Time/target defaults and desktop defaultRange fields are not hard limits. Inputs
here require finite, nonnegative, ordered time and applicable finite nonnegative
target values, including zero. Overflow in normalization or the original formula
fails explicitly; no invented zero/clamping is used. Source ship mass/inertia
must be usable positive finite values. Output preserves finite original rounding,
including cancellation near zero; no monotonic-y assumption is imposed.

The x grid follows original SmoothPointGetter arithmetic. Resolution counts
intervals; default 200 produces 201 points, except equal endpoints or a step which
underflows to zero produce a singleton. Native decoding checks the computed grid
with a tight ULP tolerance; no absolute tolerance disguises tiny-time errors.

## Isolation, bounds and qualification

The versioned request is capped at 16,384 characters, eight unique fits, 1024
intervals and a cooperative 10-second maximum budget. Context, revisions, handle
identity and before/after durable checks prevent stale or externally modified
results. No partial curves are returned after a failure. Cancelling/navigation
holds the launch gate until the actual serialized engine call finishes.
Sampling does not change fit/profile/history/storage inputs; EOS may populate
derived caches. Missing or malformed metadata remains explicit.

The source-only G06 checkpoint is preserved. The G07 work copy reuses its frozen
staticdata read-only through a local link, avoiding another dataset/cache copy;
that link is not part of the delivered source overlay. Host proof uses the pinned
logical database hash recorded in the receipt. Reconstructed-source provenance
and earlier supplemental-data disclaimers remain intact.

Main/instrumentation Kotlin compile and independent source comparisons are
recorded in the receipt. Device tests and ten inherited inspector fixtures remain
owner-deferred; compilation does not close runtime, usability or release gates.
