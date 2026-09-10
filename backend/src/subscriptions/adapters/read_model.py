"""Subscriptions read model projections."""

from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from backend.src.shared.domain.events import DomainEvent, EventHandler
from backend.src.subscriptions.adapters.orm import (
    allocation_log_table,
    writer_subscribers_table,
    writer_followers_table,
)
from backend.src.subscriptions.domain.model import AllocationAction, AllocationChanged

if TYPE_CHECKING:
    from backend.src.identity.domain.model import User
    from backend.src.subscriptions.domain.model import Subscription


def _dialect(session: Session) -> str:
    bind = session.get_bind()
    return bind.dialect.name if bind is not None else ""


def _upsert_subscriber(
    session: Session,
    writer_id: UUID,
    reader_id: UUID,
    subscription_id: UUID,
    allocated_at: datetime,
) -> None:
    """Insert or refresh a writer_subscribers row (portable across dialects)."""
    if _dialect(session) == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        session.execute(
            pg_insert(writer_subscribers_table)
            .values(
                writer_id=writer_id,
                reader_id=reader_id,
                subscription_id=subscription_id,
                allocated_at=allocated_at,
            )
            .on_conflict_do_update(
                index_elements=["writer_id", "reader_id"],
                set_={
                    "subscription_id": subscription_id,
                    "allocated_at": allocated_at,
                    "updated_at": allocated_at,
                },
            )
        )
        return
    existing = session.execute(
        select(writer_subscribers_table.c.subscription_id).where(
            writer_subscribers_table.c.writer_id == writer_id,
            writer_subscribers_table.c.reader_id == reader_id,
        )
    ).first()
    if existing is None:
        session.execute(
            insert(writer_subscribers_table).values(
                writer_id=writer_id,
                reader_id=reader_id,
                subscription_id=subscription_id,
                allocated_at=allocated_at,
            )
        )
    else:
        session.execute(
            update(writer_subscribers_table)
            .where(
                writer_subscribers_table.c.writer_id == writer_id,
                writer_subscribers_table.c.reader_id == reader_id,
            )
            .values(
                subscription_id=subscription_id,
                allocated_at=allocated_at,
                updated_at=allocated_at,
            )
        )


def _insert_follower_ignore(
    session: Session, writer_id: UUID, reader_id: UUID, followed_at: datetime
) -> None:
    """Add a writer_followers row unless present (portable across dialects)."""
    if _dialect(session) == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        session.execute(
            pg_insert(writer_followers_table)
            .values(
                writer_id=writer_id,
                reader_id=reader_id,
                followed_at=followed_at,
            )
            .on_conflict_do_nothing()
        )
        return
    exists = session.execute(
        select(writer_followers_table.c.writer_id).where(
            writer_followers_table.c.writer_id == writer_id,
            writer_followers_table.c.reader_id == reader_id,
        )
    ).first()
    if exists is None:
        session.execute(
            insert(writer_followers_table).values(
                writer_id=writer_id,
                reader_id=reader_id,
                followed_at=followed_at,
            )
        )


class AllocationLogProjection(EventHandler[AllocationChanged]):
    """Persist AllocationChanged events to allocation_log audit table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_uuid(value) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(str(value))

    def handle(self, event: AllocationChanged) -> None:
        action = event.action.value if hasattr(event.action, "value") else str(event.action)
        self._session.execute(
            insert(allocation_log_table).values(
                subscription_id=self._to_uuid(event.aggregate_id),
                reader_id=self._to_uuid(event.reader_id),
                action=action,
                writer_id=self._to_uuid(event.writer_id),
                previous_writer_id=self._to_uuid(event.previous_writer_id),
                credits_spent=event.credits_spent,
                remaining_credits=event.remaining_credits,
                empty_slots_before=event.empty_slots_before,
                empty_slots_after=event.empty_slots_after,
                created_at=event.occurred_at,
            )
        )


class WriterSubscribersProjection(EventHandler[AllocationChanged]):
    """Project AllocationChanged events to writer_subscribers read model."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def handle(self, event: AllocationChanged) -> None:
        action = AllocationAction(event.action)
        to_uuid = AllocationLogProjection._to_uuid
        writer_id = to_uuid(event.writer_id)
        previous_writer_id = to_uuid(event.previous_writer_id)
        reader_id = to_uuid(event.reader_id)
        subscription_id = to_uuid(event.aggregate_id)

        if action == AllocationAction.ALLOCATE and writer_id:
            # Add subscriber with allocation
            assert reader_id is not None and subscription_id is not None
            _upsert_subscriber(
                self._session, writer_id, reader_id, subscription_id, event.occurred_at
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
            assert reader_id is not None and subscription_id is not None
            self._session.execute(
                delete(writer_subscribers_table).where(
                    writer_subscribers_table.c.writer_id == previous_writer_id,
                    writer_subscribers_table.c.reader_id == reader_id,
                )
            )
            # Add to new writer's subscribers
            _upsert_subscriber(
                self._session, writer_id, reader_id, subscription_id, event.occurred_at
            )
            # Remove from new writer's followers
            self._session.execute(
                delete(writer_followers_table).where(
                    writer_followers_table.c.writer_id == writer_id,
                    writer_followers_table.c.reader_id == reader_id,
                )
            )
            # Add to old writer's followers (they still follow, just no allocation)
            _insert_follower_ignore(
                self._session, previous_writer_id, reader_id, event.occurred_at
            )

        elif action == AllocationAction.RELEASE and previous_writer_id:
            # Remove from subscribers
            assert reader_id is not None
            self._session.execute(
                delete(writer_subscribers_table).where(
                    writer_subscribers_table.c.writer_id == previous_writer_id,
                    writer_subscribers_table.c.reader_id == reader_id,
                )
            )
            # Add to followers (they still follow the writer)
            _insert_follower_ignore(
                self._session, previous_writer_id, reader_id, event.occurred_at
            )


class SubscriptionStatusProjection(EventHandler[DomainEvent]):
    """Project subscription status changes to read models."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def handle(self, event: DomainEvent) -> None:
        if event.__class__.__name__ == "SubscriptionStatusChanged":
            new_status = getattr(event, "new_status", None)
            # NOTE: enum members are always truthy; plain values compare
            # against "active". Structured to keep mypy narrowing sound.
            if hasattr(new_status, "value"):
                became_inactive = True
            else:
                became_inactive = new_status != "active"
            if became_inactive:
                # Subscription became inactive - remove all allocations
                sub_id = AllocationLogProjection._to_uuid(event.aggregate_id)
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
    from datetime import datetime

    _insert_follower_ignore(session, writer_id, reader_id, datetime.utcnow())


def remove_follower(session: Session, writer_id: UUID, reader_id: UUID) -> None:
    """Remove a follower."""
    session.execute(
        delete(writer_followers_table).where(
            writer_followers_table.c.writer_id == writer_id,
            writer_followers_table.c.reader_id == reader_id,
        )
    )
