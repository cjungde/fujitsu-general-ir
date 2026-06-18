"""Climate platform for Fujitsu General IR."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import (
    InfraredEmitterConsumerEntity,
    InfraredReceivedSignal,
    async_subscribe_receiver,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CALLBACK_TYPE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .codec import (
    TEMP_MAX,
    TEMP_MIN,
    Fan,
    FujitsuCommand,
    FujitsuState,
    Mode,
    Swing,
    decode,
)
from .const import CONF_EMITTER_ENTITY_ID, CONF_RECEIVER_ENTITY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# --- mappings: HA climate <-> codec ---
_HVAC_TO_MODE: dict[HVACMode, Mode] = {
    HVACMode.HEAT_COOL: Mode.AUTO,
    HVACMode.COOL: Mode.COOL,
    HVACMode.DRY: Mode.DRY,
    HVACMode.FAN_ONLY: Mode.FAN,
    HVACMode.HEAT: Mode.HEAT,
}
_MODE_TO_HVAC: dict[Mode, HVACMode] = {v: k for k, v in _HVAC_TO_MODE.items()}

_FAN_AUTO, _FAN_LOW, _FAN_MEDIUM, _FAN_HIGH, _FAN_QUIET = (
    "auto",
    "low",
    "medium",
    "high",
    "quiet",
)
_FAN_TO_CODEC: dict[str, Fan] = {
    _FAN_AUTO: Fan.AUTO,
    _FAN_LOW: Fan.LOW,
    _FAN_MEDIUM: Fan.MEDIUM,
    _FAN_HIGH: Fan.HIGH,
    _FAN_QUIET: Fan.SILENT,
}
_CODEC_TO_FAN: dict[Fan, str] = {v: k for k, v in _FAN_TO_CODEC.items()}

_SWING_OFF, _SWING_VERT, _SWING_HORIZ, _SWING_BOTH = (
    "off",
    "vertical",
    "horizontal",
    "both",
)
_SWING_TO_CODEC: dict[str, Swing] = {
    _SWING_OFF: Swing.NONE,
    _SWING_VERT: Swing.VERTICAL,
    _SWING_HORIZ: Swing.HORIZONTAL,
    _SWING_BOTH: Swing.BOTH,
}
_CODEC_TO_SWING: dict[Swing, str] = {v: k for k, v in _SWING_TO_CODEC.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fujitsu General IR climate entity."""
    async_add_entities([FujitsuGeneralClimate(entry)])


class FujitsuGeneralClimate(
    InfraredEmitterConsumerEntity, RestoreEntity, ClimateEntity
):
    """A Fujitsu General AC controlled over an IR proxy."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT_COOL,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = [_FAN_AUTO, _FAN_LOW, _FAN_MEDIUM, _FAN_HIGH, _FAN_QUIET]
    _attr_swing_modes = [_SWING_OFF, _SWING_VERT, _SWING_HORIZ, _SWING_BOTH]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the climate entity."""
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Fujitsu General",
        )
        self._infrared_emitter_entity_id = entry.data[CONF_EMITTER_ENTITY_ID]
        self._receiver_entity_id: str | None = entry.data.get(
            CONF_RECEIVER_ENTITY_ID
        )
        self._remove_receiver: CALLBACK_TYPE | None = None

        # assumed state, defaults until first command or restore
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 22
        self._attr_fan_mode = _FAN_AUTO
        self._attr_swing_mode = _SWING_OFF
        self._last_mode: Mode = Mode.AUTO

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to the optional receiver."""
        await super().async_added_to_hass()

        if (last := await self.async_get_last_state()) is not None:
            if last.state in [m.value for m in self._attr_hvac_modes]:
                self._attr_hvac_mode = HVACMode(last.state)
            attrs = last.attributes
            if (temp := attrs.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = float(temp)
            if (fan := attrs.get("fan_mode")) in self._attr_fan_modes:
                self._attr_fan_mode = fan
            if (swing := attrs.get("swing_mode")) in self._attr_swing_modes:
                self._attr_swing_mode = swing

        if self._receiver_entity_id:
            self._remove_receiver = async_subscribe_receiver(
                self.hass, self._receiver_entity_id, self._handle_signal
            )
            self.async_on_remove(self._unsubscribe_receiver)

    @callback
    def _unsubscribe_receiver(self) -> None:
        if self._remove_receiver is not None:
            self._remove_receiver()
            self._remove_receiver = None

    # --- transmit ---
    async def _transmit(self) -> None:
        """Encode the current state and send it through the IR proxy."""
        was_on = self._attr_hvac_mode != HVACMode.OFF
        if self._attr_hvac_mode == HVACMode.OFF:
            state = FujitsuState(power=False)
        else:
            state = FujitsuState(
                power=True,
                temperature=int(self._attr_target_temperature or 22),
                mode=_HVAC_TO_MODE[self._attr_hvac_mode],
                fan=_FAN_TO_CODEC[self._attr_fan_mode or _FAN_AUTO],
                swing=_SWING_TO_CODEC[self._attr_swing_mode or _SWING_OFF],
            )
        await self._send_command(FujitsuCommand(state, was_on=was_on))
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        self._attr_hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_mode = _HVAC_TO_MODE[hvac_mode]
        await self._transmit()

    async def async_turn_on(self) -> None:
        """Turn the AC on, restoring the last active mode."""
        self._attr_hvac_mode = _MODE_TO_HVAC.get(self._last_mode, HVACMode.HEAT_COOL)
        await self._transmit()

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        self._attr_hvac_mode = HVACMode.OFF
        await self._transmit()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._attr_target_temperature = temp
        if self._attr_hvac_mode != HVACMode.OFF:
            await self._transmit()
        else:
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        self._attr_fan_mode = fan_mode
        if self._attr_hvac_mode != HVACMode.OFF:
            await self._transmit()
        else:
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        self._attr_swing_mode = swing_mode
        if self._attr_hvac_mode != HVACMode.OFF:
            await self._transmit()
        else:
            self.async_write_ha_state()

    # --- receive (optional): track the original remote ---
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update assumed state when the physical remote is used."""
        state = decode(signal.timings)
        if state is None:
            return
        if not state.power:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_hvac_mode = _MODE_TO_HVAC.get(state.mode, HVACMode.HEAT_COOL)
            self._last_mode = state.mode
            self._attr_target_temperature = state.temperature
            self._attr_fan_mode = _CODEC_TO_FAN.get(state.fan, _FAN_AUTO)
            self._attr_swing_mode = _CODEC_TO_SWING.get(state.swing, _SWING_OFF)
        _LOGGER.debug("Decoded IR from remote: %s", state)
        self.async_write_ha_state()
