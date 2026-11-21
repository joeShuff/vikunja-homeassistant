from collections.abc import Awaitable, Callable
from datetime import datetime, date, timezone
from typing import Any, cast, Optional

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
    ATTR_ADD_ASSIGNEES,
    ATTR_ADD_LABELS,
    ATTR_ASSIGNEES,
    ATTR_DESCRIPTION,
    ATTR_DUE_DATETIME,
    ATTR_ITEM,
    ATTR_LABELS,
    ATTR_PRIORITY,
    ATTR_REMOVE_ASSIGNEES,
    ATTR_REMOVE_LABELS,
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
_STRING_LIST = vol.All(cv.ensure_list, [cv.string])

CREATE_TASK_SCHEMA = {
    vol.Required(ATTR_TITLE): _TITLE,
    vol.Optional(ATTR_DESCRIPTION): cv.string,
    vol.Optional(ATTR_DUE_DATETIME): cv.datetime,
    vol.Optional(ATTR_PRIORITY): _PRIORITY,
    vol.Optional(ATTR_LABELS): _STRING_LIST,
    vol.Optional(ATTR_ASSIGNEES): _STRING_LIST,
}

# Fields of update_task that change the task; at least one of them is required
UPDATE_TASK_CHANGES = (
    ATTR_RENAME, ATTR_DESCRIPTION, ATTR_DUE_DATETIME, ATTR_PRIORITY,
    ATTR_LABELS, ATTR_ADD_LABELS, ATTR_REMOVE_LABELS,
    ATTR_ASSIGNEES, ATTR_ADD_ASSIGNEES, ATTR_REMOVE_ASSIGNEES,
)

# (replace, add, remove): replacing all cannot be combined with adding or removing
_LIST_CHANGE_FIELDS = (
    (ATTR_LABELS, ATTR_ADD_LABELS, ATTR_REMOVE_LABELS),
    (ATTR_ASSIGNEES, ATTR_ADD_ASSIGNEES, ATTR_REMOVE_ASSIGNEES),
)


def _replace_or_add_remove(data: dict) -> dict:
    """Reject replacing a list together with adding to or removing from it."""
    for replace, add, remove in _LIST_CHANGE_FIELDS:
        if replace in data and (add in data or remove in data):
            raise vol.Invalid(f"'{replace}' replaces all {replace} and cannot be combined with '{add}' or '{remove}'")
    return data


UPDATE_TASK_SCHEMA = vol.All(
    cv.make_entity_service_schema({
        vol.Required(ATTR_ITEM): cv.string,
        vol.Optional(ATTR_RENAME): _TITLE,
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Optional(ATTR_DUE_DATETIME): cv.datetime,
        vol.Optional(ATTR_PRIORITY): _PRIORITY,
        vol.Optional(ATTR_LABELS): _STRING_LIST,
        vol.Optional(ATTR_ADD_LABELS): _STRING_LIST,
        vol.Optional(ATTR_REMOVE_LABELS): _STRING_LIST,
        vol.Optional(ATTR_ASSIGNEES): _STRING_LIST,
        vol.Optional(ATTR_ADD_ASSIGNEES): _STRING_LIST,
        vol.Optional(ATTR_REMOVE_ASSIGNEES): _STRING_LIST,
    }),
    cv.has_at_least_one_key(*UPDATE_TASK_CHANGES),
    _replace_or_add_remove,
)


def _check_add_remove_overlap(add: list, remove: list, kind: str, name: Callable[[Any], str]) -> None:
    """Reject adding and removing the same label or user in one call."""
    remove_ids = {item.id for item in remove}
    if overlap := [item for item in add if item.id in remove_ids]:
        raise ServiceValidationError(
            f"Cannot add and remove the same {kind} in one call: {', '.join(name(item) for item in overlap)}."
        )


async def _async_change_ids(
        current_ids: set[int],
        replace_ids: list[int] | None,
        add_ids: list[int],
        remove_ids: list[int],
        add: Callable[[list[int]], Awaitable[Any]],
        remove: Callable[[int], Awaitable[Any]],
        replace: Callable[[list[int]], Awaitable[Any]],
) -> None:
    """Replace, or add and remove, IDs on a task, calling the API only for actual changes."""
    if replace_ids is not None:
        if set(replace_ids) != current_ids:
            await replace(replace_ids)
        return

    missing_ids = [item_id for item_id in add_ids if item_id not in current_ids]
    if missing_ids:
        await add(missing_ids)

    # Removing something the task does not have is an error in Vikunja, so skip those
    for item_id in remove_ids:
        if item_id in current_ids:
            await remove(item_id)


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
            labels: list[str] | None = None,
            add_labels: list[str] | None = None,
            remove_labels: list[str] | None = None,
            assignees: list[str] | None = None,
            add_assignees: list[str] | None = None,
            remove_assignees: list[str] | None = None,
    ) -> ServiceResponse:
        """Update an existing task. Fields that are not given stay unchanged."""
        api: VikunjaAPI = self.project.api
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

        change_labels = any(value is not None for value in (labels, add_labels, remove_labels))
        change_assignees = any(value is not None for value in (assignees, add_assignees, remove_assignees))

        try:
            # Resolve all names first, so a typo does not leave a half-updated task behind
            replace_label_ids = None if labels is None else [l.id for l in await async_resolve_labels(api, labels)]
            labels_to_add = await async_resolve_labels(api, add_labels or [])
            labels_to_remove = await async_resolve_labels(api, remove_labels or [])
            _check_add_remove_overlap(labels_to_add, labels_to_remove, "label", lambda label: label.title)

            replace_user_ids = (
                None if assignees is None else [u.id for u in await async_resolve_users(self.project, assignees)]
            )
            users_to_add = await async_resolve_users(self.project, add_assignees or [])
            users_to_remove = await async_resolve_users(self.project, remove_assignees or [])
            _check_add_remove_overlap(users_to_add, users_to_remove, "assignee", user_identifier)

            # Task.update sends the whole task, so start from fresh data to not
            # overwrite changes made in Vikunja since the last poll
            task = await api.get_task(task.id)
        except APIError as err:
            raise HomeAssistantError(f"Failed to update Vikunja task {task.id}: {err}") from err

        steps: list[tuple[str, Callable[[], Awaitable[Any]]]] = []
        if data:
            steps.append(("details", lambda: task.update(data)))
        if change_labels:
            steps.append(("labels", lambda: _async_change_ids(
                {label.id for label in task.labels},
                replace_label_ids,
                [label.id for label in labels_to_add],
                [label.id for label in labels_to_remove],
                add=task.add_labels, remove=task.remove_label, replace=task.set_labels,
            )))
        if change_assignees:
            steps.append(("assignees", lambda: _async_change_ids(
                {user.id for user in task.assignees},
                replace_user_ids,
                [user.id for user in users_to_add],
                [user.id for user in users_to_remove],
                add=task.add_assignees, remove=task.remove_assignee, replace=task.set_assignees,
            )))

        done: list[str] = []
        try:
            for part, apply in steps:
                await apply()
                done.append(part)
        except APIError as err:
            already = f" Already updated: {', '.join(done)}." if done else ""
            raise HomeAssistantError(f"Failed to update the {part} of Vikunja task {task.id}: {err}.{already}") from err
        finally:
            await self._coordinator.async_request_refresh()

        return self._task_response(task)
