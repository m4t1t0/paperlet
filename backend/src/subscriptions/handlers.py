"""Subscriptions command handlers."""

from __future__ import annotations

from uuid import UUID

from backend.src.identity.domain.model import UserRole
from backend.src.identity.domain.repository import UserRepository
from backend.src.shared.config import get_settings
from backend.src.shared.service_layer.messagebus import CommandHandler
from backend.src.subscriptions.adapters.repository import SubscriptionRepository
from backend.src.subscriptions.commands import (
    AssignAllocationCommand,
    GetAllocationsCommand,
    HandlePaymentWebhookCommand,
    ReleaseAllocationCommand,
    SubscribeCommand,
    SwapAllocationCommand,
)
from backend.src.subscriptions.domain.model import AllocationChanged, Subscription
from backend.src.subscriptions.service import SubscriptionService


def _persist_allocation_log(subscription_repo, subscription: Subscription) -> None:
    """Write pending AllocationChanged events to allocation_log table.

    Direct persistence (in addition to event-bus projection) because command
    handlers mutate aggregates without publishing via the bus in v1.
    """
    from backend.src.subscriptions.adapters.read_model import AllocationLogProjection

    session = getattr(subscription_repo, "_session", None)
    if session is None:
        return
    projector = AllocationLogProjection(session)
    for event in subscription.events:
        if isinstance(event, AllocationChanged):
            projector.handle(event)


def _ensure_reader(user_repo: UserRepository, user_id: UUID) -> None:
    """Grant READER capability (roles are activity-inferred, never chosen)."""
    user = user_repo.get(user_id)
    if user is not None:
        user.add_role(UserRole.READER)


class SubscribeHandler(CommandHandler[SubscribeCommand, Subscription]):
    """Handler for creating subscriptions."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        subscription_service: SubscriptionService,
        user_repo: UserRepository,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._service = subscription_service
        self._user_repo = user_repo

    def handle(self, command: SubscribeCommand) -> Subscription:
        subscription = self._service.create_subscription(
            command.reader_id.value,
            command.payment_method_id,
        )
        _ensure_reader(self._user_repo, command.reader_id.value)
        return subscription


class GetAllocationsHandler(CommandHandler[GetAllocationsCommand, dict]):
    """Handler for getting allocations."""

    def __init__(self, subscription_repo: SubscriptionRepository) -> None:
        self._subscription_repo = subscription_repo

    def handle(self, command: GetAllocationsCommand) -> dict:
        subscription = self._subscription_repo.get_by_reader(command.reader_id.value)
        if not subscription:
            settings = get_settings()
            return {
                "subscription_id": None,
                "status": "none",
                "billing_cycle_start": None,
                "change_credits_remaining": settings.change_credits_per_billing_cycle,
                "change_credits_per_cycle": settings.change_credits_per_billing_cycle,
                "total_slots": settings.allocation_slots_per_subscription,
                "allocated_slots": 0,
                "empty_slots": settings.allocation_slots_per_subscription,
                "allocations": [],
            }
        return subscription.get_allocation_summary()


class AssignAllocationHandler(CommandHandler[AssignAllocationCommand, dict]):
    """Handler for assigning a writer to an empty slot."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        user_repo: UserRepository,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._user_repo = user_repo

    def handle(self, command: AssignAllocationCommand) -> dict:
        subscription = self._subscription_repo.get_by_reader(command.reader_id.value)
        if not subscription:
            raise ValueError("No active subscription found")

        credits_spent = subscription.allocate_writer(command.writer_id.value)
        _persist_allocation_log(self._subscription_repo, subscription)
        _ensure_reader(self._user_repo, command.reader_id.value)
        return {
            "success": True,
            "credits_spent": credits_spent,
            "allocations": subscription.get_allocation_summary()["allocations"],
        }


class SwapAllocationHandler(CommandHandler[SwapAllocationCommand, dict]):
    """Handler for swapping writers."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        user_repo: UserRepository,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._user_repo = user_repo

    def handle(self, command: SwapAllocationCommand) -> dict:
        subscription = self._subscription_repo.get_by_reader(command.reader_id.value)
        if not subscription:
            raise ValueError("No active subscription found")

        credits_spent = subscription.swap_writer(
            command.current_writer_id.value, command.new_writer_id.value
        )
        _persist_allocation_log(self._subscription_repo, subscription)
        _ensure_reader(self._user_repo, command.reader_id.value)
        return {
            "success": True,
            "credits_spent": credits_spent,
            "allocations": subscription.get_allocation_summary()["allocations"],
        }


class ReleaseAllocationHandler(CommandHandler[ReleaseAllocationCommand, dict]):
    """Handler for releasing a writer slot."""

    def __init__(self, subscription_repo: SubscriptionRepository) -> None:
        self._subscription_repo = subscription_repo

    def handle(self, command: ReleaseAllocationCommand) -> dict:
        subscription = self._subscription_repo.get_by_reader(command.reader_id.value)
        if not subscription:
            raise ValueError("No active subscription found")

        credits_spent = subscription.release_writer(command.writer_id.value)
        _persist_allocation_log(self._subscription_repo, subscription)
        return {
            "success": True,
            "credits_spent": credits_spent,
            "allocations": subscription.get_allocation_summary()["allocations"],
        }


class HandlePaymentWebhookHandler(CommandHandler[HandlePaymentWebhookCommand, None]):
    """Handler for payment webhooks."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        subscription_service: SubscriptionService,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._service = subscription_service

    def handle(self, command: HandlePaymentWebhookCommand) -> None:
        self._service.handle_webhook(command.event_type, command.payload)
