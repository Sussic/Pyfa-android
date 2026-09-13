#!/usr/bin/env python3
"""A04 oracle: unmodified pinned desktop EOS, never android_bridge."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (
    ABS_TOL, REL_TOL, SOURCE_COMMIT, DEPENDENCIES, bootstrap,
    compare, digest_file, logical_database_digest, snapshot, source_data_digest,
    validate_source)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def export(args):
    config = bootstrap(args.source, args.database)
    import eos.db
    import config as desktop_config
    import wx
    from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.drone import Drone
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship

    case = read(Path(__file__).with_name("projection.json"))
    resolved = {}
    session = eos.db.saveddata_session

    def item(name):
        value = eos.db.getItem(name)
        if value is None:
            raise ValueError("Missing pinned item: " + name)
        resolved[name] = value.ID
        return value

    def make(spec):
        if spec["target_profile"] is not None or any(spec[k] for k in (
                "implants", "boosters", "projections", "commands", "environments")):
            raise ValueError("Unsupported oracle input")
        fit = Fit(Ship(item(spec["ship"])), name=spec["name"])
        fit.character = Character("A04 synthetic skills", defaultLevel=spec["skill_level"])
        fit.damagePattern = DamagePattern(**spec["damage_pattern"])
        fit.targetProfile = None
        fit.factorReload = spec["factor_reload"]
        fit.implantLocation = ImplantLocation.FIT
        fit.systemSecurity = FitSystemSecurity[spec["security"]["system"]]
        fit.pilotSecurity = spec["security"]["pilot"]
        fit.ignoreRestrictions = False
        for row in spec["modules"]:
            module = Module(item(row["name"]))
            module.state = FittingModuleState[row["state"]]
            module.owner = fit
            if row.get("charge"):
                module.charge = item(row["charge"])
            fit.modules.append(module)
        for row in spec["drones"]:
            drone = Drone(item(row["name"]))
            drone.amount, drone.amountActive, drone.owner = row["amount"], row["active"], fit
            fit.drones.append(drone)
        fit.calculateModifiedAttributes()
        if not fit.fits:
            raise ValueError("Invalid reference equipment")
        session.add(fit)
        session.flush()
        return fit

    source, target = make(case["source"]), make(case["target"])

    def sample():
        result = {}
        # Desktop service.getFit recalculates invalidated fits before displaying.
        for name, fit in (("source", source), ("target", target)):
            if not fit.calculated:
                fit.calculateModifiedAttributes()
            result[name] = snapshot(fit)
            result[name]["scan_resolution"] = {"value": fit.ship.getModifiedItemAttr("scanResolution"), "unit": "mm"}
        return result

    states = {"initial": sample()}
    for step in case["steps"]:
        op = step["operation"]
        changed = target
        if op == "add":
            target.projectedFitDict[source.ID] = source
            # Matches desktop CalcAddProjectedFitCommand: flush and refresh the
            # source so its reverse association is keyed by the recipient ID.
            session.flush()
            session.refresh(source)
        if op in ("add", "configure"):
            info = source.getProjectionInfo(target.ID)
            info.projectionRange, info.active, info.amount = step["range_m"], step["active"], step["amount"]
        elif op == "charges":
            for index in step["module_indices"]:
                source.modules[index].charge = item(step["charge"])
            changed = source
        elif op == "remove":
            del target.projectedFitDict[source.ID]
            session.flush()
            session.refresh(source)
            if source.getProjectionInfo(target.ID) is not None:
                raise ValueError("Removed projection retains a reverse link")
        else:
            raise ValueError("Unsupported reference operation")
        changed.clear()
        changed.calculateModifiedAttributes()
        states[step["name"]] = sample()

    initial = states["initial"]
    for name in ("inactive", "removed", "removed_again"):
        compare(initial, states[name], "restoration." + name)
    for name in ("reactivated", "script_restored", "reapplied_default_range"):
        compare(states["applied_zero"], states[name], "reapplication." + name)
    ranges = [states[n]["target"]["max_target_range"]["value"] for n in (
        "applied_zero", "falloff", "distant", "initial")]
    if not 0 < ranges[0] < ranges[1] < ranges[2] < ranges[3]:
        raise ValueError("The case must exercise projection falloff")
    compare(initial["target"]["max_target_range"], states["script_changed"]["target"]["max_target_range"])
    if not states["script_changed"]["target"]["scan_resolution"]["value"] < initial["target"]["scan_resolution"]["value"]:
        raise ValueError("The script edit must affect recipient scan resolution")
    imported = {}
    for name, module in list(sys.modules.items()):
        if name.split(".")[0] == "android_bridge":
            raise ValueError("Oracle imported the adapter")
        if name.split(".")[0] in ("eos", "utils", "config") and getattr(module, "__file__", None):
            imported[name] = Path(module.__file__).resolve().relative_to(args.source).as_posix()
    write(args.output, {
        "schema_version": 1, "source_commit": SOURCE_COMMIT,
        "source_data_sha256": source_data_digest(args.source),
        "dataset_metadata": dict(eos.db.gamedata_session.execute("SELECT field_name, field_value FROM metadata").fetchall()),
        "inputs": case, "resolved_item_ids": resolved, "eos_settings": dict(config.settings),
        "reference_imports": imported, "desktop_wx_version": wx.__version__, "states": states})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True, help="Verified database from the A01 rebuild")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.source, args.database, args.output = args.source.resolve(), args.database.resolve(strict=True), args.output.resolve()
    validate_source(args.source)
    if sys.version_info[:2] != (3, 11):
        raise ValueError("Use pinned Python 3.11")
    versions = {name: importlib.metadata.version(name) for name in DEPENDENCIES}
    compare(DEPENDENCIES, versions, "desktop_dependencies")
    if args.worker:
        export(args)
        return
    if args.output.is_relative_to(ROOT) or args.output.is_relative_to(args.source) or args.database.is_relative_to(args.output):
        raise ValueError("Use a new output outside both checkouts and the input database")
    baseline = read(Path(__file__).parent / "fixtures/vexor.json")
    logical = logical_database_digest(args.database)
    compare(baseline["database_logical_sha256"], logical, "A01_database")
    before = digest_file(args.database)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ("fixture", "repeat"):
        with (args.output / (name + ".log")).open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--source", str(args.source),
                            "--database", str(args.database), "--output", str(args.output / (name + ".json")),
                            "--worker"], cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    fixture = read(args.output / "fixture.json")
    compare(fixture, read(args.output / "repeat.json"), "fresh_process")
    compare(before, digest_file(args.database), "database_unchanged")
    for key in ("source_data_sha256", "dataset_metadata", "eos_settings"):
        compare(baseline[key], fixture[key], key)
    fixture["database_logical_sha256"] = logical
    fixture["comparison_tolerance"] = {"relative": REL_TOL, "absolute": ABS_TOL}
    if args.check:
        compare(read(args.check), fixture, "committed_fixture")
    write(args.output / "fixture.json", fixture)
    evidence = {"python": platform.python_version(), "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
                "dependencies": versions, "source_commit": SOURCE_COMMIT,
                "source_data_sha256": fixture["source_data_sha256"], "database_logical_sha256": logical,
                "database_sha256": before, "fixture_sha256": digest_file(args.output / "fixture.json"),
                "exporter_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "states": len(fixture["states"]), "stats_per_fit": 39, "fits_per_state": 2,
                "checks": {"fresh_process_repeat": True, "range_and_script_changes": True,
                           "complete_restoration": True, "game_database_unchanged": True,
                           "committed_fixture_match": True if args.check else None}}
    write(args.output / "evidence.json", evidence)
    validate_source(args.source)
    print(json.dumps({"result": "PASS", "states": evidence["states"], "checks": evidence["checks"]}))


if __name__ == "__main__":
    main()
