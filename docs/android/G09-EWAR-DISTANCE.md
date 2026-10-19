# G09: electronic warfare versus distance

## Scope and checkpoint

Electronic warfare comparison adds the seven original `fitEwarStats` distance
ordinates to the existing offline graph surface. Select one to eight saved fits,
choose an ordinate, and plot the complete comparison with explicit resistance,
source lock-range and drone-control assumptions. It uses the existing serialized
EOS worker and shared chart, not an independent Kotlin calculation engine.

Source/schema/admission and native-source reviews have passed. The actual Kotlin
request/response contract passed all 15 focused methods on the host JVM, and its
actual adaptive-coordinate validator passed 1,656 original-sampler and mutation
cases. These are host proofs, not Android compilation or device execution.
Independent audit of the full finite seven-family original/candidate comparison
passed 5,128 curves / 88,410 points, with 5,206 exact request/response wire pairs
retained. This is finite-fixture evidence under the reconstructed/supplemental
source and dataset qualifications, not universal-fit parity. A separately audited
host-JVM run of the full actual Kotlin codec accepted 1,262 retained wire pairs:
1,259 successes, three complete errors and 59,892 points, with zero skipped pairs.
That finite subset is not all 5,206 parity wires. Separate resource/lifecycle
audit accepted ten successful lanes with 55 wires, 156 original-equal series and
11,536 points, including nine actual lifecycle states, undo/redo and fresh reopen.
Failed harness attempts remain retained and are not counted as passing lanes.
The 52 initial viability pairs are separate from the full-parity totals.

All 225 affected host methods passed exactly once in 12 bounded chunks, without
skips and with unchanged inputs. Guarded main and instrumentation Kotlin
compilation passed 33 tasks in 164.065 seconds, with exit 0 and no guard trigger.
The 30 new Android methods are 15 contract, 12 model and three UI methods: compiled
only, not executed on Android. Existing G05.2 remote-repair modes, G04 shield
regeneration and earlier graph routes are retained. Their earlier accepted
evidence is not a new G09 device run. Exact-byte package verification
and final documentation/source rebind remain external-receipt delivery gates.

## Choosing a comparison

Open **Electronic warfare comparison** from Home. Search and page through saved
fits, select up to eight, then choose one ordinate:

| Original quantity | Visible meaning | Original Y-axis unit |
| --- | --- | --- |
| `neutStr` | Cap neutralized per second | None specified (`null`) |
| `webStr` | Speed reduction | `%` |
| `ecmStrMax` | Combined ECM strength | None specified (`null`) |
| `dampStrLockRange` | Lock range reduction | `%` |
| `tdStrOptimal` | Turret optimal range reduction | `%` |
| `gdStrRange` | Missile flight range reduction | `%` |
| `tpStr` | Signature radius increase | `%` |

The two absent units are preserved, not silently replaced with percentages,
`GJ/s`, the text `null`, or another invented wire unit. ECM sums each contributor's
maximum racial strength; it is not jam probability. The other ordinates describe
the original effect, not a full target-fit or target-profile simulation. Signed
outputs and values outside 0–100 are preserved, including for percentage axes.

Distance is entered in kilometres. Defaults are 0–100 km. Both endpoints must be
finite and nonnegative, ordered from start to end, and remain finite after
conversion to metres. The app does not silently reorder the draft, shorten the
range, or choose a smaller selection to make a request succeed.

Target EWAR resistance defaults to 0%. Blank is a real unspecified value, not an
input error and not an invented numeric zero in the request. The original getter
uses zero resistance when unspecified. Finite requested values are divided by
100 and then clamped to [0,1]. For example, -25% has effective fraction 0, 37.5%
has 0.375, and 250% has 1. Requested and effective values remain separately
visible; clamping does not overwrite the draft. Nonfinite values are rejected.

**Ignore source lock range** defaults on. **Ignore drone control range** defaults
off. These are request-local graph assumptions and do not edit saved fits or
persistent global graph settings.

## Preserving the original curve

