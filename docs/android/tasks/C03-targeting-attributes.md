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

Full run `20261003-150233-9badd3ec-e6ca98` on `9badd3ec` passed58 gates through
headless capacitor. Defense calculations and restart passed; its22-test validator
then failed only the persistent-flag set expectation, missing `c031_phase`.
This original failure and logs remain. The repair adds that exact literal while
keeping every historical flag and the storage-preservation assertions.
Twenty-two defense validators and10 focused reuse guards pass. The existing
launcher/reporter reuse path admits only that complete exact-source replacement
at this58-gate boundary; unrelated test/native/engine/fixture differences fail.
Executed plan/host/build/execute function bodies and every completed input remain
identical. No new framework, fixture, numerical assertion or timeout changes.
Next: commit the repair, resume only the failed gate and remaining dependants,
and preserve all58 passing results. Full native/build delivery proof is outstanding.

## C03.1.1 — keyboard viewport repair (selected2026-10-04)

Parent C03.1 remains active. Screenshot review of the current full run found
`charge-edits-active.png` draws the scrolled Recent edits heading under status
icons while the software keyboard is open. Numerical/native charge tests passed;
this is a failed visual acceptance result, recorded by exact hash in the run's
`keyboard-visual-failure.json`. The run paused cleanly after variations with78
passing gates. Preserve all previous failures and original requirements.

Bounded scope: activity IME resize, consume Scaffold insets, keyboard-aware
viewport padding/clipping; a test tag and native geometry assertions against
actual system/IME insets. Retain all existing charge matrix, compatibility,
rejection, recreation, copy and restart assertions. No fitting calculations,
fixtures, storage behavior, numerical tolerance or existing timeout changes.
Acceptance: focused offline native keyboard/search/recreation/back proof and
actual screenshot review; both APKs/lint/package; complete stable-candidate full
verification and all215 existing required screenshots before parent delivery.
Use the existing test framework and local launcher. Android's official
[edge-to-edge setup](https://developer.android.com/develop/ui/compose/system/setup-e2e)
and [inset consumption](https://developer.android.com/develop/ui/compose/system/insets-ui)
provide the platform handling, without dependency or infrastructure changes.

Focused keyboard proof `c031-keyboard-focused-20261004-042420` on `e2005c92`
passes offline ephemeral storage, query retention, recreation and dismissal.
All3 original screenshots are hash-verified and visually reviewed. Open/recreated
viewport top63/bottom1048 and input top880/bottom1048 stay inside actual1920px
window/status63/IME872 bounds; closed viewport bottom1857 with IME0. Five strict
geometry validator tests pass. Both APKs/lint/signature/package pass. Earlier
catalog-readiness, boot-service and transfer failures retain their logs/images.
Disk exhaustion was resolved by deleting only stopped owned disposable probe
AVDs while retaining captured evidence; original screenshots unavailable after
one failed transfer are not represented as recovered or approved.

Historical full run `20261003-150233-9badd3ec-e6ca98` preserves interrupted
cargo prerequisite failures (actual66 versus required57; original interrupted
store unavailable), native restarts and the System UI/IME failure. Its exact10-fit
store remains in `library-ime-failure/partial-graph.sqlite3`, SHA256
`88a12f9f65cd1843986546114e78e452cc84b377654e651b43758a3a803af039`.
The original9 IDs/revisions match prior B02 proof. Temporary tracked checkpoint
editing also hit the clean-tree guard; restoring the exact tree allowed resume.
The final historical run paused after78 gates for the actual visual defect.

## C03.1.2 — validator metadata indexing (selected2026-10-04)

Fresh full run `20261004-042857-bfbbe157-2dd1cc` passed61 gates through host output.
All desktop references, original targeting/skill-input exports and host regression
matrices passed. Targeting prepare/restored engine processes completed; its
16-test summary validator subprocess then exceeded the unchanged60-second limit.
The raw failure and partial host artifacts remain in that run. No native/build
gate has executed there and no full success is claimed.

Bounded scope: profile and index repeated inherited numeric-metadata prefix
lookups while preserving every existing comparison. No application, engine,
fixture, tolerance, restart boundary or deadline changes. Acceptance requires
prefix-filter equivalence (including overlapping IDs and boundary characters),
all16 original tests/29 corruption subcases within the existing60 seconds, and
the full delivery suite/215 screenshot review. Keep completed61-gate inputs exact;
reuse only through the installed launcher/reporter's narrowly proven source seam.
The failed targeting gate and all remaining prerequisites must execute after repair.

Retained diagnostic profiles show one complete synthetic summary spent12.458 of
13.683 seconds in6,432 metadata filters/30,089,983 prefix calls. The equivalent
prefix trie takes1.606 seconds for the same full summary; all582,166 exact-value
calls and19 typed-wrapper validations remain. The new boundary/overlapping-ID
regression compares every indexed subset to the original filter directly.
All16 original tests and29 corruption subcases plus that regression pass as17
tests in21.215 seconds (21.532 subprocess seconds), inside the unchanged60 seconds.
Twelve source-reuse guards reject removed assertions/corruptions, weaker prefix
boundaries, changed deadlines/fixtures/engine/app, missing gates, executed failed
gate reuse and a different baseline. Application/APKs, fixtures, numerical
tolerances, native900-second deadlines and A10 checks are unchanged.
Full proof and215 screenshot review remain outstanding.

## C03.1.3 — keyboard-ready charge selection (selected2026-10-04)

Full candidate `9272c2a5` passed76 gates through native module editing. Charge
prepare then failed its existing `charge-item-29001` visibility assertion after
filtering Tracking Speed Script with the IME opening. The retained actual image
shows the search field at the keyboard edge and the result below the viewport;
the fixed status-bar boundary is clear. This suggests a platform resize/scroll
timing race; a focused reproduction must establish the correction.

The exact failed9-fit store is retained in the full run's
`charge-keyboard-failure/partial-graph.sqlite3`, SHA256
`3da2ad960d331403d7a51f94b1e690ee15435b273c7331da47f2007a586a2f6b`.
Its original8 IDs/revisions match the preceding module report. Main run state
was preserved during diagnostic extraction; original instrumentation and image
hashes are bound in `charge-keyboard-failure/receipt.json`.

Bounded outcome: synchronize actual keyboard/layout readiness before scrolling
to a filtered charge, and extend the existing ephemeral probe to assert/select/
load that script with the IME open. Keep original visibility, numerical, restart,
geometry and persistence assertions, tolerances and deadlines. Acceptance requires
focused offline native proof and reviewed screenshots, then the complete stable
delivery suite. Previous native results remain historical if the test APK changes;
reuse unchanged host inputs only with exact source/prerequisite proof.

First focused candidate `9564f0ca` passes all5 build/package checks. Its first
probe attempt stopped before instrumentation on the emulator's12GB free-space
prerequisite; stopped owned no-snapshot RAM files were removed with receipts,
preserving userdata/evidence. The next probe passed its existing geometry,
recreation and dismissal assertions, then exposed an incorrect added navigation
step: the equipment charge picker returns directly home, not to equipment.
Remove that extra step before retrying; filtered-script proof remains pending.

Corrected candidate `db59358a` also passes all5 build/package gates. Its probe
displayed/selected/loaded Tracking Speed Script, then failed a new assertion that
incorrectly assumed the options list contained only fitted modules. The bridge
also exposes vacant rack slots. Check the exact target index0 instead; the
selected module's charge must still equal29001. Use the original full test's
selection helper in the probe and retain its filtered-result screenshot through
an observation callback, so the focused proof exercises that exact interaction.
The original full-test assertions and numerical matrix remain intact.
