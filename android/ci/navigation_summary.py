"""Validate B03.2 actual observations against independent desktop fixtures."""
import json
from pathlib import Path
from library_summary import equal


def summarize(reports):
    assert [row["phase"] for row in reports] == ["prepare", "restored", "disabled", "closed"]
    assert len({row["pid"] for row in reports}) == 4
    assert len({row["runtime"]["session_id"] for row in reports}) == 4
    fixtures = Path(__file__).resolve().parents[2] / "tools/android_reference/fixtures"
    expected = {"Vexor": json.loads((fixtures / "projection.json").read_text())["states"]["initial"]["target"],
                "Vulture": json.loads((fixtures / "command.json").read_text())["states"]["initial"]["source"]}
    checks = set()
    previous = None
    stats_checked = 0
    for report in reports:
        assert report["task"] == "B03.2"
        runtime = report["runtime"]
        assert runtime["persistence"]["enabled"] and runtime["persistence"]["opened_existing"]
        assert runtime["android_worker_thread"] == "pyfa-engine" and not runtime["android_main_thread"]
        assert not runtime["desktop_import_attempts"]
        assert report["catalog_groups"] == 55 and report["catalog_hulls"] == 437
        initial, final = report["initial"], report["final"]
        if previous is None:
            assert not initial["fits"] and not initial["open_ids"]
        else:
            equal(previous["fits"], initial["fits"])
            equal(previous["modified"], initial["modified"])
            assert previous["restore"] == initial["restore"]
            assert previous["hide_empty"] == initial["hide_empty"]
            assert initial["open_ids"] == (previous["open_ids"] if previous["restore"] else [])
            assert initial["active_id"] == (previous["active_id"] if previous["restore"] else None)
        for state in (initial, final):
            ids = {fit["id"] for fit in state["fits"]}
            assert set(state["modified"]) == ids
            assert set(state["open_ids"]) <= ids and len(set(state["open_ids"])) == len(state["open_ids"])
            assert state["active_id"] in state["open_ids"] if state["open_ids"] else state["active_id"] is None
            for fit in state["fits"]:
                golden = expected[fit["ship"]]
                equal(golden, fit["stats"])
                assert fit["types"] == {key: {int: "Integer", float: "Decimal", bool: "BooleanValue", str: "Text"}[type(stat["value"])] for key, stat in golden.items()}
                stats_checked += len(golden)
        assert len(final["fits"]) == 2
        checks.update(report["checks"])
        previous = final
    assert checks == {
        "independent_desktop_catalog", "opening_does_not_modify_recents", "rename_updates_recents",
        "groups_races_empty_visibility_and_back", "back_to_correct_hull", "search_opens_intended_id",
        "close_active_inactive_and_delete_open", "activity_recreation_and_restore_enabled",
        "corrupt_preferences_preserved", "previous_set_and_active_restored",
        "close_all_preserves_saved_fits_and_disable_restore",
        "disabled_restart_keeps_library_and_enabled_close_all", "empty_open_set_stays_empty_after_restart",
    }
    return {"processes": 4, "checks": sorted(checks), "desktop_statistics_checked": stats_checked,
            "desktop_catalog_groups": 55, "desktop_catalog_hulls": 437, "restart_boundaries": 3}
