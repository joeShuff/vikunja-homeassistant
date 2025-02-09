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
        try:
            async with async_timeout.timeout(10):
                LOGGER.info("Fetching projects from Vikunja API...")
                projects = await self._vikunja_api.get_projects()
                LOGGER.info(f"Fetched {len(projects)} projects.")

                # Get current projects and tasks, defaulting to empty sets
                has_data = self.data is not None

                current_projects = set(self.data[DATA_PROJECTS_KEY].keys()) if self.data else set()
                current_tasks = set(self.data[DATA_TASKS_KEY].keys()) if self.data else set()

                result = {DATA_PROJECTS_KEY: {}, DATA_TASKS_KEY: {}}
                tasks = {}

                for project in projects:
                    result[DATA_PROJECTS_KEY][project.id] = project
                    LOGGER.info(f"Fetching tasks from Vikunja API for project {project.id}...")
                    new_tasks = await self._vikunja_api.get_tasks(project.id)

                    for task in new_tasks:
                        if task.id not in tasks.keys():
                            tasks[task.id] = task

                LOGGER.info(f"Fetched {len(tasks)} tasks.")
                result[DATA_TASKS_KEY] = tasks

                # Calculate new and removed items
                new_tasks = set(result[DATA_TASKS_KEY].keys()) - current_tasks
                removed_tasks = current_tasks - set(tasks)
                new_projects = set(result[DATA_PROJECTS_KEY].keys()) - current_projects

                # Reload only if new tasks or projects exist
                if has_data and (new_tasks or new_projects):
                    LOGGER.info("New tasks or projects detected, reloading entry")
                    self._hass.config_entries.async_schedule_reload(self._config_id)

                # Remove deleted tasks
                # if removed_tasks:
                #     for task_id in removed_tasks:
                #         entity_id = f"sensor.vikunja_task_{task_id}"  # Adjust based on entity type
                #         if entity_id in self._hass.states.async_entity_ids():
                #             await self._hass.states.async_remove(entity_id)
                #             LOGGER.info(f"Removed deleted Vikunja task: {entity_id}")

                return result
        except Exception as e:
            LOGGER.error(f"Error fetching data from Vikunja API: {e}")
            raise e
