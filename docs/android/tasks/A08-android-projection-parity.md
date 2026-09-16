# A08 — Android projection parity

Dependencies: A04, A07. Status: in progress.

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

Native build/test evidence is pending. Run the existing
[Android commands](../../../android/README.md); `ci/native-test.sh` now requires
four named native tests and retains `projection-native.json` alongside A01 values.

This task establishes the bounded A04 linked-dampener case, not all projection
families or a touch projection editor. D01/D02 retain full UI, counts/stacking,
other effect types, source deletion, cycles and interactions. ARM64 execution,
physical phones, persistence and upgrades remain unverified. A09 is the exact
next task after native evidence and delivery: command parity on Android.
