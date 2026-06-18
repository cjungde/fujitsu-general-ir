"""Round-trip tests for the Fujitsu General codec.

Requires ``infrared_protocols`` to be importable (it ships with the Home
Assistant ``infrared`` integration). Run with: ``pytest tests/``.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "fujitsu_general_ir")
)

from codec import (  # noqa: E402
    TEMP_MAX,
    TEMP_MIN,
    Fan,
    FujitsuCommand,
    FujitsuState,
    Mode,
    Swing,
    decode,
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


def test_signed_timings() -> None:
    """Marks are positive, spaces negative, and they alternate."""
    timings = FujitsuCommand(FujitsuState()).get_raw_timings()
    assert all(t > 0 for t in timings[0::2])
    assert all(t < 0 for t in timings[1::2])
