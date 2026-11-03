"""NONIDENTITY1 addition with independently qualified private duration oracle.

Uses retained independent module/drone raw oracles and original Unit methods.
A selected family is finite supporting proof, not full C10 or Android acceptance.
No old r12 descriptor, resource limit, installed environment or receipt is replayed.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from copy import deepcopy
import ctypes
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback
from uuid import uuid4

PIN = "8b04f3b271e614b3e103853b44a7851a63d79d0e"
DB_PIN = "e0dc4b3d281bd949f0a8089d587053ad66c0fcef90163cc6988e670d15d01065"
LOGICAL_PIN = "5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607"
ORACLE_PINS = {
    "module": "0e9cddf9eb8df1c8c31620167dc4c86596d782a42d9e7859b7edce708d6205e7",
    "drone": "e29a341eac166131c5b4bee8a78be93c3880debf7eb4024417ae30bbe5dbe342",
}
NEW_CASE = "module399-duration73"
# Fill only after the separately admitted original-reference run and raw review.
# A command-line hash cannot override this deliberately failclosed draft pin.
NEW_ORACLE_SHA256 = "14baf8fe09bca5783d7d6955ba3a7b57c2c884fa2d8b3987eaaf6b3b3d9d1136"
ORACLE_PINS[NEW_CASE] = NEW_ORACLE_SHA256
NEW_PRODUCER_SHA256 = "e202db67cbb09bf90e69e9b958c175c7ccf96406877a5275199191405965c737"
REFERENCE_HELPER_SHA256 = "292b550ddb4552d74c87116ba82d12d828584f0a175913027cc17d2297f4ec20"
CASE_KINDS = {"module": "module", "drone": "drone", NEW_CASE: "module"}
MISSING_DRONE_ORIGINAL = (r"C:\Users\HallT\Documents\Codex\2026-10-21\task-9\c04-host-run-01"
                          r"\results\reference-drone_details\actual.json")
DEPENDENCIES = {"logbook": "1.7.0.post0", "sqlalchemy": "1.4.50", "greenlet": "3.0.3"}
FORBIDDEN = ("wxPython", "numpy", "cryptography", "pyyaml", "pillow")
NONNUMERIC_UNITS = frozenset(("Sizeclass", "Boolean", "typeID", "groupID", "attributeID"))
UNIT_REL_TOL, UNIT_ABS_TOL = 1e-12, 1e-12
METRIC_REL_TOL, METRIC_ABS_TOL = 1e-10, 1e-9


_WINDOWS_IDENTITY = None


def windows_identity():
    global _WINDOWS_IDENTITY
    if _WINDOWS_IDENTITY is None:
        path = Path(__file__).with_name("windows_venv_identity.py")
        spec = importlib.util.spec_from_file_location("_units_windows_identity", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _WINDOWS_IDENTITY = module
    return _WINDOWS_IDENTITY


class WitnessQualificationRequired(RuntimeError):
    pass


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value, *, fresh=True):
    with Path(path).open("x" if fresh else "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def exact(actual, expected, label):
    if type(actual) is not type(expected):
        raise AssertionError((label, "raw scalar/container type differs", type(actual), type(expected)))
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), label
        for key in expected:
            exact(actual[key], expected[key], label + "." + str(key))
    elif isinstance(expected, list):
        assert len(actual) == len(expected), label
        for index, (value, wanted) in enumerate(zip(actual, expected)):
            exact(value, wanted, label + "." + str(index))
    elif type(expected) is float:
        assert math.isfinite(actual) and actual.hex() == expected.hex(), (label, actual, expected)
    else:
        assert actual == expected, (label, actual, expected)


def metrics(actual, expected, label):
    if isinstance(expected, dict):
        assert type(actual) is dict and actual.keys() == expected.keys(), label
        for key in expected:
            metrics(actual[key], expected[key], label + "." + str(key))
    elif isinstance(expected, list):
        assert type(actual) is list and len(actual) == len(expected), label
        for index, (value, wanted) in enumerate(zip(actual, expected)):
            metrics(value, wanted, label + "." + str(index))
    elif type(expected) is float:
        assert type(actual) is float and math.isfinite(actual) and math.isclose(
            actual, expected, rel_tol=METRIC_REL_TOL, abs_tol=METRIC_ABS_TOL), (label, actual, expected)
    else:
        exact(actual, expected, label)


def process_identity():
    return windows_identity().current_identity()


def family_definition(oracle, case_id):
    assert oracle["source_commit"] == PIN and oracle["database_sha256"] == DB_PIN
    if case_id == "module":
        assert (oracle["base_item_id"], oracle["mutaplasmid_id"], oracle["resulting_item_id"]) == (438, 47746, 47749)
        assert [state["fraction"] for state in oracle["states"]] == [0.25, 0.75]
        return {"seed": deepcopy(oracle["initial_spec"]),
                "vectors": [deepcopy(state["attributes"]) for state in oracle["states"]],
                "metrics": [state["metrics"] for state in oracle["states"]], "position": None,
                "resulting_item_id": 47749}
    if case_id == NEW_CASE:
        assert oracle["schema"] == 1 and oracle["case_id"] == NEW_CASE
        assert oracle["status"] == "QUALIFIED_INDEPENDENT_REFERENCE_FIXTURE"
        assert oracle["database_logical_sha256"] == LOGICAL_PIN
        assert oracle["producer_sha256"] == NEW_PRODUCER_SHA256
        assert oracle["helper_sha256"] == REFERENCE_HELPER_SHA256
        assert (oracle["base_item_id"], oracle["mutaplasmid_id"], oracle["resulting_item_id"]) == (399, 47778, 47781)
        assert oracle["runtime"]["version"] == [3, 11, 9] and oracle["runtime"]["bits"] == 64
        assert oracle["adapter_imported"] is False and oracle["gui_or_service_imported"] is False
        assert oracle["wx_library_imported"] is True
        assert oracle["forbidden_import_attempts"] == oracle["network_attempts"] == []
        assert oracle["inputs_preserved"] is True and oracle["omitted_raw_scalars_exact"] is True
        states = oracle["states"]
        assert len(states) == 2 and [state["name"] for state in states] == ["baseline", "duration_only_target"]
        assert states[0]["fraction"] == 0.25
        assert states[1]["endpoint"] == "maximum" and states[1]["changed_attribute_id"] == 73
        for state in states:
            assert [row["attribute_id"] for row in state["attributes"]] == [6, 30, 50, 68, 73]
            assert len(state["metrics"]) == 38
            identities = []
            for row in state["attributes"]:
                assert set(row) == {"attribute_id", "value"}
                value = row["value"]
                assert type(value) in (int, float) and math.isfinite(value)
                identities.append(dict(attribute_id=row["attribute_id"], type=type(value).__name__,
                                       encoding=value.hex() if type(value) is float else str(value)))
            exact(state["raw_identity"], identities, "new independent raw scalar identities")
        baseline, target = [state["attributes"] for state in states]
        for left, right in zip(baseline, target):
            if left["attribute_id"] == 73:
                assert left["value"] != right["value"], "new duration target must change"
            else:
                exact(right, left, "new oracle retains every omitted raw scalar")
        observation = oracle["unit_observation"]
        assert (observation["attribute_id"], observation["unit_id"], observation["unit_name"]) == (73, 101, "Milliseconds")
        assert observation["unit_label"] == "s" and observation["higher_is_better"] is False
        assert observation["endpoint"] == "maximum" and observation["inverse_within_tolerance"] is True
        exact(observation["roundtrip_tolerance"], dict(relative=UNIT_REL_TOL, absolute=UNIT_ABS_TOL),
              "new independent unchanged unit tolerance")
        exact(target[-1]["value"], observation["raw_maximum"], "new independent raw endpoint")
        exact(baseline[-1]["value"], observation["raw_baseline"], "new independent raw baseline")
        assert all(type(observation[key]) in (int, float) and math.isfinite(observation[key])
                   for key in ("display_target", "inverse", "raw_maximum"))
        assert observation["display_target"] != target[-1]["value"]
        assert math.isclose(observation["inverse"], target[-1]["value"], rel_tol=UNIT_REL_TOL, abs_tol=UNIT_ABS_TOL)
        assert states[0]["metrics"]["capacitor_used"] != states[1]["metrics"]["capacitor_used"]
        exact(oracle["initial_spec"]["modules"][0]["mutation"]["attributes"], baseline,
              "new independent seed retains complete baseline")
        return {"seed": deepcopy(oracle["initial_spec"]), "vectors": [deepcopy(baseline), deepcopy(target)],
                "metrics": [state["metrics"] for state in states], "position": None,
                "resulting_item_id": 47781, "unit_observation": deepcopy(observation)}
    assert case_id == "drone"
    case = oracle["cases"][-1]
    assert case["spec"]["name"] == "C04 details skills 5 thermal 100"
    assert len(case["spec"]["drones"]) == 15 and not case["spec"]["modules"]
    left, right = case["spec"]["drones"][13:15]
    assert (left["mutation"]["base_item_id"], left["mutation"]["mutaplasmid_id"]) == (2454, 60461)
    assert (left["amount"], left["active"]) == (right["amount"], right["active"])
    assert case["stacks"][13]["metrics"]["dps_total"] == 77.9625
    assert case["stacks"][14]["metrics"]["dps_total"] == 85.3875
    return {"seed": deepcopy(case["spec"]),
            "vectors": [deepcopy(row["mutation"]["attributes"]) for row in (left, right)],
            "metrics": [case["stacks"][index]["metrics"] for index in (13, 14)], "position": 13}


def oracle_arguments(args, case_id):
    name = "duration" if case_id == NEW_CASE else case_id
    return getattr(args, name + "_oracle"), getattr(args, name + "_oracle_sha256")


def validate_inputs(args, case_ids):
    if len(NEW_ORACLE_SHA256) != 64 or any(char not in "0123456789abcdef" for char in NEW_ORACLE_SHA256):
        raise FileNotFoundError("Draft new oracle SHA is UNFILLED; qualify the independent fixture before any EOS run")
    assert sys.version_info[:2] == (3, 11), "Use the real pinned Python 3.11 headless environment"
    for name, version in DEPENDENCIES.items():
        assert importlib.metadata.version(name) == version, name
    for name in FORBIDDEN:
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            raise AssertionError("Forbidden headless package installed: " + name)
    assert sha(args.database) == DB_PIN
    oracles = {}
    for case_id in case_ids:
        path, pin = oracle_arguments(args, case_id)
        if path is None or pin is None:
            raise FileNotFoundError("Supply the exact independently qualified " + case_id + " oracle and its SHA256")
        assert pin.lower() == ORACLE_PINS[case_id], "A different oracle needs separate qualification"
        assert sha(path) == pin.lower(), str(path)
        oracles[case_id] = read(path)
        family_definition(oracles[case_id], case_id)
    # A full portable candidate can supply its bridge and EOS from one tree.
    assert args.reference_source not in {args.candidate, args.product_source}, "Keep the pinned independent reference separate"
    spec = importlib.util.spec_from_file_location(
        "_independent_units_reference", Path(__file__).with_name("reference_units.py"))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    unit_class, provenance = helper.load_unit(args.reference_source)
    dirty = subprocess.check_output(
        ["git", "-c", "safe.directory=" + args.reference_source.resolve().as_posix(),
         "--no-optional-locks", "-C", str(args.reference_source),
         "status", "--porcelain=v1", "--untracked-files=no"], text=True)
    assert not dirty, "The independent reference must remain clean at its pinned commit"
    for oracle in oracles.values():
        expected = oracle.get("source_files", {}).get("eos/gamedata.py")
        if expected is not None:
            assert provenance["source_sha256"] == expected, "Independent Unit source differs from the oracle"
    paths = {Path(__file__).resolve(), Path(__file__).with_name("reference_units.py").resolve(),
             Path(__file__).with_name("windows_venv_identity.py").resolve(),
             args.reference_source / "eos/gamedata.py",
             args.product_source / "tools/android_headless/check.py",
             args.product_source / "tools/android_reference/reference.py"}
    for package in ("tools", "tools/android_headless", "tools/android_reference"):
        initializer = args.product_source / package / "__init__.py"
        if initializer.is_file():
            paths.add(initializer)
    for base in (args.candidate / "android_bridge", args.product_source / "eos", args.product_source / "utils"):
        paths.update(base.rglob("*.py"))
    paths.update(oracle_arguments(args, case_id)[0] for case_id in case_ids)
    pins = {str(path): sha(path) for path in sorted(paths, key=str)}
    return oracles, unit_class, provenance, pins


def open_runtime(args):
    sys.path.insert(0, str(args.product_source))
    from tools.android_headless.check import NoDesktop
    barrier, network = NoDesktop(), []
    sys.meta_path.insert(0, barrier)

    def block(event, arguments):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            network.append(event)
            raise RuntimeError("Network is forbidden during this offline headless gate: " + event)
    sys.addaudithook(block)
    sys.path.insert(0, str(args.candidate))
    from android_bridge.engine import HeadlessEngine
    from android_bridge.contract import BridgeSession
    from android_bridge.store import GraphStore, decode_graph, encode_graph
    assert "eos.db" not in sys.modules, "Each OS process begins with a fresh EOS session"
    return (HeadlessEngine(args.database), BridgeSession, GraphStore, decode_graph, encode_graph,
            barrier, network)


def verify_origins(args, barrier, network):
    assert not barrier.attempts and not network
    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if name.split(".")[0] == "android_bridge":
            assert path.is_relative_to(args.candidate), (name, str(path))
        if name.split(".")[0] in ("eos", "utils"):
            assert path.is_relative_to(args.product_source), (name, str(path))
    assert sha(args.database) == DB_PIN


def current_row(bridge, key, family, position=None, *, display=False):
    query = bridge.mutation_display_details if display else bridge.mutation_details
    value = query(key)
    assert value["version"] == 1 and value["fit_id"] == key
    rows = [row for row in value["items"] if row["kind"] == family
            and (position is None or row["position"] == position)]
    assert len(rows) == 1, (family, position, len(rows))
    return rows[0]


def vector(row):
    return [dict(attribute_id=item["attribute_id"], value=item["value"]) for item in row["attributes"]]


def observe(context, expected_vector, label, oracle_state=None):
    bridge, engine, key = context["bridge"], context["engine"], context["key"]
    row = current_row(bridge, key, context["family"], context["position"])
    assert row["object_key"] == context["object_key"]
    exact(vector(row), expected_vector, label + ".query_raw")
    collection = "modules" if context["family"] == "module" else "drones"
    stored = bridge._records[key]["spec"][collection][context["position"]]["mutation"]["attributes"]
    exact(stored, expected_vector, label + ".stored_raw")
    record = {"label": label, "revision": bridge._revisions[key], "raw_vector": deepcopy(stored),
              "object_key": row["object_key"], "oracle_metrics_compared": 0}
    if oracle_state is not None:
        if context["family"] == "module":
            from eos.const import FittingModuleState
            module = bridge._fits[key].modules[context["position"]]
            assert module.itemID == context["definition"]["resulting_item_id"] and module.state == FittingModuleState.ACTIVE
            values = engine.snapshot(bridge._fits[key], weapon_index=context["position"])
        else:
            details = bridge.drone_details(key)
            stack = details["stacks"][context["position"]]
            assert stack["object_key"] == row["object_key"]
            values = {item["key"]: item["value"] for item in stack["metrics"]}
        metrics(values, context["definition"]["metrics"][oracle_state], label + ".EOS")
        record["oracle_metrics_compared"] = len(values)
    context["phases"].append(record)
    write(context["directory"] / "PROGRESS.json", context["phases"], fresh=False)
    return row


def dispatch(context, operation, arguments, *, expected_code=None, revision=None):
    bridge, key = context["bridge"], context["key"]
    request = dict(version=1, request_id="units-" + uuid4().hex, session_id=bridge.session_id,
                   operation=operation, arguments=arguments,
                   expected_revisions={key: bridge._revisions[key] if revision is None else revision})
    reply = json.loads(bridge.dispatch(json.dumps(request, allow_nan=False)))
    assert reply["status"] == ("error" if expected_code else "ok"), reply
    if expected_code:
        assert reply["error"]["code"] == expected_code, reply
    return reply


def state_identity(context):
    bridge, key = context["bridge"], context["key"]
    return {"records": deepcopy(bridge._records), "revisions": dict(bridge._revisions),
            "history": deepcopy(bridge.history_details(key)), "disk_sha256": sha(context["store"])}


def independent_edits(context, unit_class, database):
    old = current_row(context["bridge"], context["key"], context["family"], context["position"])
    shown = current_row(context["bridge"], context["key"], context["family"], context["position"], display=True)
    stripped = deepcopy(shown)
    for attribute in stripped["attributes"]:
        attribute.pop("display")
    exact(stripped, old, "new display query retains the full legacy raw row")
    target = {item["attribute_id"]: item["value"] for item in context["definition"]["vectors"][1]}
    edits, observations = [], []
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        for raw, display_row in zip(old["attributes"], shown["attributes"]):
            attribute_id = raw["attribute_id"]
            if type(raw["value"]) is type(target[attribute_id]) and (
                    raw["value"].hex() == target[attribute_id].hex() if type(raw["value"]) is float
                    else raw["value"] == target[attribute_id]):
                continue
            available = display_row["display"]["available"]
            assert type(available) is bool
            db_row = connection.execute(
                "SELECT a.unitID,u.unitName FROM dgmattribs a "
                "LEFT JOIN dgmunits u ON u.unitID=a.unitID WHERE a.attributeID=?", (attribute_id,)).fetchone()
            assert db_row is not None, attribute_id
            unit_id, unit_name = db_row
            raw_target = target[attribute_id]
            record = {"attribute_id": attribute_id, "unit_id": unit_id, "unit_name": unit_name,
                      "target_raw": raw_target, "candidate_display_available": available}
            if not available:
                edit = dict(attribute_id=attribute_id, value=raw_target, representation="raw")
            else:
                assert unit_id is None or unit_name is not None, "Unknown declared unit cannot be treated as unitless"
                assert unit_name not in NONNUMERIC_UNITS
                unit = None if unit_id is None else unit_class()
                if unit is not None:
                    unit.name, unit.displayName = unit_name, None
                converted = raw_target if unit is None else unit.SimplifyValue(raw_target)
                roundtrip = converted if unit is None else unit.ComplicateValue(converted)
                assert type(converted) in (int, float) and math.isfinite(converted)
                assert type(roundtrip) in (int, float) and math.isfinite(roundtrip)
                is_endpoint = raw_target in (raw["minimum"], raw["maximum"])
                try:
                    exact(roundtrip, raw_target, "independent raw round trip")
                    roundtrip_exact = True
                except AssertionError:
                    roundtrip_exact = False
                within_tolerance = math.isclose(roundtrip, raw_target,
                                                rel_tol=UNIT_REL_TOL, abs_tol=UNIT_ABS_TOL)
                record.update(display_input=converted, roundtrip=roundtrip,
                              roundtrip_exact=roundtrip_exact, raw_endpoint=is_endpoint,
                              roundtrip_within_documented_unit_tolerance=within_tolerance)
                observations.append(record)
                if not roundtrip_exact and not is_endpoint:
                    write(context["directory"] / "WITNESS-QUALIFICATION-REQUIRED.json",
                          {"reason": "Independent interior display conversion does not reproduce the frozen raw scalar exactly",
                           "observation": record, "raw_expectation_unchanged": True})
                    raise WitnessQualificationRequired(
                        "Qualify a display witness for attribute " + str(attribute_id) +
                        "; do not replace the frozen raw oracle with candidate output")
                edit = dict(attribute_id=attribute_id, value=converted, representation="display")
            if record not in observations:
                observations.append(record)
            edits.append(edit)
    assert edits, "The frozen cases must exercise an actual edit"
    context["unit_observations"] = observations
    context["meaningful_converted"] = sum(
        edit["representation"] == "display" and edit["value"] != target[edit["attribute_id"]]
        for edit in edits)
    if context["case_id"] == NEW_CASE:
        expected = context["definition"]["unit_observation"]
        assert len(edits) == len(observations) == 1 and edits[0]["attribute_id"] == 73
        assert edits[0]["representation"] == "display" and context["meaningful_converted"] == 1
        assert (observations[0]["unit_id"], observations[0]["unit_name"]) == (101, "Milliseconds")
        assert observations[0]["raw_endpoint"] is True
        exact(edits[0]["value"], expected["display_target"], "new independent converted endpoint input")
        raw_duration = next(row for row in old["attributes"] if row["attribute_id"] == 73)
        shown_duration = next(row["display"] for row in shown["attributes"] if row["attribute_id"] == 73)
        exact(raw_duration["minimum"], expected["raw_minimum"], "new independent raw minimum")
        exact(raw_duration["maximum"], expected["raw_maximum"], "new independent raw maximum")
        for actual_key, expected_key in (("value", "display_baseline"), ("minimum", "display_minimum"),
                                         ("maximum", "display_maximum"), ("unit_label", "unit_label"),
                                         ("higher_is_better", "higher_is_better")):
            exact(shown_duration[actual_key], expected[expected_key], "new independent display metadata." + actual_key)
    return edits


def child_arguments(args, family, case_id, output, state, state_hash):
    command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
               "--candidate", str(args.candidate), "--product-source", str(args.product_source),
               "--reference-source", str(args.reference_source), "--database", str(args.database),
               "--family", family, "--reader-case", case_id, "--output", str(output),
               "--reader-state", str(state), "--reader-state-sha256", state_hash]
    for name in ("module", "drone", "duration"):
        path, pin = getattr(args, name + "_oracle"), getattr(args, name + "_oracle_sha256")
        if path is not None and pin is not None:
            command.extend(["--" + name + "-oracle", str(path), "--" + name + "-oracle-sha256", pin])
    return command


def selected_family(args, runtime, oracle, unit_class, case_id, writer_identity):
    engine, BridgeSession, GraphStore, decode_graph, encode_graph, _, _ = runtime
    family = CASE_KINDS[case_id]
    definition = family_definition(oracle, case_id)
    if "eos_settings" in oracle:
        exact(engine.settings, oracle["eos_settings"], family + ".EOS settings")
    directory = args.output / case_id
    directory.mkdir()
    seed = deepcopy(definition["seed"])
    fit = engine.create_fit(seed, restore=True)
    # The existing raw editor fills vacancies on its first edit. Capture that
    # normal EOS shape now so sparse-edit checks isolate the selected raw roll.
    from android_bridge.fitting import _fill
    _fill(fit)
    bridge = BridgeSession(engine, fit, seed)
    key = bridge.sample_id
    initial_row = current_row(bridge, key, family, definition["position"])
    position = initial_row["position"]
    store = directory / "fits.sqlite"
    bridge._store, bridge._dataset_identity = GraphStore(store), LOGICAL_PIN
    attempt = bridge._store.prepare(bridge._graph(bridge._records, bridge._revisions))
    assert bridge._write_and_confirm(attempt) == "new"
    bridge._store.accept(attempt)
    context = dict(bridge=bridge, engine=engine, key=key, family=family, case_id=case_id,
                   definition=definition, position=position, object_key=initial_row["object_key"],
                   directory=directory, store=store, phases=[])
    baseline, target = definition["vectors"]
    observe(context, baseline, "frozen original baseline", 0)
    edits = independent_edits(context, unit_class, args.database)
    initial_records = deepcopy(bridge._records)
    hybrid = deepcopy(baseline)
    hybrid_by_id = {item["attribute_id"]: item for item in hybrid}
    hybrid_by_id[edits[0]["attribute_id"]]["value"] = next(
        item["value"] for item in target if item["attribute_id"] == edits[0]["attribute_id"])
    base_args = dict(fit_id=key, kind=family, position=position, object_key=context["object_key"])
    dispatch(context, "set_mutation_display_attributes", dict(base_args, edits=edits[:1]))
    observe(context, hybrid, "one sparse edit; omitted raw scalars remain exact")
    expected_records = deepcopy(initial_records)
    collection = "modules" if family == "module" else "drones"
    expected_records[key]["spec"][collection][position]["mutation"]["attributes"] = deepcopy(hybrid)
    exact(bridge._records, expected_records, "only the selected sparse raw attribute changed")
    step_count = 1
    if edits[1:]:
        dispatch(context, "set_mutation_display_attributes", dict(base_args, edits=edits[1:]))
        step_count = 2
    observe(context, target, "frozen original full target", 1)

    unchanged = state_identity(context)
    raw_row = current_row(bridge, key, family, position)
    first, second = raw_row["attributes"][:2]
    original = {item["attribute_id"]: item["value"] for item in baseline}
    valid_earlier_value = original[first["attribute_id"]]
    if case_id == NEW_CASE:
        # Only73 changed, so resetting6 to baseline would be a no-op. Keep the
        # ordered6/30 request and give6 a different legal endpoint before30 fails.
        valid_earlier_value = first["minimum"] if first["minimum"] != first["value"] else first["maximum"]
        assert first["minimum"] <= valid_earlier_value <= first["maximum"]
        assert valid_earlier_value != first["value"]
    invalid = [dict(attribute_id=first["attribute_id"], value=valid_earlier_value, representation="raw"),
               dict(attribute_id=second["attribute_id"],
                    value=second["maximum"] + max(1.0, abs(second["maximum"])), representation="raw")]
    dispatch(context, "set_mutation_display_attributes", dict(base_args, edits=invalid), expected_code="INVALID_EDIT")
    exact(state_identity(context), unchanged, "invalid later edit is fully atomic")
    dispatch(context, "set_mutation_display_attributes", dict(base_args, edits=edits[:1]),
             expected_code="REVISION_CONFLICT", revision=bridge._revisions[key] - 1)
    exact(state_identity(context), unchanged, "stale expected revision is fully atomic")

    for index in range(step_count):
        dispatch(context, "undo", {"fit_id": key})
        is_baseline = index == step_count - 1
        observe(context, baseline if is_baseline else hybrid,
                "undo " + str(index + 1), 0 if is_baseline else None)
    for index in range(step_count):
        dispatch(context, "redo", {"fit_id": key})
        is_target = index == step_count - 1
        observe(context, target if is_target else hybrid,
                "redo " + str(index + 1), 1 if is_target else None)

    before = state_identity(context)
    bridge._reset_storage()
    assert not engine._fits
    bridge = BridgeSession.open(engine, store, LOGICAL_PIN, None)
    context["bridge"] = bridge
    exact(bridge._records, before["records"], "same-process reopen records")
    exact(bridge._revisions, before["revisions"], "same-process reopen revisions")
    assert sha(store) == before["disk_sha256"]
    observe(context, target, "same-process durable reconstruction", 1)
    payload = encode_graph(bridge._graph(bridge._records, bridge._revisions))
    assert payload == bridge._store.current.payload
    bridge._reset_storage()
    assert not engine._fits
    copy = directory / "reader-copy.sqlite"
    shutil.copyfile(store, copy)
    assert sha(copy) == sha(store)
    state_path = directory / "READER-INPUT.json"
    state = dict(family=family, case_id=case_id, writer_identity=writer_identity, nonce=uuid4().hex,
                 reader_launch_mode="cpython311-direct-base",
                 store=str(copy), store_sha256=sha(copy), graph_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                 fit_id=key, position=position, object_key=context["object_key"],
                 revision=before["revisions"][key], original_store=str(store))
    write(state_path, state)
    command = child_arguments(args, family, case_id, directory / "reader", state_path, sha(state_path))
    command, environment = windows_identity().direct_venv_command(command)
    with (directory / "reader.stdout.log").open("xb") as stdout, \
            (directory / "reader.stderr.log").open("xb") as stderr:
        child = subprocess.Popen(command, cwd=args.product_source, stdout=stdout, stderr=stderr,
                                 creationflags=subprocess.CREATE_NO_WINDOW, env=environment)
        child_creation = windows_identity().creation_time(int(child._handle))
        exit_code = child.wait()  # Enclosing canonical Job owns the total deadline/tree.
    assert exit_code == 0, "Fresh OS reader failed; retain its raw logs and result"
    reader = read(directory / "reader/RESULT.json")
    assert reader["identity"]["pid"] == child.pid != writer_identity["pid"]
    assert reader["identity"]["creation_filetime"] == child_creation
    assert reader["status"] == "PASS_READER_SELECTED_FAMILY"
    assert reader["selected_case_ids"] == [case_id] and reader["case_id"] == case_id
    assert sha(store) == state["store_sha256"] == sha(copy)
    return dict(family=family, case_id=case_id, phases=context["phases"], sparse_steps=step_count,
                spawned_reader_pid=child.pid, spawned_reader_creation_filetime=child_creation,
                unit_observations=context["unit_observations"],
                meaningful_converted_edits=context["meaningful_converted"],
                invalid_later_edit_atomic=True, stale_revision_atomic=True,
                same_process_durable_reopen=True, distinct_OS_reader=reader,
                writer_process_death_claim=False, no_writer_job_closure_claim=True)


def reader_gate(args, runtime, oracle, state):
    engine, BridgeSession, GraphStore, decode_graph, encode_graph, _, _ = runtime
    identity = process_identity()
    writer = state["writer_identity"]
    assert identity["pid"] != writer["pid"] and identity["parent_pid"] == writer["pid"]
    assert identity["creation_filetime"] > writer["creation_filetime"]
    assert state["reader_launch_mode"] == "cpython311-direct-base"
    assert identity["runtime"] == writer["runtime"], "Reader must preserve the qualified venv"
    with windows_identity().Process(writer["pid"]) as live_writer:
        writer_before = live_writer.snapshot()
        windows_identity().same_process(writer_before, writer)
        assert state["family"] == args.family and sha(state["store"]) == state["store_sha256"]
        assert state["case_id"] == args.reader_case and CASE_KINDS[args.reader_case] == args.family
        saved = GraphStore(state["store"]).current
        assert saved is not None and hashlib.sha256(saved.payload.encode()).hexdigest() == state["graph_sha256"]
        graph = decode_graph(saved.payload)
        assert not engine._fits
        assert graph["sample_id"] == state["fit_id"]
        exact(engine.settings, graph["eos_settings"], "reader EOS settings")
        bridge = BridgeSession.open(engine, state["store"], LOGICAL_PIN, None)
        assert bridge.persistence_info["opened_existing"] and engine._fits
        assert encode_graph(bridge._graph(bridge._records, bridge._revisions)) == saved.payload
        assert bridge.sample_id == state["fit_id"] and bridge._revisions[state["fit_id"]] == state["revision"]
        definition = family_definition(oracle, args.reader_case)
        context = dict(bridge=bridge, engine=engine, key=state["fit_id"], family=args.family, case_id=args.reader_case,
                       definition=definition, position=state["position"], object_key=state["object_key"],
                       directory=args.output, store=Path(state["store"]), phases=[])
        observe(context, definition["vectors"][1], "distinct OS reader reconstructs the frozen target", 1)
        assert sha(state["store"]) == state["store_sha256"]
        bridge._reset_storage()
        assert not engine._fits
        writer_after = live_writer.snapshot()
        windows_identity().same_process(writer_after, writer)
        return dict(identity=identity, case_id=args.reader_case, phases=context["phases"], canonical_graph_exact=True,
                    unchanged_store_sha256=state["store_sha256"], writer_alive_parent=True,
                    writer_process_death_claim=False, nonce=state["nonce"],
                    writer_handle_observations=dict(before=writer_before, after=writer_after))


def main(args):
    began = time.monotonic()
    for name in ("candidate", "product_source", "reference_source", "database", "output"):
        setattr(args, name, getattr(args, name).resolve())
    for name in ("module_oracle", "drone_oracle", "duration_oracle", "reader_state"):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).resolve())
    case_ids = ("module", "drone", NEW_CASE) if args.reader_state is None else (args.reader_case,)
    for source in (args.candidate, args.product_source, args.reference_source):
        assert not args.output.is_relative_to(source), "Keep evidence outside all source checkouts"
    args.output.mkdir(parents=True, exist_ok=False)
    result = dict(scope="Deferred-authored finite UNITS1 real EOS integration gate",
                  status="FAILED", selected_family=args.family, started_pid=os.getpid(),
                  selected_case_ids=list(case_ids), required_new_case=NEW_CASE,
                  dependencies=DEPENDENCIES, database_sha256=DB_PIN,
                  unit_roundtrip_tolerance={"relative": UNIT_REL_TOL, "absolute": UNIT_ABS_TOL},
                  oracle_metric_tolerance={"relative": METRIC_REL_TOL, "absolute": METRIC_ABS_TOL},
                  full_C10_acceptance=False, Android_acceptance=False,
                  writer_process_death_claim=False, cases=[])
    pins = None
    oracles = {}
    try:
        if args.reader_state is None:
            assert args.family == "both" and args.reader_case is None, "Successor writer requires exactly all three fixed cases"
        else:
            assert args.reader_case in CASE_KINDS and CASE_KINDS[args.reader_case] == args.family
        oracles, unit_class, reference, pins = validate_inputs(args, case_ids)
        result.update(input_sha256=pins, independent_Unit_source=reference,
                      reader_mode=args.reader_state is not None)
        runtime = open_runtime(args)
        result["identity"] = process_identity()
        if args.reader_state is None:
            result["identity"]["launch_parent"] = windows_identity().launcher_parent(result["identity"])
        if args.reader_state is not None:
            assert len(case_ids) == 1 and args.reader_state_sha256 is not None
            assert sha(args.reader_state) == args.reader_state_sha256
            result.update(reader_gate(args, runtime, oracles[args.reader_case], read(args.reader_state)))
            result["status"] = "PASS_READER_SELECTED_FAMILY"
        else:
            for case_id in case_ids:
                result["cases"].append(selected_family(args, runtime, oracles[case_id],
                                                        unit_class, case_id, result["identity"]))
            assert [case["case_id"] for case in result["cases"]] == ["module", "drone", NEW_CASE]
            assert [case["family"] for case in result["cases"]] == ["module", "drone", "module"]
            meaningful = sum(case["meaningful_converted_edits"] for case in result["cases"])
            assert meaningful > 0, "No meaningful nonidentity converted edit was exercised"
            new_meaningful = result["cases"][-1]["meaningful_converted_edits"]
            assert new_meaningful == 1, "New duration case must independently exercise its sole nonidentity display edit"
            result.update(status="PASS_SELECTED_FINITE_FAMILIES", meaningful_converted_edits=meaningful,
                          new_case_meaningful_converted_edits=new_meaningful,
                          both_selected_finite_cases_executed=args.family == "both",
                          all_three_fixed_cases_executed=True,
                          unselected_family_pending=[])
        verify_origins(args, runtime[-2], runtime[-1])
    except FileNotFoundError as error:
        result.update(status="BLOCKED_INPUT", error=str(error), traceback=traceback.format_exc())
    except WitnessQualificationRequired as error:
        result.update(status="BLOCKED_WITNESS_QUALIFICATION", error=str(error), traceback=traceback.format_exc())
    except BaseException as error:
        result.update(status="FAILED", error=type(error).__name__ + ": " + str(error),
                      traceback=traceback.format_exc())
    finally:
        if pins is not None:
            try:
                assert all(sha(path) == wanted for path, wanted in pins.items()), "Bound source/oracle input changed"
                assert sha(args.database) == DB_PIN
                result["inputs_unchanged"] = True
            except BaseException as error:
                result.update(status="FAILED", input_preservation_error=str(error))
        result.update(elapsed_seconds=time.monotonic() - began,
                      pending_full_C10_native_offline_recreation_screenshots_usability=True,
                      retained_drone_oracle_requirement={"original_path": MISSING_DRONE_ORIGINAL,
                                                         "sha256": ORACLE_PINS["drone"],
                                                         "verified_in_this_run": "drone" in oracles,
                                                         "required_only_for": ["drone", "both"]})
        write(args.output / "RESULT.json", result)
    print(json.dumps({"status": result["status"], "result": str(args.output / "RESULT.json")}), flush=True)
    return 0 if result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "product-source", "reference-source", "database", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--family", choices=("module", "drone", "both"), default="both")
    for family in ("module", "drone"):
        parser.add_argument("--" + family + "-oracle", type=Path)
        parser.add_argument("--" + family + "-oracle-sha256")
    parser.add_argument("--duration-oracle", type=Path)
    parser.add_argument("--duration-oracle-sha256")
    parser.add_argument("--reader-case", choices=tuple(CASE_KINDS), help=argparse.SUPPRESS)
    parser.add_argument("--reader-state", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--reader-state-sha256", help=argparse.SUPPRESS)
    raise SystemExit(main(parser.parse_args()))
