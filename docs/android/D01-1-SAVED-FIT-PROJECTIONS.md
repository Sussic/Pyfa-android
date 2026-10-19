# D01.1 saved-fit projection management

This bounded F15.04 slice exposes existing durable saved-fit links through the
recipient's native editor. It does not complete the individual projected module,
drone/fighter or selected-row bulk editors, nor the entire D02 interaction matrix.

## Source-policy boundary

The replay-level add/configure/remove projection helpers remain unchanged. They
must reconstruct exact saved values, including older counts above20. Five new
atomic UI operations follow original projectedFit commands instead:

- Add a saved source with quantity1, enabled and default/null range. Adding an
  existing source increments its count, clamped to20; range/state are retained.
- Explicit positive quantity is clamped to1..20; zero removes the whole link.
- Change range or enabled state independently, retaining the other raw values.
- Remove the complete association. A missing/deleted endpoint fails safely.

Both endpoint revisions are required, with one key for self-projection. Self and
reciprocal links are supported by EOS; no invented blanket cycle prohibition.
No Kotlin read/modify/write loop supplies duplicate increments. No new saved
schema or read query is introduced. Existing snapshots/library are authoritative.

The original add and count wrappers always flush/recalculate/fill. Add, removal,
changed state and changed range perform their original state reconciliation;
positive quantity-only changes do not. The existing adapted check_states uses
EOS canHaveState/isValidState. A real scrambler projection disables an active MWD
by changing its captured state to ONLINE. Ordinary graph history restores both
link fields and dependent module inputs exactly, including unusual legacy counts
and nullable range; it does not inherit desktop command undo's lossy edge cases.
The graph transaction is the only durable commit authority.

## LOCAL read preparation

Independent reciprocal-link checks exposed an existing EOS cache boundary:
PROJECTED calculation may mark a source calculated without retaining that source's
own incoming projections. COMMAND calculation can likewise leave a cold source
marked calculated without its own local burst bonus. That flag alone cannot
authorize a LOCAL output read.
Original per-endpoint LOCAL calculation and immediate snapshot freezing agreed on
all39 sampled fields; merely reading both post-command caches did not.

The adapter now prepares every requested endpoint in LOCAL mode immediately
before freezing its output, retaining existing command-source warming. Live detail
and option queries use the same boundary. Local-fit edit dispatch also prepares
the endpoint before deriving a state/slot/eligibility decision; a direct bulk
click after PROJECTED evaluation must follow the original LOCAL transition.
Source/target link operations retain their original recalc/check ordering.
Graph samplers accept a separate trusted preparation
callback before each series; capacitor simulation prepares again after all capacity
validation. Identity resolution remains side-effect-free, and cooperative budget/
cancellation checks surround preparation. No EOS formulas, link eligibility or
saved inputs change. Exact read-only persistence/history/context and alternating
endpoint results require explicit regression evidence.

Capacitor preparation additionally clears the LOCAL calculation cache even for
fits without incoming projections. EOS caches simulation events by starting
capacity alone: a preceding capState snapshot can leave six-hour results which
getCapSimData would otherwise reuse for its normal one-hour simulation. The
adapter requests a fresh one-hour calculation rather than weakening event bounds
or changing EOS. The independent real command/projection regression covers this
interaction and compares the source-backed simulation output.

## Native workflow

The recipient editor offers a searchable local source picker, incoming link rows,
quantity/range drafts, active controls and removal. Range displays kilometres;
wire and EOS use metres. Blank/default is null and differs from explicit zero.
Actual unusual stored counts remain visible until explicitly edited. Retained
drafts are bound to exact endpoint identities/revisions and require deliberate
review after staleness. Source navigation retains an explicit return destination.
Undo/redo remains available through the existing history system.

## Verification boundary

Source references: gui/fitCommands/calc/projectedFit/{add,changeAmount,
changeProjectionRange,changeState,remove}.py, gui/fitCommands/gui/projectedFit/
{add,changeAmount}.py, generic projectedChangeStates/projectedChangeProjectionRange/
projectedRemove wrappers, service.fit.checkStates and EOS projection calculation.
Independent expected behavior must come from these original bodies and pinned
EOS data, not the new helper. Runtime/history/rollback/restart and native compiler
results are recorded separately in the current artifact receipt. Compiled native
tests are not Android execution. Existing fixture/device/release gates remain;
reconstructed-source and supplemental-dataset provenance limitations are retained.
