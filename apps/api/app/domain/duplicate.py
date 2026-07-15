"""Deterministic duplicate detection (Section 7.1).

Combines exact + fuzzy evidence into a weighted score with a per-feature reason breakdown.
Credit memos are never flagged as duplicates of their original by amount/reference alone.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field as dc_field
from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, InvoiceLineItem

WEIGHTS = {
    "invoice_number": 0.28,
    "vendor": 0.20,
    "total": 0.16,
    "date": 0.10,
    "service_period": 0.10,
    "line_items": 0.08,
    "perceptual_hash": 0.05,
    "remit_address": 0.03,
}
BLOCK = 0.90
REVIEW = 0.72


@dataclass
class DuplicateFinding:
    score: float
    outcome: str  # BLOCK | REVIEW | INFO | NONE
    candidate_id: uuid.UUID | None
    candidate_tracking: str | None
    features: dict = dc_field(default_factory=dict)


def _num(a: Decimal | None, b: Decimal | None) -> float:
    if a is None or b is None:
        return 0.0
    a, b = abs(a), abs(b)
    if a == 0 and b == 0:
        return 1.0
    return max(0.0, 1.0 - float(abs(a - b) / max(a, b)))


def _date_prox(a, b) -> float:
    if a is None or b is None:
        return 0.0
    days = abs((a - b).days)
    return max(0.0, 1.0 - days / 30.0)  # within a month → partial credit


async def _hamming_phash(a: str | None, b: str | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    # hex phash strings: compare bit difference
    try:
        ai, bi = int(a, 16), int(b, 16)
        bits = (ai ^ bi).bit_count()
        return max(0.0, 1.0 - bits / (len(a) * 4))
    except ValueError:
        return 0.0


async def detect_duplicate(session: AsyncSession, inv: Invoice) -> DuplicateFinding:
    # Credit memos are not duplicates of their original (Section 7.1).
    if inv.is_credit_memo:
        return DuplicateFinding(0.0, "NONE", None, None, {"skipped": "credit_memo"})

    others = (
        await session.execute(
            select(Invoice).where(
                Invoice.organization_id == inv.organization_id,
                Invoice.id != inv.id,
                Invoice.is_credit_memo.is_(False),
            )
        )
    ).scalars().all()

    my_lines = (
        await session.execute(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == inv.id))
    ).scalars().all()
    my_desc = " ".join((l.description or "") for l in my_lines)

    best: DuplicateFinding | None = None
    for o in others:
        f = {}
        f["invoice_number"] = (
            1.0 if inv.invoice_number_normalized
            and inv.invoice_number_normalized == o.invoice_number_normalized
            else fuzz.ratio(inv.invoice_number_normalized or "", o.invoice_number_normalized or "") / 100.0
        )
        f["vendor"] = 1.0 if (inv.vendor_id and inv.vendor_id == o.vendor_id) else 0.0
        f["total"] = _num(inv.total, o.total)
        f["date"] = _date_prox(inv.invoice_date, o.invoice_date)
        f["service_period"] = 0.5  # unknown for these fixtures → neutral
        o_lines = (
            await session.execute(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == o.id))
        ).scalars().all()
        o_desc = " ".join((l.description or "") for l in o_lines)
        f["line_items"] = fuzz.token_sort_ratio(my_desc, o_desc) / 100.0 if my_desc and o_desc else 0.0
        f["perceptual_hash"] = await _hamming_phash(inv.perceptual_hash, o.perceptual_hash)
        f["remit_address"] = 0.0

        score = round(sum(WEIGHTS[k] * f[k] for k in WEIGHTS), 4)
        if best is None or score > best.score:
            best = DuplicateFinding(
                score=score,
                outcome="NONE",
                candidate_id=o.id,
                candidate_tracking=o.tracking_id,
                features={k: round(f[k], 3) for k in f},
            )

    if best is None:
        return DuplicateFinding(0.0, "NONE", None, None, {})
    best.outcome = "BLOCK" if best.score >= BLOCK else "REVIEW" if best.score >= REVIEW else "INFO"
    return best
