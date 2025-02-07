from homeassistant.components.sensor import SensorDeviceClass

from custom_components.vikunja import LOGGER
from custom_components.vikunja.sensors.BaseVikunjaPlatforms import *


class VikunjaTaskProjectSensor(VikunjaTaskSensorEntity):
    """Representation of a Vikunja Task project sensor."""

    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"{task.title} Project"
        self._state = f"{task.project_id}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:calendar-badge"

    @property
    def unique_id(self):
        return self.get_device_id_prefix() + "_project"


class VikunjaTaskNameSensor(VikunjaTaskSensorEntity):
    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"Task Name"
        self._state = task.title

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:check-circle"

    @property
    def unique_id(self):
        return self.get_device_id_prefix() + "_name"


class VikunjaTaskDescriptionSensor(VikunjaTaskSensorEntity):
    """Representation of a Vikunja Task description sensor."""

    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"Task Description"
        self._state = task.description

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:clipboard-text"

    @property
    def unique_id(self):
        return self.get_device_id_prefix() + "_description"


class VikunjaTaskDoneSensor(VikunjaTaskBinarySensorEntity):
    """Representation of a Vikunja Task done status sensor."""

    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"Task Done"
        self._state = task.done

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:check-circle-outline"

    @property
    def unique_id(self):
        return self.get_device_id_prefix() + "_done"


class VikunjaTaskDueDateSensor(VikunjaTaskSensorEntity):
    """Representation of a Vikunja Task due date sensor."""

    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"Due Date"
        self._state = task.due_date.isoformat() if task.due_date else "N/A"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:calendar-clock"

    @property
    def device_class(self):
        """Define this sensor as a datetime sensor."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def unique_id(self):
        return self.get_device_id_prefix() + "_due_date"


class VikunjaTaskPrioritySensor(VikunjaTaskSensorEntity):
    """Representation of a Vikunja Task priority sensor."""

    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"Task Priority"
        self._state = self._get_priority_string(task.priority)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:flag"

    @property
    def unique_id(self):
        return self.get_device_id_prefix() + "_priority"

    def _get_priority_string(self, priority):
        match priority:
            case None:
                return "None"
            case 1:
                return "Low"
            case 2:
                return "Medium"
            case 3:
                return "High"
            case 4:
                return "Urgent"
            case 5:
                return "DO IT NOW"
            case _:
                return "Unknown"


class VikunjaTaskStartDateSensor(VikunjaTaskDateTimeEntity):
    """Representation of a Vikunja Task start date sensor."""

    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"Start Date"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._task.start_date.isoformat() if self._task.start_date else "N/A"

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:calendar-edit"

    async def async_set_value(self, value):
        LOGGER.info(f"Setting {self.name} to {value}")
        self._task = await self._task.set_start_date(value)
        self.async_write_ha_state()  # Notify Home Assistant of the change

    @property
    def unique_id(self):
        return self.get_device_id_prefix() + "_start_date"


class VikunjaTaskEndDateSensor(VikunjaTaskDateTimeEntity):
    """Representation of a Vikunja Task end date sensor."""

    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"End Date"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._task.end_date.isoformat() if self._task.end_date else "N/A"

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:calendar-edit"

    async def async_set_value(self, value):
        LOGGER.info(f"Setting {self.name} to {value}")
        self._task = await self._task.set_end_date(value)
        self.async_write_ha_state()  # Notify Home Assistant of the change

    @property
    def unique_id(self):
        return self.get_device_id_prefix() + "_end_date"


class VikunjaTaskCompleteButton(VikunjaTaskButtonEntity):
    """Button to mark a Vikunja Task as done."""

    def __init__(self, base_url, task: Task):
        super().__init__(base_url, task)
        self._name = f"Complete {task.title}"
        self._attr_unique_id = f"{self._task_id}_complete"

    async def async_press(self):
        """Handle button press."""
        LOGGER.info(f"Marking task {self._task.title} as done...")
        self._task = await self._task.mark_as_done()  # Mark task as done via API

        self.async_write_ha_state()  # Notify Home Assistant

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self) -> str | None:
        return self.get_device_id_prefix() + "_mark_as_done"