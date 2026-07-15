"""Approval workflow commands: submit (build steps from policy) and decide.

Controls enforced: submitter-cannot-approve, role + property scope on each step, idempotent
decisions, SLA due dates, and a blocking-exception gate before submission.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import record_audit
from app.domain.outbox import emit
from app.domain.policy import resolve_steps, select_policy
from app.models.enums import InvoiceStatus
from app.models.identity import User
from app.notifications import send_notification
from app.models.invoice import Invoice
from app.models.workflow import (
    ApprovalRequest,
    ApprovalStep,
    Exception_,
)


async def _find_approver(
    session: AsyncSession, role: str, inv: Invoice, exclude_user_id: uuid.UUID | None
) -> User | None:
    users = (
        await session.execute(select(User).where(User.role == role, User.active.is_(True)))
    ).scalars().all()
    for u in users:
        if exclude_user_id and u.id == exclude_user_id:
            continue  # submitter_cannot_approve
        if u.property_scope and inv.property_id and inv.property_id not in u.property_scope:
            continue  # ABAC scope
        return u
    return None


@dataclass
class SubmitResult:
    request_id: uuid.UUID
    policy: str
    steps: list[dict]


async def submit_for_approval(
    session: AsyncSession, invoice_id: uuid.UUID, *, submitter_id: uuid.UUID
) -> SubmitResult:
    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Blocking exceptions must be resolved before an approval workflow can start.
    blocking = (
        await session.execute(
            select(Exception_).where(
                Exception_.invoice_id == inv.id,
                Exception_.resolution_status == "OPEN",
                Exception_.severity == "BLOCKING",
            )
        )
    ).scalars().first()
    if blocking:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit: blocking exception {blocking.issue_type} must be resolved first",
        )

    # Idempotency: reuse an existing pending request.
    existing = (
        await session.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.invoice_id == inv.id, ApprovalRequest.status == "PENDING"
            )
        )
    ).scalar_one_or_none()
    if existing:
        steps = (
            await session.execute(
                select(ApprovalStep).where(ApprovalStep.request_id == existing.id).order_by(ApprovalStep.step_no)
            )
        ).scalars().all()
        return SubmitResult(existing.id, existing.policy_name, [{"step_no": s.step_no, "role": s.required_role} for s in steps])

    policy = await select_policy(session, inv)
    controls = policy.get("controls", {})
    escalation_hours = int(controls.get("escalation_after_hours", 48))
    step_specs = resolve_steps(policy, inv)

    req = ApprovalRequest(
        invoice_id=inv.id,
        policy_name=policy["policy"],
        policy_version=int(policy.get("version", 1)),
        status="PENDING",
        submitted_by=submitter_id,
    )
    session.add(req)
    await session.flush()

    now = dt.datetime.now(dt.timezone.utc)
    out_steps = []
    for spec in step_specs:
        approver = await _find_approver(session, spec["role"], inv, submitter_id)
        step = ApprovalStep(
            request_id=req.id,
            step_no=spec["step_no"],
            required_role=spec["role"],
            scope_ref=str(inv.property_id) if spec.get("scope") else None,
            resolved_approver_id=approver.id if approver else None,
            status="PENDING",
            due_at=now + dt.timedelta(hours=escalation_hours),
        )
        session.add(step)
        out_steps.append({"step_no": spec["step_no"], "role": spec["role"],
                          "approver": approver.full_name if approver else None})
        if approver is None:
            # No eligible approver → APPROVAL exception (Section 3.4)
            session.add(
                Exception_(
                    invoice_id=inv.id, category="APPROVAL", issue_type="NO_ELIGIBLE_APPROVER",
                    severity="REVIEW", summary=f"No eligible {spec['role']} approver found",
                    owner_role="FINANCE_ADMIN", resolution_status="OPEN",
                    due_at=now + dt.timedelta(hours=escalation_hours),
                )
            )
        elif approver.email:
            await send_notification(
                session, to_address=approver.email,
                subject=f"Approval needed: {inv.tracking_id} ({inv.currency} {inv.total})",
                body=f"Invoice {inv.tracking_id} requires your approval as {spec['role']}.",
                kind="REMINDER", invoice_id=inv.id,
            )

    inv.status = InvoiceStatus.APPROVAL_PENDING.value

    await record_audit(
        session, actor_type="USER", actor_id=str(submitter_id),
        action="SUBMITTED_FOR_APPROVAL", entity_type="INVOICE", entity_id=inv.id,
        entity_version=inv.lock_version,
        after={"policy": policy["policy"], "steps": [s["role"] for s in step_specs]},
        reason=f"Policy {policy['policy']} v{req.policy_version}",
    )
    await emit(session, "approval.requested",
               {"invoice_id": str(inv.id), "request_id": str(req.id), "policy": policy["policy"]})
    await session.commit()
    return SubmitResult(req.id, policy["policy"], out_steps)


@dataclass
class DecisionResult:
    step_no: int
    decision: str
    invoice_status: str


async def decide_step(
    session: AsyncSession,
    step_id: uuid.UUID,
    *,
    approver_id: uuid.UUID,
    decision: str,
    reason: str | None,
) -> DecisionResult:
    step = await session.get(ApprovalStep, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Approval step not found")
    if step.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Step already {step.status}")

    # Only the resolved approver may decide (delegation could widen this in future).
    if step.resolved_approver_id and step.resolved_approver_id != approver_id:
        raise HTTPException(status_code=403, detail="You are not the assigned approver for this step")

    req = await session.get(ApprovalRequest, step.request_id)
    inv = await session.get(Invoice, req.invoice_id)
    if req.submitted_by == approver_id:
        raise HTTPException(status_code=403, detail="Submitter cannot approve their own invoice")

    now = dt.datetime.now(dt.timezone.utc)
    step.decided_by = approver_id
    step.decided_at = now
    step.reason = reason

    if decision == "REJECTED":
        step.status = "REJECTED"
        step.decision = "REJECTED"
        req.status = "REJECTED"
        inv.status = InvoiceStatus.REJECTED.value
    elif decision == "REQUEST_INFO":
        step.decision = "REQUEST_INFO"  # stays PENDING
        step.decided_at = None
    elif decision == "APPROVED":
        step.status = "APPROVED"
        step.decision = "APPROVED"
        remaining = (
            await session.execute(
                select(ApprovalStep).where(
                    ApprovalStep.request_id == req.id, ApprovalStep.status == "PENDING",
                    ApprovalStep.id != step.id,
                )
            )
        ).scalars().all()
        if not remaining:
            req.status = "APPROVED"
            inv.status = InvoiceStatus.APPROVED.value
    else:
        raise HTTPException(status_code=422, detail=f"Unknown decision '{decision}'")

    await record_audit(
        session, actor_type="USER", actor_id=str(approver_id),
        action="APPROVAL_DECIDED", entity_type="INVOICE", entity_id=inv.id,
        entity_version=inv.lock_version,
        after={"step": step.step_no, "role": step.required_role, "decision": decision,
               "invoice_status": inv.status},
        reason=reason,
    )
    await emit(session, "approval.decided",
               {"invoice_id": str(inv.id), "step": step.step_no, "decision": decision})
    if inv.status == InvoiceStatus.APPROVED.value:
        await emit(session, "invoice.approved", {"invoice_id": str(inv.id)})
    await session.commit()
    return DecisionResult(step_no=step.step_no, decision=decision, invoice_status=inv.status)
