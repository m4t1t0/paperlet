"""Identity repository interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from backend.src.identity.domain.model import User


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