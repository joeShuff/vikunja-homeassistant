import httpx
import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.httpx_client import get_async_client
from pyvikunja.api import VikunjaAPI

from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_TOKEN,
    LOGGER,
    CONF_SECS_INTERVAL,
    CONF_HIDE_DONE,
    CONF_STRICT_SSL,
    CONF_SELECTED_PROJECTS,
    CONF_ALL_PROJECTS,
    CONF_KANBAN_PROJECT_ID,
    CONF_KANBAN_VIEW_ID,
)
from .coordinator import VikunjaDataUpdateCoordinator

SERVICE_CALL_API = "call_api"
CALL_API_SCHEMA = vol.Schema(
    {
        vol.Required("method"): str,
        vol.Required("path"): str,
        vol.Optional("payload"): object,
        vol.Optional("entry_id"): str,
    }
)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DATETIME,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.TODO
]


async def async_setup_entry(hass, entry):
    """Set up Vikunja from a config entry."""
    LOGGER.info("Starting Vikunja integration setup")

    base_url = entry.data.get(CONF_BASE_URL) or ""
    token = entry.data.get(CONF_TOKEN) or ""
    secs_interval = entry.data.get(CONF_SECS_INTERVAL) or 60
    strict_ssl = entry.data.get(CONF_STRICT_SSL) or True

    if not base_url or not token:
        LOGGER.error("Base URL or token is missing")
        return False

    # Initialize Vikunja API client
    client = get_async_client(hass, verify_ssl=strict_ssl)
    vikunja_api = VikunjaAPI(base_url, token, strict_ssl, client)

    try:
        await vikunja_api.ping()
    except httpx.HTTPError as e:
        LOGGER.error(f"Error setting up Vikunja at {vikunja_api.web_ui_link}: {e}")
        raise e

    coordinator = VikunjaDataUpdateCoordinator(hass, entry, vikunja_api, secs_interval)
    await coordinator.async_config_entry_first_refresh()

    # Update the entry title to include the host
    new_title = f"Vikunja ({vikunja_api.web_ui_link})"
    if entry.title != new_title:
        hass.config_entries.async_update_entry(entry, title=new_title)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": vikunja_api,
        "coordinator": coordinator
    }

    if not hass.services.has_service(DOMAIN, SERVICE_CALL_API):
        async def _handle_call_api(call):
            entry_id = call.data.get("entry_id")
            data_by_entry = hass.data.get(DOMAIN, {})
            if entry_id:
                entry_data = data_by_entry.get(entry_id)
            else:
                entry_data = next(iter(data_by_entry.values()), None)

            if not entry_data or "api" not in entry_data:
                LOGGER.error("Vikunja service call failed: no API instance available")
                return

            api = entry_data["api"]
            method = str(call.data.get("method", "")).strip().upper()
            path = str(call.data.get("path", "")).strip()

            if not method or not path:
                LOGGER.error("Vikunja service call failed: method/path required")
                return

            if path.startswith("http://") or path.startswith("https://"):
                LOGGER.error("Vikunja service call failed: path must be relative")
                return

            if path.startswith("/api/v1"):
                path = path[len("/api/v1"):]
            if not path.startswith("/"):
                path = f"/{path}"

            payload_raw = call.data.get("payload")
            payload = None
            if payload_raw is not None:
                if isinstance(payload_raw, str):
                    try:
                        payload = json.loads(payload_raw)
                    except json.JSONDecodeError:
                        payload = payload_raw
                else:
                    payload = payload_raw

            if method in {"GET", "DELETE"}:
                payload = None

            await api._request(method, path, data=payload)

        hass.services.async_register(
            DOMAIN,
            SERVICE_CALL_API,
            _handle_call_api,
            schema=CALL_API_SCHEMA,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOGGER.info("Vikunja setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove Vikunja integration."""
    hass.data[DOMAIN].pop(entry.entry_id, None)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and not hass.data.get(DOMAIN) and hass.services.has_service(DOMAIN, SERVICE_CALL_API):
        hass.services.async_remove(DOMAIN, SERVICE_CALL_API)
    return unload_ok


async def async_migrate_entry(hass, entry: config_entries.ConfigEntry) -> bool:
    """Migrate old entry to the new version."""
    new_data = {**entry.data}
    new_version = entry.version

    if entry.version < 2:
        LOGGER.debug("Migrating Vikunja to config v2")
        new_data[CONF_HIDE_DONE] = False # Add default False
        new_version = 2

    if entry.version < 3:
        LOGGER.debug("Migrating Vikunja to config v3")
        new_data[CONF_STRICT_SSL] = True
        new_version = 3

    if entry.version < 4:
        LOGGER.debug("Migrating Vikunja to config v4")
        # Add selected_projects with "all projects" as default for existing installations
        new_data[CONF_SELECTED_PROJECTS] = [CONF_ALL_PROJECTS]
        new_version = 4

    if entry.version < 5:
        LOGGER.debug("Migrating Vikunja to config v5")
        new_data[CONF_KANBAN_PROJECT_ID] = None
        new_data[CONF_KANBAN_VIEW_ID] = None
        new_version = 5

    hass.config_entries.async_update_entry(entry, data=new_data, version=new_version)
    return True
