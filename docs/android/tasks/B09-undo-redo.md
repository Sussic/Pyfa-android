# B09 — Undo and redo for fit edits

Selected 2026-09-30 after B08 delivery, from master `72b01c4c`. Live default
master and no open PRs verified. B05 is delivered. This parent owns F03.06/F03.07
and remains open until both children pass; later mutation tasks must extend the
same history contract and their independent reference/native cases.

## Bounded delivery sequence

| Child | State | Outcome and acceptance |
| --- | --- | --- |
| B09.1 | active | Per-fit transactional undo/redo for single and bulk local module edits, including charges, states, add/replace/remove, clone/fill, variations, restrictions and ordering. Original command processor evidence verifies action grouping, 100-action retention, redo invalidation and fit isolation. Native controls reverse/reapply values, keep selections valid, survive recreation and save the resulting fit across process restart. |
| B09.2 | queued | Extend and verify the remaining already supported rename, hull, cargo, addition and linked-effect edits. Enumerate original non-command gaps, preserve unrelated fit data and recent-use semantics, and establish the mandatory extension checks for later mutation tasks. Parent completion requires every existing mutation to have an explicit tested disposition. |

Each child requires focused host tests, the full required Windows/native CI,
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
- [ ] Cover all B04/B05 local-module operations, preserve notes and unrelated fits,
  reconcile valid selection state and expose available action labels/counts.
- [x] Host regression cases cover repeated cycles, stale/malformed requests,
  no-op/failed edits, durable write recovery, recreation-independent history and
  fresh-process reopening of the reversed fit with empty session history.
- [ ] Offline native touch single/bulk reversal, branching, fit switching,
  selection safety, recreation/restart, typed protocol guards and screenshots.
- [ ] Required final-revision CI, review, evidence receipt and authorized merge;
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
