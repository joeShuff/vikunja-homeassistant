"""Resolve user input into Vikunja users that can be assigned to tasks of a project."""
from __future__ import annotations

from homeassistant.exceptions import ServiceValidationError
from pyvikunja.models.project import Project
from pyvikunja.models.user import User


def user_identifier(user: User) -> str:
    """Return the identifier used for a user in action input and responses."""
    return user.username or str(user.id)


async def async_resolve_users(project: Project, identifiers: list[str]) -> list[User]:
    """Resolve user IDs, usernames or display names (case-insensitive) into users of the project.

    Only users with access to the project can be assigned in Vikunja, so the project
    users (including owners and team members) are the candidates.
    Raises ServiceValidationError for unknown users and ambiguous display names.
    """
    identifiers = [str(identifier).strip() for identifier in identifiers]
    identifiers = [identifier for identifier in identifiers if identifier]
    if not identifiers:
        return []

    candidates = await project.get_users()
    resolved: dict[int, User] = {}

    for identifier in identifiers:
        folded = identifier.casefold()
        user = None

        if identifier.isdigit():
            user = next((u for u in candidates if u.id == int(identifier)), None)

        if user is None:
            user = next((u for u in candidates if u.username and u.username.casefold() == folded), None)

        if user is None:
            matches = [u for u in candidates if u.name and u.name.casefold() == folded]
            if len(matches) > 1:
                raise ServiceValidationError(
                    f"Several Vikunja users are named '{identifier}' "
                    f"({', '.join(sorted(user_identifier(u) for u in matches))}). Use the username instead."
                )
            user = matches[0] if matches else None

        if user is None:
            known = ", ".join(sorted((user_identifier(u) for u in candidates), key=lambda n: (n.casefold(), n)))
            raise ServiceValidationError(
                f"Unknown Vikunja user '{identifier}', or the user has no access to the project "
                f"'{project.title}'. Users with access: {known or 'none'}."
            )

        resolved[user.id] = user

    return list(resolved.values())
