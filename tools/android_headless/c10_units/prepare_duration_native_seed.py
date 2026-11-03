"""Deferred private module399 duration73 seed; fresh canonical policy job only.

Run with the qualified Python 3.11 headless environment, -I -B, explicit paths
and a fresh output outside both source trees. The oracle pin binds the accepted
independent original-reference fixture. Execution additionally requires accepted
finite three-case EOS proof. Both source trees must be clean Git checkouts at that
accepted EOS commit. Produces only a private graph.sqlite3, exact original oracle
byte copy, source-manifest.json and seed.json. No test-APK asset, installation,
app-data write or native acceptance is supplied. Existing seed tools stay intact.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path, PureWindowsPath
import platform
import re
import subprocess
import struct
import sys


REFERENCE_PIN = "8b04f3b271e614b3e103853b44a7851a63d79d0e"
DATABASE_PIN = "e0dc4b3d281bd949f0a8089d587053ad66c0fcef90163cc6988e670d15d01065"
LOGICAL_PIN = "5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607"
ORACLE_PIN = "14baf8fe09bca5783d7d6955ba3a7b57c2c884fa2d8b3987eaaf6b3b3d9d1136"
ORACLE_NAME = "module399-duration.raw.json"
FIT_NAME = "C10 independent module399 duration73"
CASE_ID = "module399-duration73"
PRODUCER_PIN = "e202db67cbb09bf90e69e9b958c175c7ccf96406877a5275199191405965c737"
REFERENCE_HELPER_PIN = "292b550ddb4552d74c87116ba82d12d828584f0a175913027cc17d2297f4ec20"
REFERENCE_REVIEW_STATUS = "ACCEPT_INDEPENDENT_REFERENCE_FIXTURE_WITH_ACTUAL_ZERO_CLOSURE"
FINITE_REVIEW_STATUS = "ACCEPT_FINITE_THREE_CASE_EOS_RECEIPT_SCHEMA"
METRIC_REL_TOL, METRIC_ABS_TOL = 1e-10, 1e-9
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


def metrics(actual, expected, label):
    if type(expected) is float:
        require(type(actual) is float and math.isfinite(actual) and math.isclose(
            actual, expected, rel_tol=METRIC_REL_TOL, abs_tol=METRIC_ABS_TOL), label + ": metric differs")
    elif isinstance(expected, dict):
        require(type(actual) is dict and actual.keys() == expected.keys(), label + ": metric keys differ")
        for key in expected:
            metrics(actual[key], expected[key], label + "." + str(key))
    elif isinstance(expected, list):
        require(type(actual) is list and len(actual) == len(expected), label + ": metric list differs")
        for index, (left, right) in enumerate(zip(actual, expected)):
            metrics(left, right, label + "." + str(index))
    else:
        exact(actual, expected, label)


def hash_pin(value, label):
    require(type(value) is str and re.fullmatch("[0-9a-f]{64}", value), label + ": lowercase SHA256 required")
    return value


def read_bound(path, pin, label):
    hash_pin(pin, label)
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == pin, label + ": bytes differ")
    return json.loads(data.decode("utf-8-sig"),
        parse_constant=lambda value: (_ for _ in ()).throw(RuntimeError("Nonfinite JSON: " + value)))


def git_identity(source, expected_commit):
    # This duration preparer intentionally has a narrower contract than the
    # historical portable helper: execute only from exact clean queue checkouts.
    command = ["git", "-c", "safe.directory=" + source.as_posix(), "--no-optional-locks", "-C", str(source)]
    root = Path(subprocess.check_output(command + ["rev-parse", "--show-toplevel"], text=True).strip()).resolve()
    require(root == source and (source / ".git").exists(), "Use a real immutable checkout root")
    head = subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip()
    require(head == expected_commit, "Checkout HEAD differs from accepted finite EOS source")
    status = subprocess.check_output(command + ["status", "--porcelain=v1", "--untracked-files=all"], text=True)
    require(not status, "Source tracked/index/untracked state must remain clean")
    return dict(root=str(root), commit=head, tracked_index_untracked_clean=True)


def prerequisite_receipts(args):
    reference = read_bound(args.reference_receipt, args.reference_receipt_sha256, "accepted reference review")
    finite = read_bound(args.finite_eos_receipt, args.finite_eos_receipt_sha256, "accepted finite-three-case review")
    expected = read_bound(args.eos_input_hashes, args.eos_input_hashes_sha256, "independent finite EOS input map")
    require(type(args.accepted_source_commit) is str and re.fullmatch("[0-9a-f]{40}", args.accepted_source_commit),
            "Explicit full accepted source commit required")
    hash_pin(args.accepted_request_sha256, "accepted finite EOS request")
    hash_pin(args.accepted_policy_sha256, "accepted coherent finite EOS policy")
    require(reference["status"] == REFERENCE_REVIEW_STATUS and reference["case_id"] == CASE_ID,
            "Original-reference qualification has not been accepted")
    require(reference["oracle_sha256"] == ORACLE_PIN and reference["producer_sha256"] == PRODUCER_PIN
            and reference["source_commit"] == REFERENCE_PIN, "Reference review identities differ")
    require(reference["changed_attribute_id"] == 73 and reference["independent_metrics_per_state"] == 38,
            "Reference review has the wrong finite scope")
    require(reference["owned_root_and_tree_closed"] is True and reference["remaining_job_processes"] == 0
            and reference["candidate_acceptance"] is False and reference["native_acceptance"] is False,
            "Reference review must retain actual closure and honest scope")
    require(finite["status"] == FINITE_REVIEW_STATUS and finite["case_ids"] == ["module", "drone", CASE_ID]
            and finite["protocol_kinds"] == ["module", "drone", "module"], "Required finite-three-case EOS review is absent")
    require(finite["qualified_duration_oracle_sha256"] == ORACLE_PIN
            and finite["original_producer_sha256"] == PRODUCER_PIN
            and finite["source_commit"] == args.accepted_source_commit
            and finite["request_sha256"] == args.accepted_request_sha256
            and finite["aggregate_policy_sha256"] == args.accepted_policy_sha256,
            "Finite EOS review does not bind the intended source/request/policy/oracle")
    require(type(finite["meaningful_converted_edits"]) is int and finite["meaningful_converted_edits"] > 0
            and finite["owned_root_and_tree_closed"] is True and finite["raw_integer_precision_preserved"] is True
            and finite["all_supplied_raw_inputs_unchanged"] is True,
            "Finite EOS review must establish positive conversion and actual closed unchanged inputs")
    for name in ("full_C10_acceptance", "Android_acceptance", "writer_process_death_claim"):
        require(finite[name] is False, "Finite receipt cannot establish broader acceptance")
    require(type(expected) is dict and bool(expected), "Independent finite EOS input map required")
    for path, pin in expected.items():
        require(type(path) is str and bool(path), "Expected input path required")
        hash_pin(pin, "expected EOS input")
    reviewed_inputs = finite["review_inputs_sha256"]
    require(type(reviewed_inputs) is dict and args.eos_input_hashes_sha256 in reviewed_inputs.values(),
            "Finite reviewer did not bind the supplied independent input map")
    require(ORACLE_PIN in expected.values(), "Accepted EOS input map must include this exact independent oracle")
    require(args.accepted_source_commit not in ("9bf2779dee30ea8717c2634202c3a2f9dbc91fc5",
                                               "3d34baec5f6dc61c662c2ce94d395a95d5bc17f6"),
            "Failed189/190 source cannot supply new duration acceptance")
    return reference, finite, expected


def validate_inputs(args):
    # This must remain the first gate, before receipt/package/source loading,
    # EOS imports or any output creation. CLI hashes cannot override the draft.
    hash_pin(ORACLE_PIN, "UNFILLED independent duration oracle; qualify it before generation")
    require(sys.version_info[:3] == (3, 11, 9), "Use the qualified project Python 3.11.9 environment")
    require(sys.platform == "win32" and struct.calcsize("P") * 8 == 64, "Use the qualified Windows x64 worker")
    require(sys.flags.isolated and sys.dont_write_bytecode, "Launch with -I -B")
    # The fixed queue checkout can supply its bridge and EOS from one tree.
    require(not args.output.exists(), "Output must be new")
    for source in (args.candidate, args.product_source):
        require(not args.output.is_relative_to(source) and not source.is_relative_to(args.output),
                "Output must be outside and must not contain either source tree")
    for source in (args.database, args.oracle, args.reference_receipt, args.finite_eos_receipt,
                   args.eos_input_hashes, Path(__file__).resolve()):
        require(not source.is_relative_to(args.output), "Output must not contain an input")
    for private_input in (args.database, args.oracle, args.reference_receipt, args.finite_eos_receipt,
                          args.eos_input_hashes):
        require(not any(private_input.is_relative_to(source) for source in (args.candidate, args.product_source)),
                "Private data and qualification receipts must remain outside source checkouts")
    require(args.oracle.name == ORACLE_NAME, "Supply the exact private duration-oracle basename")
    require(args.oracle_sha256 == ORACLE_PIN and sha(args.oracle) == ORACLE_PIN,
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
    reference_review, finite_review, eos_inputs = prerequisite_receipts(args)
    roots = {str(source): git_identity(source, args.accepted_source_commit)
             for source in (args.candidate, args.product_source)}
    for source in (args.candidate, args.product_source):
        require(sha(source / "execution-policy.json") == args.accepted_policy_sha256,
                "Source policy bytes differ from accepted coherent EOS policy")
    expected_script = args.candidate / "tools/android_headless/c10_units/prepare_duration_native_seed.py"
    require(Path(__file__).resolve() == expected_script.resolve(),
            "Execute the committed duration preparer from the accepted queue source")
    oracle = read_bound(args.oracle, ORACLE_PIN, "independent duration oracle")
    require(oracle["schema"] == 1 and oracle["case_id"] == CASE_ID
            and oracle["status"] == "QUALIFIED_INDEPENDENT_REFERENCE_FIXTURE"
            and oracle["source_commit"] == REFERENCE_PIN,
            "Unsupported independent oracle provenance")
    require(oracle["database_sha256"] == DATABASE_PIN and
            oracle["database_logical_sha256"] == LOGICAL_PIN, "Oracle dataset pins differ")
    require((oracle["base_item_id"], oracle["mutaplasmid_id"], oracle["resulting_item_id"])
            == (399, 47778, 47781), "Wrong independent mutation pair")
    require(oracle["producer_sha256"] == PRODUCER_PIN and oracle["helper_sha256"] == REFERENCE_HELPER_PIN,
            "Independent fixture producer/helper differ")
    require(oracle["inputs_preserved"] is True and oracle["omitted_raw_scalars_exact"] is True,
            "Independent fixture inputs/raw scalar preservation required")
    require(len(oracle["states"]) == 2 and oracle["states"][0]["name"] == "baseline"
            and oracle["states"][0]["fraction"] == .25
            and oracle["states"][1]["name"] == "duration_only_target"
            and oracle["states"][1]["endpoint"] == "maximum"
            and oracle["states"][1]["changed_attribute_id"] == 73, "Wrong independent fixed states")
    baseline = oracle["states"][0]["attributes"]
    target = oracle["states"][1]["attributes"]
    exact([row["attribute_id"] for row in baseline], [6, 30, 50, 68, 73], "baseline IDs")
    exact([row["attribute_id"] for row in target], [6, 30, 50, 68, 73], "target IDs")
    for left, right in zip(baseline, target):
        if left["attribute_id"] == 73:
            require(left["value"] != right["value"], "Duration must genuinely change")
        else:
            exact(left, right, "independent omitted scalar remains exact")
    observation = oracle["unit_observation"]
    require((observation["attribute_id"], observation["unit_id"], observation["unit_name"], observation["unit_label"])
            == (73, 101, "Milliseconds", "s") and observation["higher_is_better"] is False,
            "Wrong independent duration unit metadata")
    require(observation["display_target"] != observation["raw_maximum"]
            and observation["inverse_within_tolerance"] is True, "A meaningful independent display conversion is required")
    exact(target[-1]["value"], observation["raw_maximum"], "independent duration maximum endpoint")
    for state in oracle["states"]:
        require(len(state["metrics"]) == 38, "All38 independent snapshot metrics required")
    spec = oracle["initial_spec"]
    require(spec["name"] == FIT_NAME and spec["ship"] == "Rifter", "Wrong synthetic fit")
    require(len(spec["modules"]) == 1, "Seed must contain exactly one fitted module")
    module = spec["modules"][0]
    require(module["name"] == "Small Abyssal Shield Booster" and module["state"] == "ACTIVE",
            "Wrong initial module or state")
    require((module["mutation"]["base_item_id"], module["mutation"]["mutaplasmid_id"])
            == (399, 47778), "Wrong initial mutation identity")
    exact(module["mutation"]["attributes"], baseline, "independent initial raw vector")
    for name in ("implants", "boosters", "projections", "commands", "environments", "drones"):
        exact(spec[name], [], "independent empty " + name)
    return oracle, reference_review, finite_review, eos_inputs, roots


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
        require(not path.is_symlink() and any(path.resolve().is_relative_to(root)
                for root in (args.candidate, args.product_source)), "Bound source must remain inside its checkout")
        required[str(path.resolve())] = {"sha256": sha(path), "size_bytes": path.stat().st_size}
    for relative in ("android_bridge/engine.py", "android_bridge/contract.py", "android_bridge/store.py",
                     "android_bridge/fitting.py", "android_bridge/mutation_records.py",
                     "android_bridge/mutation_units.py",
                     "android/app/src/androidTest/java/io/github/sussic/pyfa/MutationDurationEditorUiTest.kt",
                     "tools/android_headless/c10_units/prepare_duration_native_seed.py"):
        require(str((args.candidate / relative).resolve()) in required, "Missing derivative dependency: " + relative)
    for relative in ("tools/android_headless/check.py", "tools/android_reference/reference.py"):
        require(str((args.product_source / relative).resolve()) in required, "Missing headless helper: " + relative)
    inputs = {}
    for path in (args.database, args.oracle, args.reference_receipt, args.finite_eos_receipt, args.eos_input_hashes):
        inputs[str(path)] = {"sha256": sha(path), "size_bytes": path.stat().st_size}
    return {"schema_version": 1, "candidate": str(args.candidate),
            "product_source": str(args.product_source), "required_files": required, "private_inputs": inputs}


def match_accepted_source(args, expected):
    # The accepted input map uses the fixed queue layout. Native preparation may
    # have a new job directory, but every bound source file must have the same
    # accepted relative path/content and both checkout HEADs must match.
    marker = "/jobs/" + args.accepted_request_sha256 + "/source/"
    matched = {}
    for path, pin in expected.items():
        normalized = PureWindowsPath(path).as_posix()
        offset = normalized.casefold().find(marker)
        if offset < 0:
            continue
        relative = normalized[offset + len(marker):]
        require(relative and not PureWindowsPath(relative).is_absolute()
                and ".." not in PureWindowsPath(relative).parts, "Invalid accepted relative source path")
        require(relative not in matched, "Duplicate accepted relative source input")
        matched[relative] = pin
        for source in (args.candidate, args.product_source):
            actual = source / relative
            require(actual.is_file() and actual.resolve().is_relative_to(source) and sha(actual) == pin,
                    "Source differs from finite EOS accepted input: " + relative)
    for relative in ("android_bridge/engine.py", "android_bridge/contract.py", "android_bridge/store.py",
                     "android_bridge/fitting.py", "android_bridge/mutation_records.py", "android_bridge/mutation_units.py",
                     "tools/android_headless/check.py", "tools/android_reference/reference.py"):
        require(relative in matched, "Accepted finite EOS input map misses required source: " + relative)
    for prefix in ("eos/", "utils/"):
        require(any(path.startswith(prefix) for path in matched), "Accepted EOS package binding absent: " + prefix)
    return matched


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
    require(len(nonempty) == 1, "Exactly one real fitted module must remain after vacancy normalization")
    position = nonempty[0][0]
    module = nonempty[0][1]
    require(module["name"] == "Small Abyssal Shield Booster" and module["state"] == "ACTIVE", "Captured module differs")
    exact(module["mutation"], oracle["initial_spec"]["modules"][0]["mutation"], "captured raw mutation")
    for field in ("drones", "projections", "commands", "environments"):
        exact(spec[field], [], "captured empty " + field)
    for field in ("projected_modules", "projected_drones", "projected_fighters", "fighters", "cargo"):
        exact(spec.get(field, []), [], "captured empty " + field)
    require(bridge._fits[key].modules[position].item.ID == 47781, "EOS resulting module ID differs")
    details = bridge.mutation_details(key)
    require(details["version"] == 1 and len(details["items"]) == 1, "Unexpected mutation query shape")
    item = details["items"][0]
    require(item["kind"] == "module" and item["position"] == position, "Unexpected discovered mutation item")
    require(type(item["object_key"]) is str and bool(item["object_key"]), "Discovered stable object key required")
    require((item["base_item_id"], item["mutaplasmid_id"]) == (399, 47778), "Queried mutation identity differs")
    vector = [{"attribute_id": row["attribute_id"], "value": row["value"]} for row in item["attributes"]]
    exact(vector, oracle["states"][0]["attributes"], "queried raw baseline bits")
    exact([row["attribute_id"] for row in vector], [6, 30, 50, 68, 73], "queried complete five rolls")
    values = bridge.engine.snapshot(bridge._fits[key], weapon_index=position)
    require(len(values) == 38, "Preserve all38 independent baseline metrics")
    metrics(values, oracle["states"][0]["metrics"], "independent baseline EOS snapshot")
    shown = bridge.mutation_display_details(key)
    require(len(shown["items"]) == 1, "Expected one private duration display item")
    displayed = shown["items"][0]
    require(displayed["position"] == position and displayed["object_key"] == item["object_key"],
            "Display query must retain discovered raw routing identity")
    duration = next(row for row in displayed["attributes"] if row["attribute_id"] == 73)
    original = oracle["unit_observation"]
    require(duration["display"]["available"] is True, "Duration display conversion must be available")
    for actual, expected in (("value", "display_baseline"), ("minimum", "display_minimum"),
                             ("maximum", "display_maximum"), ("unit_label", "unit_label"),
                             ("higher_is_better", "higher_is_better")):
        exact(duration["display"][actual], original[expected], "original duration display." + actual)
    require(duration["value"] != duration["display"]["value"], "Baseline must exercise genuine seconds conversion")
    return {"fit_id": key, "object_key": item["object_key"], "position": position,
            "raw_vector": vector, "raw_scalar_identity": {str(row["attribute_id"]):
                {"type": type(row["value"]).__name__, "encoding": row["value"].hex()
                 if type(row["value"]) is float else str(row["value"])} for row in vector},
            "independent_baseline_metrics_compared": len(values),
            "history": history, "vacant_module_rows": len(spec["modules"]) - 1,
            "inspection_ids": deepcopy(record["inspection_ids"])}


def prepare(args):
    oracle, reference_review, finite_review, eos_inputs, roots = validate_inputs(args)
    bound = source_manifest(args)
    accepted_source_inputs = match_accepted_source(args, eos_inputs)
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
    write_json(args.output / "source-manifest.json", bound)
    private_oracle = args.output / ORACLE_NAME
    with private_oracle.open("xb") as stream:
        stream.write(args.oracle.read_bytes())
    require(sha(private_oracle) == ORACLE_PIN, "Private original-reference byte copy differs")
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
    exact(match_accepted_source(args, eos_inputs), accepted_source_inputs, "accepted EOS source inputs unchanged")
    exact({str(source): git_identity(source, args.accepted_source_commit)
           for source in (args.candidate, args.product_source)}, roots, "actual accepted source identities unchanged")
    require(sha(args.database) == DATABASE_PIN and sha(args.oracle) == ORACLE_PIN,
            "Frozen data or oracle changed during preparation")
    seed = {"schema_version": 1, "task": "C10.F14.02.NATIVE-DURATION-PREP1", "case_id": CASE_ID,
            "synthetic_inputs_only": True,
            "status": "PREPARED_PENDING_NATIVE_ACCEPTANCE", "native_acceptance": False,
            "native_installation_performed": False, "app_data_written": False,
            "reference_source_commit": REFERENCE_PIN, "database_sha256": DATABASE_PIN,
            "database_logical_sha256": LOGICAL_PIN, "oracle_path": str(args.oracle),
            # Retain the native metadata key, but this is a private file beside
            # seed.json. Never package the raw oracle in source or test assets.
            "oracle_asset": {"name": ORACLE_NAME, "sha256": ORACLE_PIN, "size_bytes": private_oracle.stat().st_size},
            "oracle_delivery": "private no_backup/c10-duration-fixture only; never a test-APK asset",
            "prerequisites": {
                "reference_fixture": {"status": reference_review["status"],
                    "receipt_sha256": args.reference_receipt_sha256, "oracle_sha256": ORACLE_PIN,
                    "source_commit": REFERENCE_PIN},
                "finite_three_case_eos": {"status": finite_review["status"],
                    "receipt_sha256": args.finite_eos_receipt_sha256,
                    "source_commit": args.accepted_source_commit, "request_sha256": args.accepted_request_sha256,
                    "policy_sha256": args.accepted_policy_sha256, "oracle_sha256": ORACLE_PIN}},
            "graph": {"name": store.path.name, "sha256": graph_hash, "schema": 1, "format": 1,
                      "generation": 1, "fit_count": 1, "fit_name": FIT_NAME,
                      "payload_sha256": store.current.digest, "opened_existing_on_host_reopen": True},
            "source_manifest_sha256": sha(args.output / "source-manifest.json"),
            "source_manifest": "source-manifest.json", "candidate": str(args.candidate),
            "source_identities": roots, "accepted_eos_source_inputs": accepted_source_inputs,
            "product_source": str(args.product_source), "database_path": str(args.database),
            "python_executable": sys.executable, "python_executable_sha256": sha(sys.executable),
            "python_version": sys.version,
            "platform": platform.platform(), "dependencies": DEPENDENCIES,
            "loaded_source_modules": loaded, "desktop_import_attempts": barrier.attempts,
            "network_attempts": network, "baseline_fraction": 0.25,
            "target_state": "duration_only_target", "target_attribute_id": 73, "target_endpoint": "maximum",
            "vacancies_normalized_before_initial_capture": True,
            "synthetic_ui_shape": "fitting._fill before BridgeSession adoption; exactly one real module at discovered position",
            "seed_observation": observation,
            "limits": ["Input preparation and same-process host reopen only; no native/UI proof",
                       "No APK build, installation, app-data write or writer-death test",
                       "Independent expected values remain exclusively in the copied retained oracle"]}
    require({path.name for path in args.output.iterdir()} == {
        "graph.sqlite3", "source-manifest.json", ORACLE_NAME}, "Unexpected private seed output")
    # Publish the final usable-bundle marker only after all checks. Partial
    # files remain private on failure, with the real traceback in the guard log.
    write_json(args.output / "seed.json", seed)
    print(json.dumps({"status": seed["status"], "output": str(args.output),
                      "graph_sha256": graph_hash, "native_acceptance": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "product-source", "database", "oracle", "reference-receipt",
                 "finite-eos-receipt", "eos-input-hashes", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("oracle-sha256", "reference-receipt-sha256", "finite-eos-receipt-sha256",
                 "eos-input-hashes-sha256", "accepted-source-commit", "accepted-request-sha256",
                 "accepted-policy-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    for name in ("candidate", "product_source", "database", "oracle", "reference_receipt",
                 "finite_eos_receipt", "eos_input_hashes"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.output = args.output.resolve()
    # Preserve partial private outputs and the canonical guard's actual traceback
    # on failure. Only a successful run may be handed off with seed.json.
    prepare(args)


if __name__ == "__main__":
    main()
