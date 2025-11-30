from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from custom_components.vikunja.const import LOGGER


async def remove_task_with_entities(hass, config_id, task_id):
    """Remove all entities linked to a Vikunja task within the correct config entry."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    devices_to_check = set()
    entities_to_remove = []

    for entry in ent_reg.entities.values():
        if entry.unique_id.startswith(f"task_{task_id}_") and entry.config_entry_id == config_id:
            entities_to_remove.append(entry.entity_id)
            if entry.device_id:
                devices_to_check.add(entry.device_id)

    # Remove each entity
    for entity_id in entities_to_remove:
        ent_reg.async_remove(entity_id)

    for device_id in devices_to_check:
        dev_reg.async_remove_device(device_id)


async def remove_project_entities(hass, config_id, project_id):
    """Remove all entities linked to a Vikunja project within the correct config entry."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    devices_to_check = set()
    entities_to_remove = []

    # Remove todo list entity for the project
    for entry in ent_reg.entities.values():
        if entry.config_entry_id == config_id:
            # Check for todo list entity (unique_id: todo_list_{project_id})
            if entry.unique_id == f"todo_list_{project_id}":
                LOGGER.info(f"Marking todo list entity for removal: {entry.entity_id}")
                entities_to_remove.append(entry.entity_id)
                if entry.device_id:
                    devices_to_check.add(entry.device_id)

    # Remove each entity
    for entity_id in entities_to_remove:
        LOGGER.info(f"Removing entity: {entity_id}")
        ent_reg.async_remove(entity_id)

    for device_id in devices_to_check:
        LOGGER.info(f"Removing device: {device_id}")
        dev_reg.async_remove_device(device_id)