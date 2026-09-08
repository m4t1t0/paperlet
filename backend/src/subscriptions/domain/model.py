"""Subscriptions domain model."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import reconstructor

from backend.src.shared.domain.events import AggregateRoot, DomainEvent
from backend.src.shared.config import get_settings


class SubscriptionStatus(str, Enum):
    """Subscription status."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class AllocationAction(str, Enum):
    """Allocation log action types."""

    ALLOCATE = "allocate"
    SWAP = "swap"
    RELEASE = "release"


@dataclass
class AllocationSlot:
    """A single allocation slot in a subscription."""

    writer_id: Optional[UUID] = None
    allocated_at: Optional[datetime] = None
    slot_index: int = 0

    @property
    def is_empty(self) -> bool:
        return self.writer_id is None


class SubscriptionCreated(DomainEvent):
    """Event emitted when subscription is created."""

    reader_id: UUID
    status: SubscriptionStatus
    billing_cycle_start: datetime


class SubscriptionStatusChanged(DomainEvent):
    """Event emitted when subscription status changes."""

    reader_id: UUID
    old_status: SubscriptionStatus
    new_status: SubscriptionStatus


class AllocationChanged(DomainEvent):
    """Event emitted when allocation changes."""

    reader_id: UUID
    action: AllocationAction
    writer_id: Optional[UUID]
    previous_writer_id: Optional[UUID]
    credits_spent: int
    remaining_credits: int
    empty_slots_before: int
    empty_slots_after: int


class BillingCycleRenewed(DomainEvent):
    """Event emitted when billing cycle renews (credits reset)."""

    reader_id: UUID
    new_cycle_start: datetime
    credits_reset_to: int


