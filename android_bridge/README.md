# A03–A05 headless EOS boundary

This is a host-tested Python prototype for the Android port, not an Android app
or the complete bridge contract. It uses this checkout's EOS calculations and a
separate, existing game database. See [verification commands](../tools/android_headless/README.md).

## Initialization and dependencies

The tested host baseline is Python 3.11 with Logbook 1.7.0.post0, SQLAlchemy 1.4.50
and its Greenlet 3.0.3 dependency. The runtime needs the `android_bridge`, `eos`
and `utils` packages. It does not require wxPython, NumPy, PyYAML, cryptography,
Pillow, root `config.py`, `gui`, or `service` for the A03–A05 cases. This dependency list
does not establish Android wheel/ABI availability; A07 must do that.

Create `HeadlessEngine(game_database)` **before importing `eos.db`**. EOS builds
its database engines at import time. Initialization checks that the supplied file
exists and has dataset metadata, supplies a read-only SQLite connection factory,
selects English game data, and sets saved data to `sqlite:///:memory:` before EOS
imports. No personal saved database is opened, migrated or created. The verifier
also checks the complete logical game-data digest against A01 before calculation.

Only one session is allowed per process. Calls must remain on the creating
thread; later Android code needs a dedicated serialized engine worker. Starting
another session after EOS import raises an error instead of pretending to switch
databases. Restart the process to change databases. A persistent fit store,
session disposal, bounded fit lifetime, bridge revisions and structured mobile
errors belong to B01/B02; this prototype keeps its created fits in memory.

## Provisional API

```python
from android_bridge import HeadlessEngine

engine = HeadlessEngine("/absolute/path/to/eve.db")
fit = engine.create_fit(spec)
initial = engine.snapshot(fit)
engine.set_charges(fit, [0, 1], "Iron Charge M")
changed = engine.snapshot(fit)
```

`spec` is the A01 [scenario input](../tools/android_reference/vexor.json) without
its test-only `edit` field. It accepts ship/module/drone English names, module
states/charges, all-0 through all-5 default skills, reload, damage pattern and
security settings. It rejects unknown keys, incompatible charges, invalid
selections and nonempty inputs for features it has not implemented. It does not
quietly ignore projections, commands, implants, boosters, environments or target
profiles. A04/A05 expose linked projections, command sources and fit-local implant
edits through separate methods below. Nonempty creation-time additions are still
rejected; the later full fit/persistence contract will define them explicitly.

`create_fit` returns an internal EOS object. Do not expose or modify that object
directly from Kotlin. `set_charges` validates the entire selection before changing
any module, recalculates with EOS cache clearing and restores original charges if
recalculation fails. This is not a general undo/transaction system. Equipment
limits and full fitting-edit semantics remain in B04/C04 and later feature tasks.

`snapshot` exports the 38-field **A01 sample vocabulary** with unformatted values
and units. Weapon optimal/falloff are for `weapon_index` (default 0). The legacy
`*_ehp_uniform` labels refer to A01's uniform damage pattern; EOS actually uses
the fit's selected pattern. This sample export is not the all-statistics contract
or a claim that any of the 239 Android parity rows are implemented. B01 and the
C tasks replace/expand the provisional result schema deliberately.

## A04 linked projections

```python
source = engine.create_fit(source_spec)
engine.add_projection(source, fit, range_m=100000.0)
engine.configure_projection(source, fit, range_m=0.0, active=False, amount=1)
engine.remove_projection(source, fit)
```

Fits now receive unique IDs from the in-memory EOS saved-data session. Links use
EOS's mapped association, including the desktop's flush/refresh step which keys
the source's reverse relationship by recipient ID. Removing a link flushes and
refreshes the source so it no longer retains that recipient.

`add_projection` defaults to `range_m=None`, `active=True`, `amount=1`.
`configure_projection` requires all three options explicitly and validates them
before changing any. Range accepts nonnegative finite metres or `None` (EOS's
unspecified range); state must be a boolean and count a positive integer.
Duplicate adds and edits/removals of missing links fail explicitly. Desktop UI
duplicate-add/count behavior belongs to D01. These operations do not constitute
a general transaction/undo API or a performance guarantee for large counts.

Changing source charges recalculates that source; EOS invalidates its recipients.
Both snapshot methods recalculate an invalidated recipient before reading values.
`projection_snapshot` adds scan resolution in mm to the existing 38-field sample.
The [A04 reference](../tools/android_reference/PROJECTIONS.md) verifies a scripted
Celestis dampener, range and active changes, source script edits, two recipients,
and repeated removal/restoration. No additional upstream code patch is needed.
Full projection types, multiplicities/stacking, cycles, persistent links, command
interactions and Android runtime behavior remain with D01/D02/D03/A08/A09.

## A05 command sources and supporting edits

```python
engine.add_command(source, fit)
engine.set_skill_level(source, "Shield Command Specialist", 4)
engine.add_implant(source, "Shield Command Mindlink")
engine.set_implant_active(source, 10, False)
engine.set_module_states(source, [1], "ONLINE")
engine.set_command_active(source, fit, False)
engine.remove_command(source, fit)
engine.remove_implant(source, 10)
```

`add_command` accepts an existing source/recipient and defaults to `active=True`.
Only boolean active states are accepted. Duplicate adds and edits/removals of a
missing link fail explicitly. Addition uses the desktop command's flush/refresh
pattern; removal clears the reverse association. EOS controls command selection,
effect application and recipient invalidation. No command formula was ported.

