"""Tests for the HA-agnostic climate<->codec mapping.

These exercise the value mappings and command building without importing Home
Assistant, so they run even before the core ``infrared`` integration ships.
"""

from __future__ import annotations

import itertools

import mapping
from codec import decode


def test_off_command_decodes_as_power_off() -> None:
    cmd = mapping.build_command(
        hvac_mode=mapping.MODE_OFF,
        temperature=22,
        fan_mode=mapping.FAN_AUTO,
        swing_mode=mapping.SWING_OFF,
        was_on=True,
    )
    state = decode(cmd.get_raw_timings())
    assert state is not None
    assert state.power is False


def test_build_decode_attrs_round_trip() -> None:
    """Every climate combo encodes, decodes and maps back to the same values."""
    hvac_modes = [
        mapping.MODE_HEAT_COOL,
        mapping.MODE_COOL,
        mapping.MODE_HEAT,
        mapping.MODE_DRY,
        mapping.MODE_FAN_ONLY,
    ]
    count = 0
    for hvac, temp, fan, swing in itertools.product(
        hvac_modes, (18, 24, 30), mapping.FAN_MODES, mapping.SWING_MODES
    ):
        cmd = mapping.build_command(
            hvac_mode=hvac,
            temperature=temp,
            fan_mode=fan,
            swing_mode=swing,
            was_on=True,
        )
        state = decode(cmd.get_raw_timings())
        assert state is not None
        attrs = mapping.attrs_from_state(state)
        assert attrs == {
            "hvac_mode": hvac,
            "temperature": temp,
            "fan_mode": fan,
            "swing_mode": swing,
        }
        count += 1
    assert count == 5 * 3 * 5 * 4


def test_attrs_from_state_off() -> None:
    cmd = mapping.build_command(
        hvac_mode=mapping.MODE_OFF,
        temperature=22,
        fan_mode=mapping.FAN_AUTO,
        swing_mode=mapping.SWING_OFF,
        was_on=False,
    )
    state = decode(cmd.get_raw_timings())
    assert state is not None
    assert mapping.attrs_from_state(state) == {"hvac_mode": mapping.MODE_OFF}


def test_temperature_is_truncated_to_int() -> None:
    cmd = mapping.build_command(
        hvac_mode=mapping.MODE_COOL,
        temperature=23.6,
        fan_mode=mapping.FAN_AUTO,
        swing_mode=mapping.SWING_OFF,
        was_on=True,
    )
    state = decode(cmd.get_raw_timings())
    assert state is not None
    assert state.temperature == 23
