"""Unit tests for MockPaymentGateway."""
from __future__ import annotations
import pytest

from backend.src.adapters.mock_payments import MockPaymentGateway
from backend.src.adapters.payments import SubscriptionResult


class TestMockPaymentGateway:
    """Tests for MockPaymentGateway."""

    def setup_method(self) -> None:
        self.gateway = MockPaymentGateway()

    def test_create_subscription(self) -> None:
        result = self.gateway.create_subscription(
            customer_id="user_123",
            price_id="price_monthly_eur_995",
            payment_method_id="pm_test",
        )
        assert isinstance(result, SubscriptionResult)
        assert result.subscription_id.startswith("sub_mock_")
        assert result.status == "active"
        assert result.client_secret is not None

    def test_get_subscription_status(self) -> None:
        create_result = self.gateway.create_subscription("user_123", "price_monthly_eur_995", "pm_test")
        status = self.gateway.get_subscription_status(create_result.subscription_id)
        assert status.subscription_id == create_result.subscription_id
        assert status.status == "active"

    def test_get_subscription_status_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            self.gateway.get_subscription_status("sub_nonexistent")

    def test_cancel_subscription(self) -> None:
        create_result = self.gateway.create_subscription("user_123", "price_monthly_eur_995", "pm_test")
        result = self.gateway.cancel_subscription(create_result.subscription_id)
        assert result is True

        status = self.gateway.get_subscription_status(create_result.subscription_id)
        assert status.status == "canceled"

    def test_cancel_nonexistent_subscription(self) -> None:
        result = self.gateway.cancel_subscription("sub_nonexistent")
        assert result is False

    def test_simulate_payment_failed(self) -> None:
        create_result = self.gateway.create_subscription("user_123", "price_monthly_eur_995", "pm_test")
        self.gateway.simulate_payment_failed(create_result.subscription_id)

        status = self.gateway.get_subscription_status(create_result.subscription_id)
        assert status.status == "past_due"

    def test_simulate_payment_succeeded(self) -> None:
        create_result = self.gateway.create_subscription("user_123", "price_monthly_eur_995", "pm_test")
        self.gateway.simulate_payment_failed(create_result.subscription_id)
        self.gateway.simulate_payment_succeeded(create_result.subscription_id)

        status = self.gateway.get_subscription_status(create_result.subscription_id)
        assert status.status == "active"

    def test_simulate_subscription_updated(self) -> None:
        create_result = self.gateway.create_subscription("user_123", "price_monthly_eur_995", "pm_test")
        self.gateway.simulate_subscription_updated(create_result.subscription_id, "past_due")

        status = self.gateway.get_subscription_status(create_result.subscription_id)
        assert status.status == "past_due"

    def test_webhook_handler_registration(self) -> None:
        calls = []

        def handler(event_type: str, payload: dict) -> None:
            calls.append((event_type, payload))

        self.gateway.register_webhook_handler(handler)
        create_result = self.gateway.create_subscription("user_123", "price_monthly_eur_995", "pm_test")

        # Trigger webhook via cancel
        self.gateway.cancel_subscription(create_result.subscription_id)

        assert len(calls) == 1
        assert calls[0][0] == "customer.subscription.deleted"
        assert calls[0][1]["subscription_id"] == create_result.subscription_id

    def test_reset(self) -> None:
        self.gateway.create_subscription("user_123", "price_monthly_eur_995", "pm_test")
        self.gateway.reset()

        with pytest.raises(ValueError):
            self.gateway.get_subscription_status("sub_mock_")  # Any ID should fail