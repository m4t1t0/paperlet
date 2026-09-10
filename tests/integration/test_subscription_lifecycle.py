"""Integration tests: subscription lifecycle + payment webhooks (service layer)."""
from __future__ import annotations

from uuid import uuid4

from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
from backend.src.identity.domain.model import User
from backend.src.identity.adapters.sqlalchemy_repository import (
    SqlAlchemyUserRepository,
)
from backend.src.subscriptions.domain.model import SubscriptionStatus
from backend.src.subscriptions.adapters.sqlalchemy_repository import (
    SqlAlchemySubscriptionRepository,
)
from backend.src.subscriptions.service import SubscriptionService
from backend.src.adapters.mock_payments import MockPaymentGateway


def _make_reader(email: str) -> object:
    with SqlAlchemyUnitOfWork() as uow:
        repo = SqlAlchemyUserRepository(uow.session)
        user = User.register(email, "hash-not-bcrypt")
        repo.add(user)
        uow.commit()
        return user.id


def _service_and_repo(uow):
    gateway = MockPaymentGateway()
    repo = SqlAlchemySubscriptionRepository(uow.session)
    return SubscriptionService(repo, gateway), repo, gateway


class TestSubscriptionLifecycle:
    def test_create_subscription_uses_string_price_id(self) -> None:
        reader_id = _make_reader(f"lc-{uuid4().hex[:8]}@test.com")
        with SqlAlchemyUnitOfWork() as uow:
            service, repo, gateway = _service_and_repo(uow)
            sub = service.create_subscription(reader_id, "pm_test")
            uow.commit()
            assert sub.status == SubscriptionStatus.ACTIVE
            stored = gateway.get_all_subscriptions()
            assert len(stored) == 1
            assert isinstance(next(iter(stored.values()))["price_id"], str)

    def test_duplicate_active_subscription_rejected(self) -> None:
        import pytest

        reader_id = _make_reader(f"dup-{uuid4().hex[:8]}@test.com")
        with SqlAlchemyUnitOfWork() as uow:
            service, _, _ = _service_and_repo(uow)
            service.create_subscription(reader_id, "pm_test")
            uow.commit()
            with pytest.raises(ValueError, match="already has an active subscription"):
                service.create_subscription(reader_id, "pm_test")

    def test_webhook_transitions(self) -> None:
        reader_id = _make_reader(f"wh-{uuid4().hex[:8]}@test.com")
        with SqlAlchemyUnitOfWork() as uow:
            service, repo, _ = _service_and_repo(uow)
            sub = service.create_subscription(reader_id, "pm_test")
            uow.commit()
            ext_id = sub.external_subscription_id
            assert repo.get_by_reader(reader_id).change_credits == 2

            # Stripe-canonical + legacy aliases
            service.handle_webhook(
                "invoice.payment_failed", {"subscription_id": ext_id}
            )
            assert repo.get_by_external_id(ext_id).status == SubscriptionStatus.PAST_DUE

            service.handle_webhook(
                "invoice.payment_succeeded", {"subscription_id": ext_id}
            )
            renewed = repo.get_by_external_id(ext_id)
            assert renewed.status == SubscriptionStatus.ACTIVE
            assert renewed.change_credits == 2

            service.handle_webhook(
                "customer.subscription.updated",
                {"subscription_id": ext_id, "status": "past_due"},
            )
            assert repo.get_by_external_id(ext_id).status == SubscriptionStatus.PAST_DUE

            service.handle_webhook("subscription.updated", {"subscription_id": ext_id, "status": "active"})
            assert repo.get_by_external_id(ext_id).status == SubscriptionStatus.ACTIVE

            service.handle_webhook(
                "customer.subscription.created",
                {"subscription_id": ext_id, "status": "active"},
            )
            assert repo.get_by_external_id(ext_id).status == SubscriptionStatus.ACTIVE

            service.handle_webhook(
                "customer.subscription.deleted", {"subscription_id": ext_id}
            )
            assert repo.get_by_external_id(ext_id).status == SubscriptionStatus.CANCELED

    def test_renew_billing_cycle_resets_credits(self) -> None:
        reader_id = _make_reader(f"rn-{uuid4().hex[:8]}@test.com")
        with SqlAlchemyUnitOfWork() as uow:
            service, repo, _ = _service_and_repo(uow)
            sub = service.create_subscription(reader_id, "pm_test")
            sub.change_credits = 0
            uow.commit()

            renewed = service.renew_billing_cycle(reader_id)
            assert renewed.change_credits == 2
