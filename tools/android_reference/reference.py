#!/usr/bin/env python3
"""Build and sample the unmodified pinned desktop EOS in isolated processes.

This is a reference exporter, not the Android engine adapter. See README.md.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
from pathlib import Path
import sqlite3
import subprocess
import sys


SOURCE_COMMIT = "8b04f3b271e614b3e103853b44a7851a63d79d0e"
DEPENDENCIES = {
    "wxPython": "4.2.1", "logbook": "1.7.0.post0", "sqlalchemy": "1.4.50",
    "pyyaml": "6.0.1", "cryptography": "42.0.4", "numpy": "1.26.2",
    "greenlet": "3.0.3", "typing-extensions": "4.12.2", "pillow": "10.4.0",
    "six": "1.16.0", "cffi": "1.16.0", "pycparser": "2.22",
}
# All exported floats are unformatted engine values in the units in snapshot().
# Tight tolerance allows platform floating-point noise, not display rounding.
REL_TOL = 1e-10
ABS_TOL = 1e-9


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def validate_source(source):
    if git(source, "rev-parse", "HEAD") != SOURCE_COMMIT:
        raise ValueError("Reference checkout must be at " + SOURCE_COMMIT)
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Reference checkout must have no tracked changes or untracked files")
    for name in ("eos", "utils", "staticdata", "db_update.py", "config.py"):
        if not (source / name).exists():
            raise ValueError("Reference checkout is missing " + name)


def source_data_digest(source):
    # Normalize checkout line endings so Windows and Linux hash the same JSON.
    paths = git(source, "ls-tree", "-r", "--name-only", "HEAD", "staticdata").splitlines()
    manifest = {name: hashlib.sha256((source / name).read_bytes().replace(
        b"\r\n", b"\n")).hexdigest() for name in paths}
    return hashlib.sha256(canonical(manifest)).hexdigest()


def logical_database_digest(path):
    """Hash schema/columns and sorted rows, independently of SQLite file layout."""
    digest = hashlib.sha256()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Generated database failed SQLite integrity_check")
        tables = db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' "
                            "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        for name, schema in tables:
            quoted = '"' + name.replace('"', '""') + '"'
            columns = [row[1] for row in db.execute("PRAGMA table_info(" + quoted + ")")]
            digest.update(canonical([name, schema, columns]) + b"\n")
            order = ",".join(str(i + 1) for i in range(len(columns)))
            for row in db.execute("SELECT * FROM " + quoted + " ORDER BY " + order):
                digest.update(canonical(row) + b"\n")
    return digest.hexdigest()


def compare(expected, actual, path="root"):
    """Compare complete structures; do not skip missing/extra fields or booleans."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        if expected.keys() != actual.keys():
            raise ValueError(path + ": keys differ")
        for key in expected:
            compare(expected[key], actual[key], path + "." + key)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            raise ValueError(path + ": lengths differ")
        for i, (left, right) in enumerate(zip(expected, actual)):
            compare(left, right, f"{path}[{i}]")
    elif type(expected) is float and type(actual) is float:
        if not math.isfinite(expected) or not math.isfinite(actual) or not math.isclose(
                expected, actual, rel_tol=REL_TOL, abs_tol=ABS_TOL):
            raise ValueError(f"{path}: {expected!r} != {actual!r}")
    elif type(expected) is not type(actual) or expected != actual:
        raise ValueError(f"{path}: {expected!r} != {actual!r}")


def bootstrap(source, database):
    # Children use -I: no PYTHONPATH, user site packages or working-directory imports.
    sys.path.insert(0, str(source))
    import eos.config
    eos.config.saveddata_connectionstring = "sqlite:///:memory:"
    eos.config.gamedata_connectionstring = "sqlite:///" + database.as_posix()
    eos.config.set_lang("en")
    return eos.config


def build(source, output):
    bootstrap(source, output / "eve.db")
    import db_update
    db_update.DB_PATH = str(output / "eve.db")
    db_update.update_db()


