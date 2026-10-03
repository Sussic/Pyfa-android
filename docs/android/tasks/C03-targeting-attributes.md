# C03 — targeting/navigation and attribute inspection

Selected2026-10-03 after delivered C02, base `b88713b3`, branch
`codex/c03-targeting-attributes`. Live default/open PRs checked; no open PR or
active verification remains. Preserve the full F07 inventory and serialized EOS
architecture. C06 retains F07.33 skill requirements.

Two bounded child outcomes separate fit statistics from dataset-driven item
inspection. These are related parts of the approved C03 milestone, without new
approval gates. C03 remains active until both are delivered and verified.

- **C03.1 targeting/navigation and cargo details:** all F07.01–F07.30 together.
  Maximum targets/range, scan resolution and every original reference lock time,
  sensor type/strength/jam chance, drone control range, speed, alignment/mass/
  agility, signature/probe size, warp distance/core strength and all21 special
  holds. Preserve original aggregate and formatting; absence stays explicit.
  Use original EOS and unchanged pinned targetingMiscViewMinimal as the oracle.
  Cover representative hull/sensor/hold families, actual module/skill/modifier
  changes, cargo detail refresh, history/copy/GC, activity recreation and process
  restart. Match raw values/types, units, display and exact detail; reject malformed
  results, incorrect fixture hashes and changed fixture content. Native controls,
  screenshots, every inherited local gate and A10 remain required.
- **C03.2 complete ship/item/charge inspection:** F07.31–F07.32 and F07.34–F07.48
  together. Grouped current/base/raw attributes, description/traits, affectors,
  variations, effects/properties and every equipment detail family, refreshed
  after edits. Enumerate the pinned dataset's supported attributes/effects rather
  than sampling away members. Record its concrete matrix before implementation.
  Search, precise units, copyable text and native/offline detail behavior are
  required; later CSV/skills/price-refresh owners retain their dependencies.

Current implementation scope: C03.1 only. Complete its independent fixture,
bridge/UI, focused regressions and summary readiness before one stable full
delivery verification. Group corrections before expensive checks; reuse proof
only when its inputs and prerequisites remain valid. C02 evidence stays closed.

## C03.1 implementation and focused readiness

Serialized EOS supplies the typed read-only targeting query; Compose exposes ten
main fields, precise nested details, every hold and all eight reference locks.
Details survive revision refresh and activity recreation. Numeric zero remains
the actual EOS result for absent holds; an explicit presence flag gives the
original tooltip's distinction without inventing a capacity or null result.

Two fresh unchanged pinned wx/EOS exports agree for53 cases. An exhaustive437-hull
inventory finds14 positive hold types and7 absent types. The matrix covers all
five sensor families, zero skills, module states, eight skill edits, cargo and
three linked electronic-warfare effects. Host matrix/read-only/GC, history,
copy isolation and fresh-process restart pass with the unchanged database.
The current fixture SHA256 is
`415bb29a328b0823da1c7ca0519646b505698edadeaebea2db6993ef0081f7a6`.
Focused evidence is retained externally in
`c03-targeting-reference-presence-20261003-1315` and
`c03-targeting-host-presence-20261003-1324`.

Sixteen focused validator tests pass, including all-field/type/unit/display and
member rejection, exact packaged hashes and CRLF-to-LF-only fixture equality.
Twenty-six inherited integration checks pass after adding the new persistent
runner flag to their expected set;7 history,7 resource and8 profile reuse guards
still reject unrelated source differences. Historical guards evaluate their
original delivered boundaries, not a weaker production reuse rule.

Source review confirms EOS formulas and original wx presentation, serialized
queries, revision identity, immutable strict DTOs, preserved inherited graph
metadata and process boundaries. No mutation, tolerance, timeout or performance
requirement is relaxed. No production exact-source exception was extended.

