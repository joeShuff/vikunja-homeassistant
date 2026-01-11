from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.vikunja.const import DATA_KANBAN_KEY


class VikunjaKanbanSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:view-kanban"
    _attr_has_entity_name = True

    def __init__(self, coordinator, project_id: int | None, view_id: int | None) -> None:
        super().__init__(coordinator)
        self._project_id = project_id
        self._view_id = view_id
        if project_id and view_id:
            self._attr_unique_id = f"kanban_{project_id}_{view_id}"
        else:
            self._attr_unique_id = "kanban_unconfigured"

    @property
    def name(self) -> str:
        if self._project_id and self._view_id:
            return f"Kanban {self._project_id}"
        return "Kanban"

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        return data.get(DATA_KANBAN_KEY) is not None

    @property
    def native_value(self):
        data = (self.coordinator.data or {}).get(DATA_KANBAN_KEY)
        if not isinstance(data, dict):
            return None
        buckets = data.get("buckets")
        if not isinstance(buckets, list):
            return 0
        return len(buckets)

    @property
    def extra_state_attributes(self):
        data = (self.coordinator.data or {}).get(DATA_KANBAN_KEY)
        if not isinstance(data, dict):
            return {}
        return {
            "project_id": data.get("project_id"),
            "view_id": data.get("view_id"),
            "buckets": data.get("buckets"),
            "tasks": data.get("tasks"),
        }
