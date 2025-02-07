import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_BASE_URL, CONF_TOKEN




class VikunjaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Vikunja integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user step for configuration."""
        errors = {}

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL]
            token = user_input[CONF_TOKEN]

            # TODO: Validate the credentials with the Vikunja API
            if not base_url.startswith("http"):
                errors["base"] = "invalid_url"

            if not errors:
                return self.async_create_entry(
                    title="Vikunja",
                    data={CONF_BASE_URL: base_url, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors
        )
