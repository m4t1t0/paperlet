"""Subscriptions commands."""

from __future__ import annotations
from dataclasses import dataclass

from backend.src.shared.domain.value_objects import ReaderId, WriterId
from backend.src.shared.service_layer.messagebus import Command


@dataclass(frozen=True)
class SubscribeCommand(Command):
    """Command to create a subscription."""

    reader_id: ReaderId
    payment_method_id: str  # Mock payment method token


@dataclass(frozen=True)
class GetAllocationsCommand(Command):
    """Command to get current allocations."""

    reader_id: ReaderId


@dataclass(frozen=True)
class AssignAllocationCommand(Command):
    """Command to assign a writer to an empty slot."""

    reader_id: ReaderId
    writer_id: WriterId


@dataclass(frozen=True)
class SwapAllocationCommand(Command):
    """Command to swap one writer for another."""

    reader_id: ReaderId
    current_writer_id: WriterId
    new_writer_id: WriterId


@dataclass(frozen=True)
class ReleaseAllocationCommand(Command):
    """Command to release a writer slot."""

    reader_id: ReaderId
    writer_id: WriterId


@dataclass(frozen=True)
class HandlePaymentWebhookCommand(Command):
    """Command to handle payment gateway webhook."""

    event_type: str
    payload: dict
