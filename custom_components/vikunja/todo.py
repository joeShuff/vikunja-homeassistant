from datetime import datetime, date, timezone
from typing import cast, Optional

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt
import voluptuous as vol
from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyvikunja.api import APIError, VikunjaAPI
from pyvikunja.models.enum.task_priority import Priority
from pyvikunja.models.project import Project
from pyvikunja.models.task import Task

from custom_components.vikunja import VikunjaDataUpdateCoordinator, DOMAIN, LOGGER
from custom_components.vikunja.assignees import async_resolve_users, user_identifier
from custom_components.vikunja.const import (
    ATTR_ASSIGNEES,
    ATTR_DESCRIPTION,
    ATTR_DUE_DATETIME,
    ATTR_ITEM,
    ATTR_LABELS,
    ATTR_PRIORITY,
    ATTR_RENAME,
    ATTR_TITLE,
    DATA_PROJECTS_KEY,
    DATA_TASKS_KEY,
    SERVICE_CREATE_TASK,
    SERVICE_UPDATE_TASK,
)
from custom_components.vikunja.labels import async_resolve_labels

_TITLE = vol.All(cv.string, vol.Length(min=1, max=250))
_PRIORITY = vol.In([priority.name.lower() for priority in Priority])

CREATE_TASK_SCHEMA = {
    vol.Required(ATTR_TITLE): _TITLE,
    vol.Optional(ATTR_DESCRIPTION): cv.string,
    vol.Optional(ATTR_DUE_DATETIME): cv.datetime,
    vol.Optional(ATTR_PRIORITY): _PRIORITY,
    vol.Optional(ATTR_LABELS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ASSIGNEES): vol.All(cv.ensure_list, [cv.string]),
}

# Fields of update_task that change the task; at least one of them is required
UPDATE_TASK_CHANGES = (ATTR_RENAME, ATTR_DESCRIPTION, ATTR_DUE_DATETIME, ATTR_PRIORITY)

UPDATE_TASK_SCHEMA = vol.All(
    cv.make_entity_service_schema({
        vol.Required(ATTR_ITEM): cv.string,
        vol.Optional(ATTR_RENAME): _TITLE,
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Optional(ATTR_DUE_DATETIME): cv.datetime,
        vol.Optional(ATTR_PRIORITY): _PRIORITY,
    }),
    cv.has_at_least_one_key(*UPDATE_TASK_CHANGES),
)