class Subscription(AggregateRoot):
    """Subscription aggregate - owns allocation slots and change credits."""

    MAX_SLOTS: int = 5
    CREDITS_PER_CYCLE: int = 2

    def __init__(
        self,
        id: UUID,
        reader_id: UUID,
        status: SubscriptionStatus = SubscriptionStatus.INCOMPLETE,
        billing_cycle_start: Optional[datetime] = None,
        change_credits: int = CREDITS_PER_CYCLE,
        slots: Optional[list[AllocationSlot]] = None,
        external_subscription_id: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.reader_id = reader_id
        self.status = status
        self.billing_cycle_start = billing_cycle_start or datetime.utcnow()
        self.change_credits = change_credits
        self.slots = slots or [
            AllocationSlot(writer_id=None, allocated_at=None)
            for _ in range(self.MAX_SLOTS)
        ]
        # Set slot_index for each slot
        for i, slot in enumerate(self.slots):
            slot.slot_index = i
        self.external_subscription_id = external_subscription_id
        self.updated_at = datetime.utcnow()

    @reconstructor
    def _init_on_load(self) -> None:
        """Initialize _events when loaded from database."""
        super().__init__()

    @classmethod
    def create(
        cls,
        reader_id: UUID,
        external_subscription_id: str,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    ) -> Subscription:
        """Create a new subscription."""
        settings = get_settings()
        subscription = cls(
            id=uuid4(),
            reader_id=reader_id,
            status=status,
            billing_cycle_start=datetime.utcnow(),
            change_credits=settings.change_credits_per_billing_cycle,
            external_subscription_id=external_subscription_id,
        )
        subscription.add_event(
            SubscriptionCreated(
                aggregate_id=subscription.id,
                aggregate_type="Subscription",
                reader_id=reader_id,
                status=status,
                billing_cycle_start=subscription.billing_cycle_start,
            )
        )
        return subscription

    @property
    def empty_slots(self) -> int:
        """Count of empty allocation slots."""
        return sum(1 for slot in self.slots if slot.is_empty)

    @property
    def allocated_slots(self) -> list[AllocationSlot]:
        """Get allocated (non-empty) slots."""
        return [slot for slot in self.slots if not slot.is_empty]

    @property
    def allocated_writer_ids(self) -> set[UUID]:
        """Get set of writer IDs currently allocated."""
        return {slot.writer_id for slot in self.allocated_slots}

    def is_writer_allocated(self, writer_id: UUID) -> bool:
        """Check if a writer is already allocated."""
        return writer_id in self.allocated_writer_ids

    def get_slot_for_writer(self, writer_id: UUID) -> Optional[AllocationSlot]:
        """Get the slot allocated to a specific writer."""
        for slot in self.slots:
            if slot.writer_id == writer_id:
                return slot
        return None

    def get_empty_slot(self) -> Optional[AllocationSlot]:
        """Get first empty slot."""
        for slot in self.slots:
            if slot.is_empty:
                return slot
        return None

    def allocate_writer(self, writer_id: UUID) -> int:
        """
        Allocate an empty slot to a writer.
        Returns credits spent (always 0 for filling empty slot).
        Raises ValueError if no empty slots or writer already allocated.
        """
        if self.status != SubscriptionStatus.ACTIVE:
            raise ValueError("Subscription is not active")

        if self.is_writer_allocated(writer_id):
            raise ValueError("Writer already allocated")

        empty_slot = self.get_empty_slot()
        if not empty_slot:
            raise ValueError("No empty slots available")

        empty_slot.writer_id = writer_id
        empty_slot.allocated_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        self.add_event(
            AllocationChanged(
                aggregate_id=self.id,
                aggregate_type="Subscription",
                reader_id=self.reader_id,
                action=AllocationAction.ALLOCATE,
                writer_id=writer_id,
                previous_writer_id=None,
                credits_spent=0,
                remaining_credits=self.change_credits,
                empty_slots_before=self.empty_slots + 1,
                empty_slots_after=self.empty_slots,
            )
        )
        return 0

    def swap_writer(self, current_writer_id: UUID, new_writer_id: UUID) -> int:
        """
        Swap one writer for another.
        Returns credits spent (always 1).
        Raises ValueError if no credits, writer not allocated, or new writer already allocated.
        """
        if self.status != SubscriptionStatus.ACTIVE:
            raise ValueError("Subscription is not active")

        if self.change_credits <= 0:
            raise ValueError("No change credits remaining this billing cycle")

        if self.is_writer_allocated(new_writer_id):
            raise ValueError("New writer already allocated")

        slot = self.get_slot_for_writer(current_writer_id)
        if not slot:
            raise ValueError("Current writer not allocated")

        previous_writer_id = slot.writer_id
        slot.writer_id = new_writer_id
        slot.allocated_at = datetime.utcnow()
        self.change_credits -= 1
        self.updated_at = datetime.utcnow()

        self.add_event(
            AllocationChanged(
                aggregate_id=self.id,
                aggregate_type="Subscription",
                reader_id=self.reader_id,
                action=AllocationAction.SWAP,
                writer_id=new_writer_id,
                previous_writer_id=previous_writer_id,
                credits_spent=1,
                remaining_credits=self.change_credits,
                empty_slots_before=self.empty_slots,
                empty_slots_after=self.empty_slots,
            )
        )
        return 1

    def release_writer(self, writer_id: UUID) -> int:
        """
        Release a writer allocation.
        Returns credits spent (always 1).
        Raises ValueError if no credits or writer not allocated.
        """
        if self.status != SubscriptionStatus.ACTIVE:
            raise ValueError("Subscription is not active")

        if self.change_credits <= 0:
            raise ValueError("No change credits remaining this billing cycle")

        slot = self.get_slot_for_writer(writer_id)
        if not slot:
            raise ValueError("Writer not allocated")

        previous_writer_id = slot.writer_id
        slot.writer_id = None
        slot.allocated_at = None
        self.change_credits -= 1
        self.updated_at = datetime.utcnow()

        self.add_event(
            AllocationChanged(
                aggregate_id=self.id,
                aggregate_type="Subscription",
                reader_id=self.reader_id,
                action=AllocationAction.RELEASE,
                writer_id=None,
                previous_writer_id=previous_writer_id,
                credits_spent=1,
                remaining_credits=self.change_credits,
                empty_slots_before=self.empty_slots - 1,
                empty_slots_after=self.empty_slots,
            )
        )
        return 1

    def renew_billing_cycle(self) -> None:
        """Renew billing cycle - reset credits and update cycle start."""
        settings = get_settings()
        new_cycle_start = datetime.utcnow()
        self.change_credits = settings.change_credits_per_billing_cycle
        self.billing_cycle_start = new_cycle_start
        self.updated_at = new_cycle_start

        self.add_event(
            BillingCycleRenewed(
                aggregate_id=self.id,
                aggregate_type="Subscription",
                reader_id=self.reader_id,
                new_cycle_start=new_cycle_start,
                credits_reset_to=self.change_credits,
            )
        )

    def update_status(self, new_status: SubscriptionStatus) -> None:
        """Update subscription status."""
        if self.status != new_status:
            old_status = self.status
            self.status = new_status
            self.updated_at = datetime.utcnow()
            self.add_event(
                SubscriptionStatusChanged(
                    aggregate_id=self.id,
                    aggregate_type="Subscription",
                    reader_id=self.reader_id,
                    old_status=old_status,
                    new_status=new_status,
                )
            )

    def get_allocation_summary(self) -> dict:
        """Get summary for API response."""
        # Handle both enum and string status (from DB)
        status_value = (
            self.status.value if hasattr(self.status, "value") else self.status
        )
        return {
            "subscription_id": str(self.id),
            "status": status_value,
            "billing_cycle_start": self.billing_cycle_start.isoformat(),
            "change_credits_remaining": self.change_credits,
            "change_credits_per_cycle": self.CREDITS_PER_CYCLE,
            "total_slots": self.MAX_SLOTS,
            "allocated_slots": len(self.allocated_slots),
            "empty_slots": self.empty_slots,
            "allocations": [
                {
                    "writer_id": str(slot.writer_id) if slot.writer_id else None,
                    "allocated_at": slot.allocated_at.isoformat()
                    if slot.allocated_at
                    else None,
                }
                for slot in self.slots
            ],
        }
