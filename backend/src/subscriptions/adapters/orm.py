"""Subscriptions SQLAlchemy models."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Table, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from backend.src.subscriptions.domain.model import (
    Subscription,
    SubscriptionStatus,
    AllocationSlot,
    AllocationAction,
)
from backend.src.shared.database import mapper_registry, metadata


subscriptions_table = Table(
    "subscriptions",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("reader_id", PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True),
    Column("status", String(20), nullable=False, default=SubscriptionStatus.INCOMPLETE.value),
    Column("billing_cycle_start", DateTime, nullable=False, default=datetime.utcnow),
    Column("change_credits", Integer, nullable=False, default=2),
    Column("external_subscription_id", String(255), unique=True, nullable=True, index=True),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False),
)

allocation_slots_table = Table(
    "allocation_slots",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("subscription_id", PG_UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("slot_index", Integer, nullable=False),
    Column("writer_id", PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True),
    Column("allocated_at", DateTime, nullable=True),
)

allocation_log_table = Table(
    "allocation_log",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("subscription_id", PG_UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("reader_id", PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    Column("action", String(20), nullable=False),
    Column("writer_id", PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True),
    Column("previous_writer_id", PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True),
    Column("credits_spent", Integer, nullable=False),
    Column("remaining_credits", Integer, nullable=False),
    Column("empty_slots_before", Integer, nullable=False),
    Column("empty_slots_after", Integer, nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
)


def start_mappers() -> None:
    """Start SQLAlchemy mappers."""
    from sqlalchemy.orm import class_mapper
    
    # Check if already mapped
    try:
        class_mapper(Subscription)
        return  # Already mapped
    except Exception:
        pass  # Not mapped yet
    
    mapper_registry.map_imperatively(
        AllocationSlot,
        allocation_slots_table,
        properties={},
    )
    mapper_registry.map_imperatively(
        Subscription,
        subscriptions_table,
        properties={
            "slots": relationship(
                AllocationSlot,
                backref="subscription",
                cascade="all, delete-orphan",
                collection_class=list,
                order_by=allocation_slots_table.c.slot_index,
                lazy="joined",
            ),
        },
    )


def create_tables(engine) -> None:
    """Create all tables."""
    metadata.create_all(engine)


def drop_tables(engine) -> None:
    """Drop all tables."""
    metadata.drop_all(engine)