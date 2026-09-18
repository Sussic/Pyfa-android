# Architecture and feasibility

## Fixed requirements

Android installation; all fitting calculations and saved work available offline;
Pyfa capability and numerical parity; touch-friendly bulk editing. See
[SCOPE.md](SCOPE.md). The initial reference is upstream commit
`8b04f3b271e614b3e103853b44a7851a63d79d0e`, not an unversioned moving branch.

## Implementation retained after A10

- Kotlin with a native Android UI in Compose.
- Embed Python and this repository's EOS using Chaquopy. A03–A10 establish the
  bounded feasibility gate; physical ARM64 and older APIs still need execution.
- A narrow Python adapter owns fits, operations and calculations. B01 formalizes explicit Kotlin edits and typed results with raw values, units,
  errors and fit revisions.
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
multiple-recipient updates, repeated removal and same-worker reuse. A09 adds
[native A05 command parity](evidence/a09-native.json), including source edits,
all-recipient invalidation and pending-bonus cleanup. A10 [retains this embedding design](tasks/A10-embedding-feasibility.md) after
native startup/edit/memory measurements and an adapter source-refresh correction. ARM64 execution and user-data upgrades are not established.
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

A10 retains the design for B01. In the debug API 36 x86_64 run, normal process-to-ready
startup measured 2.960 s on first installation and 2.008 s for the median of four
subsequent process launches. Per-operation edit medians ranged 10.258–60.421 ms;
graph operations updated two recipients and read all four roles. The 70.4 MB APK
contains the offline dataset and both ABI libraries. Normal ready-fit PSS was
154.1–184.8 MiB; cumulative instrumented snapshots with nine retained fits reached
231.3 MiB at command setup. [Raw evidence](evidence/a10-native.json) retains every
sample, phase and limitation. These are not release/phone/peak-memory guarantees.

The longer benchmark exposed an adapter issue: ORM relationship refresh can reload
source modules without calculated attributes. Recalculate the refreshed source,
allowing EOS to invalidate remaining recipients; explicitly recalculate the removed
target too. Forced-GC regressions and all native/Windows parity checks pass without
changing EOS formulas or expected values. Keep these lifetime/invalidation checks
when replacing the provisional bridge with B01's typed contract.

The decision supports continued development, not user usability sign-off. A technical
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


## B01 contract boundary

[B01](tasks/B01-typed-bridge.md) formalizes the existing worker with strict typed
operations/results, session-scoped logical handles and per-fit revisions. EOS
remains the calculation authority. A mutation publishes every affected snapshot
after calculation, serialization and SQL commit. Failed edits rebuild the last
committed declarative graph in the original in-memory session; transport ambiguity
or failed recovery prevents further dispatch until restart. EOS remains transient.

## B02 persistence boundary

[B02](tasks/B02-local-persistence.md) adds a separate app-private SQLite graph
store in Android's no-backup directory. Ordered inputs, fit IDs/revisions and
relationship identities commit together; cached statistics and process session
IDs are excluded. Restart validates schema, logical dataset and EOS settings,
then rebuilds and recalculates the saved graph through the original engine.
Publication follows confirmed durable commit. An ambiguous write is checked using
a fresh connection; an unresolved outcome stops dispatch until restart. Existing
invalid/incompatible data is preserved. Diagnostic direct-engine probes use
explicitly ephemeral processes so they cannot alter persistent user fits.
