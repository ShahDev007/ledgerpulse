"""Payment ingestion + reconciliation.

Simulates ingesting a payment-status update from the ERP after export. Full payment reconciles
the invoice to the terminal RECONCILED state; a mismatch opens a PAYMENT exception and leaves the
invoice in a MISMATCH payment state (never silently closed).
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import record_audit
from app.domain.flags import open_exception
from app.domain.outbox import emit
from app.models.enums import InvoiceStatus, PaymentStatus
from app.models.finance import Payment
from app.models.invoice import Invoice


@dataclass
class PaymentOutcome:
    payment_status: str
    invoice_status: str
    reconciled: bool
    mismatch: bool


async def ingest_payment(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    amount: Decimal,
    reference: str,
    actor_id: str | None = None,
) -> PaymentOutcome:
    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status not in (InvoiceStatus.EXPORTED.value, InvoiceStatus.PAYMENT_SCHEDULED.value,
                          InvoiceStatus.PAID.value):
        raise HTTPException(status_code=409, detail=f"Invoice not exported yet (status {inv.status})")

    now = dt.datetime.now(dt.timezone.utc)
    total = inv.total or Decimal("0")
    matched = abs(amount - total) <= Decimal("0.01")

    payment = Payment(
        invoice_id=inv.id, amount=amount, reference=reference, paid_at=now,
        status=PaymentStatus.PAID.value if matched else PaymentStatus.MISMATCH.value,
    )

    if matched:
        payment.reconciled_at = now
        inv.payment_status = PaymentStatus.PAID.value
        inv.status = InvoiceStatus.RECONCILED.value  # terminal
        reconciled, mismatch = True, False
    else:
        inv.payment_status = PaymentStatus.MISMATCH.value
        inv.status = InvoiceStatus.PAID.value  # paid but not reconciled
        open_exception(
            session, inv.id, category="PAYMENT", issue_type="PAYMENT_MISMATCH",
            severity="REVIEW", owner_role="FINANCE_ADMIN",
            summary=f"Paid {amount} does not match invoice total {total} (diff {amount - total})",
            evidence={"paid": str(amount), "invoice_total": str(total), "reference": reference},
        )
        reconciled, mismatch = False, True

    session.add(payment)
    await record_audit(
        session, actor_type="INTEGRATION", actor_id="mock-erp",
        action="PAYMENT_RECONCILED" if matched else "PAYMENT_MISMATCH",
        entity_type="INVOICE", entity_id=inv.id, entity_version=inv.lock_version,
        after={"amount": str(amount), "reference": reference, "status": inv.status,
               "payment_status": inv.payment_status},
        reason="Payment status ingested from ERP",
    )
    await emit(session, "payment.status_updated",
               {"invoice_id": str(inv.id), "matched": matched, "amount": str(amount)})
    if matched:
        await emit(session, "invoice.reconciled", {"invoice_id": str(inv.id)})
    await session.commit()
    return PaymentOutcome(
        payment_status=inv.payment_status, invoice_status=inv.status,
        reconciled=reconciled, mismatch=mismatch,
    )
