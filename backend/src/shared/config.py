"""Application configuration without pydantic dependency."""

from __future__ import annotations
from dataclasses import dataclass, field
from functools import lru_cache
import os
from typing import Optional, TYPE_CHECKING

try:
    from dotenv import load_dotenv

    # Load .env so DATABASE_URL etc. work without manual export.
    # conftest.py / shell env vars still take precedence (override=False by default
    # means existing env wins, file only fills gaps).
    load_dotenv()
except ImportError:
    pass

if TYPE_CHECKING:
    from backend.src.shared.domain.value_objects import Money


def _get_env(key: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.environ.get(key, default)


def _get_env_int(key: str, default: int) -> int:
    """Get environment variable as int with default."""
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


def _get_env_float(key: str, default: float) -> float:
    """Get environment variable as float with default."""
    try:
        return float(os.environ.get(key, str(default)))
    except ValueError:
        return default


@dataclass
class Settings:
    """Application settings."""

    # App
    app_env: str = field(default_factory=lambda: _get_env("APP_ENV", "development"))
    log_level: str = field(default_factory=lambda: _get_env("LOG_LEVEL", "INFO"))
    secret_key: str = field(
        default_factory=lambda: _get_env(
            "SECRET_KEY", "dev-secret-change-in-production"
        )
    )
    api_prefix: str = field(default_factory=lambda: _get_env("API_PREFIX", "/api/v1"))

    # Database
    database_url: str = field(
        default_factory=lambda: _get_env(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/paperlet"
        )
    )
    database_pool_size: int = field(
        default_factory=lambda: _get_env_int("DATABASE_POOL_SIZE", 10)
    )
    database_max_overflow: int = field(
        default_factory=lambda: _get_env_int("DATABASE_MAX_OVERFLOW", 20)
    )

    # Redis
    redis_url: str = field(
        default_factory=lambda: _get_env("REDIS_URL", "redis://localhost:6379/0")
    )

    # JWT
    jwt_algorithm: str = field(
        default_factory=lambda: _get_env("JWT_ALGORITHM", "HS256")
    )
    jwt_access_token_expire_minutes: int = field(
        default_factory=lambda: _get_env_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 15)
    )
    jwt_refresh_token_expire_days: int = field(
        default_factory=lambda: _get_env_int("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 30)
    )

    # Subscription Economics (config-driven)
    subscription_monthly_price_eur: float = field(
        default_factory=lambda: _get_env_float("SUBSCRIPTION_MONTHLY_PRICE_EUR", 9.95)
    )

    @property
    def subscription_price(self) -> "Money":
        """Monthly price as a Money value object (validates config)."""
        from backend.src.shared.domain.value_objects import Money

        return Money.from_eur(self.subscription_monthly_price_eur)
    allocation_slots_per_subscription: int = field(
        default_factory=lambda: _get_env_int("ALLOCATION_SLOTS_PER_SUBSCRIPTION", 5)
    )
    change_credits_per_billing_cycle: int = field(
        default_factory=lambda: _get_env_int("CHANGE_CREDITS_PER_BILLING_CYCLE", 2)
    )

    # Email
    email_batch_size: int = field(
        default_factory=lambda: _get_env_int("EMAIL_BATCH_SIZE", 100)
    )
    email_sender_address: str = field(
        default_factory=lambda: _get_env(
            "EMAIL_SENDER_ADDRESS", "noreply@paperlet.local"
        )
    )

    # Payment Gateway
    payment_gateway: str = field(
        default_factory=lambda: _get_env("PAYMENT_GATEWAY", "mock")
    )
    subscription_price_id: str = field(
        default_factory=lambda: _get_env(
            "SUBSCRIPTION_PRICE_ID", "price_monthly_eur_995"
        )
    )
    stripe_secret_key: Optional[str] = field(
        default_factory=lambda: _get_env("STRIPE_SECRET_KEY") or None
    )
    stripe_webhook_secret: Optional[str] = field(
        default_factory=lambda: _get_env("STRIPE_WEBHOOK_SECRET") or None
    )

    # Celery
    celery_broker_url: str = field(
        default_factory=lambda: _get_env(
            "CELERY_BROKER_URL", "redis://localhost:6379/1"
        )
    )
    celery_result_backend: str = field(
        default_factory=lambda: _get_env(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
        )
    )

    # Rate Limiting
    rate_limit_per_minute: int = field(
        default_factory=lambda: _get_env_int("RATE_LIMIT_PER_MINUTE", 60)
    )
    rate_limit_per_hour: int = field(
        default_factory=lambda: _get_env_int("RATE_LIMIT_PER_HOUR", 1000)
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
