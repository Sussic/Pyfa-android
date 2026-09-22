"""Export B03.2 hull organization from the unmodified pinned desktop Market."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (
    SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare, digest_file,
    logical_database_digest, validate_source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    args.source, args.database, args.output = args.source.resolve(), args.database.resolve(strict=True), args.output.resolve()
    validate_source(args.source)
    compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
    if args.worker:
        bootstrap(args.source, args.database)
        import config
        config.pyfaPath = str(args.source)
        # config.savePath stays None: desktop settings stay in memory.
        from service.market import Market
        market = Market.getInstance()
        groups, hulls = [], []
        for group in market.getShipRoot():
            groups.append({"id": group.ID, "name": group.displayName})
            for hull in market.getShipList(group.ID):
                hulls.append({"id": hull.ID, "name": hull.name, "group_id": group.ID, "race": hull.race})
        result = {"version": 1, "groups": sorted(groups, key=lambda row: row["name"]),
                  "hulls": sorted(hulls, key=lambda row: row["id"])}
        assert not any(name.startswith("android_bridge") for name in sys.modules)
        for name, module in list(sys.modules.items()):
            if name.split(".")[0] in ("eos", "service", "config") and getattr(module, "__file__", None):
                assert Path(module.__file__).resolve().is_relative_to(args.source), name
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return
    if args.output.is_relative_to(ROOT) or args.database.is_relative_to(args.output):
        raise ValueError("Use a new output outside the checkout and input database")
    baseline = json.loads((ROOT / "tools/android_reference/fixtures/vexor.json").read_text())
    compare(baseline["database_logical_sha256"], logical_database_digest(args.database))
    before = digest_file(args.database)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ("catalog", "repeat"):
        with (args.output / (name + ".log")).open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--source", str(args.source),
                "--database", str(args.database), "--output", str(args.output / (name + ".json")), "--worker"],
                cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    actual = json.loads((args.output / "catalog.json").read_text())
    compare(actual, json.loads((args.output / "repeat.json").read_text()))
    if args.check:
        compare(json.loads(args.check.read_text()), actual)
    compare(before, digest_file(args.database))
    validate_source(args.source)
    (args.output / "evidence.json").write_text(json.dumps({"task": "B03.2", "source_commit": SOURCE_COMMIT,
        "database_logical_sha256": baseline["database_logical_sha256"], "fresh_process_repeat": True,
        "catalog_sha256": digest_file(args.output / "catalog.json"),
        "groups": len(actual["groups"]), "hulls": len(actual["hulls"])}, indent=2) + "\n")
    print("PASS: pinned desktop hull catalogue and fresh-process repeat")


if __name__ == "__main__":
    main()
