"""Resolve user input into existing Vikunja labels."""
from __future__ import annotations

from homeassistant.exceptions import ServiceValidationError
from pyvikunja.api import VikunjaAPI
from pyvikunja.models.label import Label


async def async_resolve_labels(api: VikunjaAPI, *identifier_lists: list[str] | None) -> list[list[Label] | None]:
    """Resolve lists of label titles (case-insensitive) or label IDs into existing Vikunja labels.

    Returns one list of labels per given list. A list that is None stays None, so "not given"
    can be told apart from "empty". The labels are fetched from Vikunja at most once.
    Raises ServiceValidationError for unknown labels and for titles shared by several labels.
    """
    cleaned = [_clean(identifiers) for identifiers in identifier_lists]
    available = await api.get_labels() if any(cleaned) else []

    return [
        None if identifiers is None
        else list({label.id: label for label in (_find_label(i, available) for i in identifiers)}.values())
        for identifiers in cleaned
    ]


def _clean(identifiers: list[str] | None) -> list[str] | None:
    """Strip the identifiers and drop empty ones; None stays None."""
    if identifiers is None:
        return None
    return [identifier for identifier in (str(i).strip() for i in identifiers) if identifier]


def _find_label(identifier: str, available: list[Label]) -> Label:
    """Find a label by ID, or else by title (case-insensitive)."""
    if identifier.isdigit():
        label = next((l for l in available if l.id == int(identifier)), None)
        if label is not None:
            return label

    matches = [l for l in available if l.title.casefold() == identifier.casefold()]
    if len(matches) > 1:
        raise ServiceValidationError(
            f"Several Vikunja labels are named '{identifier}' "
            f"(IDs: {', '.join(str(l.id) for l in matches)}). Use the label ID instead."
        )
    if not matches:
        titles = sorted({l.title for l in available}, key=lambda title: (title.casefold(), title))
        raise ServiceValidationError(
            f"Unknown Vikunja label '{identifier}'. Available labels: {', '.join(titles) or 'none'}."
        )
    return matches[0]
