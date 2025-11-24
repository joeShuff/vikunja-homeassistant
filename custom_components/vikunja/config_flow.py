import httpx
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client
from pyvikunja.api import VikunjaAPI

from . import VikunjaDataUpdateCoordinator
from .const import DOMAIN, CONF_BASE_URL, CONF_TOKEN, CONF_SECS_INTERVAL, CONF_HIDE_DONE, CONF_STRICT_SSL


class VikunjaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Vikunja integration."""

    VERSION = 4

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user step for configuration."""
        errors = {}

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL]
            token = user_input[CONF_TOKEN]
            secs_interval = user_input[CONF_SECS_INTERVAL]
            hide_done = user_input.get(CONF_HIDE_DONE, False)
            strict_ssl = user_input.get(CONF_STRICT_SSL, True)

            client = get_async_client(self.hass, verify_ssl=strict_ssl)
            api = VikunjaAPI(base_url, token, strict_ssl, client)

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
                        CONF_HIDE_DONE: hide_done,
                        CONF_STRICT_SSL: strict_ssl
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_TOKEN): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_SECS_INTERVAL, default=60): int,
                vol.Optional(CONF_HIDE_DONE, default=False): bool,
                vol.Optional(CONF_STRICT_SSL, default=True): bool,
            }),
            errors=errors
        )

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Handle reconfiguration of the integration."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL]
            token = user_input[CONF_TOKEN]
            strict_ssl = user_input.get(CONF_STRICT_SSL, True)

            client = get_async_client(self.hass, verify_ssl=strict_ssl)
            api = VikunjaAPI(base_url, token, strict_ssl, client)

            try:
                await api.ping()
            except httpx.HTTPError as e:
                errors['base'] = f"API Error: {e}"

            if not errors:
                # Update only connection-related settings
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_BASE_URL: base_url,
                        CONF_TOKEN: token,
                        CONF_STRICT_SSL: strict_ssl,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL, default=entry.data.get(CONF_BASE_URL, "")): str,
                vol.Required(CONF_TOKEN, default=entry.data.get(CONF_TOKEN, "")): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_STRICT_SSL, default=entry.data.get(CONF_STRICT_SSL, True)): bool,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return the options flow."""
        return VikunjaOptionsFlow()


class VikunjaOptionsFlow(config_entries.OptionsFlow):
    """Allow reconfiguring the config in options."""

    async def async_step_init(self, user_input=None):
        """Handle options flow - only non-connection settings."""
        errors = {}

        if user_input is not None:
            # Update only non-connection settings
            data = {
                **self.config_entry.data,
                CONF_SECS_INTERVAL: user_input[CONF_SECS_INTERVAL],
                CONF_HIDE_DONE: user_input[CONF_HIDE_DONE],
            }

            hass_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            coordinator: VikunjaDataUpdateCoordinator = None if hass_data is None else hass_data['coordinator']

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=data
            )

            if coordinator is not None:
                await coordinator.async_request_refresh()
            else:
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_SECS_INTERVAL, default=self.config_entry.data.get(CONF_SECS_INTERVAL, 60)): int,
                vol.Optional(CONF_HIDE_DONE, default=self.config_entry.data.get(CONF_HIDE_DONE, False)): bool,
            }),
            errors=errors,
        )