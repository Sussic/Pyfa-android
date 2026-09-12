"""Minimal EOS session for A03. See README.md for the intentionally narrow API."""

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

    def create_fit(self, spec):
        """Create a local ship/modules/drones fit; reject unimplemented inputs."""
        self._check_thread()
        _keys(spec, ("name", "ship", "skill_level", "factor_reload", "damage_pattern",
                     "security", "modules", "drones", "target_profile", "implants",
                     "boosters", "projections", "commands", "environments"))
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
        from eos.saveddata.damagePattern import DamagePattern
        from eos.saveddata.drone import Drone
        from eos.saveddata.fit import Fit
        from eos.saveddata.module import Module
        from eos.saveddata.ship import Ship

        try:
            security = FitSystemSecurity[spec["security"]["system"]]
        except (KeyError, TypeError) as error:
            raise ValueError("Invalid system security") from error
        fit = Fit(Ship(self._item(spec["ship"])), name=spec["name"])
        fit.character = Character("Headless synthetic skills", defaultLevel=spec["skill_level"])
        fit.damagePattern = DamagePattern(**spec["damage_pattern"])
        fit.targetProfile = None
        fit.factorReload = spec["factor_reload"]
        fit.implantLocation = ImplantLocation.FIT
        fit.systemSecurity = security
        fit.pilotSecurity = pilot
        fit.ignoreRestrictions = False
        for row in spec["modules"]:
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
            fit.modules.append(module)
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
        if not fit.fits:
            raise ValueError("Fit contains incompatible equipment")
        self._fits.append(fit)
        return fit

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
        if any(not module.isValidCharge(charge) for module in modules):
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
        _integer(weapon_index, 0, len(fit.modules) - 1)
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
        weapon = fit.modules[weapon_index]
        put("gun_optimal", weapon.getModifiedItemAttr("maxRange"), "m")
        put("gun_falloff", weapon.getModifiedItemAttr("falloff"), "m")
        for layer, prefix in (("shield", "shield"), ("armor", "armor"), ("hull", "")):
            put(layer + "_hp", fit.hp[layer], "HP")
            put(layer + "_ehp_uniform", fit.ehp[layer], "HP")
            for damage in ("em", "thermal", "kinetic", "explosive"):
                attribute = prefix + damage.title() if prefix else damage
                put(layer + "_" + damage + "_resonance", ship(attribute + "DamageResonance"), "fraction")
        return result
