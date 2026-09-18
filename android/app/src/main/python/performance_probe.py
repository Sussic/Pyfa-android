"""Persistent A10 benchmark fits; EOS supplies every observed statistic.

Preparation is outside measured edits. Each edit reuses its fits and returns a
complete snapshot for independent native comparisons outside the timed region.
"""


class PerformanceProbe:
    def __init__(self, engine, ammunition_fit):
        self.engine = engine
        self.ammunition_fit = ammunition_fit
        self.prepared = {}

    def prepare(self, kind, case):
        if kind not in ("ammunition", "projection", "command"):
            raise ValueError("Unknown benchmark kind")
        if kind in self.prepared:
            raise ValueError("Benchmark kind is already prepared")
        state = {"case": case}
        if kind == "ammunition":
            self.engine.set_charges(self.ammunition_fit, case["edit"]["module_indices"],
                                    case["modules"][0]["charge"])
            state.update(stage="initial", changed=False)
        else:
            state["fits"] = {
                "source": self.engine.create_fit(case["source"]),
                **{name: self.engine.create_fit(case["target"])
                   for name in ("first", "second", "unlinked")},
            }
            state["steps"] = {step["name"]: step for step in case["steps"]}
            state.update(linked=True, changed=False)
            if kind == "command":
                # A05's Harmonizing fixture includes this active mindlink.
                # Use the same source for both charges, without implant churn.
                self.engine.add_implant(state["fits"]["source"],
                                        state["steps"]["mindlink_added"]["implant"])
                state["stage"] = "mindlink_added"
            else:
                state["stage"] = "applied_zero"
            self._links(kind, state, add=True)
        self.prepared[kind] = state
        return self._snapshot(kind, state)

    def step(self, operation):
        kinds = {"ammunition": "ammunition", "projection_range": "projection",
                 "projection_link": "projection", "command_charge": "command",
                 "command_link": "command"}
        if operation not in kinds:
            raise ValueError("Unknown benchmark operation")
        kind = kinds[operation]
        if kind not in self.prepared:
            raise ValueError("Prepare the benchmark kind before editing")
        state = self.prepared[kind]
        if operation == "ammunition":
            changed = not state["changed"]
            case = state["case"]
            charge = case["edit"]["charge"] if changed else case["modules"][0]["charge"]
            self.engine.set_charges(self.ammunition_fit, case["edit"]["module_indices"], charge)
            state.update(changed=changed, stage="iron_ammunition" if changed else "restored")
        elif operation in ("projection_range", "command_charge"):
            if not state["linked"]:
                raise ValueError("Reapply benchmark links before changing the source or range")
            changed = not state["changed"]
            if kind == "projection":
                stage = "falloff" if changed else "applied_zero"
                spec = state["steps"][stage]
                for name in ("first", "second"):
                    self.engine.configure_projection(state["fits"]["source"], state["fits"][name],
                                                     range_m=spec["range_m"], active=spec["active"],
                                                     amount=spec["amount"])
            else:
                stage = "harmonizing" if changed else "extension_restored"
                spec = state["steps"][stage]
                self.engine.set_charges(state["fits"]["source"], spec["module_indices"], spec["charge"])
            state.update(changed=changed, stage=stage)
        else:
            if state["changed"]:
                raise ValueError("Restore the initial range or charge before benchmarking links")
            linked = not state["linked"]
            self._links(kind, state, add=linked)
            # A05's disabled-link values also describe fully removed links;
            # relationship observations below independently prove removal.
            stages = ("applied_zero", "removed") if kind == "projection" else ("link_active", "link_inactive")
            state.update(linked=linked, stage=stages[0] if linked else stages[1])
        return self._snapshot(kind, state)

    def _links(self, kind, state, add):
        source = state["fits"]["source"]
        for name in ("first", "second"):
            target = state["fits"][name]
            if kind == "projection":
                if add:
                    spec = state["steps"]["applied_zero"]
                    self.engine.add_projection(source, target, range_m=spec["range_m"],
                                               active=spec["active"], amount=spec["amount"])
                else:
                    self.engine.remove_projection(source, target)
            elif add:
                self.engine.add_command(source, target)
            else:
                self.engine.remove_command(source, target)

    def _snapshot(self, kind, state):
        result = {"kind": kind, "stage": state["stage"],
                  "retained_fit_count": len(self.engine._fits)}
        if kind == "ammunition":
            result["stats"] = {"single": self.engine.snapshot(self.ammunition_fit)}
            return result
        fits = state["fits"]
        stats, pending = {}, {}
        # Read recipient two before one, without manually refreshing either.
        for name in ("second", "first", "unlinked", "source"):
            stats[name] = self.engine.projection_snapshot(fits[name])
            if kind == "command":
                pending[name] = len(fits[name].commandBonuses)
        source = fits["source"]
        reverse = source.projectedOnto if kind == "projection" else source.boostedOnto
        links = {"source_count": len(reverse), "recipients": {}}
        for name in ("first", "second", "unlinked"):
            fit = fits[name]
            forward = fit.projectedFitDict if kind == "projection" else fit.commandFitDict
            links["recipients"][name] = {"count": len(forward),
                                         "forward": forward.get(source.ID) is source,
                                         "reverse": fit.ID in reverse}
        result.update(stats=stats, links=links)
        if kind == "command":
            result["pending_command_bonuses"] = pending
        return result
