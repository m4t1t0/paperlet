"""Adapters exports."""

from backend.src.adapters.mock_payments import MockPaymentGateway
from backend.src.adapters.payments import (
    PaymentGatewayAdapter,
    SubscriptionResult,
    SubscriptionStatusResult,
)
from backend.src.shared.config import get_settings


def create_payment_gateway() -> PaymentGatewayAdapter:
    """Create payment gateway based on configuration."""
    settings = get_settings()
    if settings.payment_gateway == "stripe":
        # TODO: Implement StripePaymentGateway
        from backend.src.adapters.stripe_payments import StripePaymentGateway
        return StripePaymentGateway(
            secret_key=settings.stripe_secret_key,
            webhook_secret=settings.stripe_webhook_secret,
        )
    # Default to mock for development
    return MockPaymentGateway()


__all__ = [
    "PaymentGatewayAdapter",
    "MockPaymentGateway",
    "SubscriptionResult",
    "SubscriptionStatusResult",
    "create_payment_gateway",
]
