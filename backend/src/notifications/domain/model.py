"""Notifications domain model."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class EmailRecipient:
    """Email recipient with allocation status."""
    user_id: UUID
    email: str
    has_allocation: bool
    writer_id: UUID


@dataclass
class SendResult:
    """Result of email send attempt."""
    recipient_id: UUID
    success: bool
    error: Optional[str] = None
    message_id: Optional[str] = None


@dataclass
class EmailBatch:
    """Batch of emails to send."""
    batch_id: UUID
    post_id: UUID
    recipients: list[EmailRecipient]
    created_at: datetime = datetime.utcnow()