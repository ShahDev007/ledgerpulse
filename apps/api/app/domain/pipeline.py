"""Post-extraction pipeline: resolve → duplicate → commercial match → risk → status.

Deterministic engines produce explainable MatchResults + Exceptions; the invoice lands in
MATCHED (clean) or EXCEPTION (something needs a human), never auto-approved.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import record_audit
from app.domain.duplicate import detect_duplicate
from app.domain.flags import add_match_result, open_exception
from app.domain.matching import match_commercial
from app.domain.outbox import emit
from app.domain.resolution import resolve_invoice
from app.domain.risk import compute_risk
from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.models.workflow import Exception_


async def process_invoice(session: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise ValueError("invoice not found")

    # Clear any prior open exceptions/match results (idempotent re-run)
    await session.execute(
        Exception_.__table__.update()
        .where(Exception_.invoice_id == inv.id, Exception_.resolution_status == "OPEN")
        .values(resolution_status="SUPERSEDED")
    )

    # 1) Resolution
    resolution = await resolve_invoice(session, inv)
    add_match_result(session, inv.id, kind="resolution", outcome="MATCH" if resolution.vendor_resolved else "REVIEW",
                     score=resolution.vendor_confidence, reasons=resolution.reasons)
    if not resolution.vendor_resolved:
        open_exception(
            session, inv.id, category="IDENTITY", issue_type="UNKNOWN_VENDOR",
            severity="REVIEW", owner_role="AP_ACCOUNTANT",
            summary=f"Vendor '{inv.raw_vendor_name}' could not be resolved to master data",
            evidence=resolution.reasons.get("vendor", {}),
        )

    # 2) Duplicate detection
    dup = await detect_duplicate(session, inv)
    add_match_result(session, inv.id, kind="duplicate", outcome=dup.outcome, score=dup.score,
                     reasons={"features": dup.features, "candidate": dup.candidate_tracking},
                     related_id=dup.candidate_id)
    if dup.outcome in ("BLOCK", "REVIEW"):
        open_exception(
            session, inv.id, category="FINANCIAL", issue_type="POSSIBLE_DUPLICATE",
            severity="BLOCKING" if dup.outcome == "BLOCK" else "REVIEW",
            owner_role="AP_ACCOUNTANT",
            summary=f"Possible duplicate of {dup.candidate_tracking} (score {dup.score})",
            evidence={"score": dup.score, "features": dup.features, "candidate": dup.candidate_tracking},
        )

    # 3) Commercial matching
    findings = await match_commercial(session, inv)
    for f in findings:
        add_match_result(session, inv.id, kind=f.kind, outcome=f.outcome, reasons=f.reasons)
        if f.creates_exception and f.outcome in ("REVIEW", "BLOCK"):
            open_exception(
                session, inv.id, category=f.category, issue_type=f.issue_type,
                severity=f.severity, owner_role=f.owner_role, summary=f.summary, evidence=f.reasons,
            )

    # 4) Risk
    score, flags = compute_risk(inv, resolution, dup, findings)
    inv.risk_score = Decimal(str(score))
    inv.risk_flags = flags

    # 5) Status
    open_excs = (
        await session.execute(
            select(Exception_).where(
                Exception_.invoice_id == inv.id, Exception_.resolution_status == "OPEN"
            )
        )
    ).scalars().all()
    has_blocking = any(e.severity == "BLOCKING" for e in open_excs)
    inv.status = InvoiceStatus.EXCEPTION.value if open_excs else InvoiceStatus.MATCHED.value

    await record_audit(
        session, actor_type="RULE", actor_id="match-engine",
        action="MATCH_COMPLETED", entity_type="INVOICE", entity_id=inv.id,
        entity_version=inv.lock_version,
        after={"status": inv.status, "risk_score": str(inv.risk_score), "risk_flags": flags,
               "exceptions": [e.issue_type for e in open_excs], "blocking": has_blocking},
        reason=f"{len(open_excs)} exception(s); duplicate={dup.outcome}",
    )
    await emit(session, "invoice.match_completed",
               {"invoice_id": str(inv.id), "status": inv.status, "exceptions": len(open_excs)})
    for e in open_excs:
        await emit(session, "invoice.exception_opened",
                   {"invoice_id": str(inv.id), "issue_type": e.issue_type, "severity": e.severity})

    await session.commit()
    await session.refresh(inv)
    return inv
