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
from homeassistant.core import callback
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
    return EntitySelector(
        EntitySelectorConfig(domain="sensor", device_class="power")
    )


def _threshold_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=0, max=5000, step=1, unit_of_measurement="W", mode=NumberSelectorMode.BOX
        )
    )


class FujitsuGeneralIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fujitsu General IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # One config entry per emitter -> avoids two climate entities
            # fighting over the same IR blaster.
            await self.async_set_unique_id(user_input[CONF_EMITTER_ENTITY_ID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Klimaanlage"): str,
                vol.Required(CONF_EMITTER_ENTITY_ID): _emitter_selector(),
                vol.Optional(CONF_RECEIVER_ENTITY_ID): _emitter_selector(),
                vol.Optional(CONF_POWER_SENSOR_ENTITY_ID): _power_sensor_selector(),
                vol.Optional(
                    CONF_POWER_ON_THRESHOLD, default=DEFAULT_POWER_ON_THRESHOLD
                ): _threshold_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

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
