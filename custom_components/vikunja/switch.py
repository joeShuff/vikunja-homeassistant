from pyvikunja.api import VikunjaAPI

from custom_components.vikunja.const import LOGGER
from custom_components.vikunja.sensors.TaskSensors import *
from custom_components.vikunja.sensors.task.repeat_mode_sensors import VikunjaRepeatModeEnabledSwitch


def get_switch_for_task(coordinator, base_url, task_id):
    return [
        VikunjaRepeatModeEnabledSwitch(coordinator, base_url, task_id)
    ]


async def async_setup_entry(hass, entry, async_add_entities):
    LOGGER.info("Setting up Vikunja switches...")

    # Get stored API instance and fetched data
    vikunja_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not vikunja_data:
        LOGGER.error("No Vikunja data found in hass.data")
        return False

    vikunja_api: VikunjaAPI = vikunja_data["api"]
    coordinator = vikunja_data["coordinator"]

    if coordinator.data is None:
        LOGGER.error("No data in the coordinator yet")
        return

    # Create sensor entities
    entities = []

    tasks = coordinator.data[DATA_TASKS_KEY].keys()

    for task_id in tasks:
        LOGGER.info(f"Task is {task_id}")
        entities.extend(get_switch_for_task(coordinator, vikunja_api.web_ui_link, task_id))

    if not entities:
        LOGGER.warning("No entities created")

    async_add_entities(entities, True)
    LOGGER.info(f"Added {len(entities)} Vikunja switches.")
