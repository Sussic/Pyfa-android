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
