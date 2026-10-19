# D03.1 saved command-fit management

This bounded F16.01 and link-persistence F16.04 slice exposes saved command-source
associations through the recipient editor. It does not complete all command
families, strength/range/duration displays, multi-source winner/overlap coverage,
or shared character implant collections.

## Source policy and durable graph

Three UI operations use exact source/target revisions and the existing atomic
transaction, saved records, publication and history. `add_command_fit` inserts an
enabled association if absent; adding an existing source is a no-op preserving
its current state, not a quantity increment. `set_command_fit_active` uses a strict
boolean desired state corresponding to the original single-row forced-state
path. `remove_command_fit` removes the association. Missing/deleted links fail
safely, and history restores the exact preceding state. No saved schema expands.

The replay add/state/remove helpers remain unchanged. The new policy directly
follows original calc/commandFit mutations and the GUI flush/recalculate/fill
boundary, without checkStates or internal durable commits. Addition preserves
inspector identities and unmapped reactive-armor inputs across the original source
refresh and clears derived caches before the outer recipient calculation.
Removal does not add an unnecessary refresh. Duplicate/no-op actions do not
fabricate history or a newly-added success claim. An ordinary successful API
dispatch can still publish a new revision, even when captured inputs do not
change; native duplicate/current-state controls avoid dispatch altogether.

Both self and reciprocal associations are supported. Original EOS skips an
incoming self command association; the fit's own local burst effects still apply.
A saved fit with no active appropriately loaded burst may validly produce no
bonus. The original ship browser and drag/drop permit any saved fit, while a
convenience menu filters real module group1770. The native all-fit picker does
not invent eligibility from names or market categories.

## Native workflow

Search/page saved fits, inspect incoming command rows, add a source, change its
enabled state, remove it, open the source and explicitly return to the recipient.
The current source module/charge, C06 profile and C07.1 fit-local implant editors
supply the bounded workflow's inputs. Shared character implant collections and
source selection remain C07 scope. Stale/deleted endpoints and unavailable or
pending states cannot silently submit or repaint another recipient. Existing
undo/redo and activity recreation remain supported.

## Verification boundary

Original references: gui/fitCommands/calc/commandFit/{add,toggleStates,remove}.py,
gui/fitCommands/gui/commandFit/{add,toggleStates,remove}.py, the commandFitAdd menu,
builtinShipBrowser/fitItem.py, builtinAdditionPanes/commandView.py and EOS fit
command calculation. Meaningful proof uses actual A05 Vulture/Shield Command
Burst II, Shield Extension/Harmonizing charges, two recipients, profile skill and
fit-local Shield Command Mindlink edits, cold/read-order effects, history and
fresh restart. Independent expected values must come from original source and
frozen fixtures, not this helper.

The prior D01 LOCAL read, options and local-edit boundary plus capacitor reset
remain intact. Test/compiler results are recorded separately; compilation is not
Android execution. Ten frozen inspector fixtures and device/upgrade/release
qualification remain owner-deferred. Reconstructed-source and earlier
supplemental-dataset provenance limits remain unchanged.
