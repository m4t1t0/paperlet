"""Subscriptions service layer."""

from __future__ import annotations
from typing import Optional
from uuid import UUID

from backend.src.shared.config import get_settings
from backend.src.subscriptions.adapters.repository import SubscriptionRepository
from backend.src.subscriptions.domain.model import Subscription, SubscriptionStatus
from backend.src.adapters import PaymentGatewayAdapter, MockPaymentGateway


class SubscriptionService:
    """Subscription service orchestrating subscription lifecycle."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        payment_gateway: PaymentGatewayAdapter | None = None,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._payment_gateway = payment_gateway or MockPaymentGateway()
        self._settings = get_settings()

    def create_subscription(
        self, reader_id: UUID, payment_method_id: str
    ) -> Subscription:
        """Create a new subscription via payment gateway."""
        # Check if already has active subscription
        existing = self._subscription_repo.get_by_reader(reader_id)
        if existing and existing.status == SubscriptionStatus.ACTIVE:
            raise ValueError("Reader already has an active subscription")

        # Validate configured price as Money (rejects negative/NaN config).
        # The gateway itself is keyed by opaque price_id (Stripe-ready).
        _price = self._settings.subscription_price

        # Create subscription via payment gateway
        result = self._payment_gateway.create_subscription(
            customer_id=str(reader_id),
            price_id=self._settings.subscription_price_id,
            payment_method_id=payment_method_id,
        )

        # Create local subscription record
        subscription = Subscription.create(
            reader_id=reader_id,
            external_subscription_id=result.subscription_id,
            status=SubscriptionStatus(result.status),
        )
        self._subscription_repo.add(subscription)
        return subscription

    # Stripe-canonical names with legacy mock aliases.
    _WEBHOOK_ROUTES = {
        "customer.subscription.created": "_handle_subscription_created",
        "subscription.created": "_handle_subscription_created",
        "customer.subscription.updated": "_handle_subscription_updated",
        "subscription.updated": "_handle_subscription_updated",
        "customer.subscription.deleted": "_handle_subscription_canceled",
        "subscription.canceled": "_handle_subscription_canceled",
        "invoice.payment_failed": "_handle_payment_failed",
        "invoice.payment_succeeded": "_handle_payment_succeeded",
    }

    def handle_webhook(self, event_type: str, payload: dict) -> None:
        """Handle payment gateway webhook (Stripe + legacy mock names)."""
        handler_name = self._WEBHOOK_ROUTES.get(event_type)
        if handler_name is None:
            return
        getattr(self, handler_name)(payload)

    def _handle_subscription_created(self, payload: dict) -> None:
        """Handle subscription created webhook (Stripe customer.subscription.created)."""
        external_id = payload.get("subscription_id") or payload.get("id")
        status = payload.get("status", "active")
        if not external_id:
            return
        subscription = self._subscription_repo.get_by_external_id(external_id)
        if subscription:
            try:
                subscription.update_status(SubscriptionStatus(status))
            except ValueError:
                subscription.update_status(SubscriptionStatus.ACTIVE)

    def _handle_subscription_updated(self, payload: dict) -> None:
        """Handle subscription updated webhook."""
        external_id = payload.get("subscription_id")
        status = payload.get("status")
        subscription = self._subscription_repo.get_by_external_id(external_id)
        if subscription:
            subscription.update_status(SubscriptionStatus(status))

    def _handle_subscription_canceled(self, payload: dict) -> None:
        """Handle subscription canceled webhook."""
        external_id = payload.get("subscription_id")
        subscription = self._subscription_repo.get_by_external_id(external_id)
        if subscription:
            subscription.update_status(SubscriptionStatus.CANCELED)

    def _handle_payment_failed(self, payload: dict) -> None:
        """Handle payment failed webhook."""
        external_id = payload.get("subscription_id")
        subscription = self._subscription_repo.get_by_external_id(external_id)
        if subscription:
            subscription.update_status(SubscriptionStatus.PAST_DUE)

    def _handle_payment_succeeded(self, payload: dict) -> None:
        """Handle payment succeeded webhook - renew billing cycle."""
        external_id = payload.get("subscription_id")
        subscription = self._subscription_repo.get_by_external_id(external_id)
        if subscription and subscription.status in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
        ):
            subscription.update_status(SubscriptionStatus.ACTIVE)
            subscription.renew_billing_cycle()

    def renew_billing_cycle(self, reader_id: UUID) -> Optional[Subscription]:
        """Manually renew billing cycle (for testing/cron)."""
        subscription = self._subscription_repo.get_by_reader(reader_id)
        if subscription:
            subscription.renew_billing_cycle()
        return subscription
