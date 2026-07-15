"""Vendor + property resolution: exact alias first, Claude reasoning second (no embeddings).

Writes vendor_id / property_id / resolution_confidence and, when a vendor cannot be resolved,
signals an IDENTITY exception (handled by the pipeline).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.organization import Property
from app.models.vendor import Vendor, VendorAlias
from services.llm.gateway import resolve_entity


@dataclass
class ResolutionOutcome:
    vendor_resolved: bool
    property_resolved: bool
    vendor_confidence: float
    property_confidence: float
    reasons: dict


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


async def _vendor_candidates(session: AsyncSession) -> list[dict]:
    vendors = (await session.execute(select(Vendor))).scalars().all()
    aliases: dict[uuid.UUID, list[str]] = {}
    for a in (await session.execute(select(VendorAlias))).scalars().all():
        aliases.setdefault(a.vendor_id, []).append(a.alias)
    return [
        {"id": str(v.id), "name": v.canonical_name, "aliases": aliases.get(v.id, []), "_v": v}
        for v in vendors
    ]


async def resolve_invoice(session: AsyncSession, inv: Invoice) -> ResolutionOutcome:
    reasons: dict = {}

    # --- Vendor ---
    v_conf = 0.0
    v_resolved = False
    raw_vendor = inv.raw_vendor_name or ""
    cands = await _vendor_candidates(session)
    exact = None
    for c in cands:
        names = [c["name"]] + c["aliases"]
        if _norm(raw_vendor) in {_norm(n) for n in names}:
            exact = c
            break
    if exact:
        inv.vendor_id = uuid.UUID(exact["id"])
        inv.resolved_vendor_name = exact["name"]
        v_conf, v_resolved = 0.99, True
        reasons["vendor"] = {"method": "exact_alias", "matched": exact["name"], "confidence": 0.99}
    elif raw_vendor:
        r = resolve_entity(raw_vendor, [{k: c[k] for k in ("id", "name", "aliases")} for c in cands], kind="vendor")
        if r.match_id:
            match = next((c for c in cands if c["id"] == r.match_id), None)
            inv.vendor_id = uuid.UUID(r.match_id)
            inv.resolved_vendor_name = match["name"] if match else None
            v_conf, v_resolved = r.confidence, r.confidence >= 0.7
            reasons["vendor"] = {"method": "claude", "matched": inv.resolved_vendor_name,
                                 "confidence": r.confidence, "reason": r.reason}
        else:
            reasons["vendor"] = {"method": "claude", "matched": None, "confidence": r.confidence,
                                 "reason": r.reason}
    inv.resolution_confidence = None if v_conf == 0 else round(v_conf, 4)

    # --- Property (exact name/address match, Claude fallback) ---
    p_conf = 0.0
    p_resolved = False
    hint = _norm(inv.property_hint_text)
    props = (await session.execute(select(Property))).scalars().all()
    pmatch = None
    for p in props:
        if hint and (_norm(p.name) in hint or hint in _norm(p.name)):
            pmatch = p
            break
    if pmatch is None and inv.property_hint_text:
        pr = resolve_entity(
            inv.property_hint_text,
            [{"id": str(p.id), "name": p.name, "aliases": [p.address or ""]} for p in props],
            kind="property",
        )
        if pr.match_id:
            pmatch = next((p for p in props if str(p.id) == pr.match_id), None)
            p_conf = pr.confidence
    if pmatch is not None:
        inv.property_id = pmatch.id
        inv.legal_entity_id = pmatch.legal_entity_id
        inv.resolved_property_name = pmatch.name
        p_conf = p_conf or 0.99
        p_resolved = True
        reasons["property"] = {"matched": pmatch.name, "confidence": p_conf}
    else:
        reasons["property"] = {"matched": None, "confidence": p_conf}

    return ResolutionOutcome(
        vendor_resolved=v_resolved, property_resolved=p_resolved,
        vendor_confidence=v_conf, property_confidence=p_conf, reasons=reasons,
    )
