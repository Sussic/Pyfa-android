"""C06 host model: profile identity and fit bindings in one atomic ledger.

This is an isolated prerequisite, not the existing Android fit-store schema.
It refuses other payloads and never migrates/overwrites an existing fit graph.
The caller must later integrate profile inputs and calculations in one graph
transaction before publishing native fit snapshots. No calculated values live here.
"""
from copy import deepcopy
from dataclasses import dataclass
import re
import threading
import uuid
import unicodedata

from .profile_store import GraphStore, StoreError, StoreUncertain, StoreWriteRejected, decode_graph

ALL_ZERO = 'builtin:all0'
ALL_FIVE = 'builtin:all5'
BUILTINS = {
    ALL_ZERO: dict(name='All 0', default_level=None, levels={}, revision=0, implants=[], sec_status=0.0),
    ALL_FIVE: dict(name='All 5', default_level=5, levels={}, revision=0, implants=[], sec_status=5.0),
}


class ProfileError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise ProfileError(code, message)


def advance(value):
    require(type(value) is int and 0 <= value < 2**63 - 1, 'revision', 'Profile revision limit reached')
    return value + 1


def level(value):
    require(value is None or (type(value) is int and 0 <= value <= 5),
            'invalid_level', 'Skill level must be unlearned (null) or an integer from 0 to 5')


def name(value, *, legacy=False):
    require(type(value) is str and value == value.strip() and 0 < len(value) <= 200
            and all((ord(c) >= 32 if legacy else unicodedata.category(c) != 'Cc') and not 0xD800 <= ord(c) <= 0xDFFF for c in value), 'invalid_name', 'Invalid profile name')
    require(value.casefold() not in ('all 0', 'all 5'), 'protected', 'Built-in names are reserved')


@dataclass(frozen=True)
class Draft:
    """Detached edits stay live across selection changes until explicitly saved/reverted."""
    owner: object
    profile_id: str
    base_revision: int
    values: dict


