"""Versioned, transactional JSON boundary around the existing EOS adapter.

Only declarative committed state is retained for recovery. EOS objects are never
copied or exposed as IDs; failed edits rebuild the same transient SQL session.
"""
from copy import deepcopy
import json
import math
import uuid

from .store import GraphStore, StoreError, StoreUncertain, StoreWriteRejected, decode_graph


class ContractError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _invalid(message="Malformed bridge request"):
    raise ContractError("INVALID_REQUEST", message)


def _object(value, required, optional=()):
    if type(value) is not dict or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        _invalid()


def _text(value, identifier=False):
    if type(value) is not str or not value or identifier and len(value) > 128:
        _invalid()


def _integer(value, minimum=0, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        _invalid()


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        _invalid()


def _boolean(value):
    if type(value) is not bool:
        _invalid()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _invalid("Duplicate JSON keys are not allowed")
        result[key] = value
    return result


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _module_state(module):
    from eos.const import FittingModuleState
    # ORM reloads may return the persisted integer rather than the enum object.
    return FittingModuleState(module.state).name


ARGUMENTS = {
    "snapshot": ("fit_ids",), "create_fit": ("spec",),
    "rename_fit": ("fit_id", "name"), "duplicate_fit": ("fit_id", "name"),
    "delete_fit": ("fit_id", "resolve_references"),
    "add_module": ("fit_id", "item_id"),
    "replace_module": ("fit_id", "position", "item_id"),
    "remove_module": ("fit_id", "position"),
    "set_fit_restrictions": ("fit_id", "ignore"),
    "set_charges": ("fit_id", "module_indices", "charge"),
    "set_module_charge": ("fit_id", "position", "charge_id"),
    "set_bulk_charges": ("fit_id", "main_position", "module_indices", "scope", "charge_id"),
    "change_variation": ("fit_id", "context", "position", "item_id"),
    "swap_modules": ("fit_id", "from_position", "to_position"),
    "set_module_states": ("fit_id", "module_indices", "state"),
    "set_skill_level": ("fit_id", "skill", "level"),
    "add_implant": ("fit_id", "implant", "active"),
    "set_implant_active": ("fit_id", "slot", "active"),
    "remove_implant": ("fit_id", "slot"),
    "add_projection": ("source_id", "target_id", "range_m", "active", "amount"),
    "configure_projection": ("source_id", "target_id", "range_m", "active", "amount"),
    "remove_projection": ("source_id", "target_id"),
    "add_command": ("source_id", "target_id", "active"),
    "set_command_active": ("source_id", "target_id", "active"),
    "remove_command": ("source_id", "target_id"),
}
STATES = {"OFFLINE", "ONLINE", "ACTIVE", "OVERHEATED"}


def _spec(spec):
    _object(spec, ("name", "ship", "skill_level", "factor_reload", "damage_pattern", "security",
                   "modules", "drones", "target_profile", "implants", "boosters", "projections",
                   "commands", "environments"), ("ignore_restrictions",))
    if "ignore_restrictions" in spec:
        _boolean(spec["ignore_restrictions"])
    for key in ("name", "ship"):
        _text(spec[key])
    _integer(spec["skill_level"], 0, 5)
    _boolean(spec["factor_reload"])
    _object(spec["damage_pattern"], ("emAmount", "thermalAmount", "kineticAmount", "explosiveAmount"))
    for value in spec["damage_pattern"].values():
        _number(value)
    _object(spec["security"], ("system", "pilot"))
    _text(spec["security"]["system"])
    if spec["security"]["system"] not in {"HISEC", "LOWSEC", "NULLSEC", "WSPACE"}:
        _invalid()
    _number(spec["security"]["pilot"])
    if spec["target_profile"] is not None or any(spec[key] != [] for key in (
            "implants", "boosters", "projections", "commands", "environments")):
        raise ContractError("INVALID_EDIT", "Those fit features are not supported by this bridge yet")
    if type(spec["modules"]) is not list or type(spec["drones"]) is not list:
        _invalid()
    for module in spec["modules"]:
        if type(module) is dict and "empty_slot" in module:
            from .fitting import VACANT_SLOTS
            _object(module, ("empty_slot",))
            if type(module["empty_slot"]) is not str or module["empty_slot"] not in VACANT_SLOTS:
                _invalid()
            continue
        _object(module, ("name", "state"), ("charge",))
        _text(module["name"])
        if type(module["state"]) is not str or module["state"] not in STATES:
            _invalid()
        if module.get("charge") is not None:
            _text(module["charge"])
    for drone in spec["drones"]:
        _object(drone, ("name", "amount", "active"))
        _text(drone["name"])
        _integer(drone["amount"], 1, 2**31 - 1)
        _integer(drone["active"], 0, drone["amount"])


class BridgeSession:
    def __init__(self, engine, sample_fit=None, sample_spec=None):
        engine._check_thread()
        import eos.db
        if str(eos.db.saveddata_engine.url) != "sqlite:///:memory:":
            raise RuntimeError("The bridge requires an exclusive in-memory saveddata session")
        if sample_fit is None:
            if sample_spec is not None or engine._fits:
                raise ValueError("An empty bridge requires an empty engine")
        else:
            _spec(sample_spec)
            engine._check_fit(sample_fit)
            if engine._fits != [sample_fit]:
                raise ValueError("Only the existing sample fit may be adopted")
        self.engine = engine
        self._session = eos.db.saveddata_session
        self.session_id = uuid.uuid4().hex
        self.sample_id = uuid.uuid4().hex if sample_fit is not None else None
        self._available = True
        self._store = None
        self._fits = {self.sample_id: sample_fit} if sample_fit is not None else {}
        self._revisions = {key: 1 for key in self._fits}
        self._modified = {key: 1 for key in self._fits}
        self._recent = []
        self._records = self._capture(self._fits, {self.sample_id: sample_spec} if sample_fit is not None else {})
        self._snapshots = self._snapshots_for(self._fits, self._revisions, self._fits)
        self._provenance = dict(engine.resolved_item_ids)
        self._serialize_success("bootstrap", list(self._snapshots.values()))
        eos.db.saveddata_session.commit()

    @classmethod
    def open(cls, engine, store_path, dataset_identity, initial_sample_spec):
        """Open durable inputs on an empty engine; never reset an existing file."""
        engine._check_thread()
        if engine._fits:
            raise ValueError("Open saved fits before creating transient fits")
        if (type(dataset_identity) is not str or len(dataset_identity) != 64 or
                any(char not in "0123456789abcdef" for char in dataset_identity)):
            raise ValueError("A logical game database SHA-256 is required")
        store = GraphStore(store_path)
        if store.current is None:
            _spec(initial_sample_spec)
            fit = engine.create_fit(initial_sample_spec)
            bridge = cls(engine, fit, initial_sample_spec)
            bridge._store, bridge._dataset_identity = store, dataset_identity
            attempt = store.prepare(bridge._graph(bridge._records, bridge._revisions))
            if bridge._write_and_confirm(attempt) != "new":
                raise StoreWriteRejected("The initial fit could not be saved; existing files were preserved")
            store.accept(attempt)
            return bridge
        graph = decode_graph(store.current.payload)
        cls._validate_graph(graph, dataset_identity, engine.settings)
        bridge = cls(engine)
        bridge._store, bridge._dataset_identity = store, dataset_identity
        bridge.sample_id = graph["sample_id"]
        bridge._records = {key: graph["records"][key] for key in graph["fit_order"]}
        bridge._revisions = {key: graph["revisions"][key] for key in graph["fit_order"]}
        # Older saves did not retain modification order. Zero means unknown,
        # never a fabricated timestamp or an inference from opening a fit.
        bridge._modified = graph.get("modified", {key: 0 for key in graph["fit_order"]})
        bridge._recent = graph.get("recent", [])
        try:
            from .fitting import item
            if any(item(engine, identity).isAbyssal for identity in bridge._recent):
                raise StoreError("Saved recent use contains an unsupported item")
            fits, snapshots = bridge._rebuild()
            replayed = bridge._capture(fits, {key: record["spec"] for key, record in bridge._records.items()})
            if _json(replayed) != _json(bridge._records):
                raise StoreError("Saved fit inputs could not be restored exactly")
            bridge._serialize_success("bootstrap", list(snapshots.values()))
            bridge._session.commit()
            bridge._fits, bridge._snapshots = fits, snapshots
            bridge._provenance = dict(engine.resolved_item_ids)
            return bridge
        except Exception as error:
            bridge._available = False
            raise StoreError("Saved fits could not be restored; their file has been preserved") from error

    @property
    def persistence_info(self):
        store = self._store
        return {"enabled": store is not None, "path": str(store.path) if store else None,
                "schema": 1 if store else None, "generation": store.current.generation if store and store.current else 0,
                "opened_existing": store.opened_existing if store else False}

    def _graph(self, records, revisions, modified=None, recent=None):
        sample_id = self.sample_id if self.sample_id in records else next(iter(records), None)
        result = {"format": 1 if records else 2, "dataset_identity": self._dataset_identity,
                "eos_settings": deepcopy(self.engine.settings), "sample_id": sample_id,
                "fit_order": list(records), "records": records, "revisions": revisions,
                "modified": self._modified if modified is None else modified}
        history = self._recent if recent is None else recent
        if history:
            result["recent"] = list(history)
        return result

    def organization(self):
        """Read-only library metadata; opening/querying never counts as editing."""
        self.engine._check_thread()
        return {"version": 1, "modified": dict(self._modified)}

    def recent_items(self):
        self.engine._check_thread()
        return {"version": 1, "item_ids": list(self._recent)}

    def fitting_details(self, fit_id):
        from .fitting import details
        self.engine._check_thread()
        if not self._available:
            raise RuntimeError("Restart the fitting engine")
        return {"version": 1, "fit_id": fit_id, "revision": self._revisions[fit_id],
                **details(self.engine, self._fits[fit_id])}

    def charge_options(self, fit_id):
        from .charges import options
        self.engine._check_thread()
        if not self._available:
            raise RuntimeError("Restart the fitting engine")
        return {"version": 1, "fit_id": fit_id, "revision": self._revisions[fit_id],
                **options(self.engine, self._fits[fit_id])}

    def variation_options(self, fit_id):
        from .variations import options
        self.engine._check_thread()
        if not self._available:
            raise RuntimeError("Restart the fitting engine")
        return {"version": 1, "fit_id": fit_id, "revision": self._revisions[fit_id],
                **options(self.engine, self._fits[fit_id])}

    def bulk_charge_options(self, fit_id):
        from .bulk import options
        self.engine._check_thread()
        if not self._available:
            raise RuntimeError("Restart the fitting engine")
        return {"version": 1, "fit_id": fit_id, "revision": self._revisions[fit_id],
                **options(self.engine, self._fits[fit_id])}

    def rack_options(self, fit_id):
        from .ordering import details
        self.engine._check_thread()
        if not self._available:
            raise RuntimeError("Restart the fitting engine")
        return {"version": 1, "fit_id": fit_id, "revision": self._revisions[fit_id],
                **details(self.engine, self._fits[fit_id])}

    @staticmethod
    def _validate_graph(graph, dataset_identity, settings):
        try:
            _object(graph, ("format", "dataset_identity", "eos_settings", "sample_id", "fit_order", "records", "revisions"), ("modified", "recent"))
            if "recent" in graph:
                recent = graph["recent"]
                if type(recent) is not list or len(recent) > 20:
                    _invalid()
                for identity in recent:
                    _integer(identity, 1, 2**31 - 1)
                if len(recent) != len(set(recent)):
                    _invalid()
            if type(graph["format"]) is not int or graph["format"] not in (1, 2):
                raise StoreError("Saved fits use an unsupported graph format")
            if graph["dataset_identity"] != dataset_identity or _json(graph["eos_settings"]) != _json(settings):
                raise StoreError("Saved fits require a different game dataset or calculation settings")
            order = graph["fit_order"]
            if type(order) is not list or not order and graph["format"] == 1:
                _invalid()
            if graph["format"] == 2 and order:
                _invalid()
            for key in order:
                _text(key, True)
            if len(set(order)) != len(order):
                _invalid()
            _object(graph["records"], order)
            _object(graph["revisions"], order)
            if "modified" in graph:
                _object(graph["modified"], order)
                for value in graph["modified"].values():
                    _integer(value)
            if order:
                _text(graph["sample_id"], True)
                if graph["sample_id"] not in order:
                    _invalid()
            elif graph["sample_id"] is not None:
                _invalid()
            for key in order:
                _integer(graph["revisions"][key], 1)
                record = graph["records"][key]
                _object(record, ("spec", "skills", "implants", "projections", "commands"))
                _spec(record["spec"])
                if type(record["skills"]) is not dict:
                    _invalid()
                for name, level in record["skills"].items():
                    _text(name)
                    if level is not None:
                        _integer(level, 0, 5)
                slots = set()
                if type(record["implants"]) is not list:
                    _invalid()
                for implant in record["implants"]:
                    _object(implant, ("name", "slot", "active"))
                    _text(implant["name"])
                    _integer(implant["slot"], 1, 2**31 - 1)
                    _boolean(implant["active"])
                    if implant["slot"] in slots:
                        _invalid()
                    slots.add(implant["slot"])
                for kind in ("projections", "commands"):
                    if type(record[kind]) is not list:
                        _invalid()
                    sources = set()
                    for edge in record[kind]:
                        _object(edge, ("source_id", "active", "range_m", "amount") if kind == "projections" else ("source_id", "active"))
                        _text(edge["source_id"], True)
                        _boolean(edge["active"])
                        if edge["source_id"] not in order or edge["source_id"] in sources:
                            _invalid()
                        sources.add(edge["source_id"])
                        if kind == "projections":
                            _integer(edge["amount"], 1, 2**31 - 1)
                            if edge["range_m"] is not None:
                                _number(edge["range_m"])
                                if edge["range_m"] < 0:
                                    _invalid()
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            raise StoreError("Saved fits have invalid graph inputs; their file has been preserved") from error

    def _write_and_confirm(self, attempt):
        write_error = None
        try:
            self._store.write(attempt)
        except Exception as error:
            # A commit may have succeeded before an I/O exception was reported.
            # Only a fresh read can distinguish the exact old/new generations.
            write_error = error
        try:
            outcome = self._store.confirm(attempt)
        except Exception as error:
            raise StoreUncertain("Cannot confirm the saved fit commit; reopen the app") from error
        if outcome == "old":
            raise StoreWriteRejected("The edit could not be saved; previous saved fits are intact") from write_error
        return outcome

    def get_fit(self, logical_id):
        self.engine._check_thread()
        if not self._available:
            raise RuntimeError("The fitting engine is unavailable")
        return self._fits[logical_id]

    def bootstrap(self):
        self.engine._check_thread()
        if not self._available:
            return self._error("bootstrap", "ENGINE_UNAVAILABLE", "Restart the app to recover the fitting engine")
        return self._serialize_success("bootstrap", list(self._snapshots.values()))

    def _error(self, request_id, code, message):
        return _json({"version": 1, "request_id": request_id, "session_id": self.session_id,
                      "status": "error", "fits": [], "error": {"code": code, "message": message}})

    def _serialize_success(self, request_id, fits):
        return _json({"version": 1, "request_id": request_id, "session_id": self.session_id,
                      "status": "ok", "fits": fits, "error": None})

    def _request(self, text):
        request = json.loads(text, object_pairs_hook=_pairs,
                             parse_constant=lambda value: _invalid("Nonfinite numbers are not allowed"))
        _object(request, ("version", "request_id", "session_id", "operation", "expected_revisions", "arguments"))
        _integer(request["version"])
        if request["version"] != 1:
            raise ContractError("UNSUPPORTED_VERSION", "Unsupported bridge version")
        _text(request["request_id"], True)
        _text(request["session_id"], True)
        _text(request["operation"])
        revisions = request["expected_revisions"]
        if type(revisions) is not dict:
            _invalid()
        for key, value in revisions.items():
            _text(key, True)
            _integer(value)
        operation, args = request["operation"], request["arguments"]
        if operation not in ARGUMENTS:
            raise ContractError("UNKNOWN_OPERATION", "Unknown bridge operation")
        _object(args, ARGUMENTS[operation])
        if "name" in args:
            _text(args["name"])
            if not args["name"].strip() or len(args["name"]) > 200 or any(ord(c) < 32 for c in args["name"]):
                _invalid("Fit names must contain 1–200 characters without control characters")
        if "resolve_references" in args:
            _boolean(args["resolve_references"])
        if "ignore" in args:
            _boolean(args["ignore"])
        if "item_id" in args:
            _integer(args["item_id"], 1, 2**31 - 1)
        if "charge_id" in args and args["charge_id"] is not None:
            _integer(args["charge_id"], 1, 2**31 - 1)
        if "position" in args:
            _integer(args["position"], 0, 2**31 - 1)
        if "main_position" in args:
            _integer(args["main_position"], 0, 2**31 - 1)
        if "scope" in args:
            _text(args["scope"])
            if args["scope"] not in ("SELECTED", "SIMILAR"):
                _invalid()
        if "context" in args:
            _text(args["context"])
            if args["context"] not in ("module", "drone", "implant"):
                _invalid()
        if "spec" in args:
            _spec(args["spec"])
        for key in ("fit_id", "source_id", "target_id"):
            if key in args:
                _text(args[key], True)
        if "fit_ids" in args:
            if type(args["fit_ids"]) is not list:
                _invalid()
            for value in args["fit_ids"]:
                _text(value, True)
            if len(set(args["fit_ids"])) != len(args["fit_ids"]):
                _invalid()
        if "module_indices" in args:
            if type(args["module_indices"]) is not list:
                _invalid()
            for value in args["module_indices"]:
                _integer(value)
        for key in ("charge", "skill", "implant", "state"):
            if key in args and not (key == "charge" and args[key] is None):
                _text(args[key])
        if "state" in args and args["state"] not in STATES:
            _invalid()
        for key in ("level", "slot", "amount"):
            if key in args:
                _integer(args[key], 0, 5 if key == "level" else 2**31 - 1)
        if "active" in args:
            _boolean(args["active"])
        if "range_m" in args and args["range_m"] is not None:
            _number(args["range_m"])
        if request["session_id"] != self.session_id:
            raise ContractError("REVISION_CONFLICT", "The engine session has changed; reload the fit")
        named = {args[key] for key in ("fit_id", "source_id", "target_id") if key in args}
        references = named | set(args.get("fit_ids", []))
        if references - self._fits.keys():
            raise ContractError("UNKNOWN_FIT", "A requested fit no longer exists")
        if set(revisions) != named:
            _invalid("Revision keys must match the operation's fit IDs")
        if any(revisions[key] != self._revisions[key] for key in named):
            raise ContractError("REVISION_CONFLICT", "The fit changed; reload it before editing")
        if operation == "delete_fit" and not args["resolve_references"]:
            deleted = args["fit_id"]
            if any(record[kind] if key == deleted else
                   any(edge["source_id"] == deleted for edge in record[kind])
                   for key, record in self._records.items() for kind in ("projections", "commands")):
                raise ContractError("INVALID_EDIT", "Confirm removal of this fit's references")
        return request, named

    def dispatch(self, request_json):
        request_id = None
        # Recover a valid correlation ID even when another envelope field fails.
        try:
            envelope = json.loads(request_json, object_pairs_hook=_pairs)
            candidate = envelope.get("request_id") if type(envelope) is dict else None
            if type(candidate) is str and 0 < len(candidate) <= 128:
                request_id = candidate
        except (ValueError, TypeError, OverflowError, RecursionError):
            pass
        if not self._available:
            return self._error(request_id, "ENGINE_UNAVAILABLE", "Restart the app to recover the fitting engine")
        try:
            self.engine._check_thread()
        except RuntimeError:
            return self._error(request_id, "ENGINE_ERROR", "Use the serialized engine worker")
        try:
            request, named = self._request(request_json)
        except ContractError as error:
            return self._error(request_id, error.code, str(error))
        except (ValueError, TypeError, OverflowError, RecursionError):
            return self._error(request_id, "INVALID_REQUEST", "Malformed bridge request")
        operation, args = request["operation"], request["arguments"]
        from .fitting import FittingRejected, promote
        editing = False
        durable_confirmed = False
        try:
            if operation == "snapshot":
                selected = args["fit_ids"] or list(self._fits)
                snapshots = self._snapshots_for(self._fits, self._revisions, selected)
                return self._serialize_success(request_id, list(snapshots.values()))
            fits = dict(self._fits)
            recent = list(self._recent)
            specs = {key: value["spec"] for key, value in self._records.items()}
            editing = True
            if operation == "create_fit":
                logical_id = uuid.uuid4().hex
                fits[logical_id] = self.engine.create_fit(args["spec"])
                specs[logical_id] = deepcopy(args["spec"])
                named = {logical_id}
            elif operation == "rename_fit":
                fits[args["fit_id"]].name = args["name"]
                specs[args["fit_id"]] = {**specs[args["fit_id"]], "name": args["name"]}
            elif operation == "duplicate_fit":
                logical_id = uuid.uuid4().hex
                record = deepcopy(self._records[args["fit_id"]])
                record["spec"]["name"] = args["name"]
                copy = fits[logical_id] = self.engine.create_fit(record["spec"], restore=True)
                specs[logical_id] = record["spec"]
                for name, level in record["skills"].items():
                    copy.character.getSkill(name).setLevel(level, persist=True, ignoreRestrict=True)
                for implant in record["implants"]:
                    self.engine.add_implant(copy, implant["name"], active=implant["active"])
                self.engine._recalculate(copy)
                for edge in record["projections"]:
                    self.engine.add_projection(fits[edge["source_id"]], copy,
                        **{key: value for key, value in edge.items() if key != "source_id"})
                for edge in record["commands"]:
                    self.engine.add_command(fits[edge["source_id"]], copy, active=edge["active"])
                named = {logical_id}
            elif operation == "delete_fit":
                deleted = args["fit_id"]
                linked = any(record[kind] if key == deleted else
                    any(edge["source_id"] == deleted for edge in record[kind])
                    for key, record in self._records.items() for kind in ("projections", "commands"))
                if linked and not args["resolve_references"]:
                    raise ValueError("Confirm removal of this fit's references")
                for target, record in self._records.items():
                    for kind, method in (("projections", self.engine.remove_projection), ("commands", self.engine.remove_command)):
                        for edge in record[kind]:
                            if target == deleted or edge["source_id"] == deleted:
                                method(fits[edge["source_id"]], fits[target])
                removed = fits.pop(deleted)
                self._session.delete(removed)
                self.engine._fits.remove(removed)
                specs.pop(deleted)
            else:
                used = self._apply(operation, args, fits)
                if operation in {"add_module", "replace_module", "remove_module"} and used:
                    recent = promote(self.engine, recent, used)
            editing = False
            records = self._capture(fits, specs)
            modified = {key: self._modified.get(key, 0) for key in records}
            changed_inputs = [key for key in records if records[key] != self._records.get(key)]
            if changed_inputs:
                sequence = max(self._modified.values(), default=0) + 1
                _integer(sequence)
                for key in changed_inputs:
                    modified[key] = sequence
            affected = self._affected(named, self._records, records) & fits.keys()
            revisions = {key: value for key, value in self._revisions.items() if key in fits}
            for key in affected:
                revisions[key] = revisions.get(key, 0) + 1
                if revisions[key] > 2**63 - 1:
                    raise ValueError("Fit revision limit reached")
            # Clear the entire dependent set first, so recursion never reads a
            # transitively stale fit merely because it precedes its source.
            for key in fits:
                if key in affected:
                    fits[key].clear()
            if operation in {"rename_fit", "duplicate_fit", "delete_fit"}:
                # Relationship refresh during copy/removal can invalidate sources
                # outside the edited set. Replay the candidate graph exactly as
                # restart does before publishing its complete library snapshot.
                fits, snapshots = self._rebuild(records, revisions)
            else:
                snapshots = self._snapshots_for(fits, revisions, [key for key in fits if key in affected])
            all_snapshots = {key: snapshots.get(key, self._snapshots.get(key)) for key in fits}
            # Lifecycle operations return the complete surviving library. Other
            # operations retain the B01 affected-snapshots response contract.
            library_operation = operation in {"rename_fit", "duplicate_fit", "delete_fit"}
            result = self._serialize_success(request_id, list(all_snapshots.values() if library_operation else snapshots.values()))
            provenance = dict(self.engine.resolved_item_ids)
            attempt = self._store.prepare(self._graph(records, revisions, modified, recent)) if self._store else None
            import eos.db
            eos.db.saveddata_session.commit()
            if attempt is not None:
                if self._write_and_confirm(attempt) != "new":
                    raise StoreWriteRejected("The edit could not be saved; the previous saved fits are intact")
                durable_confirmed = True
                self._store.accept(attempt)
            self._fits, self._records, self._revisions = fits, records, revisions
            self._modified = modified
            self._recent = recent
            self._snapshots = all_snapshots
            self.sample_id = self.sample_id if self.sample_id in fits else next(iter(fits), None)
            self._provenance = provenance
            return result
        except Exception as error:
            if durable_confirmed or isinstance(error, StoreUncertain):
                self._available = False
                return self._error(request_id, "ENGINE_UNAVAILABLE", "Saved fit state needs to be reopened; restart the app")
            code = "INVALID_EDIT" if editing and isinstance(error, ValueError) else "ENGINE_ERROR"
            try:
                self._recover()
            except Exception:
                self._available = False
                return self._error(request_id, "ENGINE_UNAVAILABLE", "Restart the app to recover the fitting engine")
            if isinstance(error, FittingRejected):
                # Desktop records valid-item attempts even when legality rejects
                # the fit mutation. Fit inputs, values and revisions stay intact.
                recent = promote(self.engine, self._recent, [error.item_id])
                if recent != self._recent:
                    history_confirmed = False
                    try:
                        if self._store:
                            attempt = self._store.prepare(self._graph(self._records, self._revisions, recent=recent))
                            if self._write_and_confirm(attempt) != "new":
                                raise StoreWriteRejected("The attempt could not be saved; previous fits and recent use are intact")
                            history_confirmed = True
                            self._store.accept(attempt)
                        self._recent = recent
                    except StoreUncertain:
                        self._available = False
                        return self._error(request_id, "ENGINE_UNAVAILABLE", "Restart the app to confirm saved recent use")
                    except Exception:
                        if history_confirmed:
                            self._available = False
                            return self._error(request_id, "ENGINE_UNAVAILABLE", "Restart the app to reopen saved recent use")
                        return self._error(request_id, "ENGINE_ERROR", "The attempt could not be saved; previous fits and recent use are intact")
                return self._error(request_id, "INVALID_EDIT", str(error))
            message = "The edit is not supported by this fit" if code == "INVALID_EDIT" else "The engine could not complete the request"
            if isinstance(error, StoreWriteRejected):
                message = str(error)
            return self._error(request_id, code, message)

    def _apply(self, operation, args, fits):
        if "source_id" in args:
            positional = (fits[args["source_id"]], fits[args["target_id"]])
            kwargs = {key: value for key, value in args.items() if key not in ("source_id", "target_id")}
            return getattr(self.engine, operation)(*positional, **kwargs)
        fit = fits[args["fit_id"]]
        from . import fitting
        if operation == "add_module":
            return fitting.add(self.engine, fit, args["item_id"])
        if operation == "replace_module":
            return fitting.replace(self.engine, fit, args["position"], args["item_id"])
        if operation == "remove_module":
            return fitting.remove(self.engine, fit, args["position"])
        if operation == "set_fit_restrictions":
            return fitting.restrictions(self.engine, fit, args["ignore"])
        if operation == "set_charges":
            return self.engine.set_charges(fit, args["module_indices"], args["charge"])
        if operation == "set_module_charge":
            from .charges import change
            return change(self.engine, fit, args["position"], args["charge_id"])
        if operation == "set_bulk_charges":
            from .bulk import change_charges
            return change_charges(self.engine, fit, args["main_position"], args["module_indices"], args["scope"], args["charge_id"])
        if operation == "change_variation":
            from .variations import change
            return change(self.engine, fit, args["context"], args["position"], args["item_id"])
        if operation == "swap_modules":
            from .ordering import swap
            return swap(self.engine, fit, args["from_position"], args["to_position"])
        if operation == "set_module_states":
            return self.engine.set_module_states(fit, args["module_indices"], args["state"])
        if operation == "set_skill_level":
            return self.engine.set_skill_level(fit, args["skill"], args["level"])
        if operation == "add_implant":
            return self.engine.add_implant(fit, args["implant"], active=args["active"])
        if operation == "set_implant_active":
            return self.engine.set_implant_active(fit, args["slot"], args["active"])
        return self.engine.remove_implant(fit, args["slot"])

    @staticmethod
    def _affected(named, before, after):
        affected = set(named)
        edges = [(edge["source_id"], target) for records in (before, after)
                 for target, record in records.items() for kind in ("projections", "commands") for edge in record[kind]]
        while True:
            expanded = affected | {target for source, target in edges if source in affected}
            if expanded == affected:
                return affected
            affected = expanded

    def _capture(self, fits, specs):
        logical = {fit.ID: key for key, fit in fits.items()}
        records = {}
        for key, fit in fits.items():
            spec = deepcopy(specs[key])
            from eos.const import FittingSlot
            spec["modules"] = [({"empty_slot": FittingSlot(module.slot).name} if module.isEmpty else
                                {"name": module.item.name, "charge": module.charge.name if module.charge else None,
                                 "state": _module_state(module)}) for module in fit.modules]
            spec["drones"] = [{"name": drone.item.name, "amount": drone.amount, "active": drone.amountActive}
                              for drone in fit.drones]
            if "ignore_restrictions" in spec or fit.ignoreRestrictions or any(module.isEmpty for module in fit.modules):
                spec["ignore_restrictions"] = fit.ignoreRestrictions
            skills = {skill.item.name: skill.activeLevel for skill in fit.character.skills
                      if skill.activeLevel != spec["skill_level"]}
            # EOS edits activeLevel while SQL maps the saved level. Commit the
            # actual state so a later ORM refresh cannot discard valid edits.
            for skill in fit.character.skills:
                skill.saveLevel()
            projections, commands = [], []
            for source in fit.projectedFitDict.values():
                info = source.getProjectionInfo(fit.ID)
                projections.append({"source_id": logical[source.ID], "range_m": info.projectionRange,
                                    "active": info.active, "amount": info.amount})
            for source in fit.commandFitDict.values():
                info = source.getCommandInfo(fit.ID)
                commands.append({"source_id": logical[source.ID], "active": info.active})
            records[key] = {"spec": spec, "skills": skills,
                            "implants": [{"name": implant.item.name, "slot": implant.slot, "active": implant.active}
                                         for implant in fit.implants],
                            "projections": sorted(projections, key=lambda edge: edge["source_id"]),
                            "commands": sorted(commands, key=lambda edge: edge["source_id"])}
        return records

    def _snapshots_for(self, fits, revisions, selected):
        from eos.const import FittingSlot
        result = {}
        logical = {fit.ID: key for key, fit in fits.items()}
        # EOS command-mode recursion marks a previously cold source calculated
        # before applying that source's own local burst bonuses. Warm sources
        # locally before their recipients, regardless of library insertion order.
        prepared, visiting = set(), set()
        def prepare(key):
            if key in prepared or key in visiting:
                return
            visiting.add(key)
            fit = fits[key]
            for source in list(fit.projectedFitDict.values()) + list(fit.commandFitDict.values()):
                prepare(logical[source.ID])
            if not fit.calculated:
                fit.calculateModifiedAttributes()
            visiting.remove(key)
            prepared.add(key)
        for key in selected:
            prepare(key)
        for key in selected:
            fit = fits[key]
            stats = self.engine.projection_snapshot(fit)
            for statistic in stats.values():
                value = statistic["value"]
                if (set(statistic) != {"value", "unit"} or type(statistic["unit"]) is not str or
                        value is not None and type(value) not in (str, bool, int, float) or
                        type(value) is float and not math.isfinite(value) or
                        type(value) is int and not -(2**63) <= value < 2**63):
                    raise RuntimeError("The engine returned an invalid statistic")
            spec = self._records[key]["spec"] if key in self._records else None
            default_level = spec["skill_level"] if spec else fit.character.defaultLevel
            projections, commands = [], []
            for source in fit.projectedFitDict.values():
                info = source.getProjectionInfo(fit.ID)
                projections.append({"source_id": logical[source.ID], "range_m": info.projectionRange,
                                    "active": info.active, "amount": info.amount})
            for source in fit.commandFitDict.values():
                commands.append({"source_id": logical[source.ID], "active": source.getCommandInfo(fit.ID).active})
            result[key] = {"id": key, "revision": revisions[key], "name": fit.name, "ship": fit.ship.item.name,
                           "stats": stats,
                           "modules": [({"index": index, "empty_slot": FittingSlot(module.slot).name}
                                        if module.isEmpty else {"index": index, "name": module.item.name,
                                        "charge": module.charge.name if module.charge else None, "state": _module_state(module)})
                                       for index, module in enumerate(fit.modules)],
                           "skills": {skill.item.name: skill.activeLevel for skill in fit.character.skills
                                      if skill.activeLevel != default_level},
                           "implants": [{"name": implant.item.name, "slot": implant.slot, "active": implant.active}
                                        for implant in fit.implants],
                           "projections": sorted(projections, key=lambda edge: edge["source_id"]),
                           "commands": sorted(commands, key=lambda edge: edge["source_id"])}
        return result

    def _reset_storage(self):
        self.engine._check_thread()
        import eos.db
        from eos.db.saveddata import queries
        if (str(eos.db.saveddata_engine.url) != "sqlite:///:memory:" or
                eos.db.saveddata_session is not self._session):
            raise RuntimeError("Recovery requires the original in-memory session")
        session = eos.db.saveddata_session
        session.rollback()
        session.expunge_all()
        self.engine._fits.clear()
        self._fits = {}
        for cache in getattr(queries, "itemCache", {}).values():
            cache.clear()
        for functions in getattr(queries, "queryCache", {}).values():
            for cache in functions.values():
                cache.clear()
        for table in reversed(eos.db.saveddata_meta.sorted_tables):
            session.execute(table.delete())
        self.engine.resolved_item_ids.clear()

    def _rebuild(self, records=None, revisions=None):
        records = self._records if records is None else records
        revisions = self._revisions if revisions is None else revisions
        self._reset_storage()
        fits = {}
        for key, record in records.items():
            fit = fits[key] = self.engine.create_fit(record["spec"], restore=True)
            for name, level in record["skills"].items():
                fit.character.getSkill(name).setLevel(level, persist=True, ignoreRestrict=True)
            for implant in record["implants"]:
                self.engine.add_implant(fit, implant["name"], active=implant["active"])
            self.engine._recalculate(fit)
        for target, record in records.items():
            for edge in record["projections"]:
                self.engine.add_projection(fits[edge["source_id"]], fits[target],
                                           **{key: value for key, value in edge.items() if key != "source_id"})
            for edge in record["commands"]:
                self.engine.add_command(fits[edge["source_id"]], fits[target], active=edge["active"])
        for fit in fits.values():
            fit.clear()
        snapshots = self._snapshots_for(fits, revisions, fits)
        return fits, snapshots

    def _recover(self):
        fits, snapshots = self._rebuild()
        if _json(snapshots) != _json(self._snapshots):
            raise RuntimeError("Recovered fits do not match the last committed state")
        import eos.db
        eos.db.saveddata_session.commit()
        self._fits = fits
        self.engine.resolved_item_ids.clear()
        self.engine.resolved_item_ids.update(self._provenance)
