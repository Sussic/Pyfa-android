#!/usr/bin/env python3
"""A05 oracle: command bursts from unmodified pinned desktop EOS."""

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
from tools.android_reference.projection import read, write


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
    from eos.saveddata.implant import Implant
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship

    case = read(Path(__file__).with_name("command.json"))
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
        fit.character = Character("A05 synthetic skills", defaultLevel=spec["skill_level"])
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
        for name, fit in (("source", source), ("target", target)):
            if not fit.calculated:
                fit.calculateModifiedAttributes()
            result[name] = snapshot(fit)
            result[name]["scan_resolution"] = {"value": fit.ship.getModifiedItemAttr("scanResolution"), "unit": "mm"}
            if fit.commandBonuses:
                raise ValueError("Finished fit retains unconsumed command bonuses")
        return result

    states = {"initial": sample()}
    for step in case["steps"]:
        op = step["operation"]
        changed = source
        if op == "add":
            target.commandFitDict[source.ID] = source
            # Desktop CalcAddCommandCommand uses this flush/refresh to rekey
            # reverse associations by the recipient ID (upstream issue #83).
            session.flush()
            session.refresh(source)
            changed = target
        elif op == "command_state":
            source.getCommandInfo(target.ID).active = step["active"]
            changed = target
        elif op == "skill":
            source.character.getSkill(item(step["skill"])).setLevel(step["level"])
        elif op == "implant_add":
            implant = Implant(item(step["implant"]))
            if any(i.slot == implant.slot for i in source.implants):
                raise ValueError("Oracle implant slot is already occupied")
            source.implants.append(implant)
        elif op in ("implant_state", "implant_remove"):
            implant = next(i for i in source.implants if i.slot == step["slot"])
            if op == "implant_state":
                implant.active = step["active"]
            else:
                source.implants.remove(implant)
        elif op == "module_state":
            for index in step["module_indices"]:
                source.modules[index].state = FittingModuleState[step["state"]]
        elif op == "charges":
            for index in step["module_indices"]:
                source.modules[index].charge = item(step["charge"])
        elif op == "remove":
            del target.commandFitDict[source.ID]
            session.flush()
            session.refresh(source)
            if source.getCommandInfo(target.ID) is not None:
                raise ValueError("Removed command retains a reverse link")
            changed = target
        else:
            raise ValueError("Unsupported reference operation")
        changed.clear()
        changed.calculateModifiedAttributes()
        states[step["name"]] = sample()

    for name in ("removed", "removed_again"):
        compare(states["initial"], states[name], "complete_restoration." + name)
    for name in ("burst_online", "link_inactive"):
        compare(states["initial"]["target"], states[name]["target"], "recipient_restoration." + name)
    for name in ("specialist_restored", "command_ships_restored", "mindlink_inactive", "mindlink_removed", "reapplied"):
        compare(states["applied"], states[name], "restored_strength." + name)
    for name in ("mindlink_active", "burst_active", "link_active", "extension_restored"):
        compare(states["mindlink_added"], states[name], "restored_mindlink." + name)
    hp = lambda name: states[name]["target"]["shield_hp"]["value"]
    for name in ("specialist_4", "command_ships_4"):
        if not hp("initial") < hp(name) < hp("applied") < hp("mindlink_added"):
            raise ValueError("Skills and mindlink must change received burst strength")
    compare(states["initial"]["target"]["shield_hp"], states["harmonizing"]["target"]["shield_hp"])
    for damage in ("em", "thermal", "kinetic", "explosive"):
        key = "shield_" + damage + "_resonance"
        if not states["harmonizing"]["target"][key]["value"] < states["initial"]["target"][key]["value"]:
            raise ValueError("Harmonizing must replace HP with resistance bonuses")
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
                "checks": {"fresh_process_repeat": True, "skill_implant_state_charge_changes": True,
                           "complete_restoration": True, "game_database_unchanged": True,
                           "no_pending_command_bonuses": True,
                           "committed_fixture_match": True if args.check else None}}
    write(args.output / "evidence.json", evidence)
    validate_source(args.source)
    print(json.dumps({"result": "PASS", "states": evidence["states"], "checks": evidence["checks"]}))


if __name__ == "__main__":
    main()
