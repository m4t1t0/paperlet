"""Unit of Work pattern implementation."""

from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

T = TypeVar("T")


class AbstractRepository(ABC, Generic[T]):
    """Abstract base repository."""

    @abstractmethod
    def add(self, entity: T) -> None:
        """Add an entity."""
        ...

    @abstractmethod
    def get(self, id: UUID) -> T | None:
        """Get entity by ID."""
        ...

    @abstractmethod
    def list(self) -> list[T]:
        """List all entities."""
        ...


class AbstractUnitOfWork(AbstractContextManager, ABC):
    """Abstract Unit of Work."""

    def __init__(self) -> None:
        self._events: list = []

    @abstractmethod
    def __enter__(self) -> AbstractUnitOfWork: ...

    @abstractmethod
    def __exit__(self, *args: Any) -> None: ...

    @abstractmethod
    def commit(self) -> None:
        """Commit the transaction."""
        ...

    @abstractmethod
    def rollback(self) -> None:
        """Rollback the transaction."""
        ...

    @abstractmethod
    def collect_new_events(self) -> list:
        """Collect new domain events from all tracked aggregates."""
        ...

    @property
    @abstractmethod
    def session(self) -> Session:
        """Get the SQLAlchemy session."""
        ...
