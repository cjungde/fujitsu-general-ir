"""Config flow for the Fujitsu General IR integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_EMITTER_ENTITY_ID,
    CONF_POWER_ON_THRESHOLD,
    CONF_POWER_SENSOR_ENTITY_ID,
    CONF_RECEIVER_ENTITY_ID,
    DEFAULT_POWER_ON_THRESHOLD,
    DOMAIN,
)


def _emitter_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="infrared"))


def _power_sensor_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power"))


def _threshold_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=0,
            max=5000,
            step=1,
            unit_of_measurement="W",
            mode=NumberSelectorMode.BOX,
        )
    )


def _classify_infrared(hass: HomeAssistant) -> tuple[list, list]:
    """Split the ``infrared`` entities into (emitters, receivers).

    Receivers carry ``device_class: receiver``; everything else in the domain
    is treated as an emitter. This lets the config flow auto-detect the IR
    proxy instead of asking the user to hand-pick from a mixed list.
    """
    emitters, receivers = [], []
    for state in hass.states.async_all("infrared"):
        if state.attributes.get("device_class") == "receiver":
            receivers.append(state)
        else:
            emitters.append(state)
    return emitters, receivers


def _receiver_for_emitter(
    hass: HomeAssistant, emitter_entity_id: str, receivers: list
) -> str | None:
    """Best-effort: the receiver entity on the same device as the emitter.

    An ESPHome IR proxy usually exposes a TX and an RX entity on one device,
    so once the emitter is known we can pre-pair its sibling receiver.
    """
    ent_reg = er.async_get(hass)
    emitter_entry = ent_reg.async_get(emitter_entity_id)
    if emitter_entry is None or emitter_entry.device_id is None:
        return None
    for state in receivers:
        rx_entry = ent_reg.async_get(state.entity_id)
        if rx_entry is not None and rx_entry.device_id == emitter_entry.device_id:
            return state.entity_id
    return None


class FujitsuGeneralIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fujitsu General IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: auto-detect the IR proxy, then confirm."""
        if user_input is not None:
            # One config entry per emitter -> avoids two climate entities
            # fighting over the same IR blaster.
            await self.async_set_unique_id(user_input[CONF_EMITTER_ENTITY_ID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        emitters, receivers = _classify_infrared(self.hass)
        configured = {entry.unique_id for entry in self._async_current_entries()}
        available = [s for s in emitters if s.entity_id not in configured]

        # Nothing to control yet -> guide the user instead of an empty dropdown.
        if not available:
            return self.async_abort(reason="no_ir_proxy")

        # Pre-fill the detected proxy; pair its sibling receiver if there is one.
        default_emitter = available[0].entity_id
        suggested_receiver = _receiver_for_emitter(
            self.hass, default_emitter, receivers
        )
        detected = ", ".join(
            s.attributes.get("friendly_name", s.entity_id) for s in available
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Klimaanlage"): str,
                vol.Required(
                    CONF_EMITTER_ENTITY_ID, default=default_emitter
                ): _emitter_selector(),
                vol.Optional(
                    CONF_RECEIVER_ENTITY_ID,
                    description={"suggested_value": suggested_receiver},
                ): _emitter_selector(),
                vol.Optional(CONF_POWER_SENSOR_ENTITY_ID): _power_sensor_selector(),
                vol.Optional(
                    CONF_POWER_ON_THRESHOLD, default=DEFAULT_POWER_ON_THRESHOLD
                ): _threshold_selector(),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={"detected": detected},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return FujitsuGeneralIrOptionsFlow()


class FujitsuGeneralIrOptionsFlow(OptionsFlow):
    """Allow changing the emitter/receiver entities after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # An omitted optional receiver clears the previous selection.
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_EMITTER_ENTITY_ID,
                    default=current.get(CONF_EMITTER_ENTITY_ID),
                ): _emitter_selector(),
                vol.Optional(
                    CONF_RECEIVER_ENTITY_ID,
                    description={
                        "suggested_value": current.get(CONF_RECEIVER_ENTITY_ID)
                    },
                ): _emitter_selector(),
                vol.Optional(
                    CONF_POWER_SENSOR_ENTITY_ID,
                    description={
                        "suggested_value": current.get(CONF_POWER_SENSOR_ENTITY_ID)
                    },
                ): _power_sensor_selector(),
                vol.Optional(
                    CONF_POWER_ON_THRESHOLD,
                    default=current.get(
                        CONF_POWER_ON_THRESHOLD, DEFAULT_POWER_ON_THRESHOLD
                    ),
                ): _threshold_selector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
