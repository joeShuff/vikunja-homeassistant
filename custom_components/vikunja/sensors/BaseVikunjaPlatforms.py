from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from pyvikunja.models.task import Task

from custom_components.vikunja import DOMAIN


class VikunjaTaskSensorEntity(Entity):

    def __init__(self, base_url, task: Task):
        self._task = task
        self._base_url = base_url
        self._device_name = f"Vikunja Task: {self._task.title}"
        self._task_id = f"task_{task.id}"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._task_id)
            },
            name=self._device_name,
            manufacturer="Vikunja",
            model="Task",
            configuration_url=self._base_url.replace("/api/v1", "") + f"/tasks/{self._task.id}"
        )

    def get_device_id_prefix(self):
        return self._task_id


class VikunjaTaskBinarySensorEntity(BinarySensorEntity):
    def __init__(self, base_url, task: Task):
        self._task = task
        self._base_url = base_url
        self._device_name = f"Vikunja Task: {self._task.title}"
        self._task_id = f"task_{task.id}"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._task_id)
            },
            name=self._device_name,
            manufacturer="Vikunja",
            model="Task",
            configuration_url=self._base_url.replace("/api/v1", "") + f"/tasks/{self._task.id}"
        )

    def get_device_id_prefix(self):
        return self._task_id


class VikunjaTaskDateTimeEntity(DateTimeEntity):
    """Base Vikunja task datetime entity that supports editing."""

    def __init__(self, base_url, task: Task):
        """Initialize the datetime entity."""
        self._task = task
        self._base_url = base_url
        self._device_name = f"Vikunja Task: {self._task.title}"
        self._task_id = f"task_{task.id}"

    @property
    def device_info(self):
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._task_id)},
            name=self._device_name,
            manufacturer="Vikunja",
            model="Task",
            configuration_url=self._base_url.replace("/api/v1", "") + f"/tasks/{self._task.id}"
        )

    def get_device_id_prefix(self):
        return self._task_id


class VikunjaTaskButtonEntity(ButtonEntity):
    """Base class for Vikunja Task buttons."""

    def __init__(self, base_url, task: Task):
        self._task = task
        self._base_url = base_url
        self._device_name = f"Vikunja Task: {self._task.title}"
        self._task_id = f"task_{task.id}"

    @property
    def should_poll(self) -> bool:
        """Button does not need polling."""
        return False

    @property
    def device_info(self):
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._task_id)},
            name=self._device_name,
            manufacturer="Vikunja",
            model="Task",
            configuration_url=self._base_url.replace("/api/v1", "") + f"/tasks/{self._task.id}"
        )

    def get_device_id_prefix(self):
        return self._task_id
