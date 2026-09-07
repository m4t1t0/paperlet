"""SQLAlchemy Subscription repository implementation."""
from __future__ import annotations
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.src.subscriptions.adapters.repository import SubscriptionRepository
from backend.src.subscriptions.domain.model import Subscription, SubscriptionStatus


class SqlAlchemySubscriptionRepository(SubscriptionRepository):
    """SQLAlchemy implementation of SubscriptionRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, subscription: Subscription) -> None:
        self._session.add(subscription)

    def get(self, subscription_id: UUID) -> Optional[Subscription]:
        return self._session.get(Subscription, subscription_id)

    def get_by_reader(self, reader_id: UUID) -> Optional[Subscription]:
        return (
            self._session.query(Subscription)
            .filter(Subscription.reader_id == reader_id)
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
            .first()
        )

    def get_by_external_id(self, external_id: str) -> Optional[Subscription]:
        return (
            self._session.query(Subscription)
            .filter(Subscription.external_subscription_id == external_id)
            .first()
        )