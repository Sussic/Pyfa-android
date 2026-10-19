# D05.2: reusable named incoming damage patterns

## Bounded outcome
Provide the original 118 built-in incoming damage patterns and custom create/edit/rename/duplicate/delete, live named fit bindings, explicit Reset to Uniform, and exact server-side Detach to Anonymous. Shared edits and delete-to-Uniform are atomic, persistent and part of existing history. Fit copies retain named bindings; profile copies are independent identities. Existing target profiles, characters, EFT receipts and saved fit state remain preserved.

This is the named-library and per-fit child of D05, not all D05. Global defaults, Selected Ammo/ammunition-derived patterns, explicit custom RAH bindings, interchange and new graph families remain separate. Existing distance/time graph modes are unchanged.

## Deliberate compatibility boundaries
- Four raw values are nonnegative contributions, not resistance fractions or percentages. Preserve exact numeric kinds, fractions and signed zero in saved records. Derive displayed percentages by contribution / total * 100 in EM/thermal/kinetic/explosive order, avoiding intermediate overflow.
- Unassigned custom records may have all-zero values. Binding requires finite positive total, preserving the current Android fit domain. Reject assigning zero or changing a bound record to zero before calculations or any state/write/history change. Do not claim full original zero-total fit parity.
- Uniform is a real built-in selection, not a null/No Profile state. Reset and confirmed delete rebind affected fits to Uniform; undo restores prior identity and raw values.
- A dedicated detach operation resolves current raw values server-side, so an identity-only detach never resubmits rounded UI values. Unsaved drafts remain unapplied. Reload saved contributions, Detach to Anonymous and Reset to Uniform are distinct actions.
- Preserve fractions instead of reproducing the original editor's round-on-load loss. Reserve exact trimmed special names Uniform and Selected Ammo; other custom names use the reviewed Unicode and exact case-sensitive rules.
- Original built-in source order and deterministic separate custom order remain explicit. Built-in identities do not depend on displayed names.
- Inherited reactive armor recalculates after shared pattern edits. Explicit built-in and disabled RAH overrides remain unchanged; custom RAH bindings are outside this child.

## Required proof
Independent unchanged-original semantics and finite real-EOS numerical witnesses; live shared edits, detach/copy/reset/delete/history/reopen; legacy migration without read-time writes; target/character/import coexistence; failures and uncertain publication; native codec/model and actual wire compatibility; affected host regressions; guarded offline main/instrumentation compile. G04 raw invariants concern samples and shield capacity/recharge, not correctly changing revisions, contexts or source echoes.

## Qualified cloud checkpoint
Independent source/wire/original-semantics review passed. Pure Python proof passed 83 methods, including 46 new damage cases; actual native codec/model host proof passed 33 methods with explicit synchronous stubs. The accepted original reference has 13 observations on five fits and 1,206 G04 points. Initial and fresh-process candidate evidence supplies 18 exact observations and 1,608 ordered points in total, with 14,290 independently checked exact scalar comparisons. Shared lifecycle, legacy migration, definite/uncertain failures and seven saved stores are covered. Source, helpers and the read-only database stayed unchanged.

All 414 affected host methods passed exactly once across 35 bounded chunks: 322 inherited, 46 new damage, 20 defense, 18 tank and eight RAH methods. There were no skips or expected failures. Existing G04 modes and G05 distance AND time coverage remain selected.

All 234 captured wire rows are accounted for: 106 actual native request/response pairs (92 success, 14 complete errors), 11 native-invalid requests with complete backend errors, one backend-normalized-name no-op that is not native request acceptance, and 116 other-route exclusions. Original catalogue order, all 118 builtin identities, all 11 operations, raw integer/fractional/signed-zero values, zero-unassigned state and fresh reopen witnesses passed.

Guarded offline main and Android-test Kotlin compilation passed all 33 tasks in 165.302 seconds, with no resource trigger and unchanged shared/source inputs. The 36 new Android methods are compiled-only: 16 contract, 17 model and three UI methods. Host stubs do not establish Android scheduling, rendering, usability or lifecycle behavior; no device, offline-device, accessibility, ARM64, signing, upgrade or release result is claimed.

## Retained qualifications
The first original numerical attempt completed observations but failed an invalid assumption that a flat-resistance fighter must change EHP. The corrected witness checks owner linkage, cache replacement and source-predicted invariance without changing formulas. A second numerical pass lacked fresh prelaunch resource evidence and is excluded from qualified acceptance; the third run passed through a reviewed fail-fast admission wrapper. Pure/AST preparation and native test-syntax failures, helper-only preflight corrections and the unused first freeze remain separately retained. Missing early Python source variants were reconstructed from narrow known deltas and accepted only after matching their recorded hashes; they are not represented as contemporaneous captures.

D05.1 remains independently frozen and Library-delivered. Existing reconstructed-source, supplemental dataset and deferred missing-inspector qualifications persist. Source compilation is separate from final package audit and consumer integration. Global defaults, ammo-derived patterns, custom RAH bindings, interchange and broader D05 parent scope remain open.
