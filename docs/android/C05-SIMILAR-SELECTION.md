# C05 similar-fighter selection

Adds a separate Select similar squadrons action beside Select same type. It feeds
existing bulk activation, ability, variation and removal actions, without changing
saved graph schema or selecting anything on the user's behalf at startup.

## Source contract

The original `gui/fitCommands/helpers.py::getSimilarFighters` includes the main
squadron; includes other identical item IDs; otherwise requires the same non-null
Market-service item group and equal nonempty complete ability-ID sets. Other
missing item IDs are skipped. Quantity, active state and ability on/off states do
not affect membership. Full sets include unimplemented abilities, unlike displayed
ability controls. Source order is retained. Market uses item.group, not marketGroup;
the pinned-data independent oracle verifies all 51 forced group exceptions are
ships, not fighters. Catalogue proof covers all 94 fighter anchors.

The read-only query returns fit ID, revision, reference row and ordered matching
row identities. More than 1024 matches is an explicit refusal, never truncation.
The query changes no fit values, revision, profile binding, history or Recent list.

## Native behavior

Only one selection query is outstanding. Captured exact details, main row,
fit/revision and every returned item/object identity must match before applying
selection. Manual selection changes, reload, edits and switching fits discard late
results; ordinary bulk edits keep their existing revision/identity guards. Loading,
empty and failure states remain visible. Known limit errors are explained safely;
arbitrary exception text is not shown. Selected keys survive activity recreation
through the existing retained ViewModel, not durable fit state.

## Evidence boundary

See the current artifact TEST-RECEIPT.json and independent REVIEW.md for executed
host/reference/runtime checks and Kotlin compiler results. Native instrumentation
sources cover codec and retained UI/model races but require later Android execution.
The frozen Recent-use baseline has separate broad numerical/persistence evidence;
that exact-source result is not relabelled as a run on this candidate. Projected
fighters, device usability and the ten owner-deferred frozen inspector fixtures
remain open. The source is reconstructed exported/public source with a verified
pinned logical database; earlier supplemental-dataset receipts remain supplemental.
