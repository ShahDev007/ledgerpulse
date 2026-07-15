"""Exception investigator command: assemble a read-only evidence snapshot, run the tool-scoped
Claude agent, and persist the model run + tool calls + cited findings on the exception.

The agent never touches the database - it only sees the snapshot we build here - so it is
structurally incapable of mutating financial records (Section 4.3).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import record_audit
from app.domain.outbox import emit
from app.models.ai_audit import MatchResult, ModelRun, ToolCall
from app.models.commercial import Contract, ContractRate, PurchaseOrder, WorkOrder
from app.models.finance import Budget, BudgetLine
from app.models.invoice import FieldProvenance, Invoice, InvoiceLineItem
from app.models.vendor import Vendor
from app.models.workflow import ApprovalPolicy, Exception_
import asyncio

from services.llm.investigator import investigate


async def _snapshot(session: AsyncSession, inv: Invoice) -> dict:
    """Build the read-only evidence bundle the agent's tools return from."""
    snap: dict = {}

    lines = (
        await session.execute(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == inv.id))
    ).scalars().all()
    snap["get_invoice"] = {
        "evidence_id": "ev:invoice",
        "tracking_id": inv.tracking_id,
        "vendor_raw": inv.raw_vendor_name,
        "vendor_resolved": inv.resolved_vendor_name,
        "invoice_number": inv.invoice_number,
        "invoice_date": str(inv.invoice_date),
        "due_date": str(inv.due_date),
        "total": str(inv.total),
        "currency": inv.currency,
        "is_credit_memo": inv.is_credit_memo,
        "property": inv.resolved_property_name,
        "status": inv.status,
        "risk_flags": inv.risk_flags,
        "lines": [
            {"description": l.description, "qty": str(l.quantity), "unit_price": str(l.unit_price),
             "amount": str(l.amount)} for l in lines
        ],
    }

    prov = (
        await session.execute(select(FieldProvenance).where(FieldProvenance.invoice_id == inv.id))
    ).scalars().all()
    snap["get_document_evidence"] = {
        "evidence_id": "ev:document",
        "fields": [
            {"field": p.field_name, "page": p.page, "bbox": p.bbox,
             "confidence": str(p.confidence)} for p in prov
        ],
    }

    dup = (
        await session.execute(
            select(MatchResult).where(MatchResult.invoice_id == inv.id, MatchResult.kind == "duplicate")
        )
    ).scalar_one_or_none()
    snap["search_duplicate_candidates"] = {
        "evidence_id": "ev:duplicate",
        "outcome": dup.outcome if dup else "NONE",
        "score": str(dup.score) if dup and dup.score is not None else None,
        "reasons": dup.reasons if dup else {},
    }

    if inv.vendor_id:
        others = (
            await session.execute(
                select(Invoice).where(Invoice.vendor_id == inv.vendor_id, Invoice.id != inv.id)
            )
        ).scalars().all()
        snap["get_vendor_history"] = {
            "evidence_id": "ev:vendor_history",
            "vendor": inv.resolved_vendor_name,
            "invoices": [
                {"tracking_id": o.tracking_id, "invoice_number": o.invoice_number,
                 "total": str(o.total), "date": str(o.invoice_date), "status": o.status}
                for o in others
            ],
        }
    else:
        snap["get_vendor_history"] = {"evidence_id": "ev:vendor_history",
                                      "note": "vendor unresolved - no history"}

    if inv.purchase_order_id:
        po = await session.get(PurchaseOrder, inv.purchase_order_id)
        snap["get_purchase_order"] = {"evidence_id": "ev:po", "number": po.number,
                                      "amount": str(po.amount), "open_amount": str(po.open_amount),
                                      "status": po.status}
    else:
        snap["get_purchase_order"] = {"evidence_id": "ev:po", "note": "no linked PO"}

    if inv.contract_id:
        contract = await session.get(Contract, inv.contract_id)
        rates = (
            await session.execute(select(ContractRate).where(ContractRate.contract_id == contract.id))
        ).scalars().all()
        snap["get_contract"] = {
            "evidence_id": "ev:contract", "number": contract.number,
            "ceiling": str(contract.ceiling),
            "rates": [{"description": r.description, "unit_rate": str(r.unit_rate),
                       "tolerance_pct": str(r.tolerance_pct)} for r in rates],
        }
    else:
        snap["get_contract"] = {"evidence_id": "ev:contract", "note": "no linked contract"}

    if inv.work_order_id:
        wo = await session.get(WorkOrder, inv.work_order_id)
        snap["get_work_order"] = {"evidence_id": "ev:work_order", "number": wo.number,
                                  "status": wo.status, "description": wo.description}
    else:
        snap["get_work_order"] = {"evidence_id": "ev:work_order", "note": "no linked work order"}

    if inv.property_id:
        bl = (
            await session.execute(
                select(BudgetLine).join(Budget, BudgetLine.budget_id == Budget.id).where(
                    Budget.property_id == inv.property_id
                )
            )
        ).scalars().all()
        remaining = sum(
            (b.revised_budget or Decimal("0")) - (b.committed or Decimal("0")) - (b.actual or Decimal("0"))
            for b in bl
        )
        snap["get_budget_status"] = {
            "evidence_id": "ev:budget",
            "budget_lines": len(bl),
            "remaining": str(remaining),
        }
    else:
        snap["get_budget_status"] = {"evidence_id": "ev:budget", "note": "no property resolved"}

    snap["get_approval_policy"] = {"evidence_id": "ev:policy",
                                   "note": "policy resolved at submission time"}
    return snap


