import logging

DOMAIN = "vikunja"

CONF_BASE_URL = "url"
CONF_TOKEN = "api_key"
CONF_SECS_INTERVAL = "seconds_interval"
CONF_HIDE_DONE = "hide_done"
CONF_STRICT_SSL = "strict_ssl"
CONF_SELECTED_PROJECTS = "selected_projects"

# Special value to indicate all projects should be synced
CONF_ALL_PROJECTS = "__all__"

DATA_PROJECTS_KEY = "projects"
DATA_TASKS_KEY = "tasks"

LOGGER = logging.getLogger(__package__)