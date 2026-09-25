"""Minimal EOS session for A03–A05. See README.md for the narrow API."""

from contextlib import closing
import math
from pathlib import Path
import sqlite3
import sys
import threading


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or (
            value.keys() - set(required) - set(optional)):
        raise ValueError("Unsupported or missing input fields")


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid integer input")


class HeadlessEngine:
    """One in-memory EOS session per process, used on its creating thread.

    No desktop service imports, network calls, user database or schema migration.
    EOS objects are provisional internal handles, not the later Kotlin contract.
    """

    def __init__(self, game_database):
        database = Path(game_database).resolve(strict=True)
        if not database.is_file():
            raise ValueError("Game database must be an existing file")
        if "eos.db" in sys.modules:
            raise RuntimeError("Initialize HeadlessEngine before importing eos.db; one session per process")
        uri = database.as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            metadata = dict(connection.execute("SELECT field_name, field_value FROM metadata"))
            if not all(metadata.get(key) for key in ("client_build", "dump_time", "schema_version")):
                raise ValueError("Game database metadata is incomplete")

        # eos.db creates engines at import time. Configure paths first.
        import eos.config
        eos.config.gamedata_connectionstring = lambda: sqlite3.connect(uri, uri=True)
        eos.config.saveddata_connectionstring = "sqlite:///:memory:"
        # Match desktop config.init: the optional global query cache aliases
        # item/group IDs. Charge discovery calls both with overlapping IDs.
        eos.config.gamedataCache = False
        eos.config.set_lang("en")
        import eos.db

        self.database = database
        self.metadata = metadata
        self.settings = dict(eos.config.settings)
        self.resolved_item_ids = {}
        self._thread = threading.get_ident()
        self._fits = []

    def _check_thread(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("Use the EOS session on its creating thread")

    def _check_fit(self, fit):
        self._check_thread()
        if not any(value is fit for value in self._fits):
            raise ValueError("Fit does not belong to this session")

    def _item(self, name):
        import eos.db
        if not isinstance(name, str) or not name:
            raise ValueError("Item name must be a nonempty English name")
        item = eos.db.getItem(name)
        if item is None:
            raise ValueError("Unknown item: " + name)
        self.resolved_item_ids[name] = item.ID
        return item

    def create_fit(self, spec, *, restore=False):
        """Create a local ship/modules/drones fit; reject unimplemented inputs."""
        self._check_thread()
        _keys(spec, ("name", "ship", "skill_level", "factor_reload", "damage_pattern",
                     "security", "modules", "drones", "target_profile", "implants",
                     "boosters", "projections", "commands", "environments"), ("ignore_restrictions", "mode"))
        if spec["target_profile"] is not None or any(spec[key] != [] for key in (
                "implants", "boosters", "projections", "commands", "environments")):
            raise ValueError("This adapter does not implement those scenario inputs yet")
        _integer(spec["skill_level"], 0, 5)
        if not isinstance(spec["name"], str) or not spec["name"] or type(spec["factor_reload"]) is not bool:
            raise ValueError("Invalid fit name or reload setting")
        _keys(spec["damage_pattern"], ("emAmount", "thermalAmount", "kineticAmount", "explosiveAmount"))
        amounts = spec["damage_pattern"].values()
        if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in amounts) or sum(amounts) <= 0:
            raise ValueError("Invalid damage pattern")
        _keys(spec["security"], ("system", "pilot"))
        pilot = spec["security"]["pilot"]
        if type(pilot) not in (int, float) or not math.isfinite(pilot) or not -10 <= pilot <= 5:
            raise ValueError("Invalid pilot security")
        if not isinstance(spec["modules"], list) or not isinstance(spec["drones"], list):
            raise ValueError("Modules and drones must be lists")

        from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
        from eos.saveddata.character import Character
        from eos.saveddata.citadel import Citadel
        from eos.saveddata.damagePattern import DamagePattern
        from eos.saveddata.drone import Drone
        from eos.saveddata.fit import Fit
        from eos.saveddata.module import Module
        from eos.saveddata.ship import Ship

        try:
            security = FitSystemSecurity[spec["security"]["system"]]
        except (KeyError, TypeError) as error:
            raise ValueError("Invalid system security") from error
        item = self._item(spec["ship"])
        hull = Citadel(item) if item.category.name == "Structure" else Ship(item)
        fit = Fit(hull, name=spec["name"])
        if "mode" in spec:
            from eos.saveddata.mode import Mode
            mode_id = spec["mode"]
            if type(mode_id) is not int:
                raise ValueError("Invalid hull mode")
            mode_item = next((candidate for candidate in hull.modeItems or () if candidate.ID == mode_id), None)
            if mode_item is None:
                raise ValueError("Invalid hull mode")
            fit.mode = Mode(mode_item)
        fit.character = Character("Headless synthetic skills", defaultLevel=spec["skill_level"])
        fit.damagePattern = DamagePattern(**spec["damage_pattern"])
        fit.targetProfile = None
        fit.factorReload = spec["factor_reload"]
        fit.implantLocation = ImplantLocation.FIT
        fit.systemSecurity = security
        fit.pilotSecurity = pilot
        fit.ignoreRestrictions = spec.get("ignore_restrictions", False)
        if type(fit.ignoreRestrictions) is not bool:
            raise ValueError("Invalid restriction override")
        for row in spec["modules"]:
            if "empty_slot" in row:
                from .fitting import VACANT_SLOTS
                _keys(row, ("empty_slot",))
                if type(row["empty_slot"]) is not str or row["empty_slot"] not in VACANT_SLOTS:
                    raise ValueError("Invalid empty module slot")
                fit.modules.appendIgnoreEmpty(Module.buildEmpty(VACANT_SLOTS[row["empty_slot"]]))
                continue
            _keys(row, ("name", "state"), ("charge",))
            module = Module(self._item(row["name"]))
            try:
                state = FittingModuleState[row["state"]]
            except (KeyError, TypeError) as error:
                raise ValueError("Invalid module state") from error
            if not module.isValidState(state):
                raise ValueError("Module cannot use that state")
            module.state = state
            module.owner = fit
            if row.get("charge") is not None:
                charge = self._item(row["charge"])
                if not module.isValidCharge(charge):
                    raise ValueError("Incompatible module charge")
                module.charge = charge
            fit.modules.appendIgnoreEmpty(module)
        for row in spec["drones"]:
            _keys(row, ("name", "amount", "active"))
            _integer(row["amount"], 1, 2**31 - 1)
            _integer(row["active"], 0, row["amount"])
            drone = Drone(self._item(row["name"]))
            drone.amount = row["amount"]
            drone.amountActive = row["active"]
            drone.owner = fit
            fit.drones.append(drone)
        fit.calculateModifiedAttributes()
        # Desktop restriction re-enable deliberately retains over-hardpoint fits.
        # Saved/copy replay must preserve them; new fitting still checks them.
        if any(not module.isEmpty and not module.fits(fit, hardpointLimit=not restore)
               for module in fit.modules):
            raise ValueError("Fit contains incompatible equipment")
        # EOS projection associations need unique fit IDs and the mapped reverse
        # relationships. This database is in memory; disk persistence is B02.
        import eos.db
        eos.db.saveddata_session.add(fit)
        eos.db.saveddata_session.flush()
        self._fits.append(fit)
        return fit

    @staticmethod
    def _projection_values(range_m, active, amount):
        if range_m is not None and (type(range_m) not in (int, float) or
                                    not math.isfinite(range_m) or range_m < 0):
            raise ValueError("Projection range must be nonnegative metres or None")
        if type(active) is not bool:
            raise ValueError("Projection active state must be boolean")
        _integer(amount, 1, 2**31 - 1)

    def _projection(self, source, target):
        self._check_fit(source)
        self._check_fit(target)
        if target.projectedFitDict.get(source.ID) is not source:
            raise ValueError("Projection does not exist")
        info = source.getProjectionInfo(target.ID)
        if info is None:
            raise RuntimeError("EOS projection reverse relationship is missing")
        return info

    def add_projection(self, source, target, *, range_m=None, active=True, amount=1):
        """Link existing fits; duplicates must be edited explicitly."""
        self._check_fit(source)
        self._check_fit(target)
        self._projection_values(range_m, active, amount)
        if source.ID in target.projectedFitDict:
            raise ValueError("Projection already exists; use configure_projection")
        import eos.db
        target.projectedFitDict[source.ID] = source
        # Same flush/refresh as desktop CalcAddProjectedFitCommand (issue #83).
        eos.db.saveddata_session.flush()
        eos.db.saveddata_session.refresh(source)
        # Refresh expires module relationships; collected ORM objects can reload
        # without modified attributes while the source still says calculated.
        self._recalculate(source)
        self.configure_projection(source, target, range_m=range_m, active=active, amount=amount)

    def configure_projection(self, source, target, *, range_m, active, amount):
        """Set all link options together after validation; range units are metres."""
        info = self._projection(source, target)
        self._projection_values(range_m, active, amount)
        info.projectionRange, info.active, info.amount = range_m, active, amount
        self._recalculate(target)

    def remove_projection(self, source, target):
        """Remove the complete link, including its reverse association."""
        self._projection(source, target)
        import eos.db
        del target.projectedFitDict[source.ID]
        eos.db.saveddata_session.flush()
        eos.db.saveddata_session.refresh(source)
        self._recalculate(source)
        self._recalculate(target)

    def projection_snapshot(self, fit):
        """A04 extends the A03 sample with scan resolution for script changes."""
        result = self.snapshot(fit)
        result["scan_resolution"] = {"value": fit.ship.getModifiedItemAttr("scanResolution"), "unit": "mm"}
        return result

    def _command(self, source, target):
        self._check_fit(source)
        self._check_fit(target)
        if target.commandFitDict.get(source.ID) is not source:
            raise ValueError("Command link does not exist")
        info = source.getCommandInfo(target.ID)
        if info is None:
            raise RuntimeError("EOS command reverse relationship is missing")
        return info

    def add_command(self, source, target, *, active=True):
        """Link an existing command source using EOS's mapped association."""
        self._check_fit(source)
        self._check_fit(target)
        if type(active) is not bool:
            raise ValueError("Command active state must be boolean")
        if source.ID in target.commandFitDict:
            raise ValueError("Command link already exists")
        import eos.db
        target.commandFitDict[source.ID] = source
        eos.db.saveddata_session.flush()
        eos.db.saveddata_session.refresh(source)
        self._recalculate(source)
        self.set_command_active(source, target, active)

    def set_command_active(self, source, target, active):
        info = self._command(source, target)
        if type(active) is not bool:
            raise ValueError("Command active state must be boolean")
        info.active = active
        self._recalculate(target)

    def remove_command(self, source, target):
        self._command(source, target)
        import eos.db
        del target.commandFitDict[source.ID]
        eos.db.saveddata_session.flush()
        eos.db.saveddata_session.refresh(source)
        self._recalculate(source)
        self._recalculate(target)

    def set_skill_level(self, fit, skill_name, level):
        """Edit one skill on this fit's synthetic character through EOS."""
        self._check_fit(fit)
        _integer(level, 0, 5)
        item = self._item(skill_name)
        if item.category.name != "Skill":
            raise ValueError("Selected item is not a skill")
        fit.character.getSkill(item).setLevel(level)
        self._recalculate(fit)

    def add_implant(self, fit, item_name, *, active=True):
        """Add a fit-local implant to a vacant slot; replacement belongs to C07."""
        self._check_fit(fit)
        if type(active) is not bool:
            raise ValueError("Implant active state must be boolean")
        from eos.saveddata.implant import Implant
        implant = Implant(self._item(item_name))
        if any(existing.slot == implant.slot for existing in fit.implants):
            raise ValueError("Implant slot is occupied")
        implant.active = active
        fit.implants.append(implant)
        self._recalculate(fit)

    def _implant(self, fit, slot):
        self._check_fit(fit)
        _integer(slot, 1, 2**31 - 1)
        implant = next((value for value in fit.implants if value.slot == slot), None)
        if implant is None:
            raise ValueError("Implant slot is empty")
        return implant

    def set_implant_active(self, fit, slot, active):
        implant = self._implant(fit, slot)
        if type(active) is not bool:
            raise ValueError("Implant active state must be boolean")
        implant.active = active
        self._recalculate(fit)

    def remove_implant(self, fit, slot):
        implant = self._implant(fit, slot)
        fit.implants.remove(implant)
        self._recalculate(fit)

    def set_module_states(self, fit, module_indices, state_name):
        """Validate the full selection before changing module states together."""
        self._check_fit(fit)
        if not isinstance(module_indices, list) or not module_indices:
            raise ValueError("Select at least one module")
        for index in module_indices:
            _integer(index, 0, len(fit.modules) - 1)
        if len(set(module_indices)) != len(module_indices):
            raise ValueError("Module selection contains duplicates")
        from eos.const import FittingModuleState
        try:
            state = FittingModuleState[state_name]
        except (KeyError, TypeError) as error:
            raise ValueError("Invalid module state") from error
        modules = [fit.modules[index] for index in module_indices]
        if any(module.isEmpty or not module.isValidState(state) for module in modules):
            raise ValueError("A selected module cannot use that state")
        previous = [module.state for module in modules]
        try:
            for module in modules:
                module.state = state
            self._recalculate(fit)
        except Exception:
            for module, old in zip(modules, previous):
                module.state = old
            self._recalculate(fit)
            raise

    def set_charges(self, fit, module_indices, charge_name):
        """Change a selection together; validate all entries before editing any."""
        self._check_fit(fit)
        if not isinstance(module_indices, list) or not module_indices:
            raise ValueError("Select at least one module")
        for index in module_indices:
            _integer(index, 0, len(fit.modules) - 1)
        if len(set(module_indices)) != len(module_indices):
            raise ValueError("Module selection contains duplicates")
        charge = None if charge_name is None else self._item(charge_name)
        modules = [fit.modules[index] for index in module_indices]
        if any(module.isEmpty or not module.isValidCharge(charge) for module in modules):
            raise ValueError("Charge is incompatible with the selection")
        previous = [module.charge for module in modules]
        try:
            for module in modules:
                module.charge = charge
            self._recalculate(fit)
        except Exception:
            for module, old in zip(modules, previous):
                module.charge = old
            self._recalculate(fit)
            raise

    @staticmethod
    def _recalculate(fit):
        fit.clear()
        fit.calculateModifiedAttributes()

    def snapshot(self, fit, weapon_index=0):
        """A03's 38-field sample contract; weapon range is for the chosen module.

        This is not a full Pyfa statistics API. It deliberately reads EOS values
        instead of importing the desktop reference exporter or porting formulas.
        """
        self._check_fit(fit)
        _integer(weapon_index, 0, max(0, len(fit.modules) - 1))
        # Calculating a changed source invalidates its direct recipients in EOS.
        # Read after recalculation, as desktop getFit does before displaying it.
        if not fit.calculated:
            fit.calculateModifiedAttributes()
        result = {}

        def put(name, value, unit):
            result[name] = {"value": value, "unit": unit}

        ship = fit.ship.getModifiedItemAttr
        for name, attribute, unit in (
                ("cpu_output", "cpuOutput", "tf"),
                ("powergrid_output", "powerOutput", "MW"),
                ("capacitor_capacity", "capacitorCapacity", "GJ"),
                ("capacitor_recharge_time", "rechargeRate", "ms"),
                ("max_velocity", "maxVelocity", "m/s"),
                ("max_target_range", "maxTargetRange", "m")):
            put(name, ship(attribute), unit)
        put("cpu_used", fit.getItemAttrOnlineSum(fit.modules, "cpu"), "tf")
        put("powergrid_used", fit.getItemAttrOnlineSum(fit.modules, "power"), "MW")
        put("drone_control_range", fit.extraAttributes["droneControlRange"], "m")
        put("drone_bandwidth_used", fit.droneBandwidthUsed, "Mbit/s")
        for name, value, unit in (
                ("weapon_dps", fit.getWeaponDps().total, "HP/s"),
                ("drone_dps", fit.getDroneDps().total, "HP/s"),
                ("total_dps", fit.getTotalDps().total, "HP/s"),
                ("total_volley", fit.getTotalVolley().total, "HP"),
                ("capacitor_used", fit.capUsed, "GJ/s"),
                ("capacitor_recharge", fit.capRecharge, "GJ/s"),
                ("capacitor_stable", fit.capStable, "boolean"),
                ("capacitor_state", fit.capState, "%" if fit.capStable else "s")):
            put(name, value, unit)
        weapon = fit.modules[weapon_index] if fit.modules else None
        put("gun_optimal", weapon.getModifiedItemAttr("maxRange") if weapon else None, "m")
        put("gun_falloff", weapon.getModifiedItemAttr("falloff") if weapon else None, "m")
        for layer, prefix in (("shield", "shield"), ("armor", "armor"), ("hull", "")):
            put(layer + "_hp", fit.hp[layer], "HP")
            put(layer + "_ehp_uniform", fit.ehp[layer], "HP")
            for damage in ("em", "thermal", "kinetic", "explosive"):
                attribute = prefix + damage.title() if prefix else damage
                put(layer + "_" + damage + "_resonance", ship(attribute + "DamageResonance"), "fraction")
        return result
