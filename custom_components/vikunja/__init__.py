from datetime import timedelta

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pyvikunja.api import VikunjaAPI

from .const import DOMAIN, CONF_BASE_URL, CONF_TOKEN, LOGGER, CONF_SECS_INTERVAL
from .coordinator import VikunjaDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DATETIME, Platform.BUTTON]

async def async_setup_entry(hass, entry):
    """Set up Vikunja from a config entry."""
    LOGGER.info("Starting Vikunja integration setup")

    base_url = entry.data.get(CONF_BASE_URL)
    token = entry.data.get(CONF_TOKEN)
    secs_interval = entry.data.get(CONF_SECS_INTERVAL)

    if not base_url or not token:
        LOGGER.error("Base URL or token is missing")
        return False

    # Initialize Vikunja API client
    vikunja_api = VikunjaAPI(base_url, token)
    coordinator = VikunjaDataUpdateCoordinator(hass, entry.entry_id, vikunja_api, secs_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": vikunja_api,
        "coordinator": coordinator
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOGGER.info("Vikunja setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove Vikunja integration."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
