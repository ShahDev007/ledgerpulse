"""Extraction command: run live Claude on the immutable original and persist the digital twin.

Writes header fields, line items, field-level provenance (page/bbox/confidence/model run), a
model_runs ledger row, and transitions the invoice to NEEDS_REVIEW - all inside one transaction
with an audit event (actor=MODEL) and an outbox event.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import record_audit
from app.domain.normalize import normalize_invoice_number, parse_date, parse_decimal
from app.domain.outbox import emit
from app.models.ai_audit import ModelRun
from app.models.enums import InvoiceStatus
from app.models.invoice import FieldProvenance, Invoice, InvoiceFile, InvoiceLineItem
from app.models.organization import Property
from app.models.vendor import Vendor
from app.storage import get_blob
from services.llm.gateway import ExtractionOutcome, extract_invoice

# rough per-model prices (USD per 1M tokens) for the model_runs cost estimate
_PRICES = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (15.0, 75.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


def _estimate_cost(model: str | None, tin: int | None, tout: int | None) -> float | None:
    if not model or tin is None or tout is None:
        return None
    pin, pout = _PRICES.get(model, (0.0, 0.0))
    return round(pin * tin / 1_000_000 + pout * tout / 1_000_000, 6)


def _field_conf(field) -> float:
    try:
        return float(field.confidence or 0)
    except Exception:
        return 0.0


async def _context(session: AsyncSession) -> tuple[list[str], list[str]]:
    props = (await session.execute(select(Property.name))).scalars().all()
    vendors = (await session.execute(select(Vendor.canonical_name))).scalars().all()
    return list(props), list(vendors)


async def run_extraction(
    session: AsyncSession, invoice_id: uuid.UUID, *, actor_id: str | None = None
) -> Invoice:
    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise ValueError("invoice not found")

    file_row = (
        await session.execute(
            select(InvoiceFile).where(
                InvoiceFile.invoice_id == invoice_id, InvoiceFile.is_original.is_(True)
            )
        )
    ).scalar_one_or_none()
    if file_row is None:
        raise ValueError("original file missing")

    inv.status = InvoiceStatus.EXTRACTING.value
    await session.flush()

    data = await get_blob(session, file_row.storage_key)
    props, vendors = await _context(session)

    # Claude call is blocking; run off the event loop.
    outcome: ExtractionOutcome = await asyncio.to_thread(
        extract_invoice, data, file_row.content_type, properties=props, vendors=vendors
    )
    ex = outcome.extraction
    run = outcome.run

    model_run = ModelRun(
        invoice_id=inv.id,
        capability="extract",
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        latency_ms=run.latency_ms,
        cost_usd=_estimate_cost(run.model, run.input_tokens, run.output_tokens),
        status=run.status,
        output=run.raw_output,
    )
    session.add(model_run)
    await session.flush()

    # --- Persist header fields ---
    inv.document_type = ex.document_type
    inv.is_credit_memo = ex.document_type == "credit_memo"
    inv.raw_vendor_name = (ex.vendor_name.value or inv.raw_vendor_name) if ex.vendor_name else inv.raw_vendor_name
    inv.invoice_number = ex.invoice_number.value if ex.invoice_number else None
    inv.invoice_number_normalized = normalize_invoice_number(inv.invoice_number)
    inv.property_hint_text = ex.property_hint.value if ex.property_hint else None
    inv.po_number_text = ex.purchase_order_number.value if ex.purchase_order_number else None
    inv.work_order_text = ex.work_order_number.value if ex.work_order_number else None
    inv.invoice_date = parse_date(ex.invoice_date.value) if ex.invoice_date else None
    inv.due_date = parse_date(ex.due_date.value) if ex.due_date else None
    inv.subtotal = parse_decimal(ex.subtotal.value) if ex.subtotal else None
    inv.tax = parse_decimal(ex.tax.value) if ex.tax else None
    inv.total = parse_decimal(ex.total.value) if ex.total else None
    if ex.currency and ex.currency.value:
        inv.currency = str(ex.currency.value)[:3].upper()

    # Overall extraction confidence: mean of the fields that matter most.
    key = [ex.vendor_name, ex.invoice_number, ex.invoice_date, ex.total]
    confs = [_field_conf(f) for f in key if f]
    inv.extraction_confidence = Decimal(str(round(sum(confs) / len(confs), 4))) if confs else Decimal("0")

    # --- Line items + provenance ---
    await session.execute(
        InvoiceLineItem.__table__.delete().where(InvoiceLineItem.invoice_id == inv.id)
    )
    for idx, ln in enumerate(ex.lines, start=1):
        session.add(
            InvoiceLineItem(
                invoice_id=inv.id,
                line_no=idx,
                description=ln.description.value if ln.description else None,
                quantity=parse_decimal(ln.quantity.value) if ln.quantity else None,
                unit_price=parse_decimal(ln.unit_price.value) if ln.unit_price else None,
                amount=parse_decimal(ln.amount.value) if ln.amount else None,
            )
        )

    await session.execute(
        FieldProvenance.__table__.delete().where(FieldProvenance.invoice_id == inv.id)
    )
    for name, field in {
        "vendor_name": ex.vendor_name,
        "invoice_number": ex.invoice_number,
        "invoice_date": ex.invoice_date,
        "due_date": ex.due_date,
        "subtotal": ex.subtotal,
        "tax": ex.tax,
        "total": ex.total,
    }.items():
        if field and field.value is not None:
            session.add(
                FieldProvenance(
                    invoice_id=inv.id,
                    field_name=name,
                    page=field.page,
                    bbox=list(field.bbox) if field.bbox else None,
                    extraction_method=f"{run.provider}:{run.model or 'mock'}",
                    model_run_id=model_run.id,
                    confidence=Decimal(str(round(_field_conf(field), 4))),
                    raw_text=field.raw_text,
                )
            )

    inv.status = InvoiceStatus.NEEDS_REVIEW.value

    await record_audit(
        session,
        actor_type="MODEL",
        actor_id=run.model or run.provider,
        action="EXTRACTION_COMPLETED",
        entity_type="INVOICE",
        entity_id=inv.id,
        entity_version=inv.lock_version,
        after={
            "vendor": inv.raw_vendor_name,
            "invoice_number": inv.invoice_number,
            "total": str(inv.total) if inv.total is not None else None,
            "confidence": str(inv.extraction_confidence),
            "provider": run.provider,
            "model": run.model,
        },
        reason=f"Extracted via {run.provider} ({run.status})",
        model_run_id=model_run.id,
    )
    await emit(
        session,
        "invoice.extraction_completed",
        {"invoice_id": str(inv.id), "status": inv.status, "provider": run.provider},
    )
    await session.commit()

    # Chain straight into resolution + matching + risk so the invoice lands in MATCHED or
    # EXCEPTION rather than sitting in NEEDS_REVIEW.
    from app.domain.pipeline import process_invoice

    return await process_invoice(session, inv.id)


async def run_extraction_standalone(invoice_id: uuid.UUID) -> None:
    """Entrypoint for the Celery worker (opens its own session)."""
    from app.db import SessionLocal

    async with SessionLocal() as session:
        await run_extraction(session, invoice_id)
