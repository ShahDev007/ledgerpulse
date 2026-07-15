"""Copilot domain: build a permission-filtered data context, answer, log the model run."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal
from app.models.ai_audit import ModelRun
from app.models.invoice import Invoice
from app.models.workflow import Exception_
from services.llm.copilot import answer_question
import asyncio


async def run_copilot(session: AsyncSession, principal: Principal, question: str) -> dict:
    # ABAC: property-scoped users only see their properties (+ unresolved). Sensitive fields
    # (tax id, bank) are never included in the context.
    q = select(Invoice).order_by(Invoice.created_at.desc())
    if principal.property_scope:
        q = q.where(
            (Invoice.property_id.in_(principal.property_scope)) | (Invoice.property_id.is_(None))
        )
    invs = (await session.execute(q)).scalars().all()
    inv_ids = [i.id for i in invs]

    excs = (
        await session.execute(
            select(Exception_).where(
                Exception_.invoice_id.in_(inv_ids), Exception_.resolution_status == "OPEN"
            )
        )
    ).scalars().all() if inv_ids else []
    exc_by_inv = {}
    for e in excs:
        exc_by_inv.setdefault(e.invoice_id, []).append(e.issue_type)

    context = {
        "invoices": [
            {
                "tracking_id": i.tracking_id,
                "vendor": i.resolved_vendor_name or i.raw_vendor_name,
                "property": i.resolved_property_name,
                "invoice_number": i.invoice_number,
                "invoice_date": str(i.invoice_date),
                "due_date": str(i.due_date),
                "total": float(i.total) if i.total is not None else None,
                "currency": i.currency,
                "status": i.status,
                "payment_status": i.payment_status,
                "risk_flags": i.risk_flags or [],
                "open_exceptions": exc_by_inv.get(i.id, []),
            }
            for i in invs
        ],
    }

    outcome = await asyncio.to_thread(answer_question, question, context)

    session.add(ModelRun(
        capability="copilot", provider=outcome.provider, model=outcome.model,
        prompt_version="copilot-v1", input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens, latency_ms=outcome.latency_ms,
        status=outcome.status, output=outcome.result,
    ))
    await session.commit()

    return {
        "question": question,
        "result": outcome.result,
        "model": outcome.model,
        "tokens": {"in": outcome.input_tokens, "out": outcome.output_tokens},
        "latency_ms": outcome.latency_ms,
        "context_size": len(context["invoices"]),
        "status": outcome.status,
    }
