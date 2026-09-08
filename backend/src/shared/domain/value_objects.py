"""Value objects for domain identifiers."""

from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class EntityId(Generic[T]):
    """Base class for typed entity IDs."""

    value: UUID = field(default_factory=uuid4)

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EntityId):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True)
class UserId(EntityId["User"]):
    """User identifier."""

    pass


@dataclass(frozen=True)
class SubscriptionId(EntityId["Subscription"]):
    """Subscription identifier."""

    pass


@dataclass(frozen=True)
class PostId(EntityId["Post"]):
    """Post identifier."""

    pass


@dataclass(frozen=True)
class WriterId(EntityId["User"]):
    """Writer identifier (subset of User)."""

    pass


@dataclass(frozen=True)
class ReaderId(EntityId["User"]):
    """Reader identifier (subset of User)."""

    pass
