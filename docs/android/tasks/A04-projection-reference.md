# A04 — projected-effect reference cases

Dependency: A03. Status: done and merged.

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

[PR #4](https://github.com/Sussic/Pyfa-android/pull/4) merged as
`4ab6b75fa29e4eccfb395369417c7f23c0ee8f22` after
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/34759292301)
passed on the first run for head `ef0950fc78168ea9fe77a4792bf741e0c377c353`.
Windows passed the same 18 headless behavioral tests, eight reference utility
checks, independent desktop references and migration regression. The normalized
code/input/fixture and logical data hashes agree with Linux. Retained evidence
records the actual CI merge checkout separately from the delivered commit.

Next task: **A05 — command-burst reference cases**.
