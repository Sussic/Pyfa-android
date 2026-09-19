"""B03.1 real EOS lifecycle, durable restart and failed-save regressions."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from android_bridge.contract import BridgeSession
from android_bridge.store import GraphStore
from tools.android_reference.reference import compare

ENGINE = CASES = EXPECTED = IDENTITY = DATABASE = None
ROOT = Path(__file__).resolve().parents[3]


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "fits.sqlite3"
        self.spec = deepcopy(CASES["ammunition"])
        self.spec.pop("edit")
        self.bridge = BridgeSession.open(ENGINE, self.path, IDENTITY, self.spec)
        self.sample = self.bridge.sample_id
        self.serial = 0

    def tearDown(self):
        import eos.db
        self.bridge._reset_storage()
        eos.db.saveddata_session.commit()
        self.directory.cleanup()

    def send(self, operation, arguments, code=None, revisions=None):
        self.serial += 1
        named = {arguments[key] for key in ("fit_id", "source_id", "target_id") if key in arguments}
        request = {"version": 1, "request_id": str(self.serial), "session_id": self.bridge.session_id,
            "operation": operation, "arguments": arguments, "expected_revisions": revisions if revisions is not None else
            {key: self.bridge._revisions.get(key, 0) for key in named}}
        result = json.loads(self.bridge.dispatch(json.dumps(request)))
        self.assertEqual(result["request_id"], request["request_id"])
        self.assertEqual(result["status"], "error" if code else "ok", result)
        if code:
            self.assertEqual(result["error"]["code"], code, result)
            self.assertEqual(result["fits"], [])
        return result["fits"]

    def current(self):
        return self.send("snapshot", {"fit_ids": []})

    def create(self, kind="ammunition", role=None):
        spec = deepcopy(CASES[kind] if role is None else CASES[kind][role])
        spec.pop("edit", None)
        return self.send("create_fit", {"spec": spec})[0]["id"]

    def delete(self, key, code=None, resolve=True):
        return self.send("delete_fit", {"fit_id": key, "resolve_references": resolve}, code)

    def reopen(self):
        output = Path(self.directory.name) / "reopened.json"
        subprocess.run([sys.executable, "-I", str(ROOT / "tools/android_headless/check_persistence.py"),
            "--database", str(DATABASE), "--identity", IDENTITY, "--store", str(self.path),
            "--output", str(output), "--worker", "reopen"], check=True, capture_output=True, text=True,
            encoding="utf-8", timeout=60)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_unicode_rename_stale_invalid_and_restart(self):
        before = self.current()[0]
        for name in ("", "   ", "a\nb", "a" * 201):
            self.send("rename_fit", {"fit_id": self.sample, "name": name}, "INVALID_REQUEST")
        renamed = self.send("rename_fit", {"fit_id": self.sample, "name": "探索 Δ 🚀"})[0]
        self.assertEqual(renamed, {**before, "name": "探索 Δ 🚀", "revision": 2})
        self.send("rename_fit", {"fit_id": self.sample, "name": "stale"}, "REVISION_CONFLICT", {self.sample: 1})
        reopened = self.reopen()
        self.assertNotEqual(reopened["session_id"], self.bridge.session_id)
        self.assertEqual(reopened["bootstrap"]["fits"], self.current())

    def test_copy_actual_inputs_links_and_independent_edits(self):
        source = self.create("command", "source")
        target = self.sample
        self.send("set_skill_level", {"fit_id": source, "skill": "Shield Command Specialist", "level": 4})
        self.send("add_implant", {"fit_id": source, "implant": "Shield Command Mindlink", "active": True})
        self.send("add_command", {"source_id": source, "target_id": target, "active": True})
        projection = self.create("projection", "source")
        self.send("add_projection", {"source_id": projection, "target_id": source,
            "range_m": 100000, "active": False, "amount": 2})
        originals = {fit["id"]: fit for fit in self.current()}
        copied = self.send("duplicate_fit", {"fit_id": source, "name": "Source copy"})
        copy_id = next(fit["id"] for fit in copied if fit["id"] not in originals)
        copy = self.bridge._records[copy_id]
        expected = deepcopy(self.bridge._records[source]); expected["spec"]["name"] = "Source copy"
        self.assertEqual(copy, expected)
        self.assertEqual(self.bridge._records[target]["commands"], [{"source_id": source, "active": True}])
        for fit in copied:
            if fit["id"] in originals:
                old = originals[fit["id"]]
                self.assertEqual({k: v for k, v in old.items() if k != "stats"}, {k: v for k, v in fit.items() if k != "stats"})
                compare(old["stats"], fit["stats"], fit["name"])
        self.send("set_implant_active", {"fit_id": copy_id, "slot": 10, "active": False})
        self.send("set_skill_level", {"fit_id": copy_id, "skill": "Shield Command Specialist", "level": 3})
        self.assertEqual(self.bridge._records[source], {**expected, "spec": {**expected["spec"], "name": originals[source]["name"]}})
        self.assertEqual(self.reopen()["bootstrap"]["fits"], self.current())
        # Copy a recipient: incoming links still point at the same sources.
        before = {fit["id"] for fit in self.current()}
        result = self.send("duplicate_fit", {"fit_id": target, "name": "Recipient copy"})
        recipient = next(fit for fit in result if fit["id"] not in before)
        self.assertEqual(recipient["commands"], originals[target]["commands"])
        self.send("set_charges", {"fit_id": recipient["id"], "module_indices": [0, 1], "charge": "Iron Charge M"})
        self.assertEqual(self.bridge.get_fit(target).modules[0].charge.name, "Antimatter Charge M")

    def test_delete_source_updates_both_kinds_and_preserves_control(self):
        source = self.create("command", "source")
        other = self.create()
        control = self.create()
        for target in (self.sample, other):
            self.send("add_command", {"source_id": source, "target_id": target, "active": True})
            self.send("add_projection", {"source_id": source, "target_id": target,
                "range_m": 0, "active": False, "amount": 1})
        before = self.current(); control_before = next(f for f in before if f["id"] == control)
        self.delete(source, "INVALID_EDIT", resolve=False)
        self.assertEqual(before, self.current())
        result = self.delete(source)
        self.assertEqual([f["id"] for f in result], [self.sample, other, control])
        for fit in result:
            self.assertEqual(fit["commands"], []); self.assertEqual(fit["projections"], [])
            compare(EXPECTED["command"]["states"]["initial"]["target"], fit["stats"])
        self.assertEqual(result[-1], control_before)
        self.assertEqual(self.reopen()["bootstrap"]["fits"], result)
        self.delete(source, "UNKNOWN_FIT")

    def test_delete_recipient_cleans_reverse_links(self):
        source = self.create("projection", "source")
        self.send("add_projection", {"source_id": source, "target_id": self.sample,
            "range_m": 0, "active": True, "amount": 1})
        victim_eos_id = self.bridge.get_fit(self.sample).ID
        self.delete(self.sample)
        self.assertNotIn(victim_eos_id, self.bridge.get_fit(source).projectedOnto)
        self.assertEqual(self.bridge.sample_id, source)
        self.assertEqual(self.reopen()["bootstrap"]["fits"], self.current())

    def test_last_delete_reopens_empty_then_can_create(self):
        self.assertEqual(self.delete(self.sample), [])
        self.assertIsNone(self.bridge.sample_id)
        reopened = self.reopen()
        self.assertEqual(reopened["bootstrap"]["fits"], [])
        self.assertIsNone(reopened["sample_id"])
        self.assertEqual(json.loads(GraphStore(self.path).current.payload)["format"], 2)
        new_id = self.create()
        self.assertNotEqual(new_id, self.sample)
        self.assertEqual(self.bridge.sample_id, new_id)
        self.assertEqual(self.reopen()["bootstrap"]["fits"], self.current())

    def test_failed_saves_restore_rename_copy_and_last_delete(self):
        before = self.current(); disk = self.path.read_bytes()
        for operation, args in (("rename_fit", {"fit_id": self.sample, "name": "New"}),
            ("duplicate_fit", {"fit_id": self.sample, "name": "Copy"}),
            ("delete_fit", {"fit_id": self.sample, "resolve_references": True})):
            with patch.object(GraphStore, "_commit", side_effect=OSError("Injected disk failure")):
                self.send(operation, args, "ENGINE_ERROR")
            self.assertEqual(self.current(), before)
            self.assertEqual(self.path.read_bytes(), disk)
            self.assertEqual(self.bridge.sample_id, self.sample)
            self.assertEqual(len(ENGINE._fits), 1)
        self.assertEqual(self.reopen()["bootstrap"]["fits"], before)

    def test_failed_linked_delete_restores_all_recipients(self):
        source = self.create("projection", "source")
        self.send("add_projection", {"source_id": source, "target_id": self.sample,
            "range_m": 0, "active": True, "amount": 1})
        before = self.current()
        with patch.object(GraphStore, "_commit", side_effect=OSError("Injected disk failure")):
            self.delete(source, "ENGINE_ERROR")
        self.assertEqual(self.current(), before)
        self.assertEqual(self.reopen()["bootstrap"]["fits"], before)

    def test_confirmed_last_delete_survives_lost_write_ack(self):
        original = GraphStore._commit
        def commit_then_raise(connection):
            original(connection)
            raise OSError("Committed, acknowledgement lost")
        with patch.object(GraphStore, "_commit", side_effect=commit_then_raise):
            self.assertEqual(self.delete(self.sample), [])
        self.assertEqual(self.reopen()["bootstrap"]["fits"], [])
