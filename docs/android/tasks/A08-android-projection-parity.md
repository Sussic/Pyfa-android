# A08 — Android projection parity

Dependencies: A04, A07. Status: done and merged.

## Acceptance and implementation

- Execute the unchanged [A04 inputs and independent desktop fixture](../../../tools/android_reference/PROJECTIONS.md)
  through the existing Kotlin worker and embedded EOS on Android, offline.
- Compare all 39 raw statistics and units on both fits across all 11 states:
  range changes, disable/reactivate, source script changes, removal and reapplication.
  Preserve absolute 1e-9 / relative 1e-10 tolerances and exact integer/boolean/input checks.
- Verify two recipients plus an unlinked control in nine phases, with the second
  recipient read first after source edits. No manual recipient refresh is allowed.
  Link edits/removal must affect only the chosen recipient; both relationship
  directions and five repeated apply/remove cycles must restore correctly.
- Repeat the complete probe on the same process-owned worker, then verify A01
  ammunition again. Case-specific resolved item identities prevent test-order leakage.
- Keep A07's offline first installation, ammunition, navigation/recreation,
  read-only database, APK source/data/license and both-ABI inspection checks.

The new `projection_probe.py` only performs adapter operations and records actual
results. It contains no expected numbers or calculation formulas. Kotlin compares
the output to the independent fixture in the instrumentation APK. The app contains
the synthetic input, while expected values remain test-only. Package inspection
checks both mobile Python sources and rejects golden assets in the app archives.

## Verification and boundaries

[PR #8](https://github.com/Sussic/Pyfa-android/pull/8) merged as
`0f463ab938489b766565831695a50f0be472e93b` after [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35159732933)
passed on the first run for head `7799cecf906950c24f7e23901d359df99030fedf`. Build, lint,
signing, source/data checks and ARM64/x86_64 native dependency inspection passed.
All four native tests passed without failures, errors or skips on API 36 x86_64,
with networking disabled before installation. A01 and all A08 assertions above
passed, including the same-worker repeat and ammunition after projections.

Local verification passed eight A04 behavioral tests and its independent fixture
comparison/fresh-process repeat, eight reference utility tests and the mobile
runtime's full sequence against the unchanged golden values. SQLite integrity,
logical dataset identity and unchanged database bytes were verified. Python/shell
syntax and staged diff checks passed. The desktop workflow was not triggered:
EOS, the adapter and the desktop-reference files are unchanged in this task.

[Durable raw native values, JUnit, hashes and provenance](../evidence/a08-native.json).
Use the existing [Android commands](../../../android/README.md);
`ci/native-test.sh` requires all four named native tests and retains
`projection-native.json` alongside A01 values. Expected fixture SHA-256:
`01487d69559f274844e9734f880703a7babd32b8367ab0601e13bfa17cce6f05`.

This task establishes the bounded A04 linked-dampener case, not all projection
families or a touch projection editor. D01/D02 retain full UI, counts/stacking,
other effect types, source deletion, cycles and interactions. ARM64 execution,
physical phones, persistence and upgrades remain unverified.

Exact next task: **A09 — Android command parity**.
