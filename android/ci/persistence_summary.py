"""Validate B02's three native process receipts against independent desktop data."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re


ROLES = ("sample", "projection_source", "projection_first", "projection_second", "projection_unlinked",
         "command_source", "command_first", "command_second", "command_unlinked")
PHASES = ("prepare", "reopen_edit", "verify")
STAGES = {"prepare": {"committed": "prepared"},
          "reopen_edit": {"opened": "prepared", "recipients_refreshed": "both", "committed": "edited"},
          "verify": {"opened": "edited"}}
REVISIONS = {"prepared": (2, 3, 3, 2, 1, 4, 3, 2, 1),
             "both": (2, 6, 6, 5, 1, 8, 7, 6, 1),
             "edited": (3, 7, 7, 6, 1, 9, 8, 7, 1)}
SNAPSHOT_KEYS = {"id", "revision", "name", "ship", "stats", "modules", "skills", "implants", "projections", "commands"}


def _equal(expected, actual, path):
    """Exact non-statistical comparison, allowing JSON's integral-decimal rendering."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and expected.keys() == actual.keys(), path
        for key in expected:
            _equal(expected[key], actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(expected) == len(actual), path
        for index, (left, right) in enumerate(zip(expected, actual)):
            _equal(left, right, f"{path}[{index}]")
    elif type(expected) is float:
        assert type(actual) in (int, float) and math.isfinite(actual) and expected == actual, path
    else:
        assert type(expected) is type(actual) and expected == actual, path


def _spec(oracles, role):
    if role == "sample":
        return oracles["ammunition"]["inputs"]
    return oracles[role.split("_")[0]]["inputs"]["source" if role.endswith("_source") else "target"]


def _selector(role, stage):
    kind = "ammunition" if role == "sample" else role.split("_")[0]
    source = role.endswith("_source")
    if role == "sample":
        state = "restored" if stage == "edited" else "iron_ammunition"
    elif role.endswith("_unlinked"):
        state = "initial"
    elif stage == "prepared":
        state = ("falloff" if kind == "projection" else "specialist_4") if source or role.endswith("_first") else "initial"
    elif stage == "edited" and role.endswith("_first"):
        state = "initial"
    else:
        state = "script_changed" if kind == "projection" else "harmonizing"
    return {"fixture": kind, "state": state, "role": "single" if kind == "ammunition" else "source" if source else "target"}


def _structure(oracles, ids, role, stage, snapshot):
    assert set(snapshot) == SNAPSHOT_KEYS, (stage, role, "snapshot keys")
    assert snapshot["id"] == ids[role]
    _equal(REVISIONS[stage][ROLES.index(role)], snapshot["revision"], f"{stage}.{role}.revision")
    spec = _spec(oracles, role)
    expected = {"name": spec["name"] if role == "sample" else f"B02 {role.replace('_', ' ')} – Δ",
                "ship": spec["ship"], "modules": [], "skills": {}, "implants": [], "projections": [], "commands": []}
    for index, module in enumerate(spec["modules"]):
        charge = module.get("charge")
        if role == "sample" and index in (0, 1):
            charge = "Antimatter Charge M" if stage == "edited" else "Iron Charge M"
        elif stage != "prepared" and index == 1:
            if role == "projection_source":
                charge = "Scan Resolution Dampening Script"
            elif role == "command_source":
                charge = "Shield Harmonizing Charge"
        expected["modules"].append({"index": index, "name": module["name"], "state": module["state"], "charge": charge})
    if role == "command_source":
        if stage == "prepared":
            expected["skills"] = {"Shield Command Specialist": 4}
        else:
            expected["implants"] = [{"name": "Shield Command Mindlink", "slot": 10, "active": True}]
    if role.endswith(("_first", "_second")) and not (stage == "edited" and role.endswith("_first")):
        kind = role.split("_")[0]
        link = {"source_id": ids[f"{kind}_source"], "active": stage != "prepared" or role.endswith("_first")}
        if kind == "projection":
            link.update(range_m=100000.0 if stage == "prepared" and role.endswith("_first") else 0.0, amount=1)
        expected[f"{kind}s"] = [link]
    for key, value in expected.items():
        _equal(value, snapshot[key], f"{stage}.{role}.{key}")


def _stats(expected, snapshot, types, path):
    actual = snapshot["stats"]
    assert actual.keys() == expected.keys() == types.keys() and len(actual) == 39, path
    for name, stat in expected.items():
        observed = actual[name]
        assert set(observed) == {"value", "unit"} and observed["unit"] == stat["unit"], (path, name)
        value = stat["value"]
        assert types[name] == {int: "integer", float: "decimal", bool: "boolean", str: "text"}[type(value)], (path, name, "wire type")
        # JSONObject may write 1750.0 as 1750. The separate scalar receipt was
        # collected from the decoded DTO, before Android exports this JSON.
        if type(value) in (int, float):
            assert type(observed["value"]) in (int, float) and math.isfinite(observed["value"]), (path, name)
            if type(value) is int:
                assert type(observed["value"]) is int and value == observed["value"], (path, name)
            else:
                assert math.isclose(value, observed["value"], rel_tol=1e-10, abs_tol=1e-9), (path, name)
        else:
            _equal(value, observed["value"], f"{path}.{name}")


def _operations(phase, ids, oracles):
    """The fixed native scenario, independent of its reported operation labels."""
    rows = []
    projection, command = ROLES[1:4], ROLES[5:8]

    def add(operation, arguments, affected):
        rows.append((operation, arguments, affected))

    def charges(role, indices, charge, affected):
        add("set_charges", {"fit_id": ids[role], "module_indices": indices, "charge": charge}, affected)

    def endpoints(kind, recipient, **extra):
        return {"source_id": ids[f"{kind}_source"], "target_id": ids[f"{kind}_{recipient}"], **extra}

    if phase == "prepare":
        charges("sample", [0, 1], "Iron Charge M", ("sample",))
        for role in ROLES[1:]:
            spec = deepcopy(_spec(oracles, role))
            spec["name"] = f"B02 {role.replace('_', ' ')} – Δ"
            for module in spec["modules"]:
                module.setdefault("charge", None)
            add("create_fit", {"spec": spec}, (role,))
        add("add_projection", endpoints("projection", "first", range_m=100000.0, active=True, amount=1), projection[:2])
        add("add_projection", endpoints("projection", "second", range_m=0.0, active=False, amount=1), projection)
        add("set_skill_level", {"fit_id": ids["command_source"], "skill": "Shield Command Specialist", "level": 4}, command[:1])
        add("add_command", endpoints("command", "first", active=True), command[:2])
        add("add_command", endpoints("command", "second", active=False), command)
    elif phase == "reopen_edit":
        for recipient in ("first", "second"):
            add("configure_projection", endpoints("projection", recipient, range_m=0.0, active=True, amount=1), projection)
        charges("projection_source", [1], "Scan Resolution Dampening Script", projection)
        add("set_command_active", endpoints("command", "second", active=True), command)
        add("set_skill_level", {"fit_id": ids["command_source"], "skill": "Shield Command Specialist", "level": 5}, command)
        add("add_implant", {"fit_id": ids["command_source"], "implant": "Shield Command Mindlink", "active": True}, command)
        charges("command_source", [1], "Shield Harmonizing Charge", command)
        add("remove_projection", endpoints("projection", "first"), projection)
        add("remove_command", endpoints("command", "first"), command)
        charges("sample", [0, 1], "Antimatter Charge M", ("sample",))
        charges("sample", [0, 999999], "Iron Charge M", ())  # Rejected edit, no publication.
    return rows


def summarize(reports, engine):
    root = Path(__file__).resolve().parents[2]
    assert len(reports) == 3 and [report["phase"] for report in reports] == list(PHASES)
    assert len({report["pid"] for report in reports}) == 3
    assert len({report["session_id"] for report in reports}) == 3
    ids = reports[0]["role_ids"]
    assert set(ids) == set(ROLES) and len(set(ids.values())) == 9
    assert all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) for value in ids.values())
    oracles, fixture_hashes, item_ids = {}, {}, {}
    for kind, filename in (("ammunition", "vexor"), ("projection", "projection"), ("command", "command")):
        data = (root / f"tools/android_reference/fixtures/{filename}.json").read_bytes().replace(b"\r\n", b"\n")
        oracles[kind] = json.loads(data)
        fixture_hashes[kind] = hashlib.sha256(data).hexdigest()
        for name, item_id in oracles[kind]["resolved_item_ids"].items():
            assert name not in item_ids or item_ids[name] == item_id
            item_ids[name] = item_id
    ammo_spec = {key: value for key, value in oracles["ammunition"]["inputs"].items() if key not in ("name", "edit")}
    target_spec = {key: value for key, value in oracles["projection"]["inputs"]["target"].items() if key != "name"}
    _equal(ammo_spec, target_spec, "scan resolution independent input equivalence")
    checked, request_ids, storage_paths = 0, set(), set()
    phase_summaries = []
    previous = None
    for phase_index, report in enumerate(reports):
        phase = report["phase"]
        assert report["task"] == "B02" and report["airplane_mode"] is True and report["no_internet_permission"] is True
        assert type(report["pid"]) is int and report["pid"] > 0
        assert isinstance(report["session_id"], str) and re.fullmatch(r"[0-9a-f]{32}", report["session_id"])
        _equal(ids, report["role_ids"], f"{phase}.stable IDs")
        manifest = report["manifest"]
        for key in ("database_sha256", "database_logical_sha256", "engine_source_sha256", "source_data_sha256",
                    "desktop_source_commit", "dataset_metadata"):
            _equal(engine[key], manifest[key], f"{phase}.manifest.{key}")
        assert set(report["fixtures"]) == set(oracles)
        for kind, oracle in oracles.items():
            proof = report["fixtures"][kind]
            assert proof["sha256"] == fixture_hashes[kind]
            assert proof["source_commit"] == oracle["source_commit"] == manifest["desktop_source_commit"]
            hash_key = "desktop_fixture_sha256" if kind == "ammunition" else f"{kind}_fixture_sha256"
            assert manifest[hash_key] == proof["sha256"]
            _equal(oracle["inputs"], proof["inputs"], f"{phase}.{kind}.inputs")
            _equal(oracle["eos_settings"], proof["eos_settings"], f"{phase}.{kind}.settings")
            for key in ("database_logical_sha256", "source_data_sha256", "dataset_metadata"):
                _equal(oracle[key], manifest[key], f"{phase}.{kind}.{key}")
        for boundary in ("start", "end"):
            runtime = report[f"runtime_{boundary}"]
            assert runtime["android_worker_thread"] == "pyfa-engine" and runtime["android_main_thread"] is False
            assert runtime["session_id"] == report["session_id"] and runtime["sample_id"] == ids["sample"]
            assert runtime["saveddata_connectionstring"] == "sqlite:///:memory:" and runtime["desktop_import_attempts"] == []
            _equal(manifest, runtime["manifest"], f"{phase}.{boundary}.manifest")
            _equal(manifest["dataset_metadata"], runtime["dataset_metadata"], f"{phase}.{boundary}.dataset")
            _equal(oracles["ammunition"]["eos_settings"], runtime["eos_settings"], f"{phase}.{boundary}.settings")
            active_roles = ("sample",) if phase == "prepare" and boundary == "start" else ROLES
            _equal(len(active_roles), runtime["retained_fit_count"], f"{phase}.{boundary}.fit count")
            _equal({ids[role]: _spec(oracles, role)["drones"] for role in active_roles}, runtime["drones"], f"{phase}.{boundary}.drones")
            resolved = runtime["resolved_item_ids"]
            assert resolved and set(resolved) <= set(item_ids)
            for name, item_id in resolved.items():
                _equal(item_ids[name], item_id, f"{phase}.{boundary}.item.{name}")
            current = ({"sample": oracles["ammunition"]["inputs"]} if len(active_roles) == 1 else
                       report["final_fits"] if boundary == "end" else report["observations"]["opened"])
            needed = set()
            for role, fit in current.items():
                needed.add(fit["ship"])
                for row in fit["modules"] + fit["implants"] + _spec(oracles, role)["drones"]:
                    needed.add(row["name"])
                    if row.get("charge"):
                        needed.add(row["charge"])
            assert needed <= set(resolved), (phase, boundary, "missing item provenance", needed - set(resolved))
            storage = runtime["persistence"]
            assert storage["enabled"] is True and storage["opened_existing"] is True
            _equal(1, storage["schema"], f"{phase}.{boundary}.schema")
            generation = (1, 15, 25)[phase_index] if boundary == "start" else (15, 25, 25)[phase_index]
            _equal(generation, storage["generation"], f"{phase}.{boundary}.generation")
            path = storage["path"]
            assert path.startswith("/data/") and path.endswith("/io.github.sussic.pyfa.dev/no_backup/fits/graph.sqlite3")
            assert ".." not in Path(path).parts
            storage_paths.add(path)
        stages = STAGES[phase]
        assert set(report["observations"]) == set(report["oracle_states"]) == set(stages)
        paths = set()
        for observation, stage in stages.items():
            observed, selectors = report["observations"][observation], report["oracle_states"][observation]
            assert set(observed) == set(selectors) == set(ROLES)
            for role in ROLES:
                selector = _selector(role, stage)
                _equal(selector, selectors[role], f"{phase}.{observation}.{role}.oracle")
                expected = oracles[selector["fixture"]]["states"][selector["state"]]
                if selector["fixture"] == "ammunition":
                    expected = {**expected, "scan_resolution": oracles["projection"]["states"]["initial"]["target"]["scan_resolution"]}
                else:
                    expected = expected[selector["role"]]
                path = f"{observation}.{role}"
                _structure(oracles, ids, role, stage, observed[role])
                _stats(expected, observed[role], report["scalar_types"][path], f"{phase}.{path}")
                paths.add(path)
        assert set(report["scalar_types"]) == paths
        checked += len(paths)
        final = report["final_fits"]
        _equal(report["observations"]["opened" if phase == "verify" else "committed"], final, f"{phase}.final graph")
        if previous is not None:
            _equal(previous["final_fits"], report["observations"]["opened"], f"{phase}.reopened graph")
        operations = _operations(phase, ids, oracles)
        assert len(report["requests"]) == len(report["responses"]) == len(operations)
        revisions = {ids["sample"]: 1} if previous is None else {fit["id"]: fit["revision"] for fit in previous["final_fits"].values()}
        published = {} if previous is None else deepcopy(previous["final_fits"])
        successes, errors = 0, []
        for request, response, (operation, arguments, affected) in zip(report["requests"], report["responses"], operations):
            assert set(request) == {"version", "request_id", "session_id", "operation", "arguments", "expected_revisions"}
            assert set(response) == {"version", "request_id", "session_id", "status", "fits", "error"}
            _equal(1, request["version"], f"{phase}.request version")
            _equal(1, response["version"], f"{phase}.response version")
            request_id = request["request_id"]
            assert isinstance(request_id, str) and 0 < len(request_id) <= 128 and request_id not in request_ids
            request_ids.add(request_id)
            assert response["request_id"] == request_id
            assert request["session_id"] == response["session_id"] == report["session_id"]
            assert request["operation"] == operation
            _equal(arguments, request["arguments"], f"{phase}.{operation}.arguments")
            named = [arguments[key] for key in ("fit_id", "source_id", "target_id") if key in arguments]
            _equal({fit_id: revisions[fit_id] for fit_id in named}, request["expected_revisions"], f"{phase}.{operation}.expected revisions")
            if not affected:
                assert response["status"] == "error" and response["fits"] == []
                assert set(response["error"]) == {"code", "message"}
                assert response["error"]["code"] == "INVALID_EDIT"
                assert isinstance(response["error"]["message"], str) and response["error"]["message"]
                errors.append("INVALID_EDIT")
                continue
            assert response["status"] == "ok" and response["error"] is None
            assert [fit["id"] for fit in response["fits"]] == [ids[role] for role in affected]
            for role, fit in zip(affected, response["fits"]):
                assert set(fit) == SNAPSHOT_KEYS
                revision = revisions.get(ids[role], 0) + 1
                _equal(revision, fit["revision"], f"{phase}.{operation}.{role}.revision")
                revisions[ids[role]] = revision
                published[role] = fit
            successes += 1
            if phase == "reopen_edit" and successes == 7:
                _equal(report["observations"]["recipients_refreshed"], published, "both recipients published together")
        _equal(final, published, f"{phase}.last successful publication")
        flags = report["assertions"]
        expected_flags = {"desktop_snapshots_checked": len(paths), "statistics_per_snapshot": 39,
                          "all_snapshots_matched_desktop": True, "raw_scalar_types_checked": True, "units_checked": True,
                          "successful_mutations": successes, "retained_fit_count": 9, "queries_unchanged": True,
                          "drones_match_inputs": True, "reopened_identity_and_revisions": previous is not None,
                          "reopened_full_graph": previous is not None, "failed_edit_unchanged": phase == "reopen_edit",
                          "both_recipients_refreshed": phase == "reopen_edit"}
        _equal(expected_flags, flags, f"{phase}.assertions")
        assert successes == (14, 10, 0)[phase_index]
        assert errors == (["INVALID_EDIT"] if phase == "reopen_edit" else [])
        read_order = [ids[role] for role in ("projection_second", "projection_first", "command_second", "command_first")]
        _equal([read_order] * (5 if phase == "reopen_edit" else 2), report["query_orders"], f"{phase}.recipient query order")
        phase_summaries.append({"phase": phase, "pid": report["pid"], "session_id": report["session_id"],
                                "generation_start": report["runtime_start"]["persistence"]["generation"],
                                "generation_end": report["runtime_end"]["persistence"]["generation"],
                                "desktop_snapshots": len(paths), "successful_mutations": successes, "structured_errors": errors})
        previous = report
    assert checked == 45 and len(request_ids) == 25 and len(storage_paths) == 1
    return {"desktop_snapshots": checked, "statistics_per_snapshot": 39, "fit_count": 9,
            "process_restarts": 2, "phases": phase_summaries, "responses_retained": len(request_ids),
            "successful_mutations": 24, "structured_errors": ["INVALID_EDIT"],
            "android_worker_thread": "pyfa-engine", "stable_ids_and_revisions": True,
            "whole_graph_reopened": True, "two_recipient_source_edits": True,
            "limits": ["API 36 x86_64 emulator; no physical, ARM64 or older-API execution claim.",
                       "Same installed APK across process restarts; no upgrade, migration or backup/restore claim."]}
