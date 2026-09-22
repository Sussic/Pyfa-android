"""Export the complete B04.1 catalogue and execute real desktop Market searches."""
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
        configuration = bootstrap(args.source, args.database)
        # Match config.init's desktop query-cache setting before importing EOS.
        # Its search worker supplies list tokens; the provisional EOS default
        # cache cannot hash these. No desktop method is patched or substituted.
        configuration.gamedataCache = False
        import config
        config.pyfaPath = str(args.source)
        # config.savePath stays None: desktop settings stay in memory.
        from service.market import Market
        market = Market.getInstance()
        import wx
        import time
        import eos.db
        app = wx.App(False)
        groups, all_items, searchable = {}, {}, set()
        for category in market.SEARCH_CATEGORIES:
            for item in eos.db.getItemsByCategory(category):
                if market.getPublicityByItem(item):
                    all_items[item.ID] = item
                    searchable.add(item.ID)
        for group_name in market.SEARCH_GROUPS:
            for item in market.getGroup(group_name).items:
                if market.getPublicityByItem(item):
                    all_items[item.ID] = item
                    searchable.add(item.ID)
        pending = [(group, None) for group in market.getMarketRoot()]
        while pending:
            group, parent = pending.pop()
            children = market.getMarketGroupChildren(group)
            leaf = market.marketGroupHasTypesCheck(group)
            members = market.getItemsByMarketGroup(group) if leaf else set()
            groups[group.ID] = {"id": group.ID, "name": group.name, "parent_id": parent,
                "item_ids": sorted(item.ID for item in members)}
            all_items.update((item.ID, item) for item in members)
            if not leaf:
                pending.extend((child, group.ID) for child in children if market.marketGroupValidityCheck(child))
        items = []
        for item in all_items.values():
            meta = market.getMetaGroupIdByItem(item)
            group = market.getMarketGroupByItem(item)
            items.append({"id": item.ID, "name": item.name, "category": item.category.name,
                "meta_id": meta, "meta": market.META_MAP_REVERSE[meta].title(),
                "parent_id": market.getParentItemByItem(item).ID,
                "market_group_id": group.ID if group is not None else None,
                "searchable": item.ID in searchable})
        searches = {}
        while not hasattr(market.searchWorkerThread, 'cv'):
            time.sleep(0.01)
        for query in json.loads((ROOT / 'tools/android_reference/equipment-queries.json').read_text()):
            received = []
            market.searchItems(query, lambda ids: received.append(ids), 'market')
            deadline = time.monotonic() + 30
            while not received:
                app.Yield()
                if time.monotonic() > deadline:
                    raise TimeoutError(query)
                time.sleep(0.01)
            searches[query] = received[0]
        result = {"catalog": {"version": 1, "roots": sorted(group.ID for group in market.getMarketRoot()),
                  "groups": sorted(groups.values(), key=lambda row: row["id"]),
                  "items": sorted(items, key=lambda row: row["id"])}, "searches": searches}
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
    (args.output / "evidence.json").write_text(json.dumps({"task": "B04.1", "source_commit": SOURCE_COMMIT,
        "database_logical_sha256": baseline["database_logical_sha256"], "fresh_process_repeat": True,
        "gamedata_cache": False, "search_execution": "unmodified Market worker with wx event dispatch",
        "catalog_sha256": digest_file(args.output / "catalog.json"),
        "groups": len(actual["catalog"]["groups"]), "items": len(actual["catalog"]["items"]), "searches": len(actual["searches"])}, indent=2) + "\n")
    print("PASS: pinned desktop equipment catalogue/searches and fresh-process repeat")


if __name__ == "__main__":
    main()
