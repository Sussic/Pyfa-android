"""Validate effective-state stdout from existing offline command captures.

This is not phone-readiness, data-disable, timing or device-provenance proof.
Those prerequisites remain pending; no commands or observers are introduced.
"""
import hashlib

from c10_collection import CollectionError, _require

LABELS = {'initial', 'contract', 'legacy-1', 'legacy-2', 'duration-edit', 'duration-reopen'}
FIELDS = {'airplane', 'wifi', 'connectivity'}


def check_offline_states(samples, required_hashes, offline_state):
    _require(set(samples) == set(required_hashes) == LABELS, 'Missing or unexpected offline sample')
    for label in LABELS:
        sample, pins = samples[label], required_hashes[label]
        _require(set(sample) == set(pins) == FIELDS, 'Incomplete effective-state evidence')
        for field, raw in sample.items():
            _require(type(raw) is bytes, 'Offline evidence must be original bytes')
            _require(hashlib.sha256(raw).hexdigest() == pins[field], f'{label}/{field} hash differs')
        try:
            offline_state(*(sample[key].decode('utf-8', errors='strict') for key in ('airplane','wifi','connectivity')))
        except (RuntimeError, ValueError, UnicodeError) as error:
            raise CollectionError(f'{label} effective offline state is not proved') from error
    return dict(status='EFFECTIVE_OFFLINE_SAMPLES_CHECKED_PREREQUISITES_PENDING', native_accepted=False,
                checked_samples=len(LABELS), remaining=['phone_readiness_and_data_disable',
                    'prerequisite_deadlines', 'device_and_command_provenance', 'outer_closure', 'owner_acceptance'])
