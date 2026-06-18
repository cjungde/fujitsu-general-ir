"""HA-agnostic mapping between climate values and the Fujitsu codec.

Deliberately free of Home Assistant imports so it can be unit-tested without HA
installed (and without the very new core ``infrared`` integration being
released yet). Climate values are passed as their string forms; ``HVACMode``,
fan and swing modes are ``StrEnum``/str, so the same dicts work whether the
caller passes the enum member or the plain string.
"""

from __future__ import annotations

try:  # package context (Home Assistant)
    from .codec import Fan, FujitsuCommand, FujitsuState, Mode, Swing
except ImportError:  # standalone context (unit tests / scripts)
    from codec import Fan, FujitsuCommand, FujitsuState, Mode, Swing

# --- hvac mode strings (must match homeassistant HVACMode values) ---
MODE_OFF = "off"
MODE_HEAT_COOL = "heat_cool"
MODE_COOL = "cool"
MODE_HEAT = "heat"
MODE_DRY = "dry"
MODE_FAN_ONLY = "fan_only"

HVAC_TO_MODE: dict[str, Mode] = {
    MODE_HEAT_COOL: Mode.AUTO,
    MODE_COOL: Mode.COOL,
    MODE_DRY: Mode.DRY,
    MODE_FAN_ONLY: Mode.FAN,
    MODE_HEAT: Mode.HEAT,
}
MODE_TO_HVAC: dict[Mode, str] = {v: k for k, v in HVAC_TO_MODE.items()}

# --- fan mode strings (match homeassistant climate FAN_* values) ---
FAN_AUTO = "auto"
FAN_LOW = "low"
FAN_MEDIUM = "medium"
FAN_HIGH = "high"
FAN_QUIET = "quiet"

FAN_TO_CODEC: dict[str, Fan] = {
    FAN_AUTO: Fan.AUTO,
    FAN_LOW: Fan.LOW,
    FAN_MEDIUM: Fan.MEDIUM,
    FAN_HIGH: Fan.HIGH,
    FAN_QUIET: Fan.SILENT,
}
CODEC_TO_FAN: dict[Fan, str] = {v: k for k, v in FAN_TO_CODEC.items()}

# --- swing mode strings (match homeassistant climate SWING_* values) ---
SWING_OFF = "off"
SWING_VERTICAL = "vertical"
SWING_HORIZONTAL = "horizontal"
SWING_BOTH = "both"

SWING_TO_CODEC: dict[str, Swing] = {
    SWING_OFF: Swing.NONE,
    SWING_VERTICAL: Swing.VERTICAL,
    SWING_HORIZONTAL: Swing.HORIZONTAL,
    SWING_BOTH: Swing.BOTH,
}
CODEC_TO_SWING: dict[Swing, str] = {v: k for k, v in SWING_TO_CODEC.items()}

FAN_MODES = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_QUIET]
SWING_MODES = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]


def build_command(
    *,
    hvac_mode: str,
    temperature: float,
    fan_mode: str,
    swing_mode: str,
    was_on: bool,
) -> FujitsuCommand:
    """Build the IR command for the requested climate state.

    ``was_on`` is the *previous* power state; it drives the off->on flag.
    """
    if hvac_mode == MODE_OFF:
        return FujitsuCommand(FujitsuState(power=False))
    state = FujitsuState(
        power=True,
        temperature=int(temperature),
        mode=HVAC_TO_MODE[hvac_mode],
        fan=FAN_TO_CODEC[fan_mode],
        swing=SWING_TO_CODEC[swing_mode],
    )
    return FujitsuCommand(state, was_on=was_on)


def attrs_from_state(state: FujitsuState) -> dict[str, object]:
    """Translate a decoded codec state into climate attribute values."""
    if not state.power:
        return {"hvac_mode": MODE_OFF}
    return {
        "hvac_mode": MODE_TO_HVAC.get(state.mode, MODE_HEAT_COOL),
        "temperature": state.temperature,
        "fan_mode": CODEC_TO_FAN.get(state.fan, FAN_AUTO),
        "swing_mode": CODEC_TO_SWING.get(state.swing, SWING_OFF),
    }
