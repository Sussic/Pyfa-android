# G04 shield regeneration comparison

Current state: independently reviewed source/host/compile checkpoint; final package
audit pending. This is not Android execution or release proof.

## Bounded capability

The complete original fitShieldRegen family has three X choices (time, shield
HP/EHP, shield %) and two Y choices (shield amount or regeneration rate), each
with coupled raw/effective mode. Shield-X range inputs are always percentages;
per-fit capacity/resistances determine plotted HP/EHP coordinates. Time-X accepts
starting shield %, including blank/null as the original zero default. Finite signed
and reversed endpoints preserve the source API; desktop typed range syntax was
unsigned and is separately qualified. Percent/start limits are original per-fit
clamps, not new gameplay gates. There is no invented time ceiling or Y floor.

Up to eight selected fits use the existing serialized offline EOS session. Each
series shows current raw shield capacity/recharge and four damage contributions.
Original graph/getter methods, normalization, sampling and effective conversion
supply the numbers. Fixed 200 intervals normally yield 201 samples; underflow or
equal bounds yield one; zero-capacity percent identity can yield the original two
requested endpoints. Preserve duplicates, order and valid signed results. Undefined
arithmetic or nonfinite final outputs produce an explicit whole-request error.

The screen retains mode-specific range/start drafts, pagination and selection.
Changing inputs or source state invalidates old results. Cancellation is cooperative;
worker ownership stays held until completion, including navigation/recreation.
Graph reads do not simulate capacitor or generate cycle events. Inherited source
preparation is separately resource-admitted and is not an interruptible call.

## Dependencies and exact boundary

C01.3.1 provides fit-local damage contributions; named D05 pattern collections
are still unfinished and unnecessary for these original getters. G05.1 supplies
the existing graph worker/lifecycle integration. Shared plotting performs screen
scaling only, preserving source samples. Native validates time/HP/% coordinate
protocol; effective-HP coordinates have structural validation, with independent
original/candidate numerical comparison required. No fitting formula lives in Kotlin.

The immutable root GRAPH-CONTRACT.md binds exact request/result fields, finite
numbers, context/revision identity, ordered selection, units, error/cancel rules,
and no partial publication. Existing positive-total pattern mutation validation
is unchanged. Read-boundary source arithmetic does not invent additional positive
capacity/recharge/pattern restrictions.

## Independent original proof already completed

Three source processes:29 stages,97 fit observations,644 curves,126,244 points;
every observation repeated in reverse read order. Twenty-six no-EOS source-method
checks cover parser and arithmetic edge cases. Maximum18.03s/210,024KiB; no forbidden
graph capacitor/cycle/network entries; exact retained database unchanged.

The candidate-supported subset is26 stages,88 observations,608 curves,119,008
points. Three original all-zero-pattern stages remain source-only because current
Android mutation validation rejects zero totals. Original skill restoration also
leaves Capital Shield Operation unset after Shield Management undo and Caldari
Defensive Systems unset after Shield Operation undo. Any candidate comparison must
record exact stage/fit/value distinctions and prove occupied hull/module effects
are unaffected; this is not general raw profile-history equivalence.

An initial pre-import exporter assertion confused logical dataset identity with
physical file hash. Failed evidence and its focused correction remain retained.
No dataset, original arithmetic or acceptance criterion changed.

## Remaining acceptance and qualification

Product/native source and final evidence passed independent review. Six successful
candidate processes cover the supported26 stages/88 observations/608 curves/
119,008 exact ordered X values, plus122,656 tolerance-checked Y/source scalars.
Three populated fresh-process reopens and durable read-only/history/rollback/
cancel/stale/error boundaries passed. All15 pure comparator methods passed.
Maximum candidate44.68s/171,476KiB. The approved skill differences are restricted
to two named undo stages and two shared fits, with live hull/module applicability
checks and exact typed-input undo retained.

All107 distinct affected host methods passed in six bounded chunks, including24
new shield methods. Actual main/instrumentation Kotlin compilation passed33 tasks
in2m41s (162.13s wrapper). All370 frozen executable/input bindings remain exact;
350 of355 predecessor paths are unchanged, five shared routes/plot files changed
additively, and15 new executable/test paths were added. The22 new instrumentation
methods compiled but were not executed. Final exact original/D01.9 package audit
remains a separate required delivery proof, recorded externally after archive creation.

One candidate defense seed initially failed a stale-context injection: changing
session.context after the sampler captured its callable could not affect the read.
The independently reviewed harness fix preinstalls a closure and changes its
returned generation after range evaluation. No product correction was needed.
The old executable, failed receipt/log and original freeze remain preserved.

For later native qualification, explicitly select `offline_features_phase=shield_regeneration_graph` and the four OfflineShieldRegeneration Contract, Model,
Plot and Ui test classes. Compilation alone does not execute these methods.
Do not add them silently to existing default gates or overwrite MSI-local wiring.

Reconstructed source/supplemental data, missing frozen inspector fixtures,
clean-pin/source-data, actual Android/offline/visual/accessibility/ARM64 and
R02/release qualifications remain open. No local/device/publish action belongs
to this cloud slice. The protected G05.1 archive is unchanged.
