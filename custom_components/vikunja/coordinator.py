from datetime import timedelta

import async_timeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from pyvikunja.api import VikunjaAPI

from custom_components.vikunja import LOGGER
from custom_components.vikunja.const import DATA_PROJECTS_KEY, DATA_TASKS_KEY


class VikunjaDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Vikunja API updates."""

    def __init__(self, hass: HomeAssistant, config_id, vikunja_api: VikunjaAPI, seconds_interval: int = 60):
        """Initialize the coordinator."""
        self._hass = hass
        self._vikunja_api = vikunja_api
        self._config_id = config_id

        super().__init__(
            hass,
            LOGGER,
            name="Vikunja Coordinator",
            update_interval=timedelta(seconds=seconds_interval),
        )

    async def _async_update_data(self):
        """Fetch data from Vikunja API."""
        result = {
            DATA_PROJECTS_KEY: {},
            DATA_TASKS_KEY: {}
        }

        try:
            async with async_timeout.timeout(10):
                LOGGER.info("Fetching projects from Vikunja API...")
                projects = await self._vikunja_api.get_projects()
                LOGGER.info(f"Fetched {len(projects)} projects.")

                current_projects = set(self.data[DATA_PROJECTS_KEY].keys()) if self.data else None
                current_tasks = set(self.data[DATA_TASKS_KEY].keys()) if self.data else None

                tasks = {}
                for project in projects:
                    result[DATA_PROJECTS_KEY][project.id] = project
                    LOGGER.info(f"Fetching tasks from Vikunja API for project {project.id}...")
                    new_tasks = await self._vikunja_api.get_tasks(project.id)

                    for task in new_tasks:
                        # Check if the task is already in the tasks list based on its ID
                        if not any(existing_task_id == task.id for existing_task_id in tasks.keys()):
                            tasks[task.id] = task  # Add the task if it's not already in the list

                LOGGER.info(f"Fetched {len(tasks)} tasks.")
                result[DATA_TASKS_KEY] = tasks

                new_tasks = set(result[DATA_TASKS_KEY].keys()) - current_tasks
                new_projects = set(result[DATA_PROJECTS_KEY].keys()) - current_projects

                # Reload the entry if there is new data so the new devices and entities get created
                if current_projects is not None and current_tasks is not None:
                    if current_tasks != new_tasks or current_projects != new_projects:
                        LOGGER.info("Change detected so reloading entry")
                        self._hass.config_entries.async_schedule_reload(self._config_id)

                return result
        except Exception as e:
            LOGGER.error(f"Error fetching data from Vikunja API: {e}")
            raise e
