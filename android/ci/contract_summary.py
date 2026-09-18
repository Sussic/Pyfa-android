"""Validate B01's native receipt against the unchanged independent fixtures."""
import hashlib
import math
from pathlib import Path
import json


def summarize(report, engine):
    root = Path(__file__).resolve().parents[2]
    assert report["task"] == "B01" and report["airplane_mode"] is True
    assert report["no_internet_permission"] is True
    runtime, manifest = report["runtime"], report["manifest"]
    assert runtime["android_worker_thread"] == "pyfa-engine" and runtime["android_main_thread"] is False
    assert runtime["session_id"] == report["session_id"]
    assert runtime["saveddata_connectionstring"] == "sqlite:///:memory:"
    assert runtime["retained_fit_count"] == 5 and not runtime["desktop_import_attempts"]
    assert runtime["manifest"] == manifest
    for key in ("database_sha256", "database_logical_sha256", "engine_source_sha256", "source_data_sha256",
                "desktop_source_commit", "dataset_metadata"):
        assert manifest[key] == engine[key], key
    flags = report["assertions"]
    for key in ("all_snapshots_matched_desktop", "raw_scalar_types_checked", "units_checked",
                "bulk_rejection_unchanged", "stale_revision_unchanged", "queries_unchanged",
                "unrelated_revisions_unchanged", "queued_same_revision_one_success_one_conflict",
                "missing_revision_rejected_before_dispatch", "invalid_create_unchanged",
                "queued_arguments_copied", "ui_preserved_after_errors"):
        assert flags[key] is True, key
    assert flags["desktop_snapshots_checked"] == 63
    assert flags["statistics_per_snapshot"] == 39 and flags["retained_fit_count"] == 5
    assert len(report["codec_rejections"]) == 15
    assert len(set(report["codec_rejections"])) == len(report["codec_rejections"])
    oracles = {}
    for kind, filename in (("ammunition", "vexor"), ("projection", "projection"), ("command", "command")):
        data = (root / f"tools/android_reference/fixtures/{filename}.json").read_bytes()
        oracle = oracles[kind] = json.loads(data)
        proof = report["fixtures"][kind]
        # The build stages LF-normalized fixtures, including on Windows hosts.
        assert proof["sha256"] == hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        assert proof["source_commit"] == oracle["source_commit"] == manifest["desktop_source_commit"]
        assert proof["inputs"] == oracle["inputs"]
        assert proof["eos_settings"] == oracle["eos_settings"] == runtime["eos_settings"]
        for key in ("database_logical_sha256", "source_data_sha256", "dataset_metadata"):
            assert oracle[key] == manifest[key], key
    checked = set()

    def compare(expected, snapshot, path):
        actual = snapshot["stats"]
        types = report["scalar_types"][path]
        assert actual.keys() == expected.keys() == types.keys(), path
        assert type(snapshot["revision"]) is int and snapshot["revision"] >= 1
        assert snapshot["id"] and len(snapshot["id"]) <= 128
        for name, stat in expected.items():
            observed = actual[name]
            assert set(observed) == {"value", "unit"}
            assert observed["unit"] == stat["unit"], (path, name)
            value = stat["value"]
            scalar = {int: "integer", float: "decimal", bool: "boolean", str: "text"}[type(value)]
            assert types[name] == scalar, (path, name, "wire type")
            # Android's report writer may render a decimal 1.0 as JSON 1. Its
            # separate type receipt is captured from the strict DTO before export.
            if type(value) in (int, float):
                assert type(observed["value"]) in (int, float) and math.isfinite(observed["value"])
                if type(value) is int:
                    assert value == observed["value"], (path, name)
                else:
                    assert math.isclose(value, observed["value"], rel_tol=1e-10, abs_tol=1e-9), (path, name)
            else:
                assert type(value) is type(observed["value"]) and value == observed["value"], (path, name)
        checked.add(path)

    states = report["states"]
    assert set(states) == set(oracles)
    ammo_spec = dict(oracles["ammunition"]["inputs"])
    ammo_spec.pop("name")
    ammo_spec.pop("edit")
    target_spec = dict(oracles["projection"]["inputs"]["target"])
    target_spec.pop("name")
    assert ammo_spec == target_spec
    scan = oracles["projection"]["states"]["initial"]["target"]["scan_resolution"]
    for kind, oracle in oracles.items():
        assert states[kind].keys() == oracle["states"].keys()
        for stage, expected in oracle["states"].items():
            if kind == "ammunition":
                compare({**expected, "scan_resolution": scan}, states[kind][stage], f"{kind}.{stage}")
            else:
                assert set(states[kind][stage]) == {"source", "target"}
                for role in ("source", "target"):
                    compare(expected[role], states[kind][stage][role], f"{kind}.{stage}.{role}")
    assert len(checked) == 63 and set(report["scalar_types"]) == checked
    request_ids, errors = set(), []
    for response in report["responses"]:
        assert response["session_id"] == report["session_id"]
        assert response["request_id"] and response["request_id"] not in request_ids
        request_ids.add(response["request_id"])
        if response["status"] == "error":
            assert response["fits"] == [] and response["error"]["message"]
            errors.append(response["error"]["code"])
        else:
            assert response["status"] == "ok" and response["error"] is None
    assert len(request_ids) == 44
    assert sorted(errors) == sorted(["INVALID_EDIT"] * 3 + ["REVISION_CONFLICT"] * 2 +
                                    ["UNKNOWN_FIT", "INVALID_REQUEST"])
    return {"desktop_snapshots": len(checked), "statistics_per_snapshot": 39,
            "responses_retained": len(request_ids), "structured_errors": errors,
            "codec_rejections": report["codec_rejections"], "assertions": flags,
            "android_worker_thread": runtime["android_worker_thread"],
            "fresh_process_pid": report["pid"], "fit_count": runtime["retained_fit_count"]}
