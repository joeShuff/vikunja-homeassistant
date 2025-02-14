from datetime import timedelta
from enum import Enum
from typing import Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity
from pyvikunja.models.enum.repeat_mode import RepeatMode
from pyvikunja.models.task import Task

from custom_components.vikunja import LOGGER
from custom_components.vikunja.sensors.vikunja_task_entity import VikunjaTaskEntity


def get_repeat_info_for_task(task: Task) -> tuple[Optional['RepeatUnit'], Optional[int]]:
    """Returns the repeat unit and repeat interval from a Task."""
    if task.repeat_after is None or task.repeat_after.total_seconds() <= 0:
        return None, None

    unit = RepeatUnit.from_seconds(int(task.repeat_after.total_seconds()))
    scaled_value = int(int(task.repeat_after.total_seconds()) / unit.seconds)

    return unit, scaled_value


class RepeatUnit(Enum):
    HOURS = (3600, "Hours")  # 1 Hour = 3600 seconds
    DAYS = (86400, "Days")  # 1 Day = 86400 seconds
    WEEKS = (604800, "Weeks")  # 1 Week = 604800 seconds

    def __init__(self, seconds: int, display: str):
        self.seconds = seconds
        self.display = display

    @classmethod
    def list_display_values(cls) -> list[str]:
        """Returns a list of display names for the UI dropdown."""
        return [unit.display for unit in cls]

    @classmethod
    def from_seconds(cls, seconds: int) -> 'RepeatUnit':
        """Determine the best unit and return the unit"""
        if seconds % RepeatUnit.WEEKS.seconds == 0:
            return RepeatUnit.WEEKS
        elif seconds % RepeatUnit.DAYS.seconds == 0:
            return RepeatUnit.DAYS
        else:
            return RepeatUnit.HOURS

    @classmethod
    def from_display(cls, display: str) -> 'RepeatUnit':
        """Get the RepeatUnit from its display string."""
        for unit in cls:
            if unit.display.lower() == display.lower():
                return unit
        raise ValueError(f"Invalid repeat unit: {display}")


REPEAT_MODE_OPTIONS = {
    RepeatMode.DEFAULT: "Default",
    RepeatMode.MONTHLY: "Monthly",
    RepeatMode.FROM_CURRENT_DATE: "From Current Date"
}


class VikunjaRepeatModeEnabledSwitch(VikunjaTaskEntity, SwitchEntity):

    def __init__(self, coordinator, base_url, task_id):
        super().__init__(coordinator, base_url, task_id)

    @property
    def is_on(self) -> bool | None:
        return self.task.repeat_enabled

    async def async_turn_on(self, **kwargs):
        """Turn on repeat mode."""
        await self.task.set_repeating_enabled(True)  # Update task to enable repeat mode
        await self.update_task()

    async def async_turn_off(self, **kwargs):
        """Turn off repeat mode."""
        await self.task.set_repeating_enabled(False)  # Update task to disable repeat mode
        await self.update_task()

    @property
    def name(self):
        return f"{self.name_prefix()} Repeat Mode"

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:repeat"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_repeat_mode"


class VikunjaRepeatModeSelect(VikunjaTaskEntity, SelectEntity):
    """Select entity for Vikunja task repeat mode."""

    def __init__(self, coordinator, base_url, task_id):
        """Initialize the select entity."""
        super().__init__(coordinator, base_url, task_id)

    @property
    def options(self):
        return list(REPEAT_MODE_OPTIONS.values())

    @property
    def state(self):
        """Return the state of the sensor."""
        return REPEAT_MODE_OPTIONS.get(self.task.repeat_mode, "None")

    @property
    def available(self) -> bool:
        return self.task.repeat_enabled

    async def async_select_option(self, option: str):
        """Handle user selection of a new repeat mode."""
        mode_value = next((k for k, v in REPEAT_MODE_OPTIONS.items() if v == option), None)
        await self.task.set_repeating_interval(mode=RepeatMode(mode_value))
        await self.update_task()

    @property
    def name(self):
        return f"{self.name_prefix()} Repeat Mode"

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:repeat"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_repeat_mode"


class VikunjaRepeatIntervalSizeSensor(VikunjaTaskEntity, NumberEntity):
    """Sensor entity for Vikunja task repeat interval."""

    def __init__(self, coordinator, base_url, task_id):
        """Initialize the sensor."""
        super().__init__(coordinator, base_url, task_id)

    async def async_set_value(self, value: float) -> None:
        # Get the tasks current repeat unit and value
        current_unit, current_value = get_repeat_info_for_task(self.task)

        if current_unit is None or current_value is None:
            return None

        # Calculate the new repeat interval with the current value * new unit scale
        # e.g. 4 Days -> Change 4 to 8 -> calculate 8 * seconds in a day
        new_value = value * current_unit.seconds

        # Send update
        await self.task.set_repeating_interval(interval=timedelta(seconds=new_value))
        await self.update_task()

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Repeat Interval"

    @property
    def state(self):
        """Return the state of the sensor."""
        unit, scaled_value = get_repeat_info_for_task(self.task)
        return scaled_value

    @property
    def max_value(self) -> float:
        return 999999999

    @property
    def min_value(self) -> float:
        return 1

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        unit, scaled_value = get_repeat_info_for_task(self.task)

        if unit is None or scaled_value is None:
            return None

        return unit.display.lower()

    @property
    def mode(self) -> NumberMode:
        return NumberMode.BOX

    @property
    def available(self) -> bool:
        if not self.task.repeat_enabled:
            return False

        if self.task.repeat_mode == RepeatMode.MONTHLY:
            return False
        else:
            return True

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:repeat"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_repeat_interval_value"


class VikunjaRepeatIntervalUnitSensor(VikunjaTaskEntity, SelectEntity):
    """Sensor entity for Vikunja task repeat interval unit."""

    def __init__(self, coordinator, base_url, task_id):
        """Initialize the sensor."""
        super().__init__(coordinator, base_url, task_id)

    @property
    def options(self):
        return RepeatUnit.list_display_values()

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.name_prefix()} Repeat Interval Unit"

    @property
    def state(self):
        """Return the state of the sensor."""
        unit, scaled_value = get_repeat_info_for_task(self.task)

        if unit is None:
            return None

        return unit.display

    async def async_select_option(self, option: str):
        """Handle user selection of a new repeat unit."""

        # Get the new unit
        unit = RepeatUnit.from_display(option)

        # Get the tasks current repeat unit and value
        current_unit, current_value = get_repeat_info_for_task(self.task)

        if current_unit is None or current_value is None:
            return None

        # Calculate the new repeat interval with the current value * new unit scale
        # e.g. 4 Days -> Change Days to Weeks -> calculate 4 * seconds in a week
        new_value = current_value * unit.seconds

        # Send update
        await self.task.set_repeating_interval(interval=timedelta(seconds=new_value))
        await self.update_task()

    @property
    def available(self) -> bool:
        if not self.task.repeat_enabled:
            return False

        if self.task.repeat_mode == RepeatMode.MONTHLY:
            return False
        else:
            return True

    @property
    def icon(self):
        """Icon for the sensor."""
        return "mdi:repeat"

    @property
    def unique_id(self) -> str:
        return self.id_prefix() + "_repeat_interval_unit"
