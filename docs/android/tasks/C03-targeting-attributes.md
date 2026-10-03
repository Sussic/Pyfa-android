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
After readiness and visual review, full delivery requires all113 gates,73 native
executions,325 persisted fits and215 reviewed screenshots on the final revision.
