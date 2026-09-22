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

## B03.1 library boundary

[B03.1](tasks/B03-fit-library.md) extends typed operations with rename, independent copy and explicit reference-resolving deletion. These operations return the complete surviving library after replay, calculation and confirmed durable commit. EOS sources are calculated locally before dependent recipients, irrespective of insertion order. Other B01 edits retain affected-only responses.

An intentionally empty library is represented by graph format 2 with null sample ID and empty records/order/revisions, within the existing SQLite schema. Nonempty graphs retain format 1, including existing B02 saves. Startup accepts an empty result and Chaquopy's Java null sample ID; it never replaces saved data with a new sample.

## B03.2 organization and navigation boundary

The offline hull catalogue uses EOS data and the pinned desktop Market display
policy, verified against an independent desktop export. Optional `modified`
metadata commits with saved fit inputs in existing graph formats 1/2. Only actual
input changes advance the order; earlier saves without metadata remain explicitly
unknown. Opening a fit or recalculating a recipient does not count as editing it.

Ordered open-fit IDs, active selection, restart restoration and empty-group
visibility live in a separate app-private `AtomicFile`, accessed on the same
serialized worker. Closing a view leaves its fit intact; deleting a fit prunes its
view. Restoration defaults off. Invalid preferences remain preserved with a
visible session-only fallback. UI collectors explicitly use Android's main
dispatcher; decoding, calculations, storage and flow publication stay on the
serialized worker. EOS, fitting calculations and the typed operation
boundary remain unchanged. Upgrade/downgrade distribution remains R02.

## B04.1 equipment discovery boundary

Equipment catalogue and search load on demand on the existing EOS worker. The
isolated display-policy adaptation retains pinned Market exceptions and default
jargon without importing desktop services. Independent unmodified desktop
exports compare complete groups/items/memberships and actual search results.
Kotlin decodes typed catalogue records and manages UI filters/navigation/pages;
fitting formulas and persisted inputs remain untouched. The expected catalogue
belongs only to the instrumentation APK, never the production asset path.

## B04.2.1 empty hull boundary

Empty creation uses the original EOS `Ship` or `Citadel`, with explicit all-V
skills, uniform damage, high-security space, zero pilot security and no equipment
or additions. The worker accepts every hull in the bundled desktop catalogue.
The typed snapshot still requires all 39 named fields and their units. An absent
value is explicit JSON `null` / `StatValue.Unavailable`, displayed as
"Unavailable"; a calculated zero remains numeric. Empty hulls have absent gun
optimal/falloff, while the existing fitted reference values retain their types.
The bundled version-1 contract gains this nullable scalar variant; it is not a
public mixed-version protocol. Older app builds reject empty-module fits and
preserve the incompatible file. No downgrade or install-over-data guarantee is
claimed; R02 retains those checks.

Empty fits use ordinary nonempty graph format 1 with empty module/drone arrays;
format 2 still exclusively means an empty library. Save, copy, rollback and
process reconstruction use the existing atomic graph path. Expected values for
all 437 hulls are independently exported from pinned desktop EOS and included
only in the test APK. Module editing and full structure modes remain later B04
children and B06 respectively.

## B04.2.2 module editing boundary

Module add/replace/remove and restriction changes run only on the serialized EOS
worker. The isolated desktop-command adaptation delegates fitting, states and all
numeric resources to EOS. Read-only fitting details expose exact resource values,
slot/hardpoint totals and recursive skill warnings. CPU, powergrid, calibration
and missing skills are warnings; EOS slots and restrictions determine acceptance.
Re-enabling restrictions removes invalid modules in reverse position order and
retains excess hardpoints, matching the desktop command.

Optional `ignore_restrictions` and explicit `{"empty_slot":"HIGH"}` module inputs
preserve overrides and vacancies in the existing declarative graph. Fitted module
inputs remain unchanged. Snapshot vacancies use `index` plus `empty_slot`; the
typed Kotlin alternative has absent name/charge/state. Subsystem vacancies are
retained but subsystem editing remains B06. Reconstruction appends positions
without filling holes and preserves over-hardpoint fits left by re-enabling.
The bundled version-1 contract is still not a mixed-version public API.

Optional graph `recent` holds at most 20 unique bundled IDs. Successful edits and
their history commit together. A valid-item add/replace rejected by legality
first restores all fit inputs/revisions/results, then separately confirms the
attempted recent item, matching desktop history. Malformed/stale requests and
failed durable writes preserve both. Unknown commit outcomes stop further edits.
History survives an empty library; viewing does not change it. Earlier saves
without metadata open with an empty history. Older apps reject the new fields
and preserve their files; install-over-data and downgrade verification remain R02.

## B04.2.3.1 charge boundary

Charge discovery calls EOS `getValidCharges` and the pinned Market publicity
policy on the serialized worker. Active-fit discovery is the union of local
module choices. Versioned options carry fit ID/revision, exact module positions,
current charge IDs and complete charge IDs/names. Native decoding rejects
inconsistent unions, vacancies, duplicates and incorrect scalar types. Views
reload on active-fit/revision changes; pending edits include the displayed revision.

Single-module charge changes validate category and EOS compatibility before
assignment, recalculate/check states and fill vacancies as the original desktop
command does. Failed edits/writes use existing graph rollback; charge changes do
not promote recent equipment. No storage schema or calculation formula changes.
The earlier bulk operation remains available, with B05 retaining full selection
semantics. Variation/reordering tasks remain separate retained B04 children.

Engine initialization now matches desktop `config.init` by disabling the optional
EOS gamedata query cache before imports. Its global cache otherwise aliases item
and group integer IDs during charge enumeration. EOS session ownership and its
normal ORM identity map remain; required prior performance/native gates still run.
