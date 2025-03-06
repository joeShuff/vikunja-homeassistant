from datetime import datetime, date, timezone
from typing import cast, Optional

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyvikunja.api import VikunjaAPI
from pyvikunja.models.project import Project
from pyvikunja.models.task import Task

from custom_components.vikunja import VikunjaDataUpdateCoordinator, DOMAIN, LOGGER
from custom_components.vikunja.const import DATA_PROJECTS_KEY, DATA_TASKS_KEY


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    # Get stored API instance and fetched data
    vikunja_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not vikunja_data:
        LOGGER.error("No Vikunja data found in hass.data")
        return

    vikunja_api: VikunjaAPI = vikunja_data["api"]
    coordinator = vikunja_data["coordinator"]

    ## Filter projects to all that aren't ID -1 (that's favourites)
    projects: list[Project] = [proj for proj in coordinator.data[DATA_PROJECTS_KEY].values() if proj.id != -1]

    async_add_entities(
        (
            VikunjaTaskTodoListEntity(
                coordinator,
                vikunja_api.web_ui_link,
                project.id,
            )
            for project in projects
        ),
        True,
    )


def _convert_api_item(item: Task) -> TodoItem:
    """Convert tasks API items into a TodoItem."""
    status = TodoItemStatus.COMPLETED if item.done else TodoItemStatus.NEEDS_ACTION

    return TodoItem(
        summary=item.title,
        uid=str(item.id),
        status=status,
        due=item.due_date,
        description=item.description,
    )


class VikunjaTaskTodoListEntity(
    CoordinatorEntity, TodoListEntity
):
    """A To-do List representation of the Shopping List."""

    _attr_has_entity_name = True
    _attr_supported_features = (
            TodoListEntityFeature.CREATE_TODO_ITEM |
            TodoListEntityFeature.UPDATE_TODO_ITEM |
            #        | TodoListEntityFeature.DELETE_TODO_ITEM |
            #        | TodoListEntityFeature.MOVE_TODO_ITEM |
            TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM |
            TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
            self,
            coordinator: VikunjaDataUpdateCoordinator,
            base_url: str,
            project_id,
    ) -> None:
        super().__init__(coordinator)
        self._base_url = base_url
        self._coordinator = coordinator
        self._project_id = project_id

    @property
    def project(self) -> Project:
        return self._coordinator.data[DATA_PROJECTS_KEY][self._project_id]

    @property
    def name(self) -> str:
        return self.project.title

    @property
    def unique_id(self) -> str | None:
        return f"todo_list_{self.project.id}"

    def tasks_for_project(self) -> list[Task]:
        """Return tasks that belong to this project."""
        return [task for task in self._coordinator.data[DATA_TASKS_KEY].values() if task.project_id == self._project_id]

    def task_by_id(self, id: int) -> Optional[Task]:
        """Return a single task by its ID, or None if not found."""
        tasks = self.tasks_for_project()

        return next((task for task in tasks if task.id == id), None)

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Get the current set of To-do items."""
        if self._coordinator.data is None:
            return None

        return [_convert_api_item(item) for item in self.tasks_for_project()]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        data = {
                "done": item.status == TodoItemStatus.COMPLETED,
                "title": item.summary,
                "due_date": None,
                "description": item.description
            }

        if item.due is not None and item.status != TodoItemStatus.COMPLETED:
            data["due_date"] = str(item.due.replace(tzinfo=timezone.utc).isoformat())

        await self.project.create_task(data)
        await self._coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        uid = int(item.uid)

        LOGGER.info(f"setting {uid} to {item}")

        task = self.task_by_id(uid)
        LOGGER.info(f"matching task is {task}")

        new_data = {
            "done": item.status == TodoItemStatus.COMPLETED,
            "title": item.summary,
            "due_date": None,
            "description": item.description
        }

        if item.due is not None and item.status != TodoItemStatus.COMPLETED:
            new_data["due_date"] = str(item.due.replace(tzinfo=timezone.utc).isoformat())

        LOGGER.info(f"new data is {new_data}")

        if task is not None:
            LOGGER.info(f"current data is {task.data}")
            await task.update(new_data)

        self._coordinator.async_update_listeners()
        await self._coordinator.async_request_refresh()
