"""Operational analytics: command-center KPIs and per-property cost view."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import get_session
from app.models.ai_audit import ModelRun
from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.models.organization import Property
from app.models.workflow import Exception_

router = APIRouter(tags=["analytics"])


class Stats(BaseModel):
    total_invoices: int
    by_status: dict[str, int]
    open_exceptions: int
    blocking_exceptions: int
    approval_pending: int
    duplicate_risk: int
    total_exposure: float
    unbudgeted_flags: int


@router.get("/stats", response_model=Stats)
async def stats(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    # ABAC: property-scoped roles (e.g. Property Manager) see only their properties'
    # invoices - plus not-yet-resolved ones - exactly like the inbox list. Org-wide roles
    # (AP, Finance, Asset, Auditor) have no scope and see everything.
    inv_q = select(Invoice)
    if principal.property_scope:
        inv_q = inv_q.where(
            (Invoice.property_id.in_(principal.property_scope)) | (Invoice.property_id.is_(None))
        )
    invs = (await session.execute(inv_q)).scalars().all()
    scoped_ids = [i.id for i in invs]
    by_status: dict[str, int] = {}
    exposure = Decimal("0")
    dup = 0
    unbudget = 0
    for i in invs:
        by_status[i.status] = by_status.get(i.status, 0) + 1
        if i.total and i.status not in (
            InvoiceStatus.PAID.value, InvoiceStatus.RECONCILED.value,
            InvoiceStatus.REJECTED.value, InvoiceStatus.VOIDED.value,
        ):
            exposure += i.total
        flags = i.risk_flags or []
        if "POSSIBLE_DUPLICATE" in flags:
            dup += 1
        if "UNBUDGETED_SPEND" in flags or "OVER_BUDGET" in flags:
            unbudget += 1

    # Count exceptions only for the invoices this persona can see.
    open_q = select(func.count()).select_from(Exception_).where(
        Exception_.resolution_status == "OPEN", Exception_.invoice_id.in_(scoped_ids)
    )
    blocking_q = select(func.count()).select_from(Exception_).where(
        Exception_.resolution_status == "OPEN", Exception_.severity == "BLOCKING",
        Exception_.invoice_id.in_(scoped_ids),
    )
    open_exc = (await session.execute(open_q)).scalar_one() if scoped_ids else 0
    blocking = (await session.execute(blocking_q)).scalar_one() if scoped_ids else 0

    return Stats(
        total_invoices=len(invs),
        by_status=by_status,
        open_exceptions=int(open_exc),
        blocking_exceptions=int(blocking),
        approval_pending=by_status.get(InvoiceStatus.APPROVAL_PENDING.value, 0),
        duplicate_risk=dup,
        total_exposure=float(exposure),
        unbudgeted_flags=unbudget,
    )


@router.get("/model-runs")
async def model_runs(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """AI usage/quality dashboard: per-capability runs, tokens, latency, cost."""
    principal.require("view_model_trace")
    runs = (await session.execute(select(ModelRun))).scalars().all()
    agg: dict[str, dict] = {}
    for r in runs:
        a = agg.setdefault(r.capability, {"runs": 0, "input_tokens": 0, "output_tokens": 0,
                                          "latency_ms": 0, "cost_usd": 0.0, "errors": 0,
                                          "providers": set()})
        a["runs"] += 1
        a["input_tokens"] += r.input_tokens or 0
        a["output_tokens"] += r.output_tokens or 0
        a["latency_ms"] += r.latency_ms or 0
        a["cost_usd"] += float(r.cost_usd or 0)
        a["errors"] += int(r.status != "OK")
        if r.model:
            a["providers"].add(f"{r.provider}/{r.model}")
    out = []
    for cap, a in agg.items():
        out.append({
            "capability": cap, "runs": a["runs"],
            "input_tokens": a["input_tokens"], "output_tokens": a["output_tokens"],
            "avg_latency_ms": round(a["latency_ms"] / a["runs"]) if a["runs"] else 0,
            "cost_usd": round(a["cost_usd"], 4), "errors": a["errors"],
            "models": sorted(a["providers"]),
        })
    return {"by_capability": sorted(out, key=lambda x: -x["runs"]),
            "total_runs": len(runs),
            "total_cost_usd": round(sum(x["cost_usd"] for x in out), 4)}


class PropertyCost(BaseModel):
    property_id: str
    property_name: str
    invoice_count: int
    total_spend: float
    by_vendor: dict[str, float]


@router.get("/analytics/property/{property_id}", response_model=PropertyCost)
async def property_cost(
    property_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    prop = await session.get(Property, property_id)
    invs = (
        await session.execute(select(Invoice).where(Invoice.property_id == property_id))
    ).scalars().all()
    by_vendor: dict[str, float] = {}
    total = 0.0
    for i in invs:
        if i.total:
            v = i.resolved_vendor_name or i.raw_vendor_name or "Unknown"
            by_vendor[v] = by_vendor.get(v, 0.0) + float(i.total)
            total += float(i.total)
    return PropertyCost(
        property_id=str(property_id),
        property_name=prop.name if prop else "",
        invoice_count=len(invs),
        total_spend=total,
        by_vendor=by_vendor,
    )
