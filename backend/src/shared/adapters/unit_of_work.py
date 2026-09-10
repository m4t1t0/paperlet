"""SQLAlchemy Unit of Work implementation."""

from __future__ import annotations
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.src.shared.config import get_settings
from backend.src.shared.service_layer.unit_of_work import AbstractUnitOfWork
from backend.src.shared.domain.events import AggregateRoot, DomainEvent


class SqlAlchemyUnitOfWork(AbstractUnitOfWork, AbstractContextManager):
    """SQLAlchemy implementation of Unit of Work."""

    def __init__(self, session_factory: sessionmaker | None = None) -> None:
        super().__init__()
        self._session_factory = session_factory or self._create_session_factory()
        self._session: Session | None = None
        self._tracked_aggregates: list[AggregateRoot] = []

    def _create_session_factory(self) -> sessionmaker:
        settings = get_settings()
        is_sqlite = "sqlite" in settings.database_url
        engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if not is_sqlite:
            engine_kwargs["pool_size"] = settings.database_pool_size
            engine_kwargs["max_overflow"] = settings.database_max_overflow

        engine = create_engine(settings.database_url, **engine_kwargs)

        # Enable foreign keys for SQLite
        if is_sqlite:

            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        return sessionmaker(bind=engine, expire_on_commit=False)

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        return self

    def __exit__(self, *args: Any) -> None:
        self.rollback()
        if self._session:
            self._session.close()
            self._session = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError(
                "Unit of Work not started. Use 'with uow:' context manager."
            )
        return self._session

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work not started.")
        self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()

    def track_aggregate(self, aggregate: AggregateRoot) -> None:
        """Track an aggregate for event collection."""
        if aggregate not in self._tracked_aggregates:
            self._tracked_aggregates.append(aggregate)

    def collect_new_events(self) -> list[DomainEvent]:
        """Collect new domain events from all tracked aggregates."""
        events = []
        for aggregate in self._tracked_aggregates:
            events.extend(aggregate.clear_events())
        self._tracked_aggregates.clear()
        return events
