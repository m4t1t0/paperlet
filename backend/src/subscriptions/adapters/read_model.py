"""Subscriptions read model projections."""

from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from backend.src.shared.domain.events import DomainEvent, EventHandler
from backend.src.subscriptions.adapters.orm import (
    writer_subscribers_table,
    writer_followers_table,
)
from backend.src.subscriptions.domain.model import AllocationAction, AllocationChanged

if TYPE_CHECKING:
    from backend.src.identity.domain.model import User
    from backend.src.subscriptions.domain.model import Subscription


class WriterSubscribersProjection(EventHandler[AllocationChanged]):
    """Project AllocationChanged events to writer_subscribers read model."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def handle(self, event: AllocationChanged) -> None:
        action = AllocationAction(event.action)
        writer_id = UUID(event.writer_id) if event.writer_id else None
        previous_writer_id = (
            UUID(event.previous_writer_id) if event.previous_writer_id else None
        )
        reader_id = UUID(event.reader_id)

        if action == AllocationAction.ALLOCATE and writer_id:
            # Add subscriber with allocation
            self._session.execute(
                insert(writer_subscribers_table)
                .values(
                    writer_id=writer_id,
                    reader_id=reader_id,
                    subscription_id=UUID(event.aggregate_id),
                    allocated_at=event.occurred_at,
                )
                .on_conflict_do_update(
                    index_elements=["writer_id", "reader_id"],
                    set_={
                        "subscription_id": UUID(event.aggregate_id),
                        "allocated_at": event.occurred_at,
                        "updated_at": event.occurred_at,
                    },
                )
            )
            # Remove from followers if present
            self._session.execute(
                delete(writer_followers_table).where(
                    writer_followers_table.c.writer_id == writer_id,
                    writer_followers_table.c.reader_id == reader_id,
                )
            )

        elif action == AllocationAction.SWAP and writer_id and previous_writer_id:
            # Remove from old writer's subscribers
            self._session.execute(
                delete(writer_subscribers_table).where(
                    writer_subscribers_table.c.writer_id == previous_writer_id,
                    writer_subscribers_table.c.reader_id == reader_id,
                )
            )
            # Add to new writer's subscribers
            self._session.execute(
                insert(writer_subscribers_table)
                .values(
                    writer_id=writer_id,
                    reader_id=reader_id,
                    subscription_id=UUID(event.aggregate_id),
                    allocated_at=event.occurred_at,
                )
                .on_conflict_do_update(
                    index_elements=["writer_id", "reader_id"],
                    set_={
                        "subscription_id": UUID(event.aggregate_id),
                        "allocated_at": event.occurred_at,
                        "updated_at": event.occurred_at,
                    },
                )
            )
            # Remove from new writer's followers
            self._session.execute(
                delete(writer_followers_table).where(
                    writer_followers_table.c.writer_id == writer_id,
                    writer_followers_table.c.reader_id == reader_id,
                )
            )
            # Add to old writer's followers (they still follow, just no allocation)
            self._session.execute(
                insert(writer_followers_table)
                .values(
                    writer_id=previous_writer_id,
                    reader_id=reader_id,
                    followed_at=event.occurred_at,
                )
                .on_conflict_do_nothing()
            )

        elif action == AllocationAction.RELEASE and previous_writer_id:
            # Remove from subscribers
            self._session.execute(
                delete(writer_subscribers_table).where(
                    writer_subscribers_table.c.writer_id == previous_writer_id,
                    writer_subscribers_table.c.reader_id == reader_id,
                )
            )
            # Add to followers (they still follow the writer)
            self._session.execute(
                insert(writer_followers_table)
                .values(
                    writer_id=previous_writer_id,
                    reader_id=reader_id,
                    followed_at=event.occurred_at,
                )
                .on_conflict_do_nothing()
            )


class SubscriptionStatusProjection(EventHandler[DomainEvent]):
    """Project subscription status changes to read models."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def handle(self, event: DomainEvent) -> None:
        if event.__class__.__name__ == "SubscriptionStatusChanged":
            new_status = event.new_status
            if (
                new_status.value
                if hasattr(new_status, "value")
                else new_status != "active"
            ):
                # Subscription became inactive - remove all allocations
                sub_id = UUID(event.aggregate_id)
                self._session.execute(
                    delete(writer_subscribers_table).where(
                        writer_subscribers_table.c.subscription_id == sub_id
                    )
                )
                # Note: We keep followers as they may still want to follow


def get_subscribers_with_allocation(
    session: Session, writer_id: UUID
) -> list[tuple["User", "Subscription"]]:
    """Get all users with active allocation to a writer."""
    from backend.src.identity.adapters.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
    )
    from backend.src.subscriptions.adapters.sqlalchemy_repository import (
        SqlAlchemySubscriptionRepository,
    )

    user_repo = SqlAlchemyUserRepository(session)
    sub_repo = SqlAlchemySubscriptionRepository(session)

    rows = session.execute(
        select(
            writer_subscribers_table.c.reader_id,
            writer_subscribers_table.c.subscription_id,
        ).where(writer_subscribers_table.c.writer_id == writer_id)
    ).all()

    result = []
    for reader_id, sub_id in rows:
        user = user_repo.get(reader_id)
        subscription = sub_repo.get(sub_id)
        if user and subscription:
            result.append((user, subscription))
    return result


def get_followers_without_allocation(session: Session, writer_id: UUID) -> list["User"]:
    """Get users following a writer but without allocation."""
    from backend.src.identity.adapters.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
    )

    user_repo = SqlAlchemyUserRepository(session)

    rows = session.execute(
        select(writer_followers_table.c.reader_id).where(
            writer_followers_table.c.writer_id == writer_id
        )
    ).all()

    result = []
    for (reader_id,) in rows:
        user = user_repo.get(reader_id)
        if user:
            result.append(user)
    return result


def add_follower(session: Session, writer_id: UUID, reader_id: UUID) -> None:
    """Add a follower (when user follows a writer without allocation)."""
    session.execute(
        insert(writer_followers_table)
        .values(
            writer_id=writer_id,
            reader_id=reader_id,
        )
        .on_conflict_do_nothing()
    )


def remove_follower(session: Session, writer_id: UUID, reader_id: UUID) -> None:
    """Remove a follower."""
    session.execute(
        delete(writer_followers_table).where(
            writer_followers_table.c.writer_id == writer_id,
            writer_followers_table.c.reader_id == reader_id,
        )
    )
