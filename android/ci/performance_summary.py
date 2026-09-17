"""Validate complete A10 receipts and summarize observed samples, without speed gates."""
import math
import statistics


OPERATIONS = {
    "ammunition": (1, ["iron_ammunition", "restored"]),
    "projection_range": (5, ["falloff", "applied_zero"]),
    "projection_link": (5, ["removed", "applied_zero"]),
    "command_charge": (9, ["harmonizing", "extension_restored"]),
    "command_link": (9, ["link_inactive", "link_active"]),
}


def distribution(values):
    assert values and all(type(value) in (int, float) and math.isfinite(value) and value > 0 for value in values)
    ordered = sorted(values)
    return {"samples": len(values), "min_ms": min(values), "median_ms": statistics.median(values),
            "observed_p95_ms": ordered[math.ceil(len(values) * .95) - 1], "max_ms": max(values)}


def summarize(launches, report, engine):
    assert len(launches) == 5
    assert len({sample["pid"] for sample in launches} | {report["pid"]}) == 6
    for index, sample in enumerate(launches):
        assert sample["sample"] == ("first_install" if index == 0 else f"cold_process_{index}")
        assert sample["database_installed"] is (index == 0)
        assert sample["database_sha256"] == engine["database_sha256"]
        assert sample["process_start_elapsed_ms"] < sample["engine_ready_elapsed_ms"] < sample["ready_draw_elapsed_ms"]
        assert sample["process_to_ready_draw_ms"] > sample["engine_start_to_ready_ms"] > 0
        phases = [sample[key] for key in ("queue_ms", "database_ms", "python_start_ms", "python_boot_snapshot_ms")]
        assert all(math.isfinite(value) and value >= 0 for value in phases)
        assert math.isclose(sum(phases), sample["engine_start_to_ready_ms"], abs_tol=1e-6)
        assert math.isclose(sample["process_to_ready_draw_ms"],
                            sample["ready_draw_elapsed_ms"] - sample["process_start_elapsed_ms"], abs_tol=1e-6)
        assert sample["memory"]["total_pss_kb"] > 0
    assert report["task"] == "A10" and report["instrumented_process"] is True
    assert report["airplane_mode"] is True and report["all_snapshots_matched_desktop"] is True
    assert report["retained_fit_count"] == 9
    assert report["startup"]["pid"] == report["pid"]
    assert report["startup"]["database_installed"] is False
    assert set(report["setup"]) == {"ammunition", "projection", "command"}
    for kind, count in (("ammunition", 1), ("projection", 5), ("command", 9)):
        setup = report["setup"][kind]
        assert setup["kind"] == kind and setup["retained_fit_count"] == count
        for key in ("database_sha256", "database_logical_sha256", "engine_source_sha256",
                    "source_data_sha256", "desktop_source_commit", "dataset_metadata"):
            assert setup[key] == engine[key], (kind, key)
        assert not setup["desktop_import_attempts"]
        distribution([report["setup_ms"][kind]])
    assert set(report["operations"]) == set(OPERATIONS)
    edits = {}
    for operation, (count, stages) in OPERATIONS.items():
        result = report["operations"][operation]
        assert result["retained_fit_count"] == count
        assert result["checked_snapshots"] == 24
        assert len(result["warmup_ms"]) == 4 and len(result["samples_ms"]) == 20
        assert set(result["actual_states"]) == set(stages)
        for stage, actual in result["actual_states"].items():
            assert actual["stage"] == stage and actual["retained_fit_count"] == count
            if operation == "ammunition":
                assert set(actual["stats"]) == {"single"} and len(actual["stats"]["single"]) == 38
            else:
                assert set(actual["stats"]) == {"source", "first", "second", "unlinked"}
                assert all(len(values) == 39 for values in actual["stats"].values())
                linked = stage not in ("removed", "link_inactive")
                assert actual["links"]["source_count"] == (2 if linked else 0)
                for role, link in actual["links"]["recipients"].items():
                    on = linked and role != "unlinked"
                    assert link == {"count": int(on), "forward": on, "reverse": on}
                if operation.startswith("command"):
                    assert actual["pending_command_bonuses"] == dict.fromkeys(("source", "first", "second", "unlinked"), 0)
        distribution(result["warmup_ms"])
        edits[operation] = {**distribution(result["samples_ms"]), "retained_fit_count": count,
                            "directions": {stage: distribution(result["samples_ms"][i::2]) for i, stage in enumerate(stages)}}
    expected_memory = {"before_activity", "single_fit_ready", "after_ammunition_setup", "after_projection_setup", "after_command_setup"}
    expected_memory |= {f"after_{operation}" for operation in OPERATIONS}
    assert set(report["memory"]) == expected_memory
    for memory in report["memory"].values():
        assert memory["total_pss_kb"] > 0 and memory["total_private_dirty_kb"] >= 0
    startup_distribution = distribution([sample["process_to_ready_draw_ms"] for sample in launches[1:]])
    del startup_distribution["observed_p95_ms"]  # Four observations do not support a tail estimate.
    return {
        "normal_startup": {"first_install_ms": launches[0]["process_to_ready_draw_ms"],
                           "cold_process_reusing_database": startup_distribution},
        "setup_ms": report["setup_ms"], "edits": edits, "memory_snapshots": report["memory"],
        "normal_startup_memory_snapshots": [sample["memory"] for sample in launches],
        "checked_edit_snapshots": 120, "checked_setup_snapshots": 3,
        "measurement_limits": [
            "Debug APK, API36 x86_64 emulator; not a physical-phone or release-build benchmark.",
            "Startup is process-start to ready Compose draw; excludes earlier system dispatch/zygote time. Raw ADB request-to-receipt also includes transport, report writing and polling.",
            "One fresh installation and four force-stopped process launches reuse OS page/disk caches. No device reboot/cold disk, warm/hot Activity or startup percentile claim.",
            "Edits include serialized queue, JNI, EOS mutation, refreshed role snapshots and both JSON directions; exclude golden assertions and UI interaction/rendering. No contention injected.",
            "Projection/command operations update two recipients; four roles are read including unlinked control. Commands include the reference mindlink.",
            "Four warmups, twenty alternating samples (ten per direction); p95 is descriptive of these samples, not a reliable device-tail estimate.",
            "Memory is current process PSS/private dirty, not peak or a leak test; protected graphics may be omitted. Edit-test memory includes instrumentation, assertions and reports.",
            "Fit counts stay1/5/9 by stage: earlier fit graphs remain alive. Graph setup and memory are cumulative; no per-fit or command-only memory claim.",
        ],
    }
