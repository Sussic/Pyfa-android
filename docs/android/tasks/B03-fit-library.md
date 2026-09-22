# B03 — Fit library (parent)

## Scope split before implementation

B03.1 implements fit lifecycle/search using bundled synthetic fixtures, with native controls, cancellation, Unicode names, independent copies, reference cleanup, save failure recovery and empty-library restart. B03.2 retains all organization/open-view requirements. B03 stays open until both children pass. The queue now has 73 leaf work items and five parent rollups; no parity row was removed.

## Desktop audit

Pinned source remains `8b04f3b271e614b3e103853b44a7851a63d79d0e`.

- `service/fit.py:newFit` creates a named ship/structure with defaults; B03.1 creates only the bundled Vexor, Celestis and Vulture test fixtures. Arbitrary hull/equipment and complete stats remain B04/C tasks and F01.01 is not declared fully verified.
- `service/fit.py:copyFit`, `eos/saveddata/fit.py:__deepcopy__` copy fitted contents and incoming projection/command links, retaining the original source identities and link settings. Outgoing recipients are not cloned. B03.1 preserves that relationship behavior, with independent per-fit skill inputs until C06 introduces shared character profiles.
- `service/fit.py:deleteFit` removes a fit and refreshes its projection/command recipients. Phone deletion requires explicit confirmation that incoming/outgoing links will be removed; surviving fits are recalculated and saved in the same transaction. Deletion is not undoable until B09.
- `gui/shipBrowser.py` browses groups/races/hulls and fit names; `service/fit.py:getRecentFits` means recently modified, not merely opened. B03.2 must preserve that distinction.
- `gui/mainFrame.py` and fit notebook controls own multiple open fits, close one/all and previous-open-set preferences. B03.2 owns these together with back-to-hull navigation and empty-group visibility (F01.03–F01.05).
- Notes remain B08; fixture-based creation does not establish complete hull support. All 239 parity rows remain intact.

## B03.1 acceptance

Create, search, select, rename, duplicate and confirm/cancel deletion in native Compose. Retain IDs/revisions across restart; copies preserve actual modules, drones, skills, implants and incoming links without sharing editable fit contents. Source deletion refreshes both kinds of recipient and leaves unlinked controls unchanged. Reject stale/invalid requests; failure before durable commit restores the prior graph. An intentionally empty store must reopen empty, without restoring a sample. Preserve existing corrupt-store rejection and every existing regression gate. Inspect real screenshots including keyboard/long names and empty state.

## B03.2 acceptance and implementation boundary

Active on `android/b03-2-library-navigation`, based on setup PR #14. User authorized
implementation, review, all required checks and merge; stop after B03.2.

- Browse every pinned desktop hull group and race, including structures, limited
  issue ships, Capsule's Shuttle placement and hidden converted/skinned hulls.
  Hide/show empty groups and hulls, combine race filters, navigate back through
  groups and jump from the selected fit to its hull. Search spans all saved fits.
- Recent means up to 50 recently modified fits. Persist a monotonic input-edit
  order in the same SQLite graph transaction. Reads, opening, switching, failed
  edits and pure recipient recalculation do not change that order. Prior saves
  have unknown order (zero), sorted last; no date is invented. Deleting a source
  changes recipients' stored links and therefore their modification order.
- Open an ordered set of stable fit IDs, select existing views without duplicate
  tabs, close active/inactive/all views without deleting fits, and remove deleted
  fit IDs. Activity recreation preserves navigation and browser/dialog state.
  Opt-in restart restoration retains the ordered set and selected ID. Default
  is off, as in `pyfaPrevOpenFits.enabled`; first use retains the B03.1 sample.
- App-private `AtomicFile` stores open IDs, selected ID, restore and empty-group
  preferences off the UI thread. It is independent of saved fitting inputs.
  Invalid navigation preferences are preserved with an explicit session-only
  fallback; missing/deleted IDs are removed on restore. A failed fit save retains
  the previous modification order. Optional `modified` metadata extends existing
  graph formats 1/2; old files open without rewriting. Earlier builds reject this
  extension, so safe downgrade/upgrade distribution still belongs to R02.

