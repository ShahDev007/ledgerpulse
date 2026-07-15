"""Deterministic demo reset: drop + recreate schema, reseed master data + policies, then
intake + live-extract + run the pipeline on all 8 demo invoices.

    python -m app.demo_reset
"""
from __future__ import annotations

import asyncio

from app.bootstrap import main as bootstrap_main
from app.seed_invoices import seed_invoices


async def main() -> None:
    await bootstrap_main(reset=True)          # schema + master data + personas + policies
    await seed_invoices(extract=True)          # 8 invoices → extraction → resolution/matching/risk
    print("[demo-reset] complete - 8 invoices intaken, extracted, and matched")


if __name__ == "__main__":
    asyncio.run(main())
