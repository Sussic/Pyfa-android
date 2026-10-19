"""Minimal EOS session for A03–A05. See README.md for the narrow API."""

from contextlib import closing
import math
from pathlib import Path
import sqlite3
import sys
import threading
from .pilot_security import ABSENT as _NO_CHARACTER_SECURITY


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
        self._restore_security_inputs()

    def _restore_security_inputs(self, extra=None):
        """Restore every possible recursive source before an EOS lazy read."""
        from .pilot_security import restore
        for fit in self._fits: restore(fit)
        if extra is not None and all(value is not extra for value in self._fits): restore(extra)

    def prepare_read(self, fit):
        """Restore LOCAL effects before freezing one endpoint's output.

        PROJECTED and COMMAND evaluation may leave calculated=True without a
        source's own incoming projections or local burst effects. That flag does
        not identify the cached context. Calculation caches are not durable fit
        inputs; ownership checks and identity resolution remain side-effect-free.
        """
        self._check_fit(fit)
        self._recalculate(fit)
        return fit

    def prepare_capacitor_read(self, fit):
        """Start each capacitor graph read with a clean LOCAL simulation cache.

        EOS keys saved cap simulation events by starting capacity, not horizon.
        A preceding capState snapshot can cache six hours, while getCapSimData
        normally simulates one hour. Clear that ephemeral cache before sampling;
        do not relax the graph's one-hour event validation or mutate fit inputs.
        """
        self._check_fit(fit)
        self._recalculate(fit)
        return fit

    def _item(self, name):
        import eos.db
        if not isinstance(name, str) or not name:
            raise ValueError("Item name must be a nonempty English name")
        item = eos.db.getItem(name)
        if item is None:
            raise ValueError("Unknown item: " + name)
        self.resolved_item_ids[name] = item.ID
        return item

    def create_fit(self, spec, *, restore=False, named_resolver=None, character_security=_NO_CHARACTER_SECURITY):
        """Create a local ship/modules/drones fit; reject unimplemented inputs."""
        self._check_thread()
        if named_resolver is not None and not restore:
            raise ValueError('Named reactive armor requires trusted graph reconstruction')
        if character_security is not _NO_CHARACTER_SECURITY and not restore:
            raise ValueError('Character security requires trusted graph reconstruction')
        _keys(spec, ("name", "ship", "skill_level", "factor_reload", "damage_pattern",
                     "security", "modules", "drones", "target_profile", "implants",
                     "boosters", "projections", "commands", "environments"), ("ignore_restrictions", "mode", "cargo", "notes", "fighters", "projected_modules", "projected_drones", "projected_fighters"))
        if 'notes' in spec:
            from .notes import validate
            validate(spec['notes'])
        from .output_inputs import profile, environments, fighters
        profile(spec['target_profile']); environments(spec['environments']); fighters(spec.get('fighters',[]))
        if any(spec[key] != [] for key in (
                "implants", "boosters", "projections", "commands")):
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
        from .pilot_security import number as security_number
        security_number(pilot, nullable=character_security is not _NO_CHARACTER_SECURITY)
        if character_security is not _NO_CHARACTER_SECURITY: security_number(character_security)
        if not isinstance(spec["modules"], list) or not isinstance(spec["drones"], list):
            raise ValueError("Modules and drones must be lists")

        from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
        from eos.saveddata.character import Character
        from eos.saveddata.cargo import Cargo
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
        fit._native_rah_resolver = named_resolver
        if 'notes' in spec:
            fit.notes = spec['notes']
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
        from eos.saveddata.targetProfile import TargetProfile
        fit.targetProfile = None if spec['target_profile'] is None else TargetProfile(**spec['target_profile'])
        fit.factorReload = spec["factor_reload"]
        fit.implantLocation = ImplantLocation.FIT
        fit.systemSecurity = security
        fit.pilotSecurity = pilot
        from .pilot_security import install as install_security
        install_security(fit, pilot, character_security)
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
            _keys(row, ("name", "state"), ("charge", "spool_cycles", "rah_pattern"))
            module = Module(self._item(row["name"]))
            try:
                state = FittingModuleState[row["state"]]
            except (KeyError, TypeError) as error:
                raise ValueError("Invalid module state") from error
            if not module.isValidState(state):
                raise ValueError("Module cannot use that state")
            module.state = state
            module.owner = fit
            from .module_spool import restore as restore_spool
            restore_spool(module, row)
            from .module_rah import restore as restore_rah
            restore_rah(module, row, named_resolver)
            if row.get("charge") is not None:
                charge = self._item(row["charge"])
                if not module.isValidCharge(charge):
                    raise ValueError("Incompatible module charge")
                module.charge = charge
            fit.modules.appendIgnoreEmpty(module)
        from .drone_records import restore as restore_drone
        for row in spec["drones"]:
            if 'mutation' in row and not restore:
                raise ValueError('Creating mutated drones is not supported by this editor')
            drone = restore_drone(self, row)
            drone.owner = fit
            fit.drones.append(drone)
        from eos.saveddata.fighter import Fighter
        for row in spec.get('fighters',[]):
            fighter = Fighter(self._item(row['name']))
            fighter.owner = fit
            fit.fighters.append(fighter)
            if row['amount'] > fighter.fighterSquadronMaxSize:
                raise ValueError('Fighter amount exceeds its squadron size')
            fighter.amount = row['amount']; fighter.active = row['active']
            from .fighter_records import restore_states
            restore_states(fighter,row)
        for row in spec['environments']:
            effect = Module(self._item(row['name']))
            effect.state = FittingModuleState[row['state']]
            effect.owner = fit
            fit.projectedModules.append(effect)
        from .projected_module_records import setup as setup_projected
        setup_projected(self, fit, spec)
        from .projected_drone_records import setup as setup_drones
        setup_drones(self, fit, spec)
        from .projected_fighter_records import setup as setup_fighters
        setup_fighters(self, fit, spec)
        seen_cargo = set()
        for row in spec.get("cargo", []):
            _keys(row, ("name", "amount"))
            _integer(row["amount"], 1, 2**63 - 1)
            cargo = Cargo(self._item(row["name"]))
            if cargo.itemID in seen_cargo:
                raise ValueError("Duplicate cargo stack")
            seen_cargo.add(cargo.itemID)
            cargo.amount = row["amount"]
            fit.cargo.append(cargo)
        self._restore_security_inputs(fit)
        self._guard_drone_inputs(fit)
        fit.calculateModifiedAttributes()
        self._guard_drone_cap(fit)
        # Desktop restriction re-enable deliberately retains over-hardpoint fits.
        # Saved/copy replay must preserve them; new fitting still checks them.
        def valid_saved_module(module):
            if module.isEmpty or module.fits(fit, hardpointLimit=not restore):
                return True
            # The original subsystem-removal command leaves equipped modules
            # in place when their HIGH/MED/LOW slot disappears, with fits=False.
            # Reopening our own durable graph must retain that visible warning.
            # EOS still checks all non-slot restrictions, including hull type.
            from eos.const import FittingSlot
            return (restore and fit.ship.item.group.name == "Strategic Cruiser"
                    and module.slot in (FittingSlot.HIGH, FittingSlot.MED, FittingSlot.LOW)
                    and fit.getSlotsUsed(module.slot) > fit.getNumSlots(module.slot)
                    and module._Module__fitRestrictions(fit, hardpointLimit=False))

        if any(not valid_saved_module(module) for module in fit.modules):
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

    def add_projected_fit(self, source, target):
        from .projected_fit_editor import add
        return add(self, source, target)

    def set_projected_fit_amount(self, source, target, *, amount):
        from .projected_fit_editor import amount as change_amount
        return change_amount(self, source, target, amount)

    def set_projected_fit_range(self, source, target, *, range_m):
        from .projected_fit_editor import option
        return option(self, source, target, field='range', value=range_m)

    def set_projected_fit_active(self, source, target, *, active):
        from .projected_fit_editor import option
        return option(self, source, target, field='active', value=active)

    def remove_projected_fit(self, source, target):
        from .projected_fit_editor import remove
        return remove(self, source, target)

    def add_projection(self, source, target, *, range_m=None, active=True, amount=1):
        """Link existing fits; duplicates must be edited explicitly."""
        self._check_fit(source)
        self._check_fit(target)
        self._projection_values(range_m, active, amount)
        if source.ID in target.projectedFitDict:
            raise ValueError("Projection already exists; use configure_projection")
        import eos.db
        from .inspection_identity import capture, restore
        # ORM refresh can replace unchanged addition objects. Their logical
        # identities belong to the saved graph, not to Python object lifetimes.
        source_identities = capture(source)
        from .module_rah import capture_overrides, restore_overrides
        source_rah = capture_overrides(source)
        target.projectedFitDict[source.ID] = source
        # Same flush/refresh as desktop CalcAddProjectedFitCommand (issue #83).
        eos.db.saveddata_session.flush()
        from .projected_module_records import refresh_order, restore_refresh_order
        projected_order = refresh_order(source)
        from .projected_drone_records import refresh_order as drone_order, restore_refresh_order as restore_drones
        saved_drone_order = drone_order(source)
        from .projected_fighter_records import refresh_order as fighter_order, restore_refresh_order as restore_fighters
        saved_fighter_order = fighter_order(source)
        from .character_implants import refresh_order as implant_order, restore_refresh_order as restore_implants
        saved_implant_order = implant_order(source)
        eos.db.saveddata_session.refresh(source)
        self._restore_security_inputs(source)
        restore_implants(source, saved_implant_order)
        restore_refresh_order(source, projected_order)
        restore_drones(source, saved_drone_order)
        restore_fighters(source, saved_fighter_order)
        restore_overrides(source, source_rah)
        # Refresh expires module relationships; collected ORM objects can reload
        # without modified attributes while the source still says calculated.
        self._recalculate(source)
        restore(source, source_identities)
        self.configure_projection(source, target, range_m=range_m, active=active, amount=amount)

    def configure_projection(self, source, target, *, range_m, active, amount):
        """Set all link options together after validation; range units are metres."""
        info = self._projection(source, target)
        self._projection_values(range_m, active, amount)
        # EOS persists metres as Float and Kotlin exposes Double. Canonicalize
        # integral JSON inputs before history records them, so ORM refresh after
        # copying a linked fit cannot turn an unchanged range into a typed edit.
        info.projectionRange = None if range_m is None else float(range_m)
        info.active, info.amount = active, amount
        self._recalculate(target)

    def remove_projection(self, source, target):
        """Remove the complete link, including its reverse association."""
        self._projection(source, target)
        import eos.db
        from .inspection_identity import capture, restore
        source_identities = capture(source)
        from .module_rah import capture_overrides, restore_overrides
        source_rah = capture_overrides(source)
        del target.projectedFitDict[source.ID]
        eos.db.saveddata_session.flush()
        from .projected_module_records import refresh_order, restore_refresh_order
        projected_order = refresh_order(source)
        from .projected_drone_records import refresh_order as drone_order, restore_refresh_order as restore_drones
        saved_drone_order = drone_order(source)
        from .projected_fighter_records import refresh_order as fighter_order, restore_refresh_order as restore_fighters
        saved_fighter_order = fighter_order(source)
        from .character_implants import refresh_order as implant_order, restore_refresh_order as restore_implants
        saved_implant_order = implant_order(source)
        eos.db.saveddata_session.refresh(source)
        self._restore_security_inputs(source)
        restore_implants(source, saved_implant_order)
        restore_refresh_order(source, projected_order)
        restore_drones(source, saved_drone_order)
        restore_fighters(source, saved_fighter_order)
        restore_overrides(source, source_rah)
        self._recalculate(source)
        restore(source, source_identities)
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

    def add_command_fit(self, source, target):
        from .command_fit_editor import add
        return add(self, source, target)

    def set_command_fit_active(self, source, target, *, active):
        from .command_fit_editor import active as change_active
        return change_active(self, source, target, active)

    def remove_command_fit(self, source, target):
        from .command_fit_editor import remove
        return remove(self, source, target)

    def add_command(self, source, target, *, active=True):
        """Link an existing command source using EOS's mapped association."""
        self._check_fit(source)
        self._check_fit(target)
        if type(active) is not bool:
            raise ValueError("Command active state must be boolean")
        if source.ID in target.commandFitDict:
            raise ValueError("Command link already exists")
        import eos.db
        from .inspection_identity import capture, restore
        source_identities = capture(source)
        from .module_rah import capture_overrides, restore_overrides
        source_rah = capture_overrides(source)
        target.commandFitDict[source.ID] = source
        eos.db.saveddata_session.flush()
        from .projected_module_records import refresh_order, restore_refresh_order
        projected_order = refresh_order(source)
        from .projected_drone_records import refresh_order as drone_order, restore_refresh_order as restore_drones
        saved_drone_order = drone_order(source)
        from .projected_fighter_records import refresh_order as fighter_order, restore_refresh_order as restore_fighters
        saved_fighter_order = fighter_order(source)
        from .character_implants import refresh_order as implant_order, restore_refresh_order as restore_implants
        saved_implant_order = implant_order(source)
        eos.db.saveddata_session.refresh(source)
        self._restore_security_inputs(source)
        restore_implants(source, saved_implant_order)
        restore_refresh_order(source, projected_order)
        restore_drones(source, saved_drone_order)
        restore_fighters(source, saved_fighter_order)
        restore_overrides(source, source_rah)
        self._recalculate(source)
        restore(source, source_identities)
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
        from .inspection_identity import capture, restore
        source_identities = capture(source)
        from .module_rah import capture_overrides, restore_overrides
        source_rah = capture_overrides(source)
        del target.commandFitDict[source.ID]
        eos.db.saveddata_session.flush()
        from .projected_module_records import refresh_order, restore_refresh_order
        projected_order = refresh_order(source)
        from .projected_drone_records import refresh_order as drone_order, restore_refresh_order as restore_drones
        saved_drone_order = drone_order(source)
        from .projected_fighter_records import refresh_order as fighter_order, restore_refresh_order as restore_fighters
        saved_fighter_order = fighter_order(source)
        from .character_implants import refresh_order as implant_order, restore_refresh_order as restore_implants
        saved_implant_order = implant_order(source)
        eos.db.saveddata_session.refresh(source)
        self._restore_security_inputs(source)
        restore_implants(source, saved_implant_order)
        restore_refresh_order(source, projected_order)
        restore_drones(source, saved_drone_order)
        restore_fighters(source, saved_fighter_order)
        restore_overrides(source, source_rah)
        self._recalculate(source)
        restore(source, source_identities)
        self._recalculate(target)

    def set_damage_pattern(self, fit, pattern):
        """Apply fit-local incoming contributions using EOS's original pattern model."""
        self._check_fit(fit)
        import math
        amounts=tuple(pattern.values())
        if set(pattern)!= {'emAmount','thermalAmount','kineticAmount','explosiveAmount'} or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in amounts) or not math.isfinite(sum(amounts)) or sum(amounts)<=0:
            raise ValueError('Invalid incoming damage contributions')
        from eos.saveddata.damagePattern import DamagePattern
        fit.damagePattern=DamagePattern(**pattern)
        self._recalculate(fit)

    def set_target_profile(self, fit, value):
        self._check_fit(fit)
        from .output_inputs import profile
        from eos.saveddata.targetProfile import TargetProfile
        profile(value)
        fit.targetProfile = None if value is None else TargetProfile(**value)
        self._recalculate(fit)

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
        """User edit: structures and dormant fit-local input are read-only."""
        self._check_fit(fit)
        from .implant_editor import require_editable
        require_editable(fit)
        self._restore_implant(fit, item_name, active=active)

    def _restore_implant(self, fit, item_name, *, active=True):
        """Reconstruct validated historical local rows, including structures."""
        self._check_fit(fit)
        if type(active) is not bool:
            raise ValueError("Implant active state must be boolean")
        from eos.saveddata.implant import Implant
        value = self._item(item_name)
        if not value.isImplant: raise ValueError('Choose a genuine implant')
        implant = Implant(value)
        if any(existing.slot == implant.slot for existing in fit.implants):
            raise ValueError("Implant slot is occupied")
        implant.active = active
        fit.implants.append(implant)
        self._recalculate(fit)

    def _implant(self, fit, slot):
        self._check_fit(fit)
        from .implant_editor import require_editable
        require_editable(fit)
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

    def _guard_drone_inputs(self, extra=None):
        fits = list(self._fits)
        if extra is not None and all(value is not extra for value in fits): fits.append(extra)
        if not any(fit.projectedDrones or fit.projectedFighters for fit in fits): return
        from .projected_drone_budget import admit, live_records
        admit(live_records(fits))

    def _guard_drone_cap(self, fit):
        fits = list(self._fits)
        if all(value is not fit for value in fits): fits.append(fit)
        if not any(value.projectedDrones or value.projectedFighters for value in fits): return
        from .projected_drone_cap_budget import check, request_factor
        check(fit, len(fits), simulations_per_fit=request_factor(self))

    def _recalculate(self, fit):
        self._restore_security_inputs(fit)
        self._guard_drone_inputs(fit)
        fit.clear()
        fit.calculateModifiedAttributes()
        self._guard_drone_cap(fit)

    def snapshot(self, fit, weapon_index=0):
        """A03's 38-field sample contract; weapon range is for the chosen module.

        This is not a full Pyfa statistics API. It deliberately reads EOS values
        instead of importing the desktop reference exporter or porting formulas.
        """
        self._check_fit(fit)
        _integer(weapon_index, 0, max(0, len(fit.modules) - 1))
        # Calculating a changed source invalidates its direct recipients in EOS.
        # Read after recalculation, as desktop getFit does before displaying it.
        self._guard_drone_inputs(fit)
        if not fit.calculated:
            fit.calculateModifiedAttributes()
        self._guard_drone_cap(fit)
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