def snapshot(fit):
    def stat(value, unit):
        return {"value": value, "unit": unit}

    ship = fit.ship.getModifiedItemAttr
    stats = {
        "cpu_used": stat(fit.getItemAttrOnlineSum(fit.modules, "cpu"), "tf"),
        "cpu_output": stat(ship("cpuOutput"), "tf"),
        "powergrid_used": stat(fit.getItemAttrOnlineSum(fit.modules, "power"), "MW"),
        "powergrid_output": stat(ship("powerOutput"), "MW"),
        "drone_control_range": stat(fit.extraAttributes["droneControlRange"], "m"),
        "drone_bandwidth_used": stat(fit.droneBandwidthUsed, "Mbit/s"),
        "weapon_dps": stat(fit.getWeaponDps().total, "HP/s"),
        "drone_dps": stat(fit.getDroneDps().total, "HP/s"),
        "total_dps": stat(fit.getTotalDps().total, "HP/s"),
        "total_volley": stat(fit.getTotalVolley().total, "HP"),
        "capacitor_capacity": stat(ship("capacitorCapacity"), "GJ"),
        "capacitor_recharge_time": stat(ship("rechargeRate"), "ms"),
        "capacitor_used": stat(fit.capUsed, "GJ/s"),
        "capacitor_recharge": stat(fit.capRecharge, "GJ/s"),
        "capacitor_stable": stat(fit.capStable, "boolean"),
        # Pyfa returns percent when stable, seconds to depletion when unstable.
        "capacitor_state": stat(fit.capState, "%" if fit.capStable else "s"),
        "max_velocity": stat(ship("maxVelocity"), "m/s"),
        "max_target_range": stat(ship("maxTargetRange"), "m"),
        "gun_optimal": stat(fit.modules[0].getModifiedItemAttr("maxRange"), "m"),
        "gun_falloff": stat(fit.modules[0].getModifiedItemAttr("falloff"), "m"),
    }
    for layer in ("shield", "armor", "hull"):
        stats[layer + "_hp"] = stat(fit.hp[layer], "HP")
        stats[layer + "_ehp_uniform"] = stat(fit.ehp[layer], "HP")
    for layer, prefix in (("shield", "shield"), ("armor", "armor"), ("hull", "")):
        for damage in ("em", "thermal", "kinetic", "explosive"):
            attribute = (prefix + damage.title() if prefix else damage) + "DamageResonance"
            stats[layer + "_" + damage + "_resonance"] = stat(ship(attribute), "fraction")
    return stats


def export(source, output, name):
    config = bootstrap(source, output / "eve.db")
    import eos.db
    from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.drone import Drone
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship

    case = json.loads(Path(__file__).with_name("vexor.json").read_text())
    if case["target_profile"] is not None or any(case[key] for key in (
            "implants", "boosters", "projections", "commands", "environments")):
        raise ValueError("A01 exporter does not implement those scenario inputs yet")
    resolved = {}

    def item(item_name):
        value = eos.db.getItem(item_name)
        if value is None:
            raise ValueError("No such pinned-data item: " + item_name)
        resolved[item_name] = value.ID
        return value

    fit = Fit(Ship(item(case["ship"])), name=case["name"])
    fit.character = Character("Synthetic all-V reference", defaultLevel=case["skill_level"])
    fit.damagePattern = DamagePattern(**case["damage_pattern"])
    fit.targetProfile = None
    fit.factorReload = case["factor_reload"]
    fit.implantLocation = ImplantLocation.FIT
    fit.systemSecurity = FitSystemSecurity[case["security"]["system"]]
    fit.pilotSecurity = case["security"]["pilot"]
    fit.ignoreRestrictions = False
    for row in case["modules"]:
        module = Module(item(row["name"]))
        if row.get("charge"):
            module.charge = item(row["charge"])
        module.state = FittingModuleState[row["state"]]
        module.owner = fit
        fit.modules.append(module)
    for row in case["drones"]:
        drone = Drone(item(row["name"]))
        drone.amount = row["amount"]
        drone.amountActive = row["active"]
        drone.owner = fit
        fit.drones.append(drone)

    fit.calculateModifiedAttributes()
    if not fit.fits:
        raise ValueError("Synthetic fit contains incompatible equipment")
    initial = snapshot(fit)
    for index in case["edit"]["module_indices"]:
        fit.modules[index].charge = item(case["edit"]["charge"])
    fit.clear()
    fit.calculateModifiedAttributes()
    changed = snapshot(fit)
    for index in case["edit"]["module_indices"]:
        fit.modules[index].charge = item(case["modules"][index]["charge"])
    fit.clear()
    fit.calculateModifiedAttributes()
    restored = snapshot(fit)
    compare(initial, restored, "ammo_restoration")
    if not (0 < changed["weapon_dps"]["value"] < initial["weapon_dps"]["value"]):
        raise ValueError("Changing to Iron must reduce this reference fit's weapon DPS")
    if changed["gun_optimal"]["value"] <= initial["gun_optimal"]["value"]:
        raise ValueError("Changing to Iron must increase this reference fit's optimal")
    for key in ("drone_dps", "drone_control_range", "cpu_used", "powergrid_used"):
        compare(initial[key], changed[key], "unchanged_" + key)
    for key in ("weapon_dps", "drone_dps", "drone_control_range", "capacitor_capacity"):
        if initial[key]["value"] <= 0:
            raise ValueError("Reference must exercise " + key)

    imported = {}
    for module_name in ("eos", "eos.saveddata.fit", "db_update", "config"):
        module = sys.modules.get(module_name)
        if module is not None:
            path = Path(module.__file__).resolve()
            imported[module_name] = path.relative_to(source).as_posix()
    result = {
        "schema_version": 1,
        "source_commit": SOURCE_COMMIT,
        "source_data_sha256": source_data_digest(source),
        "dataset_metadata": dict(eos.db.gamedata_session.execute(
            "SELECT field_name, field_value FROM metadata").fetchall()),
        "inputs": case,
        "resolved_item_ids": resolved,
        "eos_settings": dict(config.settings),
        "reference_imports": imported,
        "states": {"initial": initial, "iron_ammunition": changed, "restored": restored},
    }
    (output / name).write_text(json.dumps(result, indent=2, sort_keys=True,
                                         allow_nan=False) + "\n", encoding="utf-8")


