# Architecture and feasibility

## Fixed requirements

Android installation; all fitting calculations and saved work available offline;
Pyfa capability and numerical parity; touch-friendly bulk editing. See
[SCOPE.md](SCOPE.md). The initial reference is upstream commit
`8b04f3b271e614b3e103853b44a7851a63d79d0e`, not an unversioned moving branch.

## Implementation, with linked-fit feasibility still pending

- Kotlin with a native Android UI (Compose is the initial candidate).
- Embed Python and this repository's EOS using Chaquopy if A03/A07–A09 validate
  the actual dependencies and behavior on the target architectures.
- A narrow Python adapter owns fits, operations and calculations. Kotlin sends
  explicit edits and receives typed data including raw values, units and errors.
  UI formatting does not recalculate fitting formulas.
- Package a game database generated from the pinned source data during the build.
  Install it into a readable local location before importing database consumers;
  keep user data in app-private writable storage. First launch must work offline.
- Perform engine work off the UI thread. Begin with serialized engine access
  because mutable fit graphs and database sessions must not race. Measure before
  introducing parallel calculation or elaborate caching.
- Reuse graph calculation code where possible; render results using Android UI.
  Desktop wx/matplotlib presentation code is not the mobile presentation layer.
- Optional ESI/price/data refresh sits outside the calculation path. Its absence
  cannot block creating, opening, editing or calculating a fit.

A07 verifies this Kotlin/Compose + Chaquopy approach for the A01 baseline on API
36 x86_64, including an offline first installation and actual ARM64 package
contents. See [the native evidence](evidence/a07-native.json). A08 adds [native A04 projection parity](evidence/a08-native.json), including
multiple-recipient updates, repeated removal and same-worker reuse. A09 still
needs command parity on Android; A10 records the broader feasibility and
performance decision. ARM64 execution and user-data upgrades are not established.
The two isolated upstream changes defer desktop config until an actual migration
backup and give dynamic migration imports a valid `fromlist` sequence. Neither
changes fitting formulas or migration functions.

## Boundaries to inspect

| Source | Why it matters |
| --- | --- |
| `eos/config.py`, `eos/db/` | Database paths, import-time initialization, sessions and migrations. |
| `eos/saveddata/fit.py`, `eos/calc.py`, `eos/capSim.py` | Fit graph, modifiers and capacitor calculations. |
| `service/fit.py`, `service/settings.py`, `config.py` | Desktop/UI dependencies and shared settings; do not package blindly. |
| `gui/fitCommands/calc/`, `gui/fitCommands/gui/` | Calculation edits versus desktop events; preserve semantics through the adapter. |
| `graphs/calc.py`, `graphs/data/`, `graphs/gui/` | Separate graph inputs/samples from desktop presentation. |
| `db_update.py`, `scripts/`, `staticdata/` | Reproducible dataset generation; avoid a first-run network dependency. |
| `service/port/` | Existing interchange formats and lossless import/export behavior. |

## Feasibility gate (A01–A10)

Before broad UI implementation, produce an actual Android build that:

1. Opens the bundled database and calculates a representative fit offline.
2. Repeats the desktop reference cases for projected effects and command bursts,
   including toggling/removing the source and clearing cached effects.
3. Packages arm64-v8a and passes native tests on x86_64. An x86_64 emulator result
   is not an arm64 runtime test; keep that distinction in the evidence.
4. Records startup, edit/recalculation latency, memory and APK size for single-fit
   and interacting-fit cases, with test hardware/API levels identified.

A10 records whether to retain or revise the proposed embedding design. A technical
alternative may be investigated with evidence, but an online backend or a reduced
feature set changes the agreed product and needs an explicit user decision.

## Updates and ownership

Keep upstream history and notices. Avoid copying the entire engine into a second
independently maintained tree. Record any adapters or small compatibility patches
so upstream changes can be reviewed. Pin the source revision, data digest and
toolchain used by each comparison run. Never refresh golden outputs automatically
from a failing Android result or fetch a changing dataset during parity tests.

Save fits and their projection/command relationships together. Database/schema
upgrades and stable APK signing must preserve existing work; release tasks verify
an actual install-over-previous-build path before describing updates as safe.

## Primary implementation references

Checked 2026-09-12; recheck when choosing concrete version pins:

- [Chaquopy Android integration](https://chaquo.com/chaquopy/doc/current/android.html):
  embedded Python and package/ABI configuration. Native package availability must
  be tested for the chosen Python version; do not assume desktop wheels will run.
- [Android instrumented tests](https://developer.android.com/training/testing/instrumented-tests):
  tests executing in an Android environment.
- [Android Emulator Runner](https://github.com/ReactiveCircus/android-emulator-runner):
  candidate GitHub Actions emulator setup; verify the selected runner supports it.
- [Upstream source baseline](https://github.com/pyfa-org/Pyfa/commit/8b04f3b271e614b3e103853b44a7851a63d79d0e).
