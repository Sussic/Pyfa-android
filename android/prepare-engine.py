"""Generate bundled game data and stage the existing engine, never golden values.

Run using tools/android_headless/requirements.txt and Python 3.11. The game-data
source and resulting logical database must match A01's independent desktop case.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT, bootstrap, canonical,
    compare, digest_file, logical_database_digest, source_data_digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-database", type=Path)
    args = parser.parse_args()
    if args.build_database:
        bootstrap(ROOT, args.build_database)
        import db_update
        db_update.DB_PATH = str(args.build_database)
        db_update.update_db()
        return
    if sys.version_info[:2] != (3, 11):
        raise ValueError("Prepare the engine with Python 3.11")
    golden_path = ROOT / "tools/android_reference/fixtures/vexor.json"
    golden = json.loads(golden_path.read_text())
    projection_path = ROOT / "tools/android_reference/fixtures/projection.json"
    projection = json.loads(projection_path.read_text())
    for key in ("source_commit", "source_data_sha256", "database_logical_sha256", "dataset_metadata"):
        compare(golden[key], projection[key], "projection." + key)
    projection_input = ROOT / "tools/android_reference/projection.json"
    compare(projection["inputs"], json.loads(projection_input.read_text()), "projection.inputs")
    command_path = ROOT / "tools/android_reference/fixtures/command.json"
    command = json.loads(command_path.read_text())
    for key in ("source_commit", "source_data_sha256", "database_logical_sha256", "dataset_metadata"):
        compare(golden[key], command[key], "command." + key)
    command_input = ROOT / "tools/android_reference/command.json"
    compare(command["inputs"], json.loads(command_input.read_text()), "command.inputs")
    compare(SOURCE_COMMIT, golden["source_commit"], "desktop_source")
    data_digest = source_data_digest(ROOT)
    compare(golden["source_data_sha256"], data_digest, "pinned_source_data")
    out = ROOT / "android/build/engine"
    out.mkdir(parents=True, exist_ok=True)
    assets = out / "assets/engine"
    assets.mkdir(parents=True, exist_ok=True)
    database = assets / "eve.db"
    # Reuse only after full identity/integrity verification, including failed or
    # interrupted builds. Never rely on metadata alone.
    try:
        valid = logical_database_digest(database) == golden["database_logical_sha256"]
    except Exception:
        valid = False
    if not valid:
        subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()),
                        "--build-database", str(database)], check=True)
    compare(golden["database_logical_sha256"], logical_database_digest(database), "bundled_database")
    python = out / "python"
    if python.exists():
        shutil.rmtree(python)
    manifest = {}
    for package in ("eos", "utils", "android_bridge"):
        for path in sorted((ROOT / package).rglob("*")):
            if path.suffix != ".py" and path.name != "lgpl.txt":
                continue
            relative = path.relative_to(ROOT)
            target = python / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            target.write_bytes(raw)
            manifest[relative.as_posix()] = hashlib.sha256(raw).hexdigest()
    shutil.copyfile(ROOT / "tools/android_reference/vexor.json", assets / "vexor.json")
    shutil.copyfile(projection_input, assets / "projection.json")
    shutil.copyfile(command_input, assets / "command.json")
    info = {"desktop_source_commit": SOURCE_COMMIT, "source_data_sha256": data_digest,
            "database_logical_sha256": golden["database_logical_sha256"],
            "database_sha256": digest_file(database), "database_bytes": database.stat().st_size,
            "dataset_metadata": golden["dataset_metadata"],
            "engine_source_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
            "engine_sources": manifest,
            "desktop_fixture_sha256": digest_file(golden_path),
            "projection_fixture_sha256": digest_file(projection_path),
            "command_fixture_sha256": digest_file(command_path)}
    (assets / "manifest.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    # Expected results belong only to the instrumentation APK, never production
    # Python or the sample's calculation path.
    tests = out / "testAssets"
    tests.mkdir(exist_ok=True)
    shutil.copyfile(golden_path, tests / "vexor-expected.json")
    shutil.copyfile(projection_path, tests / "projection-expected.json")
    shutil.copyfile(command_path, tests / "command-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/catalog.json", tests / "catalog-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/equipment.json", tests / "equipment-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/empty-hulls.json", tests / "empty-hulls-expected.json")
    print(json.dumps({k: v for k, v in info.items() if k != "engine_sources"}, indent=2))


if __name__ == "__main__":
    main()
