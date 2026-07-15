"""Best-effort email via the local Mailpit SMTP sink. Also persists a Notification row.

Used for AP intake acknowledgments (Section 2.4 step 1) and later reminders/digests.
Failures are swallowed — a mail hiccup must never fail an intake command.
"""
from __future__ import annotations

import smtplib
import uuid
from email.message import EmailMessage

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.workflow import Notification


def _send_smtp(to_address: str, subject: str, body: str) -> bool:
    s = get_settings()
    try:
        msg = EmailMessage()
        msg["From"] = s.ap_inbox_address
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=5) as smtp:
            smtp.send_message(msg)
        return True
    except Exception:
        return False


async def send_notification(
    session: AsyncSession,
    *,
    to_address: str,
    subject: str,
    body: str,
    kind: str,
    invoice_id: uuid.UUID | None = None,
) -> None:
    sent = _send_smtp(to_address, subject, body)
    import datetime as dt

    session.add(
        Notification(
            invoice_id=invoice_id,
            to_address=to_address,
            subject=subject,
            body=body,
            kind=kind,
            sent_at=dt.datetime.now(dt.timezone.utc) if sent else None,
        )
    )
