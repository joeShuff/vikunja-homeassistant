from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pyvikunja.api import VikunjaAPI

from .const import DOMAIN, CONF_BASE_URL, CONF_TOKEN, LOGGER

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DATETIME, Platform.BUTTON]


async def async_setup_entry(hass, entry):
    """Set up Vikunja from a config entry."""
    LOGGER.info("Starting Vikunja integration setup")

    base_url = entry.data.get(CONF_BASE_URL)
    token = entry.data.get(CONF_TOKEN)

    if not base_url or not token:
        LOGGER.error("Base URL or token is missing")
        return False

    # Initialize Vikunja API client
    vikunja_api = VikunjaAPI(base_url, token)

    try:
        LOGGER.info("Fetching projects from Vikunja API...")
        projects = await vikunja_api.get_projects()
        LOGGER.info(f"Fetched {len(projects)} projects.")

        tasks = []
        for project in projects:
            LOGGER.info(f"Fetching tasks from Vikunja API for project {project.id}...")
            new_tasks = await vikunja_api.get_tasks(project.id)

            for task in new_tasks:
                # Check if the task is already in the tasks list based on its ID
                if not any(existing_task.id == task.id for existing_task in tasks):
                    tasks.append(task)  # Add the task if it's not already in the list

        LOGGER.info(f"Fetched {len(tasks)} tasks.")
    except Exception as e:
        LOGGER.error(f"Error fetching data from Vikunja API: {e}")
        return False

    # Store data in Home Assistant
    hass.data.setdefault("vikunja", {})[entry.entry_id] = {
        "api": vikunja_api,
        "projects": projects,
        "tasks": tasks,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOGGER.info("Vikunja setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove Vikunja integration."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