async def run_investigation(
    session: AsyncSession, invoice_id: uuid.UUID, *, actor_id: str | None = None
) -> dict:
    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise ValueError("invoice not found")

    exc = (
        await session.execute(
            select(Exception_).where(
                Exception_.invoice_id == inv.id, Exception_.resolution_status == "OPEN"
            ).order_by(Exception_.created_at.desc())
        )
    ).scalars().first()
    if exc is None:
        raise ValueError("no open exception to investigate")

    snap = await _snapshot(session, inv)
    outcome = await asyncio.to_thread(investigate, snap, exc.issue_type, exc.summary or "")

    model_run = ModelRun(
        invoice_id=inv.id, capability="investigator", provider=outcome.provider,
        model=outcome.model, prompt_version="investigator-v1",
        input_tokens=outcome.input_tokens, output_tokens=outcome.output_tokens,
        latency_ms=outcome.latency_ms, status=outcome.status, output=outcome.result,
    )
    session.add(model_run)
    await session.flush()
    for tc in outcome.tool_calls:
        session.add(ToolCall(model_run_id=model_run.id, tool_name=tc.tool_name,
                             result_summary=tc.result_summary, allowed=tc.allowed))

    # Store findings on the exception (read-only recommendation; does not resolve it).
    evidence = dict(exc.evidence or {})
    evidence["investigation"] = outcome.result
    exc.evidence = evidence

    await record_audit(
        session, actor_type="MODEL", actor_id=outcome.model or "investigator",
        action="EXCEPTION_INVESTIGATED", entity_type="INVOICE", entity_id=inv.id,
        entity_version=inv.lock_version,
        after={"issue_type": exc.issue_type,
               "recommended_action": (outcome.result or {}).get("recommended_action"),
               "tool_calls": [t.tool_name for t in outcome.tool_calls]},
        reason="Read-only investigator agent",
        model_run_id=model_run.id,
    )
    await emit(session, "invoice.exception_investigated",
               {"invoice_id": str(inv.id), "issue_type": exc.issue_type})
    await session.commit()

    return {
        "issue_type": exc.issue_type,
        "result": outcome.result,
        "tool_calls": [{"tool": t.tool_name, "allowed": t.allowed} for t in outcome.tool_calls],
        "model": outcome.model,
        "tokens": {"in": outcome.input_tokens, "out": outcome.output_tokens},
        "latency_ms": outcome.latency_ms,
        "status": outcome.status,
    }
