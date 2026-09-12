# A02 — expand the parity inventory

Dependency: A01. Status: done (static documentation audit).

## Outcome

Translate the 23 agreed Pyfa feature families into observable, source-backed
behaviors with delivery ownership and explicit verification slots. Preserve
hidden controls, useful statistics and full offline scope.

## Delivered

- [PARITY.md](../PARITY.md): 239 stable behavior IDs, pinned source references,
  one delivery owner per row, required check types and empty D/A evidence slots.
- [PARITY_AUDIT.md](../PARITY_AUDIT.md): review method, source-surface coverage
  index, nine explicit investigation/disposition gaps and their owners.
- [ROADMAP.md](../ROADMAP.md): 21 bounded children for the four broad I rollups;
  existing A–R task IDs and prerequisite meaning preserved. A03 remains next.
- [SCOPE.md](../SCOPE.md): family map linked to the detailed checklist.

## Acceptance and actual checks

Checked all 23 families, all ten graph definition/getter pairs, every context
menu, active preference category, statistic pane, additions pane, item-detail
panel, view-column and port module. Helper/example files are explicitly mapped
or identified. Checked source paths against the pinned git tree, unique IDs,
owners, evidence slots, local links, task dependencies/rollups and whitespace.

No original runtime code, Android code, A01 fixtures or workflows changed. No
new runtime tests were run or claimed. Static audit completion does not close
any Android parity row. The remaining source/runtime ambiguities have explicit
owners and must be resolved before those features or R01 can be called complete.

Next task: **A03 — minimal headless adapter**, matching the A01 baseline without
wx/UI initialization. Read the current STATUS and verify live master before work.