Desktop audit additionally checked `gui/builtinShipBrowser/navigationPanel.py`,
`gui/builtinPreferenceViews/pyfaGeneralPreferences.py` and
`eos/db/saveddata/queries.py:getRecentFits` (modified order, limit 50).
Empty-group and race switches are transient desktop browser state; Android
persists empty-group visibility and retains race selections during activity
recreation. Kotlin/Compose, Chaquopy and serialized EOS remain unchanged.

Verification gates: original 73 host tests plus five organization regressions;
independent desktop catalogue export/repeat and existing independent calculation
references/migration; APKs, lint, signature and complete package checks; all 13
prior native executions plus four B03.2 process phases with raw desktop statistics,
catalogue comparison, navigation/restarts and screenshots. Native results and
delivery are pending; no physical-device or user usability claim.

### B03.2 first native attempt

Head `661dee73` passed Windows CI (78 tests and independent references), Android
build/lint/package gates and all 13 prior native executions in run
`35674055419`. The new prepare phase passed catalogue, recents, filtering,
recreation, back-to-hull and search selection, then timed out closing an inactive
view. The test scrolled the inner horizontal strip without first bringing it
into the outer vertical viewport. AndroidX's
[scroll helper](https://raw.githubusercontent.com/androidx/androidx/androidx-main/compose/ui/ui-test/src/commonMain/kotlin/androidx/compose/ui/test/Actions.kt)
operates on the closest scroll parent. The correction scrolls the outer container
first and asserts the target is displayed before the touch; the close assertion
and 30-second timeout remain. Screenshots are now retained before test teardown
and on partial-phase failures.

Head `ea20293f` passed Windows run `35675176226`, Android build/package gates
and all 13 prior native executions. Run `35675176247` passed the previously
failing active/inactive close checks and deletion, then failed the visibility
assertion before switching back to the first tab. The test now completes outer
scrolling after the horizontal scroll too, and captures the UI tree/screen for
visibility failures. Navigation now clears search focus when opening a fit,
switching/closing views, changing browser mode or jumping back to a hull. A new
assertion requires search focus to be cleared after opening its result. The
original touch, identity, restart assertions and timeouts remain. Final native
verification is pending; the second run's rename screenshot correctly shows
the keyboard with both dialog actions above it.

Head `b75956bf` passed Windows run `35676211561` and Android build/package,
engine, contract, three persistence phases and library-prepare checks. Run
`35676211559` stopped in the existing library empty-state assertion, before
B03.2, with `performMeasureAndLayout called during measure layout` inside
Compose/Espresso. Both library UI test rules now use the installed
`StandardTestDispatcher` through the supported
[`effectContext` API](https://developer.android.com/reference/kotlin/androidx/compose/ui/test/junit4/package-summary).
This queues worker-driven composition instead of the test default's immediate
unconfined resumption. Production scheduling, dependency pins, all original
assertions and timeouts remain unchanged. Native confirmation is pending.

Head `37c73638` passed Windows run `35677078569` and Android's first ten native
executions. Run `35677078568` exposed missing synchronization at library startup:
EOS was ready, but the queued UI collector had not displayed `library-create`.
The tests now advance the Compose frame clock after worker results, wait for
UI idle, and require the actual library control at startup within the existing
30-second deadline. No production code, timeout or behavioral assertion changed.

Head `138d26ae` passed Windows run `35677935062`, but native run `35677935056`
hit the existing 240-second library-prepare timeout. Its screenshot shows the
ready library at the initial scroll position: the standard test dispatcher also
queues scroll actions, and the pinned test scroll helper does not drain that
queue. That dispatcher experiment is reverted. UI `StateFlow` collectors now
explicitly use Android's main dispatcher, so worker emissions cannot resume UI
collection through an unconfined test effect context. EOS, decoding, storage and
flow publication remain on the same serialized worker. The standard Compose
rule, explicit UI synchronization and every original assertion/deadline remain.

## Result

B03.1 completed in [PR #13](https://github.com/Sussic/Pyfa-android/pull/13), merged as `bc6434b67846aba1bae6aa450afe5817b6560645`. Tested head `1468ab9513aa4d69cb17a48b384c27357a8d64e7`; source tree `1aafebd1794ae94c8ba5ca8579a91e4bc275df18`. B03 remains incomplete; B03.2 is ready.

[Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35415142241) passed build, lint, signing, package inspection and **13 native test executions** (five original tests, separate A10/B01 tests, three B02 phases and three B03.1 phases). All three B03 phases passed on the same offline API36 x86_64 installation. The independent validator checks 390 raw target statistics, exact scalar types/units, retained IDs/revisions and both restart boundaries. All nine prior synthetic fits remain unchanged; two new recipients persist, then the library empties and reopens empty before creating/deleting another fit.

[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35415142288) passed **73 host tests**, all independent references and the real desktop migration/backup check. Local 73 host tests also pass. The null sample-ID failure was fixed and the exact failing empty-reopen test passed without weakening it. Screenshots reviewed: original four views, the searched library, rename dialog with keyboard and empty state. No physical-device/usability sign-off is claimed.

[Durable raw evidence, provenance, failed-attempt details and limits](../evidence/b03-1-native.json). No formulas, fixtures, parity rows, dependencies, permissions, artifact-retention or billing settings changed. The APK remains a development build, with no APK upload or release.

## Contract and storage changes

`rename_fit(fit_id,name)`, `duplicate_fit(fit_id,name)` and `delete_fit(fit_id,resolve_references)` use B01 revision checks and return the complete surviving library on success. Other operations retain affected-only responses. Fit names in rename/copy are 1–200 Unicode code points, nonblank and without control characters. The phone applies the same restriction to fixture creation. Failed/uncertain writes retain B02 semantics.

Nonempty stores keep graph format 1, so existing B02 data opens without rewriting. Format 2 is reserved for an explicitly empty graph with null sample ID and empty ordered records/revisions; all other format-2 shapes are rejected. Deleting the final fit commits this marker rather than removing the database; next startup never reseeds it. Creating again writes format 1. SQLite schema remains unchanged. Older builds cannot open the new empty marker; downgrade/upgrade distribution remains R02.

Lifecycle operations rebuild candidate inputs through EOS before the durable write. Sources are calculated locally before recipients even when registration order puts a recipient first. A new command-source-copy regression initially failed (shield EHP changed from 29843.554687499993 to 24843.75) because EOS command-mode recursion marked a cold source calculated before its own local burst bonuses ran. The bridge orders source calculation; formulas and oracle fixtures are unchanged. Cyclic/overlapping graph coverage remains Q07.

The Android dialog model survives activity recreation, retaining text, target revision and pending operation state. Selection is process-local in B03.1; B03.2 owns reopening previous open fits. Test processes use production storage only with explicit B02/B03 phase arguments. B03's three phases run after all B02 assertions, retain app data throughout, then deliberately empty that disposable test library.

## First native execution

The first complete emulator attempt at `0b8fd19f59838e315b23a14e09cd5cf4f0f0bf06` passed all earlier suites and the B03 prepare/reopen-delete phases, then failed on empty-library startup: Chaquopy returns Java null for Python None, and `bridge_sample_id` was dereferenced with `toString()`. Changed that call to a Kotlin safe call; no storage reset, placeholder fit or validation weakening. The same empty-reopen test remains mandatory. Screenshot collection now retains each completed B03 phase before later phases run, and the rename layout test explicitly waits for the keyboard. Copy-name truncation uses Unicode code-point boundaries.

## Retained native screenshots

- [Searched library](../evidence/b03-1-library.png)
- [Rename dialog with keyboard](../evidence/b03-1-dialog.png)
- [Empty library](../evidence/b03-1-empty.png)

Original PNG bytes are retained; hashes and dimensions are in the evidence receipt.
