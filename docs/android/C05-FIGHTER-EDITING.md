# C05 local fighter editing

## Integrated capability

The Equipment browser can add a fighter squadron to the selected fit. A Fighters
screen exposes independent ordered squadrons, quantity/save/maximum, activation,
implemented abilities, selection-based group state/ability/removal actions and
same-family variations. Quantity zero removes the squadron. Duplicate fighter
types remain separate; the original fighter view deliberately does not merge.

Details show actual bay, total tube and per-category use/capacity. Unavailable
capacities remain unavailable, not fabricated zeros. New squadrons autoactivate
only when both total and category tubes are available. Explicit activation keeps
desktop behavior and can exceed those capacities, with visible warnings. Hull
category restrictions still govern normal additions. Variation replacements use
original eligibility and remove/append order, rather than promising stable row
positions. Logical object identities and fit revisions guard native selection.

## Durable ability states and compatibility

Legacy fighter records `{name,amount,active}` remain valid and retain their
absent-abilities representation when unchanged. An optional `abilities` list
contains the complete, sorted unique pinned effect-ID set and strict Boolean
states. Rebuild rejects missing/unknown effects or activation of unimplemented
effects. Nondefault states are always captured; explicit states survive ordinary
edits, profile changes, copy, undo/redo and restart. The native detail query exposes
implemented abilities only; hidden effect states are retained in persistence.

Six typed ordinary bridge operations own additions, quantities, removals, active
states, ability states and variations. They use the existing expected-revision
contract and single durable graph transaction/history path. A selected ability
is applied to the main squadron plus selected squadrons that actually have that
effect; missing abilities are skipped. Native quantity drafts retain their
revision and require explicit resolution after a conflicting edit.

## Original source semantics

Reference files: `gui/fitCommands/calc/fighter/{localAdd,changeAmount,localToggleStates,
abilityToggleStates}.py`, `gui/fitCommands/gui/localFighter/{changeAmount,changeMetas}.py`,
`gui/fitCommands/helpers.py:FighterInfo`, and `eos/saveddata/fighter.py`.

- Add checks `fighter.fits` and autoactivates according to original tube limits.
- The GUI quantity command removes nonpositive requests; positive amounts clamp
  to EOS squadron maximum. The native Maximum action uses that actual maximum.
  It does not invent meaning for the calc command's -1 path, whose amount setter
  normalizes -1 to zero.
- Explicit group toggles do not silently disable excess squadrons or abilities.
- Variation replacement walks matching selected positions in descending order,
  removes and appends each replacement, carrying quantity, active state and shared
  effect states. New effects retain constructor defaults; unrelated selected
  families are not changed.
- EFT export already reports that fighter abilities and active states are lost;
  it remains an interchange format, not a backup.

## Qualification and remaining scope

The G07 reviewed/compiled checkpoint remains preserved. Targeted tests use the
pinned logical dataset, including carriers/support fighters, durable rollback,
legacy compatibility, full affected publication and source-command comparisons.
Main/test Kotlin compilation and independent review are recorded in the receipt.
No instrumentation or device test has run. Owner-deferred inspector-fixture and
runtime qualification gates remain open, as do release/usability checks.

The original frozen checkpoint had only the “Select same type” shortcut and
explicit multi-selection. The current follow-on adds the source Market-service
group/full-ability-set predicate; see [C05-SIMILAR-SELECTION](C05-SIMILAR-SELECTION.md)
for its separate evidence and exact scope.

The frozen original C05 checkpoint omitted Recent-use promotion. The current
follow-on closes that gap through the existing atomic metadata/history path; see
[C05-RECENT-USE](C05-RECENT-USE.md) for rejected-attempt and quantity-zero distinctions.

Projected fighter editing remains under D01, with linked interaction coverage in
D02; it is not implied by this local editor.
G08 still needs detached-graph isolation proof. The ready queue is reassessed
against technical dependencies after this checkpoint, without turning the device
gate into a blanket development pause.
