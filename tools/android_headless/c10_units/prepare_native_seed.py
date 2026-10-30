"""Deferred synthetic UNITS1 UI seed preparation; use a fresh canonical policy job.

Run with the qualified Python 3.11 headless environment, -I -B, explicit paths
and a fresh output outside both source trees. Produces graph.sqlite3, the exact
independent test-APK oracle asset, source-manifest.json and seed.json. It never
installs an APK, touches app data, or establishes native/UI acceptance.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys
import traceback


REFERENCE_PIN = "8b04f3b271e614b3e103853b44a7851a63d79d0e"
DATABASE_PIN = "e0dc4b3d281bd949f0a8089d587053ad66c0fcef90163cc6988e670d15d01065"
LOGICAL_PIN = "5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607"
ORACLE_PIN = "0e9cddf9eb8df1c8c31620167dc4c86596d782a42d9e7859b7edce708d6205e7"
ASSET_NAME = "module438-repeat.raw.json"
FIT_NAME = "C10 existing rolled afterburner"
DEPENDENCIES = {"logbook": "1.7.0.post0", "sqlalchemy": "1.4.50", "greenlet": "3.0.3"}
FORBIDDEN = ("wxPython", "numpy", "cryptography", "pyyaml", "pillow")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def exact(actual, expected, label):
    require(type(actual) is type(expected), label + ": scalar/container type differs")
    if isinstance(expected, dict):
        require(actual.keys() == expected.keys(), label + ": keys differ")
        for key in expected:
            exact(actual[key], expected[key], label + "." + str(key))
    elif isinstance(expected, list):
        require(len(actual) == len(expected), label + ": length differs")
        for index, (left, right) in enumerate(zip(actual, expected)):
            exact(left, right, label + "." + str(index))
    elif type(expected) is float:
        require(math.isfinite(actual) and actual.hex() == expected.hex(), label + ": raw float bits differ")
    else:
        require(actual == expected, label + ": value differs")


def validate_inputs(args):
    require(sys.version_info[:2] == (3, 11), "Use the qualified project Python 3.11 environment")
    require(sys.flags.isolated and sys.dont_write_bytecode, "Launch with -I -B")
    # A full portable candidate can supply its bridge and EOS from one tree.
    require(not args.output.exists(), "Output must be new")
    for source in (args.candidate, args.product_source):
        require(not args.output.is_relative_to(source) and not source.is_relative_to(args.output),
                "Output must be outside and must not contain either source tree")
    for source in (args.database, args.oracle, Path(__file__).resolve()):
        require(not source.is_relative_to(args.output), "Output must not contain an input")
    require(args.oracle.name == ASSET_NAME, "Supply the exact retained repeat-oracle basename")
    require(args.oracle_sha256.lower() == ORACLE_PIN and sha(args.oracle) == ORACLE_PIN,
            "Independent retained oracle SHA256 differs")
    require(sha(args.database) == DATABASE_PIN, "Pinned game database SHA256 differs")
    for name, version in DEPENDENCIES.items():
        require(importlib.metadata.version(name) == version, "Headless dependency differs: " + name)
    for name in FORBIDDEN:
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        raise RuntimeError("Use a clean headless environment without " + name)
    oracle = json.loads(args.oracle.read_text(encoding="utf-8-sig"))
    require(oracle["schema"] == 1 and oracle["source_commit"] == REFERENCE_PIN,
            "Unsupported independent oracle provenance")
    require(oracle["database_sha256"] == DATABASE_PIN and
            oracle["database_logical_sha256"] == LOGICAL_PIN, "Oracle dataset pins differ")
    require((oracle["base_item_id"], oracle["mutaplasmid_id"], oracle["resulting_item_id"])
            == (438, 47746, 47749), "Wrong independent mutation pair")
    exact([state["fraction"] for state in oracle["states"]], [0.25, 0.75], "oracle fractions")
    baseline = oracle["states"][0]["attributes"]
    exact([row["attribute_id"] for row in baseline], [6, 20, 30, 50], "baseline IDs")
    spec = oracle["initial_spec"]
    require(spec["name"] == FIT_NAME and spec["ship"] == "Rifter", "Wrong synthetic fit")
    require(len(spec["modules"]) == 1, "Seed must contain exactly one fitted module")
    module = spec["modules"][0]
    require(module["name"] == "1MN Abyssal Afterburner" and module["state"] == "ACTIVE",
            "Wrong initial module or state")
    require((module["mutation"]["base_item_id"], module["mutation"]["mutaplasmid_id"])
            == (438, 47746), "Wrong initial mutation identity")
    exact(module["mutation"]["attributes"], baseline, "independent initial raw vector")
    for name in ("implants", "boosters", "projections", "commands", "environments", "drones"):
        exact(spec[name], [], "independent empty " + name)
    return oracle


def source_manifest(args):
    # Bind the complete derivative (including the later native consumer), every
    # EOS/utils Python source and both imported headless helper packages.
    paths = {Path(__file__).resolve()}
    paths.update(path for path in args.candidate.rglob("*") if path.is_file()
                 and ".git" not in path.relative_to(args.candidate).parts
                 and "__pycache__" not in path.parts)
    for package in ("eos", "utils", "tools/android_headless", "tools/android_reference"):
        paths.update((args.product_source / package).rglob("*.py"))
    for package in ("tools", "tools/android_headless", "tools/android_reference"):
        initializer = args.product_source / package / "__init__.py"
        if initializer.is_file():
            paths.add(initializer)
    required = {}
    for path in sorted(paths, key=str):
        require(path.is_file(), "Missing bound source: " + str(path))
        required[str(path.resolve())] = {"sha256": sha(path), "size_bytes": path.stat().st_size}
    for relative in ("android_bridge/engine.py", "android_bridge/contract.py", "android_bridge/store.py",
                     "android_bridge/fitting.py", "android_bridge/mutation_records.py",
                     "android_bridge/mutation_units.py"):
        require(str((args.candidate / relative).resolve()) in required, "Missing derivative dependency: " + relative)
    for relative in ("tools/android_headless/check.py", "tools/android_reference/reference.py"):
        require(str((args.product_source / relative).resolve()) in required, "Missing headless helper: " + relative)
    return {"schema_version": 1, "candidate": str(args.candidate),
            "product_source": str(args.product_source), "required_files": required}


def open_runtime(args):
    require(not any(name.split(".")[0] in {"android_bridge", "eos", "utils", "wx", "gui", "service", "config"}
                    for name in sys.modules), "Use a fresh isolated OS process")
    network = []

    def block(event, arguments):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            network.append(event)
            raise RuntimeError("Offline seed preparation forbids network: " + event)
    sys.addaudithook(block)
    sys.path.insert(0, str(args.product_source))
    from tools.android_headless.check import NoDesktop
    from tools.android_reference.reference import logical_database_digest
    barrier = NoDesktop()
    sys.meta_path.insert(0, barrier)
    require(logical_database_digest(args.database) == LOGICAL_PIN, "Logical dataset SHA256 differs")
    sys.path.insert(0, str(args.candidate))
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.fitting import _fill
    from android_bridge.store import GraphStore, decode_graph, encode_graph, SCHEMA_VERSION
    require(SCHEMA_VERSION == 1, "Unsupported GraphStore schema")
    return (HeadlessEngine(args.database), BridgeSession, GraphStore, _fill,
            decode_graph, encode_graph, barrier, network)


def check_origins(args, manifest, barrier, network):
    require(not barrier.attempts and not network, "Forbidden desktop/network operation attempted")
    loaded = {}
    roots = {"android_bridge": args.candidate, "eos": args.product_source,
             "utils": args.product_source, "tools": args.product_source}
    for name, module in list(sys.modules.items()):
        top = name.split(".")[0]
        require(top not in {"wx", "gui", "service", "config"}, "Desktop module loaded: " + name)
        filename = getattr(module, "__file__", None)
        if top not in roots or not filename:
            continue
        path = Path(filename).resolve()
        require(path.is_relative_to(roots[top]), "Imported source origin differs: " + name)
        require(str(path) in manifest["required_files"], "Imported source was not bound: " + str(path))
        loaded[name] = {"path": str(path), "sha256": sha(path)}
    return loaded


def check_bridge(bridge, oracle):
    require(len(bridge._records) == 1 and list(bridge._records) == [bridge.sample_id], "Expected one synthetic fit")
    key = bridge.sample_id
    record = bridge._records[key]
    require(bridge._revisions == {key: 1}, "Seed revision must start at one")
    history = bridge.history_details(key)
    require(history["undo_count"] == history["redo_count"] == 0, "Seed history must be empty")
    require(record["projections"] == record["commands"] == [], "Seed must have no graph links")
    require("inspection_ids" in record and record["inspection_ids"]["modules"],
            "Seed requires current inspection identities")
    spec = record["spec"]
    require(spec["name"] == FIT_NAME and spec["ship"] == "Rifter", "Captured synthetic fit differs")
    nonempty = [(position, row) for position, row in enumerate(spec["modules"]) if "empty_slot" not in row]
    require(len(nonempty) == 1 and nonempty[0][0] == 0, "Existing afterburner must remain at module position zero")
    module = nonempty[0][1]
    require(module["name"] == "1MN Abyssal Afterburner" and module["state"] == "ACTIVE", "Captured module differs")
    exact(module["mutation"], oracle["initial_spec"]["modules"][0]["mutation"], "captured raw mutation")
    for field in ("drones", "projections", "commands", "environments"):
        exact(spec[field], [], "captured empty " + field)
    for field in ("projected_modules", "projected_drones", "projected_fighters", "fighters", "cargo"):
        exact(spec.get(field, []), [], "captured empty " + field)
    require(bridge._fits[key].modules[0].item.ID == 47749, "EOS resulting module ID differs")
    details = bridge.mutation_details(key)
    require(details["version"] == 1 and len(details["items"]) == 1, "Unexpected mutation query shape")
    item = details["items"][0]
    require(item["kind"] == "module" and item["position"] == 0, "Unexpected mutation item")
    require((item["base_item_id"], item["mutaplasmid_id"]) == (438, 47746), "Queried mutation identity differs")
    vector = [{"attribute_id": row["attribute_id"], "value": row["value"]} for row in item["attributes"]]
    exact(vector, oracle["states"][0]["attributes"], "queried raw baseline bits")
    return {"fit_id": key, "object_key": item["object_key"], "position": 0,
            "raw_vector": vector, "raw_float_hex": {str(row["attribute_id"]): row["value"].hex() for row in vector},
            "history": history, "vacant_module_rows": len(spec["modules"]) - 1,
            "inspection_ids": deepcopy(record["inspection_ids"])}


def prepare(args):
    oracle = validate_inputs(args)
    bound = source_manifest(args)
    runtime = open_runtime(args)
    engine, BridgeSession, GraphStore, fill, decode_graph, encode_graph, barrier, network = runtime
    exact(engine.settings, oracle["eos_settings"], "independent EOS settings")
    spec = deepcopy(oracle["initial_spec"])
    fit = engine.create_fit(spec, restore=True)
    # The existing raw editor also fills vacancies. Normalize the synthetic UI
    # graph before its initial capture, preserving the oracle's raw mutation.
    fill(fit)
    bridge = BridgeSession(engine, fit, spec)
    observation = check_bridge(bridge, oracle)
    bridge._dataset_identity = LOGICAL_PIN
    graph = deepcopy(bridge._graph(bridge._records, bridge._revisions))
    require(graph["format"] == 1 and len(graph["fit_order"]) == 1, "Expected one-fit format-one graph")
    BridgeSession._validate_graph(graph, LOGICAL_PIN, engine.settings)
    args.output.mkdir(parents=True, exist_ok=False)
    args.output_created = True
    write_json(args.output / "source-manifest.json", bound)
    asset = args.output / ASSET_NAME
    with asset.open("xb") as stream:
        stream.write(args.oracle.read_bytes())
    require(sha(asset) == ORACLE_PIN, "Test-APK oracle asset copy differs")
    store = GraphStore(args.output / "graph.sqlite3")
    require(not store.opened_existing and store.current is None, "Seed store must be new")
    attempt = store.prepare(graph)
    store.write(attempt)
    require(store.confirm(attempt) == "new", "Seed graph durable commit was not confirmed")
    store.accept(attempt)
    graph_hash = sha(store.path)
    bridge._reset_storage()
    reopened = BridgeSession.open(engine, store.path, LOGICAL_PIN, None)
    require(reopened.persistence_info["opened_existing"] is True, "Graph must reopen as existing saved inputs")
    require(reopened.persistence_info["generation"] == 1, "Reopen must preserve the initial generation")
    exact(reopened._records, graph["records"], "actual GraphStore reopen records")
    exact(reopened._revisions, graph["revisions"], "actual GraphStore reopen revisions")
    exact(check_bridge(reopened, oracle), observation, "actual GraphStore reopen observation")
    require(encode_graph(reopened._graph(reopened._records, reopened._revisions)) == store.current.payload,
            "Actual graph reconstruction must equal the persisted payload")
    exact(decode_graph(store.current.payload), graph, "persisted graph payload")
    require(sha(store.path) == graph_hash, "Read-only reopen changed the seed database")
    loaded = check_origins(args, bound, barrier, network)
    exact(source_manifest(args), bound, "bound source remained unchanged")
    require(sha(args.database) == DATABASE_PIN and sha(args.oracle) == ORACLE_PIN,
            "Frozen data or oracle changed during preparation")
    seed = {"schema_version": 1, "task": "C10.F14.02.UNITS1", "synthetic_inputs_only": True,
            "status": "PREPARED_PENDING_NATIVE_ACCEPTANCE", "native_acceptance": False,
            "native_installation_performed": False, "app_data_written": False,
            "reference_source_commit": REFERENCE_PIN, "database_sha256": DATABASE_PIN,
            "database_logical_sha256": LOGICAL_PIN, "oracle_path": str(args.oracle),
            "oracle_asset": {"name": ASSET_NAME, "sha256": ORACLE_PIN, "size_bytes": asset.stat().st_size},
            "graph": {"name": store.path.name, "sha256": graph_hash, "schema": 1, "format": 1,
                      "generation": 1, "fit_count": 1, "fit_name": FIT_NAME,
                      "payload_sha256": store.current.digest, "opened_existing_on_host_reopen": True},
            "source_manifest_sha256": sha(args.output / "source-manifest.json"),
            "source_manifest": "source-manifest.json", "candidate": str(args.candidate),
            "product_source": str(args.product_source), "database_path": str(args.database),
            "python_executable": sys.executable, "python_executable_sha256": sha(sys.executable),
            "python_version": sys.version,
            "platform": platform.platform(), "dependencies": DEPENDENCIES,
            "loaded_source_modules": loaded, "desktop_import_attempts": barrier.attempts,
            "network_attempts": network, "baseline_fraction": 0.25, "target_fraction": 0.75,
            "vacancies_normalized_before_initial_capture": True,
            "synthetic_ui_shape": "fitting._fill before BridgeSession adoption; only module zero is fitted",
            "seed_observation": observation,
            "limits": ["Input preparation and same-process host reopen only; no native/UI proof",
                       "No APK build, installation, app-data write or writer-death test",
                       "Independent expected values remain exclusively in the copied retained oracle"]}
    write_json(args.output / "seed.json", seed)
    print(json.dumps({"status": seed["status"], "output": str(args.output),
                      "graph_sha256": graph_hash, "native_acceptance": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "product-source", "database", "oracle", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--oracle-sha256", required=True)
    args = parser.parse_args()
    for name in ("candidate", "product_source", "database", "oracle"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.output = args.output.resolve()
    args.output_created = False
    try:
        prepare(args)
    except Exception as error:
        # Preserve any newly written partial artifacts. Absence of seed.json is
        # never treated as a usable seed, and input files are never cleaned up.
        if args.output_created and not (args.output / "seed.json").exists():
            failure = args.output / "PREPARATION-FAILED.json"
            if not failure.exists():
                write_json(failure, {"status": "FAILED", "native_acceptance": False,
                                     "error": str(error), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    main()