Preserved development failures: the initial oracle used an obsolete ECM item
name (corrected to the actual pinned Multispectral ECM II); two validator tests
assumed absent holds were null instead of EOS zero; one integration expectation
omitted the new runner flag. Corrected focused checks pass. Earlier exports and
build evidence remain historical, with their actual inputs, not relabelled.

Both updated APKs compile and lint passes (`build/c03-focused-build-final.log`);
engine staging includes the current presence-aware fixture. `git diff --check`
passes. Native execution and visual review are still outstanding.

Next: commit the coherent candidate, run the new
native pair and its actual-report summary against a verified268-fit C02 synthetic
baseline on a fresh offline AVD. This focused proof does not replace delivery.
After readiness and visual review, full delivery requires all115 gates,75 native
executions,325 persisted fits and215 reviewed screenshots on the final revision.

The first focused Android prepare attempt on `c4233aa5` hit its900-second
deadline. Run `c03-targeting-focused-20261003-135257` retains its APKs, raw log,
logcat and partial store (SHA256
`a54c65e2352ec138779bf874a3f5ec69bd835fdaf86df95359784233ee71221c`).
The store reached311 fits and case42's undo revision3; successive three-GC groups
continued through14:08:24. History replay rebuilds the whole retained graph;
this is progressing execution, not proof of a hung case. It is a failed attempt,
not partial delivery success. The earlier private seed helper's Windows manifest
separator lookup failure is also retained, with exact hash/size checks unchanged.

Preparation is now bounded at cases0–32,33–44 and45–52, followed by the original
full restored verification. All53 cases and every edit/undo/redo/GC/copy/UI
assertion remain; each stage still has900 seconds and existing operation limits.
UI undo/redo executes in the first stage while that history exists, and later
stages retain its original exact proof. Additional restart checks compare the
typed incoming graph/snapshots and prior observations; every inherited fit remains
unchanged. Native progress logs record each case's start, pass and elapsed time.
No product implementation, fixture, calculation, timeout or A10 criterion changed.
The staged validators (16 tests, including26 corruption subcases) and26 inherited
integration tests pass. The first staged-validator attempt is retained: its
"recent" corruption targeted a pre-cargo stage whose empty list was already
correct; it now targets the actual cargo stage. Typed previous graphs are validated
once before comparison, preserving every member/type check without repeated
revalidation. Both APKs build and lint passes (`build/c03-staged-build.log`).

Focused native run `c03-targeting-focused-20261003-141846` on `f739cbbd` passed
all four stages in604.188/545.235/724.516/49.766 seconds. The original900-second
deadlines and every assertion pass;325 fits (268 inherited) survive all boundaries.
All24 required targeting screenshots are visually reviewed against their hashes.

Its first summary failed because it expected only the named lowered skill.
Original EOS strict skill levels also record exact dependent skills as `None`.
The original failure, full logs, reports, APKs, screenshots and store are retained.
Two fresh pinned desktop EOS processes independently export all53 complete input
maps in the host-side companion `targeting-skill-inputs.json` (SHA256
`ea880615dc7ba080d15440c8eedd51d144e25a24ddff5b5f8ac5adfee425face`).
The witness binds the complete original specs/edits, source/settings/dataset,
normalized original targeting fixture hash and original character source hash.
Summary checks require those exact maps, including every null, and retain all
manifest/report, type and restart comparisons. Full reference verification now
repeats this companion export. It is expected-input proof, not Android test data;
the original packaged targeting fixture and every reported hash are unchanged.

The summary-only retry passes without any Android rerun and verifies all retained
native inputs remain byte-identical. Sixteen focused validator tests (29 corruption
subcases),37 actual-report corruptions and18 native protocol guards pass. Missing
dependents, null-to-zero changes and arbitrary extra null skills are rejected.
Source review confirms a summary/input-oracle correction only; product code,
APKs, native assertions, tolerances, timeouts and A10 requirements are unchanged.
Current next: commit the reviewed correction and start full115-gate delivery proof.
