"""Native A09 operations and observations, with no golden values or formulas.

The instrumentation APK owns all comparisons to the independent desktop fixture.
Do not manually refresh recipients here: the adapter/EOS must invalidate them.
"""


def run(engine, case):
    source = engine.create_fit(case["source"])
    target = engine.create_fit(case["target"])
    other = engine.create_fit(case["target"])
    unlinked = engine.create_fit(case["target"])
    targets = {"first": target, "second": other, "unlinked": unlinked}
    steps = {step["name"]: step for step in case["steps"]}
    pending = {}

    def snapshot(fit, path):
        values = engine.projection_snapshot(fit)
        pending[path] = len(fit.commandBonuses)
        return values

    def pair(path):
        return {"source": snapshot(source, path + ".source"),
                "target": snapshot(target, path + ".target")}

    def links():
        return {
            "source_count": len(source.boostedOnto),
            "recipients": {name: {
                "count": len(fit.commandFitDict),
                "forward": fit.commandFitDict.get(source.ID) is source,
                "reverse": fit.ID in source.boostedOnto,
            } for name, fit in targets.items()},
        }

    def recipients(phase):
        # Reading one must not consume invalidation needed by another recipient.
        result = {name: snapshot(targets[name], "multi_recipient." + phase + "." + name)
                  for name in ("second", "first", "unlinked")}
        result["links"] = links()
        return result

    def apply(step, recipient=target):
        op = step["operation"]
        if op == "add":
            engine.add_command(source, recipient)
        elif op == "command_state":
            engine.set_command_active(source, recipient, step["active"])
        elif op == "skill":
            engine.set_skill_level(source, step["skill"], step["level"])
        elif op == "implant_add":
            engine.add_implant(source, step["implant"])
        elif op == "implant_state":
            engine.set_implant_active(source, step["slot"], step["active"])
        elif op == "implant_remove":
            engine.remove_implant(source, step["slot"])
        elif op == "module_state":
            engine.set_module_states(source, step["module_indices"], step["state"])
        elif op == "charges":
            engine.set_charges(source, step["module_indices"], step["charge"])
        elif op == "remove":
            engine.remove_command(source, recipient)
        else:
            raise ValueError("Unknown command operation")

    try:
        states = {"initial": pair("states.initial")}
        for step in case["steps"]:
            apply(step)
            states[step["name"]] = pair("states." + step["name"])
        scenario_links = links()

        multi = {"initial": recipients("initial")}
        for fit in (target, other):
            apply(steps["applied"], fit)
        multi["applied"] = recipients("applied")
        for name in ("specialist_4", "specialist_restored", "command_ships_4",
                     "command_ships_restored", "mindlink_added", "mindlink_inactive",
                     "mindlink_active", "burst_online", "burst_active"):
            apply(steps[name])
            multi[name] = recipients(name)
        apply(steps["link_inactive"])
        multi["first_disabled"] = recipients("first_disabled")
        apply(steps["link_active"])
        multi["first_reactivated"] = recipients("first_reactivated")
        apply(steps["harmonizing"])
        multi["harmonizing"] = recipients("harmonizing")
        apply(steps["removed"])
        multi["first_removed"] = recipients("first_removed")
        for name in ("extension_restored", "mindlink_removed"):
            apply(steps[name])
            multi[name] = recipients(name)
        apply(steps["removed"], other)
        multi["removed"] = recipients("removed")

        cycles = []
        for index in range(5):
            path = "repeated_cycles." + str(index)
            apply(steps["applied"])
            applied = {"stats": pair(path + ".applied"), "links": links()}
            apply(steps["removed"])
            cycles.append({"applied": applied,
                           "removed": {"stats": pair(path + ".removed"), "links": links()}})
        return {"states": states, "scenario_links": scenario_links,
                "multi_recipient": multi, "repeated_cycles": cycles,
                "pending_command_bonuses": pending}
    finally:
        # Leave no links behind, including if a calculation/serialization fails.
        for fit in targets.values():
            if source.ID in fit.commandFitDict:
                engine.remove_command(source, fit)
