"""Pytest configuration and fixtures."""
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


# Set test environment BEFORE any other fixtures
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
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


# Shared test database (file-based SQLite for persistence across connections)
_test_db_fd = None
_test_db_path = None


def _get_test_db_url() -> str:
    global _test_db_fd, _test_db_path
    if _test_db_path is None:
        _test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
        os.close(_test_db_fd)
    return f"sqlite:///{_test_db_path}"


# Override the default DATABASE_URL for tests
os.environ["DATABASE_URL"] = _get_test_db_url()


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
    """Clear all data between tests (only for integration/e2e tests)."""
    # Only run for integration and e2e tests
    if "integration" in request.keywords or "e2e" in request.keywords:
        from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
        from sqlalchemy import text
        with SqlAlchemyUnitOfWork() as uow:
            # Delete data from all tables in reverse order of dependencies
            uow.session.execute(text("DELETE FROM allocation_log"))
            uow.session.execute(text("DELETE FROM allocation_slots"))
            uow.session.execute(text("DELETE FROM subscriptions"))
            uow.session.execute(text("DELETE FROM posts"))
            uow.session.execute(text("DELETE FROM users"))
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