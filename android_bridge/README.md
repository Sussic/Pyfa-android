# A03 headless EOS boundary

This is a host-tested Python prototype for the Android port, not an Android app
or the complete bridge contract. It uses this checkout's EOS calculations and a
separate, existing game database. See [verification commands](../tools/android_headless/README.md).

## Initialization and dependencies

The tested host baseline is Python 3.11 with Logbook 1.7.0.post0, SQLAlchemy 1.4.50
and its Greenlet 3.0.3 dependency. The runtime needs the `android_bridge`, `eos`
and `utils` packages. It does not require wxPython, NumPy, PyYAML, cryptography,
Pillow, root `config.py`, `gui`, or `service` for the A03 case. This dependency list
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
profiles. A04/A05 introduce the first linked-effect cases separately.

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
implant, booster and projected-environment `makeRoom` helpers. A03 does not call
them. Investigate relevant paths in the owning later task; do not stub wx, inject
a fake config module or claim the entire engine is already decoupled.
