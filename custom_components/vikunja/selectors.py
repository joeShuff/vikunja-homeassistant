"""Offer the known Vikunja users and labels as dropdowns in the fields of the Vikunja actions.

services.yaml can only hold static options, so the action descriptions are rebuilt at
runtime with the users and labels of all loaded config entries. The dropdowns only
allow the listed values; YAML can still use any title, username or ID.
"""
from __future__ import annotations

import asyncio
import copy
from collections.abc import Awaitable, Iterable
from pathlib import Path
from typing import TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.util.yaml import load_yaml_dict
from pyvikunja.api import APIError, VikunjaAPI
from pyvikunja.models.label import Label
from pyvikunja.models.project import Project
from pyvikunja.models.user import User

from .assignees import user_identifier
from .const import (
    ATTR_ADD_ASSIGNEES,
    ATTR_ADD_LABELS,
    ATTR_ASSIGNEES,
    ATTR_LABELS,
    ATTR_REMOVE_ASSIGNEES,
    ATTR_REMOVE_LABELS,
    DOMAIN,
    LOGGER,
    SERVICE_CREATE_TASK,
    SERVICE_UPDATE_TASK,
)

USER_FIELDS = (ATTR_ASSIGNEES, ATTR_ADD_ASSIGNEES, ATTR_REMOVE_ASSIGNEES)
LABEL_FIELDS = (ATTR_LABELS, ATTR_ADD_LABELS, ATTR_REMOVE_LABELS)

DATA_SELECTOR_USERS = "selector_users"
DATA_SELECTOR_LABELS = "selector_labels"

_T = TypeVar("_T")


async def _async_or_empty(request: Awaitable[list[_T]], what: str) -> list[_T]:
    """Return the result of a request, or an empty list if Vikunja refuses it (e.g. missing permission)."""
    try:
        return await request
    except APIError as err:
        LOGGER.debug(f"Could not load {what} for the action dropdowns: {err}")
        return []


async def async_load_selector_data(api: VikunjaAPI, projects: Iterable[Project]) -> tuple[list[User], list[Label]]:
    """Load the users of the given projects and all labels visible to the API key."""
    projects = list(projects)
    *project_users, labels = await asyncio.gather(
        *(_async_or_empty(project.get_users(), f"users of project {project.id}") for project in projects),
        _async_or_empty(api.get_labels(), "labels"),
    )

    users: dict[int, User] = {}
    for user_list in project_users:
        for user in user_list:
            users.setdefault(user.id, user)

    return list(users.values()), labels


def _user_options(users: Iterable[User]) -> list[dict[str, str]]:
    options = []
    for user in users:
        value = user_identifier(user)
        label = f"{user.name} ({value})" if user.name and user.name != value else value
        options.append({"value": value, "label": label})
    return options


def _label_options(labels: Iterable[Label]) -> list[dict[str, str]]:
    """Offer labels by title; labels sharing a title are offered by ID to stay unambiguous."""
    labels = list(labels)
    counts: dict[str, int] = {}
    for label in labels:
        counts[label.title.casefold()] = counts.get(label.title.casefold(), 0) + 1

    return [
        {"value": label.title, "label": label.title}
        if counts[label.title.casefold()] == 1
        else {"value": str(label.id), "label": f"{label.title} (#{label.id})"}
        for label in labels
    ]


def _dropdown(options: list[dict[str, str]]) -> dict:
    return {
        "select": {
            "options": sorted(options, key=lambda option: (option["label"].casefold(), option["label"])),
            "multiple": True,
            "custom_value": False,
            "mode": "dropdown",
        }
    }


def _merge_by_id(hass: HomeAssistant, key: str) -> list:
    """Collect the items stored under key by all loaded config entries, once per ID."""
    items: dict[int, object] = {}
    for entry_data in hass.data.get(DOMAIN, {}).values():
        for item in entry_data.get(key, []):
            items.setdefault(item.id, item)
    return list(items.values())


def _load_services_yaml() -> dict:
    return load_yaml_dict(str(Path(__file__).parent / "services.yaml"))


async def async_update_action_selectors(hass: HomeAssistant) -> None:
    """Turn the assignee and label fields of the actions into dropdowns of the known values.

    Fields without known values (e.g. missing API key permission) keep the text input
    from services.yaml, as an empty dropdown could not be used at all.
    """
    user_options = _user_options(_merge_by_id(hass, DATA_SELECTOR_USERS))
    label_options = _label_options(_merge_by_id(hass, DATA_SELECTOR_LABELS))
    if not user_options and not label_options:
        return

    dropdowns: dict[str, dict] = {}
    if user_options:
        dropdowns |= dict.fromkeys(USER_FIELDS, _dropdown(user_options))
    if label_options:
        dropdowns |= dict.fromkeys(LABEL_FIELDS, _dropdown(label_options))

    services = await hass.async_add_executor_job(_load_services_yaml)
    for service in (SERVICE_CREATE_TASK, SERVICE_UPDATE_TASK):
        description = copy.deepcopy(services[service])
        for field, selector in dropdowns.items():
            if field in description["fields"]:
                description["fields"][field]["selector"] = copy.deepcopy(selector)
        async_set_service_schema(hass, DOMAIN, service, description)

    LOGGER.debug(f"Action dropdowns updated with {len(user_options)} users and {len(label_options)} labels")
