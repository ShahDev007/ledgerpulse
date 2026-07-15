"""One-shot bootstrap run before the API serves: wait for Postgres, create schema, seed.

Kept deterministic and idempotent so `make dev` needs no manual database steps. The
Alembic migration path (make migrate) is the production alternative to create_all.
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.db import engine, Base
import app.models  # noqa: F401  (register all tables on Base.metadata)
from app.storage import ensure_bucket
from app.seed import seed


async def _wait_for_db(max_tries: int = 30) -> None:
    for attempt in range(1, max_tries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[bootstrap] waiting for db ({attempt}/{max_tries}): {exc}")
            await asyncio.sleep(2)
    raise SystemExit("[bootstrap] database not reachable")


async def _create_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)


async def main(reset: bool = False) -> None:
    await _wait_for_db()
    if reset:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await _create_schema()
    try:
        ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        print(f"[bootstrap] storage bucket init skipped: {exc}")
    await seed(reset=reset)
    print("[bootstrap] ready")


if __name__ == "__main__":
    asyncio.run(main(reset="--reset" in sys.argv))
