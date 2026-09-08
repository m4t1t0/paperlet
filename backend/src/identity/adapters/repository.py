"""Identity SQLAlchemy repository implementations."""
from __future__ import annotations
from typing import Optional
from uuid import UUID
import json

from sqlalchemy.orm import Session as SQLAlchemySession

from backend.src.identity.domain.repository import UserRepository, SessionRepository
from backend.src.identity.domain.model import User, Session, UserRole


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

    def __init__(self, session: SQLAlchemySession) -> None:
        self._session = session

    def add(self, user: User) -> None:
        user._sync_roles_to_json()
        self._session.add(user)

    def get(self, user_id: UUID) -> Optional[User]:
        user = self._session.get(User, user_id)
        if user:
            user._load_roles_from_json()
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        user = self._session.query(User).filter(User.email == email.lower().strip()).first()
        if user:
            user._load_roles_from_json()
        return user

    def list(self) -> list[User]:
        users = self._session.query(User).all()
        for user in users:
            user._load_roles_from_json()
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
        return self._session.query(Session).filter(Session.refresh_token_hash == token_hash).first()

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
