# B04 — equipment browser and fitting

Authorized by explicit chat confirmation on 2026-09-22, including related fixes,
host/native verification, review, PR delivery/merge and automatic advancement.
Base `bd22ed6d83f7951813eb09c9d932470cad04ce0e`; B03 dependencies are delivered.
Retain Kotlin/Compose, Chaquopy, the serialized EOS worker and declarative graph
storage. No formula approximations, release publication or phone installation.

## Bounded children and complete acceptance

**B04.1 — Offline equipment discovery.** Port the pinned desktop Market's display
policy using bundled EOS data: all market roots/children, published and forced
items, variant parent/group/meta assignments, name search, meta filters and jump
from an item to its market group. Render reachable paginated native controls,
retain browser state across recreation and show empty/error states explicitly.
Compare complete enumerated groups/items/memberships against an independent
unmodified desktop Market export and fresh-process repeat; assert native query
identity and UI navigation offline. This child supplies discovery for F02.01;
recently *used* items are completed with actual mutations in B04.2, not replaced
by recently viewed items.

**B04.2 — Fitting editor and item history.** Retain the entire original B04 scope:

- Remove fixture-only creation: choose a supported hull, create an empty named
  fit, and persist/reopen it. Absent equipment attributes are explicitly absent,
  never fabricated zeroes or inherited sample-gun values (F01.01 continuation).
- Add, replace and remove modules, rigs and service modules, preserve positions,
  and expose EOS slot/resource/skill legality (F02.02). Structure-specific modes
  and the dedicated structure fixture remain B06/F02.08.
- Load/replace/unload compatible charges, scripts and crystals; incompatible
  operations are atomic failures, retaining previous inputs/results (F02.03).
  Include the desktop browser's charges-for-active-fit view.
- Swap/reorder modules with states/charges retained and independently checked
  rack/heat behavior (F02.04).
- Supported item variations reconcile state/charge exactly as desktop (F02.05).
  Existing addition inputs must not lose this capability; later addition editors
  reuse it and retain their assigned inventory rows.
- Explicit restriction override and re-enable match desktop removal/legality
  behavior, with visible consequences (F02.09). Resource overloads/skill warnings
  must follow EOS/desktop semantics rather than an invented validity rule.
- A persistent bounded recent-item list follows actual add/remove/replace use,
  including duplicate promotion, exactly 20 entries and abyssal exclusion. Opening
  an item is not usage. Native restart/UI checks finish F02.01.

B04 stays incomplete until both children pass. Bulk selection/fill remains B05;
modes/subsystems B06, cargo B07 and undo/redo B09 retain their full requirements.
The split adds one leaf and one rollup: 74 leaf tasks plus six parents.

## Relevant pinned desktop audit

Source remains `8b04f3b271e614b3e103853b44a7851a63d79d0e`.
`service/market.py` owns forced publication, parent/meta/market assignments,
variant expansion, root/group visibility and 20-item recent storage.
`gui/builtinMarketBrowser/itemView.py` owns tree/search/meta and active-fit charges.
`gui/fitCommands/gui/localModule/{add,remove,replace}.py` records real item use;
merely selecting/searching an item does not call `storeRecentlyUsed`.
Read the corresponding calc commands and EOS fitting checks before B04.2 edits.
F02.01–F02.05/F02.09 and the existing F01.01 boundary remain acceptance sources.

## Required verification and delivery

Preserve all 78 current host tests, independent references/repeats/migration,
all 17 current offline native executions, APK/lint/signature/package gates and
original numerical tolerances/types/units. Add focused host and real native
workflow/failure/restart checks for each child. Validate complete catalogue sets,
not a few familiar items. Inspect actual phone-sized screenshots and retain raw
evidence/provenance. Update this brief, STATUS, ROADMAP and local checkpoint with
actual outcomes. No child is complete on a launch or host-only result.

## Implementation and review history

B04.1 implements on-demand worker-owned catalogue/search and the native browser.
The isolated display-policy adaptation retains upstream notices and default
jargon; it imports no desktop services. Search retains desktop words/wildcards,
regex, default aliases and 100-row cap. The browser pages results and supports
meta filters, item-to-group navigation, empty states and activity recreation.
Recent use and fitting actions remain B04.2, so no full F02.01 or B04 completion.

The unmodified pinned Market exporter and fresh-process repeat pass for **718
groups, 6,822 items and 22 searches**. The exporter matches desktop `config.init`'s
`gamedataCache=False` before EOS imports; its actual search thread dispatches
through wx. An initial bootstrap using the default EOS cache failed on list
search tokens; no desktop methods were patched to bypass it. An earlier command
also correctly rejected the empty scratch DB before export. The verified A01
database was then used, with unchanged logical identity and file digest.

Six new guarded headless regressions pass, including every catalogue membership,
all 22 search results, repeat/cache isolation, unchanged fit/modification data,
invalid input and worker ownership. Local APK builds, lint, signature and package
inspection pass. The first required CI attempt passed all 84 host checks and 18
offline native executions on API 36 x86_64. Review then tightened the raw
catalogue/search/page comparator to require exact scalar types (float/bool/near-ID
mutations are rejected) and reduced equipment-screen spacing so group browsing
starts sooner. The screenshot checks now scroll the group list and destination
breadcrumb into view. Final-commit CI and screenshot review subsequently passed as recorded below.
B04.2 not started.

## B04.1 delivered

[PR #16](https://github.com/Sussic/Pyfa-android/pull/16) merged as
`794f4b1c80f714432d8dff8709d8e33682bfbf00` after review of tested head `6f53682807372d82b610b15d3ee57b64a8ebeee3`.
[Final Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35741516902)
passes 84 host tests and all independent references/repeats/migration.
[Final Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35741516907)
passes both APK builds, lint, signature/package verification and all 18 offline
native executions. All 16 screenshots were reviewed; the five equipment views
and full raw catalogue/search observations are retained in the
[delivery receipt](../evidence/b04-1-native.json). Catalogue scalar types are
exact; earlier numeric tolerances remain unchanged. API36 x86_64 ran; ARM64
package contents only. No physical-device, upgrade or usability claim is made.

Exact next task: **B04.2 — Fitting editor and item history**, automatically
authorized by the current sequential roadmap request. Parent B04 remains active.
