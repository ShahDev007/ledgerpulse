"""One-time deploy bootstrap endpoints (token-guarded).

Serverless can't run a persistent bootstrap process, so these do it on demand and in chunks that
each stay under the function time limit:
  POST /admin/bootstrap        → create schema + seed master data/policies + intake 8 invoices
  POST /admin/process/{key}    → extract + run the pipeline on ONE invoice (INV-001..008)
  GET  /admin/status           → quick counts

Guard with header  X-Admin-Token: <ADMIN_TOKEN>.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Base, engine, get_session
from app.models.invoice import Invoice

router = APIRouter(tags=["admin"])


def _require_admin(x_admin_token: str | None) -> None:
    if not x_admin_token or x_admin_token != get_settings().admin_token:
        raise HTTPException(status_code=401, detail="bad admin token")


@router.post("/admin/bootstrap")
async def bootstrap(
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    _require_admin(x_admin_token)
    import app.models  # noqa: F401  register tables
    from app.seed import seed
    from app.seed_invoices import seed_invoices

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed(reset=False)                 # org/properties/vendors/GL/commercial/users/policies
    await seed_invoices(extract=False)      # intake the 8 documents (no extraction yet)

    n = (await session.execute(select(func.count()).select_from(Invoice))).scalar_one()
    return {"ok": True, "invoices": int(n),
            "next": "POST /v1/admin/process/INV-001 … INV-008 to extract + match each"}


@router.post("/admin/process/{key}")
async def process_one(
    key: str,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    _require_admin(x_admin_token)
    from app.domain.extraction import run_extraction

    inv = (
        await session.execute(select(Invoice).where(Invoice.source_external_id == key))
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail=f"no invoice for key {key}")
    inv = await run_extraction(session, inv.id)
    return {"key": key, "tracking_id": inv.tracking_id, "status": inv.status,
            "vendor": inv.resolved_vendor_name, "total": str(inv.total),
            "risk_flags": inv.risk_flags}


@router.get("/admin/status")
async def status(
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    _require_admin(x_admin_token)
    rows = (await session.execute(select(Invoice.status, func.count()).group_by(Invoice.status))).all()
    return {"by_status": {s: int(c) for s, c in rows}}
