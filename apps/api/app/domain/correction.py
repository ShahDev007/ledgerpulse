"""Field correction command (Section 4.5, 6.3 PATCH /fields).

Every correction is a labeled learning event, never a silent overwrite: it writes a
FeedbackLabel (predicted vs corrected), an audit event, and an outbox event, guarded by an
optimistic lock so concurrent edits 409 instead of clobbering.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import record_audit
from app.domain.normalize import normalize_invoice_number, parse_date, parse_decimal
from app.domain.outbox import emit
from app.models.ai_audit import FeedbackLabel
from app.models.invoice import Invoice

# field name -> (model attribute, coercer)
_EDITABLE = {
    "raw_vendor_name": ("raw_vendor_name", lambda v: v or None),
    "invoice_number": ("invoice_number", lambda v: v or None),
    "invoice_date": ("invoice_date", parse_date),
    "due_date": ("due_date", parse_date),
    "subtotal": ("subtotal", parse_decimal),
    "tax": ("tax", parse_decimal),
    "total": ("total", parse_decimal),
}


@dataclass
class CorrectionResult:
    field: str
    old_value: str | None
    new_value: str | None
    lock_version: int


async def apply_field_correction(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    field: str,
    value: str | None,
    expected_lock_version: int,
    actor_id: str | None,
) -> CorrectionResult:
    if field not in _EDITABLE:
        raise HTTPException(status_code=422, detail=f"Field '{field}' is not editable")

    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.lock_version != expected_lock_version:
        raise HTTPException(
            status_code=409,
            detail=f"Stale edit: expected lock_version {inv.lock_version}, got {expected_lock_version}",
        )

    attr, coerce = _EDITABLE[field]
    old = getattr(inv, attr)
    new = coerce(value)
    setattr(inv, attr, new)
    if field == "invoice_number":
        inv.invoice_number_normalized = normalize_invoice_number(new)

    session.add(
        FeedbackLabel(
            invoice_id=inv.id,
            field_name=field,
            predicted={"value": str(old) if old is not None else None},
            corrected={"value": str(new) if new is not None else None},
            corrected_by=uuid.UUID(actor_id) if actor_id else None,
        )
    )
    await record_audit(
        session,
        actor_type="USER",
        actor_id=actor_id,
        action="FIELD_CORRECTED",
        entity_type="INVOICE",
        entity_id=inv.id,
        entity_version=inv.lock_version,
        before={field: str(old) if old is not None else None},
        after={field: str(new) if new is not None else None},
        reason=f"Manual correction of {field}",
    )
    await emit(
        session,
        "invoice.field_corrected",
        {"invoice_id": str(inv.id), "field": field},
    )
    await session.commit()
    await session.refresh(inv)
    return CorrectionResult(
        field=field,
        old_value=str(old) if old is not None else None,
        new_value=str(new) if new is not None else None,
        lock_version=inv.lock_version,
    )
