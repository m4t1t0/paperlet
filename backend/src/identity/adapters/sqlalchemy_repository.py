"""SQLAlchemy User repository implementation."""
from __future__ import annotations
from typing import Optional
from uuid import UUID
import json

from sqlalchemy.orm import Session

from backend.src.identity.adapters.repository import UserRepository
from backend.src.identity.domain.model import User, UserRole


def _roles_to_json(roles: set[UserRole]) -> str:
    return json.dumps([r.value for r in roles])


def _json_to_roles(json_str: str) -> set[UserRole]:
    if not json_str:
        return {UserRole.READER}
    try:
        role_values = json.loads(json_str)
        return {UserRole(r) for r in role_values}
    except (json.JSONDecodeError, ValueError):
        return {UserRole.READER}


class SqlAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of UserRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> None:
        # Sync roles to JSON column before saving
        user._roles_json = _roles_to_json(user.roles)
        self._session.add(user)

    def get(self, user_id: UUID) -> Optional[User]:
        user = self._session.get(User, user_id)
        if user:
            # Convert JSON to roles set
            user.roles = _json_to_roles(user._roles_json)
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        user = self._session.query(User).filter(User.email == email.lower().strip()).first()
        if user:
            user.roles = _json_to_roles(user._roles_json)
        return user

    def list(self) -> list[User]:
        users = self._session.query(User).all()
        for user in users:
            user.roles = _json_to_roles(user._roles_json)
        return users