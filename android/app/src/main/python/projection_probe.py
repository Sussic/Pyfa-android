"""Native A08 operations and observations, with no golden values or formulas.

The instrumentation APK owns all comparisons to the independent desktop fixture.
Do not manually refresh recipients here: the adapter/EOS must invalidate them.
"""


def run(engine, case):
    source = engine.create_fit(case["source"])
    target = engine.create_fit(case["target"])
    other = engine.create_fit(case["target"])
    unlinked = engine.create_fit(case["target"])
    targets = {"first": target, "second": other, "unlinked": unlinked}

    def pair():
        return {"source": engine.projection_snapshot(source),
                "target": engine.projection_snapshot(target)}

    def links():
        return {
            "source_count": len(source.projectedOnto),
            "recipients": {name: {
                "count": len(fit.projectedFitDict),
                "forward": fit.projectedFitDict.get(source.ID) is source,
                "reverse": fit.ID in source.projectedOnto,
            } for name, fit in targets.items()},
        }

    def recipients():
        # Read the second recipient first, before the first recipient or source.
        # Reading one must not consume invalidation needed by another.
        result = {name: engine.projection_snapshot(targets[name])
                  for name in ("second", "first", "unlinked")}
        result["links"] = links()
        return result

    try:
        states = {"initial": pair()}
        for step in case["steps"]:
            op = step["operation"]
            if op in ("add", "configure"):
                method = engine.add_projection if op == "add" else engine.configure_projection
                method(source, target, range_m=step["range_m"], active=step["active"], amount=step["amount"])
            elif op == "charges":
                engine.set_charges(source, step["module_indices"], step["charge"])
            elif op == "remove":
                engine.remove_projection(source, target)
            else:
                raise ValueError("Unknown projection operation")
            states[step["name"]] = pair()
        scenario_links = links()

        multi = {"initial": recipients()}
        for fit in (target, other):
            engine.add_projection(source, fit)
        multi["applied"] = recipients()
        engine.configure_projection(source, target, range_m=300000.0, active=True, amount=1)
        multi["first_distant"] = recipients()
        engine.configure_projection(source, target, range_m=0, active=False, amount=1)
        multi["first_disabled"] = recipients()
        engine.configure_projection(source, target, range_m=0, active=True, amount=1)
        multi["first_reactivated"] = recipients()
        script_edit = next(step for step in case["steps"] if step["name"] == "script_changed")
        engine.set_charges(source, script_edit["module_indices"], script_edit["charge"])
        multi["script_changed"] = recipients()
        engine.remove_projection(source, target)
        multi["first_removed"] = recipients()
        script_restore = next(step for step in case["steps"] if step["name"] == "script_restored")
        engine.set_charges(source, script_restore["module_indices"], script_restore["charge"])
        multi["script_restored"] = recipients()
        engine.remove_projection(source, other)
        multi["removed"] = recipients()

        cycles = []
        for _ in range(5):
            engine.add_projection(source, target)
            applied = {"stats": pair(), "links": links()}
            engine.remove_projection(source, target)
            cycles.append({"applied": applied, "removed": {"stats": pair(), "links": links()}})
        return {"states": states, "scenario_links": scenario_links,
                "multi_recipient": multi, "repeated_cycles": cycles}
    finally:
        # Leave no links behind, including if a calculation/serialization fails.
        for fit in targets.values():
            if source.ID in fit.projectedFitDict:
                engine.remove_projection(source, fit)
