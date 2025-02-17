from pyvikunja.api import VikunjaAPI

from custom_components.vikunja import LOGGER
from custom_components.vikunja.const import DATA_TASKS_KEY, DOMAIN
from custom_components.vikunja.sensors.TaskSensors import VikunjaTaskCompleteButton


def get_button_sensors_for_task(coordinator, base_url, task_id):
    return [
        VikunjaTaskCompleteButton(coordinator, base_url, task_id)
    ]


async def async_setup_entry(hass, entry, async_add_entities):
    LOGGER.info("Setting up Vikunja sensors...")

    # Get stored API instance and fetched data
    vikunja_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not vikunja_data:
        LOGGER.error("No Vikunja data found in hass.data")
        return False

    vikunja_api: VikunjaAPI = vikunja_data["api"]
    coordinator = vikunja_data["coordinator"]

    # Create sensor entities
    entities = []

    tasks = coordinator.data[DATA_TASKS_KEY].keys()

    for task_id in tasks:
        LOGGER.info(f"Task is {task_id}")
        entities.extend(get_button_sensors_for_task(coordinator, vikunja_api.web_ui_link, task_id))

    if not entities:
        LOGGER.warning("No entities created")

    async_add_entities(entities, True)
    LOGGER.info(f"Added {len(entities)} Vikunja button sensors.")