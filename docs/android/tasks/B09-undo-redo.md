# B09 — Undo and redo for fit edits

Selected 2026-09-30 after B08 delivery, from master `72b01c4c`. Live default
master and no open PRs verified. B05 is delivered. This parent owns F03.06/F03.07
and remains open until both children pass; later mutation tasks must extend the
same history contract and their independent reference/native cases.

## Bounded delivery sequence

| Child | State | Outcome and acceptance |
| --- | --- | --- |
| B09.1 | done | Per-fit transactional undo/redo for single and bulk local module edits, including charges, states, add/replace/remove, clone/fill, variations, restrictions and ordering. Original command processor evidence verifies action grouping, 100-action retention, redo invalidation and fit isolation. Native controls reverse/reapply values, keep selections valid, survive recreation and save the resulting fit across process restart. |
| B09.2 | active | Extend and verify the remaining already supported rename, hull, cargo, addition and linked-effect edits. Enumerate original non-command gaps, preserve unrelated fit data and recent-use semantics, and establish the mandatory extension checks for later mutation tasks. Parent completion requires every existing mutation to have an explicit tested disposition. |

Each child requires focused host tests, the full required local reference/build/native verification,
reviewed screenshots/evidence, fork PR merge and checkpoint. No additional approval
gate is introduced between children. No new fitting features, storage migration,
release or phone action is included.

## Audited starting boundary

Pinned `service.fit.Fit.getCommandProcessor` owns a `wx.CommandProcessor` per fit,
limited to 100 commands. `gui.mainFrame` routes undo/redo to the active fit.
GUI commands group their internal calculation commands into one user action and
recalculate/commit on reversal. History itself is process-local, while the reversed
fit is saved. The notes service writes outside command history; notes must not be
silently overwritten by undoing a fitting edit. EOS remains the calculation
authority and the existing serialized worker/atomic graph store remain unchanged.

The intended adapter retains declarative input changes, never EOS object copies or
cached expected statistics. Reversal must use the existing exact graph replay and
publish only after confirmed persistence. Reject stale or unavailable history,
failed saves and invalid reversals atomically, retaining committed values and
history position. Per-fit revisions remain monotonic. New actions clear the
appropriate redo branch; copying or restarting does not inherit command objects.

## B09.1 acceptance checks

- [x] Independent pinned original GUI/calc commands and real wx processor export
  matching do/undo/redo states, bulk grouping, failed/no-op behavior, redo branching,
  per-fit isolation and history limit; repeat in fresh processes.
- [x] Strict typed history query and undo/redo operations on the serialized worker;
  exact input replay recalculates affected recipients and commits atomically.
- [x] Cover all B04/B05 local-module operations, preserve notes and unrelated fits,
  reconcile valid selection state and expose available action labels/counts.
- [x] Host regression cases cover repeated cycles, stale/malformed requests,
  no-op/failed edits, durable write recovery, recreation-independent history and
  fresh-process reopening of the reversed fit with empty session history.
- [x] Offline native touch single/bulk reversal, branching, fit switching,
  selection safety, recreation/restart, typed protocol guards and screenshots.
- [x] Required final-revision local verification, review, evidence receipt and authorized merge;
  update this task and STATUS, then advance automatically to B09.2.

## B09.1 implementation checkpoint

The independent original GUI/calc commands and real wx processors repeat **18
cases/108 states**, plus branching/no-op/rejection/isolation and the 100-action
limit. Six focused host tests pass all states, linked recipients, monotonic
revisions, note preservation, stale/malformed/failed-write recovery, copy isolation
and two-fit fresh-process reopening with empty session history. Initial native controls compile (1m24s); both final APKs/lint pass (1m43s), and
package inspection verifies pinned data/licenses, 163 sources and both ABI ELF
dependencies. Build 27 and the offline touch/recreation/restart gate are prepared;
native execution, screenshots and final-head CI are still required.

