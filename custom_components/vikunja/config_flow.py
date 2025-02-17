import logging

import httpx
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from pyvikunja.api import VikunjaAPI

from . import VikunjaDataUpdateCoordinator
from .const import DOMAIN, CONF_BASE_URL, CONF_TOKEN, CONF_SECS_INTERVAL, CONF_HIDE_DONE, LOGGER


class VikunjaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Vikunja integration."""

    VERSION = 2

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user step for configuration."""
        errors = {}

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL]
            token = user_input[CONF_TOKEN]
            secs_interval = user_input[CONF_SECS_INTERVAL]
            hide_done = user_input.get(CONF_HIDE_DONE, False)

            api = VikunjaAPI(base_url, token)

            try:
                await api.ping()
            except httpx.HTTPError as e:
                errors['base'] = f"API Error: {e}"

            if not errors:
                return self.async_create_entry(
                    title="Vikunja",
                    data={
                        CONF_BASE_URL: base_url,
                        CONF_TOKEN: token,
                        CONF_SECS_INTERVAL: secs_interval,
                        CONF_HIDE_DONE: hide_done
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_SECS_INTERVAL, default=60): int,
                vol.Optional(CONF_HIDE_DONE, default=False): bool
            }),
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return the options flow."""
        return VikunjaOptionsFlow(config_entry)


class VikunjaOptionsFlow(config_entries.OptionsFlow):
    """Allow reconfiguring the config in options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        LOGGER.info(f"config is {config_entry.data}")

    async def async_step_init(self, user_input=None):
        """Handle updating the API key."""
        errors = {}

        if user_input is not None:
            # Validate the new API key before saving
            api = VikunjaAPI(user_input[CONF_BASE_URL], user_input[CONF_TOKEN])

            data = {
                CONF_BASE_URL: user_input[CONF_BASE_URL],
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_SECS_INTERVAL: user_input[CONF_SECS_INTERVAL],
                CONF_HIDE_DONE: user_input[CONF_HIDE_DONE]
            }

            coordinator: VikunjaDataUpdateCoordinator = \
                self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)['coordinator']

            try:
                await api.ping()  # Ensure the API key is valid
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=data
                )

                await coordinator.async_request_refresh()
                return self.async_create_entry(title="", data=data)
            except httpx.HTTPError as e:
                errors["base"] = f"Error setting up: {e}"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL, default=self.config_entry.data.get(CONF_BASE_URL, "")): str,
                vol.Required(CONF_TOKEN, default=self.config_entry.data.get(CONF_TOKEN, "")): str,
                vol.Required(CONF_SECS_INTERVAL, default=self.config_entry.data.get(CONF_SECS_INTERVAL, 60)): int,
                vol.Optional(CONF_HIDE_DONE, default=self.config_entry.data.get(CONF_HIDE_DONE, False)): bool
            }),
            errors=errors,
        )