"""Resolve user input into existing Vikunja labels."""
from __future__ import annotations

from homeassistant.exceptions import ServiceValidationError
from pyvikunja.api import VikunjaAPI
from pyvikunja.models.label import Label


async def async_resolve_labels(api: VikunjaAPI, identifiers: list[str]) -> list[Label]:
    """Resolve label titles (case-insensitive) or label IDs into existing Vikunja labels.

    Raises ServiceValidationError for unknown labels and for titles shared by several labels.
    """
    identifiers = [str(identifier).strip() for identifier in identifiers]
    identifiers = [identifier for identifier in identifiers if identifier]
    if not identifiers:
        return []

    available = await api.get_labels()
    resolved: dict[int, Label] = {}

    for identifier in identifiers:
        label = None

        if identifier.isdigit():
            label = next((l for l in available if l.id == int(identifier)), None)

        if label is None:
            matches = [l for l in available if l.title.casefold() == identifier.casefold()]
            if len(matches) > 1:
                raise ServiceValidationError(
                    f"Several Vikunja labels are named '{identifier}' "
                    f"(IDs: {', '.join(str(l.id) for l in matches)}). Use the label ID instead."
                )
            label = matches[0] if matches else None

        if label is None:
            titles = sorted({l.title for l in available}, key=lambda title: (title.casefold(), title))
            known = ", ".join(titles) or "none"
            raise ServiceValidationError(f"Unknown Vikunja label '{identifier}'. Available labels: {known}.")

        resolved[label.id] = label

    return list(resolved.values())
