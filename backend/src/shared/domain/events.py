"""Base domain events and event handling."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4


T = TypeVar("T")


class DomainEvent:
    """Base class for all domain events."""

    def __init__(
        self,
        event_id: UUID | None = None,
        occurred_at: datetime | None = None,
        aggregate_id: UUID | None = None,
        aggregate_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.event_id = event_id or uuid4()
        self.occurred_at = occurred_at or datetime.utcnow()
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type
        # Store extra fields
        for key, value in kwargs.items():
            setattr(self, key, value)


class EventHandler(ABC, Generic[T]):
    """Abstract base for event handlers."""

    @abstractmethod
    def handle(self, event: T) -> None:
        """Handle the domain event."""
        ...


class EventBus:
    """In-memory event bus for domain events."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = {}

    def register(self, event_type: type[T], handler: EventHandler[T]) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all registered handlers."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            handler.handle(event)

    def publish_all(self, events: list[DomainEvent]) -> None:
        """Publish multiple events."""
        for event in events:
            self.publish(event)


class AggregateRoot:
    """Base class for aggregate roots that emit domain events."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    @property
    def events(self) -> list[DomainEvent]:
        """Get pending events."""
        return self._events

    def add_event(self, event: DomainEvent) -> None:
        """Add a domain event to be published."""
        # Set aggregate info on the event if not already set
        if event.aggregate_id is None and hasattr(self, "id"):
            event.aggregate_id = self.id
        if event.aggregate_type is None:
            event.aggregate_type = self.__class__.__name__
        self._events.append(event)

    def clear_events(self) -> list[DomainEvent]:
        """Clear and return pending events."""
        events = self._events
        self._events = []
        return events