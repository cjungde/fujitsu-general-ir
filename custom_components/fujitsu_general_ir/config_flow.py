"""Config flow for the Fujitsu General IR integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import CONF_EMITTER_ENTITY_ID, CONF_RECEIVER_ENTITY_ID, DOMAIN


class FujitsuGeneralIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fujitsu General IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME], data=user_input
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Klimaanlage"): str,
                vol.Required(CONF_EMITTER_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(domain="infrared")
                ),
                vol.Optional(CONF_RECEIVER_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(domain="infrared")
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
