#!/usr/bin/env python3
"""Enumerate C03.2's pinned data and every original equipment presentation path.

This inventory reads the independent desktop checkout and SQLite data only. It
does not import the Android adapter or supply calculated expected results.
"""

import argparse
import ast
import importlib.util
import json
from pathlib import Path
import sqlite3


def source_paths(path, method):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                 and node.name == method]
    if len(functions) != 1:
        raise ValueError(f"Expected exactly one {method} in {path}")
    paths = []

    def visit(nodes, guards):
        for node in nodes:
            if isinstance(node, ast.If):
                condition = ast.unparse(node.test)
                visit(node.body, guards + [condition])
                visit(node.orelse, guards + ["not (" + condition + ")"])
            elif isinstance(node, ast.Return):
                paths.append({"line": node.lineno, "conditions": guards,
                              "result": ast.unparse(node.value) if node.value else "None"})
            else:
                # Include returns inside loops/try blocks, preserving their
                # structural context instead of silently dropping subfamilies.
                for field in ("body", "orelse", "finalbody"):
                    children = getattr(node, field, None)
                    if children:
                        visit(children, guards + [type(node).__name__])
                for handler in getattr(node, "handlers", []):
                    visit(handler.body, guards + ["except " + ast.unparse(handler.type)])

    visit(functions[0].body, [])
    expected = sum(isinstance(node, ast.Return) for node in ast.walk(functions[0]))
    if len(paths) != expected:
        raise ValueError(f"Incomplete return-path inventory for {method}")
    calls = sorted({ast.unparse(node) for node in ast.walk(functions[0])
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr.startswith(("getModified", "getRemote", "getMining",
                                                  "getDamage", "getCycle", "getSpool"))})
    return {"method": method, "returnPaths": paths, "engineCalls": calls,
            "conditions": [{"line": node.lineno, "expression": ast.unparse(node.test)}
                           for node in ast.walk(functions[0]) if isinstance(node, ast.If)]}


def inventory(source, database):
    spec = importlib.util.spec_from_file_location("reference", Path(__file__).with_name("reference.py"))
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    reference.validate_source(source)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        attributes = db.execute("SELECT attributeID,attributeName,unitID,published FROM dgmattribs ORDER BY attributeID").fetchall()
        effects = db.execute("SELECT effectID,effectName,published FROM dgmeffects ORDER BY effectID").fetchall()
        units = db.execute("SELECT unitID,unitName,displayName FROM dgmunits ORDER BY unitID").fetchall()
        assigned_attributes = [r[0] for r in db.execute("SELECT DISTINCT attributeID FROM dgmtypeattribs ORDER BY attributeID")]
        assigned_effects = [r[0] for r in db.execute("SELECT DISTINCT effectID FROM dgmtypeeffects ORDER BY effectID")]
        groups = db.execute("SELECT g.groupID,g.name,c.name,count(t.typeID) FROM invgroups g JOIN invcategories c ON c.categoryID=g.categoryID LEFT JOIN invtypes t ON t.groupID=g.groupID GROUP BY g.groupID ORDER BY g.groupID").fetchall()
    attribute_ids = {r[0] for r in attributes}
    effect_ids = {r[0] for r in effects}
    if not set(assigned_attributes) <= attribute_ids or not set(assigned_effects) <= effect_ids:
        raise ValueError("Assigned metadata ID missing from full catalogue")
    columns = {}
    for filename, method in (("misc.py", "__getData"), ("maxRange.py", "getToolTip"),
                             ("maxRange.py", "getText"), ("capacitorUse.py", "getText"),
                             ("capacitorUse.py", "getToolTip"), ("attributeDisplay.py", "getText"),
                             ("propertyDisplay.py", "getText")):
        columns[filename + ":" + method] = source_paths(source / "gui/builtinViewColumns" / filename, method)
    properties = {}
    for relative in ("eos/gamedata.py", "eos/saveddata/ship.py", "eos/saveddata/module.py",
                     "eos/saveddata/drone.py", "eos/saveddata/fighter.py", "eos/saveddata/implant.py",
                     "eos/saveddata/booster.py", "eos/saveddata/cargo.py", "eos/saveddata/mode.py"):
        path = source / relative
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        properties[relative] = [{"class": cls.name, "members": sorted({
            node.name for node in cls.body if isinstance(node, ast.FunctionDef)
            and any(isinstance(d, ast.Name) and d.id == "property" for d in node.decorator_list)})}
            for cls in tree.body if isinstance(cls, ast.ClassDef)]
    return {"schema": 1, "sourceCommit": reference.SOURCE_COMMIT,
            "databaseLogicalSha256": reference.logical_database_digest(database),
            "counts": {"attributes": len(attributes), "assignedAttributes": len(assigned_attributes),
                       "effects": len(effects), "assignedEffects": len(assigned_effects),
                       "units": len(units), "groups": len(groups),
                       "equipmentReturnPaths": sum(len(c["returnPaths"]) for c in columns.values())},
            "attributes": attributes, "assignedAttributeIds": assigned_attributes,
            "effects": effects, "assignedEffectIds": assigned_effects, "units": units,
            "groups": groups, "equipmentColumns": columns, "declaredProperties": properties}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--identity-check", type=Path)
    args = parser.parse_args()
    result = inventory(args.source.resolve(), args.database.resolve())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], sort_keys=True))
    if args.identity_check is not None:
        spec=importlib.util.spec_from_file_location('original_inspector_identity_inventory',Path(__file__).with_name('inspector_identity_inventory.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        expected=json.loads(args.identity_check.read_text(encoding='utf-8'))
        actual=module.inventory(args.source,args.database)
        if actual!=expected:raise AssertionError('Original complete mode identity inventory differs')
        print('PASS original complete mode identity inventory')


if __name__ == "__main__":
    main()
