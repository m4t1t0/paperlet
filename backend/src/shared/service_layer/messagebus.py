"""Message bus for commands and events."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from backend.src.shared.domain.events import DomainEvent, EventBus

T = TypeVar("T")
R = TypeVar("R")


class Command(ABC):
    """Base class for commands."""
    pass


class CommandHandler(ABC, Generic[T, R]):
    """Abstract base for command handlers."""

    @abstractmethod
    def handle(self, command: T) -> R:
        """Handle the command."""
        ...


class MessageBus:
    """Message bus handling both commands and events."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._command_handlers: dict[type[Command], Callable] = {}
        self._event_bus = event_bus or EventBus()

    def register_command(self, command_type: type[T], handler: Callable[[T], R]) -> None:
        """Register a command handler."""
        self._command_handlers[command_type] = handler

    def register_event_handler(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        """Register an event handler."""
        self._event_bus.register(event_type, handler)

    def handle(self, command: Command) -> Any:
        """Handle a command."""
        handler = self._command_handlers.get(type(command))
        if not handler:
            raise ValueError(f"No handler for command {type(command).__name__}")
        return handler(command)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event."""
        self._event_bus.publish(event)

    def publish_all(self, events: list[DomainEvent]) -> None:
        """Publish multiple events."""
        self._event_bus.publish_all(events)