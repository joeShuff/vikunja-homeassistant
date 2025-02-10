from datetime import datetime, timezone

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from custom_components.vikunja.sensors.vikunja_task_entity import *


class VikunjaTaskProjectSensor(VikunjaTaskEntity, SensorEntity):
    """Representation of a Vikunja Task project sensor."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Project ID"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.task.project_id

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:calendar-badge"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_project"


class VikunjaTaskNameSensor(VikunjaTaskEntity, SensorEntity):
    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Task Name"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.task.title

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:check-circle"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_name"


class VikunjaTaskDescriptionSensor(VikunjaTaskEntity, SensorEntity):
    """Representation of a Vikunja Task description sensor."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Description"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.task.description

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:clipboard-text"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_description"


class VikunjaTaskDoneSensor(VikunjaTaskEntity, BinarySensorEntity):
    """Representation of a Vikunja Task done status sensor."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Task Done"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self.task.done

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:check-circle-outline"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_done"


class VikunjaTaskDueTodaySensor(VikunjaTaskEntity, BinarySensorEntity):
    """Representation of a Vikunja Task done status sensor."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Due Today"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        due_date = self.task.due_date
        if not due_date:
            return False  # No due date set

        # Convert due_date to a datetime object
        due_date = datetime.fromisoformat(due_date).astimezone(timezone.utc).date()
        today = datetime.now(timezone.utc).date()

        return due_date == today

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:check-circle-outline"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_due_today"


class VikunjaTaskDueDateSensor(VikunjaTaskEntity, SensorEntity):
    """Representation of a Vikunja Task due date sensor."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Due Date"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.task.due_date.isoformat() if self.task.due_date else "N/A"

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:calendar-clock"

    @property
    def device_class(self):
        """Define this sensor as a datetime sensor."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_due_date"


class VikunjaTaskPrioritySensor(VikunjaTaskEntity, SensorEntity):
    """Representation of a Vikunja Task priority sensor."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Priority"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._get_priority_string(self.task.priority)

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:flag"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_priority"

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


class VikunjaTaskStartDateSensor(VikunjaTaskEntity, DateTimeEntity):
    """Representation of a Vikunja Task start date sensor."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Start Date"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.task.start_date.isoformat() if self.task.start_date else "N/A"

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:calendar-edit"

    async def async_set_value(self, value):
        LOGGER.info(f"Setting {self.name} to {value}")
        await self.task.set_start_date(value)
        await self.async_update()

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_start_date"


class VikunjaTaskEndDateSensor(VikunjaTaskEntity, DateTimeEntity):
    """Representation of a Vikunja Task end date sensor."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} End Date"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.task.end_date.isoformat() if self.task.end_date else "N/A"

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:calendar-edit"

    async def async_set_value(self, value):
        LOGGER.info(f"Setting {self.name} to {value}")
        await self.task.set_end_date(value)
        await self.async_update()

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_end_date"


class VikunjaTaskCompleteButton(VikunjaTaskEntity, ButtonEntity):
    """Button to mark a Vikunja Task as done."""

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    async def async_press(self):
        """Handle button press."""
        LOGGER.info(f"Marking task {self.task.title} as done...")
        await self.task.mark_as_done()  # Mark task as done via API

        await self.async_update()

    @property
    def name(self):
        return f"{self.name_prefix()} Complete Task"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_mark_as_done"
