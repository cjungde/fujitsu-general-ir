"""Climate platform for Fujitsu General IR."""

from __future__ import annotations

import asyncio
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
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from . import mapping
from .codec import TEMP_MAX, TEMP_MIN, decode
from .const import (
    CONF_EMITTER_ENTITY_ID,
    CONF_POWER_ON_THRESHOLD,
    CONF_POWER_SENSOR_ENTITY_ID,
    CONF_RECEIVER_ENTITY_ID,
    DEFAULT_POWER_ON_THRESHOLD,
    DOMAIN,
    EMITTER_WAIT_TIMEOUT,
    POWER_SYNC_GRACE,
    SEND_RETRIES,
    SEND_RETRY_BACKOFF,
)

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
    # IR is one-way; the entity tracks an assumed state and should ride out a
    # proxy that briefly drops off the LAN rather than going unavailable.
    _attr_assumed_state = True
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
        # Optional power meter for on/off detection.
        self._power_sensor_entity_id: str | None = conf.get(CONF_POWER_SENSOR_ENTITY_ID)
        self._power_on_threshold: float = float(
            conf.get(CONF_POWER_ON_THRESHOLD, DEFAULT_POWER_ON_THRESHOLD)
        )
        # Monotonic deadline until which power-derived on/off is suppressed
        # because we just transmitted (the draw is still transitional).
        self._suppress_power_until: float = 0.0

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

    @property
    def available(self) -> bool:
        """Stay available across brief emitter/LAN drops.

        The emitter going ``unavailable`` for a few seconds (e.g. the proxy
        briefly leaving the LAN) must not make the AC entity unavailable, as
        that would make Home Assistant reject service calls outright. Because
        this is an assumed-state, one-way IR device we keep reporting available
        and instead wait + retry on send (see ``_send_with_retry``). Only report
        unavailable if the emitter entity is entirely gone (e.g. removed).
        """
        return (
            self.hass is not None
            and self.hass.states.get(self._infrared_emitter_entity_id) is not None
        )

    def _emitter_available(self) -> bool:
        """True if the emitter entity exists and is not currently unavailable."""
        state = self.hass.states.get(self._infrared_emitter_entity_id)
        return state is not None and state.state != STATE_UNAVAILABLE

    async def _wait_for_emitter(self) -> bool:
        """Wait (bounded) for the emitter to become available after a LAN drop."""
        if self._emitter_available():
            return True

        ready = asyncio.Event()

        @callback
        def _check(_event: Any) -> None:
            if self._emitter_available():
                ready.set()

        unsub = async_track_state_change_event(
            self.hass, self._infrared_emitter_entity_id, _check
        )
        try:
            async with asyncio.timeout(EMITTER_WAIT_TIMEOUT):
                await ready.wait()
            return True
        except TimeoutError:
            return False
        finally:
            unsub()

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
            self._async_attach_receiver()

        if self._power_sensor_entity_id:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self._power_sensor_entity_id,
                    self._handle_power_event,
                )
            )
            # Sync once now from the current reading.
            self._sync_power_state()

    @callback
    def _handle_power_event(self, _event: Any) -> None:
        """Re-evaluate on/off whenever the power reading changes."""
        self._sync_power_state()

    @callback
    def _sync_power_state(self) -> None:
        """Detect on/off from the power meter and update the assumed state.

        This only flips power on/off -- IR cannot read back mode, temperature or
        fan, so on an off->on transition the last active HVAC mode is assumed.
        No IR is transmitted here; it is a pure observation of the AC's draw.
        """
        if self._power_sensor_entity_id is None:
            return
        if self.hass.loop.time() < self._suppress_power_until:
            return
        state = self.hass.states.get(self._power_sensor_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        try:
            watts = float(state.state)
        except (TypeError, ValueError):
            return

        is_on = watts >= self._power_on_threshold
        if is_on and self._attr_hvac_mode == HVACMode.OFF:
            self._set_hvac_mode(self._last_hvac_mode)
            self._power = True
            self.async_write_ha_state()
        elif not is_on and self._attr_hvac_mode != HVACMode.OFF:
            self._set_hvac_mode(HVACMode.OFF)
            self._power = False
            self.async_write_ha_state()

    @callback
    def _async_attach_receiver(self) -> None:
        """Subscribe to the receiver, (re)trying whenever it (re)appears.

        At startup or after a LAN drop the proxy's receiver entity may not exist
        yet; subscribing then raises ``receiver_not_found`` and would abort
        entity setup. Instead, watch the entity and subscribe once it is
        present, so a brief drop never breaks the climate entity.
        """

        @callback
        def _try_subscribe(_event: Any = None) -> None:
            if self._remove_receiver is not None:
                return  # already subscribed
            if self.hass.states.get(self._receiver_entity_id) is None:
                return  # not there yet; the tracker will fire again
            try:
                self._remove_receiver = async_subscribe_receiver(
                    self.hass, self._receiver_entity_id, self._handle_signal
                )
            except HomeAssistantError as err:
                _LOGGER.debug(
                    "IR receiver %s not ready yet: %s",
                    self._receiver_entity_id,
                    err,
                )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._receiver_entity_id, _try_subscribe
            )
        )
        self.async_on_remove(self._unsubscribe_receiver)
        # Try once now in case the receiver is already available.
        _try_subscribe()

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
        await self._send_with_retry(command)
        self._power = self._attr_hvac_mode != HVACMode.OFF
        # Our command is authoritative; ignore the transitional draw for a bit.
        self._suppress_power_until = self.hass.loop.time() + POWER_SYNC_GRACE
        self.async_write_ha_state()

    async def _send_with_retry(self, command: Any) -> None:
        """Send a command, tolerating a proxy that briefly leaves the LAN.

        Waits for the emitter to be reachable, then retries the transmit a few
        times with exponential backoff. Raises ``HomeAssistantError`` only if
        the proxy stays down for the whole window, so a momentary drop no longer
        loses the command.
        """
        if not await self._wait_for_emitter():
            raise HomeAssistantError(
                f"IR emitter {self._infrared_emitter_entity_id} is unavailable; "
                "command not sent"
            )

        delay = SEND_RETRY_BACKOFF
        last_err: Exception | None = None
        for attempt in range(1, SEND_RETRIES + 1):
            try:
                await self._send_command(command)
                if attempt > 1:
                    _LOGGER.info("IR command sent on attempt %s", attempt)
                return
            except HomeAssistantError as err:
                last_err = err
                _LOGGER.warning(
                    "IR send attempt %s/%s failed: %s", attempt, SEND_RETRIES, err
                )
                if attempt < SEND_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2
                    # The failure may itself be a fresh drop; wait for the
                    # emitter to come back before the next attempt.
                    await self._wait_for_emitter()

        assert last_err is not None
        raise last_err

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
