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
)

from .const import CONF_EMITTER_ENTITY_ID, CONF_RECEIVER_ENTITY_ID, DOMAIN


def _emitter_selector() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="infrared"))


class FujitsuGeneralIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fujitsu General IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Klimaanlage"): str,
                vol.Required(CONF_EMITTER_ENTITY_ID): _emitter_selector(),
                vol.Optional(CONF_RECEIVER_ENTITY_ID): _emitter_selector(),
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
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
