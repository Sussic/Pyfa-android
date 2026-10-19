"""Bounded time-curve output, using the production JSON numeric semantics.

The ledger is nominal host-layout-equivalent accounting, not Android heap bytes.
Six units per ASCII character cover chunks, references, joined text and byte-copy
coexistence. The strict <=8-fit envelope fits 32768 characters: conservative
empty-array skeleton 1171 + 10 escaped identifiers * 1536 + 41 numeric leaves *
310 = 29241. All admitted numeric request echoes are finite even when integers.
"""
import math
from android_bridge.contract import _json
from android_bridge.projected_drone_admission import AdmissionRejected
from .capacitor_samples import SamplingError

BASE_CHARS = 32768
PAIR_CHARS = 64
MAX_POINTS = 87210


class TimeOutput:
    def __init__(self, reserve, check):
        self.reserve = reserve
        self.check = check
        self.count = 0
        reserve('serialization_unit', BASE_CHARS)
        # Two bounded numeric-token probes, including encoder call scratch.
        # These slots are separate from retained output and wire coexistence.
        reserve('container', 4)
        reserve('output_slot', 8)
        reserve('serialization_unit', 128)

    def _token_length(self, value):
        if type(value) not in (int, float):
            raise SamplingError('invalid_engine_data', 'Invalid remote repair numeric output')
        if type(value) is int:
            # 10**62 needs 206 bits. >206 cannot fit even one 62-char token;
            # do not allocate an unbounded decimal representation to learn that.
            if value.bit_length() > 206:
                raise AdmissionRejected('Remote repair numeric token exceeds wire allowance')
        elif not math.isfinite(value):
            raise SamplingError('invalid_engine_data', 'Nonfinite remote repair output')
        return len(_json(value))

    def append(self, xs, ys, x, y):
        self.check()
        if self.count >= MAX_POINTS:
            raise AdmissionRejected('Remote repair total output ceiling exceeded')
        if self._token_length(x) + self._token_length(y) > 62:
            raise AdmissionRejected('Remote repair numeric pair exceeds wire allowance')
        self.reserve('output_point', 1)
        self.reserve('output_slot', 2)
        self.reserve('serialization_unit', PAIR_CHARS)
        xs.append(x)
        ys.append(y)
        self.count += 1
        self.check()

    def encode(self, result, encoder):
        self.check()
        text = encoder(result)
        if type(text) is not str or len(text) > BASE_CHARS + PAIR_CHARS * self.count:
            raise AdmissionRejected('Remote repair encoded output exceeds reserved bound')
        self.check()
        return text