B08 Windows CI took 28m44s under a 30-minute ceiling. The additional independent
history export and host reversal suite require more time; its job ceiling becomes
35 minutes while all existing checks and their individual limits remain intact.
No schedule, artifact-retention, upload, billing or release policy changes.

## B09.1 final review — 2026-10-02

W02 full local proof is valid for unchanged B09.1 product/test inputs: 78 gates,
52 instrumentation executions and all required screenshot review. Actual host/build
commit f7d2ad31, native execution 6792b03e and aggregate 5952c1bf are retained rather
than relabelled. History passes 18 cases/108 states, two linked recipients, 111-fit
fresh-process restore and ten protocol rejections; six history screens reviewed.
Twenty-one deliberate native report corruptions are rejected in focused review.
The [feature receipt](../evidence/b09-1-native.json) and
[raw report](../evidence/b09-1-history-native.json) preserve observations and limits.
No product/test/fixture or tolerance change was needed during final review.
PR #33 merge is pending the receipt/docs push and exact-head local reporting.
B09.2 is next after delivery; setup-only stop has been explicitly superseded.

## B09.1 delivered — 2026-10-02

PR #33 merged as `3143d771` from reviewed head `9b586d89`; merge/delivery trees
match. Exact-head `local/full-verification` passed, reusing the preserved valid
W02 execution proof and reviewed images. Feature receipt records all actual tested
commits, 21 rejected corrupt reports and raw history. No hosted job was dispatched.
B09.1 is complete; B09 remains active. B09.2 is ready and automatically selected next.

## B09.2 selected — 2026-10-02

Branch codex/b09-2-mutation-history from delivered master 0685bb32.
[Operation dispositions](B09-mutation-dispositions.md) retain every supported
mutation. Recipient-owned linked effects, rename, mode/subsystem, cargo/transfers,
addition variations/implants and skill overrides now enter session history.
Library/query/cursor and direct notes writes have explicit lifecycle dispositions.
Eight focused registration/ownership/preservation/deletion tests and six real-EOS
module regression tests pass. Remaining native UI/raw restart/screenshots and
complete final local verification remain required.

## B09.2 independent remaining-command checkpoint

The new original-command exporter passes **28 cases/168 states**, repeated in
two fresh processes against the unchanged pinned source and dataset. It retains
every original Do/Undo body and uses real wx processors, with explicit grouping
for compound phone actions and the previously identified direct skill-input gap.
The fixture is `tools/android_reference/fixtures/history-mutations.json`.
Development export and both full logs are retained outside the checkout at
`%LOCALAPPDATA%/PyfaAndroid/PyfaDevelopment/development/b092-original-20261002-010825`.

The remaining-mutation bridge comparison is in development. The durable
failure/restart test passed for all 28 cases and restored all 35 fits with empty
session history; the overall attempt remained failed on a subsystem comparison.
That attempt and its full logs are preserved at
`%LOCALAPPDATA%/PyfaAndroid/PyfaDevelopment/development/b092-matrix-20261002-005939`.
Fixture setup must use the
supported bridge operations for implants and existing links. Phone recent-use
continues its existing equipment policy: partial cargo removal promotes the item,
while implant add/remove do not. These differ from
the selected original calc/GUI command side effects and are asserted explicitly;
the original raw recent-use values remain in the independent fixture. This does
not establish exact desktop recent-use parity for those boundaries.

Both new reference and host gates are registered in the local full plan. Native
remaining-mutation cases, raw validation, screenshot review, final candidate
verification and delivery are still required. The delivered module history cases
and all earlier verification gates remain required.

The corrected focused bridge matrix now passes all **28 cases/168 states** at
`%LOCALAPPDATA%/PyfaAndroid/PyfaDevelopment/development/b092-matrix-20261002-010910`.
Its receipt explicitly records `complete_verification=false` and no restart claim.
The subsystem case now executes the original GUI wrapper, including fill and
dummy restoration, rather than only its calculation command. No adapter change,
numeric tolerance change or existing assertion removal was needed for this fix.
The complete host gate also requires all eight history registration/disposition
tests; native and final stable-candidate verification remain outstanding.

