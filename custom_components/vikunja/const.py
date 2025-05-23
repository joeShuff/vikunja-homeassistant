import logging

DOMAIN = "vikunja"

CONF_BASE_URL = "url"
CONF_TOKEN = "api_key"
CONF_SECS_INTERVAL = "seconds_interval"
CONF_HIDE_DONE = "hide_done"  # Removed
CONF_DEVICE_MODE = "devices_mode"
CONF_ENABLE_TODO = "enable_todo"
CONF_STRICT_SSL = "strict_ssl"

CONF_DEVICE_MODE_ALL = 0
CONF_DEVICE_MODE_HIDE_DONE = 1
CONF_DEVICE_MODE_NONE = 2
CONF_DEVICE_MODES = {CONF_DEVICE_MODE_ALL: "All", CONF_DEVICE_MODE_HIDE_DONE: "Hide Done",
                     CONF_DEVICE_MODE_NONE: "None"}

DATA_PROJECTS_KEY = "projects"
DATA_TASKS_KEY = "tasks"

LOGGER = logging.getLogger(__package__)
