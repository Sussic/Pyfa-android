# G05.1 current remote repair rate versus distance

## Scope and units

An offline graph compares one to eight saved fits. The horizontal axis is distance
in km; the vertical axis is outgoing shield + armor + hull repair rate in HP/s.
Capacitor transfer is excluded by the original graph. This is not target tank or
resistance-adjusted received repair. Source layer readouts are current un-applied
rates, and may differ from a curve with a different ancillary-reload assumption.

Explicit options are ancillary reload, ignore source lock range and ignore drone
control range. Defaults are true, true and false respectively, over 0–100km. Current
source spool settings and source explicit overrides remain authoritative. Empty
fits produce genuine zero curves; no selected fits is a selection state, not a
fabricated result. Invalid requests or calculation errors produce no partial graph.

G05.2 retains specified-time rates, accumulated repair amounts and time curves.
It needs separate cycle-cache/event-work qualification. This child does not close
all desktop remote-repair graph capabilities or all D02 interaction families.

## Source and protocol

Reuse original Distance2RpsGetter/XDistanceMixin/YRpsMixin, range application and
source readout methods. SmoothPointGetter uses50 base intervals with depth2
refinement, at most201 points per fit. Equal/underflow ranges may yield one point;
floating-point rounding may repeat x values or move the final endpoint by an ULP.
Do not clamp, sort, deduplicate or substitute a uniform grid. Native validation
checks the original base/refinement sequence and y-based refinement predicates.

Graph options are isolated to a validated request-local context and always reset.
The supported null-time cache path returns the original early success without
cycle generation. Existing LOCAL preparation and its incoming-object admission
remain active. No new capacitor simulation or resource-limit expansion is added.
Cancellation/deadline checks are cooperative around preparation and each point;
they cannot interrupt an individual EOS call. Native worker ownership persists
until that actual task finishes, even after cancellation or navigation.

Requests bind a durable session context, ordered fit IDs and revisions. Reads must
preserve stored bytes, profile identities, fitting/history state and navigation.
Stale context/revision/replaced-fit callbacks are rejected. Unknown native transport
or protocol failures require reopening the engine.

## Acceptance

- Independent original/current comparisons for ordinary repair, legal partial-active
  maintenance drones, mutadaptive spool, loaded/unloaded ancillary repair and linked
  sources, including edits/undo/redo and fresh durable restart.
- Declared and effective original source settings recorded; source readouts and
  graph ancillary overrides compared independently. Preserve failed diagnostics.
- Exact original adaptive coordinates, finite values, source units and explicit
  tolerance. Current reconstructed source and supplemental data remain disclosed;
  these do not establish clean-pin qualification.
- Boundary, stale, cancellation-during-refinement, deadline, preparation and durable
  failure tests; native strict codec, lifecycle and source-edit-return scenarios.
- Independent review and actual main/instrumentation Kotlin compile. Android tests
  are separately executed evidence; compilation is not Android execution.

Implementation/evidence status is authoritative in STATUS and the candidate receipt.
Android offline/visual/accessibility/ARM64, clean-pin and release/R02 gates remain
open until separately proven. Protected predecessor artifacts are never rewritten.

## Current evidence checkpoint

Independent original/current comparison passed 39 stages,87 fit observations and
129 curves/8,850 ordered points across 10 successful seed/reopen processes. Exact
zero-spool raw representation differences and two linked undo skill-map differences
are recorded with source proofs; they are not hidden by broad raw normalization.
All 83 affected host methods (including 16 new),8 original pure and 8 comparator pure
tests passed. Main/instrumentation Kotlin compiled 33 tasks in 2m34s. All 19 new
instrumentation methods remain unexecuted on Android. See candidate TEST-RECEIPT,
CORRECTIONS, COMPARISON-RESULT and independent reviews for exact scope/bindings.
