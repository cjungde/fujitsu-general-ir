"""Fujitsu General IR codec.

Ported 1:1 from ESPHome's ``fujitsu_general`` component (climate_ir). The
protocol is stateful: every frame carries the full state (temperature, mode,
fan, swing) plus a checksum. This module turns a :class:`FujitsuState` into an
``infrared`` :class:`Command` (raw signed timings) and decodes captured timings
back into a state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from infrared_protocols.commands import Command

# --- timings (microseconds) ---
HEADER_MARK, HEADER_SPACE = 3300, 1600
BIT_MARK, ONE_SPACE, ZERO_SPACE = 420, 1200, 420
TRL_MARK, TRL_SPACE = 420, 8000
CARRIER_HZ = 38000

TEMP_MIN, TEMP_MAX = 16, 30

# --- frame layout ---
COMMON = bytes([0x14, 0x63, 0x00, 0x10, 0x10])
MSG_TYPE_BYTE = 5
MSG_TYPE_STATE = 0xFE
MSG_TYPE_OFF = 0x02
STATE_LEN, UTIL_LEN, COMMON_LEN = 16, 7, 6


class Mode(IntEnum):
    """Operating mode nibble values."""

    AUTO = 0x00
    COOL = 0x01
    DRY = 0x02
    FAN = 0x03
    HEAT = 0x04


class Fan(IntEnum):
    """Fan speed nibble values."""

    AUTO = 0x00
    HIGH = 0x01
    MEDIUM = 0x02
    LOW = 0x03
    SILENT = 0x04


class Swing(IntEnum):
    """Swing nibble values."""

    NONE = 0x00
    VERTICAL = 0x01
    HORIZONTAL = 0x02
    BOTH = 0x03


# Nibble order is reversed per byte: even nibble -> high half, odd -> low half.
def _set_nibble(buf: bytearray, nibble: int, value: int) -> None:
    shift = 4 if nibble % 2 == 0 else 0
    buf[nibble // 2] |= (value & 0x0F) << shift


def _get_nibble(buf: bytes, nibble: int) -> int:
    shift = 4 if nibble % 2 == 0 else 0
    return (buf[nibble // 2] >> shift) & 0x0F


def _checksum_state(msg: bytes) -> int:
    return (256 - sum(msg[7 : STATE_LEN - 1])) & 0xFF


def _checksum_util(msg: bytes) -> int:
    return (255 - msg[5]) & 0xFF


def _safe_enum(enum_cls: type, value: int, default):
    """Convert to an enum, falling back to a default for unknown values.

    Real remotes can send nibble values we don't model (e.g. Fujitsu's 10 °C
    mode 0x0B); never raise on a checksum-valid frame.
    """
    try:
        return enum_cls(value)
    except ValueError:
        return default


@dataclass
class FujitsuState:
    """Full AC state carried in a single IR frame."""

    power: bool = True
    temperature: int = 22
    mode: Mode = Mode.AUTO
    fan: Fan = Fan.AUTO
    swing: Swing = Swing.NONE


def encode_bytes(state: FujitsuState, *, was_on: bool = True) -> bytes:
    """Build the raw IR message bytes for a target state."""
    if not state.power:
        m = bytearray(COMMON) + bytes([MSG_TYPE_OFF])
        return bytes(m) + bytes([_checksum_util(bytes(m))])

    m = bytearray(STATE_LEN)
    m[0:5] = COMMON
    m[5] = MSG_TYPE_STATE
    m[6], m[7] = 0x09, 0x30
    m[14] = 0x20

    temp = max(TEMP_MIN, min(TEMP_MAX, int(round(state.temperature))))
    _set_nibble(m, 16, temp - TEMP_MIN)  # temperature -> byte8 high
    if not was_on:  # power-on flag only on off->on transition
        _set_nibble(m, 17, 0x01)  # byte8 low
    _set_nibble(m, 19, int(state.mode))  # byte9 low
    _set_nibble(m, 20, int(state.swing))  # byte10 high
    _set_nibble(m, 21, int(state.fan))  # byte10 low

    m[STATE_LEN - 1] = _checksum_state(bytes(m))
    return bytes(m)


def _bytes_to_signed_timings(msg: bytes) -> list[int]:
    """Convert a message to signed timings (mark > 0, space < 0), LSB-first."""
    t = [HEADER_MARK, -HEADER_SPACE]
    for byte in msg:
        for bit in range(8):  # right-to-left (LSB first)
            t.append(BIT_MARK)
            t.append(-(ONE_SPACE if (byte >> bit) & 1 else ZERO_SPACE))
    t += [TRL_MARK, -TRL_SPACE]
    return t


class FujitsuCommand(Command):
    """An ``infrared`` Command that emits a full Fujitsu General frame."""

    def __init__(self, state: FujitsuState, *, was_on: bool = True) -> None:
        """Initialize from a target state."""
        super().__init__(modulation=CARRIER_HZ, repeat_count=0)
        self._timings = _bytes_to_signed_timings(encode_bytes(state, was_on=was_on))

    def get_raw_timings(self) -> list[int]:
        """Return signed raw timings (positive=mark, negative=space)."""
        return list(self._timings)


def _approx(actual: int, expected: int, tol: float = 0.30) -> bool:
    return abs(actual) <= expected * (1 + tol) and abs(actual) >= expected * (1 - tol)


def decode(timings: list[int]) -> FujitsuState | None:
    """Decode a captured timing list (signed or unsigned) into a state."""
    if len(timings) < 4:
        return None
    if not (_approx(timings[0], HEADER_MARK) and _approx(timings[1], HEADER_SPACE)):
        return None
    i = 2
    out = bytearray(STATE_LEN)

    def read_byte(idx: int) -> tuple[int | None, int]:
        b = 0
        for bit in range(8):
            if idx + 1 >= len(timings):
                return None, idx
            mark, space = timings[idx], timings[idx + 1]
            if _approx(mark, BIT_MARK) and _approx(space, ONE_SPACE):
                b |= 1 << bit
            elif not (_approx(mark, BIT_MARK) and _approx(space, ZERO_SPACE)):
                return None, idx
            idx += 2
        return b, idx

    for byte in range(COMMON_LEN):
        val, i = read_byte(i)
        if val is None:
            return None
        out[byte] = val

    mtype = out[MSG_TYPE_BYTE]
    length = STATE_LEN if mtype == MSG_TYPE_STATE else UTIL_LEN
    for byte in range(COMMON_LEN, length):
        val, i = read_byte(i)
        if val is None:
            return None
        out[byte] = val

    msg = bytes(out[:length])
    chk = _checksum_state(msg) if mtype == MSG_TYPE_STATE else _checksum_util(msg)
    if msg[length - 1] != chk:
        return None

    if mtype == MSG_TYPE_OFF:
        return FujitsuState(power=False)
    if mtype != MSG_TYPE_STATE:
        return None
    return FujitsuState(
        power=True,
        temperature=_get_nibble(msg, 16) + TEMP_MIN,
        mode=_safe_enum(Mode, _get_nibble(msg, 19), Mode.AUTO),
        fan=_safe_enum(Fan, _get_nibble(msg, 21), Fan.AUTO),
        swing=_safe_enum(Swing, _get_nibble(msg, 20), Swing.NONE),
    )
