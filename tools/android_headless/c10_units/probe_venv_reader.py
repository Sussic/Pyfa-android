"""Metadata-only Windows venv reader route qualification; no EOS/project imports.

Run under unchanged existing9bf canonical light guard, forecast0, total60s.
Use a fresh output outside source/EOS189 and bind both work-file hashes.
Raw JSON files, not JavaScript/chat projections, preserve integer FILETIMEs.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback
from uuid import uuid4


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def load_helper(args):
    require(sha(Path(__file__)) == args.probe_sha256, "Probe work-file hash differs")
    require(sha(args.helper) == args.helper_sha256, "Helper work-file hash differs")
    spec = importlib.util.spec_from_file_location("_reader_metadata_windows", args.helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def child_mode(args, windows):
    require(args.child_state_sha256 and sha(args.child_state) == args.child_state_sha256, "Exact child input SHA differs")
    state = json.loads(args.child_state.read_text(encoding="utf-8"))
    writer = state["writer_identity"]
    identity = windows.current_identity()
    require(identity["pid"] != writer["pid"] and identity["parent_pid"] == writer["pid"], "Reader is not writer's direct child")
    require(identity["creation_filetime"] > writer["creation_filetime"], "Reader process is not new")
    require(identity["runtime"] == writer["runtime"], "Reader lost the qualified venv/runtime")
    with windows.Process(writer["pid"]) as live_writer:
        before = live_writer.snapshot()
        windows.same_process(before, writer)
        # Recheck real metadata while the exact writer process handle is retained.
        require(windows.runtime_snapshot() == writer["runtime"], "Reader runtime changed during metadata operation")
        after = live_writer.snapshot()
        windows.same_process(after, writer)
    require(sha(args.child_state) == args.child_state_sha256, "Child input changed")
    require(sha(args.helper) == args.helper_sha256 and sha(Path(__file__)) == args.probe_sha256, "Work files changed")
    result = {"schema_version": 1, "status": "PASS_METADATA_DIRECT_READER", "scope": "No EOS/project imports",
              "identity": identity, "nonce": state["nonce"], "input_sha256": args.child_state_sha256,
              "writer_handle_observations": {"before": before, "after": after},
              "writer_alive_parent": True, "writer_process_death_claim": False}
    write(args.output / "CHILD.json", result)
    return result


def parent_mode(args, windows):
    require(not args.output.exists(), "Fresh metadata output is required; preserve existing paths")
    root = Path("C:/Users/HallT/Documents/Codex/Execution/MSI/pyfa/results").resolve()
    require(args.output.is_relative_to(root) and args.output != root, "Metadata output must be inside canonical MSI results")
    require("c10-units-eos-both" not in str(args.output).casefold(), "Do not touch EOS189 output namespace")
    identity = windows.current_identity()
    identity["launch_parent"] = windows.launcher_parent(identity)
    args.output.mkdir(parents=True, exist_ok=False)
    state = {"writer_identity": identity, "nonce": uuid4().hex, "probe_sha256": args.probe_sha256,
             "helper_sha256": args.helper_sha256}
    state_path = args.output / "INPUT.json"
    write(state_path, state)
    state_sha = sha(state_path)
    command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
               "--helper", str(args.helper), "--helper-sha256", args.helper_sha256,
               "--probe-sha256", args.probe_sha256, "--output", str(args.output),
               "--child-state", str(state_path), "--child-state-sha256", state_sha]
    command, environment = windows.direct_venv_command(command)
    child = None
    result = {"schema_version": 1, "status": "FAILED", "scope": "Metadata route only; no EOS/product/native acceptance",
              "identity": identity, "input_sha256": state_sha, "nonce": state["nonce"],
              "source_file_sha256": {"probe": args.probe_sha256, "helper": args.helper_sha256},
              "job_membership_scope": "in_any_job corroborates only; unchanged nonbreakaway outer guard and normal CreateProcess retain containment",
              "parent_guard_closure": "Pending actual canonical policy-result; child cannot attest its own guard closure",
              "EOS_acceptance": False, "Android_acceptance": False, "writer_process_death_claim": False}
    try:
        with (args.output / "child.stdout.log").open("xb") as stdout, (args.output / "child.stderr.log").open("xb") as stderr:
            child = subprocess.Popen(command, cwd=Path.cwd(), env=environment, stdout=stdout, stderr=stderr,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            child_creation = windows.creation_time(int(child._handle))
            exit_code = child.wait(timeout=20)
        require(exit_code == 0, "Metadata reader failed; retain child JSON/logs")
        reader_path = args.output / "CHILD.json"
        reader = json.loads(reader_path.read_text(encoding="utf-8"))
        require(reader["status"] == "PASS_METADATA_DIRECT_READER", "Metadata child did not pass")
        require(reader["identity"]["pid"] == child.pid, "Actual reader PID differs from exact Popen PID")
        require(reader["identity"]["creation_filetime"] == child_creation, "Actual reader birth differs from retained Popen handle")
        require(reader["identity"]["parent_pid"] == identity["pid"] and reader["nonce"] == state["nonce"],
                "Reader lineage/nonce differs")
        require(reader["input_sha256"] == state_sha and sha(state_path) == state_sha, "Exact metadata state changed")
        require(reader["identity"]["runtime"] == identity["runtime"], "Qualified runtime differs")
        require(sha(args.helper) == args.helper_sha256 and sha(Path(__file__)) == args.probe_sha256, "Work files changed")
        result.update(status="PASS_METADATA_DIRECT_VENV_READER", child=reader, child_file_sha256=sha(reader_path),
                      spawned_reader_pid=child.pid, spawned_reader_creation_filetime=child_creation, inputs_unchanged=True)
    except Exception as error:
        result.update(error=type(error).__name__ + ": " + str(error), traceback=traceback.format_exc())
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        write(args.output / "RESULT.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--helper-sha256", required=True)
    parser.add_argument("--probe-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--child-state", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--child-state-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.helper, args.output = args.helper.resolve(strict=True), args.output.resolve()
    require(socket.gethostname().casefold() == "msi", "Qualified MSI host is required")
    require(not any(name.split(".")[0] in {"android_bridge", "eos", "utils", "wx", "gui", "service", "config"}
                    for name in sys.modules), "Fresh metadata-only process required")
    windows = load_helper(args)
    result = child_mode(args, windows) if args.child_state else parent_mode(args, windows)
    print(json.dumps({"status": result["status"], "output": str(args.output)}), flush=True)
    return 0 if result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())

