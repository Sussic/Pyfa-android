# C07.1 fit-local implant editing

This integrated slice adds native fit-local implant inspection, Equipment add,
explicit occupied-slot replacement, individual/selected activation and removal.
The existing variation editor is reused. Rows are displayed by slot while actions
retain original list positions and logical identities. Queries use real
`item.isImplant`; boosters share a category but are not implant choices. No
invented ten-slot maximum is imposed on source data.

Normal addition removes only the incoming implant's occupied slot, appends the
new implant and uses the source active-by-default state. Bulk activation sets
main plus selected rows to the inverse of the main row's current state. Removal
runs in descending source index order. Successful add/remove promotes Recent use
inside the same atomic graph/history transaction. Variations preserve activation,
do not promote Recent use, and retain the source remove/append semantics: a
different-slot variation leaves the original fitted and can replace another
implant occupying the destination slot.

All three new mutation operations reject structures and character-sourced fits.
This deliberately exposes only fit-local editing. Desktop add can also switch
from character implants to fit implants; C07.2 must implement that separately with
both collections preserved. The current profile model contains skills, not a
character implant collection. Named/predefined sets, their editing/application,
and profile implant persistence remain separate C07 work.

An exact duplicate is unavailable and rejected without changing durable state or
Recent use. This is narrower than the desktop GUI's convenience promotion on a
duplicate add. Replacement confirmation is tied to the displayed fit revision;
stale actions reject instead of overwriting a changed occupant. Existing single
implant wire operations remain available. General implant variation choices and
mutations now enforce the same structure/source eligibility boundaries.

No new saved record type is introduced: existing implant name/slot/active records
participate in graph capture, history, profile recalculation and fresh restart.
EOS continues to calculate every bonus. See package receipts for actual focused,
independent source, runtime and compiler results. Device/upgrade/usability/release
qualification and the missing frozen inspector fixtures remain open. Older
supplemental-dataset receipts are unchanged and remain supplemental.
