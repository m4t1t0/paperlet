"""Pytest configuration and fixtures."""
from __future__ import annotations
import os
import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


# Set test environment BEFORE any other fixtures
os.environ["APP_ENV"] = "test"
# Prefer explicit TEST_DATABASE_URL, then .env.test, then default paperlet_test.
# (No SQLite fallback — tests run against Postgres per project preference.)
def _resolve_test_db_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    env_test = Path(__file__).parent.parent / ".env.test"
    if env_test.exists():
        for line in env_test.read_text().splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return "postgresql://rafa@localhost:5432/paperlet_test"


os.environ["DATABASE_URL"] = _resolve_test_db_url()
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["JWT_REFRESH_TOKEN_EXPIRE_DAYS"] = "30"
os.environ["SUBSCRIPTION_MONTHLY_PRICE_EUR"] = "9.95"
os.environ["ALLOCATION_SLOTS_PER_SUBSCRIPTION"] = "5"
os.environ["CHANGE_CREDITS_PER_BILLING_CYCLE"] = "2"
os.environ["EMAIL_BATCH_SIZE"] = "100"
os.environ["PAYMENT_GATEWAY"] = "mock"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/2"


# Shared test database: Postgres paperlet_test (see .env.test).
# Tables are created once per session; rows are truncated between tests.
def _get_test_db_url() -> str:
    return os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
def _start_mappers_and_create_tables() -> None:
    """Start SQLAlchemy mappers and create tables once per session."""
    from backend.src.identity.adapters.orm import start_mappers as start_identity_mappers, create_tables as create_identity_tables
    from backend.src.subscriptions.adapters.orm import start_mappers as start_sub_mappers, create_tables as create_sub_tables
    from backend.src.publishing.adapters.orm import start_mappers as start_pub_mappers, create_tables as create_pub_tables
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
    from backend.src.shared.config import get_settings
    
    get_settings.cache_clear()
    
    start_identity_mappers()
    start_sub_mappers()
    start_pub_mappers()
    
    # Create all tables in the shared test database
    with SqlAlchemyUnitOfWork() as uow:
        create_identity_tables(uow.session.bind)
        create_sub_tables(uow.session.bind)
        create_pub_tables(uow.session.bind)
        uow.commit()


@pytest.fixture(autouse=True)
def _clear_data(request):
    """Clear all data between tests (Postgres TRUNCATE CASCADE)."""
    # Pure domain tests (tests/unit/domain) never touch the DB — skip fast.
    if "integration" in request.keywords or "e2e" in request.keywords or "unit" in request.keywords:
        from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
        from sqlalchemy import text
        with SqlAlchemyUnitOfWork() as uow:
            # TRUNCATE handles FK order via CASCADE; keep alembic_version intact.
            uow.session.execute(text(
                "TRUNCATE TABLE allocation_log, writer_subscribers, "
                "writer_followers, allocation_slots, subscriptions, "
                "posts, sessions, users CASCADE"
            ))
            uow.commit()


@pytest.fixture
def app():
    """Create Flask app for testing."""
    from backend.src.shared.config import get_settings
    get_settings.cache_clear()

    from app import create_app
    app = create_app({
        "TESTING": True,
        "DATABASE_URL": _get_test_db_url(),
    })
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def uow():
    """Create Unit of Work for testing."""
    from backend.src.shared.config import get_settings
    get_settings.cache_clear()
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
    with SqlAlchemyUnitOfWork() as uow:
        yield uow