## B09.2 native candidate

Build 28 (`0.1.0-b09.2`) adds a native remaining-history test: four groups of seven
cases, each followed by an actual process restart. All 168 independent states use
the activity Undo/Redo controls. It also checks cargo and transfer selections,
notes, recreation, stale actions, copied history and deleted-source invalidation.
Eight independently resumable gates preserve completed groups. Final native
acceptance expects 147 retained fits, eight distinct new processes and 21 new
screenshots; these are requirements, not executed results yet.

Reports retain actual restored inputs, scalar kinds, revision/cursor transitions
and the test APK fixture's byte hash. The raw validator requires that hash to
match the verified packaged bytes, and those bytes to match the reference after
CRLF-to-LF normalization only. Twelve focused regressions pass all 168 fixture
states and reject invalid content/units/types, missing fixtures, incorrect hashes
and changed fixture bytes even with an updated matching hash. Existing reporter
regressions pass all 20 tests. B09.1 now additionally asserts its two projection
recipients retain their one link action during local-module reversals; all
original 18 cases/108 states, timeouts and restart checks remain.

Development APKs/lint pass (2m02s), signature and package inspection pass for 163
sources and both ABI ELF dependency sets. Logs are retained in the local
development root: `b092-native-build-20261002-012041.log`,
`b092-package-20261002-012532` and `b092-validator-20261002-012445.log`.
The initial environment-path compile failure and initial validator failure remain
recorded. The final candidate requires the complete 88-gate local plan, including
the 23-test new host gate, 60 actual native executions and all 146 required
screenshots. No hosted workflow or native emulator test has been dispatched for
this candidate yet. Final review, execution, raw corruption probes, screenshot
review and PR delivery remain outstanding.

Review found and corrected a concrete recent-use replay issue: cargo/subsystem
actions must retain promotion even when the item is already first. An independent
original wx two-fit case, focused bridge comparison and raw-validator regression
now verify all five interleaved steps, both history cursors and final ordering.
Native controls repeat the same case; the two extra fits persist across restart.
Focused original export is retained at `b092-original-20261002-013617`; the new
validator log and recent-use bridge receipt remain in the development root.
The earlier build precedes this fix and is not proof for the final candidate.

## B09.2 verified candidate — 2026-10-02

The [receipt](../evidence/b09-2-native.json) records 88 passing local gates,
60 required native executions, 147 retained fits and all 146 screenshots reviewed.
Four prepare/restore pairs pass 28 cases/168 independent states and eight distinct
new processes. All 46 operations have tested dispositions; future mutations must
extend the contract. B09.1 remains verified, including linked recipient assertions.
Actual native raw reports pass the unchanged validator, which rejects 26 deliberate
corruptions. APKs were built at ac90c37d; native/launcher execution uses 98ab296d
with exact source and gate provenance recorded. All prior failures stay retained.

Review fixed canonical EOS Float metres before history capture so a linked copy
cannot clear unchanged recipient history. Host cases cover 0/1000/1000.5 metres;
native copy assertions pass. The Windows-only bounded initial artifact read retry
and exact historical verifier fixture have 124 focused regression checks. Clone
restored report recovery retained every prior gate and verified the unchanged
fit database against all saved inputs and calculated statistics before repeating
only restored assertions with the original test checkpoint/selection precondition.
No functional assertion, tolerance, timeout, performance or restart requirement
was relaxed. Complete local validation is passed; focused PR delivery is pending.

History remains session-local, confirmed inputs persist, and direct profile/recent
policy gaps remain explicit. ARM64 execution, older APIs, signing upgrades and
phone usability remain unverified. No hosted job, release or phone install ran.
