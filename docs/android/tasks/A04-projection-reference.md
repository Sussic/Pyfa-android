# A04 — projected-effect reference cases

Dependency: A03. Status: active, Linux checks passed; Windows CI/delivery pending.

## Acceptance

- Generate expected values only from clean desktop EOS at the A01 pin and its
  verified data, using actual desktop dependencies and two fresh processes.
- Record source and recipient values for apply, changed range, disabled/enabled
  projection, source charge edit, removal and repeated reapplication/removal.
- Match all raw values/units through the headless adapter. Ensure every recipient
  refreshes after source edits and removed links leave no effects or reverse link.
- Keep A01/A03 checks, read-only data and desktop migration behavior passing.
- Retain host evidence and obtain Windows CI before delivery; Android parity is A08.

## Implementation

[Scenario, commands and evidence](../../../tools/android_reference/PROJECTIONS.md).
[Adapter API and limits](../../../android_bridge/README.md).

The scenario records 39 statistics on each of two fits in 11 stages. Eight new
projection tests and ten existing headless tests pass locally, along with the
eight reference utility tests, independent A01 rebuild and desktop migration.
No EOS formulas, A01 expectations or numeric tolerances changed.

Next task after verified delivery: **A05 — command-burst reference cases**.