`set_skill_level` accepts a named skill and integer 0–5 on the fit's synthetic
character, calls EOS `Skill.setLevel` with its normal restriction behavior, then
recalculates. Full character profiles, unlearned/alpha states and shared-character
editing remain C06. Each prototype fit has its own synthetic character.

Implant methods operate on the fit-local list selected by this prototype's
`ImplantLocation.FIT`. Addition validates the item and vacant slot before append;
an occupied slot fails without changing the current implant. State/removal use
the integer slot. This path needs no GUI `makeRoom` helper. Replacement, implant
sets, character-location selection and full C07 behavior are still pending.

`set_module_states` accepts a nonempty unique index selection and EOS state name.
It validates every selected module before mutation, then recalculates together,
restoring previous states if recalculation raises. This does not replace the full
restriction checking, undo system or fitting editor owned by B04/B09/C09.

All source edits recalculate EOS so linked recipients are invalidated. The
existing `projection_snapshot` is reused for A05's 39-field sample. The
[command reference](../tools/android_reference/COMMANDS.md) verifies two command
skills, mindlink addition/state/removal, module and link toggles, two burst charges
and independent recipient updates. Full burst coverage, multiple-source overlap,
self/reciprocal commands, projection interactions, persistence and native Android
execution remain D03/A09. These APIs are provisional and not general transactions.

## Small upstream compatibility change

`eos/db/migration.py` previously imported root desktop `config` eagerly. That
imports wx and creates desktop color/configuration objects even for an in-memory
EOS calculation. Its only need in migration is the saved-file backup path.

The import now occurs inside the older-schema migration branch, immediately
before the existing backup. Backup names, source paths, migration order and
version updates are unchanged. The regression check uses genuine desktop config
and wx to migrate a disposable schema-48 database to 49, verifies the backup
bytes and retained row, and verifies a second call is a no-op. Headless checks
also prove that checking a current schema does not import desktop config.

Other UI coupling remains: `eos/effectHandlerHelpers.py` has lazy `gui` imports in
implant, booster and projected-environment `makeRoom` helpers. A03–A05 do not call
them. Investigate relevant paths in the owning later task; do not stub wx, inject
a fake config module or claim the entire engine is already decoupled.

## B04.2.2 module mutations

The serialized contract adds `add_module`, `replace_module`, `remove_module` and
`set_fit_restrictions`, with expected revisions and the existing atomic graph
commit. `fitting_details` returns worker-owned slot/resource/skill/legality data;
`recent_items` returns up to 20 actual-use item IDs. EOS retains every formula.
The isolated `fitting.py` policy follows the pinned desktop commands and preserves
vacant positions, default states, group/hull/rig/hardpoint limits and overrides.
Resource/skill overloads warn without rejecting edits. Re-enable deliberately
retains excess hardpoints as desktop does.

Valid-item attempts rejected by legality still promote recent use after restoring
the unchanged fit graph. Malformed/stale requests and failed saves preserve both.
Optional graph history and fit restriction/vacancy inputs survive copy/restart;
older binaries reject these inputs without replacing the saved file. Full
upgrade/downgrade verification remains R02. Charge/variation/order mutations are
B04.2.3, bulk workflows B05, and dedicated subsystem/mode editing B06.

## B04.2.3.1 charge editing and discovery

`set_module_charge` takes fit ID, position and nullable bundled charge ID with an
expected revision. It validates the complete edit before assignment, follows
original EOS recalculation/state checks and preserves recent equipment history.
`charge_options(fit_id)` returns complete compatible IDs/names for each module and
the active local fit union, correlated with fit identity and revision. Reads do
not save inputs. Vacancies have no item/charge and no choices. Earlier bulk
`set_charges` remains unchanged; B05 retains its full editing/selection scope.

The optional EOS gamedata cache is disabled before import, matching desktop
initialization and preventing item/group ID collisions. All prior correctness,
GC, restart and native performance gates remain required. See the architecture
and task brief for the independent charge oracle and compatibility boundary.

## B04.2.3.2 existing item variations

`variation_options(fit_id)` returns revision-correlated module/drone/fit-implant
targets, current inputs and complete ordered desktop choices with hull enablement.
`change_variation` takes fit ID, context (`module`, `drone`, `implant`), position
and bundled item ID. It validates family/enablement before editing. Modules
reconcile states and charges, drone replacements append a separate stack while
retaining total/active counts, and implant replacement retains activation and
FIT location. Recent use remains unchanged. Drone capture now records current
stack inputs in the same atomic graph. No schema, EOS formula or session changes.
Accepted unchanged selections advance the B01 acknowledgement revision while
preserving inputs, values, history and modified order. Bulk selection remains B05;
later addition editors retain their assigned features.

## B04.2.3.3 rack ordering and heat

`swap_modules` takes fit ID and integer `from_position`/`to_position`. An occupied
source and either an occupied or empty destination must share an editable rack.
Original module objects retain state and charge; the enclosing transaction handles
revision checks, recipient recalculation and save rollback. Recent use stays intact.
Same-position acknowledgement preserves inputs and modified order.
`rack_options(fit_id)` returns revision-correlated positions and the original
desktop Thermodynamics class's burnout estimates and probability samples. EOS
supplies modified attributes; Kotlin formats results. Failed estimates use null,
never a fabricated zero. These are desktop estimates, not measured game duration.
Subsystem configuration and heat options remain B06 and C09 respectively.