class Profiles:
    def __init__(self, path, dataset_sha256, skill_ids, *, store_type=GraphStore):
        require(type(dataset_sha256) is str and re.fullmatch('[0-9a-f]{64}', dataset_sha256),
                'dataset', 'Expected a pinned dataset SHA256')
        skill_ids = tuple(skill_ids)
        require(skill_ids and all(type(i) is int and i > 0 for i in skill_ids)
                and len(set(skill_ids)) == len(skill_ids), 'catalog', 'Invalid skill catalogue')
        self.dataset = dataset_sha256
        self.skill_ids = frozenset(str(i) for i in skill_ids)
        self._owner = object()
        self._thread = threading.get_ident()
        self._disabled = False
        self.store = store_type(path)
        if self.store.current:
            self._state = decode_graph(self.store.current.payload)
            self._validate(self._state)
            if self._state['format'] < 3:
                self._state = deepcopy(self._state)
                self._state['format'] = 3
                for identity, record in self._state['profiles'].items():
                    record.setdefault('implants', [])
                    record['sec_status'] = BUILTINS[identity]['sec_status'] if identity in BUILTINS else 0.0
        else:
            self._state = None
            self._commit(dict(kind='pyfa.offline-profiles', format=3, dataset=dataset_sha256,
                              profiles=deepcopy(BUILTINS), bindings={}, default_profile=ALL_FIVE))

    def _ready(self):
        require(threading.get_ident() == self._thread, 'thread', 'Use the serialized owning worker')
        require(not self._disabled, 'reopen_required', 'Commit outcome uncertain; reopen the ledger')

    def _validate_profile(self, record, *, legacy=False, security=True):
        require(type(record) is dict and set(record) == ({'name', 'default_level', 'levels', 'revision'} | (set() if legacy else {'implants'}) | ({'sec_status'} if security else set())),
                'format', 'Unsupported profile fields')
        if security:
            from android_bridge.pilot_security import number
            number(record['sec_status'])
        if not legacy:
            from android_bridge.character_implants import validate
            validate(record['implants'])
        level(record['default_level'])
        require(type(record['revision']) is int and 0 <= record['revision'] < 2**63,
                'revision', 'Invalid profile revision')
        require(type(record['levels']) is dict and record['levels'].keys() <= self.skill_ids,
                'skill', 'Unknown or invalid skill identity')
        for value in record['levels'].values():
            level(value)

    def _validate(self, state):
        require(type(state) is dict and set(state) == {
            'kind', 'format', 'dataset', 'profiles', 'bindings', 'default_profile'},
            'format', 'Unsupported ledger; original data is preserved')
        require(state['kind'] == 'pyfa.offline-profiles' and type(state['format']) is int
                and state['format'] in (1, 2, 3), 'format', 'Unsupported ledger version')
        require(state['dataset'] == self.dataset, 'dataset', 'Dataset mismatch; explicit migration required')
        records = state['profiles']
        require(type(records) is dict and BUILTINS.keys() <= records.keys(), 'format', 'Missing built-in profiles')
        seen_implants = set()
        for identity, record in records.items():
            self._validate_profile(record, legacy=state['format'] == 1, security=state['format'] == 3)
            ids = {row['implant_id'] for row in record.get('implants', [])}
            require(not seen_implants & ids, 'identity', 'Character implant identity reused across profiles')
            seen_implants.update(ids)
            if identity in BUILTINS:
                from .target_profiles import exact
                omitted = ({'sec_status'} if state['format'] < 3 else set()) | ({'implants'} if state['format'] == 1 else set())
                require(exact(record, {k:v for k,v in BUILTINS[identity].items() if k not in omitted}), 'protected', 'Built-in profile was changed')
            else:
                require(type(identity) is str and re.fullmatch('profile:[0-9a-f]{32}', identity),
                        'identity', 'Invalid profile identity')
                # Preserve historically valid names during read-only migration.
                # New/changed names use the stricter publication-safe rule.
                name(record['name'], legacy=True)
                require(record['revision'] >= 1, 'revision', 'Custom profile requires a revision')
        require(type(state['default_profile']) is str and state['default_profile'] in records,
                'reference', 'Default profile is missing')
        require(type(state['bindings']) is dict, 'format', 'Invalid fit bindings')
        for fit_id, binding in state['bindings'].items():
            self._fit_id(fit_id)
            require(type(binding) is dict and set(binding) == {'profile_id', 'revision'},
                    'format', 'Invalid fit binding')
            require(type(binding['profile_id']) is str and binding['profile_id'] in records,
                    'reference', 'Fit references a missing profile')
            require(type(binding['revision']) is int and 1 <= binding['revision'] < 2**63,
                    'revision', 'Invalid binding revision')

    def _commit(self, candidate):
        self._ready()
        self._validate(candidate)
        attempt = self.store.prepare(candidate)
        try:
            self.store.write(attempt)
        except Exception:
            # A commit can succeed before acknowledgement fails. Always fresh-read.
            pass
        try:
            outcome = self.store.confirm(attempt)
        except Exception:
            self._disabled = True
            raise
        if outcome != 'new':
            raise StoreWriteRejected('Profile changes were not committed; edits remain unsaved')
        self.store.accept(attempt)
        self._state = candidate

    def snapshot(self):
        self._ready()
        return deepcopy(self._state)

    def _profile(self, profile_id, *, editable=False):
        self._ready()
        require(type(profile_id) is str and profile_id in self._state['profiles'],
                'missing_profile', 'Unknown profile identity')
        require(not editable or profile_id not in BUILTINS, 'protected', 'Built-in profiles are read-only')
        return self._state['profiles'][profile_id]

    @staticmethod
    def _fit_id(fit_id):
        require(type(fit_id) is str and 0 < len(fit_id) <= 200 and fit_id == fit_id.strip()
                and all(ord(c) >= 32 for c in fit_id), 'identity', 'Invalid fit identity')

    def _result(self, profile_id, affected):
        return dict(profile_id=profile_id, affected_fits=sorted(affected), ledger=self.snapshot())

    def create(self, profile_name, *, source=ALL_ZERO):
        record = deepcopy(self._profile(source))
        name(profile_name)
        from android_bridge.character_implants import copied
        record['implants'] = copied(record['implants'])
        record.update(name=profile_name, revision=1)
        identity = 'profile:' + uuid.uuid4().hex
        candidate = self.snapshot()
        candidate['profiles'][identity] = record
        self._commit(candidate)
        return self._result(identity, [])

    def begin(self, profile_id):
        record = self._profile(profile_id, editable=True)
        return Draft(self._owner, profile_id, record['revision'], deepcopy(record))

    def revert(self, draft):
        self._ready()
        require(type(draft) is Draft and draft.owner is self._owner, 'draft', 'Draft belongs to another session')
        return self.begin(draft.profile_id)

    def _draft(self, draft):
        self._ready()
        require(type(draft) is Draft and draft.owner is self._owner, 'draft', 'Draft belongs to another session')
        record = self._profile(draft.profile_id, editable=True)
        require(type(draft.base_revision) is int and draft.base_revision == record['revision'],
                'conflict', 'Profile changed since this draft was opened')
        self._validate_profile(draft.values)
        name(draft.values['name'], legacy=draft.values['name'] == record['name'])
        require(draft.values['revision'] == draft.base_revision, 'revision', 'Draft revision was changed')

    def save(self, draft, *, save_as=None):
        self._draft(draft)
        record = deepcopy(draft.values)
        identity = draft.profile_id
        candidate = self.snapshot()
        if save_as is not None:
            name(save_as)
            from android_bridge.character_implants import copied
            record['implants'] = copied(record['implants'])
            record.update(name=save_as, revision=1)
            identity = 'profile:' + uuid.uuid4().hex
            affected = []
        else:
            if record['sec_status'] == self._profile(identity)['sec_status']:
                record['sec_status'] = self._profile(identity)['sec_status']
            if record == self._profile(identity): return self._result(identity, [])
            record['revision'] = advance(record['revision'])
            affected = [fit for fit, binding in candidate['bindings'].items()
                        if binding['profile_id'] == identity]
            for fit in affected:
                candidate['bindings'][fit]['revision'] = advance(candidate['bindings'][fit]['revision'])
        candidate['profiles'][identity] = record
        self._commit(candidate)
        return self._result(identity, affected)

    def save_security(self, profile_id, revision, sec_status, *, save_as):
        """Change only security, or create a detached complete saved-profile copy."""
        draft = self.begin(profile_id)
        require(type(revision) is int and revision > 0 and revision == draft.base_revision,
                'conflict', 'Profile revision changed')
        from android_bridge.pilot_security import number
        draft.values['sec_status'] = number(sec_status)
        return self.save(draft, save_as=save_as)

    def add_implant(self, profile_id, revision, item_id, replace_implant_id):
        from android_bridge.character_implants import catalogue, row_id
        draft = self.begin(profile_id)
        require(type(revision) is int and revision == draft.base_revision, 'conflict', 'Profile revision changed')
        item, slot = catalogue(item_id)
        rows = draft.values['implants']
        occupant = next((row for row in rows if row['slot'] == slot), None)
        if replace_implant_id is not None: row_id(replace_implant_id)
        require((occupant is None and replace_implant_id is None) or
                (occupant is not None and replace_implant_id == occupant['implant_id']),
                'conflict', 'Character implant occupant changed; reload before replacing')
        if occupant is not None: rows.remove(occupant)
        rows.append(dict(implant_id=uuid.uuid4().hex, item_id=item.ID, slot=slot, active=True))
        return self.save(draft)

    def remove_implant(self, profile_id, revision, implant_id):
        from android_bridge.character_implants import row_id
        row_id(implant_id)
        draft = self.begin(profile_id)
        require(type(revision) is int and revision == draft.base_revision, 'conflict', 'Profile revision changed')
        row = next((row for row in draft.values['implants'] if row['implant_id'] == implant_id), None)
        require(row is not None, 'conflict', 'Character implant no longer exists')
        draft.values['implants'].remove(row)
        return self.save(draft)

    def merge_implants(self, profile_id, revision, item_ids):
        """Original character set semantics in one detached draft and one save."""
        from .implant_sets import items
        draft = self.begin(profile_id)
        require(type(revision) is int and revision == draft.base_revision, 'conflict', 'Profile revision changed')
        incoming = items(item_ids)
        rows = draft.values['implants']
        for info in incoming:
            occupant = next((row for row in rows if row['slot'] == info['slot']), None)
            if occupant is not None: rows.remove(occupant)
            rows.append(dict(implant_id=uuid.uuid4().hex, item_id=info['item_id'], slot=info['slot'], active=True))
        return self.save(draft)

    def bind(self, fit_id, profile_id=None):
        self._ready()
        self._fit_id(fit_id)
        if profile_id is None:
            profile_id = self._state['default_profile']
        self._profile(profile_id)
        candidate = self.snapshot()
        previous = candidate['bindings'].get(fit_id)
        if previous and previous['profile_id'] == profile_id:
            return self._result(profile_id, [])
        candidate['bindings'][fit_id] = dict(profile_id=profile_id,
            revision=advance(previous['revision']) if previous else 1)
        self._commit(candidate)
        return self._result(profile_id, [fit_id])

    def set_default(self, profile_id):
        self._profile(profile_id)
        candidate = self.snapshot()
        candidate['default_profile'] = profile_id
        self._commit(candidate)
        return self._result(profile_id, [])

    def unbind(self, fit_id):
        self._ready()
        self._fit_id(fit_id)
        require(fit_id in self._state['bindings'], 'missing_fit', 'Unknown fit binding')
        candidate = self.snapshot()
        del candidate['bindings'][fit_id]
        self._commit(candidate)
        return self._result(None, [fit_id])

    def delete(self, profile_id, *, replacement=None):
        self._profile(profile_id, editable=True)
        candidate = self.snapshot()
        affected = [fit for fit, binding in candidate['bindings'].items()
                    if binding['profile_id'] == profile_id]
        is_default = candidate['default_profile'] == profile_id
        require(not (affected or is_default) or replacement is not None,
                'in_use', 'Choose a replacement for assigned or default profiles')
        if replacement is not None:
            self._profile(replacement)
            require(replacement != profile_id, 'reference', 'Replacement must survive deletion')
            for fit in affected:
                candidate['bindings'][fit]['profile_id'] = replacement
                candidate['bindings'][fit]['revision'] = advance(candidate['bindings'][fit]['revision'])
            if is_default:
                candidate['default_profile'] = replacement
        del candidate['profiles'][profile_id]
        self._commit(candidate)
        return self._result(replacement, affected)

    def for_fit(self, fit_id):
        self._ready()
        self._fit_id(fit_id)
        require(fit_id in self._state['bindings'], 'missing_fit', 'Unknown fit binding')
        binding = self._state['bindings'][fit_id]
        return dict(binding=deepcopy(binding), profile=deepcopy(self._profile(binding['profile_id'])))
