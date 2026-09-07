"""Subscriptions commands."""
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from backend.src.shared.service_layer.messagebus import Command
from backend.src.subscriptions.domain.model import AllocationAction


@dataclass(frozen=True)
class SubscribeCommand(Command):
    """Command to create a subscription."""
    reader_id: UUID
    payment_method_id: str  # Mock payment method token


@dataclass(frozen=True)
class GetAllocationsCommand(Command):
    """Command to get current allocations."""
    reader_id: UUID


@dataclass(frozen=True)
class AssignAllocationCommand(Command):
    """Command to assign a writer to an empty slot."""
    reader_id: UUID
    writer_id: UUID


@dataclass(frozen=True)
class SwapAllocationCommand(Command):
    """Command to swap one writer for another."""
    reader_id: UUID
    current_writer_id: UUID
    new_writer_id: UUID


@dataclass(frozen=True)
class ReleaseAllocationCommand(Command):
    """Command to release a writer slot."""
    reader_id: UUID
    writer_id: UUID


@dataclass(frozen=True)
class HandlePaymentWebhookCommand(Command):
    """Command to handle payment gateway webhook."""
    event_type: str
    payload: dict