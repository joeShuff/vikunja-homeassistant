import httpx
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client
from pyvikunja.api import VikunjaAPI

from . import VikunjaDataUpdateCoordinator
from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_SECS_INTERVAL,
    CONF_HIDE_DONE,
    CONF_STRICT_SSL,
    CONF_SELECTED_PROJECTS,
    CONF_ALL_PROJECTS,
    LOGGER,
    DATA_PROJECTS_KEY,
    DATA_TASKS_KEY,
)
from .util import remove_project_entities, remove_task_with_entities


class VikunjaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Vikunja integration."""

    VERSION = 5

    def __init__(self):
        """Initialize the config flow."""
        self._config_data = {}
        self._api = None
        self._available_projects = {}

    async def _fetch_projects(self, api: VikunjaAPI) -> dict:
        """Fetch available projects from Vikunja API."""
        try:
            projects = await api.get_projects()
            return {str(project.id): project.title for project in projects}
        except Exception as e:
            LOGGER.error(f"Error fetching projects: {e}")
            return {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user step for configuration."""
        errors = {}

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL]
            token = user_input[CONF_TOKEN]
            secs_interval = user_input[CONF_SECS_INTERVAL]
            strict_ssl = user_input.get(CONF_STRICT_SSL, True)

            client = get_async_client(self.hass, verify_ssl=strict_ssl)
            api = VikunjaAPI(base_url, token, strict_ssl, client)

            try:
                await api.ping()
            except httpx.HTTPError as e:
                errors['base'] = f"API Error: {e}"

            if not errors:
                # Store config data for next step
                self._config_data = {
                    CONF_BASE_URL: base_url,
                    CONF_TOKEN: token,
                    CONF_SECS_INTERVAL: secs_interval,
                    CONF_STRICT_SSL: strict_ssl,
                }
                self._api = api
                
                # Fetch available projects
                self._available_projects = await self._fetch_projects(api)
                
                if self._available_projects:
                    return await self.async_step_select_projects()
                else:
                    # No projects found or error - create entry with all projects selected and hide_done default
                    return self.async_create_entry(
                        title="Vikunja",
                        data={
                            **self._config_data,
                            CONF_SELECTED_PROJECTS: [CONF_ALL_PROJECTS],
                            CONF_HIDE_DONE: True,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_TOKEN): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_SECS_INTERVAL, default=60): int,
                vol.Optional(CONF_STRICT_SSL, default=True): bool,
            }),
            errors=errors
        )

    async def async_step_select_projects(self, user_input=None) -> FlowResult:
        """Handle project selection step."""
        errors = {}

        if user_input is not None:
            selected_projects = user_input.get(CONF_SELECTED_PROJECTS, [])
            hide_done = user_input.get(CONF_HIDE_DONE, True)
            
            if not selected_projects:
                errors["base"] = "no_projects_selected"
            else:
                return self.async_create_entry(
                    title="Vikunja",
                    data={
                        **self._config_data,
                        CONF_SELECTED_PROJECTS: selected_projects,
                        CONF_HIDE_DONE: hide_done,
                    },
                )

        # Build project options for multi-select
        project_options = [
            selector.SelectOptionDict(value=CONF_ALL_PROJECTS, label="All Projects")
        ]
        for project_id, project_title in self._available_projects.items():
            project_options.append(
                selector.SelectOptionDict(value=project_id, label=project_title)
            )

        return self.async_show_form(
            step_id="select_projects",
            data_schema=vol.Schema({
                vol.Required(CONF_SELECTED_PROJECTS, default=[CONF_ALL_PROJECTS]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=project_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_HIDE_DONE, default=True): bool,
            }),
            errors=errors,
            description_placeholders={"project_count": str(len(self._available_projects))},
        )

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Handle reconfiguration of the integration."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL]
            token = user_input[CONF_TOKEN]
            strict_ssl = user_input.get(CONF_STRICT_SSL, True)

            client = get_async_client(self.hass, verify_ssl=strict_ssl)
            api = VikunjaAPI(base_url, token, strict_ssl, client)

            try:
                await api.ping()
            except httpx.HTTPError as e:
                errors['base'] = f"API Error: {e}"

            if not errors:
                # Update only connection-related settings, preserve other settings
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_BASE_URL: base_url,
                        CONF_TOKEN: token,
                        CONF_STRICT_SSL: strict_ssl,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL, default=entry.data.get(CONF_BASE_URL, "")): str,
                vol.Required(CONF_TOKEN, default=entry.data.get(CONF_TOKEN, "")): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_STRICT_SSL, default=entry.data.get(CONF_STRICT_SSL, True)): bool,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return the options flow."""
        return VikunjaOptionsFlow()


class VikunjaOptionsFlow(config_entries.OptionsFlow):
    """Allow reconfiguring the config in options."""

    def __init__(self):
        """Initialize options flow."""
        self._available_projects = {}

    async def _fetch_projects(self) -> dict:
        """Fetch available projects from Vikunja API."""
        try:
            hass_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if hass_data and "api" in hass_data:
                api = hass_data["api"]
                projects = await api.get_projects()
                return {str(project.id): project.title for project in projects}
        except Exception as e:
            LOGGER.error(f"Error fetching projects in options flow: {e}")
        return {}

    async def async_step_init(self, user_input=None):
        """Handle options flow - only non-connection settings."""
        errors = {}

        # Fetch available projects
        if not self._available_projects:
            self._available_projects = await self._fetch_projects()

        if user_input is not None:
            selected_projects = user_input.get(CONF_SELECTED_PROJECTS, [])
            new_hide_done = user_input.get(CONF_HIDE_DONE, True)
            
            if not selected_projects:
                errors["base"] = "no_projects_selected"
            else:
                # Find projects that were deselected and clean up their entities
                current_selection = self.config_entry.data.get(CONF_SELECTED_PROJECTS, [CONF_ALL_PROJECTS])
                current_hide_done = self.config_entry.data.get(CONF_HIDE_DONE, False)
                
                # Get coordinator data to find tasks for deselected projects
                hass_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                
                if hass_data and "coordinator" in hass_data:
                    coordinator = hass_data["coordinator"]
                    
                    if coordinator.data:
                        # Determine which projects are being removed
                        projects_to_remove = set()
                        
                        # If switching from "all projects" to specific selection
                        if CONF_ALL_PROJECTS in current_selection and CONF_ALL_PROJECTS not in selected_projects:
                            # Remove all projects not in the new selection
                            for project_id in coordinator.data.get(DATA_PROJECTS_KEY, {}).keys():
                                if str(project_id) not in selected_projects:
                                    projects_to_remove.add(project_id)
                        elif CONF_ALL_PROJECTS not in current_selection:
                            # Was specific selection, find removed projects
                            for project_id_str in current_selection:
                                if project_id_str not in selected_projects and project_id_str != CONF_ALL_PROJECTS:
                                    try:
                                        projects_to_remove.add(int(project_id_str))
                                    except ValueError:
                                        pass
                        
                        # Clean up entities for deselected projects
                        for project_id in projects_to_remove:
                            LOGGER.info(f"Cleaning up entities for deselected project {project_id}")
                            
                            # Remove project/todo list entity
                            await remove_project_entities(self.hass, self.config_entry.entry_id, project_id)
                            
                            # Remove all task entities and devices for this project
                            tasks_data = coordinator.data.get(DATA_TASKS_KEY, {})
                            for task_id, task in tasks_data.items():
                                if task.project_id == project_id:
                                    LOGGER.info(f"Removing task entities for task {task_id}")
                                    await remove_task_with_entities(self.hass, self.config_entry.entry_id, task_id)
                        
                        # Clean up completed tasks when enabling "Hide Completed Tasks"
                        if new_hide_done and not current_hide_done:
                            LOGGER.info("Hide Completed Tasks enabled, cleaning up completed task entities")
                            tasks_data = coordinator.data.get(DATA_TASKS_KEY, {})
                            for task_id, task in tasks_data.items():
                                if task.done:
                                    LOGGER.info(f"Removing completed task entities for task {task_id}")
                                    await remove_task_with_entities(self.hass, self.config_entry.entry_id, task_id)
                
                # Update all settings
                data = {
                    **self.config_entry.data,
                    CONF_SECS_INTERVAL: user_input[CONF_SECS_INTERVAL],
                    CONF_HIDE_DONE: new_hide_done,
                    CONF_SELECTED_PROJECTS: selected_projects,
                }

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=data
                )

                # Reload to apply new settings
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        # Get currently selected projects
        current_selection = self.config_entry.data.get(CONF_SELECTED_PROJECTS, [CONF_ALL_PROJECTS])

        # Build project options for multi-select
        project_options = [
            selector.SelectOptionDict(value=CONF_ALL_PROJECTS, label="All Projects")
        ]
        
        if self._available_projects:
            for project_id, project_title in self._available_projects.items():
                project_options.append(
                    selector.SelectOptionDict(value=project_id, label=project_title)
                )
            
            # Filter current selection to only include valid projects
            valid_selection = [
                p for p in current_selection
                if p == CONF_ALL_PROJECTS or p in self._available_projects
            ]
            if not valid_selection:
                valid_selection = [CONF_ALL_PROJECTS]
        else:
            # If we couldn't fetch projects, keep current selection
            valid_selection = current_selection if current_selection else [CONF_ALL_PROJECTS]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_SELECTED_PROJECTS, default=valid_selection): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=project_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SECS_INTERVAL, default=self.config_entry.data.get(CONF_SECS_INTERVAL, 60)): int,
                vol.Optional(CONF_HIDE_DONE, default=self.config_entry.data.get(CONF_HIDE_DONE, True)): bool,
            }),
            errors=errors,
            description_placeholders={"project_count": str(len(self._available_projects))},
        )