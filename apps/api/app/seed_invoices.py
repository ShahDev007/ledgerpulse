"""Seed the 8 demo invoices: render → intake (immutable) → live Claude extraction.

Idempotent on the invoice source_external_id (= spec key). Run after master-data seed:
    python -m app.seed_invoices              # intake only
    python -m app.seed_invoices --extract    # intake + run live extraction
    python -m app.seed_invoices --only INV-001 --extract
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.demo_invoices import SPECS, SPEC_BY_KEY, render_png
from app.domain.extraction import run_extraction
from app.domain.invoice import intake_invoice
from app.models.enums import SourceType
from app.models.invoice import Invoice

EMAIL_KEYS = {"INV-001", "INV-007"}  # arrive via the AP mailbox; rest via upload


async def seed_invoices(*, extract: bool = False, only: str | None = None) -> None:
    specs = [SPEC_BY_KEY[only]] if only else SPECS
    async with SessionLocal() as session:
        for spec in specs:
            existing = (
                await session.execute(
                    select(Invoice).where(Invoice.source_external_id == spec.key).limit(1)
                )
            ).scalar_one_or_none()
            if existing:
                inv_id = existing.id
                print(f"[seed-inv] {spec.key} exists ({existing.tracking_id})")
            else:
                png = render_png(spec)
                src = SourceType.EMAIL if spec.key in EMAIL_KEYS else SourceType.UPLOAD
                result = await intake_invoice(
                    session,
                    file_bytes=png,
                    filename=f"{spec.key}.png",
                    content_type="image/png",
                    source_type=src,
                    source_external_id=spec.key,
                    raw_vendor_hint=None,
                )
                inv_id = result.invoice_id
                print(f"[seed-inv] {spec.key} intaken -> {result.tracking_id}")

            if extract:
                inv = await run_extraction(session, inv_id)
                print(
                    f"           extracted: vendor={inv.raw_vendor_name!r} "
                    f"number={inv.invoice_number!r} total={inv.total} "
                    f"conf={inv.extraction_confidence}"
                )


if __name__ == "__main__":
    args = sys.argv[1:]
    only = None
    if "--only" in args:
        only = args[args.index("--only") + 1]
    asyncio.run(seed_invoices(extract="--extract" in args, only=only))
