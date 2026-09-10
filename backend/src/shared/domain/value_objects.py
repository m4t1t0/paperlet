"""Value objects for domain identifiers."""

from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from typing import Generic, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    # Quoted forward refs for the `EntityId["..."]` bases below (mypy-only).
    from backend.src.identity.domain.model import User  # noqa: F401
    from backend.src.publishing.domain.model import Post  # noqa: F401
    from backend.src.subscriptions.domain.model import Subscription  # noqa: F401

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


@dataclass(frozen=True)
class Money:
    """Money value object (integer minor units + currency, no float math)."""

    cents: int
    currency: str = "EUR"

    def __post_init__(self) -> None:
        if self.cents < 0:
            raise ValueError("Money amount cannot be negative")
        if not self.currency or len(self.currency) != 3:
            raise ValueError("Currency must be a 3-letter code")

    @classmethod
    def from_eur(cls, amount: float) -> Money:
        """Build from a euro float (rounded to cents)."""
        import math

        if not isinstance(amount, (int, float)) or math.isnan(amount):
            raise ValueError("Invalid euro amount")
        return cls(cents=int(round(amount * 100)), currency="EUR")

    @property
    def eur(self) -> float:
        """Amount in euros (display only; arithmetic should use cents)."""
        return self.cents / 100

    def __str__(self) -> str:
        return f"{self.eur:.2f} {self.currency}"
