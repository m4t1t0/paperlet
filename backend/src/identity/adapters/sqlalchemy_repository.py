"""SQLAlchemy User repository implementation."""

from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session as SQLAlchemySession

from backend.src.identity.domain.repository import UserRepository, SessionRepository
from backend.src.identity.domain.model import User, Session, UserRole


def _roles_to_json(roles: set[UserRole]) -> str:
    return json.dumps([r.value for r in roles])


def _json_to_roles(json_str: str | None) -> set[UserRole]:
    if not json_str:
        return {UserRole.READER}
    try:
        role_values = json.loads(json_str)
        return {UserRole(r) for r in role_values}
    except (json.JSONDecodeError, ValueError):
        return {UserRole.READER}


def _hydrate_roles(user: User) -> User:
    persisted = user.__dict__.get("_roles_persisted")
    user.roles = _json_to_roles(persisted)
    return user


class SqlAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of UserRepository."""

    def __init__(self, session: SQLAlchemySession) -> None:
        self._session = session

    def add(self, user: User) -> None:
        user._roles_persisted = _roles_to_json(user.roles)  # type: ignore[attr-defined]
        self._session.add(user)

    def get(self, user_id: UUID) -> Optional[User]:
        user = self._session.get(User, user_id)
        if user:
            _hydrate_roles(user)
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        user = (
            self._session.query(User)
            .filter(User.email == email.lower().strip())
            .first()
        )
        if user:
            _hydrate_roles(user)
        return user

    def list(self) -> list[User]:
        users = self._session.query(User).all()
        for user in users:
            _hydrate_roles(user)
        return users


class SqlAlchemySessionRepository(SessionRepository):
    """SQLAlchemy implementation of SessionRepository."""

    def __init__(self, session: SQLAlchemySession) -> None:
        self._session = session

    def add(self, session: Session) -> None:
        self._session.add(session)

    def get(self, session_id: UUID) -> Optional[Session]:
        return self._session.get(Session, session_id)

    def get_by_refresh_token_hash(self, token_hash: str) -> Optional[Session]:
        return (
            self._session.query(Session)
            .filter(Session.refresh_token_hash == token_hash)
            .first()
        )

    def get_active_by_user(self, user_id: UUID) -> Optional[Session]:
        from datetime import datetime

        now = datetime.utcnow()
        return (
            self._session.query(Session)
            .filter(Session.user_id == user_id)
            .filter(Session.revoked_at.is_(None))
            .filter(Session.expires_at > now)
            .first()
        )
