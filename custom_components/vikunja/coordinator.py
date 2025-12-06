from datetime import timedelta

import async_timeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from pyvikunja.api import VikunjaAPI

from custom_components.vikunja import LOGGER
from custom_components.vikunja.const import (
    DATA_PROJECTS_KEY,
    DATA_TASKS_KEY,
    CONF_HIDE_DONE,
    CONF_SELECTED_PROJECTS,
    CONF_ALL_PROJECTS,
)
from custom_components.vikunja.util import remove_task_with_entities, remove_project_entities


class VikunjaDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Vikunja API updates."""

    def __init__(self, hass: HomeAssistant, config_entry, vikunja_api: VikunjaAPI, seconds_interval: int = 60):
        """Initialize the coordinator."""
        self._hass = hass
        self._vikunja_api = vikunja_api
        self._config_id = config_entry.entry_id
        self._config_entry = config_entry

        super().__init__(
            hass,
            LOGGER,
            name="Vikunja Coordinator",
            update_interval=timedelta(seconds=seconds_interval),
        )

    def _is_project_selected(self, project_id: int) -> bool:
        """Check if a project is selected for synchronization."""
        selected_projects = self._config_entry.data.get(CONF_SELECTED_PROJECTS, [CONF_ALL_PROJECTS])
        
        # If "all projects" is selected, include all projects
        if CONF_ALL_PROJECTS in selected_projects:
            return True
        
        # Check if this specific project is in the selected list
        return str(project_id) in selected_projects

    async def _async_update_data(self):
        """Fetch data from Vikunja API."""
        try:
            async with async_timeout.timeout(10):
                LOGGER.info("Fetching projects from Vikunja API...")
                all_projects = await self._vikunja_api.get_projects()
                LOGGER.info(f"Fetched {len(all_projects)} total projects from API.")

                # Filter projects based on user selection
                projects = [p for p in all_projects if self._is_project_selected(p.id)]
                LOGGER.info(f"Syncing {len(projects)} selected projects.")

                # Get current projects and tasks, defaulting to empty sets
                has_data = self.data is not None

                skip_done = self._config_entry.data.get(CONF_HIDE_DONE) or False

                current_projects = set(self.data[DATA_PROJECTS_KEY].keys()) if self.data else set()
                current_tasks = set(self.data[DATA_TASKS_KEY].keys()) if self.data else set()

                result = {DATA_PROJECTS_KEY: {}, DATA_TASKS_KEY: {}}
                tasks = {}

                for project in projects:
                    result[DATA_PROJECTS_KEY][project.id] = project
                    LOGGER.info(f"Fetching tasks from Vikunja API for project {project.id}...")
                    new_tasks = await self._vikunja_api.get_tasks(project.id)

                    for task in new_tasks:
                        if task.done and skip_done:
                            continue

                        if task.id not in tasks.keys():
                            tasks[task.id] = task

                LOGGER.info(f"Fetched {len(tasks)} tasks from selected projects.")
                result[DATA_TASKS_KEY] = tasks

                # Calculate new and removed items
                new_tasks = set(result[DATA_TASKS_KEY].keys()) - current_tasks
                removed_tasks = current_tasks - set(tasks)
                new_projects = set(result[DATA_PROJECTS_KEY].keys()) - current_projects
                removed_projects = current_projects - set(result[DATA_PROJECTS_KEY].keys())

                # Reload only if new tasks or projects exist
                if has_data and (new_tasks or new_projects):
                    LOGGER.info("New tasks or projects detected, reloading entry")
                    self._hass.config_entries.async_schedule_reload(self._config_id)

                # Remove deleted tasks (including tasks from deselected projects)
                if removed_tasks:
                    for task_id in removed_tasks:
                        LOGGER.info(f"Attempting to remove task {task_id}")
                        await remove_task_with_entities(self._hass, self._config_id, task_id)

                # Remove entities for deselected/deleted projects
                if removed_projects:
                    LOGGER.info(f"Projects removed from sync: {removed_projects}")
                    for project_id in removed_projects:
                        LOGGER.info(f"Attempting to remove project entities for project {project_id}")
                        await remove_project_entities(self._hass, self._config_id, project_id)

                return result
        except Exception as e:
            LOGGER.error(f"Error fetching data from Vikunja API: {e}")
            raise e
