"""Stub email sender for v1 (logs only)."""

from __future__ import annotations
import logging

from backend.src.notifications.adapters.email import (
    EmailRecipient,
    SendResult,
)

logger = logging.getLogger(__name__)


class StubEmailSender:
    """Stub email sender that logs emails instead of sending."""

    def __init__(self) -> None:
        self.sent_emails: list[dict] = []

    def send_batch(
        self,
        recipients: list[EmailRecipient],
        template: str,
        context: dict,
    ) -> list[SendResult]:
        """Log emails instead of sending."""
        results = []
        for recipient in recipients:
            # Log the email
            email_data = {
                "recipient_id": str(recipient.user_id),
                "recipient_email": recipient.email,
                "template": template,
                "context": context,
                "has_allocation": recipient.has_allocation,
            }
            self.sent_emails.append(email_data)
            logger.info(f"STUB EMAIL SENT: {email_data}")

            results.append(
                SendResult(
                    recipient_id=recipient.user_id,
                    success=True,
                    message_id=f"stub-{len(self.sent_emails)}",
                )
            )
        return results


class LoggingEmailSender(StubEmailSender):
    """Alias for clarity."""

    pass
