from pyvikunja.api import VikunjaAPI

from custom_components.vikunja.const import (
    CONF_KANBAN_PROJECT_ID,
    CONF_KANBAN_VIEW_ID,
    DATA_TASKS_KEY,
    DOMAIN,
    LOGGER,
)
from custom_components.vikunja.sensors.kanban_sensor import VikunjaKanbanSensor
from custom_components.vikunja.sensors.TaskSensors import *


def get_sensors_for_task(coordinator, base_url, task_id):
    return [
        VikunjaTaskProjectSensor(coordinator, base_url, task_id),
        VikunjaTaskNameSensor(coordinator, base_url, task_id),
        VikunjaTaskDescriptionSensor(coordinator, base_url, task_id),
        VikunjaTaskDueDateSensor(coordinator, base_url, task_id),
        VikunjaTaskPrioritySensor(coordinator, base_url, task_id),
        VikunjaTaskAssigneeSensor(coordinator, base_url, task_id)
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
        entities.extend(get_sensors_for_task(coordinator, vikunja_api.web_ui_link, task_id))

    kanban_project_id = entry.data.get(CONF_KANBAN_PROJECT_ID)
    kanban_view_id = entry.data.get(CONF_KANBAN_VIEW_ID)
    entities.append(
        VikunjaKanbanSensor(coordinator, kanban_project_id, kanban_view_id, entry.entry_id)
    )

    if not entities:
        LOGGER.warning("No entities created")

    async_add_entities(entities, True)
    LOGGER.info(f"Added {len(entities)} Vikunja sensors.")
