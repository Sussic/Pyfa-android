# I01 outbound EFT: integrated bounded slice

The selected saved fit has a read-only EFT export preview with retained inclusion
choices, then explicit Copy, Save and Share actions. Export requests bind the
session/dataset/generation, fit identity and revision. Durable graph freshness is
verified before and after rendering. Stale, missing, unavailable or invalid data
returns no usable text. Export never changes the fit, graph, history or import
receipt. Android file-picker cancellation is not a successful save.

## Representation and limitations

Rendering follows pinned `service/port/eft.py` at commit
`8b04f3b271e614b3e103853b44a7851a63d79d0e`: low/medium/high/rig/subsystem/service
order, empty positions, loaded charges, offline suffix, drone/fighter ordering,
implant/booster slot ordering and cargo ordering. The existing headless market
policy retains forced drone market groups. Names unsafe for EFT (including line
breaks, controls, delimiters and surrounding whitespace) fail explicitly.

Choices cover loaded charges, cargo, implants, boosters and mutated attributes.
Mutation-detail serialization is still unsupported: enabled mutations on a
mutated object fail; disabling that choice intentionally exports base types and
shows the loss. Unsupported abyssal cargo without its record fails. This is not
full I01 closure or a replacement for C10 mutation interchange.

Every preview says EFT is not a backup. It omits skills/profiles, notes, linked
fits, environments, damage/target/security settings and history. Diagnostics also
identify non-offline module-state ambiguity, drone active counts/fighter states,
booster side effects, intentional exclusions, unsupported current Android
re-import addition types and all-drone cargo reclassification. Do not claim exact
round-trip fidelity for these fields.

The importer now accepts a section containing only matching explicit empty-slot
labels, discarding trailing vacancies exactly as desktop `_clearTail` does.
Mixed-rack vacancy sections still fail. Hull-defined vacant positions are rebuilt
by EOS; unsupported subsystem cases remain explicit failures.

## Verification boundary

Host tests compare the actual pinned desktop export function bodies with the
renderer, including all 32 inclusion combinations, then exercise real EOS and
atomic import against the verified pinned logical dataset. This is narrowly
source-backed EFT proof, not the full desktop GUI/reference qualification suite.
Native main/test compilation is required for the final source checkpoint.
Instrumentation tests remain source/compile evidence until run on Android.

The owner deferred fixture transfer and device tests. Those gates remain open;
they do not block independent, integrated implementation. No clipboard operation,
file-provider write or third-party share is executed by cloud tests on the user's
behalf. Runtime usability, provider errors/cancellation and lifecycle behavior
still need actual Android qualification.

## Short ready queue

1. Finish and review this integrated I01 export slice; retain all deferred gates.
2. G06 lock-time graph: C03-backed, calls EOS `calculateLockTime(radius)`, uses the
   shared plot surface with target signature radius in metres and lock time in
   seconds. No new profile schema or missing inspector fixture is needed to
   implement/compile it; device acceptance remains separate.
3. Reassess the next existing dependency-ready row after that integrated review.
   Do not expand into unrelated features or accumulate standalone backend drafts.
