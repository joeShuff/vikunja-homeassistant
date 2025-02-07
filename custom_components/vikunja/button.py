from pyvikunja.api import VikunjaAPI
from pyvikunja.models.task import Task

from custom_components.vikunja import LOGGER
from custom_components.vikunja.sensors.TaskSensors import VikunjaTaskCompleteButton


def get_button_sensors_for_task(base_url, task: Task):
    return [
        VikunjaTaskCompleteButton(base_url, task)
    ]


async def async_setup_entry(hass, entry, async_add_entities):
    LOGGER.info("Setting up Vikunja sensors...")

    # Get stored API instance and fetched data
    vikunja_data = hass.data.get("vikunja", {}).get(entry.entry_id)
    if not vikunja_data:
        LOGGER.error("No Vikunja data found in hass.data")
        return False

    vikunja_api: VikunjaAPI = vikunja_data["api"]
    projects = vikunja_data["projects"]
    tasks = vikunja_data["tasks"]

    LOGGER.info(f"Found {len(projects)} projects and {len(tasks)} tasks")

    # Create sensor entities
    entities = []

    for task in tasks:
        LOGGER.info(f"Task is {task}")
        entities.extend(get_button_sensors_for_task(vikunja_api.base_url, task))

    if not entities:
        LOGGER.warning("No entities created")

    async_add_entities(entities, True)
    LOGGER.info(f"Added {len(entities)} Vikunja button sensors.")