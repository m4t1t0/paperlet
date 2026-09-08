"""Identity repository interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from backend.src.identity.domain.model import User, Session


class UserRepository(ABC):
    """Abstract repository for User aggregate."""

    @abstractmethod
    def add(self, user: User) -> None:
        """Add a user."""
        ...

    @abstractmethod
    def get(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        ...

    @abstractmethod
    def list(self) -> list[User]:
        """List all users."""
        ...


class SessionRepository(ABC):
    """Abstract repository for Session."""

    @abstractmethod
    def add(self, session: Session) -> None:
        """Add a session."""
        ...

    @abstractmethod
    def get(self, session_id: UUID) -> Optional[Session]:
        """Get session by ID."""
        ...

    @abstractmethod
    def get_by_refresh_token_hash(self, token_hash: str) -> Optional[Session]:
        """Get session by refresh token hash."""
        ...

    @abstractmethod
    def get_active_by_user(self, user_id: UUID) -> Optional[Session]:
        """Get active session for user."""
        ...
