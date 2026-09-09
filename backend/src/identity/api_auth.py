"""Shared Flask auth helpers, owned by the identity context.

Single implementation for resolving the current user from a Bearer token,
used by identity / subscriptions / publishing blueprints. Keeps JWT handling
and user-status checks in one place instead of duplicated per blueprint.
"""

from __future__ import annotations

from uuid import UUID

from flask import request
from werkzeug.exceptions import Unauthorized


def get_bearer_user_id() -> UUID:
    """Return the user id from a valid Authorization Bearer token (401 if bad)."""
    from backend.src.identity.service import JwtService

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise Unauthorized("Missing or invalid Authorization header")
    try:
        user_id, _ = JwtService().verify_access_token(auth_header[7:])
    except ValueError as e:
        raise Unauthorized(str(e))
    return user_id


def get_current_user(require_writer: bool = False) -> dict:
    """Return active user dict from Bearer token (401 if missing/invalid/inactive)."""
    from backend.src.identity.adapters.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
    )
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork

    user_id = get_bearer_user_id()
    with SqlAlchemyUnitOfWork() as uow:
        user = SqlAlchemyUserRepository(uow.session).get(user_id)
        if not user or not user.is_active:
            raise Unauthorized("User not found or inactive")
        if require_writer and not user.is_writer():
            raise Unauthorized("Writer capability required")
        return {
            "id": user.id,
            "is_writer": user.is_writer(),
            "is_reader": user.is_reader(),
        }


def get_current_reader() -> dict:
    """Get current user as reader (no writer requirement)."""
    return get_current_user(require_writer=False)


def get_current_writer() -> dict:
    """Get current user as writer."""
    return get_current_user(require_writer=True)


def get_optional_reader() -> dict | None:
    """Current reader if a Bearer token is present, else None (public preview).

    No header -> anonymous. Present-but-invalid header -> 401.
    """
    if not request.headers.get("Authorization", ""):
        return None
    return get_current_reader()


def get_optional_reader_id() -> UUID | None:
    """Reader id if a *valid* Bearer token is present, else None (never raises)."""
    try:
        return get_bearer_user_id()
    except Unauthorized:
        return None
    except Exception:
        return None