The engine uses the original 50 base intervals and depth-two adaptive sampler.
A fit produces at most 201 ordered sample pairs; eight fits produce at most
1,608. A zero or underflowed normalized step yields one point. Original floating
rounding can repeat coordinates or move the final sample slightly beyond the
requested endpoint. The chart includes that endpoint drift without changing the
samples. No sorting, deduplication, clipping, uniform resampling or downsampling
is used to manufacture a smoother result.

Adaptive refinement follows the original endpoint-value predicates and captured
recursion behavior. The native boundary validates those source-shaped sequences;
it does not independently calculate the expected EWAR values. Finite generic
integer values are not restricted to `Long`. Integer/float comparisons used to
validate adaptive branches preserve the source numeric distinction before chart
conversion. The chart itself uses `Double`, so very large distinct integers can
share one displayed numerical coordinate; arbitrary-precision rendering is not
claimed.

Source effect families retain their separate behavior:

- Ordinary modules require source lock range unless ignored. AOE branches bypass
  that lock gate and use the original nonnegative AOE effective range.
- Drones require lock and drone-control range unless each respective gate is
  ignored. Fighters require lock range but not the drone-control gate.
- Equality at a range boundary is allowed. The original restricted falloff is
  zero strictly beyond optimal plus three falloffs.
- Neutralizers add in source order and retain original cycle-duration/reload
  handling. Nosferatu contributes only when the original `nosOverride` permits
  it. No graph capacitor simulation or cycle-event iteration is introduced.
- Web, damp, tracking disruption and painting retain the original separately
  sorted positive/negative multiplier stacks. Guidance retains two independent
  velocity/time stacks and multiplies their resulting multipliers.
- Six modes retain repeated local-drone contributions for active quantities;
  guidance has no invented drone branch. Supported fighter ability quantities
  scale a contribution rather than creating repeated drone-like entries.

The original reference remains [the EWAR getters](../../graphs/data/fitEwarStats/getter.py)
and [the shared original sampler](../../graphs/data/base/getter.py). Source reuse
and finite reference proof do not establish correctness for every possible fit.

## Cancellation, invalidation and read-only behavior

Changing an ordinate, selected fit, distance, resistance or range assumption
invalidates the old graph and requests cancellation. Back and recreation preserve
retained drafts and fit selection. Search pages keep duplicate-named fits
reachable, and an explicitly empty selection remains empty.

Cancellation is cooperative. A running EOS call may need to finish before another
plot can start. Its actual worker retains the busy slot during that time; a late
callback cannot publish stale samples or release another task's slot. The default
work budget is 10 seconds, with the existing 1–10,000 ms request range. It is not
an interruption guarantee for an individual EOS call or a maximum UI wait.

Successful output must include every requested fit, in request order, with
matching context and revisions. Stale or replaced inputs invalidate the whole
result. Graph reads do not intentionally change durable fit inputs, history,
profiles, Recent or navigation. Admitted LOCAL preparation may recalculate derived
caches; this is not a claim that all internal engine memory stays unchanged.

Invalid input, stale inputs, cancellation, deadline expiry, invalid/nonfinite
engine data and resource refusal produce explicit complete errors, without a
partial curve or a fabricated zero. A valid all-zero curve remains distinguishable
from failure. Unknown transport/protocol outcomes retain the existing
restart-required handling.

## Resource refusal and strict wire bounds

Preparation admission runs for the complete selected request before its first
LOCAL preparation, including local-only drone/fighter workloads that do not have
incoming objects. It uses the authoritative normalized records and linked-source
closure. The existing incoming-effect guards and their legacy defaults are not
replaced by an unrelated preparation framework.

The whole-request graph allowance remains **100,663,296 nominal units**, with no
per-fit reset or cleanup refund. Existing preparation limits remain **16,384 cold
units** and **134,217,728 request-work units**. These ledgers model different work
and must not be added together or described as measured bytes. Admission reserves
bounded record/snapshot scratch, common-data expansion, multiplier/filter/sort
work, output and serialization before their relevant allocations.

If admission fails, the result is `resource_exhausted` for the whole request.
There is no truncated quantity, shortened range, combined drone multiplicity,
partial fit list or wider allowance fallback. A refusal can therefore be the
correct result for a finite legal fit. The nominal model is not an Android heap,
RSS, performance or universal-fit guarantee; general EOS/cache behavior remains
subject to the recorded source and execution qualifications.

