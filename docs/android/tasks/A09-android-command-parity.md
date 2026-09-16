# A09 — Android command parity

Dependencies: A05, A07. Status: active.

## Acceptance and implementation

- Execute the unchanged [A05 inputs and independent desktop fixture](../../../tools/android_reference/COMMANDS.md)
  through the existing Kotlin worker and embedded EOS on Android, offline.
- Compare all 39 raw statistics and units on both fits across all 19 states:
  source skills, mindlink addition/state/removal, burst module state, command-link
  state, charge changes, removal and reapplication. Preserve absolute 1e-9 /
  relative 1e-10 tolerances and exact integer, boolean, unit and input checks.
- Verify two recipients plus an unlinked control in 18 phases, reading the
  second recipient first. Source edits update every linked recipient; independent
  link edits and removal affect only the intended recipient. No manual refreshes.
- Verify both relationship directions through five apply/remove cycles and
  require all 112 pending-command-bonus observations to exist and be empty.
- Repeat the whole command probe on the same process-owned worker, then compare
  A01 ammunition and A04 projections against their independent fixtures again.
- Preserve all A07/A08 offline first-installation, navigation/recreation,
  read-only game data, source/license and both-ABI package checks.

`command_probe.py` performs adapter operations and records actual results. Kotlin
owns the independent comparisons; no golden values or formulas enter production
Python. Build preparation verifies the command fixture's source/data identity,
stages its synthetic input into the app and expected values only into the test
APK. The package verifier covers all three mobile Python sources. Source item
provenance includes the two skills and mindlink without leaking other cases' IDs.

## Verification and boundaries

Native build/test evidence is pending. The existing
[Android commands](../../../android/README.md) now require five named native
tests and retain `command-native.json` alongside ammunition/projection results.

Coverage is the bounded A05 Vulture case: one burst module, two shield charges,
two source skills and one mindlink. D03/C06/C07/C09 retain the editors, other
bursts, range/duration displays, shared profiles, multiple-source selection,
source/recipient overlap and interaction cases. No command editor is added.
ARM64 execution, physical phones, lower API levels, persistence and upgrades
remain unverified. Exact next task after delivery: **A10 — embedding feasibility
and performance decision**.
