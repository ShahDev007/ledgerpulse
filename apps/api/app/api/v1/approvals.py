"""Approval workflow endpoints: submit, decide, and 'my queue'."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import get_session
from app.domain.approval import decide_step, submit_for_approval
from app.models.invoice import Invoice
from app.models.workflow import ApprovalRequest, ApprovalStep

router = APIRouter(tags=["approvals"])


class SubmitOut(BaseModel):
    request_id: str
    policy: str
    steps: list[dict]


@router.post("/invoices/{invoice_id}/submit", response_model=SubmitOut)
async def submit(
    invoice_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("edit")
    r = await submit_for_approval(session, invoice_id, submitter_id=principal.user_id)
    return SubmitOut(request_id=str(r.request_id), policy=r.policy, steps=r.steps)


class DecisionIn(BaseModel):
    decision: str  # APPROVED | REJECTED | REQUEST_INFO
    reason: str | None = None


class DecisionOut(BaseModel):
    step_no: int
    decision: str
    invoice_status: str


@router.post("/approvals/{step_id}/decision", response_model=DecisionOut)
async def decide(
    step_id: uuid.UUID,
    body: DecisionIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("approve")
    r = await decide_step(
        session, step_id, approver_id=principal.user_id, decision=body.decision, reason=body.reason
    )
    return DecisionOut(step_no=r.step_no, decision=r.decision, invoice_status=r.invoice_status)


class QueueRow(BaseModel):
    step_id: str
    invoice_id: str
    tracking_id: str
    vendor: str | None
    total: float | None
    currency: str
    required_role: str
    step_no: int
    due_at: str | None


@router.get("/approvals", response_model=list[QueueRow])
async def my_queue(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Pending approval steps assigned to the current principal."""
    principal.require("view")
    q = (
        select(ApprovalStep, Invoice)
        .join(ApprovalRequest, ApprovalStep.request_id == ApprovalRequest.id)
        .join(Invoice, ApprovalRequest.invoice_id == Invoice.id)
        .where(
            ApprovalStep.status == "PENDING",
            ApprovalStep.resolved_approver_id == principal.user_id,
        )
        .order_by(ApprovalStep.due_at.asc())
    )
    rows = (await session.execute(q)).all()
    return [
        QueueRow(
            step_id=str(s.id),
            invoice_id=str(inv.id),
            tracking_id=inv.tracking_id,
            vendor=inv.resolved_vendor_name or inv.raw_vendor_name,
            total=float(inv.total) if inv.total is not None else None,
            currency=inv.currency,
            required_role=s.required_role,
            step_no=s.step_no,
            due_at=s.due_at.isoformat() if s.due_at else None,
        )
        for s, inv in rows
    ]
