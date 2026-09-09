"""Unit tests for Subscription domain model."""
from __future__ import annotations
from datetime import datetime
from uuid import uuid4

import pytest

from backend.src.subscriptions.domain.model import (
    Subscription,
    SubscriptionStatus,
    AllocationAction,
    AllocationSlot,
)


class TestSubscription:
    """Tests for Subscription aggregate."""

    def setup_method(self) -> None:
        self.reader_id = uuid4()
        self.writer_id = uuid4()
        self.writer_id_2 = uuid4()
        self.writer_id_3 = uuid4()

    def test_create_subscription(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        assert sub.reader_id == self.reader_id
        assert sub.external_subscription_id == "sub_ext_123"
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.change_credits == 2
        assert sub.empty_slots == 5
        assert len(sub.events) == 1
        assert sub.events[0].__class__.__name__ == "SubscriptionCreated"

    def test_allocate_writer_to_empty_slot(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.clear_events()

        credits_spent = sub.allocate_writer(self.writer_id)
        assert credits_spent == 0
        assert sub.empty_slots == 4
        assert sub.is_writer_allocated(self.writer_id)
        assert len(sub.allocated_slots) == 1

        event = sub.events[0]
        assert event.action == AllocationAction.ALLOCATE
        assert event.credits_spent == 0
        assert event.remaining_credits == 2

    def test_allocate_writer_fails_when_no_empty_slots(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        # Fill all 5 slots
        for i in range(5):
            sub.allocate_writer(uuid4())
        sub.clear_events()

        with pytest.raises(ValueError, match="No empty slots"):
            sub.allocate_writer(uuid4())

    def test_allocate_writer_fails_when_already_allocated(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.allocate_writer(self.writer_id)
        sub.clear_events()

        with pytest.raises(ValueError, match="already allocated"):
            sub.allocate_writer(self.writer_id)

    def test_swap_writer_consumes_credit(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.allocate_writer(self.writer_id)
        sub.clear_events()

        credits_spent = sub.swap_writer(self.writer_id, self.writer_id_2)
        assert credits_spent == 1
        assert sub.change_credits == 1
        assert not sub.is_writer_allocated(self.writer_id)
        assert sub.is_writer_allocated(self.writer_id_2)

        event = sub.events[0]
        assert event.action == AllocationAction.SWAP
        assert event.credits_spent == 1
        assert event.remaining_credits == 1

    def test_swap_writer_fails_when_no_credits(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.allocate_writer(self.writer_id)
        sub.change_credits = 0  # Exhaust credits
        sub.clear_events()

        with pytest.raises(ValueError, match="No change credits"):
            sub.swap_writer(self.writer_id, self.writer_id_2)

    def test_swap_writer_fails_when_new_writer_already_allocated(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.allocate_writer(self.writer_id)
        sub.allocate_writer(self.writer_id_2)
        sub.clear_events()

        with pytest.raises(ValueError, match="already allocated"):
            sub.swap_writer(self.writer_id, self.writer_id_2)

    def test_release_writer_consumes_credit(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.allocate_writer(self.writer_id)
        sub.clear_events()

        credits_spent = sub.release_writer(self.writer_id)
        assert credits_spent == 1
        assert sub.change_credits == 1
        assert sub.empty_slots == 5
        assert not sub.is_writer_allocated(self.writer_id)

        event = sub.events[0]
        assert event.action == AllocationAction.RELEASE
        assert event.credits_spent == 1
        assert event.remaining_credits == 1

    def test_release_writer_fails_when_no_credits(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.allocate_writer(self.writer_id)
        sub.change_credits = 0
        sub.clear_events()

        with pytest.raises(ValueError, match="No change credits"):
            sub.release_writer(self.writer_id)

    def test_operations_fail_when_subscription_not_active(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.CANCELED)

        with pytest.raises(ValueError, match="not active"):
            sub.allocate_writer(self.writer_id)

        # Manually add an allocation for swap/release tests
        sub.slots[0].writer_id = self.writer_id
        sub.slots[0].allocated_at = datetime.utcnow()

        with pytest.raises(ValueError, match="not active"):
            sub.swap_writer(self.writer_id, self.writer_id_2)

        with pytest.raises(ValueError, match="not active"):
            sub.release_writer(self.writer_id)

    def test_renew_billing_cycle_resets_credits(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.change_credits = 0
        old_cycle_start = sub.billing_cycle_start
        sub.clear_events()

        sub.renew_billing_cycle()
        assert sub.change_credits == 2
        assert sub.billing_cycle_start > old_cycle_start

        event = sub.events[0]
        assert event.__class__.__name__ == "BillingCycleRenewed"
        assert event.credits_reset_to == 2

    def test_get_allocation_summary(self) -> None:
        sub = Subscription.create(self.reader_id, "sub_ext_123", SubscriptionStatus.ACTIVE)
        sub.allocate_writer(self.writer_id)
        sub.allocate_writer(self.writer_id_2)

        summary = sub.get_allocation_summary()
        assert summary["subscription_id"] == str(sub.id)
        assert summary["status"] == "active"
        assert summary["change_credits_remaining"] == 2
        assert summary["total_slots"] == 5
        assert summary["allocated_slots"] == 2
        assert summary["empty_slots"] == 3
        assert len(summary["allocations"]) == 5
        allocated = [a for a in summary["allocations"] if a["writer_id"]]
        assert len(allocated) == 2


class TestAllocationSlot:
    """Tests for AllocationSlot."""

    def test_is_empty(self) -> None:
        slot = AllocationSlot()
        assert slot.is_empty

        slot.writer_id = uuid4()
        assert not slot.is_empty