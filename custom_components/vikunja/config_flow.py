import logging

import httpx
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from pyvikunja.api import VikunjaAPI

from .const import DOMAIN, CONF_BASE_URL, CONF_TOKEN, CONF_SECS_INTERVAL


class VikunjaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Vikunja integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user step for configuration."""
        errors = {}

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL]
            token = user_input[CONF_TOKEN]
            secs_interval = user_input[CONF_SECS_INTERVAL]

            api = VikunjaAPI(base_url, token)

            try:
                await api.ping()
            except httpx.HTTPError as e:
                errors['base'] = f"API Error: {e}"

            if not errors:
                return self.async_create_entry(
                    title="Vikunja",
                    data={CONF_BASE_URL: base_url, CONF_TOKEN: token, CONF_SECS_INTERVAL: secs_interval},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_SECS_INTERVAL, default=60): int
            }),
            errors=errors
        )
