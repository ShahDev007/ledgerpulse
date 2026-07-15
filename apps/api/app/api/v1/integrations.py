"""Export + payment-sync endpoints (Integration Service surface)."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import get_session
from app.domain.export import export_invoice
from app.domain.payment import ingest_payment

router = APIRouter(tags=["integrations"])


class ExportOut(BaseModel):
    ok: bool
    external_id: str | None
    status: str
    retryable: bool
    error: str | None


@router.post("/invoices/{invoice_id}/export", response_model=ExportOut)
async def export(
    invoice_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("export")
    r = await export_invoice(session, invoice_id, actor_id=str(principal.user_id))
    return ExportOut(ok=r.ok, external_id=r.external_id, status=r.status,
                     retryable=r.retryable, error=r.error)


class PaymentIn(BaseModel):
    amount: float
    reference: str = "SIM-PAYMENT"


class PaymentOut(BaseModel):
    payment_status: str
    invoice_status: str
    reconciled: bool
    mismatch: bool


@router.post("/invoices/{invoice_id}/simulate-payment", response_model=PaymentOut)
async def simulate_payment(
    invoice_id: uuid.UUID,
    body: PaymentIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Simulate ingesting a payment-status update from the ERP (reconcile or mismatch)."""
    principal.require("export")
    r = await ingest_payment(
        session, invoice_id, amount=Decimal(str(body.amount)), reference=body.reference,
        actor_id=str(principal.user_id),
    )
    return PaymentOut(payment_status=r.payment_status, invoice_status=r.invoice_status,
                      reconciled=r.reconciled, mismatch=r.mismatch)