def _to_vikunja_datetime(value: datetime) -> str:
    """Convert a datetime to the ISO format Vikunja expects, assuming local time if naive."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.DEFAULT_TIME_ZONE)
    return value.isoformat()


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

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CREATE_TASK,
        CREATE_TASK_SCHEMA,
        "async_service_create_task",
        supports_response=SupportsResponse.OPTIONAL,
    )
    platform.async_register_entity_service(
        SERVICE_UPDATE_TASK,
        UPDATE_TASK_SCHEMA,
        "async_service_update_task",
        supports_response=SupportsResponse.OPTIONAL,
    )

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
            TodoListEntityFeature.DELETE_TODO_ITEM |
            # TodoListEntityFeature.MOVE_TODO_ITEM |
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
            data["due_date"] = str(item.due.replace(tzinfo=dt.DEFAULT_TIME_ZONE).isoformat())

        await self.project.create_task(data)
        self._coordinator.async_update_listeners()
        await self._coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            id = int(uid)

            task = self.task_by_id(id)

            await task.delete_task()
            self._coordinator.async_update_listeners()
            await self._coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        uid = int(item.uid)

        # Find task that matches ID
        task = self.task_by_id(uid)

        new_data = {
            "done": item.status == TodoItemStatus.COMPLETED,
            "title": item.summary,
            "due_date": None,
            "description": item.description
        }

        if item.due is not None and item.status != TodoItemStatus.COMPLETED:
            new_data["due_date"] = str(item.due.replace(tzinfo=dt.DEFAULT_TIME_ZONE).isoformat())

        if task is not None:
            await task.update(new_data)

        self._coordinator.async_update_listeners()
        await self._coordinator.async_request_refresh()

    # Vikunja specific actions

    def _task_response(self, task: Task) -> dict:
        """Describe a task in an action response."""
        return {
            "task_id": task.id,
            "title": task.title,
            "project_id": self._project_id,
            "url": f"{self._base_url}/tasks/{task.id}",
            "labels": [label.title for label in task.labels],
            "assignees": [user_identifier(user) for user in task.assignees],
        }

    def _find_task(self, item: str) -> Task:
        """Find a task of this to-do list by its ID or its title (case-insensitive)."""
        item = item.strip()
        tasks = self.tasks_for_project()

        if item.isdigit():
            task = next((t for t in tasks if t.id == int(item)), None)
            if task is not None:
                return task

        matches = [t for t in tasks if t.title.casefold() == item.casefold()]
        if not matches:
            raise ServiceValidationError(f"No task '{item}' found in the Vikunja project '{self.project.title}'.")
        if len(matches) > 1:
            raise ServiceValidationError(
                f"Several tasks are named '{item}' in the Vikunja project '{self.project.title}' "
                f"(IDs: {', '.join(str(t.id) for t in matches)}). Use the task ID instead."
            )
        return matches[0]

    async def async_service_create_task(
            self,
            title: str,
            description: str | None = None,
            due_datetime: datetime | None = None,
            priority: str | None = None,
            labels: list[str] | None = None,
            assignees: list[str] | None = None,
    ) -> ServiceResponse:
        """Create a task with Vikunja specific fields."""
        data = {"title": title, "done": False}
        if description:
            data["description"] = description
        if due_datetime is not None:
            data["due_date"] = _to_vikunja_datetime(due_datetime)
        if priority is not None:
            data["priority"] = Priority[priority.upper()].value

        try:
            # Resolve labels and users first, so a typo does not leave a half-configured task behind
            task_labels = await async_resolve_labels(self.project.api, labels or [])
            users = await async_resolve_users(self.project, assignees or [])

            # Unlike labels, Vikunja accepts assignees on create
            if users:
                data["assignees"] = [{"id": user.id} for user in users]

            task = await self.project.create_task(data)
        except APIError as err:
            raise HomeAssistantError(f"Failed to create Vikunja task '{title}': {err}") from err

        LOGGER.info(f"Created Vikunja task {task.id} '{task.title}' in project {self._project_id}")

        try:
            # Vikunja ignores labels on create, they are attached afterwards
            if task_labels:
                await task.set_labels([label.id for label in task_labels])
        except APIError as err:
            raise HomeAssistantError(
                f"Created Vikunja task {task.id} '{title}', but failed to add its labels: {err}"
            ) from err
        finally:
            await self._coordinator.async_request_refresh()

        return self._task_response(task)

    async def async_service_update_task(
            self,
            item: str,
            rename: str | None = None,
            description: str | None = None,
            due_datetime: datetime | None = None,
            priority: str | None = None,
    ) -> ServiceResponse:
        """Update an existing task. Fields that are not given stay unchanged."""
        task = self._find_task(item)

        data = {}
        if rename is not None:
            data["title"] = rename
        if description is not None:
            data["description"] = description
        if due_datetime is not None:
            data["due_date"] = _to_vikunja_datetime(due_datetime)
        if priority is not None:
            data["priority"] = Priority[priority.upper()].value

        try:
            # Task.update sends the whole task, so start from fresh data to not
            # overwrite changes made in Vikunja since the last poll
            task = await self.project.api.get_task(task.id)
            await task.update(data)
        except APIError as err:
            raise HomeAssistantError(f"Failed to update Vikunja task {task.id}: {err}") from err
        finally:
            await self._coordinator.async_request_refresh()

        return self._task_response(task)
