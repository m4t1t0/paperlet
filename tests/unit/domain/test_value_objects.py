"""Unit tests for Money value object (pure, no DB)."""
from __future__ import annotations

import pytest

from backend.src.shared.domain.value_objects import Money


class TestMoney:
    def test_from_eur_rounds_to_cents(self) -> None:
        assert Money.from_eur(9.95).cents == 995
        assert Money.from_eur(9.955).cents == 996

    def test_eur_display(self) -> None:
        assert Money.from_eur(9.95).eur == pytest.approx(9.95)
        assert str(Money.from_eur(9.95)) == "9.95 EUR"

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            Money(cents=-1)
        with pytest.raises(ValueError, match="negative"):
            Money.from_eur(-9.95)

    def test_rejects_bad_currency(self) -> None:
        with pytest.raises(ValueError, match="3-letter"):
            Money(cents=100, currency="EURO")

    def test_settings_price_is_money(self) -> None:
        from backend.src.shared.config import get_settings

        price = get_settings().subscription_price
        assert isinstance(price, Money)
        assert price.cents == 995
