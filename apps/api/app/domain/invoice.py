"""Invoice intake command handler.

A single transactional command: store the immutable original in object storage, persist the
Invoice + InvoiceFile, and — in the same DB transaction — write the audit event and the outbox
event. This is the only way an invoice is created; status transitions go through commands, never
raw updates (Section 3.3).
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import record_audit
from app.domain.hashing import perceptual_hash, sha256_hex
from app.domain.outbox import emit
from app.ids import sid
from app.models.enums import InvoiceStatus, SourceType
from app.models.invoice import Invoice, InvoiceFile
from app.storage import put_blob

ORG_ID = sid("org:cadence-demo")


def _tracking_id() -> str:
    return "LP-" + secrets.token_hex(4).upper()


@dataclass
class IntakeResult:
    invoice_id: uuid.UUID
    tracking_id: str
    duplicate_of: uuid.UUID | None  # exact SHA-256 match already in the system


async def intake_invoice(
    session: AsyncSession,
    *,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    source_type: SourceType,
    source_external_id: str | None = None,
    raw_vendor_hint: str | None = None,
    property_hint: str | None = None,
    actor_id: str | None = None,
    request_id: str | None = None,
) -> IntakeResult:
    from sqlalchemy import select

    sha = sha256_hex(file_bytes)
    phash = perceptual_hash(file_bytes, content_type)

    # Exact-duplicate short-circuit: same bytes already stored. We still create the record
    # (so the event is tracked) but flag the prior match for the duplicate engine / UI.
    prior = (
        await session.execute(select(Invoice.id).where(Invoice.document_hash == sha).limit(1))
    ).scalar_one_or_none()

    invoice = Invoice(
        organization_id=ORG_ID,
        source_type=source_type.value,
        source_external_id=source_external_id,
        tracking_id=_tracking_id(),
        document_hash=sha,
        perceptual_hash=phash,
        raw_vendor_name=raw_vendor_hint,
        status=InvoiceStatus.RECEIVED.value,
    )
    session.add(invoice)
    await session.flush()  # assign invoice.id

    storage_key = f"invoices/{invoice.id}/original/{filename}"
    await put_blob(session, storage_key, file_bytes, content_type)

    file_row = InvoiceFile(
        invoice_id=invoice.id,
        storage_key=storage_key,
        content_type=content_type,
        byte_size=len(file_bytes),
        sha256=sha,
        perceptual_hash=phash,
        is_original=True,
    )
    session.add(file_row)

    await record_audit(
        session,
        actor_type="USER" if source_type != SourceType.EMAIL else "SYSTEM",
        actor_id=actor_id,
        action="INVOICE_RECEIVED",
        entity_type="INVOICE",
        entity_id=invoice.id,
        entity_version=invoice.lock_version,
        after={
            "tracking_id": invoice.tracking_id,
            "source_type": source_type.value,
            "document_hash": sha,
            "filename": filename,
        },
        reason=f"Intake via {source_type.value}",
        request_id=request_id,
    )
    await emit(
        session,
        "invoice.received",
        {
            "invoice_id": str(invoice.id),
            "tracking_id": invoice.tracking_id,
            "source_type": source_type.value,
            "document_hash": sha,
            "exact_duplicate_of": str(prior) if prior else None,
        },
    )
    await session.commit()

    return IntakeResult(
        invoice_id=invoice.id, tracking_id=invoice.tracking_id, duplicate_of=prior
    )
