# A09 — Android command parity

Dependencies: A05, A07. Status: done and merged.

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

[PR #9](https://github.com/Sussic/Pyfa-android/pull/9) merged as
`bba96d3d74c5bbc3441f4180e1010a57d5db10e3` after [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35161269681)
passed on the first run for head `e5e249b9ac95b9144d16f99de4801473661ffa05`. Build, lint,
signing, data/source checks and ARM64/x86_64 dependency inspection passed. All
five native tests passed without failures, errors or skips on a fresh API 36
x86_64 installation with networking disabled before installation. Every command
assertion above passed, alongside the unchanged A01/A04 native checks.

Locally, nine existing command regression tests, independent fixture comparison
and fresh-process repeat passed, as did eight reference utility tests. The full
mobile-runtime sequence matched A05, repeated on the same worker, and preserved
A01/A04 before/after it. Database integrity/logical identity and unchanged bytes,
Python/shell syntax and staged diffs were verified. An independent integration
review confirmed the native phase/observation mappings. The desktop workflow was
not triggered because EOS, the adapter and reference files are unchanged.

[Durable raw native values, JUnit and provenance](../evidence/a09-native.json).
The [Android commands](../../../android/README.md) require all five named tests
and retain `command-native.json` alongside ammunition/projection results.
Unchanged command fixture SHA-256:
`e7fc9ff92370c5a0e6895fd92eb836e9bdc34dfa573899535794bf906d430299`.

Coverage is the bounded A05 Vulture case: one burst module, two shield charges,
two source skills and one mindlink. D03/C06/C07/C09 retain the editors, other
bursts, range/duration displays, shared profiles, multiple-source selection,
source/recipient overlap and interaction cases. No command editor is added.
ARM64 execution, physical phones, lower API levels, persistence and upgrades
remain unverified.

Exact next task: **A10 — Decide embedding feasibility**.
