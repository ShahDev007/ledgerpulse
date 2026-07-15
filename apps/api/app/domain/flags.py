"""Helpers to record explainable match results and open exceptions."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_audit import MatchResult
from app.models.workflow import Exception_


def add_match_result(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    kind: str,
    outcome: str,
    score: float | None = None,
    reasons: dict | None = None,
    related_id: uuid.UUID | None = None,
) -> MatchResult:
    mr = MatchResult(
        invoice_id=invoice_id,
        kind=kind,
        outcome=outcome,
        score=score,
        reasons=reasons or {},
        related_id=related_id,
    )
    session.add(mr)
    return mr


def open_exception(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    category: str,
    issue_type: str,
    severity: str,
    summary: str,
    owner_role: str,
    evidence: dict | None = None,
    sla_hours: int = 48,
) -> Exception_:
    exc = Exception_(
        invoice_id=invoice_id,
        category=category,
        issue_type=issue_type,
        severity=severity,
        summary=summary,
        owner_role=owner_role,
        evidence=evidence or {},
        resolution_status="OPEN",
        due_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=sla_hours),
    )
    session.add(exc)
    return exc
