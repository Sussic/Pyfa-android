"""B02 restart and interrupted-save tests; every engine runs in a fresh process."""
from contextlib import closing
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from android_bridge.store import GraphStore, encode_graph
from tools.android_reference.reference import compare

ROOT = Path(__file__).resolve().parents[3]
DATABASE = None
IDENTITY = None
RUNNER = ROOT / "tools/android_headless/check_persistence.py"


def worker(mode, database, identity, store_path, output):
    from android_bridge import HeadlessEngine
    from android_bridge.contract import BridgeSession
    cases, expected = {}, {}
    for kind, name in (("ammunition", "vexor"), ("projection", "projection"), ("command", "command")):
        cases[kind] = json.loads((ROOT / "tools/android_reference" / (name + ".json")).read_text(encoding="utf-8"))
        expected[kind] = json.loads((ROOT / "tools/android_reference/fixtures" / (name + ".json")).read_text(encoding="utf-8"))
    spec = deepcopy(cases["ammunition"])
    spec.pop("edit")
    engine = HeadlessEngine(database)
    original_commit = GraphStore._commit
    if mode.startswith("initial_kill_"):
        def interrupt_initial(connection):
            if mode.endswith("after"):
                original_commit(connection)
            os._exit(61)
        with patch.object(GraphStore, "_commit", side_effect=interrupt_initial):
            BridgeSession.open(engine, store_path, identity, spec)
        raise AssertionError("Initial commit interruption did not occur")
    if mode == "open_invalid":
        try:
            BridgeSession.open(engine, store_path, identity, spec)
        except Exception as error:
            output.write_text(json.dumps({"rejected": True, "error": type(error).__name__}), encoding="utf-8")
            return
        raise AssertionError("Invalid saved fits unexpectedly opened")
    bridge = BridgeSession.open(engine, store_path, identity, spec)
    initial = json.loads(bridge.bootstrap())

    def send(operation, arguments, error=None):
        keys = {arguments[key] for key in ("fit_id", "source_id", "target_id") if key in arguments}
        request = {"version": 1, "request_id": "persistence-check", "session_id": bridge.session_id,
                   "operation": operation, "arguments": arguments,
                   "expected_revisions": {key: bridge._revisions[key] for key in keys}}
        result = json.loads(bridge.dispatch(json.dumps(request)))
        assert result["status"] == ("error" if error else "ok"), result
        if error:
            assert result["error"]["code"] == error and result["fits"] == [], result
        return result

    def edit_ammunition(error=None):
        return send("set_charges", {"fit_id": bridge.sample_id, "module_indices": [0, 1],
                                    "charge": "Antimatter Charge M"}, error)

    detail = {}
    if mode == "seed":
        def create(kind, role, suffix):
            fit_spec = deepcopy(cases[kind][role])
            fit_spec["name"] += suffix
            return send("create_fit", {"spec": fit_spec})["fits"][0]["id"]
        send("set_charges", {"fit_id": bridge.sample_id, "module_indices": [0, 1], "charge": "Iron Charge M"})
        for kind in ("projection", "command"):
            source = create(kind, "source", " source")
            targets = [create(kind, "target", " " + role) for role in ("first", "second", "unlinked")]
            if kind == "projection":
                for target, distance, active in ((targets[0], 100000.0, True), (targets[1], 0.0, False)):
                    send("add_projection", {"source_id": source, "target_id": target,
                         "range_m": distance, "active": active, "amount": 1})
                # Preserve cascaded unlearned values even after parent returns V.
                for level in (0, 5):
                    send("set_skill_level", {"fit_id": targets[2], "skill": "Gunnery", "level": level})
            else:
                send("add_implant", {"fit_id": source, "implant": "Shield Command Mindlink", "active": True})
                for active in (False, True):
                    send("set_implant_active", {"fit_id": source, "slot": 10, "active": active})
                for level in (4, 5):
                    send("set_skill_level", {"fit_id": source, "skill": "Shield Command Specialist", "level": level})
                for state in ("ONLINE", "ACTIVE"):
                    send("set_module_states", {"fit_id": source, "module_indices": [1], "state": state})
                send("set_charges", {"fit_id": source, "module_indices": [1], "charge": "Shield Harmonizing Charge"})
                for index, target in enumerate(targets[:2]):
                    send("add_command", {"source_id": source, "target_id": target, "active": index == 0})
        rows = send("snapshot", {"fit_ids": []})["fits"]
        compare(expected["ammunition"]["states"]["iron_ammunition"],
                {key: value for key, value in rows[0]["stats"].items() if key != "scan_resolution"})
        for index, kind, stage, role in ((1, "projection", "applied_zero", "source"),
                (2, "projection", "falloff", "target"), (3, "projection", "initial", "target"),
                (5, "command", "harmonizing", "source"), (6, "command", "harmonizing", "target"),
                (7, "command", "initial", "target"), (8, "command", "initial", "target")):
            compare(expected[kind]["states"][stage][role], rows[index]["stats"])
        assert any(level is None for level in rows[4]["skills"].values())
        detail["independent_fixture_comparisons"] = True
    elif mode in ("failure_before", "failure_after", "kill_before", "kill_after"):
        def interrupted_commit(connection):
            if mode.endswith("after"):
                original_commit(connection)
            if mode.startswith("kill"):
                os._exit(62)
            raise OSError("Injected saved-file commit failure")
        with patch.object(bridge._store, "_commit", side_effect=interrupted_commit):
            edit_ammunition("ENGINE_ERROR" if mode == "failure_before" else None)
        if mode == "failure_before":
            assert json.loads(bridge.bootstrap())["fits"] == initial["fits"]
    elif mode in ("confirmation_failure", "publication_failure"):
        seam = "confirm" if mode == "confirmation_failure" else "accept"
        with patch.object(bridge._store, seam, side_effect=OSError("Injected confirmation/publication failure")):
            edit_ammunition("ENGINE_UNAVAILABLE")
        send("snapshot", {"fit_ids": []}, "ENGINE_UNAVAILABLE")
        detail["terminal"] = True
    elif mode == "stale_writer":
        external = output.with_suffix(".other.json")
        subprocess.run([sys.executable, "-I", str(RUNNER), "--worker", "edit", "--database", str(database),
                        "--identity", identity, "--store", str(store_path), "--output", str(external)], check=True)
        digest = hashlib.sha256(store_path.read_bytes()).hexdigest()
        edit_ammunition("ENGINE_UNAVAILABLE")
        assert hashlib.sha256(store_path.read_bytes()).hexdigest() == digest
        detail["terminal"] = True
        detail["external"] = json.loads(external.read_text(encoding="utf-8"))
    elif mode == "edit":
        edit_ammunition()
    elif mode == "read_reject":
        generation = bridge.persistence_info["generation"]
        send("snapshot", {"fit_ids": []})
        send("set_charges", {"fit_id": bridge.sample_id, "module_indices": [999], "charge": "Iron Charge M"}, "INVALID_EDIT")
        assert generation == bridge.persistence_info["generation"]
        assert json.loads(bridge.bootstrap())["fits"] == initial["fits"]
    elif mode != "reopen":
        raise ValueError("Unknown persistence worker")
    result = {"session_id": bridge.session_id, "sample_id": bridge.sample_id,
              "persistence": bridge.persistence_info, "bootstrap": json.loads(bridge.bootstrap()),
              "retained_fit_count": len(engine._fits), "detail": detail}
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="pyfa-b02-check-")
        self.root = Path(self.directory.name)
        self.store = self.root / "fits.sqlite"
        self.sequence = 0

    def tearDown(self):
        self.directory.cleanup()

    def run_worker(self, mode, expected_exit=0):
        self.sequence += 1
        output = self.root / (str(self.sequence) + ".json")
        result = subprocess.run([sys.executable, "-I", str(RUNNER), "--worker", mode, "--database", str(DATABASE),
                                 "--identity", IDENTITY, "--store", str(self.store), "--output", str(output)],
                                capture_output=True, text=True, encoding="utf-8", timeout=90)
        self.assertEqual(result.returncode, expected_exit, result.stdout + result.stderr)
        return json.loads(output.read_text(encoding="utf-8")) if expected_exit == 0 else None

    def assert_roundtrip(self, before, after):
        self.assertNotEqual(before["session_id"], after["session_id"])
        self.assertEqual(before["sample_id"], after["sample_id"])
        self.assertEqual(before["bootstrap"]["fits"], after["bootstrap"]["fits"])
        self.assertEqual(before["persistence"]["generation"], after["persistence"]["generation"])
        self.assertTrue(after["persistence"]["opened_existing"])

    def test_nine_fit_graph_reopens_in_a_fresh_process(self):
        before = self.run_worker("seed")
        after = self.run_worker("reopen")
        self.assert_roundtrip(before, after)
        self.assertEqual(after["retained_fit_count"], 9)
        self.assertTrue(before["detail"]["independent_fixture_comparisons"])
        rows = after["bootstrap"]["fits"]
        self.assertEqual(len(rows[2]["projections"]), 1)
        self.assertFalse(rows[3]["projections"][0]["active"])
        self.assertTrue(rows[6]["commands"][0]["active"])
        self.assertFalse(rows[7]["commands"][0]["active"])
        self.assertTrue(any(level is None for level in rows[4]["skills"].values()))
        self.assertEqual(rows[5]["implants"], [{"name": "Shield Command Mindlink", "slot": 10, "active": True}])

    def test_reads_rejections_and_failed_commit_keep_prior_generation(self):
        before = self.run_worker("seed")
        self.assert_roundtrip(before, self.run_worker("read_reject"))
        self.assert_roundtrip(before, self.run_worker("failure_before"))
        self.assert_roundtrip(before, self.run_worker("reopen"))

    def test_exception_after_real_commit_acknowledges_confirmed_candidate(self):
        before = self.run_worker("seed")
        saved = self.run_worker("failure_after")
        self.assertEqual(saved["persistence"]["generation"], before["persistence"]["generation"] + 1)
        self.assertEqual(saved["bootstrap"]["fits"][0]["modules"][0]["charge"], "Antimatter Charge M")
        self.assert_roundtrip(saved, self.run_worker("reopen"))

    def test_process_death_before_commit_preserves_previous_graph(self):
        before = self.run_worker("seed")
        self.run_worker("kill_before", 62)
        self.assert_roundtrip(before, self.run_worker("reopen"))

    def test_process_death_after_commit_reopens_complete_candidate(self):
        before = self.run_worker("seed")
        self.run_worker("kill_after", 62)
        after = self.run_worker("reopen")
        self.assertEqual(after["persistence"]["generation"], before["persistence"]["generation"] + 1)
        self.assertEqual(after["bootstrap"]["fits"][0]["revision"], before["bootstrap"]["fits"][0]["revision"] + 1)
        self.assertEqual(after["bootstrap"]["fits"][0]["modules"][0]["charge"], "Antimatter Charge M")
        self.assertEqual(after["bootstrap"]["fits"][1:], before["bootstrap"]["fits"][1:])

    def test_confirmation_failure_is_terminal_without_reverting_saved_candidate(self):
        before = self.run_worker("seed")
        failed = self.run_worker("confirmation_failure")
        self.assertEqual(failed["bootstrap"]["error"]["code"], "ENGINE_UNAVAILABLE")
        after = self.run_worker("reopen")
        self.assertEqual(after["persistence"]["generation"], before["persistence"]["generation"] + 1)
        self.assertEqual(after["bootstrap"]["fits"][0]["modules"][0]["charge"], "Antimatter Charge M")

    def test_publication_failure_after_confirmed_save_never_reverts_candidate(self):
        before = self.run_worker("seed")
        failed = self.run_worker("publication_failure")
        self.assertEqual(failed["bootstrap"]["error"]["code"], "ENGINE_UNAVAILABLE")
        after = self.run_worker("reopen")
        self.assertEqual(after["persistence"]["generation"], before["persistence"]["generation"] + 1)
        self.assertEqual(after["bootstrap"]["fits"][0]["modules"][0]["charge"], "Antimatter Charge M")

    def test_stale_writer_cannot_overwrite_another_process_commit(self):
        self.run_worker("seed")
        stale = self.run_worker("stale_writer")
        self.assertTrue(stale["detail"]["terminal"])
        self.assert_roundtrip(stale["detail"]["external"], self.run_worker("reopen"))

    def test_interrupted_initialization_leaves_no_partial_final_file(self):
        for mode in ("initial_kill_before", "initial_kill_after"):
            with self.subTest(mode=mode):
                self.run_worker(mode, 61)
                self.assertFalse(self.store.exists())
                reopened = self.run_worker("reopen")
                self.assertEqual(reopened["persistence"]["generation"], 1)
                self.assertEqual(len(reopened["bootstrap"]["fits"]), 1)
                self.store.unlink()

    def test_initial_install_never_replaces_an_existing_destination(self):
        first = GraphStore(self.store)
        attempt = first.prepare({"new": "candidate"})
        other = GraphStore(self.store)
        winner = other.prepare({"other": "winner"})
        other.write(winner)
        digest = hashlib.sha256(self.store.read_bytes()).hexdigest()
        with self.assertRaises(FileExistsError):
            first.write(attempt)
        self.assertEqual(hashlib.sha256(self.store.read_bytes()).hexdigest(), digest)

    def test_invalid_unsupported_or_mismatched_saved_files_are_preserved(self):
        self.run_worker("seed")
        original = self.root / "valid.sqlite"
        shutil.copyfile(self.store, original)
        variants = ("corrupt", "schema", "checksum", "dataset", "settings", "graph_version", "empty",
                    "sample", "duplicate_order", "dangling_edge", "skill_bool", "unknown_item")
        for variant in variants:
            with self.subTest(variant=variant):
                shutil.copyfile(original, self.store)
                if variant == "corrupt":
                    self.store.write_bytes(b"Broken SQLite header" + self.store.read_bytes()[20:])
                else:
                    with closing(sqlite3.connect(self.store)) as connection:
                        if variant == "schema":
                            connection.execute("PRAGMA user_version=999")
                        elif variant == "checksum":
                            connection.execute("UPDATE graph_state SET payload_sha256='bad'")
                        else:
                            graph = json.loads(connection.execute("SELECT payload FROM graph_state").fetchone()[0])
                            first = graph["fit_order"][0]
                            if variant == "dataset": graph["dataset_identity"] = "0" * 64
                            elif variant == "settings": graph["eos_settings"]["strictSkillLevels"] = False
                            elif variant == "graph_version": graph["format"] = 999
                            elif variant == "empty": graph.update(fit_order=[], records={}, revisions={}, sample_id=None)
                            elif variant == "sample": graph["sample_id"] = None
                            elif variant == "duplicate_order": graph["fit_order"].append(first)
                            elif variant == "dangling_edge": graph["records"][first]["commands"] = [{"source_id": "missing", "active": True}]
                            elif variant == "skill_bool": graph["records"][first]["skills"]["Gunnery"] = True
                            elif variant == "unknown_item": graph["records"][first]["spec"]["modules"][0]["name"] = "B02 nonexistent module"
                            payload = encode_graph(graph)
                            connection.execute("UPDATE graph_state SET payload=?,payload_sha256=?",
                                               (payload, hashlib.sha256(payload.encode()).hexdigest()))
                        connection.commit()
                before = self.store.read_bytes()
                self.assertTrue(self.run_worker("open_invalid")["rejected"])
                self.assertEqual(self.store.read_bytes(), before)
