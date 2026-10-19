# C09.2 local reactive armor patterns

This bounded native module editor exposes the original Armor Resistance Shift
Hardener group's three distinct settings: inherit Fit Pattern, Do Not Adapt,
and an explicit built-in damage pattern. All adaptation and armor calculations
remain in EOS. Built-ins retain source IDs, full hierarchy names, order and
relative component weights; weights are not presented as percentages. Search
and pages bound the native list. Explicit Uniform never becomes inherited merely
because its current components match the fit pattern.

The details query is versioned and bound to fit ID/revision and logical module
identity. Ordinary writes use existing atomic graph publication, history and
rollback. The durable optional `rah_pattern` tag is omitted for inheritance,
`{mode: disabled}` for disabled adaptation, and `{mode: builtin, pattern_id: id}`
for a built-in. Saved null, inherited tags, unknown IDs, extra fields and tags on
unsupported modules reject rather than silently discard state. Existing records
without the field keep their previous inherited behavior. Projection and command
association refreshes serialize these unmapped EOS overrides before refresh and
restore them before recalculation; garbage collection cannot silently turn an
offline hardener into inherited mode.

Custom named patterns are not flattened into built-ins. A custom live override
fails the query with an explicit unavailable message. Creating/editing a named
pattern library remains D05; this slice does not invent a numeric per-module
pattern editor absent from the original menu. EFT export warns that explicit
reactive armor overrides are lost on import.

Do Not Adapt retains the source hardener's base armor resistance behavior; it
is not an off switch. Offline modules retain their selection. Fit Pattern follows
subsequent fit damage-pattern edits; explicit patterns do not.

## Qualification

The prior C09.1 reviewed artifact is frozen separately. See package receipts for
executed host, independent source-reference, fresh-process runtime and native
compiler results. Compilation does not mean Android execution. Device usability,
upgrade/release qualification and the ten owner-deferred inspector fixtures remain
open. Global reload/default persistence and projected-module UI remain separate
C09 dependencies. Source inputs are the reconstructed export plus public base;
older supplemental-dataset receipts remain supplemental.
