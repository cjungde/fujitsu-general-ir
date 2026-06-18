"""Climate platform for Fujitsu General IR."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
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
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import mapping
from .codec import TEMP_MAX, TEMP_MIN, decode
from .const import CONF_EMITTER_ENTITY_ID, CONF_RECEIVER_ENTITY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


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
    _attr_fan_modes = mapping.FAN_MODES
    _attr_swing_modes = mapping.SWING_MODES
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
        # Options (set via the options flow) take precedence over the initial
        # data so the emitter/receiver can be changed after setup.
        conf = {**entry.data, **entry.options}
        self._infrared_emitter_entity_id = conf[CONF_EMITTER_ENTITY_ID]
        self._receiver_entity_id: str | None = conf.get(CONF_RECEIVER_ENTITY_ID)
        self._remove_receiver: CALLBACK_TYPE | None = None

        # assumed state, defaults until first command or restore
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 22.0
        self._attr_fan_mode = mapping.FAN_AUTO
        self._attr_swing_mode = mapping.SWING_OFF
        # Last active (non-off) mode, restored by turn_on.
        self._last_hvac_mode = HVACMode.HEAT_COOL
        # Mirrors ESPHome's `power_`: the unit's last known power state, used to
        # set the off->on flag. Tracked separately because the HVAC mode is
        # already updated before _transmit() runs.
        self._power = False

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to the optional receiver."""
        await super().async_added_to_hass()

        if (last := await self.async_get_last_state()) is not None:
            if last.state in [m.value for m in self._attr_hvac_modes]:
                self._attr_hvac_mode = HVACMode(last.state)
                self._power = self._attr_hvac_mode != HVACMode.OFF
            attrs = last.attributes
            if (temp := attrs.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = float(temp)
            if (fan := attrs.get(ATTR_FAN_MODE)) in self._attr_fan_modes:
                self._attr_fan_mode = fan
            if (swing := attrs.get(ATTR_SWING_MODE)) in self._attr_swing_modes:
                self._attr_swing_mode = swing
            if self._attr_hvac_mode != HVACMode.OFF:
                self._last_hvac_mode = self._attr_hvac_mode

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

    def _set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Update the HVAC mode and remember the last active one."""
        self._attr_hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_hvac_mode = hvac_mode

    # --- transmit ---
    async def _transmit(self) -> None:
        """Encode the current state and send it through the IR proxy."""
        # was_on is the *previous* power state -> sets the off->on flag.
        command = mapping.build_command(
            hvac_mode=self._attr_hvac_mode,
            temperature=self._attr_target_temperature or 22,
            fan_mode=self._attr_fan_mode or mapping.FAN_AUTO,
            swing_mode=self._attr_swing_mode or mapping.SWING_OFF,
            was_on=self._power,
        )
        await self._send_command(command)
        self._power = self._attr_hvac_mode != HVACMode.OFF
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        self._set_hvac_mode(hvac_mode)
        await self._transmit()

    async def async_turn_on(self) -> None:
        """Turn the AC on, restoring the last active mode."""
        self._set_hvac_mode(self._last_hvac_mode)
        await self._transmit()

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        self._set_hvac_mode(HVACMode.OFF)
        await self._transmit()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature (and optionally the HVAC mode)."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self._set_hvac_mode(HVACMode(hvac_mode))
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
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
            # Log the raw capture so a non-matching model can be analysed
            # (e.g. with scripts/decode.py).
            _LOGGER.debug(
                "Received IR signal did not decode as Fujitsu General; raw timings: %s",
                signal.timings,
            )
            return
        attrs = mapping.attrs_from_state(state)
        self._set_hvac_mode(HVACMode(attrs["hvac_mode"]))
        if state.power:
            self._attr_target_temperature = attrs["temperature"]
            self._attr_fan_mode = attrs["fan_mode"]
            self._attr_swing_mode = attrs["swing_mode"]
        self._power = state.power
        _LOGGER.debug("Decoded IR from remote: %s", state)
        self.async_write_ha_state()
