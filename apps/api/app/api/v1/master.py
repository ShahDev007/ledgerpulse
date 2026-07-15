"""Read-only master-data endpoints (properties, vendors, GL) — proves seed + authz."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import get_session
from app.models.finance import GLAccount
from app.models.organization import Property
from app.models.vendor import Vendor

router = APIRouter(tags=["master-data"])


class PropertyOut(BaseModel):
    id: str
    name: str
    code: str | None
    address: str | None


class VendorOut(BaseModel):
    id: str
    canonical_name: str
    status: str


class GLOut(BaseModel):
    id: str
    code: str
    name: str
    default_capex_opex: str | None


@router.get("/properties", response_model=list[PropertyOut])
async def properties(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    q = select(Property).order_by(Property.name)
    # ABAC: property-scoped users only see their properties (None = all)
    if principal.property_scope:
        q = q.where(Property.id.in_(principal.property_scope))
    rows = (await session.execute(q)).scalars().all()
    return [PropertyOut(id=str(p.id), name=p.name, code=p.code, address=p.address) for p in rows]


@router.get("/vendors", response_model=list[VendorOut])
async def vendors(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    rows = (await session.execute(select(Vendor).order_by(Vendor.canonical_name))).scalars().all()
    return [VendorOut(id=str(v.id), canonical_name=v.canonical_name, status=v.status) for v in rows]


@router.get("/gl-accounts", response_model=list[GLOut])
async def gl_accounts(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    rows = (await session.execute(select(GLAccount).order_by(GLAccount.code))).scalars().all()
    return [
        GLOut(id=str(g.id), code=g.code, name=g.name, default_capex_opex=g.default_capex_opex)
        for g in rows
    ]