def run_child(args, kind, name="unused"):
    command = [sys.executable, "-I", str(Path(__file__).resolve()), "--source",
               str(args.source), "--output", str(args.output), "--worker", kind,
               "--result-name", name]
    log = args.output / ("build.log" if kind == "build" else name + ".log")
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True,
                       cwd=args.source, timeout=600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New disposable directory outside either checkout")
    parser.add_argument("--check", type=Path, help="Compare against a committed fixture")
    parser.add_argument("--worker", choices=("build", "export"), help=argparse.SUPPRESS)
    parser.add_argument("--result-name", default="fixture.json", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.source = args.source.resolve()
    args.output = args.output.resolve()
    if sys.version_info[:2] != (3, 11):
        raise ValueError("Use Python 3.11 for the pinned desktop reference")
    validate_source(args.source)
    if args.worker:
        if args.worker == "build":
            build(args.source, args.output)
        else:
            export(args.source, args.output, args.result_name)
        return

    versions = {name: importlib.metadata.version(name) for name in DEPENDENCIES}
    compare(DEPENDENCIES, versions, "dependencies")
    project = Path(__file__).resolve().parents[2]
    if args.output.is_relative_to(args.source) or args.output.is_relative_to(project):
        raise ValueError("Output must be outside both source and development checkouts")
    args.output.mkdir(parents=True, exist_ok=False)
    print("Building database from pinned static data...", flush=True)
    run_child(args, "build")
    logical = logical_database_digest(args.output / "eve.db")
    for name in ("fixture.json", "repeat.json"):
        run_child(args, "export", name)
    fixture = json.loads((args.output / "fixture.json").read_text())
    compare(fixture, json.loads((args.output / "repeat.json").read_text()), "fresh_process")
    fixture["database_logical_sha256"] = logical
    fixture["comparison_tolerance"] = {"relative": REL_TOL, "absolute": ABS_TOL}
    if args.check:
        compare(json.loads(args.check.read_text()), fixture, "committed_fixture")
    (args.output / "fixture.json").write_text(
        json.dumps(fixture, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    evidence = {
        "python": platform.python_version(), "platform": platform.platform(),
        "sqlite": sqlite3.sqlite_version, "dependencies": versions,
        "source_commit": SOURCE_COMMIT,
        "source_data_sha256": fixture["source_data_sha256"],
        "database_sha256": digest_file(args.output / "eve.db"),
        "database_logical_sha256": logical,
        "database_bytes": (args.output / "eve.db").stat().st_size,
        "exporter_sha256": digest_file(Path(__file__)),
        "fixture_sha256": digest_file(args.output / "fixture.json"),
        "checks": {"fresh_process_repeat": True, "reversible_ammo_edit": True,
                   "committed_fixture_match": True if args.check else None},
    }
    (args.output / "evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validate_source(args.source)
    print(json.dumps({"result": "PASS", "stats_per_state": len(fixture["states"]["initial"]),
                      "states": len(fixture["states"]), "checks": evidence["checks"]}))


if __name__ == "__main__":
    main()
