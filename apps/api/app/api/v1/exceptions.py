"""Exception queue (feeds the exception cockpit; investigator agent lands in Phase 6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import get_session
from app.models.invoice import Invoice
from app.models.workflow import Exception_

router = APIRouter(tags=["exceptions"])


class ExceptionRow(BaseModel):
    id: str
    invoice_id: str
    tracking_id: str
    category: str
    issue_type: str
    severity: str
    summary: str | None
    owner_role: str | None
    status: str
    due_at: str | None


@router.get("/exceptions", response_model=list[ExceptionRow])
async def list_exceptions(
    status: str = "OPEN",
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    q = (
        select(Exception_, Invoice.tracking_id)
        .join(Invoice, Exception_.invoice_id == Invoice.id)
        .order_by(Exception_.created_at.desc())
    )
    if status:
        q = q.where(Exception_.resolution_status == status)
    rows = (await session.execute(q)).all()
    return [
        ExceptionRow(
            id=str(e.id),
            invoice_id=str(e.invoice_id),
            tracking_id=tid,
            category=e.category,
            issue_type=e.issue_type,
            severity=e.severity,
            summary=e.summary,
            owner_role=e.owner_role,
            status=e.resolution_status,
            due_at=e.due_at.isoformat() if e.due_at else None,
        )
        for e, tid in rows
    ]
