import logging

DOMAIN = "vikunja"

CONF_BASE_URL = "url"
CONF_TOKEN = "api_key"
CONF_TOKEN_NOT_CHANGED = "__**token_not_changed**__" # Value to indicate token was not changed during reconfiguration
CONF_SECS_INTERVAL = "seconds_interval"
CONF_HIDE_DONE = "hide_done"
CONF_STRICT_SSL = "strict_ssl"
CONF_SELECTED_PROJECTS = "selected_projects"
CONF_KANBAN_PROJECT_ID = "kanban_project_id"
CONF_KANBAN_VIEW_ID = "kanban_view_id"

# Special value to indicate all projects should be synced
CONF_ALL_PROJECTS = "__all__"

DATA_PROJECTS_KEY = "projects"
DATA_TASKS_KEY = "tasks"
DATA_KANBAN_KEY = "kanban"

LOGGER = logging.getLogger(__package__)
