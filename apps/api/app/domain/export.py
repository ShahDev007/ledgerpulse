"""Export command: idempotent export of an APPROVED invoice to the ERP.

Enforces: only APPROVED invoices export; one export per (invoice, version, target) via a unique
idempotency key + export ledger; retryable vs permanent failures are recorded distinctly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import record_audit
from app.domain.outbox import emit
from app.models.enums import ExportStatus, InvoiceStatus
import os

from app.models.finance import Export
from app.models.invoice import Invoice

TARGET = "mock-erp"


def _adapter():
    if os.getenv("ERP_MODE", "http").lower() == "inprocess":
        from services.integrations.inprocess_erp import InProcessErpAdapter

        return InProcessErpAdapter()
    from services.integrations.mock_erp import MockErpAdapter

    return MockErpAdapter()


@dataclass
class ExportOutcome:
    ok: bool
    external_id: str | None
    status: str
    retryable: bool
    error: str | None


def _idem_key(inv: Invoice) -> str:
    return f"{inv.id}:{inv.version}:{TARGET}"


async def export_invoice(
    session: AsyncSession, invoice_id: uuid.UUID, *, actor_id: str | None = None
) -> ExportOutcome:
    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status not in (InvoiceStatus.APPROVED.value, InvoiceStatus.EXPORTED.value):
        raise HTTPException(status_code=409, detail=f"Only APPROVED invoices can export (status {inv.status})")

    idem = _idem_key(inv)
    existing = (
        await session.execute(select(Export).where(Export.idempotency_key == idem))
    ).scalar_one_or_none()
    if existing and existing.status == ExportStatus.EXPORTED.value:
        return ExportOutcome(True, existing.external_id, existing.status, False, None)

    adapter = _adapter()
    payload = {
        "invoice_id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "invoice_version": inv.version,
        "total": float(inv.total) if inv.total is not None else None,
        "vendor": inv.resolved_vendor_name or inv.raw_vendor_name,
        "property": inv.resolved_property_name,
    }
    result = adapter.export_invoice(payload, idem)

    row = existing or Export(
        invoice_id=inv.id, invoice_version=inv.version, target_system=TARGET, idempotency_key=idem
    )
    if result.ok:
        row.external_id = result.external_id
        row.status = ExportStatus.EXPORTED.value
        row.error = None
        inv.export_status = ExportStatus.EXPORTED.value
        inv.status = InvoiceStatus.EXPORTED.value
    else:
        row.status = ExportStatus.FAILED.value
        row.error = result.error
        inv.export_status = ExportStatus.FAILED.value
    if existing is None:
        session.add(row)

    await record_audit(
        session, actor_type="INTEGRATION", actor_id=TARGET,
        action="EXPORT_SUCCEEDED" if result.ok else "EXPORT_FAILED",
        entity_type="INVOICE", entity_id=inv.id, entity_version=inv.lock_version,
        after={"external_id": result.external_id, "status": row.status,
               "retryable": result.retryable, "error": result.error},
        reason=f"Export to {TARGET}",
    )
    await emit(
        session,
        "invoice.export_succeeded" if result.ok else "invoice.export_failed",
        {"invoice_id": str(inv.id), "external_id": result.external_id, "retryable": result.retryable},
    )
    await session.commit()
    return ExportOutcome(result.ok, result.external_id, row.status, result.retryable, result.error)
