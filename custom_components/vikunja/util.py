from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr


async def remove_task_with_entities(hass, config_id, task_id):
    """Remove all entities linked to a Vikunja task within the correct config entry."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    devices_to_check = set()
    entities_to_remove = []

    for entry in ent_reg.entities.values():
        if entry.unique_id.startswith(f"task_{task_id}") and entry.config_entry_id == config_id:
            entities_to_remove.append(entry.entity_id)
            if entry.device_id:
                devices_to_check.add(entry.device_id)

    # Remove each entity
    for entity_id in entities_to_remove:
        ent_reg.async_remove(entity_id)

    for device_id in devices_to_check:
        dev_reg.async_remove_device(device_id)