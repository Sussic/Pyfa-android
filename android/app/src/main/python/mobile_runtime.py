"""Provisional, serialized Android entry point. EOS owns every value."""
import importlib.abc
import importlib.metadata
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time

_engine = None
_fit = None
_bridge = None
_case = None
_manifest = None
_boot_ms = None
_store_path = None
_forbidden = []
_equipment = None


class NoDesktop(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"wx", "gui", "service", "config"}:
            _forbidden.append(fullname)
            raise ImportError("Desktop dependency is unavailable on Android: " + fullname)


def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def boot(database_path, manifest_json, case_json, store_path=None):
    global _engine, _fit, _case, _manifest, _boot_ms, _store_path
    if _engine is not None:
        raise RuntimeError("Android engine has already started")
    start = time.monotonic()
    sys.meta_path.insert(0, NoDesktop())
    _manifest = json.loads(manifest_json)
    _case = json.loads(case_json)
    _store_path = str(store_path) if store_path else None
    with closing(sqlite3.connect(Path(database_path).as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("Bundled database failed SQLite quick_check")
    from android_bridge import HeadlessEngine
    _engine = HeadlessEngine(database_path)
    if _engine.metadata != _manifest["dataset_metadata"]:
        raise ValueError("Bundled dataset metadata differs from the build manifest")
    spec = dict(_case)
    del spec["edit"]
    if _store_path is None:
        _fit = _engine.create_fit(spec)
    _boot_ms = (time.monotonic() - start) * 1000
    return snapshot() if _fit is not None else encoded({"initialized": True})


def bridge_bootstrap():
    """Open saved fits, or adopt the explicitly ephemeral diagnostic sample."""
    global _bridge, _fit
    if _bridge is not None:
        raise RuntimeError("Android bridge has already started")
    from android_bridge.contract import BridgeSession
    spec = dict(_case)
    del spec["edit"]
    if _store_path is None:
        _bridge = BridgeSession(_engine, _fit, spec)
    else:
        _bridge = BridgeSession.open(
            _engine, _store_path, _manifest["database_logical_sha256"], spec)
    _fit = None  # Recovery may replace EOS objects; retain only logical IDs.
    return _bridge.bootstrap()


def bridge_sample_id():
    _engine._check_thread()
    return _bridge.sample_id


def library_catalog():
    from android_bridge.catalog import hull_catalog
    return encoded(hull_catalog(_engine))


def library_organization():
    return encoded(_bridge.organization())


def fitting_details(fit_id):
    return encoded(_bridge.fitting_details(fit_id))


def charge_options(fit_id):
    return encoded(_bridge.charge_options(fit_id))


def variation_options(fit_id):
    return encoded(_bridge.variation_options(fit_id))


def rack_options(fit_id):
    return encoded(_bridge.rack_options(fit_id))


def variation_families_diagnostics(fit_id):
    """Complete native menu enumeration using the production family policy."""
    from android_bridge.variations import choices
    from android_bridge.market_policy import MarketPolicy
    from eos.saveddata.module import Module
    import eos.db
    _engine._check_thread()
    fit, policy, rows = _bridge._fits[fit_id], MarketPolicy(), []
    for row in json.loads(equipment_catalog())['items']:
        category = row['category']
        if category not in ('Module', 'Structure Module', 'Drone', 'Implant'):
            continue
        item = eos.db.getItem(row['id'])
        if category in ('Module', 'Structure Module'):
            try:
                module = Module(item)
            except ValueError:
                continue
            if module.slot not in (1, 2, 3, 4, 8):
                continue
            context = 'module'
        elif category == 'Drone':
            context = 'drone'
        else:
            if 'implantness' not in item.attributes:
                continue
            context = 'implant'
        rows.append({'id': item.ID, 'context': context, 'choices': choices(_engine, fit, item, context, policy)})
    return encoded(rows)


def variation_addition_diagnostics(fit_id):
    _engine._check_thread()
    from eos.const import ImplantLocation
    fit = _bridge._fits[fit_id]
    return encoded({'drones': [{'index': i, 'id': drone.itemID, 'amount': drone.amount, 'active': drone.amountActive}
                              for i, drone in enumerate(fit.drones)],
        'implants': [{'index': i, 'id': implant.itemID, 'slot': implant.slot, 'active': implant.active}
                     for i, implant in enumerate(fit.implants)], 'implant_location': ImplantLocation(fit.implantLocation).name})


def charge_compatibility_diagnostics():
    """Complete native compatibility enumeration through production policy."""
    _engine._check_thread()
    from android_bridge.charges import compatible
    from eos.saveddata.module import Module
    import eos.db
    rows = []
    for item in json.loads(equipment_catalog())['items']:
        if item['category'] not in ('Module', 'Structure Module'):
            continue
        value = eos.db.getItem(item['id'])
        try:
            module = Module(value)
        except ValueError:
            continue  # Original ModuleInfo excludes non-fitting quantum cores.
        if module.slot in (1, 2, 3, 4, 8):
            rows.append({'id': item['id'], 'charge_ids': sorted(value.ID for value in compatible(module))})
    return encoded(rows)


def charge_module_diagnostics(fit_id):
    """Raw EOS charge effects for the debug native comparison, not UI formulas."""
    _engine._check_thread()
    from eos.const import FittingModuleState
    fit = _bridge._fits[fit_id]
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    units = {'maxRange': 'm', 'falloff': 'm', 'trackingSpeed': 'rad/s',
        'speed': 'ms', 'damageMultiplier': 'multiplier', 'capacitorNeed': 'GJ',
        'capacitorBonus': 'GJ', 'armorDamageAmount': 'HP', 'shieldBonus': 'HP',
        'miningAmount': 'm3', 'scanResolutionBonus': '%', 'maxTargetRangeBonus': '%'}
    return encoded([{'index': i, 'id': mod.itemID, 'state': FittingModuleState(mod.state).name,
        'charge_id': mod.chargeID, 'attributes': {key: {'value': mod.getModifiedItemAttr(key, None), 'unit': unit}
            for key, unit in units.items()}} for i, mod in enumerate(fit.modules) if not mod.isEmpty])


def recent_items():
    return encoded(_bridge.recent_items())


def module_defaults_diagnostics():
    """Real module construction policy for the debug native catalogue gate."""
    _engine._check_thread()
    from android_bridge import fitting
    from eos.const import FittingModuleState, FittingSlot
    catalogue = json.loads(equipment_catalog())
    before = dict(_engine.resolved_item_ids)
    rows = []
    try:
        for item in catalogue['items']:
            if item['category'] not in ('Module', 'Structure Module'):
                continue
            try:
                module = fitting.new_module(_engine, item['id'])
            except ValueError:
                continue
            rows.append({'id': module.itemID, 'name': module.item.name, 'slot': FittingSlot(module.slot).name,
                'state': FittingModuleState(module.state).name,
                'limit': 'ONLINE' if fitting.ONLINE_EFFECTS.intersection(module.item.effects) else 'ACTIVE'})
        return encoded(rows)
    finally:
        _engine.resolved_item_ids.clear()
        _engine.resolved_item_ids.update(before)


def equipment_catalog():
    global _equipment
    _engine._check_thread()
    if _equipment is None:
        from android_bridge.market import EquipmentMarket
        _equipment = EquipmentMarket(_engine)
    return encoded(_equipment.catalog())


def equipment_search(text):
    if _equipment is None:
        equipment_catalog()
    return encoded(_equipment.search(text))


def bridge_dispatch(request_json):
    if _bridge is None:
        raise RuntimeError("Start the Android bridge before sending requests")
    return _bridge.dispatch(request_json)


def bridge_diagnostics():
    """Read-only instrumentation provenance on the same engine worker."""
    if _bridge is None:
        raise RuntimeError("Start the bridge before reading diagnostics")
    _engine._check_thread()
    import eos.config
    return encoded({
        "engine_thread": threading.current_thread().name,
        "main_thread": threading.current_thread() is threading.main_thread(),
        "session_id": _bridge.session_id,
        "sample_id": _bridge.sample_id,
        "persistence": _bridge.persistence_info,
        "drones": {
            fit_id: [{"name": drone.item.name, "amount": drone.amount,
                      "active": drone.amountActive} for drone in fit.drones]
            for fit_id, fit in _bridge._fits.items()
        },
        "retained_fit_count": len(_engine._fits),
        "saveddata_connectionstring": eos.config.saveddata_connectionstring,
        "desktop_import_attempts": list(_forbidden),
        "dataset_metadata": _engine.metadata,
        "eos_settings": _engine.settings,
        "resolved_item_ids": dict(sorted(_engine.resolved_item_ids.items())),
        "manifest": _manifest,
    })


def _sample_fit():
    return _bridge.get_fit(_bridge.sample_id) if _bridge is not None else _fit


def _require_ephemeral():
    if _store_path is not None:
        raise RuntimeError("Legacy diagnostics require an ephemeral engine process")


def snapshot():
    fit = _sample_fit()
    stats = _engine.snapshot(fit)
    if _forbidden:
        raise RuntimeError("An unsupported desktop import was attempted")
    return encoded({"stats": stats, "ammunition": fit.modules[0].charge.name})


def set_ammunition(name):
    _require_ephemeral()
    if name not in (_case["modules"][0]["charge"], _case["edit"]["charge"]):
        raise ValueError("The development sample supports Antimatter and Iron ammunition")
    _engine.set_charges(_sample_fit(), _case["edit"]["module_indices"], name)
    return snapshot()


def resolved_items(specs, additional_items):
    # The worker/session is shared across tests. Report this case's identities,
    # not the cumulative items resolved by earlier unrelated operations.
    names = set(additional_items)
    for spec in specs:
        names.add(spec["ship"])
        for row in spec["modules"] + spec["drones"]:
            names.add(row["name"])
            if row.get("charge"):
                names.add(row["charge"])
    return {name: _engine.resolved_item_ids[name] for name in sorted(names)}


def verify_projection(case_json):
    """Exercise linked fits on the existing worker; return only observed values."""
    _require_ephemeral()
    from projection_probe import run
    case = json.loads(case_json)
    start = time.monotonic()
    actual = run(_engine, case)
    if _forbidden:
        raise RuntimeError("An unsupported desktop import was attempted")
    actual.update({
        "inputs": case, "dataset_metadata": _engine.metadata,
        "eos_settings": _engine.settings,
        "resolved_item_ids": resolved_items(
            [case["source"], case["target"]],
            [step["charge"] for step in case["steps"] if step["operation"] == "charges"]),
        "database_sha256": _manifest["database_sha256"],
        "database_logical_sha256": _manifest["database_logical_sha256"],
        "desktop_source_commit": _manifest["desktop_source_commit"],
        "source_data_sha256": _manifest["source_data_sha256"],
        "desktop_fixture_sha256": _manifest["projection_fixture_sha256"],
        "engine_source_sha256": _manifest["engine_source_sha256"],
        "desktop_import_attempts": list(_forbidden),
        "projection_sequence_ms": (time.monotonic() - start) * 1000,
    })
    return encoded(actual)


def verify_command(case_json):
    """Exercise command sources on the same worker; no expected values here."""
    _require_ephemeral()
    from command_probe import run
    case = json.loads(case_json)
    start = time.monotonic()
    actual = run(_engine, case)
    if _forbidden:
        raise RuntimeError("An unsupported desktop import was attempted")
    actual.update({
        "inputs": case, "dataset_metadata": _engine.metadata,
        "eos_settings": _engine.settings,
        "resolved_item_ids": resolved_items(
            [case["source"], case["target"]],
            [step[key] for step in case["steps"] for key in ("charge", "skill", "implant") if key in step]),
        "database_sha256": _manifest["database_sha256"],
        "database_logical_sha256": _manifest["database_logical_sha256"],
        "desktop_source_commit": _manifest["desktop_source_commit"],
        "source_data_sha256": _manifest["source_data_sha256"],
        "desktop_fixture_sha256": _manifest["command_fixture_sha256"],
        "engine_source_sha256": _manifest["engine_source_sha256"],
        "desktop_import_attempts": list(_forbidden),
        "command_sequence_ms": (time.monotonic() - start) * 1000,
    })
    return encoded(actual)


def verify_ammunition():
    """Return actual native values to the independent instrumentation comparator.

    No expected numbers or desktop exporter is imported by the Android runtime.
    Restore the existing sample so test order and activity recreation are safe.
    """
    start = time.monotonic()
    initial_name = _case["modules"][0]["charge"]
    try:
        initial = json.loads(set_ammunition(initial_name))["stats"]
        changed = json.loads(set_ammunition(_case["edit"]["charge"]))["stats"]
    finally:
        restored = json.loads(set_ammunition(initial_name))["stats"]
    import eos.db
    from sqlalchemy.exc import OperationalError
    readonly = False
    with eos.db.gamedata_engine.connect() as connection:
        try:
            connection.execute("UPDATE metadata SET field_value=field_value WHERE field_name='client_build'")
        except OperationalError as error:
            if "readonly" not in str(error).lower():
                raise
            readonly = True
    if not readonly:
        raise RuntimeError("EOS game database unexpectedly permits writes")
    import greenlet._greenlet
    from eos.db import migrations
    return encoded({
        "states": {"initial": initial, "iron_ammunition": changed, "restored": restored},
        "inputs": _case, "dataset_metadata": _engine.metadata,
        "eos_settings": _engine.settings,
        "resolved_item_ids": resolved_items([_case], [_case["edit"]["charge"]]),
        "database_sha256": _manifest["database_sha256"],
        "database_logical_sha256": _manifest["database_logical_sha256"],
        "desktop_source_commit": _manifest["desktop_source_commit"],
        "source_data_sha256": _manifest["source_data_sha256"],
        "desktop_fixture_sha256": _manifest["desktop_fixture_sha256"],
        "engine_source_sha256": _manifest["engine_source_sha256"],
        "python": sys.version, "native_greenlet_module": greenlet._greenlet.__file__,
        "dependencies": {name: importlib.metadata.version(name) for name in ("logbook", "sqlalchemy", "greenlet")},
        "engine_thread": threading.current_thread().name, "readonly_database": readonly,
        "migration_versions": sorted(migrations.updates),
        "desktop_import_attempts": _forbidden, "boot_ms": _boot_ms,
        "edit_sequence_ms": (time.monotonic() - start) * 1000,
    })


_benchmark = None


def prepare_benchmark(kind, case_json):
    """Prepare reusable fits outside measured edits; expose their provenance."""
    global _benchmark
    _require_ephemeral()
    if _engine is None:
        raise RuntimeError("Start the Android engine before preparing benchmarks")
    if _benchmark is None:
        from performance_probe import PerformanceProbe
        _benchmark = PerformanceProbe(_engine, _sample_fit())
    case = _case if kind == "ammunition" else json.loads(case_json)
    actual = _benchmark.prepare(kind, case)
    if _forbidden:
        raise RuntimeError("An unsupported desktop import was attempted")
    fixture_key = {"ammunition": "desktop_fixture_sha256", "projection": "projection_fixture_sha256",
                   "command": "command_fixture_sha256"}[kind]
    actual.update({
        "inputs": case, "dataset_metadata": _engine.metadata, "eos_settings": _engine.settings,
        "database_sha256": _manifest["database_sha256"],
        "database_logical_sha256": _manifest["database_logical_sha256"],
        "desktop_source_commit": _manifest["desktop_source_commit"],
        "source_data_sha256": _manifest["source_data_sha256"],
        "desktop_fixture_sha256": _manifest[fixture_key],
        "engine_source_sha256": _manifest["engine_source_sha256"],
        "desktop_import_attempts": list(_forbidden),
    })
    return encoded(actual)


def step_benchmark(operation):
    """Apply one edit to existing benchmark fits and serialize observed values."""
    _require_ephemeral()
    if _benchmark is None:
        raise RuntimeError("Prepare a benchmark before editing")
    actual = _benchmark.step(operation)
    if _forbidden:
        raise RuntimeError("An unsupported desktop import was attempted")
    return encoded(actual)
