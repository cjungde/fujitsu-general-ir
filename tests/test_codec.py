"""Round-trip tests for the Fujitsu General codec.

Import paths and the ``infrared_protocols`` dependency are set up in
``conftest.py``. Run with: ``pytest tests/``.
"""

from __future__ import annotations

import itertools

from codec import (
    STATE_LEN,
    TEMP_MAX,
    TEMP_MIN,
    Fan,
    FujitsuCommand,
    FujitsuState,
    Mode,
    Swing,
    _bytes_to_signed_timings,
    _checksum_state,
    _set_nibble,
    decode,
    encode_bytes,
)


def test_full_state_round_trip() -> None:
    """Encode then decode every reachable state and compare."""
    count = 0
    for temp, mode, fan, swing in itertools.product(
        range(TEMP_MIN, TEMP_MAX + 1), Mode, Fan, Swing
    ):
        state = FujitsuState(True, temp, mode, fan, swing)
        timings = FujitsuCommand(state).get_raw_timings()
        assert decode(timings) == state
        count += 1
    assert count == 1500


def test_off_round_trip() -> None:
    """The off frame round-trips."""
    off = FujitsuState(power=False)
    assert decode(FujitsuCommand(off).get_raw_timings()) == off


def test_unknown_mode_does_not_raise() -> None:
    """A checksum-valid frame with an unmapped mode (e.g. 0x0B) decodes safely."""
    base = FujitsuState(True, 24, Mode.AUTO, Fan.AUTO, Swing.NONE)
    raw = bytearray(encode_bytes(base))
    raw[9] = 0  # clear mode nibble (byte9 low)
    _set_nibble(raw, 19, 0x0B)  # Fujitsu 10 °C mode, not modelled here
    raw[STATE_LEN - 1] = _checksum_state(bytes(raw))
    state = decode(_bytes_to_signed_timings(bytes(raw)))
    assert state is not None
    assert state.mode == Mode.AUTO  # safe fallback, no ValueError


def test_signed_timings() -> None:
    """Marks are positive, spaces negative, and they alternate."""
    timings = FujitsuCommand(FujitsuState()).get_raw_timings()
    assert all(t > 0 for t in timings[0::2])
    assert all(t < 0 for t in timings[1::2])
