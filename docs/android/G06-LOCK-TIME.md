# G06 lock-time comparison

## Bounded integrated capability

The fit library opens a native comparison screen for up to eight fits. Target
signature radius defaults to 25–500 metres. Inputs are finite, ordered and bounded
at 1–1,000,000,000 metres. The graph labels lock time in seconds and reports each
fit's scan resolution in millimetres, or explicitly identifies EOS's scan-speed
fallback. Empty/invalid selections, stale context and unavailable engine results
have explicit states. Changing fit/profile inputs invalidates old curves.

The existing capacitor Canvas is extracted into one small shared plot composable,
retaining capacitor tags, series order and singleton/duplicate-x handling. G06
adds no graph framework or Kotlin fitting formula.

## Source contract

`graphs/data/fitLockTime/getter.py` delegates points to
`fit.calculateLockTime(radius=x)`; this adapter calls that same EOS method.
The x grid follows `SmoothPointGetter._xIterLinear`: resolution means interval
count, so the default is 201 points, or one point for an equal-endpoint range.
Floating-point coordinates are preserved, including representational endpoint
rounding and repeated coordinates in very narrow ranges.

EOS owns the scan-resolution formula and its scan-speed fallback. Missing,
nonfinite or negative lock times fail the entire response. Finite nonpositive or
missing scan resolution is retained because EOS explicitly supports fallback.
No synthetic zero is substituted.

Requests carry session, dataset, graph generation, fit identities and revisions.
The sampler rechecks context, revisions and handle identity before returning.
The native bridge verifies durable storage before and after sampling. No fit,
profile, history or durable input is edited. Derived EOS caches may be populated.

## Bounds and errors

Requests are at most 16,384 characters; 1–8 unique fits; 1–1024 intervals; at most
8,200 returned points. The native UI uses 200 intervals and a 10-second budget.
Cancellation and deadline checks are cooperative between EOS calls, not hard
interrupts of an individual EOS calculation. The native launch gate remains
held until the actual worker completes, including after cancellation/navigation.
Every failed response omits series, so no partial result looks complete.

## Qualification

Focused Python tests use the regenerated pinned logical database hash
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
Source reconstruction combines the recorded public base and dirty source export;
it is not a claim of a clean upstream Git checkout. Earlier supplemental-dataset
receipts retain their original limitation.

Main/test Kotlin compilation, independent source review and source-backed host
comparisons are recorded in the slice receipt. Device instrumentation remains
unexecuted and owner-deferred. Ten inherited frozen inspector assets remain
unavailable; no replacement goldens or weakened acceptance are introduced.
