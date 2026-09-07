"""Payment gateway adapter abstraction."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SubscriptionResult:
    """Result of subscription creation."""
    subscription_id: str
    status: str
    client_secret: Optional[str] = None


@dataclass
class SubscriptionStatusResult:
    """Result of subscription status check."""
    subscription_id: str
    status: str
    current_period_end: Optional[int] = None
    cancel_at_period_end: bool = False


class PaymentGatewayAdapter(ABC):
    """Abstract interface for payment gateways."""

    @abstractmethod
    def create_subscription(
        self,
        customer_id: str,
        price_id: float,  # Price in EUR
        payment_method_id: str,
    ) -> SubscriptionResult:
        """Create a new subscription."""
        ...

    @abstractmethod
    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription."""
        ...

    @abstractmethod
    def get_subscription_status(self, subscription_id: str) -> SubscriptionStatusResult:
        """Get subscription status."""
        ...

    @abstractmethod
    def handle_webhook(self, event_type: str, payload: dict) -> None:
        """Handle incoming webhook."""
        ...