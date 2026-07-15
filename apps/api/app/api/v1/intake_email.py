"""Simulated AP-email intake.

Represents the dedicated AP mailbox (invoices@…): a vendor 'emails' a PDF and the sender
receives an acknowledgment with the tracking id (Section 2.4 step 1). In production a
Microsoft Graph / Gmail poller would call this same command; here an endpoint stands in so the
demo can show the acknowledgment land in Mailpit. Message-id gives idempotency via the unique
(org, source_type, source_external_id) constraint.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.domain.invoice import intake_invoice
from app.models.enums import SourceType
from app.models.invoice import Invoice
from app.notifications import send_notification

router = APIRouter(tags=["intake"])

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/heic", "image/webp"}


class EmailIntakeOut(BaseModel):
    invoice_id: str
    tracking_id: str
    acknowledged_to: str


@router.post("/intake/email", response_model=EmailIntakeOut, status_code=201)
async def email_intake(
    from_address: str = Form(...),
    subject: str = Form(default=""),
    message_id: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    # Idempotency: same message-id → return the existing invoice, don't double-create.
    existing = (
        await session.execute(
            select(Invoice).where(Invoice.source_external_id == message_id).limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return EmailIntakeOut(
            invoice_id=str(existing.id),
            tracking_id=existing.tracking_id,
            acknowledged_to=from_address,
        )

    data = await file.read()
    ctype = file.content_type or "application/octet-stream"
    if ctype not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {ctype}")

    result = await intake_invoice(
        session,
        file_bytes=data,
        filename=file.filename or "email-attachment.pdf",
        content_type=ctype,
        source_type=SourceType.EMAIL,
        source_external_id=message_id,
        raw_vendor_hint=None,
    )

    # Acknowledgment email back to the sender (lands in Mailpit). intake_invoice already
    # committed the invoice; this records + sends the ack in its own transaction.
    await send_notification(
        session,
        to_address=from_address,
        subject=f"Received: {subject or 'your invoice'} [{result.tracking_id}]",
        body=(
            f"Thank you — your invoice has been received and assigned tracking id "
            f"{result.tracking_id}. You can reference this id in any correspondence.\n\n"
            f"— LedgerPulse AP intake"
        ),
        kind="ACK",
        invoice_id=result.invoice_id,
    )
    await session.commit()

    return EmailIntakeOut(
        invoice_id=str(result.invoice_id),
        tracking_id=result.tracking_id,
        acknowledged_to=from_address,
    )
