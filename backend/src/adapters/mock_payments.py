"""Mock payment gateway for development and testing."""

from __future__ import annotations
import uuid

from backend.src.adapters.payments import (
    PaymentGatewayAdapter,
    SubscriptionResult,
    SubscriptionStatusResult,
)


class MockPaymentGateway(PaymentGatewayAdapter):
    """Mock payment gateway that simulates Stripe-like behavior."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, dict] = {}
        self._webhook_handlers: list[callable] = []

    def create_subscription(
        self,
        customer_id: str,
        price_id: float,
        payment_method_id: str,
    ) -> SubscriptionResult:
        """Create a mock subscription."""
        subscription_id = f"sub_mock_{uuid.uuid4().hex[:16]}"
        self._subscriptions[subscription_id] = {
            "id": subscription_id,
            "customer_id": customer_id,
            "price_id": price_id,
            "payment_method_id": payment_method_id,
            "status": "active",
            "current_period_end": None,
            "cancel_at_period_end": False,
        }
        return SubscriptionResult(
            subscription_id=subscription_id,
            status="active",
            client_secret=f"pi_mock_{uuid.uuid4().hex[:16]}_secret",
        )

    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a mock subscription."""
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id]["status"] = "canceled"
            self._subscriptions[subscription_id]["cancel_at_period_end"] = True
            self._emit_webhook(
                "subscription.canceled", {"subscription_id": subscription_id}
            )
            return True
        return False

    def get_subscription_status(self, subscription_id: str) -> SubscriptionStatusResult:
        """Get mock subscription status."""
        sub = self._subscriptions.get(subscription_id)
        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found")
        return SubscriptionStatusResult(
            subscription_id=sub["id"],
            status=sub["status"],
            current_period_end=sub["current_period_end"],
            cancel_at_period_end=sub["cancel_at_period_end"],
        )

    def handle_webhook(self, event_type: str, payload: dict) -> None:
        """Handle mock webhook (for testing)."""
        self._emit_webhook(event_type, payload)

    def _emit_webhook(self, event_type: str, payload: dict) -> None:
        """Emit webhook to registered handlers."""
        for handler in self._webhook_handlers:
            try:
                handler(event_type, payload)
            except Exception:
                pass  # Ignore handler errors in mock

    def register_webhook_handler(self, handler: callable) -> None:
        """Register a webhook handler."""
        self._webhook_handlers.append(handler)

    # Test helper methods
    def simulate_payment_failed(self, subscription_id: str) -> None:
        """Simulate a failed payment."""
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id]["status"] = "past_due"
            self._emit_webhook(
                "invoice.payment_failed", {"subscription_id": subscription_id}
            )

    def simulate_payment_succeeded(self, subscription_id: str) -> None:
        """Simulate a successful payment renewal."""
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id]["status"] = "active"
            self._emit_webhook(
                "invoice.payment_succeeded", {"subscription_id": subscription_id}
            )

    def simulate_subscription_updated(self, subscription_id: str, status: str) -> None:
        """Simulate subscription status update."""
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id]["status"] = status
            self._emit_webhook(
                "subscription.updated",
                {"subscription_id": subscription_id, "status": status},
            )

    def get_all_subscriptions(self) -> dict:
        """Get all subscriptions (for testing)."""
        return self._subscriptions.copy()

    def reset(self) -> None:
        """Reset gateway state (for testing)."""
        self._subscriptions.clear()
        self._webhook_handlers.clear()
