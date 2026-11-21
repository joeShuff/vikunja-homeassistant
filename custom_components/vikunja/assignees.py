"""Resolve user input into Vikunja users that can be assigned to tasks of a project."""
from __future__ import annotations

from homeassistant.exceptions import ServiceValidationError
from pyvikunja.models.project import Project
from pyvikunja.models.user import User


def user_identifier(user: User) -> str:
    """Return the identifier used for a user in action input and responses."""
    return user.username or str(user.id)


async def async_resolve_users(project: Project, *identifier_lists: list[str] | None) -> list[list[User] | None]:
    """Resolve lists of user IDs, usernames or display names (case-insensitive) into users of the project.

    Only users with access to the project can be assigned in Vikunja, so the project
    users (including owners and team members) are the candidates.
    Returns one list of users per given list. A list that is None stays None, so "not given"
    can be told apart from "empty". The project users are fetched from Vikunja at most once.
    Raises ServiceValidationError for unknown users and ambiguous display names.
    """
    cleaned = [_clean(identifiers) for identifiers in identifier_lists]
    candidates = await project.get_users() if any(cleaned) else []

    return [
        None if identifiers is None
        else list({user.id: user for user in (_find_user(i, candidates, project) for i in identifiers)}.values())
        for identifiers in cleaned
    ]


def _clean(identifiers: list[str] | None) -> list[str] | None:
    """Strip the identifiers and drop empty ones; None stays None."""
    if identifiers is None:
        return None
    return [identifier for identifier in (str(i).strip() for i in identifiers) if identifier]


def _find_user(identifier: str, candidates: list[User], project: Project) -> User:
    """Find a user by ID, else by username, else by display name (case-insensitive)."""
    folded = identifier.casefold()

    if identifier.isdigit():
        user = next((u for u in candidates if u.id == int(identifier)), None)
        if user is not None:
            return user

    user = next((u for u in candidates if u.username and u.username.casefold() == folded), None)
    if user is not None:
        return user

    matches = [u for u in candidates if u.name and u.name.casefold() == folded]
    if len(matches) > 1:
        raise ServiceValidationError(
            f"Several Vikunja users are named '{identifier}' "
            f"({', '.join(sorted(user_identifier(u) for u in matches))}). Use the username instead."
        )
    if not matches:
        known = sorted((user_identifier(u) for u in candidates), key=lambda name: (name.casefold(), name))
        raise ServiceValidationError(
            f"Unknown Vikunja user '{identifier}', or the user has no access to the project "
            f"'{project.title}'. Users with access: {', '.join(known) or 'none'}."
        )
    return matches[0]
