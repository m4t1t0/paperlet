"""Subscriptions repository interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from backend.src.subscriptions.domain.model import Subscription


class SubscriptionRepository(ABC):
    """Abstract repository for Subscription aggregate."""

    @abstractmethod
    def add(self, subscription: Subscription) -> None:
        """Add a subscription."""
        ...

    @abstractmethod
    def get(self, subscription_id: UUID) -> Optional[Subscription]:
        """Get subscription by ID."""
        ...

    @abstractmethod
    def get_by_reader(self, reader_id: UUID) -> Optional[Subscription]:
        """Get active subscription for a reader."""
        ...

    @abstractmethod
    def get_by_external_id(self, external_id: str) -> Optional[Subscription]:
        """Get subscription by external payment gateway ID."""
        ...
