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



def require_private_database(path):
    """Regeneration must never write through links into a shared cache."""
    path = path.absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Database regeneration refuses symbolic links: " + str(part))
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError("Database regeneration requires a private regular file")


def verify_reused_database(database, cache, expected_sha, expected_bytes, logical_sha):
    """Fail closed: no bootstrap or regeneration is reachable from this function.

    The caller supplies a trusted earlier receipt, and guarantees no concurrent
    cache writers. Existing file permissions are never changed.
    """
    cache = cache.absolute()
    # An explicit physical cache path, never an alias or an external-root escape.
    approved_root = Path("/workspace/shared")
    if cache != cache.resolve(strict=True) or not cache.is_relative_to(approved_root):
        raise ValueError("Reuse cache must be a physical file within /workspace/shared")
    if not cache.is_file() or cache.stat().st_nlink != 1:
        raise ValueError("Reuse cache must be an unshared regular file")
    if not database.is_symlink() or database.resolve(strict=True) != cache:
        raise ValueError("Bundled database must link to the exact approved cache")
    for path in (cache, database):
        for suffix in ("-wal", "-shm", "-journal"):
            if Path(str(path) + suffix).exists():
                raise ValueError("Reuse cache has pending SQLite sidecars")
    if not expected_sha or len(expected_sha) != 64 or expected_bytes is None or expected_bytes <= 0:
        raise ValueError("Reuse requires trusted physical SHA-256 and byte count")
    before = (cache.stat().st_size, digest_file(cache))
    if before != (expected_bytes, expected_sha):
        raise ValueError("Reuse cache physical identity mismatch")
    compare(logical_sha, logical_database_digest(cache), "reuse_database")
    if (cache.stat().st_size, digest_file(cache)) != before:
        raise ValueError("Reuse cache changed during verification")


def prepare_database(database, logical_sha, reuse_cache=None, expected_sha=None, expected_bytes=None):
    if reuse_cache is not None:
        verify_reused_database(database, reuse_cache, expected_sha, expected_bytes, logical_sha)
        return
    # Guard before even inspecting a shared destination: the normal command must
    # not silently accept a link and later acquire a regeneration write path.
    require_private_database(database)
    try:
        valid = logical_database_digest(database) == logical_sha
    except Exception:
        valid = False
    if not valid:
        require_private_database(database)
        subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()),
                        "--build-database", str(database)], check=True)
    compare(logical_sha, logical_database_digest(database), "bundled_database")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--build-database", type=Path)
    modes.add_argument("--reuse-only-database", type=Path)
    parser.add_argument("--reuse-sha256")
    parser.add_argument("--reuse-bytes", type=int)
    args = parser.parse_args()
    if not args.reuse_only_database and (args.reuse_sha256 is not None or args.reuse_bytes is not None):
        parser.error("Reuse identity arguments require --reuse-only-database")
    if args.build_database:
        require_private_database(args.build_database)
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
    prepare_database(database, golden["database_logical_sha256"],
                     args.reuse_only_database, args.reuse_sha256, args.reuse_bytes)
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
    for family in ("drone-details", "drone-core-edits", "drone-acceptance", "drone-conservation"):
        shutil.copyfile(ROOT / f"tools/android_reference/fixtures/{family}.json", tests / f"{family}-expected.json")
    shutil.copyfile(projection_path, tests / "projection-expected.json")
    shutil.copyfile(command_path, tests / "command-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/catalog.json", tests / "catalog-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/equipment.json", tests / "equipment-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/empty-hulls.json", tests / "empty-hulls-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/module-edits.json", tests / "module-edits-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/charge-edits.json", tests / "charge-edits-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/variation-edits.json", tests / "variation-edits-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/rack-ordering.json", tests / "rack-ordering-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/bulk-charges.json", tests / "bulk-charges-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/bulk-states.json", tests / "bulk-states-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/cargo-actions.json", tests / "cargo-actions-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/cargo-transfers.json", tests / "cargo-transfers-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/notes.json", tests / "notes-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/history.json", tests / "history-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/history-mutations.json", tests / "history-mutations-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/resources.json", tests / "resources-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/resources-edited.json", tests / "resources-edited-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/capacitor.json", tests / "capacitor-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/defenses.json", tests / "defenses-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/tank.json", tests / "tank-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/output.json", tests / "output-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/targeting.json", tests / "targeting-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/inspector-attributes.json", tests / "inspector-attributes-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/inspector-metadata.json", tests / "inspector-metadata-expected.json")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/inspector-affectors.json", tests / "inspector-affectors-expected.json")
    for family in ("units", "properties", "projection", "command", "equipment-paths", "equipment-probes", "guard-domains", "effect-catalog", "identities", "sorting", "text"):
        shutil.copyfile(ROOT / f"tools/android_reference/fixtures/inspector-{family}.json", tests / f"inspector-{family}-expected.json")
    # Android's asset merge expands *.gz and removes the suffix. Preserve the
    # compressed bytes under a binary filename for explicit bounded streaming.
    (tests / "inspector-contexts-expected.json.gz").unlink(missing_ok=True)
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/inspector-contexts.json.gz", tests / "inspector-contexts-expected.bin")
    shutil.copyfile(ROOT / "tools/android_reference/fixtures/inspector-context-metadata.json", tests / "inspector-context-metadata-expected.json")
    print(json.dumps({k: v for k, v in info.items() if k != "engine_sources"}, indent=2))


if __name__ == "__main__":
    main()