The version-one route is `offline_ewar_samples`. Its request carries context,
ordered fit identities/revisions, distance/ordinate metadata, nullable requested
resistance, two Boolean range assumptions and the cooperative budget. A success
also carries normalized metre endpoints and nullable effective resistance,
complete ordered series and an exact total. A failure carries only its version,
correlated or not-yet-established request identity, and bounded error.

The raw request bound is 16,384 characters. The raw response is checked before
native JSON parsing against **1,036,160 characters**, then against
**32,768 + 624 × actual total points** for success. Generic finite numeric tokens
are limited to 310 characters before conversion. Protocol integer fields retain
exact signed-63 integer rules; identity strings are 1–128 Unicode codepoints and
error messages at most 1,024. Duplicate/unknown keys, incorrect
units, malformed types, incomplete comparisons and mismatched requested/effective
values are rejected. The bridge has already materialized its raw string before
the native parse guard, so that guard alone is not a native memory bound.

## Evidence and remaining delivery gates

The source-bound host receipt is `native-contract-proof/EXECUTION-VERIFY.json` in
the associated G09 evidence package: 15 actual contract methods and 1,656 original
sampler/mutation cases, with unchanged bindings. Android runner annotations alone
were removed for host JUnit; no model or UI device execution follows from it.

The separate actual-wire harness consumed exact request/response bytes retained
by completed candidate lanes. Its audited 1,262-pair run includes all seven modes,
original null units, nullable/negative/above-100 requested resistance, eight-fit
output, cancellation, natural resource refusal and successful immediate recovery.
Every indexed pair was accepted by the unchanged full production Kotlin codec;
all wire hashes, case receipts and reviewed source/harness bindings were checked.
The receipt is `native-wire-proof/ACTUAL-SUBSET-EXECUTION-VERIFY.json` in the G09
evidence package. This is host parser acceptance, not a numerical oracle or
Android execution. Corrected lifecycle and fresh-reopen lanes are not included
in this wire run and keep their separate evidence.

The accepted resource/lifecycle audit is `REVIEW-G09-SUPPLEMENTAL-EVIDENCE.json`,
SHA256 `900b195f7c06c8bd947182334bc599ea4e8cc42aa956a579d467d1a593945312`.
Its ten successful lanes retain exact source bindings and the failed harness
attempts separately. Finite resource witnesses do not establish a universal
memory guarantee, and engine lifecycle evidence is not native UI execution.

The host regression receipt is `host-regression-attempt-1/HOST-REGRESSION-RESULT.json`:
153 inherited methods, 63 G09 pure methods, four legacy drone guards and five
legacy fighter guards passed, with 58.578 seconds of recorded chunk execution.
The compilation receipt is `native-compile-final-result.json`; observed minimum
available memory was 6,370,942,976 bytes, not an app-memory measurement.
`COMPILE-SOURCE-FREEZE.json` preserves the exact 965-entry compile manifest,
SHA256 `755224bcf06af0371e706f1ac68435ffd8bda8c07bd6809f9cdd0fea88f954d9`.
Final documentation updates require an explicit separate rebind; they do not
rewrite the compilation's source identity.

Final delivery still requires independent final review, the documentation/source
rebind and external exact-byte package verification for the final revision,
alongside the accepted finite original, resource/lifecycle, actual-wire, host
regression and compile receipts. The explicit deferred native phase
is [ewar_graph](../../android/ci/offline/ewar-native-phase.json); older launchers
are not claimed to schedule it automatically.

Android instrumentation, offline/restart operation, visual/accessibility review,
ARM64 execution, MSI integration, missing inspector-fixture qualifications,
reconstructed/supplemental inputs, independent clean-pin proof, signing/upgrade
and release remain separately open. G08 isolation, G10, named profiles and shared
graph export/overlay closure are outside this G09 slice. See
[STATUS](STATUS.md) for the current authorized next action and
[the roadmap](ROADMAP.md) for their owners.
